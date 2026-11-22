"""Run a predeclared fixed standard-JSON matrix on handwritten diagnostics fixtures."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import time
from batch import *
from compile_repair.toolchain.solc import diagnostic_template,load_trusted_compilers

fixture=ROOT/"compile_repair/tests/fixtures/cp4_1/diagnostics.json"
fixtures=json.loads(fixture.read_bytes())
compilers,_,_=load_trusted_compilers()

def run(pair):
    row,v=pair
    sources={name:{"content":src} for name,src in row["sources"].items()}
    spec={"language":"Solidity","sources":sources,"settings":{"outputSelection":{"*":{"*":["abi","evm.bytecode.object"]}}}}
    raw=json.dumps(spec,ensure_ascii=False,sort_keys=True).encode();compiler=compilers[v];argv=[compiler.path,"--standard-json"]
    start=time.monotonic()
    result=subprocess.run(argv,input=raw,capture_output=True,timeout=120,cwd=str(LOCAL))
    try:obj=json.loads(result.stdout)
    except (ValueError,UnicodeError):obj={}
    diags=[dict(type=x.get("type"),message=x.get("message",""),template=diagnostic_template(x.get("message","")),
                error_code=x.get("errorCode")) for x in obj.get("errors",[]) if isinstance(x,dict) and x.get("severity")=="error"]
    return dict(id=row["id"],version=v,compiler_sha256=compiler.sha256,command=argv,request_sha256=sha(raw),
                returncode=result.returncode,stdout_sha256=sha(result.stdout),stderr_sha256=sha(result.stderr),
                stderr_first=result.stderr.decode("utf8","replace").splitlines()[:1],diagnostics=diags,
                elapsed_seconds=round(time.monotonic()-start,6),cost_usd=0)

pairs=[(r,v) for r in fixtures if r["mode"]=="standard_json" for v in r["versions"]]
with ThreadPoolExecutor(max_workers=4) as pool:
    output_rows("standard_json_observations.jsonl.gz",pool.map(run,pairs))
by={r["id"]:r for r in fixtures}
catalog={r["id"]:[] for r in fixtures}
for obs in rows(OUT/"standard_json_observations.jsonl.gz"):
    target=by[obs["id"]]["template"]
    for d in obs["diagnostics"]:
        if d["template"]==target or (obs["id"]==55 and d["message"].startswith("Source file requires different compiler version")):
            catalog[obs["id"]].append(dict(version=obs["version"],type=d["type"],code=d["error_code"],request_sha256=obs["request_sha256"]))
saved("diagnostic_oracle.json",dict(fixtures_sha256=sha(fixture.read_bytes()),calls=len(pairs),
    fixtures=len(fixtures),type_matches={str(i):v for i,v in catalog.items()},exactly_witnessed=sum(bool(v) for v in catalog.values())))
print("matching templates",sum(bool(v) for v in catalog.values()),"of",len(fixtures),"calls",len(pairs))
