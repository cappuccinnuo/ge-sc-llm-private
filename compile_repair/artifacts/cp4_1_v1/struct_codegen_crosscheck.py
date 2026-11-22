"""Test the same reviewed source and compiler under the two authorized output selections."""
import time
from dataclasses import asdict
from batch import *
from compile_repair.toolchain.solc import compile_file, load_trusted_compilers

request = OUT / "struct_codegen_review_request.json"
saved("struct_codegen_authorization.json", dict(date="2026-11-22", source="user reply in current CP4.1 session",
    quote="同意交叉核对及条件口径", request_sha256=sha(request.read_bytes()), cost_usd=0))
review = ART / "cp4_review_v1/fixtures/struct_copy2.sol"
source = LOCAL / "review_fixture" / review.name
source.parent.mkdir(exist_ok=False)
with source.open("xb") as fp:
    fp.write(frozen(review))
compiler = load_trusted_compilers()[0]["0.8.38"]
command = [compiler.path, "--combined-json", "abi", source.name]
start = time.monotonic()
q = subprocess.run(command, cwd=str(source.parent), capture_output=True, timeout=120)
abi = dict(command=command, returncode=q.returncode, stderr=q.stderr.decode("utf8","replace"),
           stdout_sha256=sha(q.stdout), elapsed_seconds=time.monotonic()-start, cost_usd=0)
compiled = compile_file(source, compiler)
passed = (q.returncode == 0 and bool(json.loads(q.stdout).get("contracts")) and not compiled.timed_out
          and compiled.returncode != 0 and "only supported by the IR pipeline" in compiled.stderr)
saved("struct_codegen_crosscheck.json", dict(source=str(source), source_sha256=sha(source.read_bytes()),
    compiler="0.8.38", compiler_sha256=compiler.sha256, abi_only=abi, production=asdict(compiled),
    prior_matrix_sha256=sha((OUT/"struct_support.json").read_bytes()), passed=passed))
print("same fixture, binary, output requests", q.returncode, compiled.returncode, passed)
if not passed:
    raise SystemExit(2)
