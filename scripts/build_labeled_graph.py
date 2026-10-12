"""Merge per-contract tree-sitter CFGs into one compressed graph and attach labels.

This reproduces stage A of the upstream MANDO pipeline
(ge-sc/process_graphs/control_flow_graph_generator.py::compress_full_smart_contracts)
for the tree-sitter graphs produced by scripts/gen_reentrancy_cfg.py.

Upstream builds and labels in a single pass over Slither nodes; the tree-sitter path
has no equivalent driver, so the merge and the labelling run as two explicit steps
here. The labelling helpers below are ported verbatim from upstream so the semantics
stay identical:

  get_vulnerabilities(file_name_sc, vulnerabilities)
      -> the vulnerability records for one contract, matched by file name

  get_vulnerabilities_of_node_by_source_code_line(source_code_lines, list_vul_info_sc)
      -> the subset of those records whose 'lines' intersect a node's source lines,
         or None when there is no overlap

Note upstream applies NO category filter: any record matching the file name counts,
which is why a contract annotated only with e.g. unchecked_low_level_calls still ends
up labelled buggy in the reentrancy corpus.

Annotation sources:
  SmartBugs curated  : data/smartbug-dataset/vulnerabilities.json (already in shape)
  SolidiFI injected  : data/SolidiFI-benchmark/buggy_contracts/Re-entrancy/BugLog_*.csv
                       converted here; a row (loc, length) covers lines
                       [loc, loc+length-1] inclusive, verified against buggy_20.sol.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import networkx as nx

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from line_mapping import build_line_map, preprocessed_to_original  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# Upstream labelling helpers (ported verbatim in behaviour)
# --------------------------------------------------------------------------
def get_vulnerabilities(file_name_sc, vulnerabilities):
    """Collect every annotation record for one contract.

    DELIBERATE DEVIATION FROM UPSTREAM. ge-sc's version assigns instead of
    accumulating and has no break, so when a file is listed more than once the last
    record silently shadows the earlier ones. That happens for real: SmartBugs files
    0x627fa62c....sol under both dataset/reentrancy (line 94) and
    dataset/unchecked_low_level_calls (line 44), and upstream would drop the
    reentrancy annotation from the reentrancy corpus. Accumulating keeps both.
    """
    collected = []
    if vulnerabilities is not None:
        for vul_item in vulnerabilities:
            if file_name_sc == vul_item["name"]:
                collected.extend(vul_item["vulnerabilities"])
    return collected or None


def get_vulnerabilities_of_node_by_source_code_line(source_code_lines, list_vul_info_sc):
    if list_vul_info_sc is not None:
        list_vulnerability = []
        for vul_info_sc in list_vul_info_sc:
            vulnerabilities_lines = vul_info_sc["lines"]
            interset_lines = set(vulnerabilities_lines).intersection(set(source_code_lines))
            if len(interset_lines) > 0:
                list_vulnerability.append(vul_info_sc)
    else:
        list_vulnerability = None

    if list_vulnerability is None or len(list_vulnerability) == 0:
        node_info_vulnerabilities = None
    else:
        node_info_vulnerabilities = list_vulnerability

    return node_info_vulnerabilities


def merge_data_from_vulnerabilities_json_files(list_vulnerabilities_json_files):
    result = list()
    for f1 in list_vulnerabilities_json_files:
        with open(f1, "r") as infile:
            result.extend(json.load(infile))
    return result


# --------------------------------------------------------------------------
# SolidiFI BugLog -> upstream vulnerabilities.json shape
# --------------------------------------------------------------------------
def solidifi_buglogs_to_records(buglog_dir, category, line_mode="range"):
    """Convert BugLog_N.csv files into [{'name','vulnerabilities':[{'lines','category'}]}].

    A row is (loc, length, bug type, approach); the injected snippet occupies `length`
    lines starting at `loc`.

    line_mode picks how much of that counts as vulnerable, because this conversion is
    a reconstruction - the authors shipped a pre-built
    solidifi_buggy_contracts/<bug>/vulnerabilities.json that is not in this repo:
      range (default) the whole injected snippet, [loc, loc+length-1]
      start           only the first line, [loc]
    'range' marks every statement of the injected function; 'start' marks just the
    injection point. The choice moves the positive-node count substantially.
    """
    records = []
    for csv_path in sorted(Path(buglog_dir).glob("BugLog_*.csv")):
        index = csv_path.stem.split("_")[-1]
        contract_name = f"buggy_{index}.sol"
        vulns = []
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                try:
                    loc = int(row["loc"])
                    length = int(row["length"])
                except (KeyError, ValueError, TypeError):
                    continue
                if length <= 0:
                    continue
                lines = [loc] if line_mode == "start" else list(range(loc, loc + length))
                vulns.append({"lines": lines, "category": category})
        if vulns:
            records.append({"name": contract_name, "vulnerabilities": vulns})
    return records


def normalize_smartbugs(records):
    """Key SmartBugs entries by bare file name, which is what upstream matches on."""
    out = []
    for e in records:
        out.append(
            {
                "name": Path(e["name"]).name,
                "vulnerabilities": e["vulnerabilities"],
            }
        )
    return out


# --------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cfg_dir", default="/tmp/reentrancy_cfg_regen",
                   help="Directory of per-contract .gpickle CFGs from gen_reentrancy_cfg.py")
    p.add_argument("--source_dir",
                   default=str(REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"),
                   help="Raw .sol directory, used to define corpus membership")
    p.add_argument("--smartbugs",
                   default=str(REPO / "data/smartbug-dataset/vulnerabilities.json"))
    p.add_argument("--solidifi_buglogs",
                   default=str(REPO / "data/SolidiFI-benchmark/buggy_contracts/Re-entrancy"))
    p.add_argument("--solidifi_category", default="reentrancy",
                   help="Category string written for SolidiFI-injected bugs")
    p.add_argument("--solidifi_lines", choices=("range", "start"), default="range",
                   help="How much of a SolidiFI injected snippet counts as vulnerable: "
                        "the whole range, or only its first line")
    p.add_argument("--output",
                   default=str(REPO / "experiments/ge-sc-data/source_code/reentrancy/cfg_compressed_graphs.gpickle"))
    p.add_argument("--dump_vulnerabilities", default=None,
                   help="Optional path to write the merged annotation list as JSON")
    return p


def main():
    args = build_parser().parse_args()

    # ---- assemble the annotation list, mirroring upstream's merge ----
    smartbugs = normalize_smartbugs(json.load(open(args.smartbugs)))
    solidifi = solidifi_buglogs_to_records(args.solidifi_buglogs, args.solidifi_category,
                                           line_mode=args.solidifi_lines)
    vulnerabilities = smartbugs + solidifi
    print(f"annotation records: smartbugs={len(smartbugs)} solidifi={len(solidifi)} "
          f"total={len(vulnerabilities)}")

    if args.dump_vulnerabilities:
        Path(args.dump_vulnerabilities).write_text(json.dumps(vulnerabilities, indent=2))
        print(f"wrote merged annotations -> {args.dump_vulnerabilities}")

    # ---- merge the per-contract graphs ----
    corpus = sorted(p.name for p in Path(args.source_dir).glob("*.sol"))
    cfg_dir = Path(args.cfg_dir)

    merged = None
    used, missing = 0, []
    for name in corpus:
        gp = cfg_dir / f"{Path(name).stem}.gpickle"
        if not gp.exists():
            missing.append(name)
            continue
        g = nx.read_gpickle(gp)
        merged = g.copy() if merged is None else nx.disjoint_union(merged, g)
        used += 1

    if merged is None:
        raise SystemExit(f"no graphs found under {cfg_dir}")

    print(f"merged {used}/{len(corpus)} contract graphs "
          f"-> {merged.number_of_nodes()} nodes / {merged.number_of_edges()} edges")
    if missing:
        print(f"  MISSING graphs for {len(missing)}: {missing[:10]}")

    # ---- attach node_info_vulnerabilities ----
    # node_source_code_lines indexes the preprocessed (comment/blank-stripped) source
    # that parser_driver feeds to tree-sitter, while annotations reference original
    # file lines, so translate before intersecting.
    source_dir = Path(args.source_dir)
    per_file_vulns = {}
    per_file_linemap = {}
    buggy_nodes = 0
    buggy_files = set()
    empty_lines_nodes = 0
    for _, nd in merged.nodes(data=True):
        source_file = nd.get("source_file")
        if source_file not in per_file_vulns:
            per_file_vulns[source_file] = get_vulnerabilities(source_file, vulnerabilities)
            sol = source_dir / source_file
            per_file_linemap[source_file] = (
                build_line_map(sol.read_text(encoding="utf8", errors="ignore"))
                if sol.exists() else []
            )

        pre_lines = nd.get("node_source_code_lines") or []
        if not pre_lines:
            empty_lines_nodes += 1
        orig_lines = preprocessed_to_original(pre_lines, per_file_linemap[source_file])
        nd["node_source_code_lines_original"] = orig_lines

        info = get_vulnerabilities_of_node_by_source_code_line(
            orig_lines, per_file_vulns[source_file]
        )
        nd["node_info_vulnerabilities"] = info
        if info:
            buggy_nodes += 1
            buggy_files.add(source_file)

    annotated_files = {f for f, v in per_file_vulns.items() if v}
    total_files = len(per_file_vulns)

    print()
    print(f"contracts in graph              : {total_files}")
    print(f"contracts with an annotation    : {len(annotated_files)}")
    print(f"contracts with >=1 buggy node   : {len(buggy_files)}")
    print(f"contracts annotated but 0 nodes hit: "
          f"{len(annotated_files - buggy_files)} {sorted(annotated_files - buggy_files)[:10]}")
    print()
    print(f"buggy nodes : {buggy_nodes}/{merged.number_of_nodes()} "
          f"({100.0 * buggy_nodes / merged.number_of_nodes():.2f}%)")
    print(f"nodes with empty source lines (cannot ever match): {empty_lines_nodes}")

    cat = Counter()
    for _, nd in merged.nodes(data=True):
        for v in (nd.get("node_info_vulnerabilities") or []):
            cat[v.get("category")] += 1
    print(f"buggy-node category spread: {cat.most_common()}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    nx.write_gpickle(merged, str(out))
    print(f"\nwrote merged labelled graph -> {out}")


if __name__ == "__main__":
    main()
