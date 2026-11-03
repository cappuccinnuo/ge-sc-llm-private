"""Read-only AST joins for CTX text and name roles, never new semantic facts."""
from collections import defaultdict
import copy
import re
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import reserved
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from .facts_ast import AstSemantics, key, walk, FUNCTIONS, CONTRACTS
from .text_view import cut_span, normalize, PLACEHOLDERS
from .carrier import row_key

ROLE = {"state":"STATE","param":"PARAM","local":"LOCAL","function":"FUNC","contract":"TYPE"}


def _role(node, sem):
    binding=sem.resolve_identifier(node)
    if binding["kind"] in ROLE: return ROLE[binding["kind"]]
    parent=node.parent
    if parent is not None and key(parent.child_by_field_name("name"))==key(node):
        if parent.type in FUNCTIONS: return "FUNC"
        if parent.type in CONTRACTS or parent.type in ("struct_declaration","enum_declaration"): return "TYPE"
        if parent.type=="parameter": return "PARAM"
        if parent.type=="state_variable_declaration": return "STATE"
        if parent.type=="variable_declaration": return "LOCAL"
    if reserved(sem.text(node)): return "RESERVED"
    if parent is not None and parent.type in ("user_defined_type","type_alias","type_name"): return "TYPE"
    return "IDENT"


def _piece(ast, view, sem, inverse, node_type):
    start,end,prefix,suffix,_,_=cut_span(ast,view,node_type)
    raw=prefix+view.compat[start:end].decode("utf8")+suffix
    spans=[]
    for token in walk(ast):
        if token.type not in ("identifier","yul_identifier","enum_value"): continue
        if any(c.start_byte==token.start_byte and c.end_byte==token.end_byte for c in token.named_children): continue
        if not start<=token.start_byte<token.end_byte<=end: continue
        raw_candidates=inverse.get(key(token),[])
        role=_role(view.raw_nodes[raw_candidates[0]],sem) if len(raw_candidates)==1 else "IDENT"
        name=view.compat[token.start_byte:token.end_byte].decode("utf8")
        lo=len(prefix)+len(view.compat[start:token.start_byte].decode("utf8"))
        normalized_lo=len(re.sub(r"\s+"," ",raw[:lo]).lstrip())
        spans.append(dict(start=normalized_lo,end=normalized_lo+len(name),name=name,role=role))
    text=normalize(raw)
    previous=-1
    for item in sorted(spans,key=lambda x:x["start"]):
        if item["start"]<previous or text[item["start"]:item["end"]]!=item["name"]:
            raise ValueError("CTX normalized AST identifier span differs")
        previous=item["end"]
    return dict(text=text,identifiers=sorted(spans,key=lambda x:x["start"]))


def enrich(graph,sources,text_rows,fact_rows):
    """Return disposable sidecars aligned by exact Projector identity."""
    before=graph_fingerprint(graph)
    texts={r["row_key"]:r for r in text_rows}
    facts={r["row_key"]:r["facts"] for r in fact_rows}
    if set(texts)!=set(facts): raise ValueError("CTX facts/text identities differ")
    pieces,functions,owners={}, {}, {}
    for filename,source in sorted(sources.items()):
        ids=[n for n,a in graph.nodes(data=True) if a["source_file"]==filename and a["node_type"]!="env_source"]
        view=ProjectionView(source,filename)
        projector=Projector(graph.subgraph(ids).copy(),view)
        sem=AstSemantics(view)
        inverse=defaultdict(list)
        for raw,compat in view.mapping.items(): inverse[compat].append(raw)
        by_id={i:k for k,i in view.compat_ids.items()}
        for ast_id,nid in projector.by_ast.items():
            compat=by_id[ast_id]
            candidates=inverse.get(compat,[])
            if len(candidates)!=1: raise ValueError("CTX node has no unique raw AST identity")
            raw=view.raw_nodes[candidates[0]]
            ast=view.compat_nodes[compat]
            piece=_piece(ast,view,sem,inverse,graph.nodes[nid]["node_type"])
            if piece["text"]!=texts[nid]["text"]: raise ValueError("CTX source/text slicing differs")
            pieces[nid]=piece
            fn=sem.owner(raw)
            if fn is not None:
                ident=(filename,key(fn))
                owners[nid]=ident
                if ident not in functions:
                    fncompat=view.mapping.get(key(fn))
                    if fncompat is None: raise ValueError("CTX function lacks compatibility identity")
                    functions[ident]=_piece(view.compat_nodes[fncompat],view,sem,inverse,
                        "modifier_definition" if fn.type=="modifier_definition" else "function_definition")
        for nid in ids:
            if graph.nodes[nid]["node_type"] in PLACEHOLDERS:
                pieces[nid]=dict(text=texts[nid]["text"],identifiers=[])
            elif nid not in pieces: raise ValueError("CTX original node lacks exact projection")
    summaries=defaultdict(set)
    unknown=set()
    for nid,owner in owners.items():
        f=facts[nid]
        summaries[owner].update(g["kind"] for g in f["guards"])
        if f["guard_status"]=="unknown": unknown.add(owner)
    for row in text_rows:
        if row["node_type"]=="env_source": pieces[row["row_key"]]=dict(text=row["text"],identifiers=[])
    out=[]
    for row in text_rows:
        value=copy.deepcopy(row)
        nid=row["row_key"]
        owner=owners.get(nid)
        f=facts[nid]
        refs=(f["dfg"].get("from",[])+f["dfg"].get("to",[])+
              ([f["order"]["pre_ext_call"]] if f["order"].get("pre_ext_call") else []))
        neighbors={}
        for item in refs:
            target=item["node"]
            if target not in pieces or texts[target]["file"]!=row["file"]:
                raise ValueError("CTX reference missing or crosses source identity")
            neighbors[target]=pieces[target]
        value["_ctx"]=dict(piece=pieces[nid],function=functions.get(owner),
            function_guards=sorted(summaries.get(owner,set())),
            function_guards_unknown=owner in unknown,neighbors=neighbors)
        out.append(value)
    if graph_fingerprint(graph)!=before: raise AssertionError("CTX alignment mutated graph")
    return out
