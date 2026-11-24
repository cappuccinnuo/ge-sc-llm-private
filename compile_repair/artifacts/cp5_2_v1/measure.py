"""CP5.2 reproducible measurements against sealed CP5.1 results, using fresh output paths."""
import gzip
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ART = HERE.parent
ROOT = ART.parents[1]
OLD = ART / "cp5_1_v1"
LOCAL = ROOT.parent / "compile-repair-local" / HERE.name
sys.path[:0] = [str(ROOT), str(OLD)]
from population import entry, population, load, save
from evidence import verified_index, steps_facts
from moved_benchmark import bases
from compile_repair.core.model import Compilation, Compiler, Provenance, Change, Segment
from compile_repair.core.store import ArtifactStore, emit, read_checked_json, sha256
from compile_repair.evaluation.benchmark import stratified_sample
from compile_repair.pipeline import repair_unit
from compile_repair.toolchain.project import resolve_project, ProjectIndex
from compile_repair.toolchain.slither import check_profile, run_slither
from compile_repair.toolchain.solc import load_trusted_compilers


def frozen(name):
    path = OLD / "packed" / (name + ".jsonl.gz")
    seal = read_checked_json(OLD / "seal.json", "42eff2b03f203ceeb5714dcbc6e2cdacd0d659f8058b3c39eec9f2f217018914")
    assert sha256(path) == seal["files_excluding_this_seal"]["packed/" + path.name]["sha256"]
    return list(map(json.loads, gzip.decompress(path.read_bytes()).splitlines()))


def active():
    stop = HERE / "measurement_stop.json"
    if stop.exists():
        raise RuntimeError("A measurement stopped; see " + str(stop))


def jsonline(name):
    return (HERE / (name + ".jsonl")).open("x", encoding="utf8")


def graph_of(record, folder):
    if record["status"] != "success":
        assert not (folder / "graph.json").exists()
        return None
    last = record["attempts"][-1]["slither"]
    assert last["d3"] and last.get("graph_usable", True)
    path = folder / "graph.json"
    assert sha256(path) == last["graph_sha256"]
    return last["graph_sha256"]


def real(part, count):
    check_profile("production")
    index = verified_index()
    compilers, _, _ = load_trusted_compilers()
    targets, _ = population()
    baseline = {r["unit_id"]:r for r in frozen("real_full")}
    assert set(baseline) == set(targets) and len(targets) == 9138
    name = "real_{:02d}".format(part)
    summary = Counter()
    with jsonline(name) as out:
        for i, item in enumerate(list(targets.values())[part::count]):
            active()
            uid = item["unit_id"]
            old = baseline[uid]
            assert old["rule"] == "oldest" and old["limit"] == 21
            rec = read_checked_json(old["result_path"], old["result_sha256"])
            previous_hash = graph_of(rec, Path(old["result_path"]).parent)
            unit, project, inventory = entry(item)
            store = ArtifactStore(LOCAL / name / uid)
            with store.journal("invocations.jsonl") as journal:
                new = repair_unit(unit, compilers, store, journal, project=project, project_index=inventory,
                                  offline_index=index, dependency_policy="oldest", dependency_limit=21)
            facts = steps_facts(store.path, uid, new)
            folder = Path(facts["result_path"]).parent
            current_hash = graph_of(asdict(new), folder)
            affected = bool(set(item["primary"]) & {"missing_relative_file","io_error"})
            row = dict(unit_id=uid, corpus=item["corpus"], split=item["split"], primary=item["primary"],
                       affected=affected, prior_d3=old["d3"], d3=facts["d3"], prior_graph_sha256=previous_hash,
                       graph_sha256=current_hash, old_receipt_sha256=old["result_sha256"],
                       result_path=facts["result_path"], result_sha256=facts["result_sha256"],
                       accepted_steps=facts["accepted_steps"], mechanical=facts["mechanical"],
                       equal=(old["d3"], previous_hash) == (facts["d3"], current_hash))
            emit(out, row)
            if not affected and not row["equal"]:
                raise ValueError("Unchanged external cohort differs: " + uid)
            summary[(affected,old["d3"],facts["d3"])] += 1
            if (i+1) % 100 == 0:
                print(name, i+1, flush=True)
    save(HERE / (name + ".json"), dict(rows=sum(summary.values()), counts=[[*k,v] for k,v in sorted(summary.items())],
         sha256=sha256(HERE / (name + ".jsonl"))))


def ir_targets(cohort):
    if cohort == "real_dev":
        for r in frozen("real_dev"):
            if r["rule"] == "oldest" and r["d3"]:
                yield (r["unit_id"], r["corpus"], None, r["result_path"], r["result_sha256"], None)
    elif cohort == "benchmark":
        for r in frozen("benchmark"):
            if r["status"] == "success":
                yield (r["unit_id"], r["corpus"], r["operator"], r["result_path"], r["result_sha256"], r["graph_sha256"])
    elif cohort == "cp3":
        rows = [r for r in bases().values() if r["corpus"] != "MANDO"]
        for r in stratified_sample(rows, 1000, 20261122, "cp5_2_partial_ir"):
            yield (r["unit_id"], r["corpus"], None, r["result"]["result_path"],
                   r["result"]["result_sha256"], r["graph_sha256"])


def ir(cohort):
    check_profile("production")
    rows = list(ir_targets(cohort))
    assert len(rows) == {"real_dev":1131, "benchmark":1240, "cp3":1000}[cohort]
    name = "ir_" + cohort
    counts = Counter()
    with jsonline(name) as out:
        for uid, corpus, op, path, digest, graph_digest in rows:
            active()
            rec = read_checked_json(path, digest)
            attempt = rec["attempts"][-1]
            old = attempt["slither"]
            assert old["profile"] == "production" and old["d3"]
            expect = graph_digest or old["graph_sha256"]
            assert old["graph_sha256"] == expect
            truth = read_checked_json(Path(path).with_name("graph.json"), expect)
            raw = dict(attempt["solc"])
            raw["compiler"] = Compiler(**raw["compiler"])
            build = Compilation(**raw)
            project = None
            if old.get("project"):
                info = old["project"]
                members = tuple(Path(f["path"]) for f in info["files"])
                project = resolve_project(info["root"], info["entry"], info["remappings"],
                    ProjectIndex(info["root"], members), info.get("additional_entries", ()))
                assert json.loads(json.dumps(project.manifest())) == info
            actual = run_slither(build, profile="production", project=project)
            assert actual["d3"] and actual.get("graph_usable", True)
            flags = actual["partial_ir"]
            names = flags["incorrectly_constructed_contracts"]
            native = dict(truth, nodes=[{k:v for k,v in n.items() if k != "provenance"} for n in truth["nodes"]])
            row = dict(unit_id=uid, corpus=corpus, operator=op, result_path=path, result_sha256=digest,
                       historical_graph_sha256=expect, raw_facts_equal=native == actual["graph"],
                       invocation={k:actual[k] for k in ("source_path","source_sha256","version","compiler_sha256",
                           "command","equivalent_solc_argv","profile","d3","d3_a","d3_b","elapsed_seconds","cost_usd",
                           "error_first_line","preceding_observed_solc_returncode")}, **flags)
            emit(out, row)
            counts["units"] += 1
            counts["contracts"] += len(names)
            counts["flagged_contract_units"] += bool(names)
            counts["top_level_errors"] += flags["top_level_errors"]
            counts["top_level_error_units"] += bool(flags["top_level_errors"])
            counts["any_flag_units"] += bool(names or flags["top_level_errors"])
            counts["raw_facts_equal"] += row["raw_facts_equal"]
            if counts["units"] % 100 == 0:
                print(name, counts["units"], flush=True)
    save(HERE / (name + ".json"), dict(counts=counts, sha256=sha256(HERE / (name + ".jsonl"))))


def typed_record(raw):
    proof = {}
    for name, p in raw["provenance"].items():
        fields = dict(p)
        fields["segments"] = tuple(Segment(**s) for s in p["segments"])
        changes = []
        for change in p["changes"]:
            change = dict(change)
            for key in ("old","new"):
                assert change[key]["encoding"] == "hex"
                change[key] = bytes.fromhex(change[key]["data"])
            changes.append(Change(**change))
        fields["changes"] = tuple(changes)
        proof[name] = Provenance(**fields)
    return SimpleNamespace(**dict(raw, provenance=proof))


if __name__ == "__main__":
    if sys.argv[1] == "ir":
        ir(sys.argv[2])
    elif sys.argv[1] == "real":
        real(int(sys.argv[2]), int(sys.argv[3]))
