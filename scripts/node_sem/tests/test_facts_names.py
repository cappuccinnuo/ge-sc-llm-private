"""Deterministic spelling-bijection tests, never a production anonymous view."""
import copy
import pytest
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import reserved
from scripts.node_sem.facts import extract_source
from scripts.node_sem.facts_ast import walk
from scripts.node_sem.tests.test_facts_oracle import MANIFEST,FIXTURES
from scripts.node_sem.tests.test_facts_integration import graph_fixture,FILE


def rename(source):
    view=ProjectionView(source,FILE)
    selected=[n for n in walk(view.tree.root_node) if n.type=="identifier" and not reserved(n.text.decode())]
    names=sorted({n.text.decode() for n in selected})
    occupied={n.text.decode() for n in walk(view.tree.root_node) if n.type=="identifier"}
    mapping={}
    i=1
    for name in names:
        while "n"+str(i) in occupied:i+=1
        mapping[name]="n"+str(i);i+=1
    data=source.encode()
    for n in sorted(selected,key=lambda n:n.start_byte,reverse=True):
        data=data[:n.start_byte]+mapping[n.text.decode()].encode()+data[n.end_byte:]
    return data.decode(),{v:k for k,v in mapping.items()}


def restore(rows, inverse):
    result=copy.deepcopy(rows)
    for r in result.values():
        r["provenance"]["source_sha256"]=""
        r["names"]=sorted(inverse.get(x,x) for x in r["names"])
        for group,fields in (("dfg",("defs","uses")),("state",("reads","writes"))):
            for field in fields:
                for item in r[group].get(field,[]):item["var"]=inverse.get(item["var"],item["var"])
                # Facts use set semantics for deduplicated declaration names.
                if field in r[group]: r[group][field]=sorted(r[group][field],key=lambda x:repr(sorted(x.items())))
    return result


@pytest.mark.parametrize("case",MANIFEST["cases"],ids=lambda c:c["id"])
def test_all_handwritten_oracles_name_independent(case):
    source=(FIXTURES/case["source"]).read_text()
    changed,inverse=rename(source)
    old,_=extract_source(source,FILE)
    new,_=extract_source(changed,FILE,original_names=inverse)
    assert restore(old,{})==restore(new,inverse)


@pytest.mark.parametrize("case",[c for c in MANIFEST["cases"] if c["id"] in ("ii","jj","kk","ll","mm","nn")],ids=lambda c:c["id"])
def test_sealed_layers_name_independence_including_symbol_fields(case):
    source=(FIXTURES/case["source"]).read_text()
    changed,inverse=rename(source)
    s,g,e=graph_fixture("",source_override=source)
    t,h,f=graph_fixture("",source_override=changed)
    old,_=extract_source(s,FILE,graph=g,evidence=e)
    new,_=extract_source(t,FILE,graph=h,evidence=f,original_names=inverse)
    assert restore(old,{})==restore(new,inverse)
