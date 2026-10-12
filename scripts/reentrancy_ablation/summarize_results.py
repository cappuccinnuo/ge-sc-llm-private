"""Recompute metrics from held-out predictions; produce CSV/JSON/Markdown and integrity checks."""
import argparse, csv, io
import numpy as np
from common import *

def summarize(root):
    root=confined(root);prepared=root/"prepared";manifest=read_json(prepared/"manifest.json")
    experiments=[];index={}
    fold_docs={task:read_json(prepared/(task+"_folds.json")) for task in ["node","contract"]}
    folds_ok=all(object_hash(doc["folds"])==doc["split_hash"]==manifest["fold_hashes"][task]
                 for task,doc in fold_docs.items())
    fold_sources_ok=all(sha256(f["source_selection"])==f["source_sha256"]
                        for doc in fold_docs.values() for f in doc["folds"])
    if not folds_ok:raise AssertionError("Frozen fold manifest changed")
    for path in sorted((root/"runs").glob("*/*/seed_*/result.json")):
        raw=read_json(path)
        if not raw["complete"]:continue
        cfg=raw["config"];task=cfg["task"];name=cfg["experiment"];seed=cfg["seed"];rows=[]
        for fold in raw["folds"]:
            folder=path.parent/("fold_"+str(fold["fold"]))
            predictions=read_json(folder/"predictions.json")
            frozen=next(f for f in fold_docs[task]["folds"] if f["fold"]==fold["fold"])
            if fold["train_files"]!=frozen["train_files"] or fold["val_files"]!=frozen["val_files"]:
                raise AssertionError("Run changed frozen file split")
            if {r["file"] for r in predictions}!=set(frozen["val_files"]):
                raise AssertionError("Predictions do not match held-out files")
            for checkpoint in ["best","last"]:
                recalculated=metrics([r["y"] for r in predictions],[r[checkpoint] for r in predictions])
                if any(abs(recalculated[m]-fold[checkpoint][m])>1e-8 for m in ["buggy_f1","macro_f1"]):
                    raise AssertionError("Recorded F1 disagrees with predictions")
                if sha256(folder/(checkpoint+".pt"))!=fold["checkpoint_hashes"][checkpoint]:
                    raise AssertionError("Checkpoint changed")
            for row in predictions:rows.append(dict(row,fold=fold["fold"]))
        key=lambda r:r["node"] if task=="node" else r["file"]
        expected=12036 if task=="node" else 142
        if len(rows)!=expected or len({key(r) for r in rows})!=expected:
            raise AssertionError("Held-out samples repeated or omitted")
        primary=cfg["settings"]["primary_checkpoint"]
        item={"task":task,"experiment":name,"seed":seed,"folds":raw["fold_count"],"primary":primary,
              "primary_metrics":raw[primary],"best":raw["best"],"last":raw["last"],
              "author_labels_best":{m:float(np.mean([f["against_author_labels"]["best"][m] for f in raw["folds"]])) for m in ["buggy_f1","macro_f1"]},
              "pooled":metrics([r["y"] for r in rows],[r[primary] for r in rows]),
              "pooled_by_origin":{origin:metrics([r["y"] for r in rows if r["origin"]==origin],
                                                [r[primary] for r in rows if r["origin"]==origin])
                                  for origin in sorted({r["origin"] for r in rows})},
              "runtime_seconds":sum(f["seconds"] for f in raw["folds"]),
              "result":str(path),"fold_values":[{"fold":f["fold"],"best":f["best"],"last":f["last"],
                                  "author_best":f["against_author_labels"]["best"]} for f in raw["folds"]]}
        experiments.append(item);index[(task,name,seed)]=item
    for item in experiments:
        base=index.get((item["task"],"A_author",item["seed"]))
        if base:
            diffs=[f[item["primary"]]["buggy_f1"]-b["best"]["buggy_f1"] for f,b in zip(item["fold_values"],base["fold_values"])]
            item["paired_buggy_delta_vs_A"]={"mean":float(np.mean(diffs)),
                 "sample_std":float(np.std(diffs,ddof=1)),"per_fold":diffs,
                 "positive_folds":sum(d>0 for d in diffs),
                 "note":"Fold deltas are paired descriptive results; CV folds are not independent statistical replicates."}
    changed={p:{"expected":h,"actual":sha256(p) if Path(p).exists() else None}
             for p,h in manifest["original_code_hashes"].items() if not Path(p).exists() or sha256(p)!=h}
    sources_ok=all(sha256(p)==h for p,h in manifest["source_hashes"].items())
    graphs_ok=all(sha256(v[t])==v[t+"_sha256"] for v in manifest["variants"].values() for t in ["node","contract"])
    feature=read_json(root/"feature_text_audit.json") if (root/"feature_text_audit.json").exists() else None
    result={"created_utc":utc(),"experiments":experiments,"feature_text_audit":feature,
            "checks":{"original_code_unchanged":not changed,"source_graphs_unchanged":sources_ok,
                      "prepared_graphs_unchanged":graphs_ok,"frozen_folds_unchanged":folds_ok,
                      "historical_fold_sources_unchanged":fold_sources_ok,"held_out_predictions_and_metrics_verified":True},
            "original_code_files_checked":len(manifest["original_code_hashes"]),"changed_originals":changed,
            "limitations":["Fixed historical folds are not the paper authors original folds.",
                "A contains local tokenization of the author's serialized code strings, not author-provided embeddings.",
                "Changing labels changes the scoring target; use author_labels_best for an additional common-target comparison.",
                "C preserves common parameter initialization but relation schema and relation parameter counts necessarily differ.",
                "Best and last are evaluated in eval mode; upstream_behavior is a combined diagnostic under common folds/init/epoch cap.",
                "Selecting epochs on the same validation folds being reported is not an independent outer test.",
                "Single initialization seed unless additional seed runs are present. Template overlap has not been removed.",
                "Origin subgroup metrics are pooled held-out predictions, not mean-fold F1; contract subgroups have one class."]}
    write_json(root/"summary.json",result)
    with (root/"summary.csv").open("w",newline="") as f:
        writer=csv.writer(f);writer.writerow(["task","experiment","seed","folds","primary","buggy_f1","macro_f1","best_buggy_f1","last_buggy_f1","author_labels_best_buggy_f1","delta_vs_A"])
        for x in experiments:
            writer.writerow([x["task"],x["experiment"],x["seed"],x["folds"],x["primary"],
                             x["primary_metrics"]["buggy_f1"],x["primary_metrics"]["macro_f1"],
                             x["best"]["buggy_f1"],x["last"]["buggy_f1"],x["author_labels_best"]["buggy_f1"],
                             x.get("paired_buggy_delta_vs_A",{}).get("mean")])
    lines=["# Reentrancy controlled ablations","",
           "Generated by Codex at "+utc()+". All metrics below are percentages.","",
           "| Task | Experiment | Seed | Folds | Primary weights | Buggy-F1 | Macro-F1 | Delta vs A (pp) |",
           "|---|---|---:|---:|---|---:|---:|---:|"]
    for x in experiments:
        lines.append("| {} | {} | {} | {} | {} | {:.4f} | {:.4f} | {:+.4f} |".format(
            x["task"],x["experiment"],x["seed"],x["folds"],x["primary"],
            x["primary_metrics"]["buggy_f1"],x["primary_metrics"]["macro_f1"],
            x.get("paired_buggy_delta_vs_A",{}).get("mean",0)))
    lines+=["","## Interpretation rules",""]+["- "+x for x in result["limitations"]]
    lines+=["","## Integrity","",json.dumps(result["checks"]),"",
            "See summary.json for per-fold differences, common-author-label scores, source subgroups, and input provenance."]
    (root/"RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf8")
    print(json.dumps({"experiments_complete":len(experiments),"checks":result["checks"]},indent=2))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=HERE/"artifacts/v1")
    summarize(p.parse_args().root)
