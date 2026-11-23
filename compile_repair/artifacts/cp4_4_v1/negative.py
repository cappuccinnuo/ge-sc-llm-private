"""Apply the frozen 22 CP4 bad repairs to the same recorded compiling fixture graphs."""
import copy
import json
from pathlib import Path
import runpy
import subprocess
import sys
import types

OUT=Path(__file__).resolve().parent
OLD=OUT.parent/"cp4_v1"
ROOT=OUT.parents[2]
sys.path.insert(0,str(OLD))
from batch import checked, sha
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.evaluation.benchmark import _identity, score_graphs
from compile_repair.toolchain.project import resolve_project


def main():
    archive=json.loads((OLD/"wrong_repairs.json").read_bytes())
    fixture=runpy.run_path(str(OLD/"negative_probes.py"))
    sources=fixture["SOURCES"]
    scratch=ROOT.parent/"compile-repair-local"/"cp4_v1"/"negative_fixture"
    truth=json.loads(checked(scratch/"units/truth/graph.json",archive["fixture_truth_sha256"]))
    project=resolve_project(scratch/"truth","Main.sol",[])
    assert {Path(f.path).relative_to(project.root).as_posix():f.content for f in project.files}==sources
    base=dict(unit_id="handwritten",entry=str(scratch/"truth/Main.sol"),project_root=project.root,remappings=[],
              corpus="handwritten",kind="project",version="0.8.24",settings=[],series="0.8")
    git_path="812f8ea0:compile_repair/evaluation/benchmark.py"
    old_code=subprocess.check_output(["git","show",git_path],cwd=ROOT)
    previous=types.ModuleType("cp4_frozen_mutation_builder")
    exec(compile(old_code,git_path,"exec"),previous.__dict__)
    sites=previous.mutation_sites(base,sources,{k:previous.SourceLayout(v) for k,v in sources.items()},project.imports)
    outcomes=[]
    for r in archive["rows"]:
        op=r["operator"]
        if op=="slither_incomplete":
            actual=copy.deepcopy(truth)
            node=next(n for n in actual["nodes"] if n["filename"]=="Keep.sol" and n["ir"])
            key=_identity(node);actual["nodes"].remove(node)
            actual["cfg_edges"]=[e for e in actual["cfg_edges"] if key not in (_identity(e["source"]),_identity(e["target"]))]
            actual["calls"]=[c for c in actual["calls"] if _identity(c["node"])!=key]
            score=score_graphs(truth,actual,sources,sources,sources,{},{},0,True)
        else:
            site=sites[op];name=site[0]
            damaged,patch,damage=previous.build_mutation(base,sources,site,op)
            edits={name:[Patch(patch.start,patch.start+len(patch.replacement),patch.replacement,patch.expected,"inverse")]}
            a=sources["Keep.sol"].index(b"901")
            edits.setdefault("Keep.sol",[]).append(Patch(a,a+3,b"901",fixture["WRONG"][op],"wrong_return"))
            fixed=dict(damaged);maps={}
            for n,items in edits.items():fixed[n],maps[n]=apply_patches(damaged.get(n,b""),items)
            assert sha(fixed["Keep.sol"])==r["source_sha256"]
            actual=json.loads(checked(scratch/"units"/op/"graph.json",r["graph_sha256"]))
            score=score_graphs(truth,actual,sources,damaged,fixed,{name:damage},maps,0,True)
        outcomes.append(dict(operator=op,score=score,detected=not score["exact"]))
        assert not score["exact"],op
    assert len(outcomes)==23
    with (OUT/"negative.json").open("x",encoding="utf8") as fp:
        json.dump(dict(frozen_operator_source_sha256=sha(old_code),wrong_repairs_detected=22,
                       missing_node_detected=1,rows=outcomes),fp,indent=2);fp.write("\n")
    print("22 wrong repairs and one missing-node control detected")
if __name__=="__main__":main()
