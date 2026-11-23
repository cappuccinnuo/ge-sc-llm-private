"""CP4.4 review probe (synthetic graphs, no compiler): stale generated names in wrong repairs.

Every graph is one function T.f() with EXPRESSION nodes at offsets 0, 2, 4, ...; sources are unchanged
bytes, so all nodes are kept and the scorer only has to decide which nodes are equal.
A correct repair that shifts numbering renames every temporary consistently (TMP_4 -> TMP_8, TMP_5 -> TMP_9).
A wrong repair keeps a stale name in a USE node, so that node now reads a different value.
Per-node truth ("correct_nodes") is stated for each case; a sound scorer must never count more.
"""
import json, sys
sys.path.insert(0, sys.argv[1])
from compile_repair.evaluation.benchmark import score_graphs

def g(*irs):
    nodes = [dict(key5=["T", "f()", "EXPRESSION", 2 * i, 1], node_type="EXPRESSION", ir=[ir], length=1)
             for i, ir in enumerate(irs)]
    return {"nodes": nodes, "cfg_edges": [], "calls": []}
src = {"": b"abcdefghij"}
P4, P8 = "TMP_4(uint256) = x (c)+ 1", "TMP_8(uint256) = x (c)+ 1"
U4, U8, U5 = "y(uint256) := TMP_4(uint256)", "y(uint256) := TMP_8(uint256)", "y(uint256) := TMP_5(uint256)"
Q5, Q9 = "TMP_5(uint256) = y (c)* 2", "TMP_9(uint256) = y (c)* 2"
cases = {
    # name: (truth, actual, number of nodes that are really correct)
    "correct_shift": (g(P4, U4, Q5), g(P8, U8, Q9), 3),
    "one_stale_use": (g(P4, U4, Q5), g(P8, U4, Q9), 2),
    "three_stale_uses": (g(P4, U4, U4, U4, Q5), g(P8, U4, U4, U4, Q9), 2),
    "unshifted_wrong_use": (g(P4, U4, Q5), g(P4, U5, Q5), 2),
}
out = {}
for name, (truth, actual, correct) in cases.items():
    r = score_graphs(truth, actual, src, src, src, {}, {}, 0, True)
    out[name] = {"correct_nodes": correct, "scored_equal": r["kept"]["equal"], "units": r["kept"]["units"],
                 "over_counted": r["kept"]["equal"] > correct, "raw_equal": r["raw"]["kept"]["equal"],
                 "status": r["counter_correspondence"]["status"], "nodes": r["counter_correspondence"].get("nodes")}
print(json.dumps(out, indent=1))
