"""CP4.3 review probe: one changed kept node plus a neutral insertion.

Contract with g() and k() after the damaged helper h().  Damage: delete h().
Repair A: insert h() at the top (neutral; shifts TMP/REF numbering in g and k).
Repair B: A plus change one constant in k() (a genuine change to ONE kept node).
Expectation for a proportional scorer: B loses only k()'s changed node, not every renumbered node.
"""
import json, os, sys, tempfile
repo, solc = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)
from slither import Slither
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.toolchain.slither import graph_facts
from compile_repair.evaluation.benchmark import score_graphs

H = b"    function h(uint z) internal pure returns (uint) { uint[] memory t = new uint[](z); return t.length * 7 + 1; }\n"
body = (b"    mapping(address => uint) bal;\n"
        b"    function g(address a, uint x) public { bal[a] = bal[a] + h(x) * 2; }\n"
        b"    function k(address a, uint y) public { bal[a] = bal[a] * 3 + y; if (y > 9) { bal[a] = bal[a] - 1; } }\n")
orig = b"pragma solidity ^0.8.0;\ncontract A {\n" + body + H + b"}\n"
def graph(src):
    d = tempfile.mkdtemp(); p = os.path.join(d, "A.sol"); open(p, "wb").write(src)
    return json.loads(json.dumps(graph_facts(Slither(p, solc=solc, solc_disable_warnings=True))))
def patch(raw, edits):
    return apply_patches(raw, [Patch(a, b, raw[a:b], v, "probe") for a, b, v in edits])
s = orig.index(H)
damaged, dmap = patch(orig, [(s, s + len(H), b"")])
top = damaged.index(b"    mapping")
c = damaged.index(b"* 3 + y") + 2
out = {}
for name, edits in {"neutral_insert": [(top, top, H)],
                    "neutral_insert_plus_one_changed_node": [(c, c + 1, b"4"), (top, top, H)],
                    "one_changed_node_only_in_place": [(s, s, H), (c, c + 1, b"4")]}.items():
    edits = sorted(edits, key=lambda e: -e[0])
    repaired, rmap = patch(damaged, edits)
    r = score_graphs(graph(orig), graph(repaired), {"": orig}, {"": damaged}, {"": repaired}, {"": dmap}, {"": rmap}, 0, True)
    out[name] = {"kept": r["kept"], "status": r["counter_correspondence"]["status"],
                 "reason": r["counter_correspondence"]["reason"]}
print(json.dumps(out, indent=1))
