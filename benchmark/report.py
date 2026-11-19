"""report.md of a benchmark run: the rebuilt pipeline next to the paper's numbers."""
import json
from pathlib import Path

from benchmark import paper

PROTOCOL_TITLES = {
    "paper": "paper protocol (held-out fold selects the checkpoint and is scored, as the authors' trainers)",
    "grouped": "grouped protocol (duplicate-disjoint folds, checkpoint selected on inner validation)",
}


def _n(value, digits=2):
    return "—" if value is None else "%.*f" % (digits, value)


def _sd(summary, key):
    if summary is None or summary.get(key) is None:
        return "—"
    sd = summary.get(key + "_sd")
    return _n(summary[key]) + ("" if sd is None else " ± " + _n(sd))


def _delta(ours, theirs):
    return "—" if ours is None or theirs is None else "%+.2f" % (ours - theirs)


def _table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _get(scored, *path):
    for key in path:
        if scored is None:
            return None
        scored = scored.get(key)
    return scored


def contract_table(by_category):
    rows, ours_b, ours_m, ref_b, ref_m = [], [], [], [], []
    for category in paper.CATEGORIES:
        s = _get(by_category, category, "contract")
        if s is None:
            continue
        pb = paper.value("contract", paper.SAME_TOKENIZER, "buggy_f1", category)
        pm = paper.value("contract", paper.SAME_TOKENIZER, "macro_f1", category)
        best_row, best = paper.best_llm("contract", "buggy_f1", category)
        rows.append([category, s["folds"], _sd(s, "buggy_f1"), _n(pb), _delta(s.get("buggy_f1"), pb),
                     _sd(s, "macro_f1"), _n(pm), _delta(s.get("macro_f1"), pm), "%s (%s)" % (_n(best), best_row)])
        ours_b.append(s.get("buggy_f1")), ours_m.append(s.get("macro_f1")), ref_b.append(pb), ref_m.append(pm)
    if len(rows) > 1:
        rows.append(["**mean**", "", _n(_mean(ours_b)), _n(_mean(ref_b)), _delta(_mean(ours_b), _mean(ref_b)),
                     _n(_mean(ours_m)), _n(_mean(ref_m)), _delta(_mean(ours_m), _mean(ref_m)), ""])
    return _table(["category", "folds", "Buggy-F1", "paper", "Δ", "Macro-F1", "paper", "Δ",
                   "paper best LLM row"], rows)


def line_table(by_category):
    rows, ours, ref, src = [], [], [], []
    for category in paper.CATEGORIES:
        nodes, source = _get(by_category, category, "line_nodes"), _get(by_category, category, "line_source")
        if nodes is None:
            continue
        pb = paper.value("line", paper.SAME_TOKENIZER, "buggy_f1", category)
        best_row, best = paper.best_llm("line", "buggy_f1", category)
        rows.append([category, nodes["folds"], _sd(nodes, "buggy_f1"), _n(pb), _delta(nodes.get("buggy_f1"), pb),
                     "%s (%s)" % (_n(best), best_row), _sd(source, "buggy_f1"), _n(_get(source, "precision")),
                     _n(_get(source, "recall")), _n(_get(source, "coverage"), 1), _n(_get(source, "hit_rate"), 1)])
        ours.append(nodes.get("buggy_f1")), ref.append(pb), src.append(_get(source, "buggy_f1"))
    if len(rows) > 1:
        rows.append(["**mean**", "", _n(_mean(ours)), _n(_mean(ref)), _delta(_mean(ours), _mean(ref)), "",
                     _n(_mean(src)), "", "", "", ""])
    return _table(["category", "folds", "node Buggy-F1", "paper", "Δ", "paper best LLM row",
                   "source-line Buggy-F1", "P", "R", "line coverage %", "contracts hit %"], rows)


def cascade_table(by_category):
    rows = []
    for category in paper.CATEGORIES:
        c = _get(by_category, category, "cascade")
        if c is None:
            continue
        contract = _get(by_category, category, "contract")
        rows.append([category, len(c["folds"]), _n(_get(contract, "buggy_f1")),
                     _sd(c["gated"]["lines"], "buggy_f1"), _n(c["gated"]["lines"].get("precision")),
                     _n(c["gated"]["lines"].get("recall")), _n(c["oracle"]["lines"].get("buggy_f1")),
                     _n(c["ungated"]["lines"].get("buggy_f1")), _n(c["gated"]["nodes"].get("buggy_f1")),
                     _n(c["gated"]["lines"].get("hit_rate"), 1)])
    return _table(["category", "folds", "contract Buggy-F1", "line Buggy-F1 (detector)", "P", "R",
                   "line, true contract gate", "line, no gate", "node Buggy-F1 (detector)",
                   "vulnerable contracts hit %"], rows)


def upstream_table(upstream):
    rows = []
    for category in paper.CATEGORIES:
        levels = upstream.get(category)
        if not levels:
            continue
        c, l = levels.get("contract"), levels.get("line")
        rows.append([category, _sd(c, "buggy_f1"), _n(paper.value("contract", paper.SAME_TOKENIZER, "buggy_f1", category)),
                     _sd(c, "macro_f1"), _sd(l, "buggy_f1"),
                     _n(paper.value("line", paper.SAME_TOKENIZER, "buggy_f1", category))])
    return _table(["category", "contract Buggy-F1", "paper", "contract Macro-F1", "line (node) Buggy-F1", "paper"], rows)


def render(evaluation, run):
    out = ["# Benchmark: rebuilt MANDO-LLM pipeline vs. the paper", "",
           "Reference: %s, row `%s` (the tokenizer the pipeline uses); `paper best LLM row` is the best of "
           "the paper's three tokenizer rows. Scores are fold means (± SD) of the best checkpoint in percent; "
           "Δ = ours − paper." % (paper.SOURCE, paper.SAME_TOKENIZER), "",
           "Run settings: `%s`" % json.dumps(run.get("settings", {}), sort_keys=True),
           "Code commit: `%s`" % run.get("commit"), ""]
    for protocol in ("paper", "grouped"):
        for profile, by_category in sorted(evaluation["protocols"].get(protocol, {}).items()):
            out += ["## %s — %s" % (profile, PROTOCOL_TITLES[protocol]), "",
                    "### Contract level (paper Table 3)", ""] + contract_table(by_category)
            out += ["", "### Line level (paper Table 5: node scores on vulnerable contracts; "
                    "plus the same predictions on source lines)", ""] + line_table(by_category)
            out += ["", "### End to end: contract model → line model on every held-out contract", "",
                    "`detector`: lines of contracts the contract model flags; `true contract gate`: the "
                    "line model on the truly vulnerable contracts only; `no gate`: the line model alone.",
                    ""] + cascade_table(by_category) + [""]
    if evaluation.get("upstream"):
        out += ["## The authors' trainers on the rebuilt graphs (paper protocol)", ""]
        out += upstream_table(evaluation["upstream"]) + [""]
    out += ["Source lines are preprocessed lines spoken for by node label endpoints "
            "(`benchmark/lines.py`); `line coverage` is the share of annotated lines any node speaks "
            "for, `contracts hit` the share of vulnerable contracts with at least one annotated "
            "line flagged. Per-contract detector output: `findings/<protocol>/<profile>/<category>.json`."]
    return "\n".join(out) + "\n"


def write(run_dir, evaluation):
    run_dir = Path(run_dir)
    run = json.loads((run_dir / "run.json").read_text()) if (run_dir / "run.json").is_file() else {}
    text = render(evaluation, run)
    (run_dir / "report.md").write_text(text)
    return text
