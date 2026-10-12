import os
# EARLY STOP FIX (2026-10-08): per-fold checkpoint selection metadata.
import json
from shutil import rmtree

import gc
import numpy as np
import torch
from sklearn.model_selection import StratifiedKFold
from tqdm import tqdm

from sco_models.utils import score, get_classification_report, get_confusion_matrix
from sco_models.tools import EarlyStopping
from sco_models.visualization import visualize_average_k_folds, visualize_k_folds
from sco_models.classifier_cli import (
    build_graph_parser,
    ensure_output_parent,
    finalize_graph_args,
    validate_paths,
)


def train(args, model, train_loader, optimizer, loss_fcn, epoch, scheduler=None):
    model.train()
    total_accucracy =  0
    total_macro_f1 = 0
    total_micro_f1 = 0
    total_buggy_f1 = 0
    total_loss = 0
    circle_lrs = []
    for idx, (batched_graph, labels) in enumerate(train_loader):
        labels = labels.to(args['device'])
        optimizer.zero_grad()
        logits, _ = model(batched_graph)
        loss = loss_fcn(logits, labels)
        train_acc, train_micro_f1, train_macro_f1, train_buggy_f1 = score(labels, logits)
        loss.backward()
        # torch.nn.utils.clip_grad_norm_(model.parameters(), 1e-3)
        # Record the LR actually used by this update, before advancing the cycle.
        circle_lrs.append(optimizer.param_groups[0]["lr"])
        optimizer.step()
        if scheduler is not None:
            scheduler.step()
        total_accucracy += train_acc
        total_micro_f1 += train_micro_f1
        total_macro_f1 += train_macro_f1
        total_buggy_f1 += train_buggy_f1
        total_loss += loss.item()
    steps = idx + 1
    return model, total_loss/steps, total_micro_f1/steps, total_macro_f1/steps, total_accucracy/steps, total_buggy_f1/steps, circle_lrs


def validate(args, model, val_loader, loss_fcn):
    model.eval()
    total_loss = 0
    total_macro_f1 = 0
    total_micro_f1 = 0
    total_accucracy =  0
    total_buggy_f1 = 0
    with torch.no_grad():
        for idx, (batched_graph, labels) in enumerate(val_loader):
            labels = labels.to(args['device'])
            logits, _ = model(batched_graph)
            loss = loss_fcn(logits, labels)
            total_loss += loss.item()
            val_acc, val_micro_f1, val_macro_f1, val_buggy_f1 = score(labels, logits)
            total_accucracy += val_acc
            total_micro_f1 += val_micro_f1
            total_macro_f1 += val_macro_f1
            total_buggy_f1 += val_buggy_f1
    steps = idx + 1
    return total_loss/steps, total_micro_f1/steps, total_macro_f1/steps, total_accucracy/steps, total_buggy_f1/steps


def test(args, model, test_loader):
    model.eval()
    total_macro_f1 = 0
    total_micro_f1 = 0
    total_accucracy =  0
    total_logits = []
    total_target = []
    with torch.no_grad():
        for idx, (batched_graph, labels) in enumerate(test_loader):
            labels = labels.to(args['device'])
            # logits, _ = model(batched_graph, './forensics/graph_hiddens/reentrancy/creation_last_attention.pt')
            logits, _ = model(batched_graph)
            total_logits += logits.tolist()
            total_target += labels.tolist()
            test_acc, test_micro_f1, test_macro_f1, _ = score(labels, logits)
            total_accucracy += test_acc
            total_micro_f1 += test_micro_f1
            total_macro_f1 += test_macro_f1
    steps = idx + 1
    total_logits = torch.tensor(total_logits)
    total_target = torch.tensor(total_target)
    classification_report = get_classification_report(total_target, total_logits, output_dict=True)
    confusion_report = get_confusion_matrix(total_target, total_logits)
    return total_micro_f1/steps, total_macro_f1/steps, total_accucracy/steps, classification_report, confusion_report

def get_class_distribution(dataset, sample_ids):
    categories = {}
    for s in sample_ids:
        graph, label = dataset.__getitem__(s)
        label = int(label)
        if label in categories:
            categories[label].append(graph)
        else:
            categories[label] = [graph]
    return categories


def main(args):
    from dgl.dataloading import GraphDataLoader

    from sco_models.dataloader import EthIdsDataset
    from sco_models.model_hgt import HGTVulGraphClassifier

    print('===============================================')
    print('Graph file ', args['compressed_graph'])
    epochs = args['num_epochs']
    k_folds = args['k_folds']
    device = args['device']
    ethdataset = EthIdsDataset(args['label'])
    # kfold = KFold(n_splits=k_folds, shuffle=True)
    # FOLD SEED FIX (2026-10-09): original code retained for rollback.
    # kfold = StratifiedKFold(n_splits=k_folds, shuffle=True)
    # FOLD SEED FIX: without random_state the shuffle draws from numpy's global RNG,
    # which --seed never touches, so every run got different folds.
    kfold = StratifiedKFold(n_splits=k_folds, shuffle=True, random_state=args['seed'])
    train_results = {}
    val_results = {'buggy_f1_folds': [], 'macro_f1_folds': []}
    # Get feature extractor
    print('Getting features')
    if args['node_feature'] == 'han':
        feature_extractor = HGTVulGraphClassifier(args['feature_compressed_graph'], node_feature='nodetype', hidden_size=16, device=args['device'])
        feature_extractor.load_state_dict(torch.load(args['feature_extractor']))
        feature_extractor.to(args['device'])
        feature_extractor.eval()
    else:
        feature_extractor = args['feature_extractor']

    # dataloader =  GraphDataLoader(ethdataset)
    # # for graphs, labels in dataloader:
    # for epoch in range(epochs):
    classification_total_report = {'0': {'precision': [], 'recall': [], 'f1-score': [], 'support': []}, '1': {'precision': [], 'recall': [], 'f1-score': [], 'support': []}, 'macro avg': {'precision': [], 'recall': [], 'f1-score': [], 'support': []}, 'weighted avg': {'precision': [], 'recall': [], 'f1-score': [], 'support': []}}
    confusion_matrix_total_report = []
    # test_ids = [ethdataset.filename_mapping[sc] for sc in os.listdir(args['testset']) if sc.endswith('.sol')]
    test_ids = []
    test_subsampler = torch.utils.data.SubsetRandomSampler(test_ids)
    test_dataloader = GraphDataLoader(ethdataset, batch_size=args['batch_size'], drop_last=False, sampler=test_subsampler)
    total_train_ids = list(set(list(range(ethdataset.num_graphs))).difference(set(test_ids)))
    assert len(set(test_ids) & set(total_train_ids)) == 0
    # for fold, (train_ids, val_ids) in enumerate(kfold.split(total_train_ids)):
    # FOLD SEED FIX (2026-10-09): original code retained for rollback.
    # for fold, (train_ids, val_ids) in enumerate(kfold.split(ethdataset.graphs, ethdataset.label)):
    # FOLD SEED FIX: split over a name-sorted view of the contracts, so the folds do
    # not depend on the order the label file happens to list them in.
    fold_order = sorted(range(len(ethdataset.graphs)), key=lambda i: ethdataset.graphs[i])
    fold_labels = [int(ethdataset.label[i]) for i in fold_order]
    for fold, (train_pos, val_pos) in enumerate(kfold.split(fold_order, fold_labels)):
        train_ids = [fold_order[i] for i in train_pos]
        val_ids = [fold_order[i] for i in val_pos]
        # train_ids = [total_train_ids[i] for i in _train_ids]
        # print(_train_ids == np.array(train_ids))
        # val_ids = [total_train_ids[i] for i in _val_ids]
        # print(_val_ids == np.array(val_ids))
        train_categories = get_class_distribution(ethdataset, train_ids)
        val_categories = get_class_distribution(ethdataset, val_ids)
        print('---------------------------------------------------------------------------')
        print([ethdataset.graphs[i] for i in train_ids if int(ethdataset.label[i]) == 0])
        print('---------------------------------------------------------------------------')
        print([ethdataset.graphs[i] for i in train_ids if int(ethdataset.label[i]) == 1])
        print('---------------------------------------------------------------------------')
        print([ethdataset.graphs[i] for i in val_ids if int(ethdataset.label[i]) == 0])
        print('---------------------------------------------------------------------------')
        print([ethdataset.graphs[i] for i in val_ids if int(ethdataset.label[i]) == 1])
        print('---------------------------------------------------------------------------')
        print(f'Train class distribution: {len(train_categories[0])}/{len(train_categories[1])}')
        print(f'Val class distribution: {len(val_categories[0])}/{len(val_categories[1])}')
        assert len(test_ids) + len(train_ids) + len(val_ids) == len(ethdataset)
        assert len(set(test_ids) & set(train_ids)) == 0
        assert len(set(test_ids) & set(val_ids)) == 0
        train_results[fold] = {'loss': [], 'acc': [], 'micro_f1': [], 'macro_f1': [], 'buggy_f1': [], 'lrs': []}
        val_results[fold] = {'loss': [], 'acc': [], 'micro_f1': [], 'macro_f1': [], 'buggy_f1': []}
        train_subsampler = torch.utils.data.SubsetRandomSampler(train_ids)
        val_subsampler = torch.utils.data.SubsetRandomSampler(val_ids)
        train_dataloader = GraphDataLoader(ethdataset,batch_size=args['batch_size'],drop_last=False,sampler=train_subsampler)
        val_dataloader = GraphDataLoader(ethdataset,batch_size=args['batch_size'],drop_last=False,sampler=val_subsampler)
        print('Start training fold {} with {}/{}/{} train/val/test smart contracts'.format(fold, len(train_subsampler), len(val_subsampler), len(test_ids)))
        total_steps = epochs * len(train_dataloader)
        model = HGTVulGraphClassifier(args['compressed_graph'], feature_extractor=feature_extractor, node_feature=args['node_feature'], device=device)
        model.reset_parameters()
        model.to(device)
        loss_fcn = torch.nn.CrossEntropyLoss()
        # Paper Sec. 5.3 specifies the LR bounds, but not the scheduling curve.
        # Keep OneCycle: start at max_lr / 20 and return to that lower bound.
        # final_div_factor=1 avoids decaying below the paper's stated range.
        optimizer = torch.optim.Adam(model.parameters(), lr=args['lr'], weight_decay=0.000005)
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer, max_lr=0.01, total_steps=total_steps,
            div_factor=0.01 / args['lr'], final_div_factor=1.0)
        early_stopping = EarlyStopping(patience=args['patience'], delta=0.001, verbose=True)
        print('Training settings: patience={}, delta=0.001, LR={:.6g} -> 0.01 -> {:.6g}, '
              'OneCycle per optimizer update'.format(
                  args['patience'], optimizer.param_groups[0]['lr'], args['lr']), flush=True)
        early_stopped_at = None
        last_epoch = -1
        stop_epoch = epochs
        # EARLY STOP FIX (2026-10-08): original code retained for rollback.
        # checkpoint_path = args['output_models']
        checkpoint_dir = os.path.splitext(args['output_models'])[0] + '_fold{}'.format(fold)
        os.makedirs(checkpoint_dir, exist_ok=True)
        checkpoint_path = os.path.join(checkpoint_dir, 'best.pt')
        last_checkpoint_path = os.path.join(checkpoint_dir, 'last.pt')
        best_epoch = None
        lrs = []
        epoch_iter = range(epochs)
        progress = None
        if not args.get('no_progress') and not args.get('verbose_epochs'):
            progress = tqdm(epoch_iter, desc=f'fold {fold}', unit='ep', leave=True)
            epoch_iter = progress
        for epoch in epoch_iter:
            # EARLY STOP FIX: also record the epoch that triggers the break.
            last_epoch = epoch
            model, train_loss, train_micro_f1, train_macro_f1, train_acc, train_buggy_f1, lrs = train(args, model, train_dataloader, optimizer, loss_fcn, epoch, scheduler=scheduler)
            val_loss, val_micro_f1, val_macro_f1, val_acc, val_buggy_f1 = validate(args, model, val_dataloader, loss_fcn)

            if args.get('verbose_epochs'):
                print('Fold {} | Epoch {}/{} | Train Loss: {:.4f} Buggy f1: {:.4f} Macro f1: {:.4f} '
                      '| Val Loss: {:.4f} Buggy f1: {:.4f} Macro f1: {:.4f} | LR: {:.6g}'.format(
                          fold, epoch, epochs,
                          float(train_loss), train_buggy_f1, train_macro_f1,
                          float(val_loss), val_buggy_f1, val_macro_f1, lrs[-1]),
                      flush=True)
            elif progress is not None:
                progress.set_postfix({
                    'tr_loss': f'{float(train_loss):.4f}',
                    'val_loss': f'{float(val_loss):.4f}',
                    'val_bf1': f'{val_buggy_f1:.4f}',
                })

            # Stored as floats: holding the loss tensors would pin an autograd graph
            # per epoch, and the visualizers stack these into torch.tensor().
            train_results[fold]['loss'].append(float(train_loss))
            train_results[fold]['micro_f1'].append(train_micro_f1)
            train_results[fold]['macro_f1'].append(train_macro_f1)
            train_results[fold]['acc'].append(train_acc)
            train_results[fold]['buggy_f1'].append(train_buggy_f1)
            train_results[fold]['lrs'] += lrs

            val_results[fold]['loss'].append(float(val_loss))
            val_results[fold]['micro_f1'].append(val_micro_f1)
            val_results[fold]['macro_f1'].append(val_macro_f1)
            val_results[fold]['buggy_f1'].append(val_buggy_f1)
            val_results[fold]['acc'].append(val_acc)
            # Early stopping
            early_stopping(val_loss)
            # EARLY STOP FIX: save immediately, including improvements below delta.
            if early_stopping.improved:
                best_epoch = epoch
                early_stopping.save_checkpoint(val_loss, model, checkpoint_path)
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
            last_epoch = epoch

        if progress is not None:
            progress.close()
        # earliest_epoch used to be initialised to 0 and printed unconditionally, so a
        # fold that ran to completion still reported "Early stopping at epoch 0".
        if early_stopped_at is not None:
            print('Fold {}: early stopped at epoch {} (patience {}, best val loss {:.6f})'.format(
                fold, early_stopped_at, args['patience'], early_stopping.best_val_loss))
        else:
            print('Fold {}: ran all {} epochs, early stopping never triggered '
                  '(best val loss {:.6f})'.format(
                      fold, last_epoch + 1, early_stopping.best_val_loss))
        print('Saving model fold {}'.format(fold))

        # _, _, _, classification_report, confusion_report = test(args, model, val_dataloader)
        # for category, metrics in classification_total_report.items():
        #     for metric in metrics.keys():
        #         classification_total_report[category][metric].append(classification_report[category][metric])

        # confusion_matrix_total_report.append(confusion_report)

        # print('Saving model fold {}'.format(fold))
        # save_path = os.path.join(args['output_models'], f'han_fold_{fold}.pth')
        # bugtype = args['log_dir'].split('/')[-1]
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
                'train_files': [ethdataset.graphs[i] for i in train_ids],
                'val_files': [ethdataset.graphs[i] for i in val_ids],
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
        _, _, _, classification_report, confusion_report = test(args, model, val_dataloader)
        
        val_results['buggy_f1_folds'].append(classification_report['1']['f1-score'])
        val_results['macro_f1_folds'].append(classification_report['macro avg']['f1-score'])
        print(confusion_report)

    
    # headers = ['precision', 'recall', 'f1-score', 'avg_support']
    # classification_tabular_report = []
    # for category, metrics in classification_total_report.items():
    #     row = [category]
    #     for metric in metrics.keys():
    #         std = np.std(classification_total_report[category][metric])
    #         classification_total_report[category][metric] = np.max(classification_total_report[category][metric])
    #         row.append(f'{classification_total_report[category][metric]}(#{classification_total_report[category][metric]*std:.2f})')
    #     classification_tabular_report.append(row)
    # print(tabulate(classification_tabular_report, headers=headers))
    # print(np.round(np.mean(confusion_matrix_total_report, axis=0)))
        del model
        gc.collect()
        torch.cuda.empty_cache()
    return train_results, val_results


def load_model(model_path):
    from sco_models.model_hgt import HGTVulGraphClassifier

    model = HGTVulGraphClassifier()
    model.load_state_dict(torch.load(model_path))
    return model.eval()


def _graph_test_ids(dataset, testset):
    if not testset or not os.path.isdir(testset):
        return list(range(len(dataset)))
    test_names = {f for f in os.listdir(testset) if f.endswith('.sol')}
    if not test_names:
        return list(range(len(dataset)))
    selected = []
    for idx, graph_name in enumerate(dataset.graphs):
        if graph_name in test_names or os.path.basename(graph_name) in test_names:
            selected.append(idx)
    return selected or list(range(len(dataset)))


def run_inference(args):
    from dgl.dataloading import GraphDataLoader

    from sco_models.dataloader import EthIdsDataset
    from sco_models.model_hgt import HGTVulGraphClassifier

    validate_paths(args, ['compressed_graph', 'checkpoint', 'label'])
    ethdataset = EthIdsDataset(args['label'])
    test_ids = _graph_test_ids(ethdataset, args.get('testset'))
    test_subsampler = torch.utils.data.SubsetRandomSampler(test_ids)
    test_dataloader = GraphDataLoader(
        ethdataset,
        batch_size=args['batch_size'],
        drop_last=False,
        sampler=test_subsampler,
    )
    model = HGTVulGraphClassifier(
        args['compressed_graph'],
        feature_extractor=args['feature_extractor'],
        node_feature=args['node_feature'],
        device=args['device'],
    )
    model.load_state_dict(torch.load(args['checkpoint'], map_location=args['device']))
    model.to(args['device'])
    model.eval()
    test_micro_f1, test_macro_f1, test_acc, report, confusion = test(args, model, test_dataloader)
    print(f'Testing on {len(test_ids)} smart contracts')
    print('Test Micro f1:   {:.4f} | Test Macro f1:   {:.4f} | Test Accuracy:   {:.4f}'.format(test_micro_f1, test_macro_f1, test_acc))
    print('Classification report', '\n', report)
    print('Confusion matrix', '\n', confusion)


if __name__ == '__main__':
    parser = build_graph_parser()
    args = finalize_graph_args(parser.parse_args())
    torch.manual_seed(args['seed'])
    ensure_output_parent(args['output_models'])

    # Training
    if not args['test']:
        print('Training phase')
        validate_paths(args, ['compressed_graph', 'label'])
        train_results, val_results = main(args)
        if not args['non_visualize']:
            # Clear stale scalars first, then actually write: upstream cleared the
            # directory and left both writers commented out, so TensorBoard never
            # received anything for the contract-level phase.
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
