"""CP4.3 review probe: Yul switch names carry source offsets.

Original: helper h() after asm function f() with two switches and a nested one.  Damage: delete h().
Repair A: re-insert h() at the top of the contract (shifts f's switches).  Repair B: same, plus a
comment inserted INSIDE f's assembly block before the switch (still semantically neutral).
Repair C (wrong): change a switch case constant in f.  Must not score as equal.
"""
import json, os, sys, tempfile
repo, solc = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)
from slither import Slither
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.toolchain.slither import graph_facts
from compile_repair.evaluation.benchmark import score_graphs

H = b"    function h(uint z) internal pure returns (uint) { return z * 7 + 1; }\n"
F = (b"    function f(uint x) public pure returns (uint r) {\n"
     b"        assembly {\n"
     b"            switch x\n            case 0 { r := 1 }\n            default {\n"
     b"                switch mod(x, 2) case 0 { r := 2 } default { r := 3 }\n            }\n"
     b"        }\n        r = r + h(x);\n    }\n")
orig = b"pragma solidity ^0.8.0;\ncontract A {\n" + F + H + b"}\n"
def graph(src):
    d = tempfile.mkdtemp(); p = os.path.join(d, "A.sol"); open(p, "wb").write(src)
    return json.loads(json.dumps(graph_facts(Slither(p, solc=solc, solc_disable_warnings=True))))
def patch(raw, edits):  # edits in descending position order
    return apply_patches(raw, [Patch(a, b, raw[a:b], v, "probe") for a, b, v in edits])
s = orig.index(H)
damaged, dmap = patch(orig, [(s, s + len(H), b"")])
top = damaged.index(F)
inner = damaged.index(b"            switch x")
case = damaged.index(b"case 0 { r := 1 }") + len(b"case ")
repairs = {"insert_at_top": [(top, top, H)],
           "insert_at_top_plus_inner_comment": [(inner, inner, b"            // note\n"), (top, top, H)],
           "wrong_case_constant": [(case, case + 1, b"5"), (top, top, H)]}
truth = graph(orig)
out = {"truth_switch_names": sorted({t for n in truth["nodes"] for op in n["ir"] for t in op.split() if "switch_expr_" in t})}
for name, edits in repairs.items():
    repaired, rmap = patch(damaged, edits)
    r = score_graphs(truth, graph(repaired), {"": orig}, {"": damaged}, {"": repaired}, {"": dmap}, {"": rmap}, 0, True)
    out[name] = {"kept": r["kept"], "raw_kept": r["raw"]["kept"], "exact": r["exact"],
                 "status": r["counter_correspondence"]["status"], "reason": r["counter_correspondence"]["reason"],
                 "yul_switches": len(r["counter_correspondence"].get("yul_switches", []))}
print(json.dumps(out, indent=1))
