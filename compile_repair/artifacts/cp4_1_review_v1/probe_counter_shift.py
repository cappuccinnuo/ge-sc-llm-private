"""CP4.1 review probe: does a semantically neutral repair placement change kept-node scores?

Original: helper h() declared AFTER g(). Damage: delete h() (g calls it -> undeclared).
Repair A: re-insert h() at its original place.  Repair B: insert identical h() at the top of the contract.
Both repairs are semantically equivalent; only TMP/REF numbering in kept nodes can differ.
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
orig = (b"pragma solidity ^0.8.0;\ncontract A {\n    mapping(address => uint) bal;\n"
        b"    function g(address a, uint x) public { bal[a] = bal[a] + h(x) * 2; }\n" + H + b"}\n")
def edit(raw, a, b, v): return apply_patches(raw, [Patch(a, b, raw[a:b], v, "probe")])
def graph(src):
    d = tempfile.mkdtemp(); p = os.path.join(d, "A.sol"); open(p, "wb").write(src)
    return json.loads(json.dumps(graph_facts(Slither(p, solc=solc, solc_disable_warnings=True))))
s = orig.index(H)
damaged, dmap = edit(orig, s, s + len(H), b"")
top = damaged.index(b"    mapping")
out = {}
for name, (a, b) in {"restore_in_place": (s, s), "insert_at_top": (top, top)}.items():
    repaired, rmap = edit(damaged, a, b, H)
    r = score_graphs(graph(orig), graph(repaired), {"": orig}, {"": damaged}, {"": repaired},
                     {"": dmap}, {"": rmap}, 0, True)
    out[name] = {k: r[k] for k in ("exact", "kept", "cfg_edges", "calls", "lost", "added") if k in r}
# Show the kept-node IR that differs under insert_at_top.
repaired, _ = edit(damaged, top, top, H)
g0 = [n for n in graph(orig)["nodes"] if n["key5"][1].startswith("g(")]
g1 = [n for n in graph(repaired)["nodes"] if n["key5"][1].startswith("g(")]
out["g_ir"] = {"original": [n["ir"] for n in g0], "insert_at_top": [n["ir"] for n in g1]}
print(json.dumps(out, indent=1))
