"""Scores of a benchmark run, computed from the files the fits wrote.

Per protocol, category and profile (best checkpoint, outer-test set, fold means as
in the paper):

* ``contract``     contract scores (paper Table 3);
* ``line_nodes``   node scores of the line track (paper Table 5);
* ``line_source``  the same predictions on source lines (``benchmark.lines``);
* ``cascade``      the two-phase detector on every held-out contract: the cascade line
                   model's nodes gated by the contract model of the same fold
                   (``gated``), by the true contract label (``oracle``) or not at all
                   (``ungated``), each as node and source-line scores;
* ``by_source``    the same three views on the contracts of one source (SolidiFI,
                   SmartBugs-curated, DAppSCAN), each against all clean contracts,
                   pooled over folds (every contract is held out once): shows how
                   much of a score comes from SolidiFI's injected templates;
* ``findings``     the detector's final output per contract (pooled over folds; each
                   contract is held out once): contract verdict and flagged lines,
                   with the annotated lines, in original line numbers.

``upstream`` carries the authors' trainers' fold scores (``benchmark.upstream``).
"""
import json
import statistics
from pathlib import Path

from benchmark import lines
from dfg.utils import metrics
from hcg.datasets.registry import SOLIDIFI_FILE, get_dataset
from hcg.sources import composition
from hcg.store.io import read_gpickle

REPO = Path(__file__).resolve().parents[1]
SUMMARY_KEYS = ("buggy_f1", "macro_f1", "precision", "recall", "coverage", "hit_rate")
GATES = ("gated", "oracle", "ungated")
CLEAN = "clean"


def summarize(fold_scores):
    """Fold mean and sample SD of every summary metric, plus the fold list."""
    out = {"folds": len(fold_scores)}
    for key in SUMMARY_KEYS:
        values = [s[key] for s in fold_scores if s.get(key) is not None]
        if values:
            out[key] = statistics.mean(values)
            out[key + "_sd"] = statistics.stdev(values) if len(values) > 1 else None
    return out


def fold_outputs(task_dir, profile):
    """{fold: (result, predictions)} of the finished fits of one profile."""
    out = {}
    for path in sorted(Path(task_dir).glob("fold_*/%s/result.json" % profile)):
        result = json.loads(path.read_text())
        out[result["fold"]] = (result, json.loads((path.parent / "predictions.json").read_text()))
    return out


def profiles_in(protocol_dir):
    return sorted({p.parent.name for p in Path(protocol_dir).glob("*/fold_*/*/result.json")})


class CategoryRefs:
    """What scoring needs of one category: node lines, annotated lines, line maps."""

    def __init__(self, hcg_root, dataset, category):
        directory = Path(hcg_root) / dataset / category
        self.category = category
        self.file_labels = {r["contract_name"]: int(r["targets"]) for r in
                            json.loads((directory / "graph_labels.json").read_text())}
        self.truth = lines.truth_lines(json.loads((directory / "annotations.json").read_text()))
        self.node_lines = {"contract": lines.node_lines(read_gpickle(directory / "contract_level.gpickle")),
                           "line": lines.node_lines(read_gpickle(directory / "line_level.gpickle"))}
        spec = get_dataset(dataset)
        self._corpus = spec.corpus(REPO, category)
        self._maps = {}
        self.source = self._sources(spec, category)

    def _sources(self, spec, category):
        """{file: source}; clean contracts are CLEAN whatever pool they come from."""
        if spec.composition:
            rows = composition.entries(composition.load(REPO / spec.composition), category)
            named = {r["name"]: r["source"] for r in rows}
        else:
            named = {f: "SolidiFI" if SOLIDIFI_FILE.fullmatch(f) else "SmartBugs-curated"
                     for f in self.file_labels}
        return {f: (named[f] if self.file_labels[f] else CLEAN) for f in self.file_labels}

    def sources(self):
        return sorted({s for s in self.source.values() if s != CLEAN})

    def original(self, name):
        if name not in self._maps:
            self._maps[name] = lines.original_lines((self._corpus / name).read_bytes().decode("utf8"))
        return self._maps[name]


def source_scores(rows, refs, graph, files, key="best"):
    predicted, addressable = lines.project(rows, refs.node_lines[graph], key)
    return lines.scores(lines.counts(files, refs.truth, predicted, addressable))


def _gate(rows, verdict):
    return [dict(r, best=r["best"] if verdict[r["file"]] else 0) for r in rows]


def cascade_fold(contract_rows, node_rows, refs):
    """Node and source-line scores of the three gates on one held-out fold."""
    files = sorted(r["file"] for r in contract_rows)
    if sorted({r["file"] for r in node_rows}) != files:
        raise ValueError("%s: cascade and contract folds hold out different contracts" % refs.category)
    verdicts = {"gated": {r["file"]: r["best"] for r in contract_rows},
                "oracle": {f: refs.file_labels[f] for f in files},
                "ungated": {f: 1 for f in files}}
    out = {}
    for gate in GATES:
        rows = _gate(node_rows, verdicts[gate])
        out[gate] = dict(nodes=metrics([r["target"] for r in rows], [r["best"] for r in rows]),
                         lines=source_scores(rows, refs, "contract", files))
    return out


def findings(contract_rows, node_rows, refs, fold):
    """The detector's output for each held-out contract of one fold."""
    flagged = {}
    for row in _gate(node_rows, {r["file"]: r["best"] for r in contract_rows}):
        if row["best"]:
            flagged.setdefault(row["file"], set()).update(refs.node_lines["contract"][row["node"]][1])
    out = []
    for row in sorted(contract_rows, key=lambda r: r["file"]):
        mapping = refs.original(row["file"])
        out.append(dict(file=row["file"], fold=fold, vulnerable=refs.file_labels[row["file"]],
                        predicted=row["best"], probability=round(row["best_probability"], 4),
                        flagged_lines=lines.to_original(flagged.get(row["file"], ()), mapping),
                        annotated_lines=lines.to_original(refs.truth.get(row["file"], ()), mapping)))
    return out


def _keep(rows, refs, source, with_clean):
    return [r for r in rows if refs.source[r["file"]] == source or (with_clean and refs.source[r["file"]] == CLEAN)]


def by_source(tasks, refs):
    """Pooled out-of-fold scores of each vulnerable source (see the module docstring)."""
    contract = [r for _, p in tasks["contract"].values() for r in p["outer_test"]]
    line = [r for _, p in tasks["line"].values() for r in p["outer_test"]]
    paired = sorted(set(tasks["contract"]) & set(tasks["cascade"]))
    out = {}
    for source in refs.sources():
        part = {}
        if contract:
            rows = _keep(contract, refs, source, True)
            part["contract"] = metrics([r["target"] for r in rows], [r["best"] for r in rows])
        if line:
            rows = _keep(line, refs, source, False)
            part["line_nodes"] = metrics([r["target"] for r in rows], [r["best"] for r in rows])
            part["line_source"] = source_scores(rows, refs, "line", sorted({r["file"] for r in rows}))
        if paired:
            verdict = {r["file"]: r["best"] for k in paired for r in tasks["contract"][k][1]["outer_test"]}
            rows = _gate(_keep([r for k in paired for r in tasks["cascade"][k][1]["outer_test"]], refs, source, True),
                         verdict)
            part["detector_lines"] = source_scores(rows, refs, "contract", sorted({r["file"] for r in rows}))
        out[source] = part
    return out


def evaluate_category(protocol_dir, refs, profile):
    """Scores (and findings) of one category, protocol and profile; None if nothing ran."""
    tasks = {name: fold_outputs(Path(protocol_dir) / ("%s_%s" % (refs.category, name)), profile)
             for name in ("contract", "line", "cascade")}
    if not any(tasks.values()):
        return None
    out = {}
    if tasks["contract"]:
        out["contract"] = summarize([r["outer_test"]["best"] for r, _ in tasks["contract"].values()])
    if tasks["line"]:
        out["line_nodes"] = summarize([r["outer_test"]["best"] for r, _ in tasks["line"].values()])
        out["line_source"] = summarize([
            source_scores(p["outer_test"], refs, "line", sorted({x["file"] for x in p["outer_test"]}))
            for _, p in tasks["line"].values()])
    paired = sorted(set(tasks["contract"]) & set(tasks["cascade"]))
    if paired:
        per_fold = [cascade_fold(tasks["contract"][k][1]["outer_test"], tasks["cascade"][k][1]["outer_test"], refs)
                    for k in paired]
        out["cascade"] = {gate: dict(nodes=summarize([f[gate]["nodes"] for f in per_fold]),
                                     lines=summarize([f[gate]["lines"] for f in per_fold]))
                          for gate in GATES}
        out["cascade"]["folds"] = paired
        out["findings"] = [row for k in paired for row in findings(
            tasks["contract"][k][1]["outer_test"], tasks["cascade"][k][1]["outer_test"], refs, k)]
    out["by_source"] = by_source(tasks, refs)
    out["folds"] = {name: sorted(done) for name, done in tasks.items()}
    return out


def evaluate(run_dir, hcg_root, dataset, categories):
    """evaluation.json and findings/<protocol>/<profile>/<category>.json of a run."""
    run_dir = Path(run_dir)
    result = {"dataset": dataset, "protocols": {}, "upstream": {}}
    for category in categories:
        if not any(run_dir.glob("*/%s_*" % category)):
            continue
        refs = CategoryRefs(hcg_root, dataset, category)
        for protocol_dir in sorted(p for p in run_dir.iterdir() if p.is_dir() and p.name in ("paper", "grouped")):
            for profile in profiles_in(protocol_dir):
                scored = evaluate_category(protocol_dir, refs, profile)
                if scored is None:
                    continue
                found = scored.pop("findings", None)
                if found is not None:
                    path = run_dir / "findings" / protocol_dir.name / profile / (category + ".json")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(found, indent=1) + "\n")
                result["protocols"].setdefault(protocol_dir.name, {}).setdefault(profile, {})[category] = scored
        for level in ("contract", "line"):
            done = run_dir / "upstream" / ("%s_%s" % (category, level)) / "result.json"
            if done.is_file():
                record = json.loads(done.read_text())
                result["upstream"].setdefault(category, {})[level] = summarize(
                    [dict(buggy_f1=f["buggy_f1"], macro_f1=f["macro_f1"]) for f in record["folds"]])
    (run_dir / "evaluation.json").write_text(json.dumps(result, indent=1) + "\n")
    return result
