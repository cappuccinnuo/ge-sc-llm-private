import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import torch
from torch.utils.tensorboard import SummaryWriter


def _as_float_list(values):
    """Metrics arrive as a mix of python floats and 0-d tensors; normalize them."""
    return [float(v.item()) if torch.is_tensor(v) else float(v) for v in values]


def _fold_ids(args, results):
    """Fold keys actually present. results also carries string summary keys."""
    return [f for f in range(args['k_folds']) if f in results]


def _stack_folds(results, key, folds):
    """Average a metric across folds, truncating to the shortest fold.

    Early stopping means folds run for different numbers of epochs, so the raw
    per-fold lists are ragged and cannot go straight into torch.tensor().
    """
    series = [_as_float_list(results[fold][key]) for fold in folds]
    series = [s for s in series if s]
    if not series:
        return []
    length = min(len(s) for s in series)
    if length == 0:
        return []
    trimmed = [s[:length] for s in series]
    return torch.mean(torch.tensor(trimmed), dim=0).tolist()


def visualize_average_k_folds(args, train_results, val_results):
    train_folds = _fold_ids(args, train_results)
    val_folds = _fold_ids(args, val_results)
    if not train_folds or not val_folds:
        return {}, {}

    avg_train_result = {
        key: _stack_folds(train_results, key, train_folds)
        for key in ('acc', 'micro_f1', 'macro_f1', 'buggy_f1', 'loss')
    }
    avg_train_result['lrs'] = _as_float_list(train_results[train_folds[0]]['lrs'])

    avg_val_result = {
        key: _stack_folds(val_results, key, val_folds)
        for key in ('acc', 'micro_f1', 'macro_f1', 'buggy_f1', 'loss')
    }

    # Only plot epochs that every series actually reached.
    steps = min(
        [len(v) for v in avg_train_result.values() if v and isinstance(v, list)]
        + [len(v) for v in avg_val_result.values() if v]
    )

    writer = SummaryWriter(args['log_dir'])
    for idx in range(steps):
        writer.add_scalars('Accuracy', {'train_avg': avg_train_result['acc'][idx],
                                        'valid_avg': avg_val_result['acc'][idx]}, idx)
        writer.add_scalars('Micro_f1', {'train_avg': avg_train_result['micro_f1'][idx],
                                        'valid_avg': avg_val_result['micro_f1'][idx]}, idx)
        writer.add_scalars('Macro_f1', {'train_avg': avg_train_result['macro_f1'][idx],
                                        'valid_avg': avg_val_result['macro_f1'][idx]}, idx)
        writer.add_scalars('Buggy_f1', {'train_avg': avg_train_result['buggy_f1'][idx],
                                        'valid_avg': avg_val_result['buggy_f1'][idx]}, idx)
        writer.add_scalars('Train_results', {'buggy_f1': avg_train_result['buggy_f1'][idx],
                                             'macro_f1': avg_train_result['macro_f1'][idx]}, idx)
        writer.add_scalars('Val_results', {'buggy_f1': avg_val_result['buggy_f1'][idx],
                                           'macro_f1': avg_val_result['macro_f1'][idx]}, idx)
        writer.add_scalars('Loss', {'train_avg': avg_train_result['loss'][idx],
                                    'valid_avg': avg_val_result['loss'][idx]}, idx)
    for idx, lr in enumerate(avg_train_result['lrs']):
        writer.add_scalar('Learning rate', lr, idx)
    writer.close()
    return avg_train_result, avg_val_result


def visualize_k_folds(args, train_results, val_results):
    writer = SummaryWriter(args['log_dir'])
    for fold in _fold_ids(args, train_results):
        if fold not in val_results:
            continue
        train_fold = {k: _as_float_list(v) for k, v in train_results[fold].items()}
        val_fold = {k: _as_float_list(v) for k, v in val_results[fold].items()}
        steps = min(
            len(train_fold['acc']), len(train_fold['micro_f1']),
            len(train_fold['macro_f1']), len(train_fold['buggy_f1']), len(train_fold['loss']),
            len(val_fold['acc']), len(val_fold['micro_f1']),
            len(val_fold['macro_f1']), len(val_fold['buggy_f1']), len(val_fold['loss']),
        )
        for idx in range(steps):
            writer.add_scalars('Accuracy', {f'train_{fold+1}': train_fold['acc'][idx],
                                            f'valid_{fold+1}': val_fold['acc'][idx]}, idx)
            writer.add_scalars('Micro_f1', {f'train_{fold+1}': train_fold['micro_f1'][idx],
                                            f'valid_{fold+1}': val_fold['micro_f1'][idx]}, idx)
            writer.add_scalars('Macro_f1', {f'train_{fold+1}': train_fold['macro_f1'][idx],
                                            f'valid_{fold+1}': val_fold['macro_f1'][idx]}, idx)
            writer.add_scalars('Train_results', {f'buggy_f1_{fold+1}': train_fold['buggy_f1'][idx],
                                                 f'macro_f1_{fold+1}': train_fold['macro_f1'][idx]}, idx)
            writer.add_scalars('Val_results', {f'buggy_f1_{fold+1}': val_fold['buggy_f1'][idx],
                                               f'macro_f1_{fold+1}': val_fold['macro_f1'][idx]}, idx)
            writer.add_scalars('Loss', {f'train_{fold+1}': train_fold['loss'][idx],
                                        f'valid_{fold+1}': val_fold['loss'][idx]}, idx)
    first_fold = _fold_ids(args, train_results)
    if first_fold:
        for idx, lr in enumerate(_as_float_list(train_results[first_fold[0]]['lrs'])):
            writer.add_scalar('Learning rate', lr, idx)
    writer.close()


def nodes_edges_correlation(graph_file_list, axis_plt, title):
    for graph_files in graph_file_list:
        fig, ax = plt.subplots()
        nodes = {}
        edges = {}
        for graph in graph_files:
            nx_graph = nx.read_gpickle(graph)
            nodes[graph] = len(nx_graph.nodes)
            edges[graph] = len(nx_graph.edges)
        axis_plt.scatter(list(nodes.values()), list(edges.values()), c=[np.random.rand(3,)], alpha=0.6, s=10)
    axis_plt.set_xlabel('Number of nodes', fontsize=8)
    axis_plt.set_ylabel('Number of edge', fontsize=8)
    axis_plt.set_title(title, fontsize=8)


def nodes_edges_compressed_graph_correlation(compressed_graphs, axis_plt, title):
    nx_graph = nx.read_gpickle(compressed_graphs)
    node_dict = {}
    edge_dict = {}
    for idx, node in nx_graph.nodes(data=True):
        file_name = node['source_file']
        if file_name in node_dict:
            node_dict[file_name] += 1
        else:
            node_dict[file_name] = 1
    for source, target, data in nx_graph.edges(data=True):
        assert nx_graph.nodes[source]['source_file'] == nx_graph.nodes[target]['source_file']
        file_name = nx_graph.nodes[source]['source_file']
        if file_name in edge_dict:
            edge_dict[file_name] += 1
        else:
            edge_dict[file_name] = 1
    assert len(node_dict) >= len(edge_dict)
    if len(node_dict) > len(edge_dict):
        for k in node_dict.keys():
            if k not in edge_dict:
                edge_dict[k] = 0
    
    # ax.set_xlim(0,3000)
    # ax.set_ylim(0,3000)
    axis_plt.scatter(list(node_dict.values()), list(edge_dict.values()), c=[np.random.rand(3,)], alpha=0.6, s=10)
    axis_plt.set_xlabel('Number of nodes', fontsize=8)
    axis_plt.set_ylabel('Number of edge', fontsize=8)
    axis_plt.set_title(title, fontsize=8)
    axis_plt.grid(True)
    # fig.tight_layout()
    # plt.savefig(output)
