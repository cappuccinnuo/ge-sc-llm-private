"""Node labels: the pipeline's public-annotation labels against the authors' released ones.

``audit`` explains the line-level gap to the paper without training. Per category it
aligns the rebuilt line-level graph with the authors' (``data/upstream_mando_llm/
node_detection``) node by node, by (source file, node label: AST id, type, lines), and
reports:

* where the labels differ, by file, and whether that file's SolidiFI BugLog has
  overlapping intervals (the authors' line conversion fails there: the injected bugs
  of those files are unlabelled in their graphs);
* ``ceiling``: Buggy-F1 of the public labels scored against the authors' labels, i.e.
  what a model that learned the public labels perfectly would score in the paper's
  evaluation;
* ``lookup``: Buggy-F1 of a model-free baseline under the paper's 10 folds: a node is
  predicted vulnerable when its (node type, code) was mostly vulnerable in the
  training folds. Under either set of labels it is close to the HGT.

``transplant`` puts the authors' labels on a rebuilt graph (matched nodes only; nodes
the authors' graph does not have keep theirs), so ``benchmark run --labels author``
trains the same pipeline on the authors' labels: the controlled test of the cause.
"""
import collections
import csv
import json
import re
from pathlib import Path

from benchmark import folds, paper
from hcg import verify
from hcg.datasets import DATASET_A
from hcg.store.io import read_gpickle

REPO = Path(__file__).resolve().parents[1]
AUTHOR_GRAPHS = {
    "contract": "data/upstream_mando_llm/graph_detection/{category}_tree_sitter_cfg_cg_compressed_graphs.gpickle",
    "node": "data/upstream_mando_llm/node_detection/{category}_tree_sitter_cfg_compressed_graphs.gpickle",
}
SOLIDIFI_FILE = re.compile(r"buggy_(\d+)\.sol")


def _key(data):
    return data["source_file"], data["label"]


def _positive(data):
    return int(verify.is_positive(data.get(verify.LABEL)))


def author_graph(category, task):
    path = REPO / AUTHOR_GRAPHS[task].format(category=category)
    if not path.is_file():
        raise SystemExit("authors' graph missing: %s" % path)
    return read_gpickle(path)


def transplant(graph, reference):
    """A copy of ``graph`` carrying ``reference``'s node labels where nodes match."""
    labels = {_key(d): d.get(verify.LABEL) for _, d in reference.nodes(data=True)}
    out = graph.copy()
    stats = collections.Counter()
    for _, data in out.nodes(data=True):
        key = (data.get("source_file"), data.get("label"))
        if key not in labels:
            stats["unmatched"] += 1
            continue
        stats["matched"] += 1
        stats["changed"] += _positive(data) != int(verify.is_positive(labels[key]))
        data[verify.LABEL] = labels[key]
    return out, dict(stats)


def overlapping_buglogs(label_root, solidifi_dir):
    """SolidiFI file numbers whose BugLog has overlapping intervals."""
    found = set()
    for path in (Path(label_root) / "SolidiFI-benchmark/buggy_contracts" / solidifi_dir).glob("BugLog_*.csv"):
        with open(path, newline="", encoding="utf-8-sig") as stream:
            spans = sorted((int(r["loc"]), int(r["loc"]) + int(r["length"]) - 1) for r in csv.DictReader(stream)
                           if r["loc"].strip().isdigit() and r["length"].strip().isdigit())
        if any(b[0] <= a[1] for a, b in zip(spans, spans[1:])):
            found.add(int(re.search(r"(\d+)", path.name).group(1)))
    return found


def _f1(pairs):
    tp = sum(1 for y, p in pairs if y and p)
    fp = sum(1 for y, p in pairs if p and not y)
    fn = sum(1 for y, p in pairs if y and not p)
    return 200.0 * tp / (2 * tp + fp + fn) if tp else 0.0


def lookup(nodes):
    """Fold-mean Buggy-F1 of the (type, code) majority-label lookup; nodes: (file, type, code, y)."""
    plan = folds.paper_line("lookup", sorted({n[0] for n in nodes}))
    scores = []
    for split in plan["folds"]:
        train, test = set(split["inner_train_files"]), set(split["outer_test_files"])
        votes = collections.defaultdict(lambda: [0, 0])
        for name, kind, code, y in nodes:
            if name in train:
                votes[(kind, code)][y] += 1
        scores.append(_f1([(y, int(votes[(k, c)][1] > votes[(k, c)][0])) for n, k, c, y in nodes if n in test]))
    return sum(scores) / len(scores)


def audit_category(hcg_root, category, label_root):
    ours = read_gpickle(Path(hcg_root) / "A" / category / "line_level.gpickle")
    theirs = author_graph(category, "node")
    a = {_key(d): d for _, d in theirs.nodes(data=True)}
    o = {_key(d): d for _, d in ours.nodes(data=True)}
    common = sorted(a.keys() & o.keys())
    differing = [k for k in common if _positive(a[k]) != _positive(o[k])]
    by_file = collections.Counter(k[0] for k in differing)
    overlaps = overlapping_buglogs(label_root, DATASET_A.category(category).solidifi_dir)
    in_overlap = {f: n for f, n in by_file.items()
                  if SOLIDIFI_FILE.fullmatch(f) and int(SOLIDIFI_FILE.fullmatch(f).group(1)) in overlaps}
    rows = lambda graph: [(d["source_file"], d["node_type"], d["code"], _positive(d)) for _, d in graph.nodes(data=True)]  # noqa: E731
    return dict(
        nodes=dict(authors=len(a), ours=len(o), common=len(common)),
        positives=dict(authors=sum(map(_positive, a.values())), ours=sum(map(_positive, o.values()))),
        differing_nodes=len(differing),
        positive_only_ours=sum(1 for k in differing if _positive(o[k])),
        positive_only_authors=sum(1 for k in differing if _positive(a[k])),
        files=dict(by_file.most_common()),
        in_overlapping_buglog_files=sum(in_overlap.values()),
        corpus_files_with_overlapping_buglog=sorted(
            f for f in {d["source_file"] for d in o.values()}
            if SOLIDIFI_FILE.fullmatch(f) and int(SOLIDIFI_FILE.fullmatch(f).group(1)) in overlaps),
        ceiling=_f1([(_positive(a[k]), _positive(o[k])) for k in common]),
        lookup_authors=lookup(rows(theirs)), lookup_ours=lookup(rows(ours)),
        paper=paper.value("A", "line", paper.SAME_TOKENIZER, "buggy_f1", category))


def render(result):
    out = ["# Node-label audit: public-annotation labels vs the authors' (Dataset A, line level)", "",
           "Nodes aligned by (file, label). `ceiling`: the public labels scored as predictions against the "
           "authors' labels. `lookup`: model-free (type, code) majority lookup under the paper's 10 folds. "
           "`paper`: Table 5, codet5p-770m.", "",
           "| category | differing nodes | of them in SolidiFI files with overlapping BugLog intervals | files | "
           "ceiling | lookup, authors' labels | lookup, public labels | paper |", "|---|---|---|---|---|---|---|---|"]
    for category, r in result.items():
        files = ", ".join("%s (%d)" % kv for kv in r["files"].items()) or "—"
        out.append("| %s | %d | %d | %s | %.2f | %.2f | %.2f | %.2f |" % (
            category, r["differing_nodes"], r["in_overlapping_buglog_files"], files, r["ceiling"],
            r["lookup_authors"], r["lookup_ours"], r["paper"]))
    return "\n".join(out) + "\n"


def run(hcg_root, label_root, out_dir, categories, log=print):
    result = {}
    for category in categories:
        result[category] = audit_category(hcg_root, category, label_root)
        log("[audit] %s: %d differing nodes, ceiling %.2f" % (category, result[category]["differing_nodes"],
                                                             result[category]["ceiling"]))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "label_audit.json").write_text(json.dumps(result, indent=1) + "\n")
    text = render(result)
    (out_dir / "label_audit.md").write_text(text)
    return text
