"""Check exact delivery paths; preserve only enumerated raw output whitespace."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).resolve().parent;OLD=B.with_name("cp3_continue_v1")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.run(["git"]+list(args),cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
base=json.loads((OLD/"working_inventory.json").read_text())
paths=set(base["files"])|{str((OLD/"working_inventory.json").relative_to(ROOT))}
paths.update(str(p.relative_to(ROOT)) for p in B.rglob("*") if p.is_file())
assert git("branch","--show-current").stdout.decode().strip()=="compile-repair"
assert not git("diff","--cached","--name-only").stdout
old=json.loads((OLD/"whitespace_review.json").read_text())["raw_output_preservation_exemptions"]
exemptions={}
for path,row in old.items():
 assert sha(ROOT/path)==row["sha256"]
 exemptions[path]=dict(row,reason="Previously sealed exact raw compiler/test output")
tracked=set(git("ls-files").stdout.decode().splitlines())
check=git("diff","--check")
failures=[]
for path in sorted(paths-tracked-set(old)):
 result=git("diff","--no-index","--check","/dev/null",str(ROOT/path))
 if result.returncode:
  if Path(path).suffix in (".stdout",".stderr") and "/artifacts/" in path:
   exemptions[path]={"sha256":sha(ROOT/path),"reason":"Exact raw tool output; no prose/code exception","check_output":result.stdout.decode("utf8","replace")}
  else:failures.append({"path":path,"returncode":result.returncode,"output":result.stdout.decode("utf8","replace"),"stderr":result.stderr.decode("utf8","replace")})
result={"tracked_returncode":check.returncode,"tracked_stdout":check.stdout.decode("utf8","replace"),"tracked_stderr":check.stderr.decode("utf8","replace"),"candidate_files":len(paths),"raw_output_preservation_exemptions":exemptions,"new_file_failures":failures,"passed":check.returncode==0 and not failures,"scope":"Exact recorded delivery paths only; no broad code/document exemption; no staging yet."}
with (B/"whitespace_review.json").open("x") as f:json.dump(result,f,indent=2);f.write("\n")
print(json.dumps({k:v for k,v in result.items() if k!="raw_output_preservation_exemptions"}),flush=True)
print("exact_raw_exemptions",len(exemptions),flush=True)
sys.exit(0 if result["passed"] else 2)
