"""Check the scoring entry on one predetermined development observation for each index-independent operator."""
from benchmark_inputs import ART, HERE, ROOT, samples, pinned
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(ART/"cp4_1_v1"))
sys.path.insert(0, str(ROOT))
from replay import restore_sample
from compile_repair.core.store import emit
from compile_repair.evaluation.benchmark import base_contents, dependency_repair_observation
from compile_repair.toolchain.solc import load_trusted_compilers

rows = samples()
base_rows = gzip.decompress(pinned(ART/"cp4_v1/bases.jsonl.gz")).splitlines()
bases = {r["unit_id"]:r for r in map(json.loads, base_rows)}
compilers, versions, _ = load_trusted_compilers()
scratch = ROOT.parent/"compile-repair-local/cp5_v1/dev_probes"
scratch.mkdir(parents=True, exist_ok=False)
with (HERE/"dev_probes.jsonl").open("x") as log:
    for operator in ("standard_json_input","missing_relative_file","io_error","closure_version_conflict"):
        row = next(r for r in rows if r["split"] == "dev" and r["operator"] == operator)
        base = bases[row["unit_id"]]
        original = base_contents(base)
        manifest, damaged, _, damage, _ = restore_sample(base, original, row)
        result = dependency_repair_observation(base, manifest, original, damaged, damage,
            Path(row["mutation_path"]).parent/"damaged", compilers, versions, None, "latest",
            scratch/(operator+"_"+row["unit_id"]))
        emit(log, result)
        print(operator, row["unit_id"], result["status"], result["score"]["exact"], flush=True)
        assert result["score"]["removed_by_repair"] == 0
