"""Prompt 8G probes reuse the frozen 8E estimators, thresholds and grouped folds.

Only the input spelling view changes. Per-role AUC describes the same pooled
OOF predictions, not extra fits or separately tuned classifiers. Never run when
any source-to-graph semantic check failed.
"""
import argparse
from pathlib import Path

from .prepare import read, write, ref, checked
from .prepare_spelling import require_semantic_pass, load_result
from .prepare_real import load_naming as load_real
from .anon_parity import node_code_view
from .leakage_probes import PROTOCOL, p2_all, p3_samples, run_p3
from .acceptance_real import binary_metrics, compare_metrics
from ..projection_view import ProjectionView
from ..diagnostics8d.keyword_baselines import keyword_prediction
from scripts.labeling_v2.safe_graph import read_graph


def rank_auc(rows):
    """Independent Mann-Whitney check; undefined for single-class strata."""
    ordered = sorted((r["probability"], r["target"]) for r in rows)
    npos = sum(y for _, y in ordered)
    nneg = len(ordered) - npos
    if not npos or not nneg:
        return None
    rank_sum, start = 0.0, 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        rank_sum += sum(y for _, y in ordered[start:end]) * (start + 1 + end) / 2.0
        start = end
    return (rank_sum - npos * (npos+1)/2.0) / (npos*nneg)


def role_results(predictions):
    output = {}
    for role in sorted({r["role"] for r in predictions}):
        rows = [r for r in predictions if r["role"] == role]
        auc = rank_auc(rows)
        output[role] = dict(samples=len(rows), positives=sum(r["target"] for r in rows),
                            auc=auc, defined=auc is not None,
                            interpretation="subset of fixed pooled OOF; no additional fit")
    return output


def node_rows(tid, task, sources, inventory, scopes, targets):
    graph = read_graph(checked(task["record"]["original_graph"]))
    sc = {(r["file"], r["original_graph_node_id"]):r for r in scopes}
    labels = {(r["file"], r["original_graph_node_id"]):r for r in targets}
    actual = {(a["source_file"], n) for n,a in graph.nodes(data=True)}
    if len(sc)!=len(scopes) or len(labels)!=len(targets) or set(sc)!=actual or set(labels)!=actual:
        raise ValueError("Node scope/label identity population differs")
    file_data = {}
    for file, reference in task["record"]["sources"].items():
        ident = task["record"]["category"]+"/"+file
        if sources[ident]["source"] != reference:
            raise ValueError("Source reference differs")
        source, result = load_result(sources[ident])
        ids = [n for n,a in graph.nodes(data=True) if a["source_file"]==file]
        codes, proof = node_code_view(graph.subgraph(ids).copy(), file, source, result)
        before = ProjectionView(source,file)
        after = ProjectionView(result["rewritten"],file)
        spans = {}
        new_ids = {ident:key for key,ident in after.compat_ids.items()}
        for key, ast_id in before.compat_ids.items():
            # Identical spans can be nested wrappers; their exact text is equal.
            old_span=(key[0],key[1]);new=new_ids[ast_id]
            text=after.compat[new[0]:new[1]].decode("utf8")
            if old_span in spans and spans[old_span][1]!=text:
                raise ValueError("Function AST span has ambiguous rewritten text")
            spans[old_span]=(before.compat[key[0]:key[1]].decode("utf8"),text)
        file_data[file]=(codes,spans)
    rows, originals = [], []
    for nid, attrs in graph.nodes(data=True):
        file=attrs["source_file"];key=(file,nid)
        inv=inventory[tid+"/"+file];scope=sc[key];label=labels[key]
        sha=task["record"]["sources"][file]["sha256"]
        if any(r["source_sha256"]!=sha for r in (inv,scope,label)):
            raise ValueError("Source SHA differs in scope/inventory/labels")
        if label["orig"]!=int(attrs.get("node_info_vulnerabilities") is not None):
            raise ValueError("Frozen graph target differs")
        codes,spans=file_data[file]
        span=scope["function_compat_span"]
        original_fn,new_fn=spans[tuple(span)] if span else (None,None)
        common=dict(file=file,source_sha256=sha,original_graph_node_id=nid,
                    solidifi=inv["solidifi"],orig=label["orig"],C1=label["C1"])
        rows.append(dict(common,own_code=codes[nid],function_code=new_fn))
        originals.append(dict(common,own_code=attrs["code"],function_code=original_fn))
    return rows, originals


def verify_p2(score, rows, folds, label):
    expected={(r["file"],r["source_sha256"],r["original_graph_node_id"]):r for r in rows}
    outer={f["fold"]:set(f["outer_test_files"]) for f in folds}
    predictions=[r for f in score["folds"] for r in f["predictions"]]
    seen=set()
    for r in predictions:
        key=(r["file"],r["source_sha256"],r["original_graph_node_id"])
        if key in seen or key not in expected or r[label]!=expected[key][label]:
            raise ValueError("P2 OOF sample/target mismatch")
        if r["file"] not in outer[r["fold"]]:
            raise ValueError("P2 OOF fold identity mismatch")
        seen.add(key)
    if seen!=set(expected):
        raise ValueError("P2 OOF incomplete")
    selected=[r for r in predictions if r["solidifi"]]
    compare_metrics(score["pooled"],binary_metrics((r[label],r["prediction"]) for r in selected))
    compare_metrics(score["all_positive"],binary_metrics((r[label],1) for r in selected))
    for fold in score["folds"]:
        selected=[r for r in fold["predictions"] if r["solidifi"]]
        compare_metrics(fold["metric"],binary_metrics((r[label],r["prediction"]) for r in selected))
    return dict(passed=True,unique_predictions=len(predictions),folds=len(folds))


def run(naming, semantic, old8e_naming, output):
    manifest,sources,sem,_=require_semantic_pass(naming,semantic)
    olde, inventory, _, _=load_real(old8e_naming)
    if olde["formal_plan"]!=manifest["formal_plan"] or olde["old_plan"]!=manifest["old_plan"]:
        raise ValueError("8E inventories belong to different frozen inputs")
    if read(checked(manifest["artifacts"]["probe_protocol"]))!=PROTOCOL:
        raise ValueError("Probe protocol was changed")
    output=Path(output);output.mkdir(exist_ok=False)
    old=read(checked(manifest["old_plan"]))
    formal=read(checked(manifest["formal_plan"]))
    scope=read(checked(olde["scope"]))["inventories"]
    targets=read(checked(old["bound_artifacts"]["node_diagnostic_views"]))
    plan=dict(naming=ref(Path(naming)/"manifest.json"),semantic=ref(Path(semantic)/"summary.json"),
        old8e=ref(Path(old8e_naming)/"manifest.json"),protocol=PROTOCOL,implementation=ref(Path(__file__)),
        view="N-anon-s",extra_role_auc="same OOF model predictions; no additional fits",
        gate="original P2 per-task/label and pooled P3 only; no role threshold added",
        fixed_mapping_no_retuning=True,hgt_fit_count=0,diagnostic_lr_fits_planned=5)
    write(output/"probe_plan.json",plan)
    write(output/"probe_plan.seal.json",dict(plan=ref(output/"probe_plan.json")))
    result=dict(view="N-anon-s",plan=ref(output/"probe_plan.json"),P2={},P3={},keywords={},
                hgt_fit_count=0,classifier_fits=0,execution_authorized=False)
    group_of={}
    maps={}
    for tid, task in old["tasks"].items():
        if task["granularity"]!="node":
            continue
        for row in read(checked(task["population"])):
            group_of[tid+"/"+row["file"]]=row["group_id"]
    if set(group_of)!=set(inventory):
        raise ValueError("Frozen P3 group identity differs")
    for tid,task in formal["tasks"].items():
        if task["record"]["task"]!="node":
            continue
        for file in task["record"]["sources"]:
            ident=task["record"]["category"]+"/"+file
            source,mapping=load_result(sources[ident])
            inv=inventory[tid+"/"+file]
            if inv["source_sha256"]!=mapping["source_sha256"]:
                raise ValueError("P3 inventory source differs")
            # All seven P3 declaration roles originate from identifier AST nodes.
            selected={(e["start"],e["end"]):e["old"] for e in mapping["edits"]}
            for d in inv["declarations"]:
                if d["word"] in mapping["mapping"] and selected.get(tuple(d["span"]))!=d["word"]:
                    raise ValueError("P3 declaration name was not actually transformed")
            maps[tid+"/"+file]=mapping["mapping"]
        rows,originals=node_rows(tid,task,sources,inventory,scope[tid],targets[tid])
        folds=read(checked(old["tasks"][tid]["folds"]))["folds"]
        result["P2"][tid]={}
        for label in ("orig","C1"):
            score=p2_all(rows,folds,label)
            score["independent_verification"]=verify_p2(score,rows,folds,label)
            path=output/("P2_"+tid+"_"+label+".json");write(path,score)
            result["P2"][tid][label]=dict(artifact=ref(path),**{k:score[k] for k in
                    ("pooled","all_positive","delta_bf1_pp","passed","scored_nodes")})
            print("P2",tid,label,score["pooled"]["buggy_f1"],"delta",score["delta_bf1_pp"],flush=True)
        category=task["record"]["category"]
        kw=[]
        for row,orig in zip(rows,originals):
            pred=keyword_prediction(category,row["own_code"],row["function_code"])["node_or_function"]
            expected=keyword_prediction(category,orig["own_code"],orig["function_code"])["node_or_function"]
            if pred!=expected:
                raise ValueError("Keyword prediction changed in anonymous view")
            kw.append(dict(row,prediction=pred))
        metrics=[]
        for cohort in (True,False):
            for label in ("orig","C1"):
                selected=[r for r in kw if r["solidifi"]==cohort]
                metrics.append(dict(solidifi=cohort,label=label,
                    **binary_metrics((r[label],r["prediction"]) for r in selected)))
        path=output/("keywords_"+tid+".json")
        write(path,dict(predictions=kw,metrics=metrics,original_predictions_exact=True))
        result["keywords"][tid]=dict(artifact=ref(path),metrics=metrics,original_predictions_exact=True)
    samples=p3_samples(inventory,maps,group_of)
    score=run_p3(samples)
    independent=rank_auc(score["predictions"])
    if independent is None or abs(independent-score["auc"])>1e-12:
        raise ValueError("Independent rank AUC mismatch")
    score["by_role"]=role_results(score["predictions"])
    score["independent_auc"]=independent
    path=output/"P3.json";write(path,score)
    result["classifier_fits"]=score["classifier_fits"]
    result["P3"]=dict(artifact=ref(path),**{k:score[k] for k in
                    ("auc","passed","by_task_auc","by_role","samples","classifier_fits")})
    result["passed"]=all(v["passed"] for task in result["P2"].values() for v in task.values()) and score["passed"]
    result["status"]="probe_passed_feature_gate_pending" if result["passed"] else "blocked_by_preregistered_leakage_gate"
    write(output/"summary.json",result)
    write(output/"summary.seal.json",dict(summary=ref(output/"summary.json")))
    print("P3",score["auc"],result["status"],flush=True)
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("naming","semantic","old8e-naming","output"):
        p.add_argument("--"+name,required=True)
    args=p.parse_args()
    run(args.naming,args.semantic,args.old8e_naming,args.output)
