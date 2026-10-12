import networkx as nx
import pytest
from scripts.DFG.experiments.prepare import check_labels


@pytest.mark.parametrize("encoding", [[], "None", "[]"])
def test_unsupported_original_model_label_encoding_is_rejected_without_relabel(encoding):
    graph = nx.MultiDiGraph()
    graph.add_node(7, source_file="x.sol", node_type="expression_statement",
                   node_info_vulnerabilities=encoding)
    with pytest.raises(ValueError, match="incompatible"):
        check_labels(graph, [{"contract_name": "x.sol", "targets": 0}])
    assert graph.nodes[7]["node_info_vulnerabilities"] == encoding
