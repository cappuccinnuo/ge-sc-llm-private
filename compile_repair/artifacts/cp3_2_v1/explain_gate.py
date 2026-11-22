"""Explain a failed CP3.2 gate using only existing input and tool receipts."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from input_census import BASE, INVENTORY, digest, frozen, solidity_snippet_evidence
from compile_repair.toolchain.solc import lexical_tokens


def verify(path, expected):
    raw = Path(path).read_bytes()
    if digest(raw) != expected:
        raise ValueError("Receipt SHA256 mismatch: " + str(path))
    return raw


def explain(census, out):
    gate = json.loads(census.read_bytes())
    assert gate["documentation_gate_passed"] is False
    units = {r["unit_id"]: r for r in (json.loads(s) for s in frozen(INVENTORY).splitlines())}
    cases = []
    for r in gate["success_conflicts"]:
        uid, sha = r["unit_id"], r["entry_sha256"]
        raw = verify(units[uid]["path"], sha)
        tokens = list(lexical_tokens(raw))
        source_kind = "empty" if not raw else "whitespace" if not raw.strip() else "comments_only"
        if tokens:
            assert tokens[0][3] == b"struct" and tokens[-1][3] == b"}"
            source_kind = "file_scope_struct"
        ref = r["prior_result"]
        record_path = Path(ref["result_path"])
        record = json.loads(verify(record_path, ref["result_sha256"]))
        attempted = record["attempts"][-1]
        slither = attempted["slither"]
        graph = json.loads(verify(record_path.with_name("graph.json"), slither["graph_sha256"]))
        assert (record["unit_id"], record["inputs"][0]["sha256"], record["status"]) == (uid, sha, "success")
        assert attempted["solc"]["returncode"] == 0 and slither["d3"] and slither["d3_a"] and slither["d3_b"]
        cases.append(dict(unit_id=uid, corpus=r["corpus"], entry_sha256=sha, bytes=len(raw),
                          source_shape=source_kind, noncomment_tokens=len(tokens),
                          selected_version=record["selected_version"], prior_result=ref,
                          solc_returncode=attempted["solc"]["returncode"], d3=slither["d3"],
                          d3_a=slither["d3_a"], d3_b=slither["d3_b"], graph_sha256=slither["graph_sha256"],
                          graph_counts={k:len(graph[k]) for k in ("nodes","declarations","cfg_edges","calls")}))
    affected = defaultdict(Counter)
    for row in gate["newly_excluded"]:
        label = "+".join(row["prior_primary"]) or "success"
        affected[row["corpus"]][label] += 1
    old_excluded = [r for r in units.values() if r["corpus"] == "SOChecker" and not r["language_evidence"]["is_solidity"]]
    first_words = Counter()
    empty_snippets = []
    for r in old_excluded:
        raw = verify(r["path"], r["entry_sha256"])
        first = next(lexical_tokens(raw), None)
        if first:
            word = first[3].decode() if first[3] in (b"struct", b"enum", b"error", b"import") else "other"
            first_words[word] += 1
        else:
            first_words["no_tokens"] += 1
            empty_snippets.append(dict(unit_id=r["unit_id"], bytes=len(raw), sha256=r["entry_sha256"],
                                       whitespace_only=not raw.strip()))
    handwritten = {k:solidity_snippet_evidence(raw) for k,raw in (
        ("struct", b"struct Pair { uint256 a; uint256 b; }"), ("enum", b"enum Color { Red, Blue }"),
        ("error", b"error InvalidAmount(uint256 amount);"))}
    decision = dict(base_commit=BASE, status="blocked_first_acceptance_gate",
                    gate_source_sha256=digest(census.read_bytes()), expected_success_positive=21223,
                    observed_success_positive=21223-len(cases), eight_verified_receipts=cases,
                    newly_flagged_by_prior_primary=affected, old_excluded_first_tokens=first_words,
                    old_excluded_without_tokens=empty_snippets, handwritten_unmodified_rule=handwritten,
                    proposed_policy="Reject explicit non-Solidity JSON language or positive foreign-language syntax. "
                                    "Treat other inputs without decisive language evidence as unknown and continue normal processing. "
                                    "Preserve positive-evidence and unknown counts separately.",
                    proposed_comparison="Retain the frozen 236 as historical exclusions. In a revised analysis distinguish "
                                        "admitted units with no historical compiler observation from measured successes and failures. "
                                        "No compilation or denominator imputation for those units without a separately agreed evaluation.",
                    invariants="One content-based production policy, no corpus/filename/SHA exceptions, preserve all eight D3 successes.",
                    approval="requested, not implemented", solc_invocations=0, slither_invocations=0)
    with out.open("x") as stream:
        json.dump(decision, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("verified", len(cases), "source shapes", dict(Counter(x["source_shape"] for x in cases)),
          "old exclusions without tokens", len(empty_snippets))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    base = Path(__file__).resolve().parent
    parser.add_argument("--census", type=Path, default=base/"input_gate.json")
    parser.add_argument("--out", type=Path, default=base/"decision_request.json")
    args = parser.parse_args()
    explain(args.census, args.out)
