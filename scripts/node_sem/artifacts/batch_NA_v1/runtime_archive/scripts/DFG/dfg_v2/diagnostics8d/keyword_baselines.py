"""Prompt 8D E: lexical call/environment baselines after frozen idN renaming."""
import argparse
from pathlib import Path
import re
from collections import defaultdict
from scripts.DFG.dfg_v2.diagnostics8c import scoring as s
from scripts.DFG.dfg_v2.diagnostics8c.inference import serialized_view, LEXEMES, IDENTIFIER
from .stratification import load_context, task_scope

VERSION="prompt8d-keyword-baselines-v1"
PATTERNS={"access_control":re.compile(r"\btx\s*\.\s*origin\b"),
          "reentrancy":re.compile(r"\.\s*(?:call\s*\.\s*value|send|transfer)\s*\(")}

def code_without_literals_comments(code, serialized=False):
    logical=serialized_view(code)[0] if serialized else code
    chars=list(logical)
    for match in LEXEMES.finditer(logical):
        if not IDENTIFIER.fullmatch(match.group()):
            chars[match.start():match.end()]=[" "]*len(match.group())
    return "".join(chars)

def keyword_prediction(category, own_code, function_code):
    if category not in PATTERNS: raise ValueError("No keyword baseline for category")
    pattern=PATTERNS[category]
    own=bool(pattern.search(code_without_literals_comments(own_code,serialized=True)))
    function=bool(function_code and pattern.search(code_without_literals_comments(function_code)))
    return dict(node_text=int(own),function_text=int(function),node_or_function=int(own or function))

def summarize(rows, views):
    output=[]
    for view in ("orig","C1","C2"):
        for stratum in ("SolidiFI","nonSolidiFI"):
            selected=[row for row in rows if row["solidifi"]==(stratum=="SolidiFI")
                      and (view!="C2" or views[s.identity(row)]["C2_include"])]
            for rule in ("node_text","function_text","node_or_function"):
                pairs=[(views[s.identity(row)][view],row["prediction"][rule]) for row in selected]
                metrics=s.metric_counts(s.confusion(pairs))
                counts=metrics
                output.append(dict(view=view,stratum=stratum,rule=rule,aggregation="pooled_OOF",
                                   precision_wilson_95=s.wilson(counts["tp"],counts["tp"]+counts["fp"]),
                                   recall_wilson_95=s.wilson(counts["tp"],counts["tp"]+counts["fn"]),
                                   **metrics))
    return output

def run_keyword_baselines(plan_path,frozen_root,output,scope_path=None):
    output=Path(output)
    if output.exists():raise FileExistsError(str(output))
    plan,raw_views,reports=load_context(plan_path,frozen_root)
    inventories=(s.read(scope_path)["inventories"] if scope_path else
                 {task:task_scope(plan,task) for task in raw_views})
    if scope_path:
        scope_report=s.read(scope_path)
        if scope_report["bindings"]["plan"]!=s.ref(plan_path):
            raise ValueError("Scope plan identity differs")
    predictions,tables={},[]
    for task,inventory in inventories.items():
        views=s.index_rows(raw_views[task])
        if set(views)!=set(s.index_rows(inventory)):raise ValueError("Scope/view identity differs")
        category=plan["tasks"][task]["record"]["category"]
        rows=[]
        for item in inventory:
            view=views[s.identity(item)]
            if item["source_sha256"]!=view["source_sha256"]:
                raise ValueError("Source identity mismatch")
            row={key:item[key] for key in ("file","source_sha256","original_graph_node_id",
                                          "node_type","solidifi","scope_status","scope_verified")}
            row["fold"]=view["fold"]
            row["prediction"]=keyword_prediction(category,item["renamed_code"],item["renamed_function_code"])
            rows.append(row)
        predictions[task]=rows
        tables.extend(dict(task=task,**row) for row in summarize(rows,views))
    result=dict(version=VERSION,training_count=0,model_forward_count=0,
                bindings=dict(plan=s.ref(plan_path),views=s.ref(Path(frozen_root)/"A/node_views.json"),
                              scopes=s.ref(scope_path) if scope_path else None),
                keyword_patterns={category:pattern.pattern for category,pattern in PATTERNS.items()},
                feature_view="frozen8C filewise idN marker-identifier rewrite; comments/strings excluded from keyword recognition",
                predictions=predictions,pooled_metrics=tables,
                notes=["No learning, checkpoint, model selection or new p-value.",
                       "node_or_function is the requested baseline; node_text/function_text are explicit decomposition.",
                       "Known keyword syntax is not a semantic vulnerability oracle; member-call binding is not asserted.",
                       "Function-scoped fallback is zero only when exact AST ownership is unavailable; counts are retained and reported.",
                       "NonSolidiFI and env-source features were not rewritten; env nodes are not scored.",
                       "C1/C2 are diagnostic views, not verified truth; C2 masks and never flips C1.",
                       "Wilson P/R intervals are descriptive and ignore within-file/clone dependence; no F1 interval."])
    output.mkdir(parents=False)
    s.write(output/"keyword_baselines.json",result);s._csv(output/"pooled_metrics.csv",tables)
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan",required=True);parser.add_argument("--frozen-root",required=True)
    parser.add_argument("--output",required=True);parser.add_argument("--scope-path")
    args=parser.parse_args()
    result=run_keyword_baselines(args.plan,args.frozen_root,args.output,args.scope_path)
    print("Scored",len(result["pooled_metrics"]),"pooled keyword baselines")
