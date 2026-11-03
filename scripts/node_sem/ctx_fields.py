"""CTX fields from sealed facts and exact, disposable AST text sidecars.

Original and locally masked names share one renderer. Dataset/source identities
remain metadata; no targets, predictions or absolute positions enter fields.
"""
from collections import OrderedDict, defaultdict
import re
from .facts_schema import validate, STATEMENT_KINDS, FUNCTION_KINDS
from .text_view import normalize
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import reserved

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
