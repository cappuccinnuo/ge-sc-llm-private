from pathlib import Path
from scripts.DFG.ddg_builder import DDGBuilder
from scripts.DFG.configuration import prepare_graph
from scripts.DFG.models import DDGConfig
from scripts.DFG.graph_audit import assert_augmented
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source

def test_minimal_example_expected_seven_forward_dependencies():
    source=(Path(__file__).parent/"fixtures/minimal.sol").read_text()
    graph=generate_cfg_from_source(source,"minimal.sol")
    enhanced,audit=prepare_graph(graph,{"minimal.sol":source},DDGConfig(True))
    assert audit["invariants"]["ddg_edges"]==7
    assert len(enhanced)==len(graph)
    assert_augmented(graph,enhanced)
    data_pairs={(enhanced.nodes[s]["code"],enhanced.nodes[t]["code"])
                for s,t,d in enhanced.edges(data=True) if d["edge_type"]=="DATA_DEF_USE"}
    assert ("y = x + 1;","return y;") in data_pairs
    assert ("y = x + 2;","return y;") in data_pairs
    assert ("uint z = 7;","return z;") in data_pairs
    assert ("uint y = x;","return y;") not in data_pairs
