import hashlib, json, os, sys
repo, solc, src, cwd = sys.argv[1:5]
sys.path.insert(0, repo)
from compile_repair.core.model import Compiler
from compile_repair.toolchain import solc as S
c = Compiler(os.path.basename(solc).split("-")[1], solc, hashlib.sha256(open(solc, "rb").read()).hexdigest())
argv = S.command(src, c, cwd=cwd)
os.chdir(cwd)
import subprocess
p = subprocess.run(argv, capture_output=True, text=True)
print(json.dumps({"cwd": cwd, "argv_tail": argv[3:], "rc": p.returncode, "err": S.error_first_line(p.stderr) if p.returncode else None}))
