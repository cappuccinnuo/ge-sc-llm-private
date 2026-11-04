"""Sidecar enhancement of a frozen HCG; no tokenizer, label or task changes."""
import copy
from dataclasses import asdict
from . import DATA_DEF_USE, __version__
from .models import Unsupported
from .ddg_builder import DDGBuilder
from .projection import Projector
from .graph_audit import assert_augmented, fingerprint

def augment(graph, sources, max_iterations=100000, scope_modes=None):
    if not graph.is_directed() or not graph.is_multigraph():
        raise ValueError("Expected a directed multigraph")
    if any(d.get("edge_type") in (DATA_DEF_USE,"REV_DATA_DEF_USE")
           for _,_,d in graph.edges(data=True)):
        raise ValueError("Already enhanced input: use the original HCG")
    initial=fingerprint(graph)
    output=copy.deepcopy(graph)
    audit={"version":__version__,"files":{},"evidence":[],"source_hashes":{}}
    files=list(dict.fromkeys(d["source_file"] for _,d in graph.nodes(data=True)))
    builder=DDGBuilder(max_iterations)
    for file in files:
        if file not in sources:
            audit["files"][file]={"diagnostics":[{"kind":"file_fallback",
                                  "reason":"Source manifest has no exact file identity"}]}
            continue
        source=sources[file]
        result=builder.analyze_source(source,file,(scope_modes or {}).get(file))
        record={"analysis":result.stats,"diagnostics":result.diagnostics,
                "scope_mode":result.view.mode if result.view is not None else None}
        audit["files"][file]=record
        if result.view is None: continue
        audit["source_hashes"][file]=result.view.sha256
        try:
            projector=Projector(graph,result.view)
            mapping,diagnostics=projector.map_facts(result.facts)
        except Unsupported as exc:
            record["diagnostics"].append({"kind":"projection_fallback","reason":str(exc)})
            continue
        edges,evidence,stats=builder.projected_edges(result.facts,mapping)
        record["projection"]=dict(projector.stats,**stats)
        record["diagnostics"].extend(diagnostics)
        record["anchors"]=[dict(asdict(anchor),node_id=identifier)
                           for anchor,identifier in sorted(mapping.items())]
        offset=len(audit["evidence"])
        audit["evidence"].extend(evidence)
        for s,t,d in edges:
            d["ddg_fact_indices"]=[offset+i for i in d["ddg_fact_indices"]]
            output.add_edge(s,t,**d)
    audit["invariants"]=assert_augmented(graph,output)
    if fingerprint(graph)!=initial: raise AssertionError("Input graph mutated")
    return output,audit
