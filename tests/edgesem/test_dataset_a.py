"""Dataset A end to end: HCG -> DFG -> EdgeSem build, against two references.

1. ``reference/old_code.json``: canonical digests of the F4 edges and edge attributes that
   the unmodified scripts/edge_sem producers (archive branch, with the networkx dominator-root
   fix) compute on the same graphs, all 7 categories x 2 tasks.
2. Sealed EdgeSem evidence built from the authors' graphs: F4 edges of reentrancy and
   access control (both tasks), edge attributes of their node tasks, and the initial weights
   of every trained profile (G3R, G3R-T, G4R, G4R-P, G3R-TA, G4R-A, G4R-Api) on folds 0 and 9.

Endpoints are canonicalized (tests/edgesem/canonical.py) because global node ids differ
between graph builds. Needs $MANDO_DATA_DIR (``python -m hcg fetch``).
"""
import json
from pathlib import Path

import numpy as np
import pytest

from dfg.inputs import load_task
from dfg.store import build_task as build_dfg
from dfg.utils import tensor_digest
from edgesem.model.build import make_edge_model
from edgesem.pipeline import build_task
from edgesem.schema import PROFILES
from edgesem.store import EdgeStore
from hcg.datasets import DATASET_A
from hcg.pipeline import build_category
from hcg.store.io import read_gpickle
from tests.dfg.test_dataset_a import LABEL_ROOT, _ready
from tests.dfg.test_units import fake_encoder
from tests.edgesem.canonical import attribute_digest, f4_digest, graph_positions

REFERENCE = Path(__file__).parent / "reference"
CATEGORIES = [c.name for c in DATASET_A.categories]
pytestmark = pytest.mark.skipif(_ready() is not None, reason=str(_ready()))


@pytest.fixture(scope="module")
def roots(tmp_path_factory):
    return tmp_path_factory.mktemp("hcg"), tmp_path_factory.mktemp("dfg"), tmp_path_factory.mktemp("edgesem")


@pytest.mark.parametrize("task", ["contract", "node"])
@pytest.mark.parametrize("category", CATEGORIES)
def test_edgesem_build_matches_references(category, task, roots):
    hcg_root, dfg_root, edgesem_root = roots
    if not (hcg_root / "A" / category / "manifest.json").exists():
        build_category(DATASET_A, category, hcg_root, LABEL_ROOT, tokenizer=None, log=lambda *a: None)
    inp = load_task(hcg_root, "A", category, task, LABEL_ROOT)
    for _, data in inp.graph.nodes(data=True):
        data["token"] = np.zeros(512, dtype=np.float32)
    build_dfg(inp, dfg_root / "A" / category / task, token_encoder=fake_encoder, profiles=False, log=lambda *a: None)
    summary = build_task("A", category, task, hcg_root, dfg_root, edgesem_root, LABEL_ROOT, log=lambda *a: None)
    store = EdgeStore(edgesem_root, "A", category, task)
    edges, attrs = store.edges(), store.attributes()
    graph = read_gpickle(dfg_root / "A" / category / task / "F3/graph.gpickle")
    pos = graph_positions(graph)
    task_id = summary["task_id"]
    mine = dict(f4_rows=len(edges), f4_counts=summary["f4_counts"], f4=f4_digest(edges, pos),
                attribute_rows=len(attrs),
                attributes=attribute_digest(list(attrs), np.stack(list(attrs.values())), pos))
    assert mine == json.loads((REFERENCE / "old_code.json").read_text())[task_id]

    sealed = json.loads((REFERENCE / "sealed.json").read_text())
    if task_id in sealed["f4"]:
        assert mine["f4"] == sealed["f4"][task_id]["digest"]
    if task_id in sealed["attributes"]:
        assert mine["attributes"] == sealed["attributes"][task_id]["digest"]
    for fold, expected in sorted(sealed["initial"].get(task_id, {}).items()):
        if fold not in ("0", "9"):
            continue
        for profile, sha in expected.items():
            uses = PROFILES[profile]["edge_features"] != "none"
            model = make_edge_model(task, graph, profile, int(fold), edges=edges, attrs=attrs if uses else None)
            assert tensor_digest(model.state_dict()) == sha, (fold, profile)
