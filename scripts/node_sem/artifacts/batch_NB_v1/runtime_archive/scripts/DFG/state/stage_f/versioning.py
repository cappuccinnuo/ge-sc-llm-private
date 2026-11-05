"""Conjunctive pragma evidence, never an arbitrary compiler selection."""
import re,csv,hashlib
from pathlib import Path
from ...frontend import text
from ...models import Unsupported
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def interval(source,root):
 expressions=[re.sub(r"^pragma\s+solidity\s*|;\s*$","",text(source,n)).strip()
              for n in root.named_children if n.type=="pragma_directive" and re.match(r"pragma\s+solidity\b",text(source,n))]
 if not expressions:return None
 lo,hi=(0,0,0),(999,0,0)
 pattern=r"(\^|~|>=|<=|>|<|=)?\s*(\d+)\.(\d+)\.(\d+)"
 for expr in expressions:
  if "||" in expr or not re.search(pattern,expr) or re.sub(pattern,"",expr).strip():raise Unsupported("F: unsupported pragma expression")
  for m in re.finditer(pattern,expr):
   op=m.group(1) or "=";v=tuple(int(m.group(i)) for i in (2,3,4));patch=(v[0],v[1],v[2]+1)
   if op in ("=","^","~"):
    upper=patch if op=="=" else (v[0],v[1]+1,0) if op=="~" else (v[0]+1,0,0) if v[0] else (0,v[1]+1,0) if v[1] else patch
    lo=max(lo,v);hi=min(hi,upper)
   elif op in (">",">="):lo=max(lo,patch if op==">" else v)
   else:hi=min(hi,patch if op=="<=" else v)
 if lo>=hi:raise Unsupported("F: empty pragma intersection")
 return lo,hi
def recorded_version(source,metadata):
 if metadata is None:return None
 # Metadata is data, never executable code. Validate its row and both byte hashes here.
 source_sha=hashlib.sha256(source.encode("utf8")).hexdigest()
 csv_path=Path(metadata["csv_path"]);origin=Path(metadata["source_path"])
 if source_sha!=metadata["source_sha256"] or sha(origin)!=source_sha or sha(csv_path)!=metadata["csv_sha256"]:
  raise Unsupported("F: version metadata/source hash mismatch")
 rows=list(csv.DictReader(csv_path.open()))
 matched=[r for r in rows if r["file"]==metadata["row_file"]]
 if len(matched)!=1 or matched[0]["compiled version"]!=metadata["version"]:
  raise Unsupported("F: ambiguous version metadata row")
 if (csv_path.parent/metadata["row_file"]).resolve()!=origin.resolve():raise Unsupported("F: metadata source path mismatch")
 if not re.fullmatch(r"\d+\.\d+\.\d+",metadata["version"]):raise Unsupported("F: unsupported recorded compiler version")
 return tuple(map(int,metadata["version"].split(".")))
def mode_for(source,root,iv):
 if iv is None:raise Unsupported("F: no version evidence for lexical scope")
 lo,hi=iv
 if (0,4,0)<=lo and hi<=(0,5,0):mode="legacy"
 elif (0,5,0)<=lo<(0,9,0):mode="modern"
 else:raise Unsupported("F: interval crosses lexical scope boundary")
 if any(re.search(r'experimental\s+["\x27]v0\.5\.0["\x27]',text(source,n)) for n in root.named_children if n.type=="pragma_directive"):mode="modern"
 return mode
def effective_interval(source,root,metadata=None):
 raw=interval(source,root);v=recorded_version(source,metadata)
 if v:
  if raw and not raw[0]<=v<raw[1]:raise Unsupported("F: recorded compiler contradicts pragma")
  return (v,(v[0],v[1],v[2]+1)),{"kind":"dataset_recorded_compiled_version","metadata":metadata,"independently_compiled":False,"pragma_interval":raw}
 return raw,{"kind":"source_pragma_intersection","pragma_interval":raw,"exact_compiler":None,"independently_compiled":False}
def available(view,name):
 lohi=view.version_interval
 windows={"require":((0,4,10),(0,9,0)),"assert":((0,4,10),(0,9,0)),"revert":((0,4,10),(0,9,0)),
 "selfdestruct":((0,4,0),(0,9,0)),"suicide":((0,4,0),(0,5,0)),
 "call":((0,4,0),(0,9,0)),"send":((0,4,0),(0,9,0)),"transfer":((0,4,10),(0,9,0)),"staticcall":((0,5,0),(0,9,0))}
 return bool(lohi and name in windows and windows[name][0]<=lohi[0] and lohi[1]<=windows[name][1])
