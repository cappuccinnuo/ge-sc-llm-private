"""Dataset A end to end: HCG -> DFG -> NodeSem analysis, against two references.

1. ``reference/old_code.json``: per-row digests of the unmodified scripts/node_sem
   producers (archive branch) on the same graphs, all 7 categories x 2 tasks.
2. Sealed NodeSem evidence for reentrancy and access control (built from the
   authors' graphs): per-file digests of code text, facts, CTX fields and STATIC
   vectors (node references and list order canonicalized, since global node ids and
   edge order differ between graph builds); every LLM prompt key of the task is one
   of the 4,485 sealed keys; fold-0 initial weights of S0o/S2/S4 x G0/G3R equal the
   sealed N-A digests.

Needs $MANDO_DATA_DIR (``python -m hcg fetch``); a category takes a few minutes.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from dfg.graph.pipeline import key_for_profile
from dfg.inputs import load_task
from dfg.store import build_task
from dfg.train.runner import initial_states
from dfg.train.trainer import task_config
from hcg.datasets import DATASET_A
from hcg.pipeline import build_category
from nodesem.features import FeatureSpec, carry
from nodesem.init import initial_state
from nodesem.inputs import load_context
from nodesem.llm.generate import plan_units
from nodesem.model import make_nodesem_model
from nodesem.pipeline import analyze
from nodesem.rows import vector_sha
from tests.dfg.test_dataset_a import LABEL_ROOT, _ready
from tests.dfg.test_units import fake_encoder
from tests.nodesem.canonical import analysis_digests, digest, strip
from tests.nodesem.test_units import _tables

REFERENCE = Path(__file__).parent / "reference"
CATEGORIES = [c.name for c in DATASET_A.categories]
pytestmark = pytest.mark.skipif(_ready() is not None, reason=str(_ready()))
H = lambda o: hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()  # noqa: E731


@pytest.fixture(scope="module")
def roots(tmp_path_factory):
    return tmp_path_factory.mktemp("hcg"), tmp_path_factory.mktemp("dfg")


@pytest.mark.parametrize("task", ["contract", "node"])
@pytest.mark.parametrize("category", CATEGORIES)
def test_nodesem_analysis_matches_references(category, task, roots):
    hcg_root, dfg_root = roots
    if not (hcg_root / "A" / category / "manifest.json").exists():
        build_category(DATASET_A, category, hcg_root, LABEL_ROOT, tokenizer=None, log=lambda *a: None)
    inp = load_task(hcg_root, "A", category, task, LABEL_ROOT)
    for _, data in inp.graph.nodes(data=True):
        data["token"] = np.zeros(512, dtype=np.float32)
    build_task(inp, dfg_root / "A" / category / task, token_encoder=fake_encoder, profiles=False, log=lambda *a: None)
    context = load_context("A", category, task, hcg_root, dfg_root, LABEL_ROOT)
    out = analyze(context)
    mine = dict(rows=len(out["text"]),
                text=digest([H({k: r[k] for k in r if k != "source_sha256"}) for r in out["text"]]),
                facts=digest([H(strip(r["facts"])) for r in out["facts"]]),
                ctx=digest([H(r["fields"]) for r in out["ctx"]]),
                ctx_masked=digest([H(r["fields"]) for r in out["ctx_masked"]]),
                static=digest([vector_sha(v) for v in out["static"]]),
                row_keys=digest([r["row_key"] for r in out["text"]]))
    assert mine == json.loads((REFERENCE / "old_code.json").read_text())[context["task_id"]]

    sealed = json.loads((REFERENCE / "sealed.json").read_text())
    if context["task_id"] not in sealed["analysis"]:
        return
    got = analysis_digests(out["text"], [r["facts"] for r in out["facts"]], [r["fields"] for r in out["ctx"]],
                           [vector_sha(v) for v in out["static"]])
    assert got == sealed["analysis"][context["task_id"]]
    units, _, _ = plan_units([(context, dict(text=out["text"], facts=out["facts"]))])
    keys = set(json.loads((REFERENCE / "sealed_prompt_keys.json").read_text())["keys"])
    assert units and set(units) <= keys

    graphs = {"F0": context["graphs"]["F0"], "F3": context["graphs"]["F3"]}
    for g in graphs.values():
        for _, data in g.nodes(data=True):
            data.setdefault("token", np.zeros(512, dtype=np.float32))
    config = task_config(task)
    seeds, base = initial_states(task, lambda p: graphs[key_for_profile(p)], 0, ["G0", "G3R"], config)
    for name, item in sealed["initial"][context["task_id"]].items():
        config_name, profile = name.split("@")
        spec = FeatureSpec.from_json(item["spec"])
        graph = graphs[key_for_profile(profile)]
        carried, record = carry(graph, spec, _tables(graph, spec, present=False, value=0.0))
        model = make_nodesem_model(task, carried, record, profile, spec, config)
        _, sha = initial_state(model, spec, context["task_id"], 0, profile, base[profile], seeds["constructor"])
        assert sha == item["state_sha256"], name
