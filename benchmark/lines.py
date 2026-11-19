"""Source-line view of node predictions.

The paper's "line-level" score is a node score: every statement node of a vulnerable
contract is classified. This module scores the same predictions on source lines,
the unit an auditor reads, with the rule that labelled the nodes
(``hcg.labels.projection``, author-endpoints policy):

* the lines a node speaks for are its label endpoints, the first and last
  preprocessed line of each span (``hcg.cfg.author_schema.label_endpoints``);
  synthetic markers (line 0) and auxiliary DFG nodes speak for no line;
* a line is predicted vulnerable when a node predicted vulnerable speaks for it;
* a line is vulnerable when a target-category annotation of its file covers it
  (``annotations.json``, preprocessed lines). Annotated lines no node speaks for can
  never be predicted; they count as misses and are reported as lost coverage.

All lines are preprocessed lines; ``original_lines`` maps them back to the file.
"""
from dfg.schema import AUX_NODE_TYPES
from hcg.cfg.author_schema import label_endpoints
from hcg.sources.annotations import preprocess_with_map


def truth_lines(annotations):
    """{file: set of annotated preprocessed lines} from an hcg ``annotations.json``."""
    return {name: {line for record in records for line in record["lines"]}
            for name, records in annotations["preprocessed"].items()}


def node_lines(graph):
    """{node: (file, lines it speaks for)} for every non-auxiliary node of a task graph."""
    return {node: (data["source_file"],
                   tuple(x for x in label_endpoints(data["node_source_code_lines"]) if x >= 1))
            for node, data in graph.nodes(data=True) if data["node_type"] not in AUX_NODE_TYPES}


def project(rows, lines_of, key="best"):
    """Node prediction rows -> ({file: predicted lines}, {file: addressable lines})."""
    predicted, addressable = {}, {}
    for row in rows:
        name, lines = lines_of[row["node"]]
        if name != row["file"]:
            raise ValueError("prediction of node %s names %s, the graph %s" % (row["node"], row["file"], name))
        addressable.setdefault(row["file"], set()).update(lines)
        predicted.setdefault(row["file"], set())
        if row[key] == 1:
            predicted[row["file"]].update(lines)
    return predicted, addressable


def counts(files, truth, predicted, addressable):
    """Line confusion counts over ``files`` (every file's addressable and annotated lines)."""
    c = dict(tp=0, fp=0, fn=0, tn=0, truth_lines=0, addressable_truth_lines=0,
             vulnerable_files=0, hit_files=0)
    for name in files:
        t, p = truth.get(name, set()), predicted.get(name, set())
        universe = addressable.get(name, set()) | t
        c["tp"] += len(p & t)
        c["fp"] += len(p - t)
        c["fn"] += len(t - p)
        c["tn"] += len(universe - (p | t))
        c["truth_lines"] += len(t)
        c["addressable_truth_lines"] += len(t & addressable.get(name, set()))
        if t:
            c["vulnerable_files"] += 1
            c["hit_files"] += bool(p & t)
    return c


def _f1(tp, fp, fn):
    return 200.0 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0


def scores(c):
    """Percent scores from ``counts``; same keys as ``dfg.utils.metrics`` plus coverage."""
    tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]
    buggy, clean = _f1(tp, fp, fn), _f1(tn, fn, fp)
    return {"n": tp + fp + fn + tn, "positive": tp + fn,
            "buggy_f1": buggy, "macro_f1": (buggy + clean) / 2,
            "precision": 100.0 * tp / (tp + fp) if tp + fp else 0.0,
            "recall": 100.0 * tp / (tp + fn) if tp + fn else 0.0,
            "tn_fp_fn_tp": [tn, fp, fn, tp],
            "coverage": (100.0 * c["addressable_truth_lines"] / c["truth_lines"]
                         if c["truth_lines"] else None),
            "hit_rate": (100.0 * c["hit_files"] / c["vulnerable_files"]
                         if c["vulnerable_files"] else None)}


def original_lines(source):
    """{preprocessed line: [original lines]} of one source file."""
    _, line_map = preprocess_with_map(source)
    return {i + 1: list(origin) for i, origin in enumerate(line_map)}


def to_original(lines, mapping):
    return sorted({o for line in lines for o in mapping.get(line, ())})
