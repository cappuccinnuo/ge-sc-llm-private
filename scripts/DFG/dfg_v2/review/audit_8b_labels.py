"""Read-only label / leakage audit of the Prompt 8B batch (written by the reviewer, not part of the frozen pipeline).

Uses only the standard library. Inputs:
  * frozen outer-test predictions  runs/<task>/fold_k/seed_1/<profile>/attempt_001/outer_test_predictions.json
  * dataset sources                experiments/ge-sc-data/source_code/<class>/{source_files,cleaned_buggy_curated}
  * SolidiFI bug logs              https://github.com/DependableSystemsLab/SolidiFI-benchmark
                                   (commit 4b0573e1b3f7031396de6f48f7f3e7380222ad3a, buggy_contracts/{tx.origin,Re-entrancy}/BugLog_N.csv)

Nothing here changes labels, graphs, folds or results. "Rule labels" are an audit view only.

Usage:
  python -I scripts/DFG/dfg_v2/review/audit_8b_labels.py --repo . --solidifi /path/to/SolidiFI-benchmark --out /tmp/audit8b.json
"""
import argparse
import collections
import csv
import glob
import json
import os
import re
import statistics

TASKS = {
    "access_control_node": ("access_control", "tx.origin", "txorigin"),
    "reentrancy_node": ("reentrancy", "Re-entrancy", "re_ent"),
}
PROFILES = ["G0", "G1R", "G2R", "G3R", "G3"]
CONTAINERS = ("contract_declaration", "library_declaration")
FUNCS = ("function_definition", "constructor_definition", "modifier_definition")


def bf1(tp, fp, fn):
    return 200.0 * tp / (2 * tp + fp + fn) if tp else 0.0


def first_line(r):
    return r["graph_label_anchor"].strip('"').split("\\n")[0]


def span(r):
    s = set()
    for g in r["graph_stored_source_lines"]:
        s |= set(range(g[0], g[-1] + 1))
    return s


def norm_lines(text):
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return [re.sub(r"\s+", "", re.sub(r"//.*", "", l)) for l in text.split("\n")]


def orig_to_cleaned(src_dir, b):
    """Map original-file line -> cleaned-file line by sequential normalized text match."""
    o = norm_lines(open(f"{src_dir}/source_files/{b}.sol").read())
    c = norm_lines(open(f"{src_dir}/cleaned_buggy_curated/{b}.sol").read())
    m, j, bad = {}, 0, 0
    for i, line in enumerate(c, 1):
        if not line:
            continue
        k = j
        while k < len(o) and o[k] != line:
            k += 1
        if k < len(o):
            m[k + 1] = i
            j = k + 1
        else:
            bad += 1
    return m, bad


def load_preds(runs, task, prof):
    out = {}
    for k in range(10):
        p = f"{runs}/{task}/fold_{k}/seed_1/{prof}/attempt_001/outer_test_predictions.json"
        out[k] = json.load(open(p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--solidifi", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    runs = f"{a.repo}/scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/runs"
    data = f"{a.repo}/experiments/ge-sc-data/source_code"
    report = {}
    for task, (cls, sd, pat) in TASKS.items():
        T = report.setdefault(task, {})
        preds = {p: load_preds(runs, task, p) for p in PROFILES}
        g0 = preds["G0"]
        files = sorted({r["file"] for k in g0 for r in g0[k]})
        # ---- 1. author label rule vs. SolidiFI bug logs
        rule, per_file, overlap = {}, {}, {}
        for fn in files:
            if not fn.startswith("buggy_"):
                continue
            b, n = fn[:-4], fn[:-4].split("_")[1]
            rows = [(int(r["loc"]), int(r["length"])) for r in csv.DictReader(open(f"{a.solidifi}/buggy_contracts/{sd}/BugLog_{n}.csv"))]
            s = sorted(rows)
            overlap[fn] = [[x, y] for x, y in zip(s, s[1:]) if y[0] < x[0] + x[1]]
            m, bad = orig_to_cleaned(f"{data}/{cls}", b)
            L = {m[x] for loc, ln in rows for x in range(loc, loc + ln) if x in m}
            agree = n_nodes = 0
            for k in g0:
                for r in g0[k]:
                    if r["file"] != fn:
                        continue
                    st = r["graph_stored_source_lines"][0][0]
                    lab = (st in L) if r["node_type"] == "contract_declaration" else bool(span(r) & L)
                    rule[(fn, r["original_graph_node_id"])] = int(lab)
                    n_nodes += 1
                    agree += int(lab) == r["target"]
            per_file[fn] = {"nodes": n_nodes, "rule_agree": agree, "bug_log_entries": len(rows),
                            "overlapping_entries": overlap[fn], "unmapped_cleaned_lines": bad}
        truncated = sorted(f for f, v in per_file.items() if v["nodes"] - v["rule_agree"] > 20)
        T["truncated_files"] = truncated
        T["files_with_overlapping_buglog_entries"] = sorted(f for f, v in overlap.items() if v)
        clean = [v for f, v in per_file.items() if f not in truncated]
        T["rule_agreement_non_truncated"] = [sum(v["rule_agree"] for v in clean), sum(v["nodes"] for v in clean)]
        T["per_file"] = per_file
        # ---- 2. rescoring: original labels vs. author rule applied without truncation (C1)
        T["scores"] = {}
        for prof in PROFILES:
            res = {}
            for mode in ("orig", "C1", "nonSolidiFI_only"):
                folds, P = [], collections.Counter()
                for k in range(10):
                    c = collections.Counter()
                    for r in preds[prof][k]:
                        t = r["target"]
                        if mode == "C1" and r["file"] in truncated:
                            t = rule[(r["file"], r["original_graph_node_id"])]
                        if mode == "nonSolidiFI_only" and r["file"].startswith("buggy_"):
                            continue
                        p = r["best"]
                        c["tp"] += t and p
                        c["fp"] += (not t) and p
                        c["fn"] += t and (not p)
                    folds.append(bf1(c["tp"], c["fp"], c["fn"]))
                    P += c
                res[mode] = {"fold_mean_bf1": statistics.mean(folds), "folds": folds,
                             "pooled_bf1": bf1(P["tp"], P["fp"], P["fn"]), "tp": P["tp"], "fp": P["fp"], "fn": P["fn"]}
            T["scores"][prof] = res
        # ---- 3. no-learning lexical rule (identifier leakage), scored on C1 labels
        folds, P = [], collections.Counter()
        for k in range(10):
            byf = collections.defaultdict(list)
            for r in g0[k]:
                byf[r["file"]].append(r)
            c = collections.Counter()
            for fn, rs in byf.items():
                fr = [(r["graph_stored_source_lines"][0][0], r["graph_stored_source_lines"][-1][-1])
                      for r in rs if r["node_type"] in FUNCS and pat in first_line(r)]
                for r in rs:
                    t = rule[(fn, r["original_graph_node_id"])] if fn in truncated else r["target"]
                    ls = [x for g in r["graph_stored_source_lines"] for x in g]
                    inside = r["node_type"] not in CONTAINERS and ls and any(lo <= min(ls) and max(ls) <= hi for lo, hi in fr)
                    p = int(bool(inside) or (pat in first_line(r) and r["node_type"] not in CONTAINERS))
                    c["tp"] += t and p
                    c["fp"] += (not t) and p
                    c["fn"] += t and (not p)
            folds.append(bf1(c["tp"], c["fp"], c["fn"]))
            P += c
        T["lexical_rule_C1"] = {"fold_mean_bf1": statistics.mean(folds), "folds": folds,
                                "pooled_bf1": bf1(P["tp"], P["fp"], P["fn"]), **dict(P)}
        # ---- 4. false-negative causes (original labels)
        T["fn_causes"] = {}
        for prof in ("G0", "G3R"):
            c = collections.Counter()
            for k in range(10):
                byf = collections.defaultdict(list)
                for r in preds[prof][k]:
                    byf[r["file"]].append(r)
                for fn, rs in byf.items():
                    fr = [(r["graph_stored_source_lines"][0][0], r["graph_stored_source_lines"][-1][-1])
                          for r in rs if r["node_type"] in FUNCS and pat in first_line(r)]
                    for r in rs:
                        if not (r["target"] == 1 and r["best"] == 0):
                            continue
                        ls = [x for g in r["graph_stored_source_lines"] for x in g]
                        if not fn.startswith("buggy_"):
                            key = "non_solidifi_annotated_vuln"
                        elif r["node_type"] in CONTAINERS:
                            key = "solidifi_container_label"
                        elif pat in first_line(r) or any(lo <= min(ls) and max(ls) <= hi for lo, hi in fr):
                            key = "solidifi_injected_code_true_miss"
                        else:
                            key = "solidifi_spillover_label_on_non_injected_code"
                        c[key] += 1
            T["fn_causes"][prof] = dict(c)
    # ---- 5. exact duplicate sources
    dups = {}
    for cls in ("access_control", "reentrancy"):
        h = collections.defaultdict(list)
        for p in glob.glob(f"{data}/{cls}/source_files/*.sol"):
            h[re.sub(r"\s+", "", open(p).read())].append(os.path.basename(p))
        dups[cls] = [sorted(v) for v in h.values() if len(v) > 1]
    report["exact_duplicate_sources"] = dups
    json.dump(report, open(a.out, "w"), indent=1, default=str)
    for task, T in report.items():
        if task == "exact_duplicate_sources":
            continue
        print(task, "truncated", T["truncated_files"], "overlap", T["files_with_overlapping_buglog_entries"],
              "rule agreement", T["rule_agreement_non_truncated"])
        for prof, res in T["scores"].items():
            print(f"  {prof}: " + "  ".join(f"{m} {v['fold_mean_bf1']:.3f} (TP/FP/FN {v['tp']}/{v['fp']}/{v['fn']})" for m, v in res.items()))
        print("  lexical rule C1 fold mean %.3f" % T["lexical_rule_C1"]["fold_mean_bf1"])
        print("  FN causes", T["fn_causes"])
    print("duplicates", dups)


if __name__ == "__main__":
    main()
