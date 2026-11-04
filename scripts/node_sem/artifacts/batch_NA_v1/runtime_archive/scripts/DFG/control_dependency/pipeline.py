"""Append one control relation to the frozen Stage K HCG+DDG graph."""
import copy
from collections import Counter
from ..models import Unsupported
from ..graph_audit import fingerprint
from ..state.stage_k.profile import SupportedSourceView
from .analysis import analyze_view
from .projection import project_results, materialize, RELATION

VERSION = "author-hcg-ddg-guard-build-v1"


def augment(graph, sources, metadata=None, use_control=True):
    if not graph.is_directed() or not graph.is_multigraph():
        raise ValueError("Expected frozen directed MultiDiGraph")
    original = fingerprint(graph)
    audit = {"version": VERSION, "files": {}, "evidence": [],
             "labels_used_for_analysis": False, "features_used_for_analysis": False,
             "structural_ast_label_used_for_exact_projection": True,
             "input_fingerprint": original, "use_control": use_control}
    if not use_control:
        output = copy.deepcopy(graph)
        audit.update(disabled_exact=fingerprint(output)==original, output_fingerprint=original)
        return output, audit
    if any(d.get("edge_type") == RELATION for _,_,d in graph.edges(data=True)):
        raise ValueError("Already enhanced control input")
    metadata = metadata or {}
    for file in sorted({d["source_file"] for _,d in graph.nodes(data=True)}):
        record = {"source_file": file, "status": "file_fallback", "functions": []}
        audit["files"][file] = record
        if file not in sources:
            record["reason"] = "Exact source missing; all original graph content retained"
            continue
        try:
            view = SupportedSourceView(sources[file], file, metadata.get(file))
            results = analyze_view(view)
            proof, projection = project_results(graph, view, results)
            record.update(status="analyzed", source_sha256=view.sha256,
                version_evidence=view.version_evidence, functions=projection["functions"],
                projection=projection["projector"], status_counts=projection["status_counts"],
                projected_facts=len(proof))
            audit["evidence"].extend(proof)
        except Unsupported as exc:
            record["reason"] = str(exc)
    output, invariants, context = materialize(graph, audit["evidence"])
    audit.update(invariants=invariants, context=context, output_fingerprint=fingerprint(output),
        relation_counts=dict(Counter(d["edge_type"] for _,_,d in output.edges(data=True))),
        file_status_counts=dict(Counter(x["status"] for x in audit["files"].values())),
        function_status_counts=dict(Counter(f["status"] for x in audit["files"].values()
                                            for f in x["functions"])))
    if fingerprint(graph) != original:
        raise AssertionError("Frozen input graph mutated")
    return output, audit
