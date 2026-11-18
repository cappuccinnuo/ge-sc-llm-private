"""NodeSem unit tests: configurations, carrier, initialization rules, LLM cache, students, CLI."""
import numpy as np
import pytest
import torch

from nodesem.features import CONFIGS, EXTENDS, carry, spec_for
from nodesem.init import extend_state
from nodesem.llm import generate as gen
from nodesem.llm.protocol import cache_key, messages
from nodesem.student import fit_student, permute
from tests.dfg.test_units import CORPUS, CONTRACT


def test_configurations():
    assert spec_for("S4").carrier_dim() == 3 + 256 + 256 + 245
    assert spec_for("S0o").carrier_dim() == 512 and spec_for("S1o").carrier_dim() == 1 + 512
    for name, base in EXTENDS.items():
        ext, s4 = CONFIGS[name]["modalities"], CONFIGS[base]["modalities"]
        assert ext[:3] == s4 and len(ext) == 4 and ext[3]["dim"] == 384
    assert spec_for("S5").digest() != spec_for("S8").digest()
    assert CONFIGS["S4-noG"]["layers"] == 0


@pytest.fixture(scope="module")
def graph():
    from hcg.cfg.builder import build_corpus
    g, failures = build_corpus([CORPUS / CONTRACT])
    assert not failures
    for _, data in g.nodes(data=True):
        data["token"] = np.zeros(512, dtype=np.float32)
    return g


def _tables(g, spec, present=True, value=0.5):
    from nodesem.features import _sha_text
    from nodesem.rows import row_key
    rows = [(row_key(n, a), a) for n, a in g.nodes(data=True)]
    out = {}
    for m in spec.modalities:
        out[m["name"]] = dict(row_keys=[k for k, _ in rows], values=np.full((len(rows), m["dim"]), value, np.float32),
                              present=[present] * len(rows), file=[a["source_file"] for _, a in rows],
                              node_type=[a["node_type"] for _, a in rows],
                              code_sha256=[_sha_text(a["code"]) for _, a in rows])
    return out


def test_carry_layout_and_identity_checks(graph):
    spec = spec_for("S2")
    carried, record = carry(graph, spec, _tables(graph, spec))
    vector = next(iter(carried.nodes(data=True)))[1]["token"]
    assert vector.shape == (257,) and vector[0] == 1.0 and np.all(vector[1:] == 0.5)
    assert all(np.all(d["token"] == 0) for _, d in graph.nodes(data=True))
    bad = _tables(graph, spec)
    bad["code"]["code_sha256"][0] = "0" * 64
    with pytest.raises(ValueError, match="identity"):
        carry(graph, spec, bad)
    with pytest.raises(ValueError, match="Absent"):
        carry(graph, spec, _tables(graph, spec, present=False))


def test_extension_keeps_only_new_modality_tensors():
    base = {"adapt_ws.0.proj.code.weight": torch.ones(2), "gcs.0.w": torch.ones(1)}
    candidate = dict(base, **{"adapt_ws.0.proj.teacher.weight": torch.zeros(3)})
    candidate = {k: torch.full_like(v, 7.0) for k, v in candidate.items()}
    merged, _ = extend_state(candidate, base, "teacher")
    assert torch.equal(merged["gcs.0.w"], torch.ones(1)) and torch.equal(merged["adapt_ws.0.proj.teacher.weight"],
                                                                        torch.full((3,), 7.0))
    with pytest.raises(ValueError):
        extend_state(dict(candidate, **{"adapt_ws.0.proj.student.weight": torch.ones(1)}), base, "teacher")


class FakeBackend:
    mode = "fake"

    def __init__(self):
        self.calls = 0

    def generate(self, prompt, schema):
        self.calls += 1
        return dict(content='{"function_intent": "moves value", "statements": []}', finish_reason="stop",
                    usage={}, elapsed_seconds=0.0)


def test_generation_is_cached_and_skips_bodyless_units(tmp_path):
    unit = dict(contract_header="contract A", state_vars="uint x;", function_with_lines="1: function f() {}",
                target_lines=[1])
    key = cache_key(unit, gen.MODEL["sha256"], gen.PARAMETERS)
    units = {key: dict(unit, cache_key=key, messages=messages(unit), occurrences=[])}
    backend = FakeBackend()
    first = gen.generate(units, {key: False}, tmp_path, backend, log=lambda *a: None)
    again = gen.generate(units, {key: False}, tmp_path, backend, log=lambda *a: None)
    assert backend.calls == 1 and first[key]["parsed"] == again[key]["parsed"]
    skipped = gen.generate(units, {key: True}, tmp_path / "other", backend, log=lambda *a: None)
    assert skipped[key]["status"] == "skipped_no_body" and backend.calls == 1


def test_student_is_deterministic_and_fold_local():
    rng = np.random.RandomState(0)
    n = 60
    files = ["f%d.sol" % (i % 6) for i in range(n)]
    split = dict(inner_train_files=["f0.sol", "f1.sol", "f2.sol"], inner_val_files=["f3.sol"],
                 outer_test_files=["f4.sol", "f5.sol"])
    ctx = rng.randn(n, 8).astype(np.float32)
    static = rng.rand(n, 3).astype(np.float32)
    teacher = rng.randn(n, 384).astype(np.float32)
    teacher /= np.linalg.norm(teacher, axis=1, keepdims=True)
    present = np.ones(n, bool)
    a = fit_student(ctx, static, teacher, present, files, split, seed=3, max_epochs=3)
    poisoned = teacher.copy()
    poisoned[[i for i, f in enumerate(files) if f in split["outer_test_files"]]] *= -1
    b = fit_student(ctx, static, poisoned, present, files, split, seed=3, max_epochs=3)
    assert np.array_equal(a["values"], b["values"])          # outer-test teacher never used
    permuted, mapping = permute(a["values"], ["x", "y"] * (n // 2), "t", 0, 1)
    assert sorted(mapping.tolist()) == list(range(n)) and all((mapping[i] - i) % 2 == 0 for i in range(n))


def test_cli_rejects_unknown_category():
    from nodesem.__main__ import main
    with pytest.raises(SystemExit, match="unknown categories"):
        main(["analyze", "--categories", "nope"])


def test_codet5_norm_guard_rejects_a_swapped_in_apex_norm():
    """transformers replaces T5LayerNorm with apex's FusedRMSNorm when apex is importable."""
    import types

    import pytest
    import torch
    from transformers import T5Config, T5EncoderModel

    from nodesem.encode import check_norms
    model = T5EncoderModel(T5Config(vocab_size=32, d_model=8, d_kv=4, d_ff=16, num_layers=1, num_heads=2))
    check_norms(model)

    fused = types.new_class("FusedRMSNorm", (torch.nn.Module,))
    fused.__module__ = "apex.normalization.fused_layer_norm"
    model.encoder.final_layer_norm = fused()
    with pytest.raises(RuntimeError, match="apex"):
        check_norms(model)
