"""Solidity cases transcribed from the two read-only CP4.3 review fixtures."""
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches

HELPER=b"    function h(uint z) internal pure returns (uint) { uint[] memory t = new uint[](z); return t.length * 7 + 1; }\n"
BODY=(b"    mapping(address => uint) bal;\n"
      b"    function g(address a, uint x) public { bal[a] = bal[a] + h(x) * 2; }\n"
      b"    function k(address a, uint y) public { bal[a] = bal[a] * 3 + y; if (y > 9) { bal[a] = bal[a] - 1; } }\n")
ASM_HELPER=b"    function h(uint z) internal pure returns (uint) { return z * 7 + 1; }\n"
ASM=(b"    function f(uint x) public pure returns (uint r) {\n"
     b"        assembly {\n"
     b"            switch x\n            case 0 { r := 1 }\n            default {\n"
     b"                switch mod(x, 2) case 0 { r := 2 } default { r := 3 }\n            }\n"
     b"        }\n        r = r + h(x);\n    }\n")


def cases(kind):
    body,helper=(ASM,ASM_HELPER) if kind=="yul" else (BODY,HELPER)
    source=b"pragma solidity ^0.8.0;\ncontract A {\n"+body+helper+b"}\n"
    start=source.index(helper)
    middle,damage=apply_patches(source,[Patch(start,start+len(helper),helper,b"","damage")])
    top=middle.index(body)
    insert=Patch(top,top,b"",helper,"insert")
    if kind=="yul":
        note=middle.index(b"            switch x")
        at=middle.index(b"case 0 { r := 1 }")+5
        options=[[insert],[Patch(note,note,b"",b"            // note\n","comment"),insert],
                 [Patch(at,at+1,b"0",b"5","case"),insert]]
    else:
        at=middle.index(b"* 3 + y")+2
        change=Patch(at,at+1,b"3",b"4","constant")
        options=[[insert],[change,insert],[Patch(start,start,b"",helper,"restore"),change]]
    for label,edits in zip("ABC",options):
        fixed,repair=apply_patches(middle,edits)
        yield label,(source,middle,fixed,damage,repair)
