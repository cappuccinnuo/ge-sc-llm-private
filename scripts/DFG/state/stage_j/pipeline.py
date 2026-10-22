"""One entry: frozen HCG -> scalar DDG -> bounded state analysis -> typed fusion."""
import copy
from dataclasses import asdict
from collections import Counter
from ...models import Unsupported
from ...graph_audit import fingerprint
from ...pipeline import augment as scalar_augment
from ..stage_f.frontend import StageFSourceView
from ..stage_f.analyzer import analyze_view as frozen_analyze
from ..stage_f.projection import projected_file, materialize, assert_preserved
from .analyzer import analyze_view
from .configuration import DDGConfig
from . import VERSION

STATE_RELATIONS = frozenset(("STATE_DEF_USE", "STATE_ACCESS_ORDER", "EXTERNAL_CALL_BEFORE_STATE_WRITE"))

def prepare_graph(graph, sources=None, config=None, metadata=None):
    config = config or DDGConfig()
    before = fingerprint(graph)
    audit = {"version": VERSION, "config": asdict(config), "files": {}, "evidence": [],
             "input_fingerprint": before, "labels_used_for_analysis": False}
    if not config.use_ddg:
        result = copy.deepcopy(graph)
        audit["disabled_exact"] = fingerprint(result) == before
        return result, audit
    if not graph.is_directed() or not graph.is_multigraph():
        raise ValueError("Expected directed multigraph")
    if any(d.get("edge_type") in STATE_RELATIONS for _,_,d in graph.edges(data=True)):
        raise ValueError("Use original HCG or frozen scalar E2; do not mix state versions")
    sources = sources or {}
    metadata = metadata or {}
    base = graph
    if config.add_scalar:
        base, audit["scalar"] = scalar_augment(graph, sources, config.max_iterations)
    if config.state_mode == "off":
        result = copy.deepcopy(base)
        audit["output_fingerprint"] = fingerprint(result)
        assert fingerprint(graph) == before
        return result, audit
    evidence = []
    files = sorted({d["source_file"] for _,d in base.nodes(data=True)})
    for file in files:
        rec = {"source_file": file, "functions": [], "status": "file_fallback"}
        audit["files"][file] = rec
        if file not in sources:
            rec["reason"] = "exact source missing; original sample preserved"
            continue
        try:
            view = StageFSourceView(sources[file], file, metadata.get(file))
            rec["source_sha256"] = view.sha256
            if config.recovery == "frozen":
                results = frozen_analyze(view, max_iterations=config.max_iterations)
                records = [{"function": x.function, "before": x.status, "after": x.status,
                            "recovered": False, "route": "frozen_stage_f_reused",
                            "before_diagnostics": x.diagnostics,
                            "facts": len(x.facts)} for x in results]
            else:
                results, records = analyze_view(view, enable_modifiers=config.recovery=="modifiers",
                                                max_iterations=config.max_iterations)
            proof, projection = projected_file(base, view, results)
            rec.update(status="analyzed", functions=records, projection=projection,
                       function_status_counts=dict(Counter(x.status for x in results)),
                       version_evidence=view.version_evidence)
            routes = {x["function"]: x for x in records}
            for e in proof:
                route = routes[e["function"]]
                e["coverage_analysis"] = {"version": VERSION, "route": route["route"],
                                           "recovered_function": route["recovered"]}
            rec["eligible_model_proofs"] = len(proof)
            rec["recovered_model_proofs"] = sum(e["coverage_analysis"]["recovered_function"] for e in proof)
            rec["recovered_functions"] = sum(x["recovered"] for x in records)
            rec["recovered_runtime_functions"] = sum(x["recovered"] and x.get("runtime_function",False) for x in records)
            evidence.extend(proof)
        except Unsupported as exc:
            rec["reason"] = str(exc)
    relations = STATE_RELATIONS if config.state_mode == "orders" else frozenset(("STATE_DEF_USE",))
    result, invariants = materialize(base, evidence, relations)
    # Frozen materializer's bookkeeping VERSION is preserved; separate semantic producer version is explicit.
    for _,_,d in result.edges(data=True):
        if d.get("edge_type") in STATE_RELATIONS:
            indices = d["state_evidence_indices"]
            d["state_materializer_version"] = d["state_version"]
            d["state_version"] = VERSION
            d["coverage_version"] = VERSION
            d["contains_recovered_fact"] = any(evidence[i]["coverage_analysis"]["recovered_function"] for i in indices)
    invariants = assert_preserved(base, result)
    audit.update(evidence=evidence, invariants=invariants, output_fingerprint=fingerprint(result),
        relation_counts=dict(Counter(d["edge_type"] for _,_,d in result.edges(data=True))))
    assert fingerprint(graph) == before
    return result, audit
