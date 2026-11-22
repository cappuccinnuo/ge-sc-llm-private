"""Make small, independent Solidity witnesses for the sealed template inventory."""
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
def contract(members):
    return "contract Probe { " + members + " }"

def fun(body, params="", ret="", visibility="public"):
    return contract("function check("+params+") "+visibility+(" returns ("+ret+")" if ret else "")+" { "+body+" }")

CASES={
1:fun("a.transfer(0);","address a"),
2:fun("return now;","","uint"),
3:fun("return a != 0;","address a","bool"),
4:fun("return x * 0.1;","uint x","uint"),5:fun("return x * 0.8;","uint x","uint"),
6:fun("return -x;","uint x","uint"),
7:fun("assembly { let t := msize }"),
8:"contract Left { function f() public {} } contract Right { function g() public { Left.f(); } }",
11:"contract Probe { function f() public virtual; }",
12:"contract Left { function Left() internal {} } contract Right { function f() public { new Left(); } }",
13:{"Decl.sol":"contract Other {}","Probe.sol":'import {Absent} from "./Decl.sol"; contract Probe {}'},
20:contract("struct Packet {}"),
21:"contract Probe is Parent {} contract Parent {}",
22:fun("return;","","uint"),
23:contract("mapping(string => uint) public values;"),
24:contract("event Seen(); function f() public { Seen(); }"),
25:fun("return bytes1(x[0:1]);","bytes calldata x","bytes1","external"),
26:"function f() payable {}",27:"function f() public {}",28:"function f();",
29:"contract Other {} contract Probe { function f(Other x) external {} function f(address x) external {} }",
30:"contract Probe { function f() public {} contract Next {}",
31:contract("function Probe() public {}"),
32:"interface I { function f() public; }",
33:fun("assembly { let x := missing.slot }"),
34:contract("uint immutable v; constructor() { v = 1; uint w = v; }"),
35:"interface A {} interface B is A {}",
37:contract("function f(function() internal fn) external {}"),
38:contract("uint n; uint[n] a;"),
39:"contract Other {} contract Probe { using Other for uint; }",
40:contract("function f(uint[] memory a) external {}"),
41:"library L { struct Data { uint x; } function getContext(Data storage x) internal view returns(uint){return x.x;} } contract Probe { using L for L.Data; function f() public { L.Data memory t; t.getContext(); } }",
42:"library A {function f(uint32) internal pure returns(uint){return 1;}} library B {function f(uint32) internal pure returns(uint){return 2;}} contract Probe {using A for uint32; using B for uint32; function g(uint32 x) public {x.f();}}",
43:contract("function Probe() public {} constructor() public {}"),
44:contract("function f(uint x) public {} function f(bool x) public {} function g() public { assembly { let x := f } }"),
45:"contract Probe { uint x; function f() public { x y; } }",
46:contract("function f(bool x) internal {} function f(bytes memory x) internal {} function g() public { f(7); }"),
47:contract("constructor() internal {}"),
48:"uint x; contract Probe {}",
49:contract("function f() public { \n/// @dev local description\n uint x; }"),
50:"contract A {function f() public virtual {}} contract B is A {function f() public view override {}}",
51:"contract A {function f() public virtual returns(uint){return 1;}} contract B is A {function f() public override returns(bool){return true;}}",
52:"contract A {function f() public {}} contract B is A {function f() internal {}}",
53:"interface A {function x() external view returns(uint);} contract B is A {bool public override x;}",
54:contract("uint x; function f() public x {}"),
55:"pragma solidity 0.3.6; contract Probe {}",
56:contract("function f(uint storage n) internal {}"),
57:"interface A {struct Data {uint x;} }",
58:fun("assembly { let t := chainid() }"),
59:contract("function f() external constant returns(uint){return 0;}"),
87:contract("mapping(uint=>uint) m; function f() public { abi.encode(m); }"),
88:contract("function f(uint[][] memory x) public {}"),
89:contract("function f(uint[][] memory x) public {}"),
90:contract("function f(uint[][] memory x) public {}"),
91:fun("assembly { let x := true }"),
92:fun("return -x;","uint x","uint"),93:fun("return -x;","uint x","uint"),
94:"pragma abicoder v2; contract Probe {}",
95:contract("function g() public payable {} function f() public { this.g.value(0)(); }"),
96:"interface Probe {uint x;}",
}

def struct_info(text):
    name=re.search(r"struct ([\w.]+)",text).group(1)
    owner,sep,member=name.partition(".")
    return (owner,member,True) if sep else ("Types",owner,False)

def fixture(i,text):
    if i in (9,10):
        return {"Types.sol":"pragma experimental ABIEncoderV2; contract A { struct S {uint x;} function f(S memory v) public {} }",
                "Probe.sol":'import "./Types.sol"; contract B is A {}'}
    if 14<=i<=19:
        owner,member,nested=struct_info(text)
        declaration="struct "+member+" { uint x; }"
        code="function decode(bytes memory x) public { abi.decode(x, ("+(owner+"." if nested else "")+member+")); }"
        return {"Probe.sol":"pragma abicoder v1; "+("contract "+owner+" { "+declaration+" }" if nested else declaration)+" "+ contract(code)}
    if 60<=i<=86:
        if "struct " in text:
            owner,member,nested=struct_info(text)
            head="struct "+member+" { uint value; }"
            typ=owner+"."+member if nested else member
            definitions="contract "+owner+" { "+head+" }" if nested else head
        else:
            typ="bytes[]" if "bytes[]" in text else "string[]";definitions=""
        returning="return parameter" in text
        external=("function f() external returns ("+typ+" memory);" if returning else "function f("+typ+" calldata x) external;")
        code=("function g(Interface ref) public { ref.f(); }" if returning else
              "function g(Interface ref) public { "+typ+" memory x; ref.f(x); }")
        return {"Decl.sol":"pragma experimental ABIEncoderV2; "+definitions+" interface Interface { "+external+" }",
                "Probe.sol":'pragma abicoder v1; import "./Decl.sol"; '+contract(code)}
    value=CASES[i]
    return value if isinstance(value,dict) else {"Probe.sol":value}

def make():
    catalog=json.loads((HERE/"old_other_templates.json").read_bytes())["templates"]
    result=[]
    for i,(template,row) in enumerate(sorted(catalog.items()),1):
        if i==36:
            result.append(dict(id=i,template=template,mode="archived_diagnostic",source=row["examples"]["cp3"]["record"]))
            continue
        version=next(iter(row["examples"].values()))["version"]
        versions=list(dict.fromkeys([version,"0.4.24","0.5.17","0.6.12","0.7.6","0.8.0","0.8.38"]))
        files=fixture(i,template)
        result.append(dict(id=i,template=template,mode="standard_json",versions=versions,sources=files))
    return result

if __name__=="__main__":
    path=HERE.parents[1]/"tests/fixtures/cp4_1"
    path.mkdir(parents=True,exist_ok=False)
    with (path/"diagnostics.json").open("x",encoding="utf8",newline="\n") as fp:
        json.dump(make(),fp,indent=2,ensure_ascii=False);fp.write("\n")
