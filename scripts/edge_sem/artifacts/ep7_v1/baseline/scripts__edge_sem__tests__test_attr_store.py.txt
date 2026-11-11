"""EP4 storage/digest and separation of feature decisions from labels."""
import ast
from pathlib import Path
import networkx as nx
import numpy as np
from scripts.edge_sem.attrs import EDGE_FEATURE_NAMES, GROUPS
from scripts.edge_sem.attr_batch import numeric_digest
from scripts.edge_sem.attr_stats import descriptive_statistics


def test_numeric_digest_covers_order_dtype_and_all_values():
    keys=["f::1->2::GUARDS::0","f::2->3::GUARDS::0"]
    m=np.zeros((2,74),dtype=np.uint8)
    value=numeric_digest(keys,m)
    assert value==numeric_digest(list(keys),m.copy())
    assert value!=numeric_digest(list(reversed(keys)),m)
    m[1,49]=1
    assert value!=numeric_digest(keys,m)


def test_descriptive_labels_do_not_mutate_feature_arrays():
    g=nx.MultiDiGraph()
    g.add_node(1,node_type="expression_statement",node_info_vulnerabilities=None)
    g.add_node(2,node_type="expression_statement",node_info_vulnerabilities=[{"category":"x"}])
    rows=[dict(key="a",relation="GUARDS",src=1,dst=2),dict(key="b",relation="GUARDS",src=2,dst=1)]
    attrs={k:np.zeros(74,dtype=np.uint8) for k in ("a","b")}
    attrs["a"][49]=1
    before={k:v.copy() for k,v in attrs.items()}
    stats=descriptive_statistics(rows,attrs,g)
    assert stats["by_relation"]["GUARDS"]["by_original_target_label"]["positive"]["bit_fractions"][EDGE_FEATURE_NAMES[49]]==1
    assert stats["by_relation"]["GUARDS"]["by_original_target_label"]["negative"]["bit_fractions"][EDGE_FEATURE_NAMES[49]]==0
    assert stats["by_relation"]["GUARDS"]["groups"]["guard_operands"]["fraction"]==.5
    assert stats["totals"]["all_zero_fraction"]==.5
    assert all(np.array_equal(attrs[k],before[k]) for k in attrs)


def test_feature_calculation_has_no_stats_import_or_label_fields():
    from scripts.edge_sem import attrs,attr_sources
    for module in (attrs,attr_sources):
        source=Path(module.__file__).read_text()
        tree=ast.parse(source)
        for n in ast.walk(tree):
            if isinstance(n,ast.ImportFrom):
                assert "attr_stats" not in (n.module or "")
            if isinstance(n,ast.Str):
                assert n.s not in ("type_label","node_info_vulnerabilities","method","label","prediction")


def test_every_enabled_bit_has_documented_group():
    indices=[i for v in GROUPS.values() for i in v]
    assert sorted(indices)==list(range(15))+list(range(16,74))
    assert len(indices)==len(set(indices))


def test_fact_digest_preserves_mixed_node_id_types_and_row_order():
    from scripts.edge_sem.attr_batch import facts_digest
    x={1:{"node_kind":"statement"},"env:1":{"node_kind":"env"}}
    assert facts_digest(x)==facts_digest(dict(x))
    assert facts_digest(x)!=facts_digest({"1":x[1],"env:1":x["env:1"]})
    assert facts_digest(x)!=facts_digest({"env:1":x["env:1"],1:x[1]})


def test_loader_rejects_source_layout_values_and_graph_tampering(tmp_path, monkeypatch):
    import json
    import pytest
    from scripts.edge_sem import attr_batch as store
    from scripts.edge_sem.io import ref
    from scripts.edge_sem.attrs import edge_rows
    from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint

    graph=nx.MultiDiGraph()
    for n in (1,2):graph.add_node(n,node_type="expression_statement",source_file="fixture.sol")
    graph.add_edge(1,2,edge_type="next_line")
    keys=[r["key"] for r in edge_rows(graph,[])]
    matrix=np.zeros((1,74),dtype=np.uint8)
    source=tmp_path/"source.sol";source.write_text("contract C {}",encoding="utf8")
    def save(name,value):
        path=tmp_path/name;path.write_text(json.dumps(value),encoding="utf8");return ref(path)
    layout=save("layout.json",dict(names=list(EDGE_FEATURE_NAMES),dimension=74,dtype="uint8"))
    selection=save("selection.json",dict(core_indices=[],context_indices=[],per_task={}))
    dummy=save("dummy.json",{})
    arrays=tmp_path/"attrs.npz"
    np.savez_compressed(str(arrays),edge_keys=np.asarray(keys),attrs=matrix)
    manifest=dict(version="edgesem-attrs-v1",task_id="reentrancy_node",dimension=74,dtype="uint8",
        implementation=[],sources={"fixture.sol":ref(source)},
        input_provenance=dict(graphs={},plan=dummy,store=dummy,audit=dummy),
        attrs=ref(arrays),diagnostics=dummy,facts=dummy,f4_manifest=dummy,layout=layout,
        selection=selection,core_indices=[],context_indices=[],rows=1,
        numeric_digest=numeric_digest(keys,matrix),original_fingerprint=graph_fingerprint(graph))
    # Only the separate F4 loader is stubbed; this test exercises the real
    # attribute loader's integrity, layout, array and identity boundaries.
    monkeypatch.setattr(store,"load_edges",lambda p:[])
    def seal():
        r=save("manifest.json",manifest);save("manifest.seal.json",dict(manifest=r))
        return tmp_path/"manifest.json"
    path=seal()
    assert np.array_equal(store.load_attributes(path,graph,[])[keys[0]],matrix[0])
    source.write_text("contract Changed {}",encoding="utf8")
    with pytest.raises(ValueError,match="SHA mismatch"):store.load_attributes(path,graph,[])
    source.write_text("contract C {}",encoding="utf8")
    changed=graph.copy();changed.add_edge(2,1,edge_type="next_line")
    with pytest.raises(ValueError,match="graph identity"):store.load_attributes(path,changed,[])
    manifest["layout"]=save("wrong_layout.json",dict(names=list(reversed(EDGE_FEATURE_NAMES)),dimension=74,dtype="uint8"));seal()
    with pytest.raises(ValueError,match="feature layout"):store.load_attributes(path,graph,[])
    manifest["layout"]=layout
    matrix[0,0]=2
    np.savez_compressed(str(arrays),edge_keys=np.asarray(keys),attrs=matrix)
    manifest["attrs"]=ref(arrays);manifest["numeric_digest"]=numeric_digest(keys,matrix);seal()
    with pytest.raises(ValueError,match="binary"):store.load_attributes(path,graph,[])
