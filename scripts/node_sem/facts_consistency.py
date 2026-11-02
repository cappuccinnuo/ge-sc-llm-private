"""Read-only NS-P3a3 boolean compatibility check against SHA-pinned NS-P3a2."""
import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from .facts_ast import AstSemantics, key, walk
from .facts_guards import GuardAnalyzer, branches
from .facts_io import PLAN
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, write, ref

REFERENCE = Path(__file__).parent/"artifacts/ns_p3a3/reference"

def historical_guards():
    hashes=read(REFERENCE/"sha.json")
    modules={}
    for name in ("facts_boolean","facts_guards"):
        path=REFERENCE/(name+".py")
        if hashlib.sha256(path.read_bytes()).hexdigest()!=hashes[path.name]:
            raise ValueError("Historical comparator changed")
        spec=importlib.util.spec_from_file_location("scripts.node_sem._historical_"+name,str(path))
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name]=module
    # Only the archived comparator's own dependency is assigned; no frozen
    # or production module is monkeypatched, and no bytecode is rebound.
    modules["facts_guards"].sender_condition=modules["facts_boolean"].sender_condition
    return modules["facts_guards"].GuardAnalyzer

def scan(source,file,old_cls):
    sem=AstSemantics(ProjectionView(source,file))
    old,new=old_cls(sem),GuardAnalyzer(sem)
    cases={}
    for n in sem.nodes:
        c=new._require(n)
        if c is not None: cases[(key(c),1)]=c
        if n.type in ("if_statement","while_statement","for_statement","do_while_statement"):
            c=n.child_by_field_name("condition")
            if c is None: continue
            cases[(key(c),1)]=c
            if n.type=="if_statement":
                _,yes,no=branches(n)
                if no is not None or new._early(n) is not None: cases[(key(c),-1)]=c
    counts=Counter(); differences=[]
    for (ident,polarity),c in sorted(cases.items()):
        bad=any(n.type=="member_expression" and n.child_by_field_name("object") is not None
                and n.child_by_field_name("object").type=="binary_expression" for n in walk(c))
        original_bad = bad
        array_bad = any(n.type == "array_access" and
            n.child_by_field_name("base") is not None and
            n.child_by_field_name("base").type == "binary_expression" and
            any(sem.text(x.child_by_field_name("operator")) in ("&&", "||")
                for x in walk(n.child_by_field_name("base")))
            for n in walk(c))
        bad = bad or array_bad
        counts["original_rule_misparsed" if original_bad else "original_rule_well_grouped"] += 1
        a=old._equalities(c,polarity,{})
        b=new._equalities(c,polarity,{})
        av,bv=(sorted(a[0]),a[2]),(sorted(b[0]),b[2])
        kind="misparsed" if bad else "well_grouped"
        counts[kind]+=1
        if av!=bv:
            counts[kind+"_differences"]+=1
            if not original_bad: counts["original_rule_well_grouped_differences"]+=1
            differences.append(dict(file=file,source_sha256=sem.view.sha256,
                condition=list(ident),polarity=polarity,text=sem.text(c),
                old=av,new=bv,misparsed=bad,
                original_rule_misparsed=original_bad,array_base_misparsed=array_bad,
                ast=c.sexp()))
    return dict(counts=dict(counts),differences=differences)

def audit(output):
    old=historical_guards(); results={}
    fixtures=Path(__file__).parent/"tests/fixtures/nodesem_oracle"
    oracle=read(fixtures/"expected.json")
    inputs={"oracle":{c["source"]:dict(path=str(fixtures/c["source"]),
            sha256=hashlib.sha256((fixtures/c["source"]).read_bytes()).hexdigest()) for c in oracle["cases"]}}
    plan=read(PLAN)
    inputs.update({t:task["record"]["sources"] for t,task in plan["tasks"].items()})
    cache={}
    for task,sources in inputs.items():
        counts=Counter();diffs=[]
        for file,r in sorted(sources.items()):
            src=checked(r).read_text(encoding="utf8")
            ck=(file,r["sha256"])
            if ck not in cache: cache[ck]=scan(src,file,old)
            item=cache[ck];counts.update(item["counts"]);diffs.extend(item["differences"])
        results[task]=dict(files=len(sources),counts=dict(counts),differences=diffs)
        print(task,dict(counts),flush=True)
    result=dict(reference=ref(REFERENCE/"sha.json"),groups=results,
        scope="All require/assert and if/loop conditions; negative polarity for else/early-exit; original sources",
        passed=not any(v["counts"].get("well_grouped_differences",0) for v in results.values()))
    if Path(output).exists():raise FileExistsError(output)
    write(output,result)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",required=True)
    result=audit(p.parse_args().out)
    if not result["passed"]:raise ValueError("Well-grouped boolean compatibility differs; see evidence")

if __name__=="__main__": main()
