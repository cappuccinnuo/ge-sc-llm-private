from scripts.edge_sem.io import read,checked,ROOT
from scripts.node_sem.facts_ast import AstSemantics
from scripts.node_sem.facts_guards import children
from scripts.DFG.dfg_v2.projection_view import ProjectionView
task="access_control_contract";file="0x0d689d1d3ef39e379329d9fc88eabceccc1215a0.sol"
m=read(ROOT/"scripts/edge_sem/artifacts/f4_v1"/task/"manifest.json")
text=checked(m["source_refs"][file]).read_text()
sem=AstSemantics(ProjectionView(text,file))
for fn in sem.functions:
 inv=[n for n in children(fn) if n.type=="modifier_invocation"]
 if inv:print(fn.type,fn.start_byte,[(n.start_byte,n.end_byte) for n in inv])
