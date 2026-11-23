"""Read the sealed before/after pair and list unrecognized IR definition forms; no tool invocation."""
from collections import Counter
import json
from pathlib import Path
import sys

DEST = Path(__file__).resolve().parent
sys.path.insert(0,str(DEST.parent))
from resume_migrations import OLD, checked, load_inputs, restore_sample, base_contents, rows, sha
from compile_repair.evaluation.benchmark import (_comparison_graph, _at_original, _correspondence, _nodes,
                                                 _IR_COUNTER, _COUNTER_DEFINITION)
def main():
    stop=json.loads((DEST/"stop.json").read_bytes())
    uid=stop["unit_id"]
    base=next(b for b in rows(OLD/"bases.jsonl.gz") if b["unit_id"]==uid)
    obs=load_inputs()[1][uid]
    src=base_contents(base)
    m,damaged,moved,first,second=restore_sample(base,src,obs,migration=True)
    rev={b:a for a,b in m["file_renames"].items()}
    after={rev.get(k,k):v for k,v in moved.items()}
    maps,_,_=_correspondence(src,damaged,after,first,second)
    gs=[_comparison_graph(json.loads(checked(stop[k]["graph_path"],stop[k]["graph_sha256"])),n,True)[0]
        for k,n in (("graph",{}),("migration_graph",rev))]
    old,new=map(_nodes,gs)
    changes,defined,locations={},set(),{}
    skeletons=True
    for (name,k),node in old.items():
        offset=k[3]
        if name in maps and offset<len(src[name]):
            segment=_at_original(maps[name][2],offset)
            offset=segment.new_start+offset-segment.original_start
        elif name in maps:offset=len(after[name])
        other=new[name,k[:3]+(offset,)+k[4:]]
        for x,y in zip(node["ir"],other["ir"]):
            a,b=_IR_COUNTER.split(x),_IR_COUNTER.split(y)
            skeletons &= a[::2]==b[::2]
            for u,v in zip(a[1::2],b[1::2]):
                assert changes.setdefault(u,v)==v
                locations.setdefault(u,[]).append((x,k[2]))
            defn=_COUNTER_DEFINITION.match(x)
            if defn:defined.add(defn.group(1))
    missing={a:b for a,b in changes.items() if a!=b and a not in defined}
    assert len(set(changes.values()))==len(changes) and skeletons
    print("missing",missing)
    for n in list(missing)[:18]:
        print(n, locations[n][:5])
if __name__=="__main__":main()
