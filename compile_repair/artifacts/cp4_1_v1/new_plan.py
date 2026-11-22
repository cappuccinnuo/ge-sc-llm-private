"""Freeze new sample eligibility and count graph constants before observing any new outcome."""
from collections import Counter, defaultdict
from functools import lru_cache
from batch import *
from compile_repair.evaluation.benchmark import (SourceLayout, _IR_BYTECODE, base_contents,
    mutation_sites, normalized_node_ir, stratified_sample)
from compile_repair.toolchain.solc import lexical_tokens
OPS=("encoding","unimplemented_feature","unresolved_package_import")
SEED=20261122
VERSIONS=tuple(load("baseline.json")["compiler_sha256"])

@lru_cache(maxsize=64)
def layout(raw):
    return SourceLayout(raw)

def sites_for(base):
    sources=base_contents(base)
    imports=[]
    if base["project_root"]:
        meta=Path(base["result"]["result_path"]).with_name("project.json")
        imports=json.loads(meta.read_bytes())["imports"]
    sites=mutation_sites(base,sources,{n:layout(s) for n,s in sources.items()},imports,versions=VERSIONS)
    return sources,{name:sites[name] for name in OPS if name in sites}

def signature(site):
    name,a,b,value,action,stage=site
    facts=dict(file=name,start=a,end=b,action=action,stage=stage)
    if action=="package_dependency":
        facts.update({k:value[k] for k in ("package","layout_evidence","file_renames","logical_package_paths","remapping")})
        facts["import_edits"]=[dict(file=n,start=x,end=y,replacement_sha256=sha(v))
            for (n,x,y),v in sorted(value["import_edits"].items())]
    else:
        facts["replacement_sha256"]=sha(value)
    return sha(json.dumps(facts,ensure_ascii=False,sort_keys=True).encode())

def ir_facts(base,sources):
    raw=checked(base["graph_path"],base["graph_sha256"])
    result=Counter()
    if b"SOLIDITY_CALL type()(" not in raw:return {}
    for node in json.loads(raw)["nodes"]:
        ops=node["ir"]
        if not any("SOLIDITY_CALL type()(" in v for v in ops) or not any(_IR_BYTECODE.search(v) for v in ops):continue
        result["embedded_hex_nodes"]+=1
        if normalized_node_ir(ops)[1]:result["verified_trailer_nodes"]+=1
        a=node["key5"][3]
        fragment=sources[node.get("filename","")][a:a+node["length"]]
        words=[t[3] for t in lexical_tokens(fragment)]
        if any(x==b"." and y==b"creationCode" for x,y in zip(words,words[1:])):
            result["creation_code_nodes"]+=1
        elif any(x==b"." and y==b"runtimeCode" for x,y in zip(words,words[1:])):
            result["runtime_code_nodes"]+=1
        else:result["unresolved_origin_nodes"]+=1
    return dict(result)

def examine(base):
    sources,sites=sites_for(base)
    # Reproduce the first draw as measured. The numbered supplement handles
    # entries inside the same published package and proves the union draw.
    package_site = sites.get("unresolved_package_import")
    if package_site and package_site[4] == "package_dependency":
        plan = package_site[3]
        original, logical = next(iter(plan["logical_package_paths"].items()))
        suffix = logical[len(plan["package"]):]
        prefix = original[:-len(suffix)]
        if next(iter(sources)).startswith(prefix + "/"):
            sites.pop("unresolved_package_import")
    row={k:base[k] for k in ("unit_id","corpus","series","group","split")}
    row["sites"]={op:signature(site) for op,site in sites.items()}
    if "unresolved_package_import" in sites:
        site=sites["unresolved_package_import"]
        if site[4]!="package_dependency":raise ValueError("Package lacks a published layout in new plan")
        row["package"]=site[3]["package"]
    row["ir"]=ir_facts(base,sources)
    return row

def main():
    assert load("struct_codegen_crosscheck.json")["passed"]
    assert load("creation_manual.json")["passed"]
    assert len(VERSIONS)==92
    frozen(OLD/"bases.jsonl.gz")
    avail=defaultdict(list);stats=defaultdict(Counter);packages=Counter();ir=Counter();by_corpus=defaultdict(Counter)
    total=0
    def collect():
        nonlocal total
        for row in ordered_work(examine,rows(OLD/"bases.jsonl.gz"),3):
            total+=1
            for op in OPS:
                k=(op,row["corpus"],row["series"]);stats[k]["bases"]+=1
                if op in row["sites"]:
                    stats[k]["applicable"]+=1;avail[op,row["corpus"]].append(row)
                else:stats[k]["not_applicable"]+=1
            if row.get("package"):packages[row["corpus"],row["package"]]+=1
            for k,v in row["ir"].items():
                ir[k]+=v;ir[k+"_units"]+=1;by_corpus[row["corpus"]][k+"_units"]+=1
            if total%2000==0:print("eligibility",total,flush=True)
            yield row
    output_rows("new_eligibility.jsonl.gz",collect())
    if total!=16136:raise ValueError("Base population changed")
    draw=[]
    for (op,corpus),items in sorted(avail.items()):
        for row in stratified_sample(items,200,SEED,op):
            k=(op,corpus,row["series"]);stats[k]["sampled"]+=1
            sample={k:row[k] for k in ("unit_id","corpus","series","group","split")}
            draw.append(dict(sample,operator=op,seed=SEED,site_sha256=row["sites"][op],package=row.get("package") if op=="unresolved_package_import" else None))
    output_rows("new_plan.jsonl.gz",draw)
    saved("new_sampling.json",dict(bases=total,planned=len(draw),seed=SEED,cap_per_operator_corpus=200,
        plan_sha256=sha((OUT/"new_plan.jsonl.gz").read_bytes()),eligibility_sha256=sha((OUT/"new_eligibility.jsonl.gz").read_bytes()),
        strata=[dict(operator=o,corpus=c,series=s,**v) for (o,c,s),v in sorted(stats.items())],
        applicable_packages=[dict(corpus=c,package=p,units=v) for (c,p),v in sorted(packages.items())],
        embedded_bytecode=ir,embedded_by_corpus=by_corpus))
    print("eligible bases",total,"new plan",len(draw),"bytecode",dict(ir),flush=True)
if __name__=="__main__":main()
