"""This model shows an example of using dgl.metapath_reachable_graph on the original heterogeneous
graph.

Because the original HAN implementation only gives the preprocessed homogeneous graph, this model
could not reproduce the result in HAN as they did not provide the preprocessing code, and we
constructed another dataset from ACM with a different set of papers, connections, features and
labels.
"""
import os
# EARLY STOP FIX (2026-10-08): per-fold checkpoint selection metadata.
import json
from shutil import rmtree

import gc
import torch
import numpy as np
from sklearn.model_selection import KFold
from tqdm import tqdm

from sco_models.graph_utils import read_gpickle
from sco_models.utils import score, get_classification_report, get_confusion_matrix
from sco_models.tools import EarlyStopping
from sco_models.visualization import visualize_average_k_folds, visualize_k_folds
from sco_models.classifier_cli import (
    build_node_parser,
    ensure_output_parent,
    finalize_node_args,
    validate_paths,
)


def get_binary_mask(total_size, indices):
    mask = torch.zeros(total_size)
    mask[indices] = 1
    return mask.byte()


def get_node_ids(graph, source_files):
    file_ids = []
    for node_ids, node_data in graph.nodes(data=True):
        filename = node_data['source_file']
        if filename in source_files:
            file_ids.append(node_ids)
    return file_ids


def get_node_ids_by_source_path(graph, source_paths):
    file_ids = []
    for node_ids, node_data in graph.nodes(data=True):
        filename = node_data['source_file']
        if filename in source_paths:
            file_ids.append(int(node_ids))
    return file_ids


def get_all_source_paths(graph):
    source_paths = []
    for _, node_data in graph.nodes(data=True):
        # print(node_data)
        file_path = node_data['source_file']
        source_paths.append(file_path)
    return list(set(source_paths))


# ============================================================================
# ADDED: snippet-deduplicated fold splitting.
# Everything between this marker and "END ADDED" is new; deleting it and passing
# --split_by contract both restore the original contract-level behaviour.
#
# Why: the corpus repeats code. SolidiFI injects a handful of bug templates into
# many host contracts, so the line-level graph holds 12,036 nodes drawn from only
# 3,077 distinct snippets, and one template occurs 322 times across 40 files, always
# with the same label. Node features are a deterministic function of the code, so
# those 322 nodes share one feature vector. Splitting folds by contract keeps a
# contract's nodes together but lets a snippet sit on both sides: 76.5% of validation
# nodes appear in their own training fold with identical code AND identical label. A
# lookup table over (code -> majority label) scores 98.69 Buggy-F1 on that split,
# against 98.98 for the full model - i.e. no measurable gain over memorisation.
#
# Splitting by snippet removes that path. The trade-off is real and worth stating:
# nodes of one contract may now land on both sides, so graph neighbours leak instead.
# Keeping both leak types out at once is impossible here - the 322-occurrence snippet
# spans 40 of 71 contracts, so isolating it would consume more than half the corpus.
# ============================================================================
def build_snippet_folds(nx_graph, node_labels, k_folds, seed):
    """Yield (train_node_ids, val_node_ids) where no code snippet crosses the split.

    Each distinct snippet is one group; StratifiedGroupKFold keeps a group whole while
    still balancing the buggy/clean ratio across folds.
    """
    from sklearn.model_selection import StratifiedGroupKFold

    node_ids = sorted(nx_graph.nodes())
    snippet_of = {}
    groups = []
    for n in node_ids:
        code = nx_graph.nodes[n].get('code') or ''
        if code not in snippet_of:
            snippet_of[code] = len(snippet_of)
        groups.append(snippet_of[code])
    y = [int(bool(nx_graph.nodes[n].get('node_info_vulnerabilities'))) for n in node_ids]

    print('Snippet-deduplicated split: {} nodes over {} distinct snippets'.format(
        len(node_ids), len(snippet_of)))
    splitter = StratifiedGroupKFold(n_splits=k_folds, shuffle=True, random_state=seed)
    for train_idx, val_idx in splitter.split(node_ids, y, groups):
        yield ([node_ids[i] for i in train_idx], [node_ids[i] for i in val_idx])


def report_snippet_overlap(nx_graph, train_ids, val_ids, fold):
    """State how much of the validation fold the model has already seen verbatim."""
    code = {n: (nx_graph.nodes[n].get('code') or '') for n in nx_graph.nodes()}
    label = {n: bool(nx_graph.nodes[n].get('node_info_vulnerabilities'))
             for n in nx_graph.nodes()}
    train_pairs = {(code[n], label[n]) for n in train_ids}
    seen = sum(1 for n in val_ids if (code[n], label[n]) in train_pairs)
    pct = 100.0 * seen / max(len(val_ids), 1)
    print('Fold {}: {}/{} validation nodes ({:.1f}%) share an exact (code, label) '
          'pair with the training fold'.format(fold, seen, len(val_ids), pct))
    return seen, len(val_ids)
# ============================================================================
# END ADDED
# ============================================================================


def main(args):
    from sco_models.model_hgt import HGTVulNodeClassifier

    epochs = args['num_epochs']
    k_folds = args['k_folds']
    device = args['device']
    # FOLD SEED FIX (2026-10-09): original code retained for rollback.
    # kfold = KFold(n_splits=k_folds, shuffle=True)
    # FOLD SEED FIX: without random_state the shuffle draws from numpy's global RNG,
    # which --seed never touches, so every run got different folds.
    kfold = KFold(n_splits=k_folds, shuffle=True, random_state=args['seed'])
    train_results = {}
    val_results = {'buggy_f1_folds': [], 'macro_f1_folds': []}
    # Get feature extractor
    print('Getting features')
    if args['node_feature'] == 'han':
        feature_extractor = HGTVulNodeClassifier(args['feature_compressed_graph'], feature_extractor=args['cfg_feature_extractor'], node_feature='gae', device=args['device'])
        feature_extractor.load_state_dict(torch.load(args['feature_extractor']))
        feature_extractor.to(args['device'])
        feature_extractor.eval()
    else:
        feature_extractor = args['feature_extractor']

    nx_graph = read_gpickle(args['compressed_graph'])
    number_of_nodes = len(nx_graph)
    model = HGTVulNodeClassifier(args['compressed_graph'], feature_extractor=feature_extractor, node_feature=args['node_feature'], device=device)

    # total_train_files = [f for f in os.listdir(args['dataset']) if f.endswith('.sol')]
    # total_test_files = [f for f in os.listdir(args['testset']) if f.endswith('.sol')]
    # total_train_files = list(set(total_train_files).difference(set(total_test_files)))
    # # clean_smart_contract = './ge-sc-data/smartbugs_wild/clean_50'
    # # total_clean_files = [f for f in os.listdir(clean_smart_contract) if f.endswith('.sol')]
    # total_clean_files = []
    # total_train_files = list(set(total_train_files).difference(set(total_clean_files)))

    # FOLD SEED FIX (2026-10-09): original code retained for rollback.
    # total_train_files = get_all_source_paths(model.nx_graph)
    # FOLD SEED FIX: get_all_source_paths returns list(set(...)), whose order changes
    # with string hashing between processes; sort it so a seed maps to one fold list.
    total_train_files = sorted(get_all_source_paths(model.nx_graph))
    total_test_files = []
    # web3bugs_files = ['yVault.sol', 'ERC721Payable.sol', 'HybridPool.sol', 'MarginRouter.sol']
    # for f in web3bugs_files:
    #     total_train_files.remove(f)
    total_clean_files = []

    # # Train valid split data
    # train_rate = 0.7
    # val_rate = 0.15
    # test_rate = 0.15
    # rand_train_ids = torch.randperm(len(total_train_files)).tolist()
    # rand_test_ids = torch.randperm(len(total_test_files)).tolist()
    # rand_clean_ids = torch.randperm(len(total_clean_files)).tolist()

    # train_size_0 = int(train_rate * len(total_train_files))
    # train_size_1 = int(train_rate * len(total_test_files))
    # train_size_2 = int(train_rate * len(total_clean_files))
    # train_files = [total_train_files[i] for i in rand_train_ids[:train_size_0]] + \
    #               [total_test_files[i] for i in rand_test_ids[:train_size_1]] + \
    #               [total_clean_files[i] for i in rand_clean_ids[:train_size_2]]
    # print('Buggy train files: ', [total_train_files[i] for i in rand_train_ids[:train_size_0]])
    # print('Curated train files: ', [total_test_files[i] for i in rand_test_ids[:train_size_1]])

    # val_size_0 = int(val_rate * len(total_train_files))
    # val_size_1 = int(val_rate * len(total_test_files))
    # val_size_2 = int(val_rate * len(total_clean_files))
    # val_files = [total_train_files[i] for i in rand_train_ids[train_size_0:train_size_0 + val_size_0]] + \
    #             [total_test_files[i] for i in rand_test_ids[train_size_1:train_size_1 + val_size_1]] + \
    #             [total_clean_files[i] for i in rand_clean_ids[train_size_2:train_size_2 + val_size_2]]
    # print('Buggy valid files: ', [total_train_files[i] for i in rand_train_ids[train_size_0:train_size_0 + val_size_0]])
    # print('Curated valid files: ', [total_test_files[i] for i in rand_test_ids[train_size_1:train_size_1 + val_size_1]])
    # test_files = [total_train_files[i] for i in rand_train_ids[train_size_0 + val_size_0:]] + \
    #              [total_test_files[i] for i in rand_test_ids[train_size_1 + val_size_1:]] + \
    #              [total_clean_files[i] for i in rand_clean_ids[train_size_2 + val_size_2:]]
    # print('Buggy test files: ', [total_train_files[i] for i in rand_train_ids[train_size_0 + val_size_0:]])
    # print('Curated test files: ', [total_test_files[i] for i in rand_test_ids[train_size_1 + val_size_1:]])

    # assert len(train_files) + len(val_files) + len(test_files) == len(total_train_files) + len(total_test_files) + len(total_clean_files)

    print('Label dict: ', model.label_ids)
    # total_test_files is hard-coded empty above, so the old "Buggy/Curated: 142/0"
    # wording described a split that does not exist: every contract in the graph goes
    # into the k-fold rotation and the held-out set is produced per fold.
    print('Contracts in graph: {} (all enter the {}-fold rotation)'.format(
        len(total_train_files), args['k_folds']))
    # total_train_ids = get_node_ids(nx_graph, total_train_files)
    # train_ids = get_node_ids(nx_graph, train_files)
    # val_ids = get_node_ids(nx_graph, val_files)
    # test_ids = get_node_ids(nx_graph, test_files)



    # train_ids = get_node_ids_by_source_path(nx_graph, train_files)
    # val_ids = get_node_ids_by_source_path(nx_graph, val_files)
    # test_ids = get_node_ids_by_source_path(nx_graph, test_files)
    # web3bugs_ids = get_node_ids_by_source_path(nx_graph, web3bugs_files)

    targets = torch.tensor(model.node_labels, device=args['device'])    
    # assert len(set(train_ids) | set(val_ids) | set(test_ids)) == len(targets)
    # assert len(set(train_ids) | set(val_ids) | set(test_ids) | set(web3bugs_ids)) == len(targets)

    buggy_node_ids = torch.nonzero(targets).squeeze().tolist()
    print('Buggy node {}/{} ({}%)'.format(len(set(buggy_node_ids)), len(targets), 100*len(set(buggy_node_ids))/len(targets)))
    # ===== ADDED: pick the fold source. --split_by contract reproduces the original =====
    if args.get('split_by') == 'snippet':
        fold_source = build_snippet_folds(nx_graph, model.node_labels, k_folds, args['seed'])
    else:
        fold_source = (
            (get_node_ids_by_source_path(nx_graph, [total_train_files[i] for i in tr]),
             get_node_ids_by_source_path(nx_graph, [total_train_files[i] for i in va]))
            for tr, va in kfold.split(total_train_files)
        )
    overlap_seen, overlap_total = 0, 0
    # ===== END ADDED =====

    for fold, (train_ids, val_ids) in enumerate(fold_source):
        # train_files/val_files are only used for the fold banner below; under a
        # snippet split a contract can appear on both sides, which the banner states.
        train_files = sorted({nx_graph.nodes[n]['source_file'] for n in train_ids})
        val_files = sorted({nx_graph.nodes[n]['source_file'] for n in val_ids})
        s, t = report_snippet_overlap(nx_graph, train_ids, val_ids, fold)
        overlap_seen += s
        overlap_total += t
        # Init model 
        
        # fold = 0
        model.to('cpu')
        del model
        gc.collect()
        torch.cuda.empty_cache()
        model = HGTVulNodeClassifier(args['compressed_graph'], feature_extractor=feature_extractor, node_feature=args['node_feature'], device=device)
        # model.reset_parameters()
        model.to(device)
        train_results[fold] = {'loss': [], 'acc': [], 'micro_f1': [], 'macro_f1': [], 'buggy_f1': [], 'lrs': []}
        val_results[fold] = {'loss': [], 'acc': [], 'micro_f1': [], 'macro_f1': [], 'buggy_f1': []}
        train_buggy_node_ids = set(buggy_node_ids).intersection(set(train_ids))
        print('Buggy nodes in train: {}/{} ({}%)'.format(len(train_buggy_node_ids), len(train_ids), 100*len(train_buggy_node_ids)/len(train_ids)))
        val_buggy_node_ids = set(buggy_node_ids).intersection(set(val_ids))
        print('Buggy nodes in valid: {}/{} ({}%)'.format(len(val_buggy_node_ids), len(val_ids), 100*len(val_buggy_node_ids)/len(val_ids)))
        # test_buggy_node_ids =set(buggy_node_ids).intersection(set(test_ids))
        # print('Buggy nodes in test: {}/{} ({}%)'.format(len(test_buggy_node_ids), len(test_ids), 100*len(test_buggy_node_ids)/len(test_ids)))
        # train_ids/val_ids are node ids, not contracts: the fold is split over
        # contracts and then expanded to their nodes, so the two counts differ by
        # orders of magnitude. Report both instead of labelling nodes as contracts.
        print('Start training fold {}: {}/{} train/val contracts, {}/{} train/val nodes'.format(
            fold, len(train_files), len(val_files), len(train_ids), len(val_ids)))
        total_steps = epochs
        # class_counter = [len(labeled_node_ids['valid']), len(labeled_node_ids['buggy'])]
        # class_weight = torch.tensor([1 - sample/len(class_counter) for sample in class_counter], requires_grad=False).to(args['device'])
        # Don't record the following operation in autograd
        # with torch.no_grad():
        #     loss_weights.copy_(initial_weights)
        loss_fcn = torch.nn.CrossEntropyLoss()
        # Paper Sec. 5.3 gives the LR bounds, not an exact schedule. Keep OneCycle
        # and return to the stated lower bound instead of decaying below it.
        optimizer = torch.optim.Adam(model.parameters(), lr=args['lr'])
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer, max_lr=0.005, total_steps=total_steps,
            div_factor=0.005 / args['lr'], final_div_factor=1.0)
        early_stopping = EarlyStopping(patience=args['patience'], delta=0.001, verbose=True)
        print('Training settings: patience={}, delta=0.001, LR={:.6g} -> 0.005 -> {:.6g}, '
              'OneCycle per optimizer update'.format(
                  args['patience'], optimizer.param_groups[0]['lr'], args['lr']), flush=True)
        train_mask = get_binary_mask(number_of_nodes, train_ids)
        val_mask = get_binary_mask(number_of_nodes, val_ids)
        # test_mask = get_binary_mask(number_of_nodes, test_ids)
        # web3bugs_mask = get_binary_mask(number_of_nodes, web3bugs_ids)
        if hasattr(torch, 'BoolTensor'):
            train_mask = train_mask.bool()
            val_mask = val_mask.bool()
            # test_mask = test_mask.bool()
        retain_graph = True if args['node_feature'] == 'han' else False
        stop_epoch = epochs
        # None until early stopping actually fires. The old code initialised this to 0
        # and printed it unconditionally, so a fold that ran to completion still
        # reported "Early stopping at epoch 0".
        early_stopped_at = None
        last_epoch = -1
        # EARLY STOP FIX (2026-10-08): original code retained for rollback.
        # checkpoint_path = args['output_models']
        checkpoint_dir = os.path.splitext(args['output_models'])[0] + '_fold{}'.format(fold)
        os.makedirs(checkpoint_dir, exist_ok=True)
        checkpoint_path = os.path.join(checkpoint_dir, 'best.pt')
        last_checkpoint_path = os.path.join(checkpoint_dir, 'last.pt')
        best_epoch = None
        epoch_iter = range(epochs)
        progress = None
        if not args.get('no_progress') and not args.get('verbose_epochs'):
            progress = tqdm(epoch_iter, desc=f'fold {fold}', unit='ep', leave=True)
            epoch_iter = progress
        for epoch in epoch_iter:
            last_epoch = epoch
            # EARLY STOP FIX: restore training mode after each validation pass.
            model.train()
            optimizer.zero_grad()
            logits = model()
            logits = logits.to(args['device'])
            train_loss = loss_fcn(logits[train_mask], targets[train_mask])
            train_loss.backward(retain_graph=retain_graph)
            used_lr = optimizer.param_groups[0]["lr"]
            optimizer.step()
            scheduler.step()
            train_acc, train_micro_f1, train_macro_f1, train_buggy_f1 = score(targets[train_mask], logits[train_mask])
            # EARLY STOP FIX (2026-10-08): original code retained for rollback.
            # val_loss = loss_fcn(logits[val_mask], targets[val_mask])
            # val_acc, val_micro_f1, val_macro_f1, val_buggy_f1 = score(targets[val_mask], logits[val_mask])
            # EARLY STOP FIX: validate the updated weights, with dropout disabled.
            model.eval()
            with torch.no_grad():
                val_logits = model().to(args['device'])
                val_loss = loss_fcn(val_logits[val_mask], targets[val_mask])
                val_acc, val_micro_f1, val_macro_f1, val_buggy_f1 = score(targets[val_mask], val_logits[val_mask])

            # Detach before storing: keeping the loss tensors alive would pin the whole
            # autograd graph for every epoch, and the visualizers need plain floats.
            train_results[fold]['loss'].append(train_loss.item())
            train_results[fold]['micro_f1'].append(train_micro_f1)
            train_results[fold]['macro_f1'].append(train_macro_f1)
            train_results[fold]['buggy_f1'].append(train_buggy_f1)
            train_results[fold]['acc'].append(train_acc)
            train_results[fold]['lrs'].append(used_lr)

            val_results[fold]['loss'].append(val_loss.item())
            val_results[fold]['micro_f1'].append(val_micro_f1)
            val_results[fold]['macro_f1'].append(val_macro_f1)
            val_results[fold]['buggy_f1'].append(val_buggy_f1)
            val_results[fold]['acc'].append(val_acc)
            # Early stopping. Reported after the call so the patience countdown is
            # visible live - upstream had that trace commented out, which is why a
            # fold looked frozen right before it stopped.
            early_stopping(val_loss)
            # EARLY STOP FIX: save immediately, including improvements below delta.
            if early_stopping.improved:
                best_epoch = epoch
                early_stopping.save_checkpoint(val_loss, model, checkpoint_path)

            patience_state = '{}/{}'.format(early_stopping.counter, args['patience'])
            if args.get('verbose_epochs'):
                print('Fold {} | Epoch {}/{} | Train Loss: {:.4f} Buggy f1: {:.4f} Macro f1: {:.4f} '
                      '| Val Loss: {:.4f} Buggy f1: {:.4f} Macro f1: {:.4f} | patience {}{} | LR: {:.6g}'.format(
                          fold, epoch, epochs,
                          train_loss.item(), train_buggy_f1, train_macro_f1,
                          val_loss.item(), val_buggy_f1, val_macro_f1,
                          patience_state, ' *best' if early_stopping.improved else '', used_lr),
                      flush=True)
            elif progress is not None:
                progress.set_postfix({
                    'tr_loss': f'{train_loss.item():.4f}',
                    'val_loss': f'{val_loss.item():.4f}',
                    'val_bf1': f'{val_buggy_f1:.4f}',
                    'patience': patience_state,
                })

            # EARLY STOP FIX (2026-10-08): original code retained for rollback.
            # if early_stopping.early_stop:
            #     if stop_epoch >= epoch:
            #         checkpoint_path = args['output_models'].replace('.pth', f'_{epoch}_{fold}.pth')
            #         early_stopping.save_checkpoint(val_loss, model, checkpoint_path)
            #         early_stopped_at = epoch
            #         break
            #     stop_epoch = epoch
            if early_stopping.early_stop:
                early_stopped_at = epoch
                break
        if progress is not None:
            progress.close()
        if early_stopped_at is not None:
            print('Fold {}: early stopped at epoch {} (patience {}, best val loss {:.6f})'.format(
                fold, early_stopped_at, args['patience'], early_stopping.best_val_loss))
        else:
            print('Fold {}: ran all {} epochs, early stopping never triggered '
                  '(best val loss {:.6f})'.format(
                      fold, last_epoch + 1, early_stopping.best_val_loss))
        print('Saving model fold {}'.format(fold))
        # dump_result(targets[val_mask], logits[val_mask], os.path.join(args['output_models'], f'confusion_{fold}.csv'))
        # save_path = os.path.join(args['output_models'])
        # torch.save(model.state_dict(), save_path)
        # EARLY STOP FIX (2026-10-08): original code retained for rollback.
        # torch.save(model.state_dict(), args['output_models'])
        # EARLY STOP FIX: keep last weights separately; never overwrite best here.
        if best_epoch is None:
            raise RuntimeError('Fold {} has no finite validation checkpoint'.format(fold))
        torch.save(model.state_dict(), last_checkpoint_path)
        with open(os.path.join(checkpoint_dir, 'selection.json'), 'w') as checkpoint_info:
            json.dump({
                'fold': fold, 'best_epoch': best_epoch, 'last_epoch': last_epoch,
                'best_val_loss': early_stopping.best_val_loss,
                'last_val_loss': float(val_loss),
                'best_val_buggy_f1': val_results[fold]['buggy_f1'][best_epoch],
                'best_val_macro_f1': val_results[fold]['macro_f1'][best_epoch],
                'patience': early_stopping.patience, 'delta': early_stopping.delta,
                'best_path': checkpoint_path, 'last_path': last_checkpoint_path,
                'checkpoint_format': 'state_dict_only', 'config': args,
                'train_files': train_files,
                'val_files': val_files,
            }, checkpoint_info, indent=2, default=str)
        print('Fold {}: restore best epoch {} (val loss {:.6f}) from {}; last epoch {} saved to {}'.format(
            fold, best_epoch, early_stopping.best_val_loss, checkpoint_path,
            last_epoch, last_checkpoint_path), flush=True)
        # print('Testing phase')
        # print(f'Testing on {len(test_ids)} nodes')

        saved_models = model
        # EARLY STOP FIX (2026-10-08): original code retained for rollback.
        # saved_models.load_state_dict(torch.load(checkpoint_path))
        saved_models.load_state_dict(torch.load(checkpoint_path, map_location=device))
        # EARLY STOP FIX: existing inference path now aliases this fold's best weights.
        torch.save(saved_models.state_dict(), args['output_models'])
        saved_models.eval()
        # with torch.no_grad():
        #     logits = saved_models()
        #     logits = logits.to(args['device'])
        #     test_acc, test_micro_f1, test_macro_f1, test_buggy_f1 = score(targets[test_mask], logits[test_mask])
        #     print('Test Micro f1:   {:.4f} | Test Macro f1:   {:.4f} | Test Accuracy:   {:.4f}'.format(test_micro_f1, test_macro_f1, test_acc))
        #     print('Classification report', '\n', get_classification_report(targets[test_mask], logits[test_mask]))
        #     print('Confusion matrix', '\n', get_confusion_matrix(targets[test_mask], logits[test_mask]))
        
        with torch.no_grad():
            logits = saved_models()
            logits = logits.to(args['device'])
            val_acc, val_micro_f1, val_macro_f1, val_buggy_f1 = score(targets[val_mask], logits[val_mask])
            # print('Test Micro f1:   {:.4f} | Test Macro f1:   {:.4f} | Test Accuracy:   {:.4f}'.format(test_micro_f1, test_macro_f1, test_acc))
            # print('Classification report', '\n', get_classification_report(targets[test_mask], logits[test_mask]))
            # print('Confusion matrix', '\n', get_confusion_matrix(targets[test_mask], logits[test_mask]))
            val_results['buggy_f1_folds'].append(val_buggy_f1)
            val_results['macro_f1_folds'].append(val_macro_f1)

    # ===== ADDED: print the leakage figure next to the score it qualifies =====
    if overlap_total:
        print('\nSplit mode: {}   validation nodes whose exact (code, label) pair was '
              'in their training fold: {}/{} ({:.1f}%)'.format(
                  args.get('split_by', 'contract'), overlap_seen, overlap_total,
                  100.0 * overlap_seen / overlap_total))
    # ===== END ADDED =====

    # with torch.no_grad():
    #     logits = saved_models()
    #     logits = logits.to(args['device'])
    #     web3bugs_acc, web3bugs_micro_f1, web3bugs_macro_f1, web3bugs_buggy_f1 = score(targets[web3bugs_mask], logits[web3bugs_mask])
    #     print('web3bugs Micro f1:   {:.4f} | web3bugs Macro f1:   {:.4f} | web3bugs Accuracy:   {:.4f}'.format(web3bugs_micro_f1, web3bugs_macro_f1, web3bugs_acc))
    #     print('Classification report', '\n', get_classification_report(targets[web3bugs_mask], logits[web3bugs_mask]))
    #     print('Confusion matrix', '\n', get_confusion_matrix(targets[web3bugs_mask], logits[web3bugs_mask]))
    
    return train_results, val_results


def _node_test_ids(nx_graph, testset):
    number_of_nodes = len(nx_graph)
    if not testset or not os.path.isdir(testset):
        return list(range(number_of_nodes))
    test_files = [f for f in os.listdir(testset) if f.endswith('.sol')]
    if not test_files:
        return list(range(number_of_nodes))
    test_ids = get_node_ids(nx_graph, test_files)
    return test_ids or list(range(number_of_nodes))


def run_inference(args):
    from sco_models.model_hgt import HGTVulNodeClassifier

    validate_paths(args, ['compressed_graph', 'checkpoint'])
    nx_graph = read_gpickle(args['compressed_graph'])
    number_of_nodes = len(nx_graph)
    feature_extractor = None if args['node_feature'] == 'nodetype' else args['feature_extractor']
    model = HGTVulNodeClassifier(
        args['compressed_graph'],
        feature_extractor=feature_extractor,
        node_feature=args['node_feature'],
        device=args['device'],
    )
    model.load_state_dict(torch.load(args['checkpoint'], map_location=args['device']))
    model.eval()
    model.to(args['device'])
    test_ids = _node_test_ids(nx_graph, args.get('testset'))
    if not test_ids:
        raise ValueError('No test nodes were selected for inference')
    targets = torch.tensor(model.node_labels, device=args['device'])
    buggy_node_ids = torch.nonzero(targets).squeeze().tolist()
    test_buggy_node_ids = set(buggy_node_ids) & set(test_ids)
    print('Buggy nodes in test: {}/{} ({}%)'.format(len(test_buggy_node_ids), len(test_ids), 100*len(test_buggy_node_ids)/len(test_ids)))
    test_mask = get_binary_mask(number_of_nodes, test_ids)
    if hasattr(torch, 'BoolTensor'):
        test_mask = test_mask.bool()
    print(f"Testing on {len(test_ids)} nodes")
    with torch.no_grad():
        logits = model()
        logits = logits.to(args['device'])
        test_acc, test_micro_f1, test_macro_f1, _ = score(targets[test_mask], logits[test_mask])
        print('Test Micro f1:   {:.4f} | Test Macro f1:   {:.4f} | Test Accuracy:   {:.4f}'.format(test_micro_f1, test_macro_f1, test_acc))
        print('Classification report', '\n', get_classification_report(targets[test_mask], logits[test_mask]))
        print('Confusion matrix', '\n', get_confusion_matrix(targets[test_mask], logits[test_mask]))


if __name__ == '__main__':
    parser = build_node_parser()
    args = finalize_node_args(parser.parse_args())
    torch.manual_seed(args['seed'])
    print('Running on ', args['device'])
    ensure_output_parent(args['output_models'])

    # Training
    if not args['test']:
        print('Training phase')
        validate_paths(args, ['compressed_graph'])
        train_results, val_results = main(args)
        if not args['non_visualize']:
            # The log dir is cleared first so a rerun does not interleave with stale
            # scalars, then the writers actually run - upstream cleared it and left
            # both visualize calls commented out, so TensorBoard never had any data.
            if os.path.exists(args['log_dir']):
                rmtree(args['log_dir'])
            print('Writing TensorBoard scalars to {}'.format(args['log_dir']))
            visualize_average_k_folds(args, train_results, val_results)
            visualize_k_folds(args, train_results, val_results)
            print('View them with: tensorboard --logdir {}'.format(args['log_dir']))
        print('Average Buggy F1 score of folds: {:.4f}'.format(np.mean(val_results['buggy_f1_folds'])*100))
        print('Average Macro F1 score of folds: {:.4f}'.format(np.mean(val_results['macro_f1_folds'])*100))
    # Testing
    else:
        print('Testing phase')
        run_inference(args)
