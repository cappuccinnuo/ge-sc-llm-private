"""Refine EP0 call census: builtins/events are not unresolved internal calls."""
from collections import Counter
from .common import OUT, read, write, checked, key
BUILTINS=("require","assert","revert","selfdestruct","suicide","keccak256","sha3","sha256",
          "ripemd160","ecrecover","addmod","mulmod","blockhash","gasleft")

def classify(sem,call):
    from scripts.node_sem.facts_ast import unwrap
    callee=unwrap(call.child_by_field_name("function"))
    if sem.builtin_call(call,BUILTINS):return "builtin",None
    resolved=sem.resolve_callable(call)
    if resolved is not None:
        contract=sem.contract(resolved)
        return ("library" if contract is not None and contract.type=="library_declaration" else "resolved_internal"),resolved
    if callee is None:return "missing_callee",None
    if callee.type=="identifier":
        binding=sem.resolve_identifier(callee)
        if binding["kind"]=="contract":return "contract_conversion",None
        members=sem.members(call).get(sem.text(callee),[])
        if members and all(n.type in ("event_definition","event_declaration","struct_declaration","enum_declaration","error_declaration") for n in members):
            return "event_struct_enum_error",None
        if len(members)>1 and any(n.type=="function_definition"for n in members):
            return "unresolved_overload",None
        if binding["kind"] in ("local","param","state"):return "unresolved_callable_value",None
        return "unclassified_unqualified",None
    if callee.type=="member_expression":
        receiver=unwrap(callee.child_by_field_name("object"))
        if receiver is not None and sem.text(receiver)=="super":return "unresolved_super",None
        return "member_or_external",None
    return "conversion_new_or_wrapper",None

def collect():
    from scripts.node_sem.facts_io import load_context
    from scripts.node_sem.facts import _raw_projection,STATEMENTS
    from scripts.node_sem.facts_ast import AstSemantics
    from scripts.DFG.dfg_v2.projection_view import ProjectionView
    from scripts.DFG.projection import Projector
    reports={}
    for tid in read(OUT/"inputs.json")["tasks"]:
        ctx=load_context(tid);g=ctx["graphs"]["F3"];files=[]
        for file,source in sorted(ctx["source_text"].items()):
            sub=g.subgraph([n for n,a in g.nodes(data=True)if a["source_file"]==file and a["node_type"]!="env_source"])
            pv=ProjectionView(source,file);sem=AstSemantics(pv)
            nodes=_raw_projection(pv,Projector(sub,pv));inverse={key(n):ident for ident,n in nodes.items()}
            counts=Counter();seen=set();pairs=set();samples=[]
            for st in sem.nodes:
                if st.type not in STATEMENTS:continue
                for call in sem.owned_nodes(st):
                    if call.type!="call_expression"or key(call)in seen:continue
                    seen.add(key(call));kind,fn=classify(sem,call);counts[kind]+=1
                    if kind=="resolved_internal":
                        a,b=inverse.get(key(st)),inverse.get(key(fn))
                        if a is not None and b is not None and a!=b:pairs.add((a,b));counts["projected_internal"]+=1
                        else:counts["missing_internal_endpoint"]+=1
                    elif kind.startswith(("unclassified","unresolved")) and len(samples)<5:
                        samples.append(dict(call=list(key(call)),reason=kind))
            files.append(dict(file=file,counts=dict(counts),unique_projected_edges=len(pairs),unresolved_examples=samples))
        total=Counter()
        for f in files:total.update(f["counts"])
        reports[tid]=dict(files=files,total=dict(total),unique_projected_edges=sum(f["unique_projected_edges"]for f in files),
            note="Unknown call sites are listed separately, not asserted internal calls. Projected/resolved rate is conditional coverage, not full semantic recall.")
    write(OUT/"call_classification.json",reports)
    print("call census complete",flush=True)

if __name__=="__main__":collect()
