"""Account for every historical/current solc and Slither argument difference in the CP3 draw."""
from collections import Counter
from pathlib import Path
import json
from ir_manifest_check import checked_project
from measure import HERE, emit, ir_targets, jsonline, load, read_checked_json, save, sha256
from compile_repair.core.model import Compiler
from compile_repair.toolchain.project import project_command, slither_arguments

pre=load(HERE/"ir_manifest_preflight.json")
assert sha256(HERE/"ir_manifest_preflight.jsonl")==pre["rows_sha256"]
missing={r["unit_id"] for r in map(json.loads,(HERE/"ir_manifest_preflight.jsonl").read_bytes().splitlines())
         if r["scope"]=="cp3" and r["problem"]}
counts=Counter()
with jsonline("ir_argument_differences") as out:
    for uid,corpus,op,path,digest,graph in ir_targets("cp3"):
        if uid not in missing:continue
        record=read_checked_json(path,digest)
        attempt=record["attempts"][-1]
        old=attempt["solc"]
        old_api=attempt["slither"]["command"]
        project,_=checked_project(attempt["slither"]["project"])
        compiler=Compiler(**old["compiler"])
        after=project_command(project,compiler,old["settings"])
        before=old["command"]
        root=project.root
        index=before.index("--allow-paths")+1
        equivalent=before[:index]+[root]+before[index+1:]==after and before[index]=="." and old["cwd"]==root
        target,kwargs=slither_arguments(project,compiler,old["settings"])
        api_diffs={k:[old_api.get(k),v] for k,v in dict(kwargs,target=target).items() if old_api.get(k)!=v}
        old_args=old_api.get("solc_args","")
        new_args=kwargs["solc_args"]
        matching_api=(set(api_diffs)=={"solc_args"} and old_args.replace("--allow-paths .","--allow-paths "+root,1)==new_args
                      and old_api["solc_working_dir"]==root)
        row=dict(unit_id=uid,corpus=corpus,version=compiler.version,historical_result_sha256=digest,
            historical_success=old["returncode"]==0 and attempt["slither"]["d3"],root=root,
            solc_only_dot_to_root=equivalent,slither_only_dot_to_root=matching_api,
            old_solc=before,new_solc=after,api_diffs=api_diffs)
        emit(out,row)
        counts[equivalent,matching_api]+=1
save(HERE/"ir_argument_differences.json",dict(total=len(missing),counts=[[*k,v] for k,v in sorted(counts.items())],
     sha256=sha256(HERE/"ir_argument_differences.jsonl")))
