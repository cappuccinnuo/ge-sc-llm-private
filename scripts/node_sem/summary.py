"""NS-P9: read-only synthesis of sealed original-view results. No inference or training."""
import argparse
import csv
import hashlib
import json
import math
import statistics
import struct
from collections import defaultdict
from pathlib import Path

from scripts.DFG.dfg_v2.experiment.stats import aggregate_metrics, record_key, validate_records
from scripts.DFG.experiments.common import metrics
from .reporting import aligned_rows

BASE = Path(__file__).resolve().parent
ART = BASE / "artifacts"
DEFAULT = ART / "summary_NS_v1"
BATCHES = ("NA", "NB", "NC1", "NC2")
SELECTED = ("S0o", "S2", "S4", "S6", "S5", "S8")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def write(path, value):
    with Path(path).open("x", encoding="utf8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def reference(path):
    return dict(path=str(Path(path).resolve()), sha256=sha(path))


def same(a, b):
    """Compare JSON values, including binary64 float bits (not rounded text)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return struct.pack("!d", a) == struct.pack("!d", b)
    if isinstance(a, dict):
        return set(a) == set(b) and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


class Sources:
    def __init__(self):
        self.verified = {}

    def check(self, ref):
        p = Path(ref["path"]).resolve()
        if not p.is_file():
            raise ValueError("Missing source: " + str(p))
        if sha(p) != ref["sha256"]:
            raise ValueError("Source SHA differs: " + str(p))
        old = self.verified.get(str(p))
        if old and old["sha256"] != ref["sha256"]:
            raise ValueError("Conflicting source references: " + str(p))
        self.verified[str(p)] = dict(path=str(p), sha256=ref["sha256"], bytes=p.stat().st_size)
        return p

    def root(self, path):
        return self.check(reference(path))

    def json(self, ref):
        return read(self.check(ref))

    def refs(self, value):
        if isinstance(value, dict):
            if "path" in value and "sha256" in value:
                self.check(value)
            else:
                for v in value.values():
                    self.refs(v)
        elif isinstance(value, list):
            for v in value:
                self.refs(v)


def csv_write(path, rows):
    rows = list(rows)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("x", encoding="utf8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, allow_nan=False)
                             if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()})


def jid(j):
    return (j["task_id"], j["profile"], j["name"], j["fold"], j["seed"])


def merge_records(groups):
    merged, origins = {}, defaultdict(list)
    for name, rows in groups:
        validate_records(rows)
        for row in rows:
            key = record_key(row)
            if key in merged and not same(merged[key], row):
                raise ValueError("Historical metric differs: " + str(key))
            merged[key] = row
            origins[key].append(name)
    return [merged[k] for k in sorted(merged)], origins


def node_key(row):
    return row["source_sha256"], row["file"], row["original_graph_node_id"]


def node_join(tables):
    if set(tables)!=set(SELECTED):
        raise ValueError("Configuration set differs")
    expected = set(tables[SELECTED[0]])
    if any(set(tables[n]) != expected for n in SELECTED):
        raise ValueError("Configuration node identities differ")
    output = []
    for key in sorted(expected):
        first = tables[SELECTED[0]][key]
        if any(tables[n][key]["target"] != first["target"] for n in SELECTED):
            raise ValueError("Node targets differ")
        for field in ("fold","node_type","source_id","cohort"):
            if any(tables[n][key][field] != first[field] for n in SELECTED):
                raise ValueError("Node identity metadata differs: "+field)
        if first["target"] != 1 or first["cohort"] != "nonSolidiFI":
            continue
        for ck in ("best", "last"):
            output.append(dict(file=first["file"], source_sha256=first["source_sha256"],
                source_id=first["source_id"], original_graph_node_id=first["original_graph_node_id"],
                node_type=first["node_type"], fold=first["fold"], target=1, checkpoint=ck,
                all_missed=all(tables[n][key][ck] == 0 for n in SELECTED),
                predictions={n: tables[n][key][ck] for n in SELECTED},
                probabilities={n: tables[n][key][ck + "_positive_probability"] for n in SELECTED}))
    return output


def collect(out=DEFAULT):
    out = Path(out)
    out.mkdir(exist_ok=False)
    reports = out / "reports"
    reports.mkdir()
    sources = Sources()
    write(out / "decisions.json", dict(stage="NS-P9", original_view=True, read_only=True,
        S3m="not_run_no_substitute", S4_noG="G0_actual_identity",
        user_approved="同意按实际实验身份汇总并标记缺项",
        new_training=0, new_model_evaluations=0, new_LLM_calls=0, new_features=0,
        next_baseline="user_decision_pending"))
    all_jobs, entries, groups, originals, source_reports, resources = {}, {}, [], [], {}, []
    for name in BATCHES:
        root = ART / ("batch_" + name + "_v1")
        seal = read(sources.root(root / "plan.seal.json"))
        plan = sources.json(seal["plan"])
        done = read(sources.root(root / "complete.json"))
        if not done["passed"] or done["plan"] != seal["plan"]:
            raise ValueError("Incomplete or mismatched batch " + name)
        sources.refs(done)
        report_receipt = read(sources.root(root / "reports/receipt.json"))
        if report_receipt["plan"] != seal["plan"]:
            raise ValueError("Report plan differs")
        sources.refs(report_receipt)
        report = read(root / "reports/report.json")
        if not report["passed"]:
            raise ValueError("Source report failed")
        source_reports[name] = report
        rows = read(root / "reports/fold_metrics.json")
        if not same(aggregate_metrics(rows), report["aggregates"]):
            raise ValueError("Source aggregates differ at binary64 precision: " + name)
        groups.append((name, rows))
        originals.append((name, read(root / "reports/orig_all_fold_metrics.json")))
        jobs = {jid(j): j for j in plan["jobs"]}
        if len(jobs) != len(plan["jobs"]) or len(done["receipts"]) != len(jobs):
            raise ValueError("Duplicate or missing jobs")
        saved_resources = {}
        with (root / "reports/resources.csv").open(encoding="utf8") as f:
            for row in csv.DictReader(f):
                graph = row.get("profile", "G3R")
                saved_resources[(row["task_id"],graph,row["name"],int(row["fold"]),1)] = row
        found = set()
        for ref in done["receipts"]:
            rc = sources.json(ref)
            key = jid(rc["job"])
            if key in found or key not in jobs or not same(rc["job"], jobs[key]):
                raise ValueError("Receipt job identity differs")
            if key in all_jobs:
                raise ValueError("Formal fit repeated across batches")
            if rc["plan"] != seal["plan"]:
                raise ValueError("Fit plan differs")
            found.add(key)
            all_jobs[key] = jobs[key]
            entries[key] = (name, ref, rc)
            resources.append(dict(batch=name, task_id=key[0], graph=key[1], name=key[2],
                fold=key[3], seed=key[4], fit_seconds=float(saved_resources[key]["fit_seconds"]),
                fit_inclusive_seconds=rc["fit"]["fit_inclusive"], epoch_loop_seconds=rc["fit"]["epoch_loop"],
                total_seconds=rc["total_seconds"], minimum_free_mib=rc["resources"]["minimum_free_mib"],
                peak_allocated_mib=rc["resources"]["peak_allocated_mib"],
                peak_reserved_mib=rc["resources"]["peak_reserved_mib"],
                receipt=ref))
        if found != set(jobs):
            raise ValueError("Missing formal fit")
        print("verified", name, len(jobs), flush=True)
    records, origins = merge_records(groups)
    orig_records, _ = merge_records([(name, validate_records(rows)) for name, rows in originals])
    expected = {(j["task_id"], j["profile"] + "/" + j["name"], j["fold"], j["seed"], ck)
                for j in all_jobs.values() for ck in ("best", "last")}
    validate_records(records, expected)
    validate_records(orig_records, expected)
    if len(all_jobs) != 450 or len(records) != 900:
        raise ValueError("Formal matrix differs")
    write(reports / "fold_metrics.json", records)
    write(reports / "orig_all_fold_metrics.json", orig_records)
    aggregates = aggregate_metrics(records)
    write(reports / "aggregates.json", aggregates)
    for ck in ("best", "last"):
        csv_write(reports / (ck + "_fold_means.csv"), [r for r in aggregates if r["checkpoint"] == ck])
    csv_write(reports / "fold_metrics.csv", [dict(**{k:v for k,v in r.items() if k!="metrics"},
        **r["metrics"], source_batches=origins[record_key(r)]) for r in records])
    write(reports / "missing_configurations.json", [dict(name="S3m", status="not_run",
        task_id=t, requested_graph="G3R") for t in sorted({j["task_id"] for j in all_jobs.values()})])
    tests = []
    for name, r in source_reports.items():
        if name == "NA":
            primary = [v for v in r["paired"] if v.get("p_raw") is not None]
        else:
            primary = r.get("primary", [])
            if isinstance(primary, dict):
                primary = [primary]
        tests.append(dict(batch=name, source_report=reference(ART / ("batch_"+name+"_v1/reports/report.json")),
            holm=r.get("holm"), primary=primary, recomputed=False))
    write(reports / "registered_inference.json", tests)
    csv_write(reports / "resources.csv", resources)
    costs = []
    for name in BATCHES:
        rows = [r for r in resources if r["batch"] == name]
        costs.append(dict(batch=name, formal_fits=len(rows),
            gpu_fit_hours=sum(r["fit_seconds"] for r in rows)/3600,
            gpu_process_hours=sum(r["total_seconds"] for r in rows)/3600,
            minimum_free_mib=min(r["minimum_free_mib"] for r in rows),
            peak_allocated_mib=max(r["peak_allocated_mib"] for r in rows),
            peak_reserved_mib=max(r["peak_reserved_mib"] for r in rows),
            scope="sum accepted fit/process wall durations, not hardware utilization; excludes failed attempts and diagnostics"))
    write(reports / "training_costs.json", costs)
    csv_write(reports / "training_costs.csv", costs)
    # Diagnostics remain read-only and retain their original limitations.
    diagnostic_refs = {}
    for name in ("ns_p6c", "ns_p6c2"):
        root = ART / name
        seal = read(sources.root(root / "plan.seal.json"))
        sources.refs(seal)
        result = read(sources.root(root / "result.seal.json"))
        sources.refs(result)
        done = read(sources.root(root / "complete.json"))
        sources.refs(done)
        diagnostic_refs[name] = result["report"]
    llm = ART / "llm_v3"
    sources.refs(read(sources.root(llm / "plan.seal.json")))
    completion = read(sources.root(llm / "finalization/complete.json"))
    sources.refs(completion)
    diagnostic_refs["NS-P7c"] = completion["results"]
    student = read(sources.root(ART / "batch_NC2_v1/student_summary.json"))
    sources.refs(student["cost"])
    sources.refs(read(sources.root(ART / "batch_NC2_v1/students_complete.json")))
    write(reports / "diagnostic_references.json", diagnostic_refs)
    write(reports / "preprocessing_costs.json", student["cost"])
    tables, label_sets = defaultdict(lambda: defaultdict(dict)), {}
    for key, job in sorted(all_jobs.items()):
        task, graph, config, fold, seed = key
        if not task.endswith("_node") or graph != "G3R" or config not in SELECTED:
            continue
        name, receipt_ref, rc = entries[key]
        label_sets[task] = sources.json(job["label_view"])[task]
        predictions_ref = [r for r in rc["artifacts"] if r["path"].endswith("/fit/outer_test_predictions.json")]
        if len(predictions_ref) != 1:
            raise ValueError("Ambiguous prediction artifact")
        rows = aligned_rows(sources.json(predictions_ref[0]), job, {task:label_sets[task]})
        for row in rows:
            k = node_key(row)
            if k in tables[task][config]:
                raise ValueError("Duplicate OOF node identity")
            row = dict(row, fold=fold)
            for ck in ("best","last"):
                p = row[ck+"_positive_probability"]
                if not math.isfinite(p) or not 0 <= p <= 1 or row[ck] not in (0,1):
                    raise ValueError("Invalid prediction/probability")
            tables[task][config][k] = row
    positive_rows, corrected, cohort_scores = [], [], []
    for task, configs in sorted(tables.items()):
        rows = node_join(configs)
        n = 32 if task=="reentrancy_node" else 20
        if len(rows) != 2*n:
            raise ValueError("NonSolidiFI positive count differs")
        positive_rows.extend(dict(r, task_id=task) for r in rows)
        for name, nodes in configs.items():
            for ck in ("best","last"):
                for cohort in ("SolidiFI","nonSolidiFI"):
                    selected=[r for r in nodes.values() if r["cohort"]==cohort]
                    counts={name_:sum(r["target"]==t and r[ck]==p for r in selected)
                            for name_,t,p in (("tp",1,1),("fp",0,1),("fn",1,0),("tn",0,0))}
                    cohort_scores.append(dict(task_id=task,name=name,checkpoint=ck,cohort=cohort,
                        **counts,**metrics([r["target"] for r in selected],[r[ck] for r in selected])))
        if task == "access_control_node":
            for k, s4 in configs["S4"].items():
                s5=configs["S5"][k]
                if s4["cohort"]=="nonSolidiFI" and s4["target"]==0 and s4["best"]==1 and s5["best"]==0:
                    corrected.append(dict(task_id=task,file=s4["file"],source_sha256=s4["source_sha256"],
                        source_id=s4["source_id"],original_graph_node_id=s4["original_graph_node_id"],
                        node_type=s4["node_type"],fold=s4["fold"],S4_probability=s4["best_positive_probability"],
                        S5_probability=s5["best_positive_probability"]))
    if len(corrected)!=10:
        raise ValueError("Expected ten removed nonSolidiFI false positives")
    checks = compare_prior_tables(positive_rows, sources)
    write(reports / "positive_nodes.json", positive_rows)
    for ck in ("best","last"):
        csv_write(reports / ("positive_nodes_"+ck+".csv"),[
            dict(**{k:v for k,v in r.items() if k not in ("predictions","probabilities")},
                 **{n+"_prediction":r["predictions"][n] for n in SELECTED},
                 **{n+"_probability":r["probabilities"][n] for n in SELECTED})
            for r in positive_rows if r["checkpoint"]==ck])
    write(reports / "removed_false_positives.json", corrected)
    csv_write(reports / "cohort_scores.csv", cohort_scores)
    write(reports / "cohort_scores.json", cohort_scores)
    write(reports / "source_audit.json", list(sources.verified.values()))
    write(out / "collect_complete.json", dict(passed=True, fits=450, metric_rows=900,
        historical_duplicate_rows=sum(len(r) for _,r in groups)-900,
        binary64_aggregates_exact=True, prior_positive_tables=checks,
        persistent_best={t:sum(r["task_id"]==t and r["checkpoint"]=="best" and r["all_missed"]
            for r in positive_rows) for t in tables},
        inputs=list(sources.verified.values()),
        artifacts=[reference(p) for p in sorted(reports.iterdir()) if p.is_file()]))
    return out


def compare_prior_tables(rows, sources):
    indexed={(r["task_id"],r["file"],r["original_graph_node_id"],r["checkpoint"]):r for r in rows}
    counts={}
    for batch in ("NC1","NC2"):
        p=ART/("batch_"+batch+"_v1/reports/nonSolidiFI_positive_pairs.csv")
        sources.root(p)  # parent report receipt has already checked this file
        old=list(csv.DictReader(p.open(encoding="utf8")))
        checked=0
        for r in old:
            # Existing CSV format is inspected explicitly; no row-number joins.
            key=(r["task_id"],r["file"],int(r["original_graph_node_id"]),r["checkpoint"])
            v=indexed[key]
            if (r["source_sha256"]!=v["source_sha256"] or r["source_id"]!=v["source_id"]
                    or int(r["fold"])!=v["fold"] or int(r["target"])!=v["target"]):
                raise ValueError("Prior positive source identity differs")
            if batch=="NC1":
                pairs=(("S6","S6_prediction","S6_probability"),("S4","S4_prediction","S4_probability"))
            else:
                left,right=r["comparison"].split("-")
                pairs=((left,"prediction","probability"),(right,"baseline_prediction","baseline_probability"))
            for config,pred,prob in pairs:
                if int(r[pred])!=v["predictions"][config] or not same(float(r[prob]),v["probabilities"][config]):
                    raise ValueError("Prior positive prediction differs")
            checked+=1
        counts[batch]=checked
    return counts


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default=str(DEFAULT))
    collect(parser.parse_args().out)
