"""Explain a below-one score on existing data, without normalizing a production score."""
import json
import re
from move import OUT, OLD, rows, checked, sha, base_contents
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.evaluation.benchmark import _IR_COUNTER, _nodes, _solc_metadata, score_graphs

CODE=re.compile(r"(?<=:= )[0-9a-fA-F]{100,}(?=\((?:string|bytes)\))")


def digest_field(old, new):
    if len(old)!=len(new):raise ValueError("creation code length differs")
    diffs=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
    if not diffs:raise ValueError("no literal change")
    for marker in (b"\x65bzzr0\x58\x20",b"\x65bzzr1\x58\x20",b"\x64ipfs\x58\x22\x12\x20"):
        d=old.rfind(marker,max(0,diffs[0]-54),diffs[0])+len(marker)
        if old[d-len(marker):d]!=marker or not d<=diffs[0]<=diffs[-1]<d+32:continue
        for a in range(max(0,d-90),d-len(marker)+1):
            for b in range(d+32,min(len(old)-1,d+120)):
                if (int.from_bytes(old[b:b+2],"big")==b-a and _solc_metadata(old[a:b]) and _solc_metadata(new[a:b])):
                    return dict(bytes=len(old),old_sha256=sha(old),new_sha256=sha(new),digest_start=d,
                                changed_bytes=len(diffs),cbor_start=a,cbor_end=b,after_length_bytes=len(old)-b-2)
    raise ValueError("difference extends beyond a recognized metadata digest")


def explain(record,base):
    raw=base_contents(base);site=record["site"];fn=site["file"];a,b,t=site["start"],site["end"],site["insert"]
    truth=json.loads(checked(base["graph_path"],base["graph_sha256"]))
    actual=json.loads(checked(record["graph_path"],record["graph_sha256"]))
    observed=_nodes(actual)
    changes=[]; text_updates={}
    for row in truth["nodes"]:
        name=row.get("filename","");k=list(row["key5"])
        if name==fn:
            if a<=k[3]<b:continue
            if k[3]>=b:k[3]+=2
            elif k[3]>=t:k[3]+=b-a+2
        new=observed[(name,tuple(k))]
        for i,(l,r) in enumerate(zip(row["ir"],new["ir"])):
            if _IR_COUNTER.sub("@",l)==_IR_COUNTER.sub("@",r):continue
            left,right=CODE.search(l),CODE.search(r)
            if not left or not right or not any("SOLIDITY_CALL type(" in x for x in row["ir"]):
                raise ValueError("additional non-creation operand difference")
            data=digest_field(bytes.fromhex(left.group()),bytes.fromhex(right.group()))
            replacement=r[:right.start()]+left.group()+r[right.end():]
            assert _IR_COUNTER.sub("@",replacement)==_IR_COUNTER.sub("@",l)
            new["ir"][i]=replacement
            text_updates[(name,tuple(k),i)]=(r,replacement)
            changes.append(dict(identity=[name,k],index=i,byte_change=data))
    from compile_repair.evaluation.benchmark import _identity
    for call in actual["calls"]:
        key=_identity(call["node"])+(call["ir_index"],)
        if key in text_updates and "text" in call["callee"]:
            old,new=text_updates[key]
            assert call["callee"]["text"]==old
            call["callee"]=dict(call["callee"],text=new)
    fragment=raw[fn][a:b]
    fixed=dict(raw)
    fixed[fn],repair=apply_patches(raw[fn],[Patch(a,b,fragment,b"","delete_function"),Patch(t,t,b"",b"\n"+fragment+b"\n","insert_function")])
    diagnostic=score_graphs(truth,actual,raw,raw,fixed,{},{fn:repair},0,True)
    assert changes and diagnostic["counter_correspondence"]["status"]!="rejected"
    assert all(diagnostic[k]["ratio"]==1 for k in ("kept","calls","cfg_edges"))
    assert diagnostic["lost"]==diagnostic["added"]==record["expected_moved_nodes"] and not diagnostic["missing_kept"]
    return dict(unit_id=record["unit_id"],changes=changes,diagnostic_ratios={k:diagnostic[k]["ratio"] for k in ("kept","cfg_edges","calls")},
                unchanged_official_score=record["score"],explanation="Complete kept facts match after isolating changes to the embedded compiler metadata digest. Production scores use the original literal.")
if __name__=="__main__":
    rec=json.loads((OUT/"documented_move_stop.json").read_bytes());base=next(b for b in rows(OLD/"bases.jsonl.gz") if b["unit_id"]==rec["unit_id"])
    result=explain(rec,base)
    from move import write
    write("literal_rest_of_graph.json",result)
    print(len(result["changes"]),result["diagnostic_ratios"])
