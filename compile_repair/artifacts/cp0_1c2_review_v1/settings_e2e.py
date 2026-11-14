"""End-to-end: Codex's compile_file + run_slither(production) with and without settings.
Usage: python settings_e2e.py <repo> <solc_dir>"""
import hashlib, json, os, sys
repo, solc_dir = sys.argv[1:3]
sys.path.insert(0, repo); os.chdir(repo)
from compile_repair.core.model import Compiler
from compile_repair.toolchain.solc import compile_file
from compile_repair.toolchain.slither import run_slither
F = "compile_repair/tests/fixtures/features/"
cases = [("0.8.24", "y0824_tstore_asm.sol", ()), ("0.8.24", "y0824_tstore_asm.sol", ("--evm-version", "cancun")),
         ("0.8.24", "h0824_blob.sol", ("--evm-version", "cancun")),
         ("0.8.26", "h0826_require_error.sol", ()), ("0.8.26", "h0826_require_error.sol", ("--via-ir",)),
         ("0.8.25", "y0824_tstore_asm.sol", ()), ("0.8.27", "h0826_require_error.sol", ())]
for v, f, st in cases:
    p = os.path.join(solc_dir, "solc-" + v)
    c = Compiler(v, p, hashlib.sha256(open(p, "rb").read()).hexdigest())
    comp = compile_file(F + f, c, settings=st)
    rec = {"v": v, "f": f, "settings": list(st), "argv_tail": comp.command[-4:], "rc": comp.returncode, "err": comp.error_first_line}
    if comp.returncode == 0:
        r = run_slither(comp, profile="production")
        rec.update(d3=r["d3"], slither_settings=r.get("settings"), solc_args=r["command"].get("solc_args"),
                   platform=r.get("crytic_compile_platform"), nodes=len(r["nodes"]))
    print(json.dumps(rec))
try:
    compile_file(F + "h0824_blob.sol", c, settings=("--optimize",))
except ValueError as e:
    print(json.dumps({"reject": str(e)}))
