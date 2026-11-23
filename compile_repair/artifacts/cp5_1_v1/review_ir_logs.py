"""Summarize native IR errors without redistributing log excerpts or changing measured outcomes."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from population import LOCAL, OUT, load, save, sha256


def log_summary(path):
    digest = hashlib.sha256()
    counts = Counter()
    with path.open("rb") as source:
        for line in source:
            digest.update(line)
            if line.startswith(b"ERROR:ContractSolcParsing:Impossible to generate IR for "):
                counts["caught_partial_ir_messages"] += 1
            elif line.lstrip().startswith(b"Failed to generate IR for "):
                counts["ir_exception_headings"] += 1
    return dict(bytes=path.stat().st_size, sha256=digest.hexdigest(),
                caught_partial_ir_messages=counts["caught_partial_ir_messages"],
                ir_exception_headings=counts["ir_exception_headings"])


def main():
    completion = load(OUT / "measurement_completion.json")
    assert completion["status"] == "complete"
    review = load(OUT / "partial_ir_review.json")
    decision = load(OUT / "partial_ir_decision.json")
    assert decision["review_sha256"] == sha256(OUT / "partial_ir_review.json")
    known = {r["graph_sha256"] for r in review["selected_receipts"]}
    uid = review["unit"]
    audit = {}
    for stage in ("real_dev", "real_full", "real_masked", "benchmark", "package_dev"):
        table = OUT / (stage + ".jsonl")
        assert sha256(table) == load(OUT / (stage + "_summary.json"))["rows_sha256"]
        rows = []
        with table.open(encoding="utf8") as stream:
            for line in stream:
                r = json.loads(line)
                if r["unit_id"] != uid:
                    continue
                path = Path(r["result_path"])
                assert sha256(path) == r["result_sha256"]
                receipt = load(path)
                item = dict(policy=r.get("policy",r.get("rule")), operator=r.get("operator"),
                            result_sha256=r["result_sha256"], status=receipt["status"])
                if receipt["status"] == "success":
                    last = receipt["attempts"][-1]["slither"]
                    graph = path.with_name("graph.json")
                    item.update(graph_sha256=sha256(graph), d3_a=last["d3_a"], d3_b=last["d3_b"])
                    assert item["graph_sha256"] == last["graph_sha256"]
                    item["exactly_matches_confirmed_partial_graph"] = item["graph_sha256"] in known
                rows.append(item)
        audit[stage] = rows
    assert len(audit["real_dev"]) == 3 and all(r["exactly_matches_confirmed_partial_graph"] for r in audit["real_dev"])
    assert len(audit["real_full"]) == 1
    # Native diagnostics may print project source and expressions. Keep full logs in the approved local stores.
    logs = {}
    for name in ("real_dev", "package_dev", "moved_measure", "benchmark", "real_full_part0", "real_full_part1", "real_masked"):
        p = OUT / (name + ".log")
        logs[p.name] = log_summary(p)
    external = LOCAL / "frozen_mando.log"
    save(OUT / "partial_ir_summary.json", dict(unit=uid, selected_measurements=audit,
         native_log_fingerprints=logs,
         external_development_continuation_log=dict(path=str(LOCAL/"development_continuation/development_native.log"),
             **log_summary(LOCAL/"development_continuation/development_native.log")),
         external_mando_log=dict(path=str(external), **log_summary(external)),
         local_only_log_paths=sorted(logs), review_sha256=sha256(OUT / "partial_ir_review.json"),
         decision_sha256=sha256(OUT / "partial_ir_decision.json"),
         scope="The selected-graph comparison follows the confirmed development unit through each measured population. "
               "A native message counts a diagnostic event. Other events may concern rejected candidates or repeated builds. "
               "These totals are not prevalence estimates for partial graphs. Raw native logs remain local."))
    full = audit["real_full"][0]
    print(uid, "frozen rule", full["policy"], "same graph", full.get("exactly_matches_confirmed_partial_graph"), flush=True)


if __name__ == "__main__":
    main()
