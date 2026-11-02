"""NS-P2b read-only CPU diagnostics. Does not train or regenerate embeddings."""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
from collections import Counter, defaultdict
import argparse
import bisect
import hashlib
import json
from pathlib import Path
import re
import numpy as np

from scripts.node_sem.carrier import load_modality
from scripts.node_sem.text_view import load_context, cut_span, normalize
from scripts.DFG.frontend import leaves
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.benchmark_v2.anon_parity import node_code_view
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import reserved
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref
from scripts.DFG.dfg_v2.benchmark_v2 import execution as legacy
from scripts.DFG.dfg_v2.experiment.run import _code_refs

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
TASKS = ("reentrancy_node","access_control_node","reentrancy_contract","access_control_contract")
EXPECTED = ((841,735,8770),(669,561,5411),(1269,1155,12427),(1005,893,9002))
PLAN = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/plan.json"
ART = ROOT / "scripts/node_sem/artifacts"
WORD = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")
MARKER = re.compile(r"re_ent|txorigin",re.I)


def write_new(name, value):
    with (OUT/name).open("x",encoding="utf8") as stream:
        json.dump(value,stream,indent=2,ensure_ascii=True)
        stream.write("\n")


def stats(values):
    a=np.asarray(values,dtype=np.float64)
    if not a.size: return dict(count=0,mean=None,median=None,p05=None,min=None,max=None)
    assert np.isfinite(a).all()
    return dict(count=int(a.size),mean=float(a.mean()),median=float(np.median(a)),
                p05=float(np.percentile(a,5)),min=float(a.min()),max=float(a.max()))


def unit(a):
    a=np.asarray(a,dtype=np.float64)
    n=np.linalg.norm(a,axis=1)
    assert np.isfinite(a).all() and (n>0).all()
    return a/n[:,None]


def cosine_pairs(a, left, right):
    return np.clip(np.einsum("ij,ij->i",a[left],a[right]),-1.0,1.0)


def load_inputs(task, view):
    p=ART/"text_v1"/view/task/"manifest.json"
    seal=read(p.with_name("manifest.seal.json"))
    assert checked(seal["manifest"])==p
    m=read(p); rows=[json.loads(s) for s in checked(m["input_text"]).read_text().splitlines()]
    assert rows==m["rows"]
    for row in rows:
        assert hashlib.sha256(row["text"].encode("utf8")).hexdigest()==row["text_sha256"]
    ep=ART/"ns_p2/encoded"/view/task/"manifest.json"
    es=read(ep.with_name("manifest.seal.json"))
    assert checked(es["manifest"])==ep
    em=read(ep)
    assert em["input_text"]==m["input_text"]
    assert em["task_id"]==task and em["view"]==view
    assert [a["row_key"] for a in em["rows"]]==[a["row_key"] for a in rows]
    values=load_modality(ref(ep))
    assert set(values)=={a["row_key"] for a in rows}
    matrix=np.stack([values[row["row_key"]] for row in rows])
    return rows,matrix,dict(text_manifest=ref(p),encoding_manifest=ref(ep),vector=em["data"])


def numbering_task(task,expected):
    original,ov,orefs=load_inputs(task,"original")
    anon,av,arefs=load_inputs(task,"anonymous")
    assert len(original)==len(anon)==len(av)==len(ov)
    groups=defaultdict(list)
    for i,(a,b) in enumerate(zip(original,anon)):
        for key in ("row_key","file","source_sha256","node_type","code_sha256","cut_mode"):
            assert a[key]==b[key]
        if a["node_type"]!="env_source" and a["cut_mode"]!="placeholder":
            groups[(a["node_type"],a["text"])].append(i)
    shared={key:ix for key,ix in groups.items() if len({original[i]["file"] for i in ix})>1}
    split={key:ix for key,ix in shared.items() if len({anon[i]["text"] for i in ix})>1}
    assert (len(shared),len(split),sum(map(len,shared.values())))==expected
    au,ou=unit(av),unit(ov)
    pools=defaultdict(list)
    for (typ,text),ix in sorted(groups.items()):
        # Uniform original-text groups, then uniform anonymous variants.
        unique={}
        for i in ix:unique.setdefault(anon[i]["text"],i)
        pools[typ].append([unique[t] for t in sorted(unique)])
    by_type=defaultdict(list); old_type=defaultdict(list)
    summaries=[];pair_counts=Counter()
    for (typ,text),ix in sorted(split.items()):
        unique={}
        for i in ix:
            if anon[i]["text"] in unique:
                assert np.array_equal(av[i],av[unique[anon[i]["text"]]])
            else:unique[anon[i]["text"]]=i
            assert np.array_equal(ov[i],ov[ix[0]])
        selected=np.array([unique[t] for t in sorted(unique)],dtype=np.int64)
        left,right=np.triu_indices(len(selected),1)
        a,b=selected[left],selected[right]
        cos=cosine_pairs(au,a,b);old=cosine_pairs(ou,a,b)
        assert np.max(np.abs(old-1.0))<1e-12
        by_type[typ].extend(cos.tolist());old_type[typ].extend(old.tolist())
        pair_counts[typ]+=len(cos)
        summaries.append(dict(node_type=typ,original_text=text,
            text_sha256=hashlib.sha256(text.encode("utf8")).hexdigest(),
            node_rows=len(ix),file_count=len({original[i]["file"] for i in ix}),
            anonymous_variants=len(selected),cosine=stats(cos),
            original_bitwise_identical=True,original_cosine=stats(old)))
    rng=np.random.RandomState(1)
    controls={};control_details={}
    for typ,count in sorted(pair_counts.items()):
        pool=pools[typ];n=len(pool);assert n>=2
        g1=rng.randint(n,size=count);g2=rng.randint(n-1,size=count)
        g2=g2+(g2>=g1)
        left=np.array([pool[j][rng.randint(len(pool[j]))] for j in g1])
        right=np.array([pool[j][rng.randint(len(pool[j]))] for j in g2])
        assert all(original[a]["text"]!=original[b]["text"] for a,b in zip(left,right))
        controls[typ]=cosine_pairs(au,left,right).tolist()
        control_details[typ]=dict(original_text_groups=n,sampled_pairs=count,
            index_sha256=hashlib.sha256(np.stack([left,right],axis=1).astype("<i8").tobytes()).hexdigest())
    within=[x for typ in sorted(by_type) for x in by_type[typ]]
    control=[x for typ in sorted(controls) for x in controls[typ]]
    upper=[x for typ in sorted(old_type) for x in old_type[typ]]
    assert len(within)==len(control)==len(upper)
    return dict(rows=len(original),shared_statements=len(shared),
        shared_statement_node_rows=sum(map(len,shared.values())),split_statements=len(split),
        input_refs=dict(original=orefs,anonymous=arefs),
        within_pair_weighted=stats(within),control_same_type=stats(control),
        original_upper_check=stats(upper),
        group_equal_mean=float(np.mean([g["cosine"]["mean"] for g in summaries])),
        by_node_type={typ:dict(within=stats(by_type[typ]),control=stats(controls[typ]),
            sample=control_details[typ]) for typ in sorted(by_type)},
        groups=summaries,carrier_loaded_views=2)


def residual_task(task):
    rows=[json.loads(s) for s in (ART/"text_v1/anonymous"/task/"text.jsonl").read_text().splitlines()]
    context=load_context(task)
    grouped=defaultdict(list)
    for row in rows:
        if row["node_type"]!="env_source":grouped[row["file"]].append(row)
    counts=Counter();examples={};literals=Counter();retained=Counter();markers=[]
    checked_rows=0
    for filename,items in sorted(grouped.items()):
        source=context["source_text"][filename];naming=context["naming"][filename]
        base=context["graphs"]["F3"].subgraph([row["row_key"] for row in items]).copy()
        codes,_=node_code_view(base,filename,source,naming)
        for nid in base:base.nodes[nid]["code"]=codes[nid]
        view=ProjectionView(naming["rewritten"],filename)
        projector=Projector(base,view)
        byid={ident:view.compat_nodes[key] for key,ident in view.compat_ids.items()}
        asts={nid:byid[ident] for ident,nid in projector.by_ast.items()}
        leafs=leaves(view.compat_tree.root_node);starts=[n.start_byte for n in leafs]
        for row in items:
            if row["cut_mode"]=="placeholder":continue
            ast=asts[row["row_key"]]
            start,end,prefix,suffix,mode,reason=cut_span(ast,view,row["node_type"])
            assert mode==row["cut_mode"] and reason is None
            assert normalize(prefix+view.compat[start:end].decode("utf8")+suffix)==row["text"]
            checked_rows+=1
            if MARKER.search(row["text"]):
                markers.append(dict(file=filename,row_key=row["row_key"],text=row["text"]))
            for n in leafs[bisect.bisect_left(starts,start):bisect.bisect_left(starts,end)]:
                if n.end_byte>end:continue
                token=view.compat[n.start_byte:n.end_byte].decode("utf8")
                literal=("string" in n.type or "comment" in n.type)
                for match in WORD.finditer(token):
                    word=match.group(0)
                    if re.fullmatch(r"v[0-9]+",word):continue
                    if reserved(word):
                        if n.type=="identifier":
                            retained[(word,n.type,n.parent.type if n.parent else "")]+=1
                        continue
                    if literal:
                        literals[(word,n.type)]+=1
                        continue
                    # Numeric literal fragments are not identifier names.
                    if "number" in n.type or re.fullmatch(r"(?:0[xX][0-9a-fA-F]+|[0-9].*)",token):continue
                    key=(word,n.type,n.parent.type if n.parent else "")
                    counts[key]+=1
                    examples.setdefault(key,dict(file=filename,row_key=row["row_key"],text=row["text"]))
    def entries(counter):
        return [dict(name=k[0],grammar_type=k[1],parent_type=k[2],occurrences=v,
                     example=examples.get(k)) for k,v in sorted(counter.items())]
    assert not markers,"SolidiFI marker substring retained in anonymous feature text"
    return dict(checked_source_statement_rows=checked_rows,
        nonreserved_code_names=entries(counts),
        nonreserved_code_occurrences=sum(counts.values()),
        retained_reserved_identifiers=entries(retained),
        nonreserved_literal_words=[dict(word=k[0],grammar_type=k[1],occurrences=v)
                                   for k,v in sorted(literals.items())],
        marker_matches=markers,
        named_examples_in_frozen_reserved={w:reserved(w) for w in
            ["data","number","min","max","sig","interfaceId","abi","encodePacked"]})


def self_check():
    a=unit(np.array([[1.,0.],[0.,1.],[1.,1.]]))
    assert np.allclose(cosine_pairs(a,np.array([0,0]),np.array([1,2])),[0,2**-0.5])
    assert stats([0,1])["mean"]==0.5 and stats([0,1])["p05"]==0.05


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=["numbering","residual","legacy"])
    args=parser.parse_args();self_check()
    if args.phase=="numbering":
        results={}
        for task,expected in zip(TASKS,EXPECTED):
            results[task]=numbering_task(task,expected)
            print(json.dumps(dict(task=task,within=results[task]["within_pair_weighted"],
                control=results[task]["control_same_type"])),flush=True)
        write_new("numbering_effect.json",dict(version="ns-p2b-numbering-v1",cpu_only=True,
            fits=0,gpu_used=False,seed=1,
            group_rule="same node type + original text across >1 filenames; exclude env and END placeholders",
            pair_rule="one representative per unique anonymous text; all unordered variant pairs",
            control_rule="sample with replacement within each type; uniformly choose two distinct original-text groups, then uniform variants; same per-type pair count",
            weighting="pooled pair-weighted summaries; equal-group mean additionally reported",
            label_or_prediction_files_used=False,tasks=results))
    elif args.phase=="residual":
        results={}
        for task in TASKS:
            results[task]=residual_task(task)
            print(json.dumps(dict(task=task,nonreserved=results[task]["nonreserved_code_occurrences"],
                reserved_groups=len(results[task]["retained_reserved_identifiers"]))),flush=True)
        write_new("residual_names.json",dict(version="ns-p2b-residual-names-v1",
            method="frozen full anonymous compat AST + exact HCG AST slice; lex words classified by leaf type; literals separated",
            label_scope="frozen Projector/node_code_view may read structural DOT anchor; no vulnerability target or prediction used",
            tasks=results))
    else:
        legacy.load(PLAN)
        effective=PLAN.with_name("runtime_resume_v2.json")
        assert _code_refs()==read(effective)["runtime"]
        write_new("legacy_acceptance.json",dict(passed=True,plan=ref(PLAN),effective_runtime=ref(effective),
            runtime_equal=True,formal_fits=0,gpu_used=False))
        print("8H read-only load and effective runtime equality passed",flush=True)


if __name__=="__main__":main()
