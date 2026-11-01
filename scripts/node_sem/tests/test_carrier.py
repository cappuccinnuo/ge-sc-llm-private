import copy
import json
import numpy as np
import pytest

from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.spelling_features import assemble
from scripts.node_sem.carrier import carry, load_modality, write_carrier
from scripts.node_sem.tests.carrier_fixtures import make_spelling_fixture, token_spec, dump


@pytest.mark.parametrize("enhanced", [False, True])
@pytest.mark.parametrize("name", ["S0", "S1"])
def test_carrier_exact_spelling_features_and_input_unchanged(tmp_path, enhanced, name):
    fixture = make_spelling_fixture(tmp_path, enhanced)
    graph = fixture["graph"]
    before = graph_fingerprint(graph)
    expected = assemble(graph, fixture["view_ref"])
    carried, record = carry(graph, token_spec(fixture, name), fixture["task_id"])
    assert list(carried) == list(graph)
    assert record["feature_shape"] == [len(graph), 512 if name == "S0" else 513]
    assert record["original_inputs_unchanged"]
    for node in graph:
        vector = carried.nodes[node]["token"]
        if name == "S0":
            assert np.array_equal(vector, expected.nodes[node]["token"])
        else:
            assert vector[0] == bool(np.any(expected.nodes[node]["token"]))
            assert np.array_equal(vector[1:], expected.nodes[node]["token"])
    assert graph_fingerprint(graph) == before
    for node in carried:
        carried.nodes[node]["token"][0] = 1000
    assert graph_fingerprint(graph) == before


@pytest.mark.parametrize("mutation", [
    "sha", "version", "task", "view", "rows", "duplicate", "node_identity",
    "source_sha", "code_sha", "node_type", "vector_sha", "dimension",
    "dtype", "nan", "npz_name", "graph_fingerprint",
])
def test_carrier_rejects_manifest_array_and_graph_tampering(tmp_path, mutation):
    fixture = make_spelling_fixture(tmp_path)
    view = copy.deepcopy(fixture["view"])
    if mutation == "sha":
        fixture["view_ref"]["sha256"] = "0" * 64
    elif mutation == "version":
        view["version"] = "wrong"
    elif mutation == "task":
        view["task_id"] = "other"
    elif mutation == "view":
        view["view"] = "original"
    elif mutation == "rows":
        view["rows"].reverse()
    elif mutation == "duplicate":
        view["rows"][1] = copy.deepcopy(view["rows"][0])
    elif mutation == "node_identity":
        view["rows"][0]["original_graph_node_id"] = "wrong-node"
    elif mutation == "source_sha":
        view["rows"][0]["source_sha256"] = "0" * 64
    elif mutation == "code_sha":
        view["rows"][0]["code_sha256"] = "0" * 64
    elif mutation == "node_type":
        view["rows"][0]["node_type"] = "wrong-type"
    elif mutation == "vector_sha":
        view["rows"][0]["anonymous_vector_sha256"] = "0" * 64
    elif mutation == "dimension":
        view["feature_shape"][1] = 511
    elif mutation == "graph_fingerprint":
        view["profiles"]["G0"]["graph_fingerprint"] = "0" * 64
    else:
        with np.load(str(fixture["data"]), allow_pickle=False) as archive:
            values = archive["features"].copy()
        if mutation == "dtype":
            values = values.astype(np.float64)
        elif mutation == "nan":
            values[0, 0] = np.nan
        np.savez_compressed(str(fixture["data"]), **{
            "unexpected" if mutation == "npz_name" else "features": values})
        from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
        view["data"] = ref(fixture["data"])
    if mutation != "sha":
        fixture["view_ref"] = dump(fixture["manifest"], view)
    with pytest.raises((ValueError, KeyError)):
        carry(fixture["graph"], token_spec(fixture), fixture["task_id"])


def test_modality_returns_detached_copies_and_original_token_is_unchanged(tmp_path):
    fixture = make_spelling_fixture(tmp_path)
    loaded = load_modality(fixture["view_ref"])
    first = next(iter(loaded))
    assert np.array_equal(loaded[first], assemble(fixture["graph"], fixture["view_ref"]).nodes[first]["token"])
    loaded[first][0] = 300
    assert load_modality(fixture["view_ref"])[first][0] != 300


def test_write_carrier_manifest_and_npz_order_are_bound_and_exclusive(tmp_path):
    fixture = make_spelling_fixture(tmp_path, True)
    output = tmp_path / "carrier"
    written = write_carrier(token_spec(fixture, "S1"), fixture["task_id"], fixture["graph"], output)
    manifest = json.loads((output / "carrier_manifest.json").read_text())
    assert manifest["data"] == written["data"]
    assert [r["original_graph_node_id"] for r in manifest["rows"]] == list(fixture["graph"])
    with np.load(str(output / "carrier.npz"), allow_pickle=False) as archive:
        assert set(archive.files) == {"features"}
        assert archive["features"].dtype == np.float32
        assert archive["features"].shape == (len(fixture["graph"]), 513)
    assert any(r["row_key"].startswith("env:") for r in manifest["rows"])
    with pytest.raises(FileExistsError):
        write_carrier(token_spec(fixture, "S1"), fixture["task_id"], fixture["graph"], output)


def _generic(fixture, tmp_path):
    import hashlib
    from scripts.node_sem import CODE
    from scripts.node_sem.carrier import MODALITY_VERSION, row_key, vector_sha
    from scripts.node_sem.feature_spec import FeatureSpec
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
    graph = fixture["graph"]
    matrix = np.arange(len(graph) * 3, dtype=np.float32).reshape(len(graph), 3)
    matrix[1] = 0
    data = tmp_path / "code.npz"
    np.savez_compressed(str(data), features=matrix)
    text = tmp_path / "input_text.json"
    text.write_text("{}", encoding="utf8")
    rows = [dict(row_key=row_key(n, a), file=a["source_file"], node_type=a["node_type"],
                 source_sha256=fixture["sources"][a["source_file"]]["sha256"],
                 code_sha256=hashlib.sha256(a["code"].encode("utf8")).hexdigest(),
                 vector_sha256=vector_sha(matrix[i]), present=i != 1)
            for i, (n, a) in enumerate(graph.nodes(data=True))]
    view = dict(version=MODALITY_VERSION, view="anonymous", task_id=fixture["task_id"],
                modality=CODE, rows=rows, data=ref(data), feature_shape=list(matrix.shape),
                feature_dtype="float32", sources=fixture["sources"],
                implementation={"fixture": ref(__file__)}, assets={}, input_text=ref(text),
                profiles={"fixture": {"graph_fingerprint": graph_fingerprint(graph)}})
    path = tmp_path / "code_manifest.json"
    view_ref = dump(path, view)
    spec = FeatureSpec("S2", "anonymous",
                       [dict(name=CODE, dim=3, manifest=view_ref, normalize=True)],
                       "none", "concat")
    return spec, view, path, data, matrix


def test_generic_modality_alignment_and_missing_presence(tmp_path):
    fixture = make_spelling_fixture(tmp_path, True)
    spec, view, path, data, matrix = _generic(fixture, tmp_path)
    graph, record = carry(fixture["graph"], spec, fixture["task_id"])
    for index, attrs in enumerate(dict(graph.nodes(data=True)).values()):
        assert attrs["token"][0] == (index != 1)
        assert np.array_equal(attrs["token"][1:], matrix[index])
    assert record["feature_shape"] == [len(graph), 4]


@pytest.mark.parametrize("mutation", ["row_order", "absent_nonzero", "presence",
                                     "input_text", "source_content", "graph",
                                     "modality", "code", "node_identity", "dimensions"])
def test_generic_modality_rejects_context_and_artifact_tampering(tmp_path, mutation):
    from scripts.node_sem.feature_spec import FeatureSpec
    fixture = make_spelling_fixture(tmp_path, True)
    spec, view, path, data, matrix = _generic(fixture, tmp_path)
    if mutation == "row_order":
        view["rows"].reverse()
    elif mutation == "absent_nonzero":
        view["rows"][0]["present"] = False
    elif mutation == "presence":
        view["rows"][0]["present"] = 1
    elif mutation == "input_text":
        view["input_text"]["sha256"] = "0" * 64
    elif mutation == "source_content":
        source = next(iter(fixture["sources"].values()))
        from pathlib import Path
        Path(source["path"]).write_text("modified", encoding="utf8")
    elif mutation == "graph":
        view["profiles"]["fixture"]["graph_fingerprint"] = "0" * 64
    elif mutation == "modality":
        view["modality"] = "wrong"
    elif mutation == "code":
        view["rows"][0]["code_sha256"] = "0" * 64
    elif mutation == "node_identity":
        view["rows"][0]["row_key"] = "wrong"
    elif mutation == "dimensions":
        view["feature_shape"][1] += 1
    values = spec.to_json()
    values["modalities"][0]["manifest"] = dump(path, view)
    altered = FeatureSpec.from_json(values)
    with pytest.raises(ValueError):
        carry(fixture["graph"], altered, fixture["task_id"])


@pytest.mark.parametrize("name", ["S0", "S1"])
@pytest.mark.parametrize("perturbation", ["forbidden_attributes", "label_prefix"])
def test_feature_independence_with_separately_bound_disposable_fixture(tmp_path, name, perturbation):
    """Rebinding here changes only a disposable fixture's input fingerprint.

    The sealed production gate stays strict: the old manifest first rejects
    the changed fixture. Features, row/code/source identities and NPZ stay exact.
    """
    from scripts.DFG.projection import ANCHOR, decoded
    fixture = make_spelling_fixture(tmp_path, True)
    graph = fixture["graph"]
    baseline, _ = carry(graph, token_spec(fixture, name), fixture["task_id"])
    altered = copy.deepcopy(graph)
    for _, attrs in altered.nodes(data=True):
        if attrs["node_type"] == "env_source":
            continue
        if perturbation == "forbidden_attributes":
            attrs["node_info_vulnerabilities"] = [{"category": "changed", "lines": [999]}]
            attrs["type_label"] = 12345
            attrs["method"] = "unrelated-private-label"
        else:
            anchor = ANCHOR.search(decoded(attrs["label"]))
            assert anchor is not None
            attrs["label"] = "changed text that is not a feature-" + anchor.group(0)
    with pytest.raises(ValueError, match="Graph schema"):
        carry(altered, token_spec(fixture, name), fixture["task_id"])
    rebound = copy.deepcopy(fixture["view"])
    for profile in rebound["profiles"].values():
        profile["graph_fingerprint"] = graph_fingerprint(altered)
    fixture["view_ref"] = dump(tmp_path / "rebound_fixture_only.json", rebound)
    carried, _ = carry(altered, token_spec(fixture, name), fixture["task_id"])
    assert rebound["rows"] == fixture["view"]["rows"]
    assert rebound["data"] == fixture["view"]["data"]
    assert rebound["sources"] == fixture["view"]["sources"]
    for node in graph:
        assert np.array_equal(carried.nodes[node]["token"], baseline.nodes[node]["token"])


def test_corrupted_anchor_rejected_even_with_fixture_fingerprint_rebound(tmp_path):
    from scripts.DFG.models import Unsupported
    fixture = make_spelling_fixture(tmp_path)
    altered = copy.deepcopy(fixture["graph"])
    node = next(iter(altered))
    altered.nodes[node]["label"] = "missing AST anchor"
    rebound = copy.deepcopy(fixture["view"])
    rebound["profiles"]["G0"]["graph_fingerprint"] = graph_fingerprint(altered)
    fixture["view_ref"] = dump(tmp_path / "rebound_invalid_anchor.json", rebound)
    with pytest.raises(Unsupported, match="anchor"):
        carry(altered, token_spec(fixture), fixture["task_id"])

def test_duplicate_auxiliary_feature_identity_rejected(tmp_path):
    fixture = make_spelling_fixture(tmp_path, True)
    graph = fixture["graph"]
    env = next(n for n, a in graph.nodes(data=True) if a["node_type"] == "env_source")
    graph.add_node("duplicate-env", **copy.deepcopy(graph.nodes[env]))
    with pytest.raises(ValueError, match="duplicate feature"):
        carry(graph, token_spec(fixture), fixture["task_id"])
