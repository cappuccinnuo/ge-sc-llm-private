"""Dataset A end to end: HCG -> DFG for each category and task, against two references.

1. ``reference/fingerprints.json``: content fingerprints of every cumulative layer
   (F0-F3) produced by the pre-restructure code (scripts/DFG, archived on branch
   archive/pre-restructure-2026-11-15) from the same HCG graphs. Node tokens are
   zeroed and env_source nodes use a hash encoder, so no tokenizer is needed.
2. Sealed Prompt 8 evidence for reentrancy and access control (built from the
   authors' graphs): canonical relation edge counts of every profile
   (``reference/sealed_relation_counts.json``), and from
   ``reference/sealed_training.json`` the fold-0 initial parameter digests of every
   profile and the anonymized code of every node, per file.

Needs the pinned label sources ($MANDO_DATA_DIR) and a C compiler for the
tree-sitter grammar; skipped otherwise. A category takes 2-8 min; use -k.
"""
import json
import os
from pathlib import Path

import numpy as np
import pytest

import hashlib

from dfg.graph.audit import computation_fingerprint, fingerprint
from dfg.graph.pipeline import iter_build, key_for_profile, profiles_for_key
from dfg.inputs import load_task
from dfg.store import canonical_counts
from dfg.train.features import anonymous_codes, code_sha
from dfg.train.runner import ALL_PROFILES, initial_states
from dfg.train.trainer import task_config
from dfg.utils import tensor_digest
from hcg.datasets import DATASET_A
from hcg.pipeline import build_category
from hcg.sources import repos
from tests.dfg.test_units import fake_encoder

LABEL_ROOT = os.environ.get("MANDO_DATA_DIR")
REFERENCE = Path(__file__).parent / "reference"
CATEGORIES = [c.name for c in DATASET_A.categories]


def _ready():
    if not LABEL_ROOT:
        return "set MANDO_DATA_DIR to the pinned label sources (python -m hcg fetch)"
    try:
        repos.verify(LABEL_ROOT)
    except SystemExit as exc:
        return str(exc)
    return None


pytestmark = pytest.mark.skipif(_ready() is not None, reason=str(_ready()))


@pytest.fixture(scope="module")
def hcg_root(tmp_path_factory):
    return tmp_path_factory.mktemp("hcg")


@pytest.mark.parametrize("task", ["contract", "node"])
@pytest.mark.parametrize("category", CATEGORIES)
def test_dfg_layers_match_references(category, task, hcg_root):
    if not (hcg_root / "A" / category / "manifest.json").exists():
        build_category(DATASET_A, category, hcg_root, LABEL_ROOT, tokenizer=None, log=lambda *a: None)
    inp = load_task(hcg_root, "A", category, task, LABEL_ROOT)
    for _, data in inp.graph.nodes(data=True):
        data["token"] = np.zeros(512, dtype=np.float32)
    expected = json.loads((REFERENCE / "fingerprints.json").read_text())[inp.task_id]
    sealed = json.loads((REFERENCE / "sealed_relation_counts.json").read_text())["tasks"].get(inp.task_id)
    training = json.loads((REFERENCE / "sealed_training.json").read_text())
    seen, graphs = [], {}
    for key, graph, _ in iter_build(inp.graph, inp.sources, inp.metadata, ("L1", "L2", "L3"),
                                    token_encoder=fake_encoder):
        seen.append(key)
        graphs[key] = graph
        assert (graph.number_of_nodes(), graph.number_of_edges()) == (expected[key]["nodes"], expected[key]["edges"]), key
        assert fingerprint(graph) == expected[key]["fp"], key
        assert computation_fingerprint(graph) == expected[key]["cfp"], key
        if sealed:
            for profile in profiles_for_key(key):
                assert canonical_counts(graph, profile) == sealed[profile], (key, profile)
    assert seen == ["F0", "F1", "F2", "F3"]
    if inp.task_id in training["initial_digests"]:
        _, states = initial_states(task, lambda p: graphs[key_for_profile(p)], 0, list(ALL_PROFILES),
                                   task_config(task))
        assert {p: tensor_digest(v) for p, v in states.items()} == training["initial_digests"][inp.task_id]
        codes, fallbacks = anonymous_codes(inp.graph, inp.sources)
        per_file = {}
        for nid, data in inp.graph.nodes(data=True):
            per_file.setdefault(data["source_file"], []).append(code_sha(codes[nid]))
        assert not fallbacks
        assert {f: hashlib.sha256(json.dumps(v).encode()).hexdigest() for f, v in per_file.items()} \
            == training["anonymous_codes"][inp.task_id]
