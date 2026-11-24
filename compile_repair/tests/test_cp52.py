"""CP5.2 file-move provenance, atomic path chains and graph measurement boundaries."""
from copy import deepcopy
import hashlib
import io
import json
import logging
from pathlib import Path

import pytest

from compile_repair.core.model import CompilationUnit, Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import ArtifactStore
from compile_repair.evaluation.benchmark import (build_mutation, file_damage_import_spans,
    relative_move_v2_site, score_graphs)
from compile_repair.pipeline import repair_unit
from compile_repair.tests.test_production import production_required, trusted_compilers
from compile_repair.toolchain.project import import_directives, resolve_project
from compile_repair.toolchain.slither import _TopLevelIRLog


def put(root, name, raw):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    return p


def supplier(name, child=None, path=None):
    directive = ('import {' + child + '} from "' + path + '";\n') if child else ''
    body = (' is ' + child) if child else ''
    return ('pragma solidity 0.8.38;\n' + directive + 'contract ' + name + body + ' {}\n').encode()


@pytest.mark.parametrize("scenario", ["success", "no_candidate", "mixed", "limit"])
def test_relative_chain_preserves_atomic_source_and_receipts(tmp_path, scenario):
    production_required()
    root = tmp_path / "src"
    originals = {"App.sol": supplier("App", "Middle", "./old/Middle.sol"),
                 "moved/Middle.sol": supplier("Middle", "Leaf", "./Leaf.sol")}
    if scenario != "no_candidate":
        originals["sibling/Leaf.sol"] = supplier("Leaf")
    if scenario == "mixed":
        originals["moved/Middle.sol"] = (b'import "external/Other.sol";\n' + originals["moved/Middle.sol"])
    if scenario == "limit":
        for old, child, parent in [("Leaf","Third","sibling"), ("Third","Fourth","three"),
                                   ("Fourth","Fifth","four")]:
            originals[parent + "/" + old + ".sol"] = supplier(old, child, "./" + child + ".sol")
        originals["five/Fifth.sol"] = supplier("Fifth")
    for name, raw in originals.items():
        put(root, name, raw)
    project = resolve_project(root, "App.sol")
    store = ArtifactStore(tmp_path/"run")
    logger = logging.getLogger("SlitherSolcParsing")
    handlers = list(logger.handlers)
    result = repair_unit(CompilationUnit("chain", project.files), {"0.8.38": trusted_compilers()["0.8.38"]},
                         store, io.StringIO(), project=project)
    assert list(logger.handlers) == handlers
    folder = store.path / "units/chain"
    steps = [r for r in json.loads((folder/"repair_steps.json").read_bytes())
             if r["step"] == 4 and "receipt" in r]
    assert [(root / n).read_bytes() for n in originals] == list(originals.values())
    if scenario == "success":
        assert result.status == "success" and len(steps) == 2
        assert all(r["accepted"] and r["chain_outcome"] == "committed" for r in steps)
        assert steps[0]["errors_after"] == steps[0]["chain_start_errors"] == 1
        assert steps[1]["errors_after"] == 0
        assert result.attempts[-1]["slither"]["partial_ir"] == {
            "incorrectly_constructed_contracts": [], "top_level_errors": 0}
        for proof in result.provenance.values():
            for c in proof.changes:
                assert c.step == "relative_import"
                assert any((i["literal_start"]+1,i["literal_end"]-1) == (c.start,c.end)
                           for raw in originals.values() for i in import_directives(raw) if raw[c.start:c.end] == c.old)
    else:
        assert result.status != "success" and not (folder/"graph.json").exists()
        assert len(steps) == (4 if scenario == "limit" else 1)
        assert all(not s["accepted"] and s["chain_outcome"] == "rolled_back" for s in steps)


def test_v2_changes_only_outgoing_literals_and_inverts(tmp_path):
    raw = b'// ./Leaf.sol\nimport {Leaf} from "./Leaf.sol"; import "./Other.sol";\ncontract Middle is Leaf {}'
    sources = {"App.sol": supplier("App","Middle","./lib/Middle.sol"), "lib/Middle.sol":raw,
               "lib/Leaf.sol":supplier("Leaf"), "lib/Other.sol":supplier("Other")}
    for name, data in sources.items():
        put(tmp_path, name, data)
    p = resolve_project(tmp_path, "App.sol")
    base = {"project_root":str(tmp_path),"entry":str(tmp_path/"App.sol"),"remappings":[]}
    op = "missing_relative_file_moved_v2"
    site = relative_move_v2_site(base, sources, p.imports)
    work, patches, damage = build_mutation(base, sources, site, op)
    moved = ".cp5_moved/Middle.sol"
    assert "lib/Middle.sol" not in work and len(patches) == 2
    assert work[moved].startswith(b'// ./Leaf.sol\n') and work["App.sol"] == sources["App.sol"]
    root = tmp_path/"copy"
    for name, data in work.items():
        put(root, name, data)
    assert not resolve_project(root, moved).issues
    assert len(resolve_project(root, "App.sol").issues) == 1
    inverse = [Patch(c.start,c.start+len(c.new),c.new,c.old,"inverse") for c in reversed(damage.changes)]
    assert apply_patches(work[moved], inverse)[0] == raw


def test_file_exact_only_adds_the_incoming_import_literal(tmp_path):
    raw = b'import "./Math.sol";\n// original note\ncontract App {}'
    sources = {"App.sol":raw, "Math.sol":b"contract Math {}"}
    for name, data in sources.items():
        put(tmp_path, name, data)
    base = {"project_root":str(tmp_path),"entry":str(tmp_path/"App.sol"),"remappings":[]}
    mutation = {"operator":"missing_relative_file_moved","file_renames":{"Math.sol":".cp5_moved/Math.sol"}}
    spans = file_damage_import_spans(base, sources, mutation)
    assert spans == {"App.sol":{(8,18)}}
    graph = {"nodes":[], "cfg_edges":[], "calls":[], "declarations":[]}
    for at, expected in ((10, True), (raw.index(b"note"), False)):
        after, proof = apply_patches(raw,[Patch(at,at,b"",b"m","repair")])
        actual = dict(sources, **{"App.sol":after})
        score = score_graphs(graph,graph,sources,sources,actual,{},{"App.sol":proof},0,True,file_import_spans=spans)
        assert score["exact"] is expected


def test_wrapper_identity_rejects_changed_facts_and_sources():
    key = ["A","f()","ENTRYPOINT",0,1]
    node = {"key5":key,"node_type":"ENTRYPOINT","ir":[],"length":1,"declaration_kind":"function"}
    truth = {"schema":"compile-repair-graph-v1","nodes":[node],"declarations":[],"cfg_edges":[],"calls":[]}
    graph = dict(truth, schema="compile-repair-project-graph-v1", nodes=[dict(node,filename="input.sol")])
    before = {"":b"sample"}
    options = dict(file_renames={"":"input.sol"},single_file_wrapper=True)
    score = score_graphs(truth,graph,before,before,{"input.sol":b"sample"},{},{},0,True,**options)
    assert score["exact"] and not score["previous_wrapper_score"]["exact"]
    for name, value in (("ir",["an observable operation"]),("filename","another.sol")):
        altered = deepcopy(graph)
        altered["nodes"][0][name] = value
        assert not score_graphs(truth,altered,before,before,{"input.sol":b"sample"},{},{},0,True,**options)["exact"]
    changed, proof = apply_patches(b"sample",[Patch(6,6,b"",b"x","repair")])
    assert not score_graphs(truth,graph,before,before,{"input.sol":changed},{},{"":proof},0,True,**options)["exact"]


def test_ir_logger_counts_only_the_native_top_level_message():
    handler = _TopLevelIRLog()
    for name, message in [("SlitherSolcParsing","Impossible to generate IR for top level function f (x):"),
                          ("SlitherSolcParsing","Impossible to generate IR for X.f (x):"),
                          ("another","Impossible to generate IR for top level function f (x):")]:
        handler.handle(logging.LogRecord(name, logging.ERROR, "", 0, message, (), None))
    assert handler.count == 1
