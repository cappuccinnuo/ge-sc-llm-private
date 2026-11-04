"""Explicit off/on switch; both variants originate from the same frozen HCG."""
import copy
from dataclasses import asdict
from .models import DDGConfig
from .pipeline import augment
from .graph_audit import fingerprint
from . import DATA_DEF_USE

def prepare_graph(graph, sources=None, config=None, scope_modes=None):
    config=config or DDGConfig()
    if any(d.get("edge_type") in (DATA_DEF_USE,"REV_DATA_DEF_USE")
           for _,_,d in graph.edges(data=True)):
        raise ValueError("Both modes require the original, unenhanced HCG")
    if config.use_ddg:
        output,audit=augment(graph,sources or {},config.max_iterations,scope_modes)
    else:
        output=copy.deepcopy(graph)
        audit={"files":{},"evidence":[],"source_hashes":{},
               "invariants":{"base_sha256":fingerprint(graph),
                             "enhanced_sha256":fingerprint(output),
                             "base_nodes":len(graph),"base_edges":graph.number_of_edges(),
                             "ddg_edges":0}}
    audit["config"]=asdict(config)
    return output,audit
