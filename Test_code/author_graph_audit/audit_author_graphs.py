"""Read-only audit of the authors' published graphs for all seven Dataset A bug types.

Answers two questions without touching any training input:
  1. What are the contract-level and line-level input graphs, and how do they relate?
  2. Does the four-step labelling rule recovered from reentrancy/access_control
     (annotation lines -> preprocessed coordinates -> node endpoints -> intersect)
     hold on every published graph?

Run inside the mando env from the repo root:
    python -B Test_code/author_graph_audit/audit_author_graphs.py
Writes Test_code/author_graph_audit/audit_result.json and prints a summary.
"""
import ast
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pickle5

REPO = Path(__file__).resolve().parents[2]
HGT = REPO.parent / "ge-sc-transformer"
UP = REPO / "data/upstream_mando_llm"
SOLIDIFI = REPO / "data/SolidiFI-benchmark/buggy_contracts"
sys.path.insert(0, str(REPO / "scripts"))
from line_mapping import build_line_map  # noqa: E402

# Paper Table 1: total/buggy contracts, nodes, edges, buggy nodes.
PAPER = {
    "access_control": (114, 57, 13432, 15538, 2977),
    "arithmetic": (120, 60, 16157, 17591, 5395),
    "denial_of_service": (92, 46, 12909, 14366, 4106),
    "front_running": (88, 44, 19415, 22278, 10400),
    "reentrancy": (142, 71, 18312, 19267, 6570),
    "time_manipulation": (100, 50, 15699, 18564, 5800),
    "unchecked_low_level_calls": (190, 95, 17525, 20952, 2352),
}
CALL_EDGES = {"internal_call", "external_call", "recursive_method_call"}


def lit(value):
    for _ in range(3):
        if not isinstance(value, str):
            break
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            break
    return value


def load(path):
    with open(path, "rb") as handle:
        return pickle5.load(handle)


def records(data):
    value = lit(data.get("node_info_vulnerabilities"))
    return value if isinstance(value, list) else []


def stats(graph):
    files = {d["source_file"] for _, d in graph.nodes(data=True)}
    buggy_files = {d["source_file"] for _, d in graph.nodes(data=True) if records(d)}
    return {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "files": len(files),
        "buggy_files": len(buggy_files),
        "positive_nodes": sum(bool(records(d)) for _, d in graph.nodes(data=True)),
        "node_types": dict(Counter(d["node_type"] for _, d in graph.nodes(data=True))),
        "edge_types": dict(Counter(d.get("edge_type") for _, _, d in graph.edges(data=True))),
    }


def embedded_annotations(graph):
    ann = defaultdict(set)
    cats = Counter()
    for _, d in graph.nodes(data=True):
        for record in records(d):
            ann[d["source_file"]].update(record["lines"])
            cats[record["category"]] += 1
    return ann, cats


def rule_replay(graph, ann):
    """Count nodes whose saved label disagrees with each candidate coverage rule."""
    mismatch = Counter()
    shapes = Counter()
    for _, d in graph.nodes(data=True):
        spans = lit(d["node_source_code_lines"])
        shapes[str([len(s) for s in spans])] += 1
        positive = bool(records(d))
        lines = ann.get(d["source_file"], set())
        ends = {x for s in spans for x in s}
        full = {x for s in spans for x in range(min(s), max(s) + 1)}
        first = {min(min(s) for s in spans)}
        for name, cover in (("endpoints", ends), ("full_range", full), ("first_line", first)):
            if bool(cover & lines) != positive:
                mismatch[name] += 1
    return {"coordinate_shapes": dict(shapes),
            "mismatches": {k: mismatch.get(k, 0) for k in ("endpoints", "full_range", "first_line")}}


def node_key(d):
    return (d["source_file"], d["node_type"], str(d.get("label")), str(d.get("node_source_code_lines")))


def compare_cfg_hcg(cfg, hcg):
    buggy_files = {d["source_file"] for _, d in hcg.nodes(data=True) if records(d)}
    cfg_files = {d["source_file"] for _, d in cfg.nodes(data=True)}
    hcg_sub = [n for n, d in hcg.nodes(data=True) if d["source_file"] in cfg_files]
    sub = hcg.subgraph(hcg_sub)
    cfg_keys = Counter(node_key(d) for _, d in cfg.nodes(data=True))
    hcg_keys = Counter(node_key(d) for _, d in sub.nodes(data=True))
    cfg_types = Counter(d["node_type"] for _, d in cfg.nodes(data=True))
    hcg_types = Counter(d["node_type"] for _, d in sub.nodes(data=True))
    return {
        "cfg_files_equal_hcg_buggy_files": cfg_files == buggy_files,
        "cfg_files": len(cfg_files),
        "hcg_buggy_files": len(buggy_files),
        "hcg_nodes_on_cfg_files": sub.number_of_nodes(),
        "hcg_edges_on_cfg_files": sub.number_of_edges(),
        "hcg_positive_on_cfg_files": sum(bool(records(d)) for _, d in sub.nodes(data=True)),
        "identical_nodes_by_file_type_label_lines": sum((cfg_keys & hcg_keys).values()),
        "node_types_only_in_hcg": {t: c for t, c in hcg_types.items() if t not in cfg_types},
        "node_types_only_in_cfg": {t: c for t, c in cfg_types.items() if t not in hcg_types},
        "cfg_has_call_edges": bool(CALL_EDGES & {d.get("edge_type") for _, _, d in cfg.edges(data=True)}),
    }


def public_annotations(bug):
    """The predecessor's annotation files, in original source coordinates."""
    out = defaultdict(set)
    origin = {}
    path = HGT / f"data/solidifi_buggy_contracts/{bug}/vulnerabilities.json"
    if path.exists():
        for record in json.load(open(path)):
            name = Path(record["name"]).name
            origin[name] = "solidifi"
            for vul in record["vulnerabilities"]:
                out[name].update(vul["lines"])
    for record in json.load(open(HGT / "data/smartbug-dataset/vulnerabilities.json")):
        name = Path(record["name"]).name
        if name in origin:
            continue
        lines = {n for v in record["vulnerabilities"] if v["category"] == bug for n in v["lines"]}
        if lines:
            origin[name] = "smartbugs"
            out[name].update(lines)
    return out, origin


def find_source(bug, name):
    for cand in (REPO / f"experiments/ge-sc-data/source_code/{bug}/source_files/{name}",
                 HGT / f"data/solidifi_buggy_contracts/{bug}/{name}"):
        if cand.exists():
            return cand
    return None


def foreign_candidates():
    cands = []
    for cat in sorted(p for p in SOLIDIFI.iterdir() if p.is_dir()):
        for log in sorted(cat.glob("BugLog_*.csv")):
            lines = set()
            with open(log, newline="") as handle:
                for row in csv.DictReader(handle):
                    lines.update(range(int(row["loc"]), int(row["loc"]) + int(row["length"])))
            cands.append((f"{cat.name}/{log.name}", lines))
    return cands


def provenance(bug, graph, ann, foreign):
    public, origin = public_annotations(bug)
    verdict = Counter()
    odd = []
    mapped_all = {}
    for name in sorted(ann):
        author = ann[name]
        source = find_source(bug, name)
        if name not in public or source is None:
            verdict["no public annotation or source found"] += 1
            odd.append({"file": name, "problem": "no public annotation or source"})
            continue
        line_map = build_line_map(source.read_text(encoding="utf8", errors="ignore"))
        mapped = {p + 1 for p, origins in enumerate(line_map) if set(origins) & public[name]}
        mapped_all[name] = mapped
        out_of_range = sorted(a for a in author if a > len(line_map))
        if author == mapped:
            verdict["equal to public annotation in preprocessed coordinates"] += 1
            continue
        entry = {"file": name, "origin": origin[name], "author_lines": len(author),
                 "expected_lines": len(mapped), "missing": len(mapped - author),
                 "extra_in_range": len({a for a in author - mapped if a <= len(line_map)}),
                 "out_of_range": len(out_of_range)}
        if out_of_range:
            verdict["contains out-of-range lines"] += 1
            best = max(((len(set(out_of_range) & lines) / len(out_of_range), label)
                        for label, lines in foreign), default=(0, None))
            entry["out_of_range_best_foreign_source"] = {"file": best[1], "coverage": round(best[0], 3)}
        elif author < mapped:
            verdict["subset: a few lines missing"] += 1
        else:
            verdict["other difference"] += 1
        odd.append(entry)
    # What the same rule yields from the clean public annotations.
    clean_positive = 0
    disagree = 0
    for _, d in graph.nodes(data=True):
        spans = lit(d["node_source_code_lines"])
        ends = {x for s in spans for x in s}
        rule = bool(ends & mapped_all.get(d["source_file"], set()))
        clean_positive += rule
        disagree += rule != bool(records(d))
    return {"per_file_verdict": dict(verdict), "files_that_differ": odd,
            "positives_from_rule_with_public_annotations": clean_positive,
            "nodes_disagreeing_with_author": disagree}


def main():
    foreign = foreign_candidates()
    result = {}
    for bug, paper in PAPER.items():
        hcg_path = UP / f"graph_detection/{bug}_tree_sitter_cfg_cg_compressed_graphs.gpickle"
        cfg_path = UP / f"node_detection/{bug}_tree_sitter_cfg_compressed_graphs.gpickle"
        hcg = load(hcg_path)
        ann, cats = embedded_annotations(hcg)
        entry = {"paper_table1": dict(zip(("contracts", "buggy_contracts", "nodes", "edges", "buggy_nodes"), paper)),
                 "hcg": stats(hcg), "hcg_record_categories": dict(cats),
                 "hcg_rule": rule_replay(hcg, ann),
                 "hcg_provenance": provenance(bug, hcg, ann, foreign)}
        if cfg_path.exists():
            cfg = load(cfg_path)
            cfg_ann, _ = embedded_annotations(cfg)
            entry["cfg"] = stats(cfg)
            entry["cfg_rule"] = rule_replay(cfg, cfg_ann)
            entry["cfg_vs_hcg"] = compare_cfg_hcg(cfg, hcg)
        else:
            entry["cfg"] = None
        result[bug] = entry

        h = entry["hcg"]
        print("=" * 100)
        print(f"{bug}")
        print(f"  paper   : contracts {paper[0]}/{paper[1]}  nodes {paper[2]}  edges {paper[3]}  buggy nodes {paper[4]}")
        print(f"  HCG     : contracts {h['files']}/{h['buggy_files']}  nodes {h['nodes']}  edges {h['edges']}  "
              f"buggy nodes {h['positive_nodes']}  edge types {sorted(h['edge_types'])}")
        print(f"  HCG rule mismatches {entry['hcg_rule']['mismatches']}  shapes {entry['hcg_rule']['coordinate_shapes']}")
        print(f"  HCG record categories {entry['hcg_record_categories']}")
        prov = entry["hcg_provenance"]
        print(f"  annotation provenance {prov['per_file_verdict']}")
        print(f"  rule + clean public annotations -> {prov['positives_from_rule_with_public_annotations']} positives, "
              f"{prov['nodes_disagreeing_with_author']} nodes differ from author")
        for odd in prov["files_that_differ"]:
            print(f"     {odd}")
        if entry["cfg"]:
            c = entry["cfg"]
            print(f"  CFG     : contracts {c['files']}/{c['buggy_files']}  nodes {c['nodes']}  edges {c['edges']}  "
                  f"buggy nodes {c['positive_nodes']}  edge types {sorted(c['edge_types'])}")
            print(f"  CFG rule mismatches {entry['cfg_rule']['mismatches']}")
            print(f"  CFG vs HCG {entry['cfg_vs_hcg']}")
        else:
            print("  CFG     : not downloaded")
    out = Path(__file__).with_name("audit_result.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
