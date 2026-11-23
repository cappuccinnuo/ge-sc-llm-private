"""Locate complete, length-delimited solc CBOR around the differing bytes, without removing them."""
import json
import re
from pathlib import Path
from move import OUT, OLD, rows, checked, sha, base_contents
from compile_repair.evaluation.benchmark import _solc_metadata, normalized_node_ir

def main():
    r=json.loads((OUT/"documented_move_stop.json").read_bytes())
    base=next(b for b in rows(OLD/"bases.jsonl.gz") if b["unit_id"]==r["unit_id"])
    values=[]
    for file,h in ((base["graph_path"],base["graph_sha256"]),(r["graph_path"],r["graph_sha256"])):
        graph=json.loads(checked(file,h))
        node=next(n for n in graph["nodes"] if n["key5"][:2]==["WaultSwapFactory","createPair(address,address)"] and any("SOLIDITY_CALL type(address)(" in op for op in n["ir"]))
        ops,_=normalized_node_ir(node["ir"])
        values.append(bytes.fromhex(re.search(r"([0-9a-fA-F]{1024,})",ops[1]).group()))
    old,new=values
    diff=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
    spans=[]
    for start in range(max(0,diff[0]-100),diff[0]+1):
        for end in range(diff[-1]+1,min(len(old)-1,diff[-1]+101)):
            if (int.from_bytes(old[end:end+2],"big")==end-start and old[end:end+2]==new[end:end+2]
                    and _solc_metadata(old[start:end]) and _solc_metadata(new[start:end])):
                spans.append(dict(start=start,end=end,length_bytes=2,trailing_bytes=len(old)-end-2))
    src=base_contents(base)[r["site"]["file"]]
    facts=dict(unit_id=r["unit_id"],version=base["version"],raw_kept=r["score"]["raw"]["kept"],
               raw_calls=r["score"]["raw"]["calls"],cfg=r["score"]["cfg_edges"],total_bytes=len(old),changed_bytes=len(diff),
               first=diff[0],last=diff[-1],passed_cbor_structure_and_length_on_both_sides=spans,
               has_hash_of_creation_code=bool(re.search(rb"keccak256\s*\(\s*(?:abi\.encodePacked\s*\(\s*)?type\s*\([^)]*\)\s*\.\s*creationCode",src)),
               literal_sha256=[sha(old),sha(new)],moved_lost=r["score"]["lost"],moved_added=r["score"]["added"],
               cause="The kept IR embeds different literal creation bytecode. Identical complete literals cannot be claimed; CP4.1 recognizes only a final CBOR trailer.",
               proposal="Keep the strict raw result, the frozen denominator and all prior observations. Count a known below-one result only with a checked byte-level explanation. Continue the remaining 124. Do not add a normalization rule; stop for other unexplained differences.")
    with (OUT/"creation_literal_request.json").open("x",encoding="utf8") as fp:json.dump(facts,fp,indent=2);fp.write("\n")
    print(spans,facts["has_hash_of_creation_code"])
if __name__=="__main__":main()
