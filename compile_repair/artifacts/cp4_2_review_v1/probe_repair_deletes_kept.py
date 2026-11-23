"""CP4.2 review probe: a repair that deletes UNDAMAGED original code.

Original: g() calls h(); u() is an unrelated public function with real IR.
Damage: delete h() (undeclared).  Repair: restore h() in place AND delete u().
A correct scorer must not report kept/edge/call ratios of 1 as if no original code were destroyed.
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
U = b"    function u(uint q) public { if (q > 3) { bal[msg.sender] = q; } else { bal[msg.sender] = h(q); } }\n"
orig = (b"pragma solidity ^0.8.0;\ncontract A {\n    mapping(address => uint) bal;\n"
        b"    function g(address a, uint x) public { bal[a] = bal[a] + h(x) * 2; }\n" + H + U + b"}\n")
def edit(raw, a, b, v): return apply_patches(raw, [Patch(a, b, raw[a:b], v, "probe")])
def graph(src):
    d = tempfile.mkdtemp(); p = os.path.join(d, "A.sol"); open(p, "wb").write(src)
    return json.loads(json.dumps(graph_facts(Slither(p, solc=solc, solc_disable_warnings=True))))
s = orig.index(H)
damaged, dmap = edit(orig, s, s + len(H), b"")
restored, _ = edit(damaged, s, s, H)
u = restored.index(U)
repaired = restored[:u] + restored[u + len(U):]
# One repair map: insert H at s, delete U (positions in damaged coordinates).
ud = damaged.index(U)
repaired2, rmap = apply_patches(damaged, [Patch(ud, ud + len(U), U, b"", "probe"), Patch(s, s, b"", H, "probe")])
assert repaired2 == repaired
r = score_graphs(graph(orig), graph(repaired), {"": orig}, {"": damaged}, {"": repaired}, {"": dmap}, {"": rmap}, 0, True)
keys = ("exact", "kept", "missing_kept", "cfg_edges", "calls", "lost", "affected_by_damage", "added")
print(json.dumps({"truth_nodes_in_u": sum(1 for n in graph(orig)["nodes"] if n["key5"][1].startswith("u(")),
                  "score": {k: r[k] for k in keys if k in r}}, indent=1))
