"""Check whether add_dummy_edges emits call edges where no call exists.

The claim under test: a contract whose functions never call each other still gets
'recursive_method_call' edges from the contract node to its function nodes, i.e. the
edge encodes containment, not a call.

Reason to suspect it: CFG_solidity.function_list is documented as collecting "method
invocations" but its guard tests current_node.type against statement_types['method_type'],
which is the set of *declaration* types. So records['function_calls'] is keyed by every
function DEFINITION, paired with the enclosing method_type ancestor. add_dummy_edges
then joins that ancestor to the method, regardless of whether a call was written.

Three minimal contracts isolate it:
  A  two functions, no calls at all
  B  one function calling another in the same contract
  C  two overloads of the same name with different arity
"""
import contextlib
import io
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from process_graphs.tree_sitter_codeviews.codeviews.CFG.CFG_driver import CFGDriver  # noqa: E402

CASES = {
    "A_no_calls": """
pragma solidity ^0.4.25;
contract NoCalls {
    uint public a;
    function setA(uint x) public { a = x; }
    function getA() public view returns (uint) { return a; }
}
""",
    "B_one_internal_call": """
pragma solidity ^0.4.25;
contract OneCall {
    uint public a;
    function helper(uint x) internal { a = x; }
    function caller(uint y) public { helper(y); }
}
""",
    "C_overloads": """
pragma solidity ^0.4.25;
contract Overloads {
    uint public a;
    function f(uint x) public { a = x; }
    function f(uint x, uint y) public { a = x + y; }
    function g() public { f(1); }
}
""",
}


def build(src):
    with contextlib.redirect_stdout(io.StringIO()):
        driver = CFGDriver("solidity", src, output_file=None)
    return driver


for name, src in CASES.items():
    print("=" * 74)
    print(name)
    print("=" * 74)
    d = build(src)
    g = d.graph

    label = {n: (data.get("label") or "").split("\n")[0][:46] for n, data in g.nodes(data=True)}
    ntype = {n: data.get("node_type") for n, data in g.nodes(data=True)}

    et = Counter(data.get("edge_type") for _, _, data in g.edges(data=True))
    print(f"  nodes {g.number_of_nodes()}  edges {g.number_of_edges()}   {dict(et)}")

    print("  records['function_calls'] (keyed by what?):")
    for k, v in d.CFG.records["function_calls"].items():
        print(f"    {k:22s} -> {v}")
    print("  records['method_list']:")
    for k, v in d.CFG.records["method_list"].items():
        print(f"    {k:22s} -> {v}")

    call_like = [(s, t, data.get("edge_type")) for s, t, data in g.edges(data=True)
                 if data.get("edge_type") in ("recursive_method_call", "internal_call",
                                              "external_call", "function_call",
                                              "function_return")]
    print(f"  call-typed edges: {len(call_like)}")
    for s, t, e in call_like:
        print(f"    [{e}]  {ntype.get(s)} {label.get(s,'')!r}")
        print(f"          -> {ntype.get(t)} {label.get(t,'')!r}")
    print()
