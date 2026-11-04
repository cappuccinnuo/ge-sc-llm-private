"""Existing file/mask supervision and audits with the extra forward relation."""
from types import FunctionType, SimpleNamespace
import sco_models.graph_utils as gu
from scripts.DFG.experiments import paper_runtime as paper
from scripts.DFG.experiments.e23_pilot import runtime as prior
from .model import reflected_input, FORWARD_RELATIONS
Supervision = paper.Supervision
_proxy = SimpleNamespace(**dict(vars(gu), reflect_graph=reflected_input))
_support = FunctionType(paper.graph_schema_and_support.__code__,
                        dict(paper.graph_schema_and_support.__globals__, gu=_proxy))
def graph_schema_and_support(graph, split):
    report = _support(graph, split)
    report["enhancement_support"] = {
        rel:{phase:sum(x[phase+"_edges"] for x in report["relations"] if x["canonical"][1]==rel)
             for phase in ("train","val")} for rel in sorted(FORWARD_RELATIONS)}
    return report
gradient_audit = FunctionType(prior.gradient_audit.__code__,
    dict(prior.gradient_audit.__globals__, FORWARD_RELATIONS=FORWARD_RELATIONS),
    prior.gradient_audit.__name__, prior.gradient_audit.__defaults__, prior.gradient_audit.__closure__)
