"""Freeze Prompt 6d 'other' samples and validate explicit analyst decisions.

Separate from review_sheet's human edge annotation. Never assigns verdicts.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random

VERSION = "dfg-v2-slither-other-review-v1"
VERDICTS = ("v2_defect", "slither_convention", "comparator_artifact", "unclear")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def _write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf8")


def sample_other(differences, seed=0, limit=30):
    """Independent Random(seed) per sorted task/layer/direction stratum."""
    if type(seed) is not int or type(limit) is not int or limit < 1:
        raise ValueError("Invalid sample configuration")
    groups, seen = defaultdict(list), set()
    for row in differences:
        identity = row["difference_id"]
        if identity in seen:
            raise ValueError("Duplicate difference identity")
        seen.add(identity)
        if row["category"] != "other":
            continue
        if row["layer"] not in ("L1", "L2") or row["direction"] not in ("FP", "FN"):
            raise ValueError("Invalid difference stratum")
        groups[(row["task"], row["layer"], row["direction"])].append(row)
    selected, strata = [], []
    for key, rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda row: row["difference_id"])
        chosen = (random.Random(seed).sample(rows, limit) if len(rows) > limit else rows)
        chosen = sorted(chosen, key=lambda row: row["difference_id"])
        selected.extend(chosen)
        strata.append(dict(task=key[0], layer=key[1], direction=key[2],
                           population=len(rows), selected=len(chosen)))
    return selected, strata


def prepare(alignment, output):
    alignment, output = Path(alignment).resolve(), Path(output)
    if output.exists():
        raise FileExistsError(str(output))
    report = _read(alignment)
    selected, strata = sample_other(report["differences"])
    selection = dict(version=VERSION, alignment=str(alignment),
                     alignment_sha256=sha256(alignment), seed=0, limit=30,
                     sampling="sorted difference_id; independent Random(0) per stratum",
                     strata=strata, selected=selected,
                     verdicts_assigned=False, human_edge_review=False)
    output.mkdir(parents=True)
    _write(output / "selection.json", selection)
    _write(output / "selection.seal.json", dict(
        version=VERSION, selection_sha256=sha256(output / "selection.json"),
        alignment_sha256=selection["alignment_sha256"]))
    return dict(selected=len(selected), strata=strata, output=str(output))


def validate(selection_path, decisions_path):
    selection_path = Path(selection_path).resolve()
    selection = _read(selection_path)
    seal = _read(selection_path.with_name("selection.seal.json"))
    if selection.get("seed") != 0 or selection.get("limit") != 30:
        raise ValueError("Selection configuration differs from frozen protocol")
    if seal.get("version") != VERSION or selection.get("version") != VERSION:
        raise ValueError("Unexpected selection version")
    if sha256(selection_path) != seal["selection_sha256"]:
        raise ValueError("Selection was modified")
    alignment = Path(selection["alignment"])
    if sha256(alignment) != selection["alignment_sha256"] or \
            seal["alignment_sha256"] != selection["alignment_sha256"]:
        raise ValueError("Alignment report was modified")
    expected, strata = sample_other(_read(alignment)["differences"])
    if expected != selection["selected"] or strata != selection["strata"]:
        raise ValueError("Selection is not the fixed seed-0 sample")
    document = _read(decisions_path)
    if document.get("selection_sha256") != seal["selection_sha256"]:
        raise ValueError("Decisions use a different selection")
    by_id = {row["difference_id"]: row for row in selection["selected"]}
    decisions = document["decisions"]
    ids = [row["difference_id"] for row in decisions]
    if len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise ValueError("Decisions must cover every selected event exactly once")
    counts, patterns, source_checked = Counter(), defaultdict(list), {}
    comparator_pending = False
    for decision in decisions:
        row, verdict = by_id[decision["difference_id"]], decision.get("verdict")
        if verdict not in VERDICTS:
            raise ValueError("Unknown analyst verdict")
        if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
            raise ValueError("Every decision needs an explicit reason")
        if not isinstance(decision.get("evidence"), dict) or not decision["evidence"]:
            raise ValueError("Every decision needs inspected evidence")
        source = row["source_path"]
        if source not in source_checked:
            source_checked[source] = sha256(source)
        if source_checked[source] != row["source_sha256"]:
            raise ValueError("Reviewed source was modified")
        comparator_pending = comparator_pending or verdict == "comparator_artifact"
        if verdict == "v2_defect":
            pattern = decision.get("pattern")
            if not isinstance(pattern, str) or not pattern.strip():
                raise ValueError("Analyzer defect needs a syntax pattern identity")
            patterns[pattern].append(row["difference_id"])
        counts[(row["task"], row["layer"], row["direction"], verdict)] += 1
    return dict(version=VERSION, selected=len(ids), reviewed=len(decisions),
                selection_sha256=seal["selection_sha256"],
                decisions_sha256=sha256(decisions_path),
                counts=[dict(task=k[0], layer=k[1], direction=k[2], verdict=k[3], count=n)
                        for k, n in sorted(counts.items())],
                defect_patterns=dict(patterns),
                prompt7_gate=("blocked_v2_defect" if patterns else
                              "pending_comparator_recompute" if comparator_pending else
                              "no_sampled_v2_defect"),
                semantic_verdicts_are_analyst_supplied=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    select = commands.add_parser("prepare")
    select.add_argument("--alignment", required=True)
    select.add_argument("--output", required=True)
    check = commands.add_parser("validate")
    check.add_argument("--selection", required=True)
    check.add_argument("--decisions", required=True)
    args = parser.parse_args(argv)
    result = (prepare(args.alignment, args.output) if args.command == "prepare"
              else validate(args.selection, args.decisions))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
