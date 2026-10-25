"""Synthetic CLI/store integration; no real training or tokenizer equivalence."""
import copy
from pathlib import Path

import pytest

from scripts.DFG.integration.io import read_json, sha256, write_json
from scripts.DFG.dfg_v2 import cli, store
from scripts.DFG.dfg_v2.inputs import build_manifest, load_manifest
from scripts.DFG.dfg_v2.tests.task_fixtures import synthetic_registry, SyntheticEncoder


@pytest.fixture
def setup(tmp_path, monkeypatch):
    registry = synthetic_registry(tmp_path)
    manifest = build_manifest(tmp_path / "inputs", registry=registry)
    monkeypatch.setattr(store, "TokenEncoder", SyntheticEncoder)
    # Synthetic runtime fixture: real runtime binding is exercised by real builds.
    monkeypatch.setattr(store, "_runtime", lambda: {"synthetic_runtime.py": "frozen"})
    return manifest, tmp_path / "store"


@pytest.fixture
def built(setup):
    manifest, output = setup
    result = store.build_store(manifest, tasks=["synthetic_contract"], output=output)
    return manifest, output, result


def resign(output, document):
    write_json(output / "store.json", document)
    seal = read_json(output / "store.seal.json")
    seal["store_sha256"] = sha256(output / "store.json")
    write_json(output / "store.seal.json", seal)


def test_default_four_tasks_construct_twenty_cpu_models_without_forward(tmp_path, monkeypatch):
    registry = synthetic_registry(tmp_path, "alpha")
    registry.update(synthetic_registry(tmp_path, "beta"))
    manifest = build_manifest(tmp_path / "inputs", registry=registry)
    monkeypatch.setattr(store, "TokenEncoder", SyntheticEncoder)
    monkeypatch.setattr(store, "_runtime", lambda: {"fixture.py": "fixed"})
    from scripts.DFG.dfg_v2.model import DfgV2NodeClassifier, DfgV2GraphClassifier
    def no_forward(*args, **kwargs):
        raise AssertionError("A real graph forward is not permitted by build/verify")
    monkeypatch.setattr(DfgV2NodeClassifier, "forward", no_forward)
    monkeypatch.setattr(DfgV2GraphClassifier, "forward", no_forward)
    calls = {"load": 0, "iterator": 0, "model": 0}
    original_load, original_iter, original_model = store.load_task, store.iter_build, store.make_model
    def load(record):
        calls["load"] += 1
        return original_load(record)
    def iterator(*args, **kwargs):
        calls["iterator"] += 1
        return original_iter(*args, **kwargs)
    def model(*args, **kwargs):
        calls["model"] += 1
        return original_model(*args, **kwargs)
    monkeypatch.setattr(store, "load_task", load)
    monkeypatch.setattr(store, "iter_build", iterator)
    monkeypatch.setattr(store, "make_model", model)
    result = store.build_store(manifest, output=tmp_path / "store")
    assert calls == {"load": 4, "iterator": 4, "model": 20}
    assert result["model_constructions"] == 20
    assert result["graph_keys_produced"] == 16
    assert not result["model_forward_executed"] and not result["training_executed"]
    assert result["runtime_start_end_equal"]
    for task in result["tasks"].values():
        assert set(task["graphs"]) == {"F0", "F1", "F2", "F3"}
        assert task["source_load_calls"] == task["pipeline_iteration_calls"] == 1
        for entry in task["graphs"].values():
            assert all(model["device"] == "cpu" and not model["model_forward_executed"]
                       for model in entry["profiles"].values())


def test_f0_is_exact_original_path_sha_and_no_reserialized_copy(built):
    manifest, output, result = built
    original = load_manifest(manifest)["tasks"]["synthetic_contract"]["original_graph"]
    f0 = result["tasks"]["synthetic_contract"]["graphs"]["F0"]["graph"]
    assert f0["path"] == original["path"] and f0["sha256"] == original["sha256"]
    assert Path(f0["path"]).read_bytes() == Path(original["path"]).read_bytes()
    assert not (output / "synthetic_contract/F0/hcg.gpickle").exists()
    assert (output / "synthetic_contract/F0/audit.json").exists()


def test_requested_f3_saves_only_f0_f3_but_contains_all_layer_evidence(setup):
    manifest, output = setup
    result = store.build_store(manifest, tasks="synthetic_node", graph_keys="F3", output=output)
    task = result["tasks"]["synthetic_node"]
    assert set(task["graphs"]) == {"F0", "F3"}
    assert not (output / "synthetic_node/F1").exists()
    assert not (output / "synthetic_node/F2").exists()
    audit = read_json(task["graphs"]["F3"]["audit"]["path"])
    assert set(audit["layers"]) == {"L1", "L2", "L3"}
    assert result["model_constructions"] == 3
    assert set(task["graphs"]["F3"]["profiles"]) == {"G3R", "G3"}


def test_f0_only_does_not_invoke_tokenizer(setup, monkeypatch):
    manifest, output = setup
    def forbidden(*args, **kwargs):
        raise AssertionError("F0 must not encode new features")
    monkeypatch.setattr(store, "TokenEncoder", forbidden)
    result = store.build_store(manifest, tasks="synthetic_contract", graph_keys="F0", output=output)
    assert result["model_constructions"] == 1 and result["graph_keys_produced"] == 1


def test_existing_output_is_never_overwritten(built):
    manifest, output, _ = built
    before = sha256(output / "store.json")
    with pytest.raises(FileExistsError):
        store.build_store(manifest, output=output)
    assert sha256(output / "store.json") == before


@pytest.mark.parametrize("keys", ["G0", "F9", "F1,F1", ""])
def test_invalid_graph_selection_rejected_before_output(setup, keys):
    manifest, output = setup
    with pytest.raises(ValueError):
        store.build_store(manifest, graph_keys=keys, output=output)
    assert not output.exists()


@pytest.mark.parametrize("tasks", ["unknown_contract", "synthetic_contract,synthetic_contract", ""])
def test_invalid_task_selection_rejected_before_output(setup, tasks):
    manifest, output = setup
    with pytest.raises(ValueError):
        store.build_store(manifest, tasks=tasks, output=output)
    assert not output.exists()


@pytest.mark.parametrize("damage", ["store", "seal", "graph", "audit", "input", "source", "summary"])
def test_artifact_and_input_tampering_rejected(built, damage):
    manifest, output, result = built
    task = result["tasks"]["synthetic_contract"]
    paths = dict(store=output / "store.json", seal=output / "store.seal.json",
        graph=Path(task["graphs"]["F1"]["graph"]["path"]),
        audit=Path(task["graphs"]["F3"]["audit"]["path"]),
        input=manifest, summary=output / "build_summary.csv")
    if damage == "source":
        source = next(iter(load_manifest(manifest)["tasks"]["synthetic_contract"]["sources"].values()))
        path = Path(source["path"])
    else:
        path = paths[damage]
    if damage == "seal":
        seal = read_json(path)
        seal["store_sha256"] = "0"*64
        write_json(path, seal)
    else:
        path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises((ValueError, KeyError)):
        store.verify_store(output / "store.json")


@pytest.mark.parametrize("field", ["fingerprint", "computation_fingerprint", "nodes"])
def test_graph_fingerprint_binding_checked_even_when_store_is_resealed(built, field):
    _, output, result = built
    ref = result["tasks"]["synthetic_contract"]["graphs"]["F1"]["graph"]
    ref[field] = 1 if field == "nodes" else "0"*64
    resign(output, result)
    with pytest.raises(ValueError, match="fingerprint"):
        store.verify_store(output / "store.json")


def test_f0_copy_rejected_even_if_byte_identical_and_store_resealed(built):
    _, output, result = built
    ref = result["tasks"]["synthetic_contract"]["graphs"]["F0"]["graph"]
    duplicate = output / "copied_original.gpickle"
    duplicate.write_bytes(Path(ref["path"]).read_bytes())
    ref["path"] = str(duplicate)
    resign(output, result)
    with pytest.raises(ValueError, match="exact original"):
        store.verify_store(output / "store.json")


def test_schema_dictionary_misalignment_rejected_after_reseal(built):
    _, output, result = built
    model = result["tasks"]["synthetic_contract"]["graphs"]["F3"]["profiles"]["G3R"]
    model["schema"]["canonical_relations"][0]["index"] += 1
    resign(output, result)
    with pytest.raises(ValueError, match="schema"):
        store.verify_store(output / "store.json")


def test_audit_graph_binding_checked_after_reseal(built):
    _, output, result = built
    ref = result["tasks"]["synthetic_contract"]["graphs"]["F2"]["audit"]
    audit = read_json(ref["path"])
    audit["input_fingerprint"] = "0"*64
    write_json(ref["path"], audit)
    ref["sha256"] = sha256(ref["path"])
    resign(output, result)
    with pytest.raises(ValueError, match="audit"):
        store.verify_store(output / "store.json")


def test_verify_allows_unrelated_python_change_and_never_constructs_hgt(built, monkeypatch):
    _, output, _ = built
    (output / "unrelated_new.py").write_text("unrelated = True\n")
    def forbidden(*args, **kwargs):
        raise AssertionError("Verification must not compare runtime or construct HGT")
    monkeypatch.setattr(store, "_runtime", forbidden)
    monkeypatch.setattr(store, "make_model", forbidden)
    result = store.verify_store(output / "store.json")
    assert result["status"] == "accepted"
    assert result["verification_model_constructions"] == 0
    assert result["current_runtime_required_to_match"] is False


def test_runtime_change_during_build_rejected_without_acceptance_seal(setup, monkeypatch):
    manifest, output = setup
    state = {"changed": False}
    original = store.iter_build
    def iterator(*args, **kwargs):
        for row in original(*args, **kwargs):
            state["changed"] = True
            yield row
    monkeypatch.setattr(store, "iter_build", iterator)
    monkeypatch.setattr(store, "_runtime", lambda: {"fixture.py": str(state["changed"])})
    with pytest.raises(AssertionError, match="Runtime source"):
        store.build_store(manifest, tasks="synthetic_contract", graph_keys="F0", output=output)
    assert not (output / "store.seal.json").exists()


def test_cli_build_verify_and_help(setup, capsys):
    manifest, output = setup
    built = cli.main(["build", "--manifest", str(manifest), "--tasks", "synthetic_node",
                      "--graph-keys", "F0", "--output", str(output)])
    assert built["model_constructions"] == 1 and not built["model_forward_executed"]
    result = cli.main(["verify", "--store", str(output / "store.json")])
    assert result["status"] == "accepted"
    with pytest.raises(SystemExit) as exc:
        cli.main(["build", "--help"])
    assert exc.value.code == 0
    assert "computed but not saved" in " ".join(capsys.readouterr().out.split())
