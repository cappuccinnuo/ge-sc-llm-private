"""NS-P3a2 row-by-row constrained revision audit; no scores/labels are read."""
import argparse
from collections import Counter
from pathlib import Path
from .facts_verify import read_jsonl, sealed_manifest, byte_sha
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, write, ref

GROUPS=("dfg","order","state","checked_call","state_decl","fn_summary","contract_summary")


def differences(a,b,path=()):
    if type(a)!=type(b):
        yield path,a,b
    elif isinstance(a,dict):
        for k in sorted(set(a)|set(b)):
            if k not in a or k not in b: yield path+(k,),a.get(k),b.get(k)
            else: yield from differences(a[k],b[k],path+(k,))
    elif isinstance(a,list) and len(a)==len(b):
        for i,(x,y) in enumerate(zip(a,b)):yield from differences(x,y,path+(str(i),))
    elif a!=b:
        yield path,a,b


def allowed(path, revision="ns-p3a2"):
    if revision == "ns-p3a3" and path[0] in ("state_decl", "fn_summary", "contract_summary"):
        permitted = {
            "state_decl": {"status", "unknown_fields", "auth", "unguarded_writer", "unguarded_write_functions"},
            "fn_summary": {"status", "unknown_fields", "sender_guard", "auth_write"},
            "contract_summary": {"status", "unknown_fields", "auth_state", "auth_state_count"},
        }
        return "precision_summary" if len(path) > 1 and path[1] in permitted[path[0]] else None
    if path in (("state","status"),("order","status")): return "precise_state_or_order_support"
    if path[0]=="unresolved":return "diagnostic_scope"
    if path[0] in ("state_decl","fn_summary","contract_summary"):
        if path[:2] in (("state_decl","shape"),("state_decl","public"),("state_decl","constant_immutable"),
                       ("state_decl","has_initializer"),("contract_summary","kind")):
            return None
        return "full_ast_or_sealed_access_summary"
    if path[0]=="guards" and len(path)>=3 and path[2] in ("eq_pairs","is_sender_guard","disjunctive"):return "boolean_sender_proof"
    if path[:2]==("self_condition","eq_pairs"):return "boolean_sender_proof"
    if path[0]=="state" and len(path)==4 and path[1] in ("reads","writes") and path[3]=="auth":return "auth_refill"
    return None


def comparison(old,new,out,revision="ns-p3a2"):
    result={}
    for dest in sorted((Path(new)/"original").iterdir()):
        if not dest.is_dir():continue
        task=dest.name
        am=sealed_manifest(Path(old)/"original"/task/"manifest.json")
        bm=sealed_manifest(dest/"manifest.json")
        a=read_jsonl(checked(am["facts"]));b=read_jsonl(checked(bm["facts"]))
        if len(a)!=len(b):raise ValueError("Changed row population")
        changes=[]; unexpected=[]; counts=Counter()
        for x,y in zip(a,b):
            if type(x["row_key"])!=type(y["row_key"]) or x["row_key"]!=y["row_key"]:
                raise ValueError("Changed identity/order")
            for path,before,after in differences(x["facts"],y["facts"]):
                why=allowed(path,revision)
                entry=dict(row_key=x["row_key"],path=list(path),before=before,after=after,reason=why)
                (changes if why else unexpected).append(entry)
                counts[".".join(path[:2])]+=1
        def metrics(rows):
            facts=[r["facts"] for r in rows];unknown={}
            for g in GROUPS:
                applicable=[f[g] for f in facts if f[g]]
                unknown[g]=dict(count=sum(i["status"]=="unknown" for i in applicable),applicable=len(applicable))
            unknown["guards"]=dict(count=sum(f["guard_status"]=="unknown" for f in facts),applicable=len(facts))
            return dict(unknown=unknown,unresolved=dict(sum((Counter(f["unresolved"]) for f in facts),Counter())),
                disjunctive_guards=sum(g.get("disjunctive",False) for f in facts for g in f["guards"]),
                auth_declarations=sum(f["state_decl"].get("auth",False) for f in facts),
                unknown_fields={g:dict(Counter(k for f in facts for k in f[g].get("unknown_fields",[])))
                                for g in ("state_decl","fn_summary","contract_summary")})
        result[task]=dict(rows=len(a),changed_rows=len({c["row_key"] for c in changes}),counts=dict(counts),
            before=metrics(a),after=metrics(b),unexpected=unexpected,changes=changes,
            old=ref(Path(old)/"original"/task/"manifest.json"),new=ref(dest/"manifest.json"),
            new_auth_declaration_rows=[x["row_key"] for x,y in zip(a,b)
                if not x["facts"]["state_decl"].get("auth") and y["facts"]["state_decl"].get("auth")])
    write(out,dict(tasks=result,passed=not any(r["unexpected"] for r in result.values())))
    if any(r["unexpected"] for r in result.values()):raise ValueError("Unexpected fact differences; see saved audit")
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--old",required=True);p.add_argument("--new",required=True);p.add_argument("--out",required=True)
    p.add_argument("--revision",choices=("ns-p3a2","ns-p3a3"),default="ns-p3a2")
    a=p.parse_args()
    if Path(a.out).exists():raise FileExistsError(a.out)
    result=comparison(a.old,a.new,a.out,a.revision)
    for task,r in result.items():print(task,r["rows"],"rows;",r["changed_rows"],"changed; unexpected",len(r["unexpected"]))

if __name__=="__main__":main()
