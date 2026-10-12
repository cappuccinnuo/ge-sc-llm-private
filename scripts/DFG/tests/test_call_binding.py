"""B1 regressions. All locally authored Solidity examples are UNCOMPILED.
Some tests deliberately exercise parser robustness; see B1_FIX_2026-10-12.md.
No test downloads or invokes a compiler.
"""
from scripts.DFG.ddg_builder import DDGBuilder

POINTER_SOURCE = """pragma solidity ^0.5.17;
contract C {
    function(address payable) internal selfdestruct;
    function g(address payable a) internal {}
    constructor() public { selfdestruct = g; }
    function f(address payable a) public returns (uint) {
        selfdestruct(a);
        uint x = 1;
        return x;
    }
}
"""

def fact_codes(source, result):
    raw = source.encode("utf8")
    return {(raw[f.definition.anchor.start:f.definition.anchor.end].decode(),
             raw[f.use.anchor.start:f.use.anchor.end].decode())
            for f in result.facts}

def test_b1_state_function_pointer_keeps_successor_and_def_use():
    result = DDGBuilder().analyze_source(POINTER_SOURCE, "b1.sol")
    assert not [d for d in result.diagnostics if d["kind"] == "function_fallback"]
    assert ("uint x = 1;", "return x;") in fact_codes(POINTER_SOURCE, result)
