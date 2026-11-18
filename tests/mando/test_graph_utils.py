import pickle

import networkx as nx

from mando.models.graph_utils import load_hetero_nx_graph


def test_load_hetero_nx_graph_reads_pickle_graph(tmp_path):
    graph = nx.MultiDiGraph()
    graph.add_node("n0", node_type="contract")
    graph.add_node("n1", node_type="function")
    graph.add_edge("n0", "n1", edge_type="contains")
    graph_path = tmp_path / "graph.gpickle"
    with open(graph_path, "wb") as f:
        pickle.dump(graph, f)

    loaded = load_hetero_nx_graph(graph_path)

    assert list(loaded.nodes) == [0, 1]
    assert loaded.nodes[0]["node_hetero_id"] == 0
    assert loaded.nodes[1]["node_hetero_id"] == 0


def _upstream_node_token(nx_graph):
    import torch
    features = {}
    for _, node_data in nx_graph.nodes(data=True):
        node_type = node_data['node_type']
        row = torch.tensor(node_data['token']).unsqueeze(0)
        features[node_type] = row if node_type not in features else torch.cat((features[node_type], row))
    return features


def _upstream_node_label(nx_graph):
    import ast
    node_labels, label_ids, labeled = [], {'valid': 0}, {'buggy': [], 'valid': []}
    for node_id, node_data in nx_graph.nodes(data=True):
        label = node_data['node_info_vulnerabilities']
        if label is None:
            labeled['valid'].append(node_id)
            node_labels.append(0)
            continue
        if isinstance(label, str):
            label = ast.literal_eval(label.strip('"'))
        if label[0]['category'] not in label_ids:
            label_ids[label[0]['category']] = len(label_ids)
        labeled['buggy'].append(node_id)
        node_labels.append(1)
    return node_labels, labeled, label_ids


def _labelled_graph():
    import networkx as nx
    import numpy as np
    graph = nx.MultiDiGraph()
    labels = [None, "[{'category': 'reentrancy', 'lines': [3]}]", [{'category': 'access_control'}],
              '"[{\'category\': \'reentrancy\'}]"', None]
    for i in range(40):
        graph.add_node(i, node_type=("FUNCTION_NAME", "EXPRESSION", "IF")[i % 3],
                       token=np.arange(i, i + 8, dtype=np.float32), node_info_vulnerabilities=labels[i % 5])
    return graph


def test_fast_node_tokens_equal_the_upstream_tensors():
    import torch
    from mando.models.graph_utils import get_node_token
    graph = _labelled_graph()
    expected, actual = _upstream_node_token(graph), get_node_token(graph)
    assert list(actual) == list(expected)
    assert all(actual[k].dtype == expected[k].dtype and torch.equal(actual[k], expected[k]) for k in expected)


def test_cached_node_labels_equal_the_upstream_labels():
    from mando.models.graph_utils import get_node_label
    graph = _labelled_graph()
    assert get_node_label(graph) == _upstream_node_label(graph)
    assert get_node_label(graph) == _upstream_node_label(graph)   # second call served from the cache


def test_timer_reports_phases_and_per_epoch_seconds():
    from dfg.utils import Timer
    timer = Timer(dict(fold_setup=1.0))
    timer.mark("build").mark("fit")
    summary = timer.summary(4)
    assert list(summary) == ["fold_setup", "build", "fit", "per_epoch"]
    assert summary["fold_setup"] == 1.0 and summary["per_epoch"] == round(summary["fit"] / 4, 2)
