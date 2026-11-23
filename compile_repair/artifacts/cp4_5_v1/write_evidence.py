"""Check both graphs for the prior binding of each apparent redefinition."""
from collections import Counter
import gzip
from pathlib import Path
import hashlib
import json
import re

out=Path(__file__).resolve().parent
def records(path):
    with gzip.open(path,"rt") as fp:yield from map(json.loads,fp)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def graph(p,h):
    path=Path(p)
    assert sha(path)==h
    return {(n.get("filename",""),tuple(n["key5"])):n for n in json.loads(path.read_bytes())["nodes"]}
bases={r["unit_id"]:r for r in records(out.parent/"cp4_v1/bases.jsonl.gz")}
moves={r["unit_id"]:r for r in map(json.loads,(out.parent/"cp4_2_v1/moves_completed.jsonl").read_text().splitlines())}
counts={}
for mode in ("moves","exact"):
    counts[mode]=Counter()
    cases=out/(mode+"_causes.jsonl.gz")
    assert sha(cases)==json.loads((out/(mode+"_causes.json")).read_bytes())["breakdown_sha256"]
    for row in records(cases):
        uid=row["unit_id"];base=bases[uid]
        left=graph(base["graph_path"],base["graph_sha256"])
        if mode=="exact":
            assert base["graph_sha256"]==row["graph_sha256"]
            right=left
        else:
            right=graph(moves[uid]["graph_path"],row["graph_sha256"])
        for d in row["definitions"]:
            first,last=d["sites"]
            kinds=set()
            for g,side,h in ((left,"key","truth_sha256"),(right,"peer","actual_sha256")):
                assert first[side]==last[side] and first["ir_index"]<last["ir_index"]
                name,key=first[side]
                ops=g[name,tuple(key)]["ir"]
                a,b=first["ir_index"],last["ir_index"]
                assert all(hashlib.sha256(ops[i].encode()).hexdigest()==s[h] for i,s in ((a,first),(b,last)))
                lhs=ops[a].split("(",1)[0]
                if re.fullmatch(re.escape(lhs)+r"\(.*\) = \[.*\]",ops[b]):
                    assert lhs.startswith("REF_") and " -> " in ops[a]
                    kinds.add("REF_array_initialization")
                else:
                    deletion=re.fullmatch(re.escape(lhs)+r" = delete (REF_\d+) *",ops[b])
                    assert deletion
                    selectors=[op for op in ops[a+1:b] if re.match(re.escape(deletion[1])+r"\(.*\) -> "+re.escape(lhs)+r"(?:\[|\.)",op)]
                    assert len(selectors)==1,(uid,lhs,deletion[1])
                    kinds.add(lhs.split("_")[0]+"_delete_reference")
            assert len(kinds)==1
            counts[mode][kinds.pop()]+=1
request=dict(status="historical_comparison_stopped",counts=counts,
             previous_approval="Only explicit (->destination) REF write-through was authorized.",
             proposal="For ordinary scoring only, also recognize two specific SlithIR writes: a typed array initialization through a previously bound REF in the same node, and a delete whose reference operand is bound to the named destination in that node. Verify names on every occurrence, preserve genuine multiple definitions and the raw score. Add positive, stale-use and genuine multi-definition cases, rerun all three historical comparisons and the suites in a new batch.",
             rows={m:{n:sha(out/(m+n)) for n in ("_summary.json","_causes.jsonl.gz")} for m in counts})
with (out/"write_semantics_request.json").open("x",encoding="utf8") as f:
    json.dump(request,f,indent=2);f.write("\n")
print(counts)
