"""Rebuild four reference task graphs without changing any historical artifact."""
import argparse
import copy
import time
from pathlib import Path
import torch
from scripts.labeling_v2.safe_graph import read_graph
from ..graph_audit import fingerprint
from .pipeline import build_graph, computation_fingerprint
from .model import build_dgl
from .io import checked, read_json, write_json, read_sources, write_bundle, sha256
from . import VERSION
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = ROOT / "scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1/build/manifest.json"


def model_edges_equal(a, b):
    ga, ida = build_dgl(a)
    gb, idb = build_dgl(b)
    if ida != idb or ga.ntypes != gb.ntypes or ga.canonical_etypes != gb.canonical_etypes:
        return False
    for typ in ga.ntypes:
        if ga.num_nodes(typ) != gb.num_nodes(typ):
            return False
    return all(all(torch.equal(x,y) for x,y in zip(ga.edges(etype=c),gb.edges(etype=c)))
               for c in ga.canonical_etypes)


def rebuild(reference_manifest, output):
    reference_manifest, output = Path(reference_manifest).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing output: " + str(output))
    seal_path = reference_manifest.with_name("manifest.seal.json")
    reference_sha = read_json(seal_path)["sha256"]
    checked(reference_manifest, reference_sha)
    reference = read_json(reference_manifest)
    if reference.get("version") != "author-hcg-ddg-guard-build-v1":
        raise ValueError("Unexpected reference build")
    expected = {"reentrancy_author_contract", "access_control_author_contract",
                "reentrancy_author_node", "access_control_author_node"}
    if len(reference["tasks"]) != 4 or {x["task_id"] for x in reference["tasks"]} != expected:
        raise ValueError("Reference task matrix mismatch")
    records = []
    output.mkdir(parents=True)
    for ref in reference["tasks"]:
        tid = ref["task_id"]
        print(tid + ": rebuild from original HCG", flush=True)
        start = time.monotonic()
        task_path = checked(ref["source_task_manifest"], ref["source_task_sha256"])
        task = read_json(task_path)
        source_path = checked(ref["source_metadata_manifest"], ref["source_metadata_sha256"])
        base_rec = task["graphs"]["HCG"]
        base_path = checked(base_rec["path"], base_rec["sha256"])
        full_path = checked(ref["source_graph"]["path"], ref["source_graph"]["sha256"])
        guard_path = checked(ref["graph"]["path"], ref["graph"]["sha256"])
        base, old_full, old_guard = (read_graph(x) for x in (base_path,full_path,guard_path))
        sources, metadata, used, missing = read_sources(source_path, base)
        candidate, audit = build_graph(base, sources, "full_guard", metadata)
        full = copy.deepcopy(candidate)
        full.remove_edges_from([(s,t,k) for s,t,k,d in full.edges(keys=True,data=True)
                                if d["edge_type"] == "CONTROL_DEPENDENCE"])
        comparisons = {}
        for label, old, new in (("full",old_full,full),("full_guard",old_guard,candidate)):
            comparisons[label] = {"exact_graph_equal": fingerprint(old)==fingerprint(new),
                "computation_fingerprint_equal": computation_fingerprint(old)==computation_fingerprint(new),
                "ordered_model_edges_equal": model_edges_equal(old,new),
                "old_fingerprint": fingerprint(old), "new_fingerprint": fingerprint(new)}
        for rec in used.values():
            checked(rec["path"],rec["sha256"])
        checked(base_path,base_rec["sha256"])
        checked(source_path,ref["source_metadata_sha256"])
        checked(task_path,ref["source_task_sha256"])
        checked(full_path,ref["source_graph"]["sha256"])
        checked(guard_path,ref["graph"]["sha256"])
        inputs = {"reference_manifest":str(reference_manifest),"reference_manifest_sha256":reference_sha,
            "task_manifest":str(task_path),"task_manifest_sha256":ref["source_task_sha256"],
            "original_graph":base_rec,"source_manifest":str(source_path),
            "source_manifest_sha256":ref["source_metadata_sha256"],"sources":used,"missing_sources":missing}
        bundle = write_bundle(output/tid,candidate,audit,inputs)
        equivalent = all(x["computation_fingerprint_equal"] and x["ordered_model_edges_equal"]
                         for x in comparisons.values())
        record = {"task_id":tid,"task":ref["task"],"cohort":ref["cohort"],"bundle":bundle,
            "comparison":comparisons,"model_input_equivalent":equivalent,
            "files":len({d["source_file"] for _,d in candidate.nodes(data=True)}),
            "added_relations":audit["invariants"]["added_by_relation"],
            "build_seconds":time.monotonic()-start,
            "historical_results_remain_under_original_runtime":True}
        records.append(record)
        write_json(output/tid/"comparison.json",record)
        print(tid+": model input equivalent="+str(equivalent),flush=True)
    checked(reference_manifest,reference_sha)
    result = {"version":VERSION,"reference_manifest":str(reference_manifest),
        "reference_manifest_sha256":reference_sha,"tasks":records,
        "all_model_inputs_equivalent":all(x["model_input_equivalent"] for x in records),
        "new_training_executed":False,"historical_results_rewritten":False,
        "meaning":"graph/input equivalence; not new fits or a claim that old runs executed the new code"}
    write_json(output/"manifest.json",result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-manifest",default=str(DEFAULT_MANIFEST))
    p.add_argument("--output",required=True)
    args=p.parse_args()
    result=rebuild(args.reference_manifest,args.output)
    print("All four model inputs equivalent: "+str(result["all_model_inputs_equivalent"]),flush=True)

if __name__ == "__main__":
    main()
