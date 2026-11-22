"""Handwritten wrong repairs change an unrelated function in a benign, local four-file project."""
from copy import deepcopy
from pathlib import Path
import time
from batch import ART, LOCAL, OUT, SEED, checked, frozen, gzip, json, save, sha
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import ArtifactStore
from compile_repair.evaluation.benchmark import (OPERATORS,SourceLayout,_identity,_materialize_closure,
    build_mutation,environment_observation,mutation_sites,score_graphs)
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers

PIN=b"pragma solidity 0.8.24;\n"
SOURCES={
    "Main.sol": PIN+b'import "./Rel.sol"; import "lib/Pkg.sol"; import "./Keep.sol";\n'
        b"contract Meter is RelativeBase { event Tick(uint n); function tally(uint x) public returns(uint) "
        b"{ if(x>0){ emit Tick(x); } return x+1; } }\n",
    "Rel.sol": PIN+b"contract RelativeBase { function baseValue() public pure returns(uint){ return 5; } }\n",
    "lib/Pkg.sol": PIN+b"library SmallNumbers { function five() internal pure returns(uint){return 5;} }\n",
    "Keep.sol": PIN+b"contract Witness { function untouched() public pure returns(uint){ return 901; } }\n",
}
# A different, compiling but incorrect return value for each documented operator.
WRONG={
    "unresolved_package_import":b"7","missing_relative_file":b"11","missing_base_contract":b"13",
    "undeclared_identifier":b"17","duplicate_definition":b"19","multiple_license_or_pragma":b"23",
    "encoding":b"29","unbalanced_structure":b"31","parser_error_other":b"37","type_error_other":b"41",
    "codegen_only":b"43","closure_version_conflict":b"47","io_error":b"53","docstring_error":b"59",
    "syntax_error":b"61","unimplemented_feature":b"67","unsupported_disjunction":b"71",
    "unsupported_expression":b"73","unterminated_pragma":b"79","pragma_missing_semicolon_candidate":b"83",
    "declaration_error":b"89","standard_json_input":b"97",
}

def main():
    start=time.monotonic()
    profile=check_profile("production");compilers,versions,_=load_trusted_compilers()
    store=ArtifactStore(LOCAL/"negative_fixture")
    base=dict(unit_id="handwritten",entry="/cp4fixture/Main.sol",project_root="/cp4fixture",remappings=[],
              corpus="handwritten",kind="project",version="0.8.24",settings=[],series="0.8")
    entry,project=_materialize_closure(base,SOURCES,store,"truth")
    base.update(entry=str(entry),project_root=project.root)
    sources={Path(f.path).relative_to(project.root).as_posix():f.content for f in project.files}
    sites=mutation_sites(base,sources,{k:SourceLayout(v) for k,v in sources.items()},project.imports)
    assert set(sites)==set(OPERATORS)==set(WRONG)
    details=[]
    with store.journal("invocations.jsonl") as journal:
        original=environment_observation(base,entry,project,compilers,versions,store,journal,"truth")
        assert original.status=="success"
        truth=json.loads((store.path/"units/truth/graph.json").read_bytes())
        for op,bad in WRONG.items():
            site=sites[op];file=site[0]
            damaged,patch,damage=build_mutation(base,sources,site,op)
            inverse=Patch(patch.start,patch.start+len(patch.replacement),patch.replacement,patch.expected,"inverse")
            repairs={file:[inverse]}
            location=sources["Keep.sol"].index(b"901")
            repairs.setdefault("Keep.sol",[]).append(Patch(location,location+3,b"901",bad,"deliberately_wrong"))
            restored=dict(damaged);maps={}
            for name,edits in repairs.items():
                restored[name],maps[name]=apply_patches(damaged.get(name,b""),edits)
            path,ctx=_materialize_closure(base,restored,store,"wrong/"+op)
            result=environment_observation(base,path,ctx,compilers,versions,store,journal,op)
            assert result.status=="success",op
            at=result.attempts[-1];path=store.path/"units"/op/"graph.json"
            score=score_graphs(truth,json.loads(path.read_bytes()),sources,damaged,restored,{file:damage},maps,
                               at["solc"]["returncode"],at["slither"]["d3"])
            row=dict(operator=op,wrong_return_value=bad.decode(),source_sha256=sha(restored["Keep.sol"]),
                     compiled=score["compiled"],detected=not score["exact"],score=score,graph_sha256=sha(path.read_bytes()))
            details.append(row)
            if not row["detected"]:
                save("wrong_repair_stop.json",row);raise ValueError("Undetected incorrect repair: "+op)
        reduced=deepcopy(truth)
        target=next(n for n in reduced["nodes"] if n["filename"]=="Keep.sol" and n["ir"])
        key=_identity(target);reduced["nodes"].remove(target)
        reduced["cfg_edges"]=[e for e in reduced["cfg_edges"] if _identity(e["source"])!=key and _identity(e["target"])!=key]
        reduced["calls"]=[c for c in reduced["calls"] if _identity(c["node"])!=key]
        score=score_graphs(truth,reduced,sources,sources,sources,{},{},0,True)
        assert not score["exact"] and score["missing_kept"]==1
        details.append(dict(operator="slither_incomplete",kind="benign_missing_node_fixture",detected=True,score=score))
    save("wrong_repairs.json",dict(expected=23,detected=sum(r["detected"] for r in details),profile=profile,
         rows=details,fixture_truth_sha256=sha((store.path/"units/truth/graph.json").read_bytes()),
         journal_sha256=sha((store.path/"invocations.jsonl").read_bytes()),elapsed_seconds=round(time.monotonic()-start,3)))
    history=[]
    for l in gzip.decompress(frozen(ART/"cp3_2_v1/unit_attributions.jsonl.gz")).splitlines():
        r=json.loads(l)
        if "slither_incomplete" not in r["primary"]["categories"]:continue
        ref=r["selected_result"];record=json.loads(checked(ref["result_path"],ref["result_sha256"]))
        obs=[(a["version"],a["slither"]) for a in record["attempts"] if (a.get("solc") or {}).get("returncode")==0 and a.get("slither")]
        assert obs and record["status"]!="success" and all(not x["d3"] or not x.get("graph_usable",True) for _,x in obs)
        history.append(dict(unit_id=r["unit_id"],corpus=r["corpus"],entry_sha256=r["entry_sha256"],result=ref,
                       observed_versions=[v for v,_ in obs],solc_successful_candidates=len(obs),
                       d3_incomplete=sum(not x["d3"] for _,x in obs),
                       unusable_graph=sum(not x.get("graph_usable",True) for _,x in obs)))
    assert len(history)==24
    save("analyzer_history.json",dict(mode="read_only_replay",new_tool_calls=0,rows=history,units=len(history)))
    print("wrong repairs",len(details),"detected",sum(r["detected"] for r in details),"historical",len(history))


if __name__=="__main__":
    main()
