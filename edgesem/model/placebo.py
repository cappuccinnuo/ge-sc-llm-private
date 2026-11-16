"""Placebos: degree-preserving relation rewiring (G4R-P) and within-relation attribute
permutation (G4R-Api), both seeded by the fold constructor seed.
"""
import copy
import hashlib
import json
import random
from collections import Counter, defaultdict

import numpy as np

from edgesem.schema import NEW_RELATIONS


DEFAULT_SEED=1729

def _rng(seed,identity):
    if type(seed) is not int:raise ValueError("Seed must be an integer")
    raw=json.dumps([seed,identity],sort_keys=True,separators=(",",":")).encode()
    return random.Random(int(hashlib.sha256(raw).hexdigest(),16))

def degree_signature(graph,edges):
    """File, canonical relation and node identity are all part of the checksum."""
    out,incoming=Counter(),Counter()
    for e in edges:
        s,t,r=e["src"],e["dst"],e["relation"]
        if s not in graph or t not in graph:raise ValueError("Unknown endpoint")
        if any(graph.nodes[n]["source_file"]!=e["file"] for n in (s,t)):
            raise ValueError("Cross-file edge")
        c=(e["file"],graph.nodes[s]["node_type"],r,graph.nodes[t]["node_type"])
        out[(c,s)]+=1;incoming[(c,t)]+=1
    return out,incoming

def randomize_edges(graph,edges,seed=DEFAULT_SEED,attempts_per_edge=10):
    """Return topology-only E1 records; never relabel old semantic evidence."""
    if type(attempts_per_edge) is not int or attempts_per_edge<=0:
        raise ValueError("Positive fixed attempt budget required")
    original=degree_signature(graph,edges)
    groups=defaultdict(list);seen=set()
    for e in edges:
        s,t,r=e["src"],e["dst"],e["relation"]
        if r not in NEW_RELATIONS or s==t:raise ValueError("Expected non-self E1 edge")
        key=(s,t,r)
        if key in seen:raise ValueError("Duplicate E1 edge")
        seen.add(key)
        c=(e["file"],graph.nodes[s]["node_type"],r,graph.nodes[t]["node_type"])
        groups[c].append((s,t))
    output=[];audit=[]
    for canonical,pairs in sorted(groups.items()):
        rng=_rng(seed,canonical);current=list(pairs);occupied=set(current)
        accepted=0;budget=attempts_per_edge*len(current) if len(current)>=2 else 0
        for _ in range(budget):
            i,j=rng.sample(range(len(current)),2)
            a,b=current[i];c,d=current[j]
            if a==c or b==d or a==d or c==b:continue
            first,second=(a,d),(c,b)
            if first in occupied or second in occupied:continue
            occupied.remove((a,b));occupied.remove((c,d))
            occupied.add(first);occupied.add(second)
            current[i],current[j]=first,second;accepted+=1
        file,src_type,rel,dst_type=canonical
        output.extend(dict(src=s,dst=t,file=file,relation=rel,
                           rule="EP5-degree-placebo",semantic_evidence=False) for s,t in current)
        audit.append(dict(file=file,canonical=[src_type,rel,dst_type],edges=len(pairs),
                          attempts=budget,accepted_switches=accepted,
                          changed_edges=len(occupied-set(pairs)),
                          unchanged_edges=len(occupied&set(pairs))))
    if degree_signature(graph,output)!=original:
        raise AssertionError("Placebo changed per-node canonical degrees")
    return output,dict(seed=seed,attempts_per_edge=attempts_per_edge,partitions=audit,
                       total_edges=len(edges),changed_edges=sum(r["changed_edges"] for r in audit),
                       zero_switch_partitions=sum(r["accepted_switches"]==0 for r in audit),
                       per_node_degrees_exact=True,uniform_sampling_claim=False)

def permute_attributes(rows,attrs,seed=DEFAULT_SEED):
    """Permute complete uint8[74] rows within relation (across files allowed)."""
    keys=[r["key"] for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=set(attrs):
        raise ValueError("Attribute population is missing or duplicate")
    groups=defaultdict(list)
    for row in rows:
        value=np.asarray(attrs[row["key"]])
        if value.dtype!=np.uint8 or value.shape!=(74,) or not np.isin(value,[0,1]).all():
            raise ValueError("Expected binary uint8[74]")
        groups[row["relation"]].append(row["key"])
    output={};mapping={};audit={}
    for relation,group in sorted(groups.items()):
        order=list(group);_rng(seed,relation).shuffle(order)
        for dest,source in zip(group,order):
            output[dest]=attrs[source].copy();mapping[dest]=source
        old=Counter(attrs[k].tobytes() for k in group)
        new=Counter(output[k].tobytes() for k in group)
        if old!=new:raise AssertionError("Attribute multiset changed")
        audit[relation]=dict(rows=len(group),moved_positions=sum(a!=b for a,b in zip(group,order)),
            changed_vectors=sum(not np.array_equal(attrs[k],output[k]) for k in group),
            unique_vectors=len(old),multiset_exact=True)
    return {k:output[k] for k in keys},dict(seed=seed,per_relation=audit,source_key_for_target=mapping)

def add_placebo_edges(graph_copy, rows, real_rows):
    """Validate topology-only E1 rows without weakening semantic add_edges."""
    import networkx as nx
    if not isinstance(graph_copy, nx.MultiDiGraph):
        raise TypeError("Expected directed multigraph")
    if len(rows) != len(real_rows):
        raise ValueError("Placebo row count differs")
    seen = set()
    for row in rows:
        if set(row) != {"src", "dst", "file", "relation", "rule", "semantic_evidence"}:
            raise ValueError("Only topology-only placebo fields are accepted")
        if row["rule"] != "EP5-degree-placebo" or row["semantic_evidence"] is not False:
            raise ValueError("Expected non-semantic placebo evidence")
        src, dst, relation = row["src"], row["dst"], row["relation"]
        if src not in graph_copy or dst not in graph_copy:
            raise ValueError("Unknown placebo endpoint")
        if relation not in NEW_RELATIONS or src == dst:
            raise ValueError("Expected non-self placebo E1 edge")
        if any(graph_copy.nodes[n]["source_file"] != row["file"] for n in (src, dst)):
            raise ValueError("Cross-file placebo edge")
        ident = (src, dst, relation)
        if ident in seen or any(
                d.get("edge_type") == relation for d in graph_copy.get_edge_data(src, dst, default={}).values()):
            raise ValueError("Duplicate placebo relation")
        seen.add(ident)
    if degree_signature(graph_copy, rows) != degree_signature(graph_copy, real_rows):
        raise ValueError("Placebo per-node canonical degrees differ")
    result = copy.deepcopy(graph_copy)
    for row in rows:
        result.add_edge(row["src"], row["dst"], edge_type=row["relation"])
    return result
