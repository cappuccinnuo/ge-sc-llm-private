"""EP5 read-only source/evidence translation via exact AST and 8G bindings.

No analyzers are patched. Nothing anonymous is a production graph or source file.
Only fields actually consumed by frozen identity joins are translated; diagnostic
summaries not consumed by the analyzers remain explicitly historical.
"""
import copy
import hashlib
from collections import Counter
from scripts.DFG.frontend import parse, walk
from scripts.DFG.dfg_v2.benchmark_v2.anon_binding import anonymize
from scripts.DFG.dfg_v2.benchmark_v2.anon_parity import node_code_view
from scripts.node_sem.facts_ast import key, FUNCTIONS
from scripts.node_sem.facts_cfg import FileCFG
from scripts.node_sem.facts_io import check_layer_edge


class TranslationError(ValueError):
    pass


class EvidenceTranslation:
    def __init__(self, source, file, result, metadata=None):
        self.file,self.source,self.result=file,source,result
        self.new=result["rewritten"]
        self.old_nodes=list(walk(parse(source).root_node))
        self.new_nodes=list(walk(parse(self.new).root_node))
        if len(self.old_nodes)!=len(self.new_nodes):
            raise TranslationError("AST topology differs")
        self.by_key={};self.starts={};self.ends={};self.at_start={}
        for a,b in zip(self.old_nodes,self.new_nodes):
            if a.type!=b.type or len(a.children)!=len(b.children):
                raise TranslationError("AST topology differs")
            self.by_key[key(a)]=b
            self.at_start.setdefault(a.start_byte,[]).append(a)
            for table,x,y in ((self.starts,a.start_byte,b.start_byte),(self.ends,a.end_byte,b.end_byte)):
                if x in table and table[x]!=y:raise TranslationError("Ambiguous AST boundary")
                table[x]=y
        self.edits={(b["start"],b["end"]):b for b in result["edits"]}
        declarations={d["id"]:d for d in result.get("declarations",[])}
        self.proof=[]
        for span,b in self.edits.items():
            d=declarations[b["declaration"]]
            if source.encode()[span[0]:span[1]].decode()!=b["old"] or d["name"]!=b["old"]:
                raise TranslationError("Occurrence/declaration spelling differs")
            if result["names"][d["id"]]!=b["new"]:
                raise TranslationError("Occurrence/declaration new name differs")
        self.functions={file+":"+str(n.start_byte):n for n in self.old_nodes if n.type in FUNCTIONS}
        callable_nodes=[n for n in self.old_nodes if n.type in FUNCTIONS or n.type=="state_variable_declaration"]
        self.function_ids={file+":"+str(n.start_byte):file+":"+str(self.by_key[key(n)].start_byte) for n in callable_nodes}
        self.old_cfg=FileCFG(source,file,metadata)
        # Original compiler records are SHA-bound to original disk bytes. They
        # cannot certify rewritten text. Unchanged pragma must suffice here.
        self.new_metadata=None if result["status"]=="renamed" else metadata
        self.new_cfg=FileCFG(self.new,file,self.new_metadata)
        self.symbols={}

    def rename_leaf(self, node, expected):
        if node is None or node.text.decode()!=expected:
            raise TranslationError("Name lacks exact occurrence: "+repr(expected))
        edit=self.edits.get((node.start_byte,node.end_byte))
        after=self.by_key[key(node)].text.decode()
        if edit is None:
            if after!=expected:raise TranslationError("Unbound leaf changed")
            return expected
        if edit["old"]!=expected or edit["new"]!=after:
            raise TranslationError("Bound occurrence changed unexpectedly")
        self.proof.append(dict(occurrence=list(key(node)),declaration=edit["declaration"],
                               old=expected,new=after))
        return after

    def name_at(self, record):
        name=record["name"]
        start=record.get("start",record.get("byte"))
        end=record.get("end")
        role=record.get("role",record.get("ast_type"))
        candidates=[n for n in self.at_start.get(start,[]) if (end is None or n.end_byte==end)
                    and (role is None or n.type==role)]
        names=[]
        for node in candidates:
            field=node.child_by_field_name("name")
            if field is not None and field.text.decode()==name:
                names.append(self.rename_leaf(field,name))
            elif node.text.decode()==name and node.type in ("identifier","enum_value"):
                names.append(self.rename_leaf(node,name))
            elif node.type==name:
                names.append(name) # structural statement role, not an identifier
        if names and len(set(names))==1:return names[0]
        # Diagnostics occasionally have a byte anchor on the receiver's parent.
        leaves=[n for parent in candidates for n in walk(parent)
                if n.type in ("identifier","enum_value") and n.text.decode()==name]
        changes={self.rename_leaf(n,name) for n in leaves}
        if changes and len(changes)==1:return changes.pop()
        raise TranslationError("No unique bound name at evidence occurrence: "+repr(record))

    def identity(self, value):
        if value in self.function_ids:return self.function_ids[value]
        for old,new in self.function_ids.items():
            if value.startswith(old+":e"):
                suffix=value[len(old):]
                if not suffix[2:].isdigit():raise TranslationError("Unsupported event identity: "+value)
                return new+suffix
        raise TranslationError("Unknown callable/event identity: "+value)

    def symbol(self, evidence):
        ident=evidence["symbol"];fn=self.functions[evidence["function"]];route=evidence["analysis_path"]
        if (route,ident) in self.symbols:return self.symbols[(route,ident)]
        old=self.old_cfg.symbol(fn,route,ident)
        mapped_start=self.starts[old.declaration.start]
        # Populate the exact original/fresh declaration tables, without CFG or
        # reaching-definition recomputation. No string slicing of symbol names.
        new_fn=self.by_key[key(fn)]
        from scripts.DFG.symbol_table import SymbolTable
        from scripts.DFG.dfg_v2.l1_symbols import ExtendedSymbolTable
        view=self.new_cfg.views.get(route)
        if view is None:raise TranslationError("Renamed sealed symbol route unavailable: "+route)
        cls=SymbolTable if route=="legacy" else ExtendedSymbolTable
        table=cls(self.new,self.file,view.raw_nodes[key(new_fn)],view.mode)
        candidates=[s for s in table.symbols.values() if s.declaration.start==mapped_start
                    and s.declaration.end==self.ends[old.declaration.end] and s.kind==old.kind]
        if len(candidates)!=1:raise TranslationError("Declaration identity mapping is not unique")
        new=candidates[0]
        declarations=[n for n in self.at_start[old.declaration.start]
                      if n.end_byte==old.declaration.end and n.child_by_field_name("name") is not None]
        names={self.rename_leaf(n.child_by_field_name("name"),old.name) for n in declarations
               if n.child_by_field_name("name").text.decode()==old.name}
        if names!={new.name}:raise TranslationError("Symbol lacks binding proof")
        self.symbols[(route,ident)]=new.id
        return new.id

    def l1(self, evidence):
        out=copy.deepcopy(evidence);ident=self.symbol(evidence)
        out["symbol"]=ident
        out["function"]=self.identity(evidence["function"])
        out["use"]=self.identity(evidence["use"])
        suffix=":"+evidence["symbol"]
        if not evidence["definition"].endswith(suffix):
            raise TranslationError("Definition/symbol identity mismatch")
        event=evidence["definition"][:-len(suffix)]
        out["definition"]=self.identity(event)+":"+ident
        return out

    def record(self, value, translate_names=True):
        if isinstance(value,list):return [self.record(x,translate_names) for x in value]
        if not isinstance(value,dict):return value
        out={}
        for field,item in value.items():
            target=self.function_ids.get(field,field)
            if field in ("start","end","byte") and isinstance(item,int):
                table=self.ends if field=="end" else self.starts
                if item not in table:raise TranslationError("Evidence offset lacks exact AST boundary")
                out[target]=table[item]
            elif field in ("function","callable") and isinstance(item,str) and item.startswith(self.file+":"):
                out[target]=self.identity(item)
            elif field=="name" and translate_names:
                out[target]=self.name_at(value)
            else:
                out[target]=self.record(item,translate_names)
        return out


def exact_code_view(graph,file,source,result):
    """Extend only ambiguous end_if text with the approved direct CFG anchor.

    Other nodes still use the frozen node_code_view implementation. No source
    line proximity, identifier spelling, or alternative AST binding is guessed.
    """
    from scripts.DFG.projection import ANCHOR,decoded,code_equal,Projector
    from scripts.DFG.dfg_v2.projection_view import ProjectionView
    import pydot
    before=ProjectionView(source,file);after=ProjectionView(result["rewritten"],file)
    old_ids={v:k for k,v in before.compat_ids.items()}
    new_ids={v:k for k,v in after.compat_ids.items()}
    if set(old_ids)!=set(new_ids):
        raise TranslationError("Compatibility AST identity population differs")
    projector=Projector(graph,before)
    extensions={}
    for n,a in graph.nodes(data=True):
        if a["node_type"]!="end_if" or ANCHOR.search(decoded(a.get("label",""))):continue
        candidates=[i for i,k in old_ids.items() if k[2]=="if_statement"
                    and code_equal(a["code"],before.compat[k[0]:k[1]].decode())]
        texts={after.compat[new_ids[i][0]:new_ids[i][1]].decode() for i in candidates}
        if len(texts)<=1:continue # frozen handling, including a missing match
        parents={s for s,_,d in graph.in_edges(n,data=True) if d["edge_type"]=="neg_next"}
        if len(parents)!=1:raise TranslationError("Ambiguous end_if has no unique neg_next parent")
        parent=next(iter(parents));p=graph.nodes[parent]
        anchor=ANCHOR.search(decoded(p.get("label","")))
        if (p["source_file"]!=file or anchor is None or
                int(anchor.group(1)) not in candidates or
                projector.by_ast.get(int(anchor.group(1)))!=parent):
            raise TranslationError("Ambiguous end_if parent lacks exact matching if AST")
        ident=int(anchor.group(1));old,new=old_ids[ident],new_ids[ident]
        if new[2]!="if_statement":raise TranslationError("Renamed parent role differs")
        original=before.compat[old[0]:old[1]].decode()
        text=after.compat[new[0]:new[1]].decode()
        value=text if a["code"]==original else pydot.quote_if_necessary(text)
        extensions[n]=(value,dict(node=n,basis="unique_neg_next_from_exact_if",
            parent=parent,compat_ast_ids=[ident],rejected_ambiguous_text_candidates=candidates))
    codes,proof=node_code_view(graph.subgraph([n for n in graph if n not in extensions]),file,source,result)
    for n,(value,record) in extensions.items():
        codes[n]=value;proof.append(record)
    if set(codes)!=set(graph):raise TranslationError("Incomplete graph code view")
    return codes,proof


def translate(source,file,graph,audit,metadata=None):
    result=anonymize(source,metadata)
    sha=hashlib.sha256(source.encode()).hexdigest()
    if result["source_sha256"]!=sha or audit["source_hashes"].get(file)!=sha:
        raise TranslationError("Original source/evidence SHA differs")
    if result["status"]=="fallback":
        if result["rewritten"]!=source or result["edits"]:
            raise TranslationError("Fallback is not identity")
        return copy.deepcopy(graph),copy.deepcopy(audit),result,dict(
            fallback_identity=True,issues=result["issues"],bindings=[],original_names={},
            metadata=metadata,compiler_metadata_policy="original identity")
    tx=EvidenceTranslation(source,file,result,metadata)
    temp=copy.deepcopy(graph);translated=copy.deepcopy(audit)
    plain=graph.subgraph([n for n,a in graph.nodes(data=True) if a["node_type"]!="env_source"])
    codes,projection=exact_code_view(plain,file,source,result)
    for n,code in codes.items():temp.nodes[n]["code"]=code
    new_sha=hashlib.sha256(result["rewritten"].encode()).hexdigest()
    translated["source_hashes"][file]=new_sha
    for layer in ("L1","L2","L3"):
        old=audit["layers"][layer];new=translated["layers"][layer]
        if old["source_hashes"].get(file)!=sha:raise TranslationError("Layer/source SHA differs")
        new["source_hashes"][file]=new_sha
        for i,ev in enumerate(old["evidence"]):
            belongs=ev.get("file")==file or ev.get("function","").startswith(file+":")
            if belongs:new["evidence"][i]=tx.l1(ev) if layer=="L1" else tx.record(ev)
        rec=old["files"].get(file,{})
        # Translate all fields consumed by facts._bind_layers / StateSupport.
        if layer=="L1":
            for i,fn in enumerate(rec.get("analysis",{}).get("functions",[])):
                new["files"][file]["analysis"]["functions"][i]=tx.record(fn)
        elif layer=="L2":
            for field in ("callables","diagnostics","declarations"):
                if field in rec:new["files"][file][field]=tx.record(rec[field])
    for s,t,k,attrs in temp.edges(keys=True,data=True):
        proof=check_layer_edge(s,t,graph[s][t][k],audit)
        if attrs["edge_type"] in ("READS_STATE","WRITES_STATE"):
            old_names=sorted({e["state"]["name"] for e in proof})
            if attrs.get("state_vars")!=old_names:raise TranslationError("F3 state vars lack exact evidence")
            indices=attrs["evidence_indices"]
            attrs["state_vars"]=sorted({translated["layers"]["L2"]["evidence"][i]["state"]["name"] for i in indices})
        if attrs["edge_type"]=="DATA_DEF_USE":
            # ddg_vars contain full symbol IDs in the frozen constructor.
            for field in ("ddg_vars","ddg_symbols","symbols"):
                if field not in attrs:continue
                pairs={e["symbol"]:tx.symbol(e) for e in proof}
                if any(x not in pairs for x in attrs[field]):raise TranslationError("Unknown F3 symbol metadata")
                attrs[field]=[pairs[x] for x in attrs[field]]
    inverse={result["names"][d["id"]]:d["name"] for d in result["declarations"] if not d["preserved"]}
    return temp,translated,result,dict(fallback_identity=False,bindings=tx.proof,projection=projection,
        original_names=inverse,metadata=tx.new_metadata,
        compiler_metadata_policy="unchanged pragma only for renamed memory text; original compilation record is not reused",
        historical_unused_diagnostics_retained=True)


def evaluate(source,file,graph,evidence,metadata=None,original_names=None):
    """Same frozen facts and E1/attribute construction, on an ephemeral subgraph."""
    from scripts.node_sem.facts import extract_source
    from scripts.node_sem.facts_schema import new_facts,validate
    from scripts.node_sem.carrier import row_key
    from scripts.edge_sem.build_f4 import inspect_file
    from scripts.edge_sem.guard_edges import task_guard_audit
    from scripts.edge_sem.attrs import compute_attributes
    plain=graph.subgraph([n for n,a in graph.nodes(data=True) if a["node_type"]!="env_source"]).copy()
    facts,diagnostics=extract_source(source,file,plain,evidence,metadata,original_names=original_names)
    # Auxiliary rows follow frozen facts.extract (SHA 5c6ba7352c902537ec4f80192963fc0c208a7a8b8691324fd122aa9e2d93dca7).
    for n,a in graph.nodes(data=True):
        if a["node_type"]=="env_source":
            fact=new_facts("env");fact["env"]["keys"]=[a["code"]]
            facts[row_key(n,a)]=fact
    for s,t,a in graph.edges(data=True):
        if a.get("edge_type")=="ENV_FLOW":
            for ev in check_layer_edge(s,t,a,evidence):
                if facts[t]["env"]:facts[t]["env"]["keys"]=sorted(set(facts[t]["env"]["keys"])|{ev["env_key"]})
    for fact in facts.values():validate(fact)
    edges,audit=inspect_file(file,source,graph)
    guard=task_guard_audit(graph,[audit],edges)
    passed=guard["nonmodifier_mapping_pass"] and audit["guards"]["correspondence_pass"]
    if not passed:raise TranslationError("F4 hard condition failed")
    ctx=dict(source_text={file:source},sources={file:dict(sha256=hashlib.sha256(source.encode()).hexdigest(),metadata=metadata)},
        audit=evidence,f4_audit=dict(hard_conditions_pass=passed,files=[audit]))
    values=compute_attributes(ctx,graph,edges,facts)
    return edges,values,diagnostics
