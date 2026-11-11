from scripts.edge_sem.tests.test_attrs import bundle,pick
from scripts.edge_sem.attrs import explain_edge
from scripts.edge_sem.attr_sources import AttributeSource
from scripts.node_sem.tests.test_facts_integration import FILE
d=bundle();c,g,e,f,v=d
for rel,src,dst in [("DATA_DEF_USE","i++;","while (i < n)"),("DATA_DEF_USE",None,"uint c = a * b;"),("DATA_DEF_USE",None,"if (!a.send(p))")]:
 print("CASE",rel,src,dst)
 for r,z in pick(d,rel,src,dst):
  print("src",g.nodes[r["src"]]["code"],"dst",g.nodes[r["dst"]]["code"],"BITS",explain_edge(z))
  print("FROM",f[r["src"]]["dfg"],"TO",f[r["dst"]]["dfg"],"EXTERNAL",f[r["dst"]]["external"])
s=AttributeSource(c["source_text"][FILE],FILE,g)
print("pre08",s.pre_08)
