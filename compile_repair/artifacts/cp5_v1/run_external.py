"""Re-evaluate all CP3 primary target units with a development-frozen release policy."""
from collections import Counter
from dataclasses import asdict
from functools import lru_cache
import gzip
import json
from pathlib import Path
import subprocess
import time

from run_benchmark import ART, HERE, ROOT, approved_index, read, write, pinned
from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.store import ArtifactStore, emit, sha256
from compile_repair.evaluation.report import aggregate_attributions, classify_record, primary_causes
from compile_repair.pipeline import repair_unit
from compile_repair.toolchain.project import ProjectIndex, resolve_project
from compile_repair.toolchain.solc import load_trusted_compilers
from compile_repair.toolchain.slither import check_profile


def main():
    start = time.monotonic()
    profile = check_profile("production")
    index = approved_index()
    freeze = read(HERE/"benchmark_dev/policy.json")
    assert freeze["status"]=="frozen" and freeze["index_sha256"]==index.seal["index_sha256"]
    policy = freeze["policy"]
    measurement = read(HERE/"measurement.json")
    units_path = HERE/"measurement_units.jsonl.gz"
    assert sha256(units_path)==measurement["units_sha256"]
    targets=[r for r in map(json.loads,gzip.decompress(units_path.read_bytes()).splitlines()) if r["primary"]]
    assert len(targets)==measurement["primary_union"]==9138
    cp41=ART/"cp4_1_v1"
    attrs=cp41/"cp3_attributions.jsonl.gz"
    inventory=ART/"cp3_continue_v1/unit_inventory.jsonl"
    assert sha256(attrs)==measurement["inputs"]["attributions_sha256"]
    assert sha256(inventory)==measurement["inputs"]["inventory_sha256"]
    all_rows={r["unit_id"]:r for r in map(json.loads,gzip.decompress(attrs.read_bytes()).splitlines())}
    catalog={r["unit_id"]:r for r in map(json.loads,inventory.read_bytes().splitlines())}
    assert len(catalog)==len(all_rows)==31307
    categories=[c["category"] for c in json.loads(pinned(cp41/"d6_priority.json"))["categories"]]
    tools, _, _ = load_trusted_compilers()
    output=HERE/"external"
    output.mkdir(exist_ok=False)
    store=ArtifactStore(ROOT.parent/"compile-repair-local/cp5_v1/external")
    folders=lru_cache(maxsize=15)(ProjectIndex)
    counts=Counter()
    with store.journal("invocations.jsonl") as log, (output/"observations.jsonl").open("x",encoding="utf8") as outcomes:
        for selection in targets:
            uid=selection["unit_id"]
            item=catalog[uid]
            old=all_rows[uid]
            source=Path(item["path"])
            digest=sha256(source)
            assert digest==selection["entry_sha256"]==old["entry_sha256"]
            ref=old["selected_result"]
            assert sha256(ref["result_path"])==selection["result_sha256"]==ref["result_sha256"]
            baseline=read(Path(ref["result_path"]))
            folder=folders(item["project_root"]) if item["project_root"] else None
            project_receipt = Path(ref["result_path"]).parent/"project.json"
            remaps = read(project_receipt)["remappings"] if folder and project_receipt.is_file() else ()
            project=resolve_project(folder.root,source,remaps,index=folder) if folder else None
            raw=source.read_bytes()
            files=project.files if project else (SourceFile(str(source),digest,raw,item["kind"]),)
            assert [(f.path,f.sha256) for f in files]==[(f["path"],f["sha256"]) for f in baseline["inputs"]]
            result=repair_unit(CompilationUnit(uid,files),tools,store,log,project=project,project_index=folder,
                               offline_index=index,dependency_policy=policy)
            report=asdict(result)
            failed=classify_record(report)
            old=dict(old,status=result.status,primary=primary_causes(report,failed),
                     any_categories=sorted({r["category"] for r in failed}))
            all_rows[uid]=old
            parent=store.path/"units"/uid
            path=parent/"repair_steps.json"
            accepted=[r for r in read(path) if r.get("accepted")] if path.is_file() else []
            tiers={r["tier"] for step in accepted for r in step.get("releases",{}).values()}
            final_step=accepted[-1]["step"] if accepted else 1
            tier=max(tiers) if tiers else "no_release"
            good=result.status=="success"
            if good:
                assert result.attempts[-1]["slither"]["d3"] and (parent/"graph.json").exists()
            counts[(item["corpus"],final_step,tier,good)]+=1
            emit(outcomes,dict(unit_id=uid,corpus=item["corpus"],status=result.status,reason=result.reason,
                               d3=good,steps=[r["step"] for r in accepted],final_step=final_step,
                               tiers=sorted(tiers),weakest_tier=tier,primary=old["primary"],
                               any_categories=old["any_categories"],result_sha256=sha256(parent/"result.json")))
    module = ROOT/"compile_repair"
    code = {p.relative_to(ROOT).as_posix():sha256(p) for p in module.rglob("*.py")
            if not {"artifacts","tests","docs"}.intersection(p.relative_to(module).parts)}
    seal=store.seal(dict(profile=profile,compilers={v:asdict(c) for v,c in tools.items()},
                         dependency_index=index.seal,policy=policy,policy_sha256=sha256(HERE/"benchmark_dev/policy.json")),
                    subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT).decode().strip(),code)
    write(output/"summary.json",dict(measured=len(targets),groups=[
          dict(corpus=k[0],final_step=k[1],tier=k[2],d3=k[3],units=v) for k,v in sorted(counts.items())],
          store_seal_sha256=sha256(store.path/"seal.json"),sealed_files=len(seal["files"]),
          elapsed_seconds=time.monotonic()-start,cost_usd=0,llm_calls=0,
          failure_table=aggregate_attributions(all_rows.values(),categories)))


if __name__=="__main__":
    main()
