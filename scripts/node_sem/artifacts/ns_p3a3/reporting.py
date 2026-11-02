"""NS-P3a3 reporting: count row impacts and bind difficult-case evidence."""
import json
from collections import Counter
from pathlib import Path
from scripts.node_sem.facts_verify import read_jsonl, sealed_manifest
from scripts.node_sem.facts_io import load_context
from scripts.node_sem.facts_ast import AstSemantics,key
from scripts.node_sem.facts import _raw_projection
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked,read,write,ref

ROOT=Path("scripts/node_sem/artifacts/facts_v1")
OLD=ROOT/"accepted_attempt3"
NEW=ROOT/"accepted_attempt4"

def main():
    revision=read(NEW/"revision_comparison.json")
    result={}
    for task,r in revision["tasks"].items():
        oldm=sealed_manifest(OLD/"original"/task/"manifest.json")
        newm=sealed_manifest(NEW/"original"/task/"manifest.json")
        old={x["row_key"]:x["facts"] for x in read_jsonl(checked(oldm["facts"]))}
        new={x["row_key"]:x["facts"] for x in read_jsonl(checked(newm["facts"]))}
        audits=read(checked(newm["audit"]))
        prior=read(checked(oldm["audit"]))
        changes=r["changes"]
        guard_rows={c["row_key"] for c in changes if c["reason"] in ("boolean_sender_proof","auth_refill") or
                    (c["path"][0] in ("state_decl","fn_summary","contract_summary") and
                     c["path"][1] in ("auth","unguarded_writer","unguarded_write_functions",
                         "sender_guard","auth_write","auth_state","auth_state_count"))}
        impacted={"guard":sorted(guard_rows),"throw_direct_statement":[],
                  "three_value":[],"target_scope":[]}
        fields={k:Counter() for k in ("three_value","target_scope")}
        throw_counts={}
        for file,audit in audits.items():
            support=audit["state_precision"]
            thrown=[c for c in support["classifications"] if
                    c["decision"]=="builtin_or_global" and c["diagnostic"].get("name")=="throw"]
            if thrown:throw_counts[file]=len(thrown)
            impacted["throw_direct_statement"].extend(n for n in support["throw_supported_rows"]
                if old[n]["state"]["status"]=="unknown" and new[n]["state"]["status"]=="supported")
            for n,entry in audit["summary_precision"].items():
                for cause in ("three_value","target_scope"):
                    if entry[cause]:
                        impacted[cause].append(n)
                        fields[cause].update(entry[cause])
        context=load_context(task)
        examples=[]
        for file in ("buggy_2.sol","buggy_3.sol"):
            if file not in context["sources"]:raise ValueError("Missing requested example")
            g=context["graphs"]["F3"]
            sub=g.subgraph([n for n,a in g.nodes(data=True)
                           if a["source_file"]==file and a["node_type"]!="env_source"]).copy()
            view=ProjectionView(context["source_text"][file],file)
            sem=AstSemantics(view)
            nodes=_raw_projection(view,Projector(sub,view))
            case=[]
            for n,node in nodes.items():
                owner=sem.owner(node)
                if owner is None or sem.text(owner.child_by_field_name("name"))!="changeOwner":continue
                if node.type not in ("function_definition","expression_statement"):continue
                case.append(dict(row_key=n,ast=list(key(node)),text=sem.text(node),
                    before={k:old[n][k] for k in ("guards","self_condition","state","fn_summary")},
                    after={k:new[n][k] for k in ("guards","self_condition","state","fn_summary")}))
            # Match each owner state declaration by identity, not CSV ordering.
            for n,node in nodes.items():
                if node.type=="state_variable_declaration" and sem.text(node.child_by_field_name("name"))=="owner":
                    case.append(dict(row_key=n,ast=list(key(node)),text=sem.text(node),
                        before=dict(state_decl=old[n]["state_decl"]),
                        after=dict(state_decl=new[n]["state_decl"])))
            if not any(x["text"].startswith("owner") and x["after"].get("guards") for x in case):
                raise ValueError("changeOwner writer evidence missing")
            examples.append(dict(file=file,source=context["sources"][file],rows=case))
        result[task]=dict(rows=r["rows"],before=r["before"],after=r["after"],
            impact_counts={k:len(set(v)) for k,v in impacted.items()},
            impact_rows={k:sorted(set(v)) for k,v in impacted.items()},
            impact_fields={k:dict(v) for k,v in fields.items()},
            throw_diagnostics=sum(throw_counts.values()),throw_files=throw_counts,
            examples=examples,changed_rows=r["changed_rows"])
        print(task,result[task]["impact_counts"],"throw diagnostics",result[task]["throw_diagnostics"],flush=True)
    out=NEW/"precision_summary.json"
    if out.exists():raise FileExistsError(str(out))
    write(out,dict(tasks=result,comparison=ref(NEW/"revision_comparison.json"),
        note="Row effects overlap and are not additive. guard is actual old/new field difference; throw is direct recovered statement support, excludes indirect K masking; three_value is removal from current scoped candidate masks; target_scope compares broad vs scoped targets with same current certain facts/three-valued rules. No model effect or F1 is measured."))
if __name__=="__main__":main()
