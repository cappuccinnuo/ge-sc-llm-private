"""Identify the leading NatSpec in the trivia between the prior Solidity token and the function."""
import json
from pathlib import Path
from move import OUT, OLD, SourceLayout, base_contents, rows, sha, write
from compile_repair.toolchain.solc import _LEXICAL


def attached(source, start):
    layout=SourceLayout(source)
    index=next(i for i,t in enumerate(layout.tokens) if t[0]==start)
    end=layout.tokens[index-1][1]
    gap=source[end:start]
    docs=[end+m.start() for m in _LEXICAL.finditer(gap)
          if m.lastgroup=="comment" and m.group().startswith((b"///",b"/**"))]
    return min(docs,default=start)


def main():
    plan=json.loads((OUT/"move_plan.json").read_bytes())["rows"]
    observed=list(rows(OUT/"moves.jsonl"))
    passed={r["unit_id"] for r in observed if not r.get("stop")}
    bases={r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}
    changes=[]
    for r in plan:
        uid=r["unit_id"];site=r["site"]
        raw=base_contents(bases[uid])[site["file"]]
        start=attached(raw,site["start"])
        if start!=site["start"]:
            changes.append(dict(unit_id=uid,start=start,old_start=site["start"],end=site["end"],
                                comment_sha256=sha(raw[start:site["start"]]),formerly_passed=uid in passed))
    stopped=observed[-1];uid=stopped["unit_id"]
    item=next(c for c in changes if c["unit_id"]==uid)
    content=base_contents(bases[uid])[stopped["site"]["file"]]
    assert b"@param service" in content[item["start"]:item["old_start"]]
    previous=sum(c["formerly_passed"] for c in changes)
    write("natspec_request.json",dict(stop=uid,diagnostic=stopped["diagnostic"],seeded_units=len(plan),observed=len(observed),
          affected=len(changes),already_passed_affected=previous,keep_successes=len(passed)-previous,new_trials=len(plan)-len(passed)+previous,
          change="Include leading NatSpec from the trivia after the prior code token in the moved declaration. Keep the selected units, functions, settings and graph criteria.",rows=changes))
    print(len(changes),previous,len(passed)-previous,len(plan)-len(passed)+previous)
if __name__=="__main__":main()
