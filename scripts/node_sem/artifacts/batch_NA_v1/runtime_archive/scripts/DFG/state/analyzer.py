"""Public function-scoped state analysis. Failed functions publish no partial DDG."""
from ..frontend import SourceView
from ..models import Unsupported
from ..semantic_cfg import CFGBuilder
from .access import StateExtractor
from .reaching_definitions import solve
from .models import StateAnalysisResult

def analyze_view(view,selected_functions=None,max_iterations=100000):
    results=[]
    selected=set(selected_functions) if selected_functions is not None else None
    for fn in view.functions:
        fid="{}:{}".format(view.file,fn.start_byte)
        if selected is not None and fid not in selected:continue
        try:
            builder=CFGBuilder(view,fn);base=builder.build()
            state_ir=StateExtractor(view,fn,builder,base).build()
            results.append(solve(state_ir,max_iterations))
        except Unsupported as exc:
            results.append(StateAnalysisResult(fid,"function_fallback",diagnostics=[{
                "file":view.file,"start":fn.start_byte,"end":fn.end_byte,
                "line":fn.start_point[0]+1,"reason":str(exc),
                "partial_state_facts_published":False}]))
    if selected is not None and selected!={r.function for r in results}:
        raise ValueError("Selected function identities absent from exact source")
    return results

def analyze_source(source,file="example.sol",mode=None,selected_functions=None,max_iterations=100000):
    view=SourceView(source,file,mode)
    return view,analyze_view(view,selected_functions,max_iterations)
