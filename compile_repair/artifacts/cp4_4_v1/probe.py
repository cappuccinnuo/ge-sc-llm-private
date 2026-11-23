"""Compile the two public review fixtures once; inspect and later score their saved graphs."""
import hashlib,json,sys
from pathlib import Path
from review_sources import cases
from compile_repair.evaluation.benchmark import score_graphs,_score_facts,_correspondence,_nodes
from compile_repair.tests.test_cp42 import graph
from compile_repair.toolchain.solc import load_trusted_compilers

OUT=Path(__file__).resolve().parent
SCRATCH=OUT.parents[3]/"compile-repair-local"/OUT.name/"review"
def write(path,record):
    with path.open("x",encoding="utf8") as fp:
        json.dump(record,fp,ensure_ascii=False,indent=2);fp.write("\n")
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main(action):
    compile_new=action=="capture"
    receipts={}
    result={}
    for kind in ("partial","yul"):
        folder=SCRATCH/kind
        def saved_graph(raw,name):
            p=folder/name
            if compile_new:
                g=graph(raw,p,compiler)
                write(p/"graph.json",g)
            else:
                for f,h in archive[kind][name].items():assert sha(p/f)==h
                g=json.loads((p/"graph.json").read_bytes())
            assert (p/"A.sol").read_bytes()==raw
            receipts[kind][name]={f:sha(p/f) for f in ("A.sol","graph.json","solc.json","slither.json")}
            return g
        if compile_new:
            folder.mkdir(parents=True)
            compiler=load_trusted_compilers()[0]["0.8.38"]
        else:
            archive=json.loads((OUT/"review_inputs.json").read_bytes())
        receipts[kind]={};result[kind]={}
        for label,(orig,mid,fixed,d,r) in cases(kind):
            if label=="A":truth=saved_graph(orig,"truth")
            actual=saved_graph(fixed,label)
            args=({"":orig},{"":mid},{"":fixed},{"":d},{"":r})
            score=score_graphs(truth,actual,*args,0,True)
            maps,near,level=_correspondence(*args)
            kept={}
            _score_facts(truth,actual,args[0],args[2],maps,near,level,True,{},kept_positions=kept)
            left,right=_nodes(truth),_nodes(actual)
            structure=[]
            for k,v in kept.items():
                before,after=left[k],right[v]
                delta=[a for a in before.keys()|after.keys() if a not in ("key5","ir") and before.get(a)!=after.get(a)]
                if delta:
                    structure.append(dict(key=k,target=v,fields=sorted(delta),old_length=before["length"],new_length=after["length"],
                                          raw_equal=before["node_type"]==after["node_type"] and before["ir"]==after["ir"]))
            result[kind][label]=dict(score=score,non_ir_differences=structure)
    if compile_new:write(OUT/"review_inputs.json",receipts)
    write(OUT/("review_baseline.json" if compile_new else "review_scores.json"),result)
    for kind,scenarios in result.items():
        print(kind,[(case,r["score"]["kept"],r["non_ir_differences"]) for case,r in scenarios.items()])
if __name__=="__main__":main(sys.argv[1])
