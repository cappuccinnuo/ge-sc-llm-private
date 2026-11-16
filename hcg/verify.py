"""Compare a built graph with a reference graph (the authors' released one).

The two graphs list contracts in different orders, so nodes are aligned contract by
contract, in node order within each contract. Everything except labels must then be
identical: node attributes, edge endpoints, edge attributes and multiplicities.
Node labels are compared separately and reported as differences, because the
public-annotation policy is expected to differ from the authors' snapshot.
"""
import ast
from collections import Counter, defaultdict

LABEL = "node_info_vulnerabilities"
IGNORED = {LABEL, "token"}


def _by_file(graph):
    files = defaultdict(list)
    for node, data in graph.nodes(data=True):
        files[data["source_file"]].append(node)
    return files


def is_positive(value):
    if value is None:
        return False
    if isinstance(value, str):
        value = ast.literal_eval(value.strip('"'))
    return bool(value)


def compare(built, reference):
    """Report dict; report['structure_identical'] is the pass/fail of the structure."""
    ours, theirs = _by_file(built), _by_file(reference)
    report = {"files_equal": set(ours) == set(theirs), "attribute_mismatches": {},
              "edge_mismatches": 0, "label_differences": [], "positives": {}}
    if not report["files_equal"]:
        report["missing_files"] = sorted(set(theirs) - set(ours))
        report["extra_files"] = sorted(set(ours) - set(theirs))
        report["structure_identical"] = False
        return report
    mapping, mismatches = {}, Counter()
    for name in sorted(theirs):
        if len(ours[name]) != len(theirs[name]):
            mismatches["node_count:" + name] += 1
            continue
        for index, (a, b) in enumerate(zip(ours[name], theirs[name])):
            mapping[a] = b
            da, db = built.nodes[a], reference.nodes[b]
            for key in (set(da) | set(db)) - IGNORED:
                if da.get(key) != db.get(key):
                    mismatches[key] += 1
            pa, pb = is_positive(da.get(LABEL)), is_positive(db.get(LABEL))
            if pa != pb:
                report["label_differences"].append(
                    {"source_file": name, "index_in_file": index,
                     "node_type": da["node_type"], "built": int(pa), "reference": int(pb)})
    report["attribute_mismatches"] = dict(mismatches)
    if len(mapping) == built.number_of_nodes() == reference.number_of_nodes():
        edges_ours = Counter((mapping[u], mapping[v], tuple(sorted(d.items())))
                             for u, v, d in built.edges(data=True))
        edges_theirs = Counter((u, v, tuple(sorted(d.items())))
                               for u, v, d in reference.edges(data=True))
        report["edge_mismatches"] = sum(((edges_ours - edges_theirs) +
                                         (edges_theirs - edges_ours)).values())
    else:
        report["edge_mismatches"] = None
    report["positives"] = {
        "built": sum(is_positive(d.get(LABEL)) for _, d in built.nodes(data=True)),
        "reference": sum(is_positive(d.get(LABEL)) for _, d in reference.nodes(data=True)),
    }
    report["structure_identical"] = (not mismatches and report["edge_mismatches"] == 0
                                     and built.graph == reference.graph)
    return report


def compare_contract_labels(entries, reference_entries):
    ours = {e["contract_name"]: e["targets"] for e in entries}
    theirs = {e["contract_name"]: e["targets"] for e in reference_entries}
    return sorted(name for name in set(ours) | set(theirs) if ours.get(name) != theirs.get(name))
