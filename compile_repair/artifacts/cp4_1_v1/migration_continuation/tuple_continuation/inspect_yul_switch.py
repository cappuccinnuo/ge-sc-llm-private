"""Inspect a sealed, failed migration without running a compiler or altering a graph."""
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from batch import HERE as BATCH, OLD, checked, rows, sha
from replay import restore_sample
from compile_repair.evaluation.benchmark import (
    _at_original, _comparison_graph, _correspondence, _nodes, _verified_migration, base_contents)

NAME = re.compile(r"(?<![\w$])switch_expr_(\d+)_(\d+)_(\d+)(_[\w$]+)?(?![\w$])")


def diagnose():
    stop_path = HERE / "stop.json"
    stop = json.loads(stop_path.read_bytes())
    obs_file = BATCH / (stop["cohort"] + "_observations.jsonl.gz")
    obs = next(x for x in rows(obs_file) if x["unit_id"] == stop["unit_id"] and x["operator"] == stop["operator"])
    bases = {b["unit_id"]: b for b in rows(OLD / "bases.jsonl.gz")}
    base = bases[stop["unit_id"]]
    source = base_contents(base)
    _, damaged, moved, first, second = restore_sample(base, source, obs, migration=True)
    reverse = {v:k for k,v in stop["file_renames"].items()}
    repaired = {reverse.get(k,k):v for k,v in moved.items()}
    maps, _, _ = _correspondence(source, damaged, repaired, first, second)
    graphs, inputs, seen = [], [], []
    for key, renames in (("graph", {}), ("migration_graph", reverse)):
        ref = stop[key]
        result = json.loads(checked(ref["result_path"], ref["result_sha256"]))
        attempt = result["attempts"][-1]
        filename = next(k for k in (source if not renames else moved) if k.endswith("/proxy/Proxy.sol"))
        ast = next(e for e in attempt["slither"]["contract_coverage"]["asts"] if Path(e["path"]).relative_to(attempt["solc"]["cwd"]).as_posix() == filename)
        code = (source if not renames else moved)[filename]
        graph, _ = _comparison_graph(json.loads(checked(ref["graph_path"], ref["graph_sha256"])), renames, True)
        matches = [m for node in graph["nodes"] for op in node["ir"] for m in NAME.finditer(op)]
        assert len(matches) == 2 and matches[0].group() == matches[1].group()
        name = matches[0].group()
        start, length, index = map(int, matches[0].groups()[:3])
        snippet = code[start:start+length]
        assert len(snippet) == length and snippet.startswith(b"switch") and name.encode() not in code
        seen.append(name)
        def alter(text):
            return NAME.sub(lambda m: "CP41_REVIEW_SWITCH" if m.group() == name else m.group(), text)
        graph["nodes"] = [dict(n, ir=[alter(x) for x in n["ir"]]) for n in graph["nodes"]]
        graph["calls"] = [dict(call, callee=dict(call["callee"], text=alter(call["callee"]["text"]))) if "text" in call["callee"] else call for call in graph["calls"]]
        graphs.append(graph)
        inputs.append(dict(file=filename, file_sha256=sha(code), switch_start=start, switch_length=length,
                           switch_bytes_sha256=sha(snippet), displayed_source_index=index, generated=name,
                           occurrences=len(matches), recorded_ast_sha256=ast["ast_sha256"],
                           recorded_stdout_sha256=attempt["solc"]["stdout_sha256"], argv=attempt["solc"]["command"]))
    positions = {}
    for name, key in _nodes(graphs[0]):
        offset = key[3]
        if name in maps and offset < len(source[name]):
            segment = _at_original(maps[name][2], offset)
            offset = segment.new_start + offset - segment.original_start
        elif name in maps:
            offset = len(repaired[name])
        positions[name,key] = (name,key[:3]+(offset,)+key[4:])
    _, verified = _verified_migration(graphs[0],graphs[1],positions,source,repaired)
    assert inputs[0]["switch_bytes_sha256"] == inputs[1]["switch_bytes_sha256"] and inputs[0]["file_sha256"] == inputs[1]["file_sha256"]
    program = Path(sys.executable).resolve().parents[1] / "lib/python3.10/site-packages/slither/solc_parsing/yul/parse_yul.py"
    slither = program.read_bytes()
    line = next(x.strip() for x in slither.decode().splitlines() if 'f"switch_expr_' in x)
    ids = {x["unit_id"] for phase in ("new","supplement") for x in rows(BATCH/(phase+"_observations.jsonl.gz")) if x["operator"] == stop["operator"]}
    containing = []
    for uid in sorted(ids):
        b = bases[uid]
        if b"switch_expr_" in checked(b["graph_path"], b["graph_sha256"]):
            containing.append(uid)
    bound = min(74,len(containing))*2
    return dict(unit=stop["unit_id"], stop_sha256=sha(stop_path.read_bytes()), inputs=inputs,
                installed_slither_source=str(program), installed_source_sha256=sha(slither), verified_generator=line,
                review_only="View substitution for exactly these two names; no scientific acceptance or compiler invocation.",
                full_nodes=verified["nodes"], full_cfg_edges=verified["cfg_edges"], full_calls=verified["calls"],
                packages=len(ids), truth_graphs_with_switch_prefix=containing, max_extra_solc_calls=bound,
                proposed="Require YulSwitch src, exact byte span and sourceList index in the authenticated combined JSON for each side. Only the numeric file index may differ. Exclude source identifiers and literals. Preserve all other IR facts, edges, calls and both scores.",
                phases={"accepted":40,"current_pair_reusable":1,"remaining_pairs":73})
if __name__ == "__main__":
    report = diagnose()
    with (HERE/"yul_switch_review.json").open("x", encoding="utf8") as fp:
        json.dump(report, fp, indent=2, ensure_ascii=False)
        fp.write("\n")
    print(report["unit"],report["full_nodes"],report["full_cfg_edges"],report["full_calls"],len(report["truth_graphs_with_switch_prefix"]),report["max_extra_solc_calls"])
