"""Direct supported-series probe and a standard-JSON type oracle."""
from dataclasses import asdict
import time
from batch import *
from compile_repair.toolchain.solc import compile_file, load_trusted_compilers, version_tuple
compilers,_,_=load_trusted_compilers()
versions=sorted(load("baseline.json")["compiler_sha256"],key=version_tuple)
body=b"struct CP41Item { uint n; } CP41Item[] private cp41Items; function cp41Copy() public { CP41Item[] memory m = new CP41Item[](1); cp41Items = m; }"
source=LOCAL/"struct_support.sol"
with source.open("xb") as fp:fp.write(b"pragma solidity >=0.4.0; contract Archive { "+body+b" }\n")
results=[]
for v in versions:
    call=compile_file(source,compilers[v])
    if call.timed_out:raise TimeoutError(v)
    results.append(asdict(call))
success=[r["compiler"]["version"] for r in results if r["returncode"]==0]
saved("struct_support.json",dict(calls=results,source_sha256=sha(source.read_bytes()),source=source.read_text(),
    first_supported=success[0] if success else None,contiguous=bool(success and success==versions[versions.index(success[0]):])))
print("first support",success[:1],flush=True)
raw=frozen(ART/"cp4_review_v1/fixtures/samename.sol");observed=[]
for v in ("0.5.17","0.6.12","0.7.6","0.8.0","0.8.38"):
    compiler=compilers[v];argv=[compiler.path,"--standard-json"]
    req=dict(language="Solidity",sources={"Probe.sol":{"content":raw.decode()}},settings={"outputSelection":{"*":{"*":["abi"]}}})
    inp=json.dumps(req).encode();start=time.monotonic();q=subprocess.run(argv,input=inp,capture_output=True,timeout=120)
    diags=[d for d in json.loads(q.stdout)["errors"] if d.get("severity")=="error"]
    observed.append(dict(version=v,compiler_sha256=compiler.sha256,command=argv,returncode=q.returncode,
        source_sha256=sha(raw),request_sha256=sha(inp),stdout_sha256=sha(q.stdout),stderr=q.stderr.decode(),
        diagnostics=diags,seconds=time.monotonic()-start,cost_usd=0))
saved("same_name_types.json",observed)
print([(r["version"],[(d["type"],d.get("errorCode")) for d in r["diagnostics"]]) for r in observed])
