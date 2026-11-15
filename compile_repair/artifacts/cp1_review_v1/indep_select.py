"""Independent ascending selection for CP1 sample with Claude's toolchain (GitHub static solc,
Slither 0.11.6 via Slither(path), Codex's D3 functions only for the D3 predicate).
Usage: python indep_select.py <repo> <jobs.json> <solc_dir> <out.jsonl>"""
import json, os, subprocess, sys
repo, jobs, solc_dir, outp = sys.argv[1:5]
sys.path.insert(0, repo)
from slither import Slither
from compile_repair.toolchain import slither as T
with open(outp, "w") as fh:
    for j in json.load(open(jobs)):
        tried, sel = [], None
        for v in j["ordered"]:
            solc = os.path.join(solc_dir, "solc-" + v)
            if not os.path.exists(solc):
                tried.append([v, "no_local_binary"]); break
            p = subprocess.run([solc, j["path"], "--combined-json", "abi,ast,bin"], capture_output=True, text=True, cwd="/")
            if p.returncode != 0:
                tried.append([v, "solc_rc%d" % p.returncode]); continue
            try:
                sl = Slither(j["path"], solc=solc, solc_disable_warnings=True)
                a, b = T.node_facts(sl, [j["path"]]), T.contract_coverage(sl, [j["path"]])
                ok = a["mapping_complete"] and b["complete"]
                tried.append([v, "d3" if ok else "d3_fail"])
            except Exception as e:
                tried.append([v, "slither_" + type(e).__name__]); ok = False
            if ok:
                sel = v; break
        fh.write(json.dumps({"case": j["case"], "codex_selected": j["selected"], "codex_status": j["status"],
                             "claude_selected": sel, "tried": tried, "codex_attempted": j["attempted"]}) + "\n"); fh.flush()
