"""Run frozen CP5 benchmark splits against the authorized, sealed offline index."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

from benchmark_inputs import ART, HERE, ROOT, samples, pinned
sys.path.insert(0,str(ART/"cp4_1_v1"))
sys.path.insert(0,str(ROOT))
from replay import restore_sample
from compile_repair.core.store import emit, sha256
from compile_repair.evaluation.benchmark import base_contents, dependency_repair_observation
from compile_repair.evaluation.report import dependency_benchmark_summary
from compile_repair.rules.dependencies import OfflineIndex
from compile_repair.toolchain.solc import load_trusted_compilers

POLICIES = ("latest","oldest","closest")


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open("x",encoding="utf8") as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2)
        f.write("\n")


def approved_index():
    auth = read(HERE/"d23/authorization.json")
    root = Path(auth["storage"])
    delivery = read(HERE/"d23/download_summary.json")
    archives = root/"archives.json"
    db = OfflineIndex(root/"index")
    assert db.seal["archive_catalog_sha256"] == sha256(archives) == delivery["catalog_sha256"]
    catalog = read(archives)
    expected = {(n,v) for n,versions in auth["exact_releases"].items() for v in versions}
    assert expected == {(n,v) for n,versions in db.packages.items() for v in versions}
    assert db.seal["releases"] == len(expected) == 172
    assert all(r["verified"] for r in catalog["releases"])
    return db


def main(mode):
    if mode not in ("dev","test"):
        raise ValueError("Expected dev or test")
    index = approved_index()
    plans = samples()
    bases = {r["unit_id"]:r for r in map(json.loads,gzip.decompress(pinned(ART/"cp4_v1/bases.jsonl.gz")).splitlines())}
    compilers, frozen, _ = load_trusted_compilers()
    output = HERE/("benchmark_"+mode)
    local = ROOT.parent/"compile-repair-local/cp5_v1"/output.name
    freeze_path = HERE/"benchmark_dev/policy.json"
    if mode == "test":
        freeze = read(freeze_path)
        assert freeze["status"] == "frozen" and freeze["index_sha256"] == index.seal["index_sha256"]
        policies = (freeze["policy"],)
    else:
        policies = POLICIES
    output.mkdir(exist_ok=False)
    local.mkdir(parents=True,exist_ok=False)

    def run(row, policy):
        base = bases[row["unit_id"]]
        original = base_contents(base)
        manifest, damaged, _, injury, _ = restore_sample(base,original,row)
        result = dependency_repair_observation(base,manifest,original,damaged,injury,
            Path(row["mutation_path"]).parent/"damaged",compilers,frozen,index,policy,
            local/policy/row["operator"]/row["unit_id"])
        result["mutation_sha256"] = row["mutation_sha256"]
        return result

    package_rows = [r for r in plans if r["split"]==mode and r["operator"]=="unresolved_package_import"]
    scores = {}
    for policy in policies:
        results = []
        with (output/("packages_"+policy+".jsonl")).open("x",encoding="utf8") as log:
            for row in package_rows:
                item=run(row,policy)
                emit(log,item)
                assert item["score"]["removed_by_repair"]==0
                results.append(item)
        scores[policy]=dependency_benchmark_summary(results)[mode]["unresolved_package_import"]
    if mode == "dev":
        # Prefer a policy that attains both empirical maxima. A genuine tradeoff
        # is reported with both statistics before a choice can affect held-out runs.
        compile_best = max(v["compiled"] for v in scores.values())
        bytes_best = max(v["original_package_files"]["equal"] for v in scores.values())
        winners = [k for k in POLICIES if scores[k]["compiled"]==compile_best and
                   scores[k]["original_package_files"]["equal"]==bytes_best]
        freeze = dict(status="frozen" if winners else "tradeoff", policy=winners[0] if winners else None,
                      tied=winners, order_for_identical_dev_metrics=POLICIES, scores=scores,
                      index_sha256=index.seal["index_sha256"], dev_units=len(package_rows))
        write(freeze_path,freeze)
        if not winners:
            raise ValueError("Development policies trade byte recovery for compilation success")
    selected = freeze["policy"]
    results = list(map(json.loads,(output/("packages_"+selected+".jsonl")).read_bytes().splitlines()))
    with (output/"other_operators.jsonl").open("x",encoding="utf8") as log:
        for row in plans:
            if row["split"]!=mode or row["operator"]=="unresolved_package_import":
                continue
            item=run(row,selected)
            emit(log,item)
            assert item["score"]["removed_by_repair"]==0
            results.append(item)
    assert len(results)==sum(r["split"]==mode for r in plans)
    write(output/"summary.json",dict(policy=selected,split=mode,units=len(results),
                                    metrics=dependency_benchmark_summary(results)))


if __name__=="__main__":
    main(sys.argv[1])
