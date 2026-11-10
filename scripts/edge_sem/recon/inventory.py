"""EP0 input provenance and frozen-run epoch inventory; no weight loading."""
import subprocess
from pathlib import Path
from .common import ROOT, OUT, PLAN, ref, read, checked, write, histogram

def collect():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.node_sem.facts_io import STORE
    plan = load(PLAN)
    preparation = read(checked(plan["source_preparation"]))
    store = read(STORE)
    assert ref(STORE)["sha256"] == read(STORE.with_name("store.seal.json"))["store_sha256"]
    features = read(checked(preparation["bound_artifacts"]["feature_views"]))
    naming = features["naming"]
    from scripts.DFG.dfg_v2.benchmark_v2.prepare_spelling import load_names
    _, names = load_names(checked(naming).parent)
    na_path = ROOT / "scripts/node_sem/artifacts/batch_NA_v1/plan.json"
    na = read(na_path)
    # NA is used only to locate the accepted static-fact input, not as a feature policy.
    na_seal = read(na_path.with_name("plan.seal.json"))
    assert na_seal["plan"]["sha256"] == ref(na_path)["sha256"]
    out = dict(head=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        prompt=ref(ROOT/"scripts/edge_sem/PROMPTS.md"), plan=ref(PLAN),
        seal=ref(PLAN.with_name("plan.seal.json")), store=ref(STORE),
        store_seal=ref(STORE.with_name("store.seal.json")),
        source_preparation=plan["source_preparation"], naming=naming,
        feature_root=preparation["bound_artifacts"]["feature_views"],
        node_sem_fact_locator_plan=ref(na_path), node_sem_fact_locator_seal=ref(na_path.with_name("plan.seal.json")),
        layer_impl=plan["layer_impl"], reducer=plan["reducer"], tasks={},
        archived_load_passed=True, optimizer_steps=0, training_executed=False)
    for tid, task in plan["tasks"].items():
        entry=dict(config=task["config"], granularity=task["granularity"],
            category=task["category"], graph_refs={k:store["tasks"][tid]["graphs"][k]["graph"] for k in ("F0","F3")},
            sources=task["record"]["sources"], feature_view=task["feature_view"],
            feature_npz=task["feature_npz"], folds=task["folds"], record_folds=task["record"]["folds"],
            labels=task["record"]["labels"], label_view=task["label_view"],
            graph_audit=store["tasks"][tid]["graphs"]["F3"]["audit"], prepared=task["prepared"], run_epochs=[])
        job=next(j for j in na["jobs"] if j["task_id"]==tid and j["profile"]=="G3R" and j["name"]=="S4")
        spec=read(checked(job["spec"]))
        static=next(m["manifest"] for m in spec["modalities"] if m["name"]=="static")
        sm=read(checked(static))
        entry["static_manifest"]=static
        entry["facts"]=sm["input_text"]
        entry["naming_sources"]={f:names[task["category"]+"/"+f] for f in entry["sources"]}
        references=list(entry["graph_refs"].values())+[entry[k] for k in
            ("feature_view","feature_npz","folds","record_folds","labels","label_view","graph_audit","facts")]
        references+=list(entry["sources"].values())+list(task["prepared"].values())
        for row in references:checked(row)
        for fold in range(task["k_folds"]):
            directory=PLAN.parent/"runs"/tid/("fold_"+str(fold))/"seed_1"/"G3R"
            receipts=[]
            for p in sorted(directory.glob("attempt_*/receipt.json")):
                rec=read(p)
                if rec.get("status")=="complete":
                    receipts.append((p,rec))
            if len(receipts)!=1:raise ValueError("Ambiguous successful historical run")
            p,rec=receipts[0]
            assert rec["plan"]["sha256"]==ref(PLAN)["sha256"]
            bound={}
            for fn in ("final_result.json","history.jsonl","effective_config.json"):
                row=dict(path=str(p.parent/fn),sha256=rec["artifacts"][fn]);checked(row);bound[fn]=row
            result=read(p.parent/"final_result.json")
            history=[__import__("json").loads(l) for l in (p.parent/"history.jsonl").read_text().splitlines()]
            assert result["history_rows"]==len(history)==result["last_epoch"]+1
            effective=read(p.parent/"effective_config.json")
            assert effective==task["config"]
            entry["run_epochs"].append(dict(fold=fold,receipt=ref(p),sources=bound,
                epochs_completed=len(history),best_epoch_zero_based=result["best_epoch"],
                best_epoch_one_based=result["best_epoch"]+1,last_epoch_zero_based=result["last_epoch"],
                seconds=result["seconds"]))
        entry["epoch_distribution"]=histogram(x["epochs_completed"] for x in entry["run_epochs"])
        entry["best_distribution_one_based"]=histogram(x["best_epoch_one_based"] for x in entry["run_epochs"])
        out["tasks"][tid]=entry
    out["naming_materialized_source"]=False
    out["naming_policy"]="8G sealed edits; prepare_spelling.load_result reconstructs in memory"
    write(OUT/"inputs.json",out)
    paths=subprocess.check_output(["git","ls-files","-z"],text=True).split("\0")
    frozen=[ref(ROOT/p) for p in paths if p.endswith(".py") and
        p.startswith(("scripts/DFG/","scripts/node_sem/","sco_models/","process_graphs/"))
        and "/artifacts/" not in p]
    write(OUT/"before.json",dict(frozen_code=frozen,dfg_code_refs=_code_refs(),
        documents={n:ref(ROOT/n) for n in ("HANDOVER.md","docs/training_changes_2026-10-07.md")}))
    print("input inventory complete",len(out["tasks"]),flush=True)

if __name__=="__main__":
    collect()
