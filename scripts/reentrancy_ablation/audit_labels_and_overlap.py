"""CPU-only label disagreement and train-only exact-snippet lookup diagnostics."""
from collections import defaultdict
import numpy as np
from common import *
from label_rules import canonical_code

def main():
    root=HERE/"artifacts/v1"; prepared=root/"prepared"
    folds=read_json(prepared/"node_folds.json")["folds"]
    graphs={k:read_graph(prepared/k/"node.gpickle") for k in ["A_author","B_local_labels"]}
    labels={k:{n:int(bool(parse_records(d.get("node_info_vulnerabilities")))) for n,d in g.nodes(data=True)} for k,g in graphs.items()}
    a=graphs["A_author"]; changed=[]; by_file=Counter(); by_type=Counter(); directions=Counter()
    for n,d in a.nodes(data=True):
        ya=labels["A_author"][n];yb=labels["B_local_labels"][n]
        if ya!=yb:
            changed.append({"node":n,"author_full_node":d["original_node_id"],"file":d["source_file"],
                            "node_type":d["node_type"],"author_label":ya,"local_label":yb})
            by_file[d["source_file"]]+=1;by_type[d["node_type"]]+=1;directions[str(ya)+"->"+str(yb)]+=1
    diagnostics={}
    for variant in graphs:
        y=labels[variant]; fold_results=[];oof=[]
        for f in folds:
            train=set(f["train_files"]);val=set(f["val_files"])
            votes=defaultdict(Counter);train_y=[]
            for n,d in a.nodes(data=True):
                if d["source_file"] in train:
                    key=(d["node_type"],canonical_code(d["code"]))
                    votes[key][y[n]]+=1;train_y.append(y[n])
            # Ties deliberately resolve to clean; unseen keys use TRAIN majority.
            default=int(sum(train_y)>len(train_y)/2)
            rows=[]
            for n,d in a.nodes(data=True):
                if d["source_file"] not in val:continue
                key=(d["node_type"],canonical_code(d["code"]))
                counts=votes.get(key)
                pred=int(counts[1]>counts[0]) if counts else default
                rows.append({"node":n,"y":y[n],"prediction":pred,"seen":bool(counts),
                    "same_label_seen":bool(counts and counts[y[n]]),"origin":"SolidiFI" if d["source_file"].startswith("buggy_") else "SmartBugs"})
            fold_results.append({"fold":f["fold"],"metrics":metrics([r["y"] for r in rows],[r["prediction"] for r in rows])})
            oof.extend(rows)
        seen=sum(r["seen"] for r in oof);pos=[r for r in oof if r["y"]]
        diagnostics[variant]={"mean_fold":{m:float(np.mean([f["metrics"][m] for f in fold_results])) for m in ["buggy_f1","macro_f1"]},
            "pooled":metrics([r["y"] for r in oof],[r["prediction"] for r in oof]),
            "held_out_nodes":len(oof),"exact_code_type_seen":seen,"exact_code_type_seen_percent":100*seen/len(oof),
            "positive_nodes":len(pos),"positive_same_code_and_label_seen":sum(r["same_label_seen"] for r in pos),
            "positive_same_code_and_label_seen_percent":100*sum(r["same_label_seen"] for r in pos)/len(pos),
            "pooled_by_origin":{origin:metrics([r["y"] for r in oof if r["origin"]==origin],
                [r["prediction"] for r in oof if r["origin"]==origin]) for origin in ["SolidiFI","SmartBugs"]},
            "folds":fold_results}
    comparison={}
    for experiment in ["A_author","B_local_labels","D_local_features","C_local_relations"]:
        path=root/"runs/node"/experiment/"seed_1/result.json"
        if not path.exists():continue
        result=read_json(path)
        if not result["complete"]:continue
        predictions=[]
        for f in result["folds"]:
            predictions+=read_json(path.parent/("fold_"+str(f["fold"]))/"predictions.json")
        lookup={r["node"]:r for r in predictions}
        comparison[experiment]={}
        for group,ids in [("disagree",[r["node"] for r in changed]),("agree",[n for n in a if labels["A_author"][n]==labels["B_local_labels"][n]])]:
            comparison[experiment][group]={k:metrics([labels[k][n] for n in ids],[lookup[n]["best"] for n in ids]) for k in graphs}
    report={"created_utc":utc(),"label_disagreement":{"nodes":len(changed),"directions":dict(directions),
         "files":dict(by_file.most_common()),"node_types":dict(by_type.most_common()),"details":changed},
         "train_only_snippet_lookup":diagnostics,"model_predictions_by_label_agreement":comparison,
         "notes":["Lookup never accesses held-out labels to choose predictions. Unseen keys use training majority.",
                  "Key = node type + decoded exact code; no identifier normalization or template grouping.",
                  "Overlap quantifies memorization opportunity, not proof of leakage via software.",
                  "Different labels define different tasks; scores on disagreements are diagnostic.",
                  "Run again after experiment completion to include all model groups."]}
    write_json(root/"label_overlap_audit.json",report)
    print(json.dumps({"label_changes":len(changed),"directions":dict(directions),"lookup":{k:{"fold_mean":v["mean_fold"],"same_label_seen_percent":v["positive_same_code_and_label_seen_percent"]} for k,v in diagnostics.items()}},indent=2))
if __name__=="__main__":main()
