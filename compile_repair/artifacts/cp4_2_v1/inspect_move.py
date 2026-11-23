"""Inspect the saved kept-node differences of a move without re-running either tool."""
import json
from pathlib import Path
import re
import sys
from move import OUT, OLD, base_contents, rows, checked, sha
from compile_repair.evaluation.benchmark import _comparison_graph, _IR_COUNTER
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches

def inspect(record):
    base=next(b for b in rows(OLD/"bases.jsonl.gz") if b["unit_id"]==record["unit_id"])
    truth,_=_comparison_graph(json.loads(checked(base["graph_path"],base["graph_sha256"])),{},True)
    actual,_=_comparison_graph(json.loads(checked(record["graph_path"],record["graph_sha256"])),{},True)
    site=record["site"];name=site["file"];a,b,t=site["start"],site["end"],site["insert"]
    changed={(v.get("filename",""),tuple(v["key5"])):v for v in actual["nodes"]}
    diffs=[]
    for n in truth["nodes"]:
        k=list(n["key5"]);fn=n.get("filename","")
        if fn==name:
            if a<=k[3]<b:continue
            if k[3]>=b:k[3]+=2
            elif k[3]>=t:k[3]+=b-a+2
        other=changed[(fn,tuple(k))]
        for i,(x,y) in enumerate(zip(n["ir"],other["ir"])):
            left=_IR_COUNTER.sub("COUNTER",x);right=_IR_COUNTER.sub("COUNTER",y)
            if left==right:continue
            hexes=re.compile(r"[0-9a-fA-F]{40,}")
            lx,rx=hexes.findall(left),hexes.findall(right)
            row=dict(owner=k[:2],node=k[2:],operation_index=i,old_chars=len(x),new_chars=len(y),
                     old_shape=hexes.sub("<hex>",left)[:330],new_shape=hexes.sub("<hex>",right)[:330],
                     same_except_hex=hexes.sub("<hex>",left)==hexes.sub("<hex>",right),hex_evidence=[])
            for old,new in zip(lx,rx):
                if len(old)%2 or len(new)%2:continue
                c,d=bytes.fromhex(old),bytes.fromhex(new)
                offsets=[i for i,(v,w) in enumerate(zip(c,d)) if v!=w]
                row["hex_evidence"].append(dict(old_bytes=len(c),new_bytes=len(d),old_sha256=sha(c),new_sha256=sha(d),
                                                different_overlap_bytes=len(offsets),first_differences=offsets[:12]))
            diffs.append(row)
    return diffs
if __name__=="__main__":
    r=json.loads((OUT/"documented_move_stop.json").read_bytes())
    result=inspect(r)
    with (OUT/"move_ir_difference.json").open("x",encoding="utf8") as fp:json.dump(result,fp,indent=2);fp.write("\n")
    print(json.dumps(result)[:1800])
