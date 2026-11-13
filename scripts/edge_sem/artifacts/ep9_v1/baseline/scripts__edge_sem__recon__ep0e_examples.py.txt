
"""Read-only residual evidence; does not change the failed EP0e gate."""
from collections import defaultdict
from .common import key, read, write, ref
from .ep0e_common import OUT, TASKS, contexts
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.node_sem.facts_ast import AstSemantics, unwrap
from scripts.edge_sem.call_resolve import receiver_type, resolve_call


def node_trace(sem, node, depth=2):
    if node is None:
        return None
    row = dict(anchor=list(key(node)),text=sem.text(node),type=node.type)
    unwrapped=unwrap(node)
    row["inferred_type"]=receiver_type(sem,unwrapped)
    binding=sem.root_binding(unwrapped)
    row["root_binding"]=dict(kind=binding["kind"],type_name=binding["type_name"],
        declaration=list(key(binding["declaration"])) if binding["declaration"] is not None else None)
    if unwrapped.type=="call_expression":
        result=resolve_call(sem,unwrapped)
        row["call_result"]=dict(status=result["status"],kind=result["kind"],reason=result["reason"],
            target=list(key(result["target"])) if result["target"] is not None else None)
    if depth:
        row["fields"]={name:node_trace(sem,child,depth-1)
            for name in ("object","base","argument","function","left","right")
            for child in (node.child_by_field_name(name),) if child is not None}
    return row


def main():
    result={}
    for task in TASKS:
        current=read(OUT/("calls_"+task+".json"))
        by_file=defaultdict(list)
        for row in current["using_candidates"]:
            if row["candidate"] and not row["matched"]:
                by_file[row["file"]].append(row)
        ctx=contexts(task)
        traces=[]
        for file,misses in sorted(by_file.items()):
            sem=AstSemantics(ProjectionView(ctx["source_text"][file],file))
            nodes={key(n):n for n in sem.nodes}
            for row in misses:
                call=nodes[tuple(row["call_anchor"])]
                callee=sem._postfix(unwrap(call.child_by_field_name("function")))
                traces.append(dict(identity=row,receiver_trace=node_trace(
                    sem,callee.child_by_field_name("object")),
                    expected_definition=list(key(nodes[tuple(row["expected_target"])]))))
        # r7's coarse option count includes one negated-receiver shape that
        # still does not match the literal member/call-option chain in this run.
        residual=[]
        for row in current["raw_calls"]:
            if row["status"]=="unknown" and row["reason"]=="receiver_or_member_not_confirmed" and (
                    ".value(" in row["expression"] or ".gas(" in row["expression"]):
                file=row["file"]
                sem=AstSemantics(ProjectionView(ctx["source_text"][file],file))
                node=next(n for n in sem.nodes if key(n)==tuple(row["call_anchor"]))
                residual.append(dict(identity=row,callee_trace=node_trace(
                    sem,unwrap(node.child_by_field_name("function")))))
        result[task]=dict(misses=traces,residual_option_shapes=residual,input=ref(OUT/("calls_"+task+".json")))
    write(OUT/"residual_evidence.json",result)
    print("Residual evidence saved; no resolver or gate changes",flush=True)


if __name__=="__main__":
    main()
