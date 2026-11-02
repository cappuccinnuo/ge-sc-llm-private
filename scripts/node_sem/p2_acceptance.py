"""CPU-only NS-P2 real-input audit and carrier acceptance; never fits a model.

Reads forbidden attributes only in the explicitly separated invariant/perturbation
audit. The production feature function receives the disposable graph directly.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import time

from scripts.DFG.graph_audit import frozen
from scripts.DFG.projection import ANCHOR, decoded
from scripts.DFG.models import Unsupported
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref, write
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2 import execution as legacy
from scripts.DFG.dfg_v2.experiment.run import _code_refs
from .text_view import PLAN, ROOT, load_context, write_views, build_text_view
from .carrier import load_modality, _load, _aligned, row_key

TASKS = ("reentrancy_node", "access_control_node", "reentrancy_contract", "access_control_contract")
ATTRIBUTES = ("code", "node_type", "source_file", "node_source_code_lines",
              "label", "type_label", "node_info_vulnerabilities", "method", "token")
ARTIFACT = ROOT / "scripts/node_sem/artifacts/ns_p2"
TEXT = ROOT / "scripts/node_sem/artifacts/text_v1"


def original_invariants(context):
    base, enhanced = context["graphs"]["F0"], context["graphs"]["F3"]
    assert list(base) == context["order"]
    fields = Counter()
    for node in base:
        assert node in enhanced
        for key in ATTRIBUTES:
            assert (key in base.nodes[node]) == (key in enhanced.nodes[node])
            assert frozen(base.nodes[node].get(key)) == frozen(enhanced.nodes[node].get(key))
            fields[key] += 1
        # Stronger than the requested nine fields: all attributes agree.
        assert frozen(dict(base.nodes[node])) == frozen(dict(enhanced.nodes[node]))
    assert [(n, a["node_type"]) for n,a in enhanced.nodes(data=True) if n in base] == [
        (n,a["node_type"]) for n,a in base.nodes(data=True)]
    for u,v,k,attrs in base.edges(keys=True,data=True):
        assert enhanced.has_edge(u,v,k)
        assert frozen(attrs) == frozen(enhanced.edges[u,v,k])
    return dict(original_nodes=len(base), auxiliary_nodes=len(enhanced)-len(base),
                original_edges=base.number_of_edges(), enhanced_edges=enhanced.number_of_edges(),
                field_comparisons=dict(fields), all_attributes_equal=True, base_edges_preserved=True)


def perturbations(context, baselines):
    results = {}
    task_id = context["task_id"]
    for change in ("forbidden", "prefix", "anchor"):
        graph = copy.deepcopy(context["graphs"]["F3"])
        changed = 0
        for _, attrs in graph.nodes(data=True):
            if change == "forbidden":
                attrs.update(type_label=998, method="forbidden-method",
                             node_info_vulnerabilities=[{"lines": [99999], "label": "perturbed"}])
                changed += 1
            else:
                match = ANCHOR.search(decoded(attrs.get("label", "")))
                if match:
                    attrs["label"] = ("poisoned-prefix-file.sol-line99999-" + match.group(0)
                                      if change == "prefix" else "broken-anchor")
                    changed += 1
                    if change == "anchor":
                        break
        assert changed > 0
        before = graph_fingerprint(graph)
        for view in ("anonymous", "original"):
            key = view + "/" + change
            if change == "anchor":
                try:
                    build_text_view(task_id, view, context, graph)
                except (ValueError, Unsupported):
                    results[key] = dict(changed=changed, rejected=True)
                else:
                    raise AssertionError("Corrupt AST anchor accepted")
            else:
                assert build_text_view(task_id, view, context, graph) == baselines[view]
                results[key] = dict(changed=changed, rows=len(baselines[view]), rows_identical=True)
            assert before == graph_fingerprint(graph)
    return results


def texts(out=TEXT, audit=ARTIFACT):
    out, audit = Path(out), Path(audit)
    if out.exists() or (audit / "text_acceptance.json").exists():
        raise FileExistsError("NS-P2 text acceptance refuses existing outputs")
    audit.mkdir(parents=True, exist_ok=True)
    summary = {}
    for task_id in TASKS:
        start = time.monotonic()
        context = load_context(task_id)
        before = {k:graph_fingerprint(g) for k,g in context["graphs"].items()}
        invariants = original_invariants(context)
        references = write_views(task_id, out, context)
        records = {v:read(checked(r)) for v,r in references.items()}
        checks = perturbations(context, {v:r["rows"] for v,r in records.items()})
        assert before == {k:graph_fingerprint(g) for k,g in context["graphs"].items()}
        summary[task_id] = dict(invariants=invariants, producer_perturbations=checks,
            manifests=references, elapsed_seconds=time.monotonic()-start,
            views={v:dict(rows=len(r["rows"]), cut_modes=r["cut_modes"],
                         fallback_by_type=r["fallback_by_type"], unique_texts=r["unique_texts"],
                         inverse_rename_exact=r["inverse_rename_exact"])
                   for v,r in records.items()})
        write(audit / (task_id + "_texts.json"), summary[task_id])
        print(json.dumps(dict(task=task_id, **summary[task_id]["views"])), flush=True)
    write(audit / "text_acceptance.json", dict(passed=True, tasks=summary))
    return summary


def verify(encoded, audit=ARTIFACT):
    result = {}
    for task_id in TASKS:
        context = load_context(task_id)
        profiles = context["graphs"]
        for view_name in ("original", "anonymous"):
            path = Path(encoded) / view_name / task_id / "manifest.json"
            if read(path.with_name("manifest.seal.json"))["manifest"] != ref(path):
                raise ValueError("Modality manifest seal differs")
            values = load_modality(ref(path))
            manifest, matrix = _load(ref(path))
            assert manifest["modality"] == "code" and manifest["feature_shape"] == [len(profiles["F3"]),256]
            selections = {}
            for profile, graph in profiles.items():
                selected = _aligned(manifest, graph, task_id, view_name,256)
                expected = [row_key(n,a) for n,a in graph.nodes(data=True)]
                assert [r["row_key"] for r in selected] == expected
                assert all(values[key].shape == (256,) for key in expected)
                selections[profile] = dict(rows=len(selected), omitted_auxiliary=len(values)-len(selected))
            record = manifest["encoding"]
            assert record["repeat_max_abs_error"] <= 1e-6 and record["optimizer_steps"] == 0
            result[task_id + "/" + view_name] = dict(manifest=ref(path),
                shape=list(matrix.shape), selected=selections, encoding=record)
    legacy.load(PLAN)  # Checks the already-authorized effective runtime amendment.
    runtime = _code_refs()
    amendment = PLAN.with_name("runtime_resume_v2.json")
    saved = read(amendment)
    # The amendment's exact shape is handled by its frozen loader; also record
    # the current digest so the acceptance report can expose equality evidence.
    assert saved["runtime"] == runtime, "8H effective runtime does not equal current code refs"
    report = dict(passed=True, fits=0, variants=8, manifest_records=result,
                  frozen_8h_plan=ref(PLAN), frozen_8h_effective_runtime=ref(amendment),
                  runtime_code_refs_equal=True)
    write(Path(audit) / "acceptance.json", report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("texts","verify"))
    p.add_argument("--texts-root",default=str(TEXT))
    p.add_argument("--encoded",default=str(ARTIFACT / "encoded"))
    p.add_argument("--audit",default=str(ARTIFACT))
    args=p.parse_args()
    if args.command=="texts":texts(args.texts_root,args.audit)
    else:
        result=verify(args.encoded,args.audit)
        print(json.dumps(dict(passed=result["passed"],variants=result["variants"],fits=0)))


if __name__=="__main__":
    main()
