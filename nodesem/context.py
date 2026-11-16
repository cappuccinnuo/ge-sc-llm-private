"""CTX fields: data-flow and contract context of a statement, rendered as short text.

Fields (STMT, DEF, USE, FROM, TO, STATE_R/W, GUARD, CALL, ENV, FUNC, ...) come only from
the statement facts and exact AST slices; ``masked`` replaces identifier spellings by
their binding role (STATE, PARAM, LOCAL, ...).
"""
import copy
import re
from collections import OrderedDict, defaultdict

from nodesem.facts.schema import FUNCTION_KINDS, STATEMENT_KINDS, validate
from nodesem.facts.syntax import AstSemantics, CONTRACTS, FUNCTIONS, key, walk
from nodesem.text import PLACEHOLDERS, cut_span, normalize

from dfg.graph.audit import fingerprint as graph_fingerprint
from dfg.graph.projection import ProjectionView, Projector
from dfg.train.features import reserved


# ----------------------------------------------------------------------
# node_sem/ctx_alignment
# Read-only AST joins for CTX text and name roles, never new semantic facts.
BINDING_ROLE = {"state":"STATE","param":"PARAM","local":"LOCAL","function":"FUNC","contract":"TYPE"}

def _role(node, sem):
    binding=sem.resolve_identifier(node)
    if binding["kind"] in BINDING_ROLE: return BINDING_ROLE[binding["kind"]]
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
    # Evidence metadata only: entry recognition never guesses from text prefixes.
    for nid,piece in pieces.items():
        piece["node_kind"]=facts[nid]["node_kind"]
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


# ----------------------------------------------------------------------
# node_sem/ctx_fields
# CTX fields from sealed facts and exact, disposable AST text sidecars.
#
# Original and locally masked names share one renderer. Dataset/source identities
# remain metadata; no targets, predictions or absolute positions enter fields.
VERSION="nodesem-ctx-fields-v1"

FIELD_ORDER=("STMT","FUNC","DEF","USE","FROM","TO","STATE_R","STATE_W","ENV",
             "CALL","LOOP","PRE_EXT_CALL","GUARD","COND","STATE_DECL","FN_SUMMARY","CONTRACT")

ROLE={"state":"STATE","parameter":"PARAM","param":"PARAM","return":"LOCAL","local":"LOCAL","unknown":"IDENT"}

ID_RE=re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")

def distance(offset):
    return "unknown" if offset is None else "@{:+d}".format(offset)

def source_distance(item, side):
    """Entry is a projected function identity, not a spelling or missing offset."""
    piece=side["neighbors"].get(item["node"], {})
    if item["offset"] is None and piece.get("node_kind") in FUNCTION_KINDS:
        return "entry"
    return distance(item["offset"])

def variable_distance(item, dfg, side):
    if item["kind"] in ("parameter", "param") and item["from_offset"] is None:
        for source in dfg["from"]:
            piece=side["neighbors"].get(source["node"], {})
            if source_distance(source,side)=="entry" and any(
                token["name"]==item["var"] and token["role"]=="PARAM"
                for token in piece.get("identifiers",[])):
                return "entry"
    return distance(item["from_offset"])

def _nearest(items):
    # Stable evidence order resolves equal distances; no spelling/label sorting.
    return sorted(enumerate(items),key=lambda pair:(
        pair[1]["offset"] is None, abs(pair[1]["offset"]) if pair[1]["offset"] is not None else 0,pair[0]))

class _Names:
    def __init__(self,mode,facts,side):
        if mode not in ("original","masked"):
            raise ValueError("Unsupported CTX name policy; anonymous view needs separately bound text/rename inputs")
        self.mode,self.mapping,self.counts=mode,{},defaultdict(int)
        roles=defaultdict(set)
        for piece in [side["piece"],side.get("function")]+list(side["neighbors"].values()):
            if piece:
                for item in piece["identifiers"]:
                    if item["role"] not in ("IDENT","RESERVED"): roles[item["name"]].add(item["role"])
        for mode_ in ("defs","uses"):
            for item in facts["dfg"].get(mode_,[]):
                role=ROLE[item["kind"]]
                if role!="IDENT": roles[item["var"]].add(role)
        for mode_ in ("reads","writes"):
            for item in facts["state"].get(mode_,[]): roles[item["var"]].add("STATE")
        self.roles={name:next(iter(values)) if len(values)==1 else "IDENT" for name,values in roles.items()}

    def name(self,name,role="IDENT"):
        if self.mode=="original": return name
        role=self.roles.get(name,role)
        if role=="RESERVED": return name
        if name not in self.mapping:
            self.counts[role]+=1
            self.mapping[name]=role+str(self.counts[role])
        return self.mapping[name]

    def var(self,name,role):
        def replace(match):
            word=match.group()
            if reserved(word) and word not in self.roles: return word
            return self.name(word,role)
        return ID_RE.sub(replace,name)

    def piece(self,piece):
        if not piece: return "-"
        text=piece["text"]
        if self.mode=="original": return text
        # Assign in first occurrence order, replace spans in reverse order.
        edits=[(s["start"],s["end"],self.name(s["name"],s["role"])) for s in piece["identifiers"]]
        for lo,hi,value in reversed(edits): text=text[:lo]+value+text[hi:]
        return text

def _scalar(value):
    if type(value) is bool:return "true" if value else "false"
    return str(value)

def _summary(obj,order):
    return [key+"="+("unknown" if key in obj["unknown_fields"] else _scalar(obj[key])) for key in order]

def ctx_fields(facts_row,text_row,names="original"):
    f=facts_row.get("facts",facts_row)
    validate(f)
    if "row_key" in facts_row and facts_row["row_key"]!=text_row["row_key"]:
        raise ValueError("CTX facts/text identity differs")
    side=text_row.get("_ctx")
    if side is None:raise ValueError("CTX requires exact AST text sidecars")
    policy=_Names(names,f,side)
    out={"STMT":[policy.piece(side["piece"])]}
    kind=f["node_kind"]
    if kind in ("env","end"):return OrderedDict((k,out[k]) for k in FIELD_ORDER if k in out)
    if side.get("function"):
        guards="unknown" if side["function_guards_unknown"] else ",".join(side["function_guards"]) or "none"
        out["FUNC"]=[policy.piece(side["function"]),
            "visibility:"+f["function_ctx"].get("visibility","default"),"guards:"+guards]
    if kind in STATEMENT_KINDS:
        dfg=f["dfg"]
        for field,source in (("DEF","defs"),("USE","uses")):
            values=[]
            if dfg["status"]=="unknown": values=["unknown"]
            else:
                for item in dfg[source]:
                    name=policy.var(item["var"],ROLE[item["kind"]])
                    role="param" if item["kind"]=="parameter" else item["kind"]
                    offset=(":"+variable_distance(item,dfg,side)) if role in ("local","param","return") else ""
                    values.append(name+":"+role+offset)
                # L2/L3 accesses are available separately; do not turn uncertain
                # local def-use support into known support.
                mode_="writes" if field=="DEF" else "reads"
                if f["state"]["status"]=="supported":
                    values += [policy.var(x["var"],"STATE")+":state" for x in f["state"][mode_]]
                if field=="USE": values += [x+":env" for x in f["env"]["keys"]]
            out[field]=list(dict.fromkeys(values)) or ["-"]
        for field,source in (("FROM","from"),("TO","to")):
            values=[]
            if dfg["status"]=="unknown": values=["unknown"]
            else:
                for _,item in _nearest(dfg[source])[:2]:
                    piece=side["neighbors"].get(item["node"])
                    if piece is None:raise ValueError("CTX missing DFG endpoint text")
                    label=(source_distance(item,side) if source=="from" else distance(item["offset"]))+":"
                    if source=="to":label+=item["sink"]+":"
                    values.append(label+" "+policy.piece(piece))
            out[field]=values or ["-"]
        for field,source in (("STATE_R","reads"),("STATE_W","writes")):
            out[field]=(["unknown"] if f["state"]["status"]=="unknown" else
                [policy.var(x["var"],"STATE")+":"+("scalar" if x["shape"] not in ("mapping","array") else x["shape"])+(":auth" if x["auth"] else "") for x in f["state"][source]]) or ["-"]
        out["ENV"]=[x+":"+(",".join(f["env"]["uses"]) or "none") for x in f["env"]["keys"]] or ["-"]
        call=f["external"]
        out["CALL"]=(["kinds:"+",".join(call["kinds"]),"target:"+(",".join(call["target_classes"]) or "none"),
            "value:"+call["value_class"],"data:"+call["data_class"],"return:"+call["return_handling"]]
            if call["kinds"] else ["uninvoked_call_value"] if call["uninvoked_call_value"] else ["-"])
        out["LOOP"]=(["unknown"] if f["loop"]["bound"]=="unknown" else
            ["bound:"+f["loop"]["bound"],"external_call:"+_scalar(bool(call["kinds"]))]
            if f["loop"]["bound"]!="none" else ["-"])
        previous=f["order"]["pre_ext_call"]
        out["PRE_EXT_CALL"]=["unknown"] if f["order"]["status"]=="unknown" else (
            [distance(previous["offset"])+": "+policy.piece(side["neighbors"][previous["node"]])] if previous else ["-"])
        if f["guard_status"]=="unknown":out["GUARD"]=["unknown"]
        elif f["nearest"] is None:out["GUARD"]=["-"]
        else:
            g=f["guards"][f["nearest"]]
            out["GUARD"]=["kind:"+g["kind"],"polarity:"+str(g["polarity"]),
                "eq:"+(",".join(g["eq_pairs"]) or "none"),distance(g["offset"]),
                "additional:"+str(len(f["guards"])-1)]
    if kind=="condition":
        obj=f["self_condition"]
        out["COND"]=["operands:"+(",".join(obj["operand_classes"]) or "none"),
            "eq:"+(",".join(obj["eq_pairs"]) or "none"),"early_exit:"+_scalar(obj["early_exit_if"])]
    if kind=="state_decl":
        out["STATE_DECL"]=_summary(f["state_decl"],("shape","public","constant_immutable","has_initializer",
            "auth","read_functions","write_functions","only_constructor_writes","unguarded_write_functions"))
    if kind in FUNCTION_KINDS:
        out["FN_SUMMARY"]=_summary(f["fn_summary"],("external_call","state_write","sender_guard","auth_write","selfdestruct","delegatecall","loop","ext_call_in_loop","timestamp","tx_origin","write_then_call","call_then_write"))
    if kind=="contract":
        out["CONTRACT"]=_summary(f["contract_summary"],("kind","explicit_constructor","payable_fallback","auth_state_count","selfdestruct"))
    return OrderedDict((field,out[field]) for field in FIELD_ORDER if field in out)

def render(fields):
    return "\n".join("["+key+"] "+" | ".join(values) for key,values in fields.items())
