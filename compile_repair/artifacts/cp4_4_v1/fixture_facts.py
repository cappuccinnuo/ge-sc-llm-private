"""Attach node-level comparisons to the six compiled review cases and the data-flow negatives."""
import json
from probe import OUT,SCRATCH,cases,write,sha
from compile_repair.evaluation.benchmark import (_comparison_graph,_correspondence,_score_facts,
    _ordinary_correspondence,_nodes,score_graphs)
from compile_repair.tests.test_cp44 import competing_definitions

def main():
    proof={}
    observed=json.loads((OUT/"review_scores.json").read_bytes())
    archive=json.loads((OUT/"review_inputs.json").read_bytes())
    for kind in ("partial","yul"):
        proof[kind]={}
        for label,(orig,mid,fixed,d,r) in cases(kind):
            def graph(n):
                p=SCRATCH/kind/n/"graph.json"
                assert sha(p)==archive[kind][n]["graph.json"]
                return _comparison_graph(json.loads(p.read_bytes()),{},True)[0]
            truth,actual=graph("truth"),graph(label)
            args=({"":orig},{"":mid},{"":fixed},{"":d},{"":r})
            maps,near,level=_correspondence(*args);positions={}
            _score_facts(truth,actual,args[0],args[2],maps,near,level,True,{},kept_positions=positions)
            counts=dict(structural=0,conflict=0,definition=0,switch=0,participating=0)
            corrected,_,_=_ordinary_correspondence(truth,actual,positions,maps,None,args[0],args[2],counts)
            left,right=_nodes(truth),_nodes(corrected)
            unequal=[]
            for k,v in positions.items():
                if any(left[k][f]!=right[v][f] for f in ("node_type","ir")):
                    unequal.append(dict(truth=k,candidate=v,ir_before=left[k]["ir"],ir_after=right[v]["ir"]))
            s=observed[kind][label]["score"]
            assert s["counter_correspondence"]["nodes"]==counts
            assert len(unequal)==s["kept"]["units"]-s["kept"]["equal"]
            proof[kind][label]=dict(unequal=unequal,counts=counts)
    proof["wrong_counter_uses"]={}
    files={"":b"contract C {}"}
    for name in ("cross_node_use","swapped_definitions"):
        score=score_graphs(*competing_definitions(name),files,files,files,{},{},0,True)
        assert not score["exact"] and score["kept"]["equal"]==2 and score["counter_correspondence"]["status"]=="partial"
        proof["wrong_counter_uses"][name]=score
    write(OUT/"fixture_facts.json",proof)
if __name__=="__main__":main()
