"""Token-budgeted CTX rendering; no graph, torch, or mando imports."""
from collections import OrderedDict
import copy

VERSION="nodesem-ctx-budget-v1"
FALLBACK_ORDER=("TO","FROM","FN_SUMMARY","CONTRACT","STATE_DECL","GUARD","COND",
                "PRE_EXT_CALL","CALL","LOOP","ENV","STATE_R","STATE_W","FUNC","USE","DEF","STMT")


def render(fields):
    return "\n".join("["+key+"] "+" | ".join(value) for key,value in fields.items())


def truncate(fields,tokenizer,limit=256):
    fields=OrderedDict((k,list(v)) for k,v in fields.items())
    if any(not v or not all(isinstance(x,str) for x in v) for v in fields.values()):
        raise ValueError("CTX fields must contain nonempty lists of strings")
    def length():return len(tokenizer.encode(render(fields),add_special_tokens=True))
    original=length()
    stage=0
    history=[dict(stage=0,tokens=original)]
    for level in range(1,8):
        if length()<=limit:break
        stage=level
        if level==1:
            for k in ("TO","FROM"):
                if k in fields:fields[k]=fields[k][:1]
        elif level==2:
            for k in ("FN_SUMMARY","CONTRACT","STATE_DECL"):
                if k in fields:fields[k]=fields[k][:4]
        elif level==3:
            for k,prefixes in (("GUARD",("kind:","eq:")),("COND",("eq:",))):
                if k in fields and fields[k] not in (["-"],["unknown"]):
                    fields[k]=[v for v in fields[k] if v.startswith(prefixes)] or ["-"]
        elif level==4:
            if "PRE_EXT_CALL" in fields:
                fields["PRE_EXT_CALL"]=[v.split(": ",1)[0] for v in fields["PRE_EXT_CALL"]]
            if "CALL" in fields and fields["CALL"] not in (["-"],["unknown"],["uninvoked_call_value"]):
                fields["CALL"]=[v for v in fields["CALL"] if v.startswith(("kinds:","target:"))]
        elif level==5:
            for k in ("DEF","USE"):
                if k in fields:
                    counts={};kept=[]
                    for value in fields[k]:
                        role=value.split(":")[1] if ":" in value else "none"
                        counts[role]=counts.get(role,0)+1
                        if counts[role]<=3:kept.append(value)
                    fields[k]=kept or ["-"]
            for k in ("STATE_R","STATE_W","ENV"):
                if k in fields:fields[k]=fields[k][:3]
        elif level==6:
            if "FUNC" in fields:
                fields["FUNC"]=[v for v in fields["FUNC"] if v.startswith(("visibility:","guards:"))] or ["-"]
        else:
            _trim_field(fields,"STMT",tokenizer,limit)
        history.append(dict(stage=level,tokens=length()))
    fallback=[]
    if length()>limit:
        stage=8
        for key in FALLBACK_ORDER:
            if length()<=limit:break
            if key in fields:
                before=list(fields[key])
                _trim_field(fields,key,tokenizer,limit)
                if fields[key]!=before:fallback.append(key)
        history.append(dict(stage=8,tokens=length()))
    if length()>limit:raise ValueError("CTX field labels alone exceed token budget")
    return render(fields),dict(stage=stage,original_tokens=original,final_tokens=length(),
        history=history,fallback_fields=fallback,retained_fields=list(fields))


def _trim_field(fields,key,tokenizer,limit):
    if key not in fields:return
    text=" | ".join(fields[key])
    # Prefix truncation is measured by the actual tokenizer after every update.
    # Never decode a truncated BPE sequence into invalid Unicode.
    while len(tokenizer.encode(render(fields),add_special_tokens=True))>limit and text:
        current=len(tokenizer.encode(render(fields),add_special_tokens=True))
        remove=max(1,min(len(text), (current-limit)*2))
        text=text[:-remove]
        fields[key]=[text if text else "-"]
    if not text:fields[key]=["-"]
