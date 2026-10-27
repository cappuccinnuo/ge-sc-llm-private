"""Prompt 8 read-only reports from sealed, independently verified predictions.

No fitting, model selection, label editing or pilot-result import occurs here.
The reporting specification is frozen before execution. Directed reachability
is descriptive association with changed predictions, never a causal estimate.
"""
import copy
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.DFG.experiments.common import digest, metrics
from scripts.DFG.integration.io import read_json, sha256, write_json
from scripts.labeling_v2.safe_graph import read_graph
from .. import AUX_NODE_TYPES, FORWARD_RELATIONS, REVERSE_OF
from ..tasks import checked_ref
from . import stats

VERSION = "dfg-v2-reporting-v1"
CHECKPOINTS = ("best", "last")
V2_RELATIONS = set(FORWARD_RELATIONS) | set(REVERSE_OF.values())


def _ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha256(path))


def validate_reporting_metadata(spec, plan):
    """Check category/file/source identities against the frozen task records."""
    if (not isinstance(spec, dict) or spec.get("version") != "prompt8-report-spec-v1"
            or not isinstance(spec.get("sensitivity"), list)):
        raise ValueError("A preregistered sensitivity list is required")
    identities = {}
    for task_id, task in plan["tasks"].items():
        record = task["record"]
        for filename, ref in record["sources"].items():
            identity = (record["category"], filename)
            previous = identities.setdefault(identity, ref["sha256"])
            if previous != ref["sha256"]:
                raise ValueError("Same category/file has different source identities")
    seen = set()
    for row in spec["sensitivity"]:
        key = (row["category"], row["file"])
        if key in seen or identities.get(key) != row.get("source_sha256"):
            raise ValueError("Sensitivity source identity is duplicate, missing or changed")
        seen.add(key)
    audit_ref = spec.get("source_audit")
    if audit_ref is not None:
        checked_ref(audit_ref)
    for review in spec.get("review_sources", []):
        checked_ref(review["csv"])
        checked_ref(review["seal"])
        if review.get("equivalence"):
            checked_ref(review["equivalence"])
    expected_mechanism = dict(direction="model_message", hops=[1, 2],
        path_rule="directed path length <= h containing named new canonical relation",
        count_unit="changed original HCG node", interim_profile="G3R", final_profile="G*")
    if spec.get("mechanism") != expected_mechanism:
        raise ValueError("Directed mechanism definition must be preregistered")
    if spec.get("statistics") != stats.specification():
        raise ValueError("Statistics specification differs from preregistration")
    return copy.deepcopy(spec)


def _identity(row, record):
    filename = row["file"]
    source = record["sources"].get(filename)
    if source is None:
        raise ValueError("Scored file has no frozen source SHA")
    node = row.get("original_graph_node_id")
    if row.get("node_type") in AUX_NODE_TYPES:
        raise ValueError("Auxiliary node cannot be scored")
    return (record["category"], filename, source["sha256"],
            json.dumps(node, sort_keys=True, ensure_ascii=False))


def _indexed(rows, record):
    result = {}
    for row in rows:
        if row.get("score_role") != "outer_test":
            raise ValueError("Report accepts outer-test predictions only")
        key = _identity(row, record)
        if key in result:
            raise ValueError("Duplicate prediction identity")
        if type(row.get("target")) is not int or row["target"] not in (0, 1):
            raise ValueError("Invalid frozen target")
        for ck in CHECKPOINTS:
            if type(row.get(ck)) is not int or row[ck] not in (0, 1):
                raise ValueError("Invalid prediction")
            probability = row.get(ck + "_positive_probability")
            if (not isinstance(probability, (int, float))
                    or not math.isfinite(probability) or not 0 <= probability <= 1):
                raise ValueError("Invalid probability")
        result[key] = row
    if not result:
        raise ValueError("Empty prediction export")
    return result


def _score(rows, checkpoint):
    if not rows:
        return None
    return metrics([row["target"] for row in rows], [row[checkpoint] for row in rows])


def _flatten_score(row, score):
    output = dict(row, n=0, positive=0, tn=None, fp=None, fn=None, tp=None)
    output.update({metric: None for metric in stats.METRICS})
    if score is not None:
        output.update({key: score[key] for key in ("n", "positive") + stats.METRICS})
        output.update(dict(zip(("tn", "fp", "fn", "tp"), score["tn_fp_fn_tp"])))
    return output


def prediction_tables(plan, bundles, spec):
    """Recompute fold, pooled, sensitivity and per-file scores; reject overlap."""
    excluded = {(r["category"], r["file"], r["source_sha256"]) for r in spec["sensitivity"]}
    records, fold_rows, file_rows, pooled, seen_oof = [], [], [], defaultdict(list), defaultdict(set)
    expected_oof = {}
    for bundle in bundles:
        job, rows = bundle["job"], bundle["predictions"]
        task_id, profile = job["task_id"], job["profile"]
        record = plan["tasks"][task_id]["record"]
        indexed = _indexed(rows, record)
        bundle["indexed"] = indexed
        split_files = set(bundle["split"]["outer_test_files"])
        if {r["file"] for r in rows} != split_files:
            raise ValueError("Scored files differ from frozen outer split")
        expected_oof[task_id] = set(record["graph_files"])
        group = (task_id, profile, job["seed"])
        if seen_oof[group] & set(indexed):
            raise ValueError("Repeated OOF identity across folds")
        seen_oof[group].update(indexed)
        pooled[group].extend(rows)
        for ck in CHECKPOINTS:
            score = _score(rows, ck)
            if score != bundle["result"]["outer_test"][ck]:
                raise ValueError("Recomputed predictions disagree with verified result")
            common = dict(task_id=task_id, task_kind=record["task"], profile=profile,
                          fold=job["fold"], seed=job["seed"], checkpoint=ck)
            records.append(dict(common, metrics={m: score[m] for m in stats.METRICS}))
            fold_rows.append(_flatten_score(dict(common, population="all"), score))
            filtered = [r for key, r in indexed.items() if key[:3] not in excluded]
            fold_rows.append(_flatten_score(dict(common, population="exclude_disputed"), _score(filtered, ck)))
            for filename in sorted(split_files):
                selected = [r for r in rows if r["file"] == filename]
                ref = record["sources"][filename]
                file_rows.append(_flatten_score(dict(common, category=record["category"],
                    file=filename, source_sha256=ref["sha256"],
                    disputed=(record["category"], filename, ref["sha256"]) in excluded),
                    _score(selected, ck)))
    pooled_rows = []
    for (task_id, profile, seed), rows in sorted(pooled.items()):
        record = plan["tasks"][task_id]["record"]
        if {r["file"] for r in rows} != expected_oof[task_id]:
            raise ValueError("Pooled OOF does not cover every frozen file")
        # Each scored node/file appears exactly once per profile and seed.
        indexed = _indexed(rows, record)
        for ck in CHECKPOINTS:
            common = dict(task_id=task_id, task_kind=record["task"],
                          profile=profile, seed=seed, checkpoint=ck)
            pooled_rows.append(_flatten_score(dict(common, population="all"), _score(rows, ck)))
            filtered = [r for key, r in indexed.items() if key[:3] not in excluded]
            pooled_rows.append(_flatten_score(dict(common, population="exclude_disputed"), _score(filtered, ck)))
    stats.validate_records(records)
    return dict(records=records, fold_metrics=fold_rows, file_metrics=file_rows,
                pooled_oof=pooled_rows)


def sensitivity_means(fold_rows):
    """Do not silently drop an empty filtered fold from the registered K folds."""
    grouped = defaultdict(list)
    for row in fold_rows:
        if row["population"] == "exclude_disputed":
            grouped[(row["task_id"], row["profile"], row["checkpoint"])].append(row)
    result = []
    for key, rows in sorted(grouped.items()):
        if any(row["n"] == 0 for row in rows):
            for metric in stats.METRICS:
                result.append(dict(task_id=key[0], profile=key[1], checkpoint=key[2],
                    metric=metric, mean=None, sample_sd=None,
                    status="unavailable_empty_filtered_fold",
                    empty_fold_seed=[dict(fold=r["fold"], seed=r["seed"]) for r in rows if not r["n"]]))
            continue
        records = [dict(task_id=r["task_id"], task_kind=r["task_kind"], profile=r["profile"],
                        checkpoint=r["checkpoint"], fold=r["fold"], seed=r["seed"],
                        metrics={m: r[m] for m in stats.METRICS}) for r in rows]
        result.extend(dict(row, status="complete") for row in stats.aggregate_metrics(records))
    return result


def directed_relation_reach(graph, profile):
    """Destinations of paths of <=1/<=2 actual message edges containing r.

    Seed each named v2 relation's destinations, then follow one outgoing edge
    of any registered relation. Explicit REV_* is a separate named relation.
    Auxiliary nodes participate in paths but are excluded from scored counts.
    """
    import networkx as nx
    from sco_models import graph_utils as gu
    from ..model_input import edge_data, materialize

    original = list(graph)
    working = gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(graph)))
    ids = gu.get_node_ids_dict(working)
    data = materialize(edge_data(working), profile)
    adjacency, targets = defaultdict(set), defaultdict(set)
    for canonical, endpoints in data.items():
        for src, dst in zip(endpoints[0].tolist(), endpoints[1].tolist()):
            u = original[ids[canonical[0]][src]]
            v = original[ids[canonical[2]][dst]]
            if graph.nodes[u]["source_file"] != graph.nodes[v]["source_file"]:
                raise ValueError("Cross-file message edge in mechanism graph")
            adjacency[u].add(v)
            if canonical[1] in V2_RELATIONS:
                targets[canonical].add(v)
    return {relation: {1: set(nodes),
                      2: set(nodes) | {v for u in nodes for v in adjacency[u]}}
            for relation, nodes in targets.items()}


def comparison_tables(plan, bundles, stage, selected_profile):
    """Identity-aligned errors/probabilities and directed node associations."""
    by_job = {(b["job"]["task_id"], b["job"]["profile"], b["job"]["fold"],
               b["job"]["seed"]): b for b in bundles}
    profiles = sorted({b["job"]["profile"] for b in bundles})
    comparisons = [(p, "G0") for p in profiles if p != "G0"]
    if stage == "complete" and "G3" in profiles and "G3R" in profiles:
        comparisons.append(("G3R", "G3"))
    changes, nodes, mechanism = [], [], []
    reach_cache = {}
    for task_id, task in plan["tasks"].items():
        record = task["record"]
        pairs = sorted({(b["job"]["fold"], b["job"]["seed"]) for b in bundles
                        if b["job"]["task_id"] == task_id})
        for profile, baseline in comparisons:
            for fold, seed in pairs:
                left = by_job[(task_id, profile, fold, seed)]
                right = by_job[(task_id, baseline, fold, seed)]
                a, b = left["indexed"], right["indexed"]
                if set(a) != set(b) or any(a[k]["target"] != b[k]["target"] for k in a):
                    raise ValueError("Paired predictions differ in frozen identity or target")
                for ck in CHECKPOINTS:
                    per_file = defaultdict(list)
                    corrected, regressed = set(), set()
                    for key in sorted(a):
                        new, old = a[key], b[key]
                        was = old[ck] == old["target"]
                        now = new[ck] == new["target"]
                        difference = new[ck + "_positive_probability"] - old[ck + "_positive_probability"]
                        per_file[key[:3]].append((was, now, difference, old[ck] != new[ck]))
                        if not was and now:
                            corrected.add(new.get("original_graph_node_id"))
                        if was and not now:
                            regressed.add(new.get("original_graph_node_id"))
                        if old[ck] != new[ck]:
                            nodes.append(dict(task_id=task_id, category=key[0], file=key[1],
                                source_sha256=key[2], original_graph_node_id=new.get("original_graph_node_id"),
                                fold=fold, seed=seed, profile=profile, baseline=baseline,
                                checkpoint=ck, target=new["target"], baseline_prediction=old[ck],
                                profile_prediction=new[ck], probability_delta=difference,
                                corrected=(not was and now), regressed=(was and not now)))
                    for (category, filename, source_sha), values in sorted(per_file.items()):
                        changes.append(dict(task_id=task_id, category=category, file=filename,
                            source_sha256=source_sha, fold=fold, seed=seed, profile=profile,
                            baseline=baseline, checkpoint=ck, n=len(values),
                            corrected=sum(not was and now for was, now, _, _ in values),
                            regressed=sum(was and not now for was, now, _, _ in values),
                            changed_predictions=sum(changed for _, _, _, changed in values),
                            changed_probabilities=sum(delta != 0 for _, _, delta, _ in values),
                            mean_abs_probability_delta=sum(abs(v[2]) for v in values) / len(values)))
                    if record["task"] == "node" and baseline == "G0" and profile == selected_profile:
                        cachekey = (task_id, profile, left["graph"]["sha256"])
                        if cachekey not in reach_cache:
                            reach_cache[cachekey] = directed_relation_reach(
                                read_graph(checked_ref(left["graph"])), profile)
                        for relation, hops in sorted(reach_cache[cachekey].items()):
                            for direction, values in (("corrected", corrected), ("regressed", regressed)):
                                for hop in (1, 2):
                                    mechanism.append(dict(task_id=task_id, profile=profile, baseline="G0",
                                        fold=fold, seed=seed, checkpoint=ck, change=direction,
                                        canonical=list(relation), relation=relation[1], within_hops=hop, changed_nodes=len(values),
                                        reached_nodes=len(values & hops[hop]),
                                        selection=("preregistered_G3R_interim" if stage == "A"
                                                   else "inner_validation_selected_Gstar"),
                                        causal_claim=False))
    return dict(error_changes=changes, changed_predictions=nodes, mechanism=mechanism)


def statistical_tables(records, stage):
    aggregate = stats.aggregate_metrics(records)
    paired, holm = [], []
    task_ids = sorted({r["task_id"] for r in records})
    profiles = sorted({r["profile"] for r in records})
    for task_id in task_ids:
        for ck in CHECKPOINTS:
            for metric in stats.METRICS:
                family = {}
                for profile in profiles:
                    if profile == "G0":
                        continue
                    item = stats.paired_comparison(records, task_id, profile,
                                                   checkpoint=ck, metric=metric)
                    paired.append(item)
                    family[profile] = item["p_raw"]
                correction = stats.holm_adjust(family, complete=(stage == "complete"))
                holm.append(dict(correction, task_id=task_id, checkpoint=ck, metric=metric))
                if stage == "complete" and {"G3", "G3R"} <= set(profiles):
                    paired.append(stats.paired_comparison(records, task_id, "G3R",
                        baseline="G3", checkpoint=ck, metric=metric))
    return dict(aggregate=aggregate, paired=paired, holm=holm)


def _manual_review(spec):
    from ..score_review import score_review
    results = []
    for source in spec.get("review_sources", []):
        report = score_review(checked_ref(source["csv"]), checked_ref(source["seal"]),
                              equivalence=(checked_ref(source["equivalence"])
                                           if source.get("equivalence") else None))
        complete = report["completed"]
        judged = sum(row["reviewed_denominator"] for row in report["relations"].values())
        results.append(dict(csv=source["csv"], seal=source["seal"],
            status="已完成" if complete else ("未完成" if not judged else "部分完成"),
            score=report))
    return dict(status=("未完成" if not results or all(r["status"] == "未完成" for r in results)
                       else "详见各冻结抽查文件"), sources=results,
                scope="Only supplied judgments; blank/unsure are not evidence of correctness.")


def _csv(path, rows):
    rows = list(rows)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("x", encoding="utf-8", newline="") as handle:
        if fields:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: (json.dumps(v, ensure_ascii=False, sort_keys=True)
                    if isinstance(v, (dict, list, tuple)) else v) for k, v in row.items()})


def _markdown_table(rows):
    if not rows:
        return "无记录。\n"
    fields = list(dict.fromkeys(key for row in rows for key in row))
    def cell(value):
        if isinstance(value, float):
            return "{:.6g}".format(value)
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(fields) + " |",
             "| " + " | ".join("---" for _ in fields) + " |"]
    lines.extend("| " + " | ".join(cell(row.get(key, "")) for key in fields) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def export_report(output, report):
    """Exclusive directory creation; report JSON and every table are bound."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    title = "Prompt 8 阶段 A 中间结果" if report["stage"] == "A" else "Prompt 8 完整结果"
    tables = report["tables"]
    for name, rows in tables.items():
        _csv(output / (name + ".csv"), rows)
    write_json(output / "report.json", report)
    lines = ["# " + title, "", report["interpretation"], "",
        "主要终点：best checkpoint，G3R−G0 的 outer-test Buggy-F1。last 为辅助结果。",
        "协议为 dfg-v2-nested-v1；inner_val 早停与选 best，outer_test 仅训练后评分。",
        "完整固定图参与前向，监督按文件划分；节点指标按原 HCG 节点，env_source 不计分。",
        "G0 不与旧 paper_kfold 或 original 层实现的历史分数直接比较。",
        "合约单种子 5 折只作描述统计；通常无零差值的精确双侧检验下限为 0.0625。",
        "节点 Wilcoxon 双侧、zero_method=zsplit；bootstrap 10000 次、seed 0。折非独立 seed，置信区间只作配对折描述。",
        "A12 为两组折分数的概率优势描述；不能将分数差异解释为纯依赖语义的因果贡献。",
        "阶段 A 四项 vs G0 的 Holm 校正等待阶段 B；方向消融单列，不混入四项校正家族。",
        "pooled OOF 与等权折均值分开；多 seed 时按每 seed OOF 列出，不复制样本充当独立试验。",
        "敏感性结果只排除预登记的 category/file/source SHA 身份，主结果不改标签或删样本。",
        "机制 1/2 跳遵循真实消息方向，含命名新增关系的至多 1/2 条边路径；不作为因果证据。",
        "历史分数曾在 94%–96% 附近；单 seed、少量折的微小差异需结合区间和配对方向。",
        "", "依赖边人工抽查精确率：" + report["manual_review"]["status"], ""]
    if report["stage"] == "A":
        lines.extend(["本中间结果固定比较 G3R 与 G0；不计算或暗示 G*，不改变阶段 B。", ""])
    else:
        lines.extend(["G* = " + report["selected_profile"] + "；只由封存内层验证选择。", ""])
    for name, rows in tables.items():
        # All metric/statistic tables are included, not only a favorable subset.
        lines.extend(["## " + name, "", _markdown_table(rows), ""])
    report_name = "REPORT_INTERIM_A.md" if report["stage"] == "A" else "REPORT.md"
    (output / report_name).write_text("\n".join(lines), encoding="utf8")
    paths = {str(p.relative_to(output)): _ref(p) for p in sorted(output.iterdir())}
    receipt = dict(version=VERSION, stage=report["stage"], plan=report["plan"],
                   report_sha256=paths[report_name]["sha256"], artifacts=paths,
                   selection=report.get("selection"))
    write_json(output / "report_receipt.json", receipt)
    return dict(output=str(output), directory=str(output), report=paths[report_name],
                receipt=_ref(output / "report_receipt.json"), artifacts=paths)


def build_report(plan_path, stage="A", verified_results=None, output=None):
    """Verify every selected fit; recompute all outputs from frozen identities."""
    from . import run
    plan_path = Path(plan_path).resolve()
    plan = run._load_plan(plan_path)
    if stage not in ("A", "complete"):
        raise ValueError("Reporting stage must be A or complete")
    spec_ref = plan["batch_registration"]["report_spec"]
    spec = validate_reporting_metadata(read_json(checked_ref(spec_ref)), plan)
    selected_profile, selection_ref = "G3R", None
    if stage == "complete":
        selection_path = plan_path.parent / "selection.json"
        seal = read_json(selection_path.with_name("selection.seal.json"))
        if seal["plan_sha256"] != sha256(plan_path):
            raise ValueError("Selection is bound to a different plan")
        selection_ref = dict(path=str(selection_path), sha256=seal["selection_sha256"])
        selected = read_json(checked_ref(selection_ref))
        if not selected.get("complete_matrix") or selected.get("outer_test_used") is not False:
            raise ValueError("Full report requires complete sealed inner selection")
        if selected != run._selection(plan, plan_path.parent):
            raise ValueError("Sealed selection differs from independently recomputed inner selection")
        selected_profile = selected["selected_profile"]
        for ref in selected["receipts"].values():
            checked_ref(ref)
    selected_jobs = [j for j in plan["jobs"] if stage == "complete" or j["profile"] in ("G0", "G3R")]
    bundles, fit_rows, relation_rows, receipts = [], [], [], {}
    observed = set()
    for job in selected_jobs:
        identity = run.job_id(job)
        if identity in observed:
            raise ValueError("Duplicate report job")
        observed.add(identity)
        completed = run._completed(plan_path.parent, plan, job, plan_path)
        if completed is None:
            raise ValueError("Incomplete report matrix: " + identity)
        attempt, result = completed
        if verified_results is not None and identity in verified_results:
            candidate = verified_results[identity]
            if candidate != result:
                raise ValueError("Caller verification differs from independently verified result")
        task, info, entry = run._prepared(plan, job)
        bundles.append(dict(job=job, predictions=read_json(attempt / "outer_test_predictions.json"),
            result=result, split=info["split"], graph=entry["graph"]))
        receipts[identity] = _ref(attempt / "receipt.json")
        resources = result["resources"]
        fit_rows.append(dict(job, best_epoch=result["best_epoch"], last_epoch=result["last_epoch"],
            parameter_count=result["parameter_count"], training_seconds=result["seconds"],
            peak_allocated_mib=resources.get("peak_allocated_mib"),
            peak_reserved_mib=resources.get("peak_reserved_mib"),
            minimum_free_mib=resources.get("minimum_free_mib"),
            memory_tight=result.get("memory_tight"), possible_memory_spill=result.get("possible_memory_spill"),
            checkpoint_roundtrip_exact=result["checkpoint_roundtrip_exact"]))
        gradients = {tuple(r["canonical"]): r for r in
                     result["gradient_audit"]["epochs"][0]["v2_relations"]}
        for row in entry["support"]["relations"]:
            if row["canonical"][1] in V2_RELATIONS:
                relation_rows.append(dict(job, **row,
                    first_epoch_message_gradient_l1=gradients[tuple(row["canonical"])]["message_gradient_l1"],
                    gradient_status=gradients[tuple(row["canonical"])]["status"]))
    # Matrix completeness and coverage are checked before any output is created.
    for task_id, task in plan["tasks"].items():
        expected = {(fold, seed, profile) for fold in task["folds"]
                    for seed in plan["seeds"] for profile in
                    (plan["profiles"] if stage == "complete" else ("G0", "G3R"))}
        actual = {(b["job"]["fold"], b["job"]["seed"], b["job"]["profile"])
                  for b in bundles if b["job"]["task_id"] == task_id}
        if actual != expected:
            raise ValueError("Missing or excess task/fold/profile result")
    prediction = prediction_tables(plan, bundles, spec)
    statistical = statistical_tables(prediction.pop("records"), stage)
    comparisons = comparison_tables(plan, bundles, stage, selected_profile)
    aggregate = statistical.pop("aggregate")
    tables = dict(prediction, **comparisons)
    tables["sensitivity_fold_means"] = sensitivity_means(tables["fold_metrics"])
    # Separate best/last tables rather than selecting whichever is favorable.
    tables["best_fold_means"] = [r for r in aggregate if r["checkpoint"] == "best"]
    tables["last_fold_means"] = [r for r in aggregate if r["checkpoint"] == "last"]
    tables.update(statistical)
    tables["fit_resources"] = fit_rows
    tables["relation_support_and_gradients"] = relation_rows
    tables["disputed_file_metrics"] = [r for r in tables["file_metrics"] if r["disputed"]]
    manual = _manual_review(spec)
    tables["manual_dependency_review"] = [dict(source=item["csv"]["path"],
        status=item["status"], relation=relation, **values)
        for item in manual["sources"] for relation, values in item["score"]["relations"].items()]
    report = dict(version=VERSION, stage=stage, plan=_ref(plan_path), spec=spec_ref,
        selected_profile=(None if stage == "A" else selected_profile), selection=selection_ref,
        interpretation=("中间结果：完整阶段 A 外层测试；不选 G*，阶段 B 未完成。"
                        if stage == "A" else "完整嵌套外层测试；G* 仅按内层验证选择。"),
        primary_endpoint="outer_test.best.buggy_f1: G3R minus G0",
        completed_jobs=len(bundles), fit_receipts=receipts, tables=tables,
        manual_review=manual)
    destination = output or plan_path.parent / "reports" / ("interim_A" if stage == "A" else "final")
    return export_report(destination, report)
