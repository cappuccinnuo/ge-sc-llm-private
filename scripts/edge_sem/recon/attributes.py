"""Inspect all planned source fields against accepted facts, without encoding."""
from collections import Counter
from .common import ROOT, OUT, read, write, checked, ref

def collect():
    from scripts.node_sem import facts_schema as fs
    from scripts.node_sem.facts_io import load_context
    inputs=read(OUT/"inputs.json")
    reports={}
    for tid,task in inputs["tasks"].items():
        rows=[__import__("json").loads(l) for l in checked(task["facts"]).read_text().splitlines()]
        counts={k:Counter() for k in ("var_kind","type_shape","sink","syntax","return_handling","arith_ops","env","guard_kind","guard_operands","write_shape","status")}
        signatures=Counter(); fn_fields=set(); state_fields=set(); dfg_fields=set()
        for row in rows:
            f=row["facts"];fs.validate(f)
            for role in ("defs","uses"):
                for v in f["dfg"].get(role,[]):
                    counts["var_kind"][v["kind"]]+=1
                    dfg_fields.update(v)
                    if "type" in v:counts["type_shape"][v["type"]]+=1
            for v in f["dfg"].get("to",[]):counts["sink"][v["sink"]]+=1
            counts["syntax"].update(f["syntax"])
            if f["external"]:counts["return_handling"][f["external"]["return_handling"]]+=1
            counts["arith_ops"].update(f["arith"].get("ops",[]))
            counts["env"].update(f["env"].get("keys",[]))
            for g in f["guards"]:
                counts["guard_kind"][g["kind"]]+=1;counts["guard_operands"].update(g["operand_classes"])
            for v in f["state"].get("writes",[]):
                state_fields.update(v);counts["write_shape"][v.get("shape","<missing>")]+=1
            fn_fields.update(f["fn_summary"])
            for group in ("dfg","order","state"):
                if f[group]:counts["status"][group+":"+f[group]["status"]]+=1
            counts["status"]["guard:"+f["guard_status"]]+=1
            signatures.update(f.keys())
        audit=read(checked(task["graph_audit"]))
        l1=audit["layers"]["L1"]
        evidence_keys=Counter(k for e in l1["evidence"] for k in e)
        update_fields=[]
        def visit(value,path):
            if isinstance(value,dict):
                for k,v in value.items():
                    if any(s in k.lower()for s in ("strong","weak","kill","update")):
                        update_fields.append(dict(path=path+"."+k,value=v if not isinstance(v,(list,dict))else type(v).__name__))
                    visit(v,path+"."+k)
            elif isinstance(value,list):
                for i,v in enumerate(value):visit(v,path+"["+str(i)+"]")
        visit(l1["evidence"],"layers.L1.evidence")
        reports[tid]=dict(facts_ref=task["facts"],rows=len(rows),observed={k:dict(v)for k,v in counts.items()},
            dfg_variable_fields=sorted(dfg_fields),state_write_fields=sorted(state_fields),
            fn_summary_fields=sorted(fn_fields),top_level_fields=dict(signatures),
            l1_evidence_count=len(l1["evidence"]),l1_evidence_keys=dict(evidence_keys),
            update_marker_fields=update_fields,bit15_available=bool(update_fields))
    write(OUT/"attribute_sources.json",dict(tasks=reports,
        schema=ref(ROOT/"scripts/node_sem/facts_schema.py"),SHAPES=list(fs.SHAPES),
        SYNTAX=list(fs.SYNTAX),RETURN_HANDLING=list(fs.RETURN_HANDLING),
        ARITH_OPS=list(fs.ARITH_OPS),ENV_KEYS=list(fs.ENV_KEYS),
        guard_anchor_source="in-memory GuardAnalyzer; serialized facts omit _anchor",
        attributes_generated=False))
    print("attribute source inspection complete",flush=True)

if __name__=="__main__":collect()
