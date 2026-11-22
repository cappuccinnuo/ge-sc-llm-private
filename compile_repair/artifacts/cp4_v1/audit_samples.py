"""Independently join the frozen candidate plan, external edit receipts and the two trigger observations."""
from collections import Counter, defaultdict
from pathlib import Path
import time
from batch import ART, LOCAL, OUT, SEED, checked, frozen, json, load, receipt_rows, save, sha
from compile_repair.evaluation.benchmark import OPERATORS


def json_lines(path):
    with path.open(encoding="utf8") as stream:
        for line in stream:
            yield json.loads(line)


def key(row):
    return row["operator"], row["unit_id"]


def summarize_splits(name, rows):
    parts = defaultdict(list)
    for row in rows:
        parts[row["split"]].append(row)
    groups = {k: {r["group"] for r in v} for k, v in parts.items()}
    assert not groups.get("dev", set()) & groups.get("test", set()), name
    return {split: dict(samples=len(rr), units=len({r["unit_id"] for r in rr}), groups=len(groups[split]))
            for split, rr in sorted(parts.items())}


def main():
    start = time.monotonic()
    spec = json.loads(frozen(ART / "cp3_2_v1/d6_cp4_final.json"))["categories"]
    actual = {row["category"] for row in spec if row["cp4_operator"]}
    assert actual == set(OPERATORS) | {"slither_incomplete"}
    batches = load("sampling.json")
    inventory = list(receipt_rows("bases.jsonl.gz"))
    bases = {r["unit_id"]: r for r in inventory}
    plan = {key(r): r for r in receipt_rows("sample_plan.jsonl.gz")}
    runs = list(json_lines(OUT / "sample_receipts.jsonl"))
    expected = load("execution.json")
    assert (len(plan) == len(runs) == expected["completed"] == batches["planned"]
            and sha((OUT / "sample_receipts.jsonl").read_bytes()) == expected["receipt_sha256"])
    assert len(runs) == len({key(r) for r in runs}) and set(plan) == {key(r) for r in runs}
    strata = {(r["operator"], r["corpus"], r["series"]):dict(r) for r in batches["rows"]}
    totals = defaultdict(Counter)
    diagnostics = defaultdict(Counter)
    examples = defaultdict(dict)
    stages, calls = Counter(), Counter()
    updated = 0
    for row in runs:
        op, uid = key(row)
        base, pick = bases[uid], plan[(op,uid)]
        assert all(row[k]==pick[k] for k in ("group","split","series","corpus","seed"))
        assert all(row[k]==base[k] for k in ("group","split","series","corpus")) and row["seed"]==SEED
        directory = LOCAL / "samples" / op / uid
        manifest = json.loads(checked(directory / "mutation.json", row["mutation_sha256"]))
        result = json.loads(checked(directory / "units/environment/result.json", row["result_sha256"]))
        checked(directory / "invocations.jsonl", row["journal_sha256"])
        assert (Path(row["result_path"]) == directory/"units/environment/result.json"
                and Path(row["mutation_path"]) == directory/"mutation.json")
        assert manifest["operator"]==manifest["target"]==op and manifest["base_unit"]==uid
        assert manifest["version"]==base["version"] and manifest["settings"]==base["settings"]
        assert manifest["truth_graph_sha256"]==base["graph_sha256"] and manifest["stage"]==row["stage"]
        assert result["status"] == row["environment_status"]
        edit = manifest["edit"]
        raw = checked(edit["new_bytes_path"], edit["new_bytes_sha256"])
        assert len(raw) == edit["new_length"]
        assert row["selected_attempted"] == (row["stage"] == "solc")
        if row["environment_status"]=="success":
            outcome="resolved_by_environment"
        elif op in row["environment_categories"] and (row["stage"]!="solc" or op in row["selected_categories"]):
            outcome="included"
        else:
            outcome="not_triggered"
        assert row["outcome"] == outcome
        if outcome=="not_triggered":
            assert row["selected_first_line"] or row["environment_first_line"], (op,uid)
            diag=(tuple(row["selected_categories"]),tuple(row["environment_categories"]))
            diagnostics[op][diag]+=1
        ex=examples[op].get(outcome)
        if ex is None or uid<ex["unit_id"]:
            examples[op][outcome] = dict(unit_id=uid,corpus=base["corpus"],version=base["version"],
                entry_sha256=base["entry_sha256"],mutation_sha256=row["mutation_sha256"],result_sha256=row["result_sha256"],
                selected_categories=row["selected_categories"],primary=row["environment_categories"])
        strat=strata[(op,base["corpus"],base["series"])]
        strat[outcome]=strat.get(outcome,0)+1
        stages[row["stage"]]+=1
        calls["selected_solc"]+=int(row["selected_attempted"])
        calls["environment_solc"]+=row["environment_solc_calls"]
        calls["environment_slither"]+=row["environment_slither_calls"]
        updated+=1
        if updated%4000==0:
            print("audited",updated,flush=True)
    outcomes=("included","resolved_by_environment","not_triggered")
    for (op,_,_), row in strata.items():
        for name in ("bases","not_applicable","applicable","sampled")+outcomes:
            row.setdefault(name,0)
            totals[op][name]+=row[name]
        assert row["bases"]==row["applicable"]+row["not_applicable"]
        assert row["sampled"]==sum(row[n] for n in outcomes)
    for op in OPERATORS:
        assert sum(r["bases"] for (o,_,_),r in strata.items() if o==op) == len(bases)
        for corpus in {r["corpus"] for r in inventory}:
            assert sum(r["sampled"] for (o,c,_),r in strata.items() if o==op and c==corpus)<=200
    controls = list(json_lines(OUT/"controls.jsonl"))
    assert all(r["passed"] for r in controls) and len(controls)==200
    counts=Counter(row["outcome"] for row in runs)
    no_operator={r["category"]:r["no_source_corruption_operator_reason"] for r in spec if not r["cp4_operator"]}
    aggregate=dict(planned=len(plan),counts=counts,stages=stages,tool_calls=calls,seed=SEED,
        strata=[strata[k] for k in sorted(strata)],operators={op:dict(totals[op]) for op in OPERATORS},
        construction=OPERATORS,examples=examples,category_substitutions={op:[
            dict(selected=list(k[0]),primary=list(k[1]),units=n) for k,n in ds.most_common()]
            for op,ds in diagnostics.items()},no_operator=no_operator,
        splits={n:summarize_splits(n,rows) for n,rows in (("bases",inventory),("controls",controls),
            ("sampled",runs),("included",[r for r in runs if r["outcome"]=="included"]))},
        audited_external_receipts=len(runs),elapsed_seconds=round(time.monotonic()-start,3))
    save("benchmark_counts.json",aggregate)
    print("outcomes",dict(counts),"tool calls",dict(calls),"splits",aggregate["splits"],flush=True)


if __name__=="__main__":
    main()
