"""Probe the call-site matching rule in add_function_call_edges.

The rule is a bare substring test:

    if '_'.join(dest_method_name.split('_')[:-1]) + '(' in code:

so the callee name has its arity suffix stripped and is then looked for as
"<name>(" anywhere in the caller's source text. Three consequences to check:

  D  whitespace  - "f (1)" never contains "f(", so a legal call is missed
  E  suffix      - "f(" is a substring of "notf(", so an unrelated function whose
                   name ends with the callee's name is wired up as a call
  F  string/comment - "f(" inside a string literal or a comment still matches
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
    "D_whitespace_before_paren": """
pragma solidity ^0.4.25;
contract WS {
    uint public a;
    function target(uint x) internal { a = x; }
    function caller() public { target (7); }
}
""",
    "E_name_is_suffix_of_another": """
pragma solidity ^0.4.25;
contract Suffix {
    uint public a;
    function f(uint x) internal { a = x; }
    function notf(uint x) internal { a = x + 1; }
    function caller() public { notf(3); }
}
""",
    "F_call_text_inside_string": """
pragma solidity ^0.4.25;
contract InString {
    uint public a;
    string public s;
    function target(uint x) internal { a = x; }
    function caller() public { s = "target(1)"; }
}
""",
}


def build(src):
    with contextlib.redirect_stdout(io.StringIO()):
        return CFGDriver("solidity", src, output_file=None)


for name, src in CASES.items():
    print("=" * 74)
    print(name)
    d = build(src)
    g = d.graph
    label = {n: (data.get("label") or "").split("\n")[0][:44] for n, data in g.nodes(data=True)}
    ntype = {n: data.get("node_type") for n, data in g.nodes(data=True)}

    calls = [(s, t, data.get("edge_type")) for s, t, data in g.edges(data=True)
             if data.get("edge_type") in ("internal_call", "external_call")]
    print(f"  internal/external_call edges: {len(calls)}")
    for s, t, e in calls:
        print(f"    [{e}] {label.get(s,'')!r}")
        print(f"        -> {label.get(t,'')!r}")
    if not calls:
        print("    (none)")
    print()

print("=" * 74)
print("expected if the matcher were correct:")
print("  D  1 edge  caller -> target        (a real call written with a space)")
print("  E  1 edge  caller -> notf          (and NOT caller -> f)")
print("  F  0 edges                          ('target(1)' is string content, not a call)")
