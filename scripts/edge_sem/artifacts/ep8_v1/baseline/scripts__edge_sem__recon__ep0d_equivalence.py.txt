"""Compare the explicit-callee adapter to the frozen resolver on prior calls."""
from collections import Counter
from .common import key, read
from .ep0d_common import EP0C, contexts, file_views
from scripts.node_sem.facts_ast import unwrap
from scripts.edge_sem.call_resolve import _resolve_callee


def compare_file(sem, prior_rows):
    previous = {tuple(r["call_anchor"]): r for r in prior_rows}
    calls = [n for n in sem.nodes if n.type == "call_expression"]
    assert set(previous) == {key(n) for n in calls}
    results = []
    for call in calls:
        callee = unwrap(call.child_by_field_name("function"))
        if callee is None or callee.type not in ("identifier", "member_expression"):
            continue
        frozen = sem.resolve_callable(call)
        adapted = _resolve_callee(sem, call, callee)
        assert key(frozen) == key(adapted), ("explicit callee changed binding", key(call))
        results.append(dict(call_anchor=list(key(call)), callee_type=callee.type,
            frozen_target=list(key(frozen)) if frozen is not None else None,
            adapter_target=list(key(adapted)) if adapted is not None else None,
            equal=True))
    return dict(prior_calls=len(calls), eligible=len(results),
                ineligible=len(calls)-len(results), rows=results, all_equal=True)


def audit_task(task):
    prior = read(EP0C/("calls_"+task+".json"))
    by_file = {}
    for row in prior["raw_calls"]:
        by_file.setdefault(row["file"], []).append(row)
    result = []
    for file,source,sub,sem,raw,inverse in file_views(contexts(task)):
        result.append(dict(file=file, **compare_file(sem,by_file.get(file,[]))))
    assert sum(r["prior_calls"] for r in result) == len(prior["raw_calls"])
    return result
