"""Inspect already measured Yul source offsets. This is outside the scoring interface."""
import json
import re
from pathlib import Path

from move import OUT, OLD, rows, checked, sha, base_contents, write
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.evaluation.benchmark import (
    _YUL_SWITCH, _nodes, _map_graph_ir, _guard_counter_sources, score_graphs,
)


def explain(row, base):
    site = row["site"]
    filename = site["file"]
    a, b, t = site["start"], site["end"], site["insert"]
    raw = base_contents(base)
    fragment = raw[filename][a:b]
    fixed = dict(raw)
    fixed[filename], repair = apply_patches(raw[filename], [
        Patch(a, b, fragment, b"", "delete_function"),
        Patch(t, t, b"", b"\n" + fragment + b"\n", "insert_function"),
    ])
    assert sha(fixed[filename]) == row["source_after_sha256"]
    truth = json.loads(checked(base["graph_path"], base["graph_sha256"]))
    actual = json.loads(checked(row["graph_path"], row["graph_sha256"]))
    target = _nodes(actual)
    pairs, reverse, seen, defined, used = {}, {}, {}, set(), set()
    kept = set()

    def project(offset):
        if t <= offset < a:
            return offset+b-a+2
        if offset >= b:
            return offset+2
        if offset < t:
            return offset
        raise ValueError("switch intersects moved function")

    for n in truth["nodes"]:
        name = n.get("filename", "")
        key = list(n["key5"])
        if name == filename and a <= key[3] < b:
            continue
        original_start = key[3]
        if name == filename:
            key[3] = project(original_start)
        dest = (name, tuple(key))
        kept.add(dest)
        other = target[dest]
        assert len(n["ir"]) == len(other["ir"])
        for l, r in zip(n["ir"], other["ir"]):
            before = list(_YUL_SWITCH.finditer(l))
            after = list(_YUL_SWITCH.finditer(r))
            assert len(before) == len(after)
            for x,y in zip(before,after):
                if x.group() == y.group():
                    continue
                start,length = map(int,x.group(1,2))
                new_start = int(y.group(1))
                assert name == filename and x.groups()[1:] == y.groups()[1:]
                assert project(start) == new_start and project(start+length-1) == new_start+length-1
                assert start <= original_start < start+length and new_start <= key[3] < new_start+length
                data = raw[name][start:start+length]
                assert len(data) == length and re.match(rb"switch\b",data)
                assert fixed[name][new_start:new_start+length] == data
                k, v = (name,x.group()), (name,y.group())
                assert pairs.setdefault(k,v) == v and reverse.setdefault(v,k) == k
                seen[k] = dict(name=name,old=x.group(),new=y.group(),old_start=start,
                               new_start=new_start,length=length,source_index=int(x.group(3)),sha256=sha(data))
                (defined if x.start()==0 and re.match(r"\([^)]*\) := ",l[x.end():]) else used).add(k)
    assert seen and set(seen) <= (defined & used)
    protected = {v[1].encode("utf8") for v in (*pairs,*reverse)}
    _guard_counter_sources(raw,fixed,protected,imports_only=False)
    def substitute(name, text):
        return _YUL_SWITCH.sub(lambda m: reverse.get((name,m.group()),(name,m.group()))[1],text)
    diagnostic = score_graphs(truth,_map_graph_ir(actual,substitute,kept),raw,raw,fixed,{},{filename:repair},0,True)
    ratios = {k:diagnostic[k]["ratio"] for k in ("kept","cfg_edges","calls")}
    assert all(v==1 for v in ratios.values()) and not diagnostic["missing_kept"]
    assert diagnostic["lost"]==diagnostic["added"]==row["expected_moved_nodes"]
    assert diagnostic["counter_correspondence"]["status"]!="rejected"
    return dict(unit_id=row["unit_id"],changes=list(seen.values()),diagnostic_ratios=ratios,
                unchanged_official_score=row["score"],scope="IR and source-range diagnosis only. Does not verify compiler AST or alter official fields.")


if __name__=="__main__":
    rec=json.loads((OUT/"unexplained_move_stop.json").read_bytes())["row"]
    base=next(b for b in rows(OLD/"bases.jsonl.gz") if b["unit_id"]==rec["unit_id"])
    detail=explain(rec,base)
    import slither.solc_parsing.yul.parse_yul as parser
    path=Path(parser.__file__)
    detail["installed_parser"]=dict(path=str(path),sha256=sha(path.read_bytes()),line=next(
        i for i,l in enumerate(path.read_text().splitlines(),1) if 'switch_expr_{ast[' in l))
    write("observed_yul_positions.json",detail)
    print(detail["unit_id"],len(detail["changes"]),detail["diagnostic_ratios"])
