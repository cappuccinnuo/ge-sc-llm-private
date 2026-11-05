"""Postdominators and direct control dependence, never transitive closure."""
from collections import deque
from ..models import Unsupported
from ..state.stage_k.profile import SupportedSourceView
from .cfg import ControlCFGBuilder
from .models import ControlFact, ControlResult, VERSION


def reachable(ir):
    seen, queue = set(), [ir.entry]
    while queue:
        node = queue.pop()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(ir.nodes[node].successors)
    return seen


def postdominators(ir, max_iterations=100000):
    active = reachable(ir)
    if ir.exit not in active:
        raise Unsupported("guard: no reachable unified exit")
    backward = {n: set() for n in active}
    for source in active:
        for target in ir.nodes[source].successors:
            if target not in active:
                raise AssertionError("reachable successor omitted")
            backward[target].add(source)
    exit_reachable, queue = set(), [ir.exit]
    while queue:
        node = queue.pop()
        if node in exit_reachable:
            continue
        exit_reachable.add(node)
        queue.extend(backward[node])
    if exit_reachable != active:
        raise Unsupported("guard: non-terminating region needs explicit divergence handling")
    sets = {n: ({n} if n == ir.exit else set(active)) for n in active}
    for iteration in range(max_iterations):
        changed = False
        for node in sorted(active):
            if node == ir.exit:
                continue
            successors = list(ir.nodes[node].successors)
            if not successors:
                raise AssertionError("non-exit node has no successor")
            value = {node} | set.intersection(*(sets[s] for s in successors))
            if value != sets[node]:
                sets[node], changed = value, True
        if not changed:
            break
    else:
        raise Unsupported("guard: postdominator iteration limit")
    immediate = {ir.exit: None}
    for node in active - {ir.exit}:
        strict = sets[node] - {node}
        candidates = [d for d in strict if strict - {d} <= sets[d]]
        if len(candidates) != 1:
            raise Unsupported("guard: nonunique immediate postdominator")
        immediate[node] = candidates[0]
    return sets, immediate


def path_between(ir, start, target):
    queue = deque([(start, (start,))])
    seen = set()
    while queue:
        node, path = queue.popleft()
        if node == target:
            return path
        if node in seen:
            continue
        seen.add(node)
        for child in sorted(ir.nodes[node].successors):
            queue.append((child, path + (child,)))
    raise AssertionError("postdominator has no CFG witness path")


def control_facts(ir, max_iterations=100000):
    sets, immediate = postdominators(ir, max_iterations)
    facts = []
    for source in sorted(sets):
        controller = ir.nodes[source]
        if controller.kind not in ("if", "guard"):
            continue
        if controller.anchor is None:
            raise AssertionError("control source has no AST anchor")
        for successor, branch in sorted(controller.successors.items()):
            if successor in sets[source]:
                continue
            target, chain = successor, []
            while target != immediate[source]:
                if target is None or target in chain:
                    raise Unsupported("guard: invalid postdominator chain")
                chain.append(target)
                dependent = ir.nodes[target]
                if dependent.anchor is not None and dependent.anchor != controller.anchor:
                    witness = (source,) + path_between(ir, successor, target)
                    for a, b in zip(witness, witness[1:]):
                        if b not in ir.nodes[a].successors:
                            raise AssertionError("invalid fact CFG path")
                    facts.append(ControlFact(ir.function, ir.source_sha256,
                        controller.anchor, dependent.anchor, branch, (source, successor), witness,
                        {"algorithm": "direct edge/postdominator control dependence",
                         "version": VERSION, "controller_kind": controller.kind,
                         "controller_evidence": controller.evidence,
                         "postdominator_chain": tuple(chain),
                         "stop_at_immediate_postdominator": immediate[source],
                         "modifier_context": ir.evidence.get("modifier"),
                         "implicit_exceptions_modeled": False,
                         "transitive_closure_added": False}))
                target = immediate[target]
    return facts


def analyze_view(view, selected_functions=None, max_iterations=100000):
    results = []
    selected = set(selected_functions) if selected_functions is not None else None
    observed = set()
    for function in view.functions:
        fid = view.file + ":" + str(function.start_byte)
        if selected is not None and fid not in selected:
            continue
        observed.add(fid)
        try:
            ir = ControlCFGBuilder(view, function).build()
            facts = control_facts(ir, max_iterations)
            results.append(ControlResult(fid, "analyzed", ir, facts,
                evidence={"source_sha256": view.sha256, "version": VERSION,
                          "function_span": [function.start_byte, function.end_byte],
                          "line": function.start_point[0] + 1, "binding": ir.evidence}))
        except Unsupported as exc:
            # IR and pending facts are local; no partially analyzed function is published.
            results.append(ControlResult(fid, "function_fallback", diagnostics=[{
                "file": view.file, "function": fid, "source_sha256": view.sha256,
                "start": function.start_byte, "end": function.end_byte,
                "line": function.start_point[0] + 1, "reason": str(exc),
                "partial_control_facts_published": False}],
                evidence={"source_sha256": view.sha256, "version": VERSION}))
    if selected is not None and observed != selected:
        raise ValueError("Selected function missing from source")
    return results


def analyze_source(source, file="example.sol", metadata=None, max_iterations=100000):
    view = SupportedSourceView(source, file, metadata)
    return view, analyze_view(view, max_iterations=max_iterations)
