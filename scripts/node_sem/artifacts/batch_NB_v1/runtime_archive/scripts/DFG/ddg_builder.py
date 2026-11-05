"""Build auditable direct facts and forward edges, without reading labels."""
from dataclasses import dataclass, field
from typing import List
from . import DATA_DEF_USE, __version__
from .frontend import parse_source
from .semantic_cfg import analyze
from .reaching_definitions import solve
from .models import Fact, DDGConfig, Unsupported

@dataclass
class BuildResult:
    view: object = None
    facts: List[Fact] = field(default_factory=list)
    diagnostics: List[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

class DDGBuilder:
    def __init__(self, max_iterations=100000):
        self.max_iterations=max_iterations

    def analyze_source(self, source, file, mode=None):
        result=BuildResult(stats={"functions_total":0,"functions_supported":0,
                                 "definitions":0,"uses_total":0,"uses_resolved":0,
                                 "iterations":0})
        try: view=parse_source(source,file,mode)
        except Unsupported as exc:
            result.diagnostics.append({"kind":"file_fallback","file":file,"reason":str(exc)})
            return result
        result.view=view
        analysis=analyze(view)
        result.diagnostics.extend(analysis.diagnostics)
        result.stats["functions_total"]=len(view.functions)
        for ir in analysis.functions:
            try: rd=solve(ir,self.max_iterations)
            except Unsupported as exc:
                result.diagnostics.append({"kind":"function_fallback","function":ir.id,"reason":str(exc)})
                continue
            result.facts.extend(rd.facts)
            result.stats["functions_supported"]+=1
            result.stats["definitions"]+=len(rd.definitions)
            result.stats["uses_total"]+=rd.uses_total
            result.stats["uses_resolved"]+=rd.uses_resolved
            result.stats["iterations"]+=rd.iterations
        return result

    def projected_edges(self, facts, mapping):
        """mapping is exact Span -> frozen HCG ID; no line/nearest fallback."""
        edges={}
        evidence=[]
        skipped=0
        self_facts=0
        for fact in facts:
            if fact.definition.function != fact.use.function:
                raise ValueError("Cross-function fact")
            a,b=fact.definition.anchor,fact.use.anchor
            if a.file != b.file: raise ValueError("Cross-file fact")
            if a not in mapping or b not in mapping:
                skipped+=1
                continue
            src,dst=mapping[a],mapping[b]
            ev={"symbol":fact.symbol,"function":fact.use.function,
                "definition":fact.definition.id,"use":fact.use.id,
                "source":src,"target":dst,"self_fact":src==dst}
            evidence.append(ev)
            if src==dst:
                self_facts+=1
                continue
            edges.setdefault((src,dst),[]).append(len(evidence)-1)
        output=[(s,t,{"edge_type":DATA_DEF_USE,"ddg_version":__version__,
                     "ddg_fact_indices":indices})
                for (s,t),indices in edges.items()]
        stats={"facts_total":len(facts),"facts_projected":len(evidence),
               "facts_unmapped":skipped,"self_facts":self_facts,
               "edges_added":len(output),
               "duplicate_projected_pairs":len(evidence)-self_facts-len(output)}
        return output,evidence,stats
