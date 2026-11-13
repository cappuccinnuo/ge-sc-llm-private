"""Apply Codex's CP0.1 D3 code (node_facts + contract_coverage) under this venv's Slither.
Usage: python codex_d3_batch.py <repo> <jobs.jsonl> <solc_dir> <out.jsonl>"""
import json, os, sys, time
repo, jobs, solc_dir, out = sys.argv[1:5]
sys.path.insert(0, repo)
from slither import Slither
from compile_repair.toolchain import slither as T

with open(out, "w") as fh:
    for line in open(jobs):
        j = json.loads(line)
        rec = {"id": j["id"], "version": j["version"]}
        t0 = time.time()
        try:
            sl = Slither(j["path"], solc=os.path.join(solc_dir, "solc-" + j["version"]), solc_disable_warnings=True)
            a = T.node_facts(sl, [j["path"]])
            b = T.contract_coverage(sl, [j["path"]])
            rec.update(ok=True, d3_a=a["mapping_complete"], d3_b=b["complete"], counts=a["counts"],
                       missing=b["missing"], unexpected=b["unexpected"],
                       key5_ir=[[n["key5"], n["ir"]] for n in a["nodes"]])
        except Exception as e:
            rec.update(ok=False, error=type(e).__name__ + ": " + (str(e).splitlines() or [""])[0][:200])
        rec["seconds"] = round(time.time() - t0, 3)
        fh.write(json.dumps(rec) + "\n"); fh.flush()
