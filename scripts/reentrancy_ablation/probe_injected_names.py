"""A fixed naming probe, not a trained detector or proof of model behavior."""
import numpy as np
from common import *
from label_rules import canonical_code
def main():
    root=HERE/"artifacts/v1";folds=read_json(root/"prepared/node_folds.json")["folds"];result={}
    for name in ["A_author","B_local_labels"]:
        g=read_graph(root/"prepared"/name/"node.gpickle");rows=[]
        for n,d in g.nodes(data=True):
            rows.append({"node":n,"file":d["source_file"],
                "y":int(bool(parse_records(d.get("node_info_vulnerabilities")))),
                "prediction":int("re_ent" in canonical_code(d["code"])),
                "origin":"SolidiFI" if d["source_file"].startswith("buggy_") else "SmartBugs"})
        fm=[]
        for f in folds:
            fs=set(f["val_files"]);rs=[x for x in rows if x["file"] in fs]
            fm.append(metrics([x["y"] for x in rs],[x["prediction"] for x in rs]))
        result[name]={"fold_mean":{m:float(np.mean([x[m] for x in fm])) for m in ["buggy_f1","macro_f1"]},
            "pooled":metrics([x["y"] for x in rows],[x["prediction"] for x in rows]),
            "pooled_by_origin":{o:metrics([x["y"] for x in rows if x["origin"]==o],
                [x["prediction"] for x in rows if x["origin"]==o]) for o in ["SolidiFI","SmartBugs"]}}
    report={"created_utc":utc(),"rule":"predict positive iff decoded node code contains literal re_ent",
        "training":"none","results":result,
        "note":"Hand-written probe of known SolidiFI injected identifier naming, not a trained model. It measures an available dataset shortcut, not proof that HGT uses only this rule. Rule was fixed before the first scores were computed."}
    write_json(root/"injected_name_probe.json",report)
    print(json.dumps({k:v["fold_mean"] for k,v in result.items()},indent=2))
if __name__=="__main__":main()
