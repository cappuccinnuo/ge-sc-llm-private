"""Check actual multi-input CLI/API behavior and a Solidity namespace import with a disconnected file."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from compile_repair.toolchain.project import ProjectIndex,resolve_project,compile_project
from compile_repair.toolchain.solc import load_trusted_compilers
from compile_repair.toolchain.slither import run_slither

OUT=Path(__file__).resolve().parent
root=OUT.parents[3]/"compile-repair-local/cp5_v1/multi_input_probe"
root.mkdir(parents=True,exist_ok=False)
sources={"A.sol":"library Lib { function value() internal pure returns (uint) { return 7; } }",
         "Main.sol":'import "A.sol" as Space; contract Client { function f() public pure returns(uint) {return Space.Lib.value();} }',
         "Spare.sol":"contract Independent { function f() public pure returns(uint) {return 9;} }"}
for n,body in sources.items():(root/n).write_text("pragma solidity 0.8.38;\n"+body+"\n",encoding="utf8")
p=resolve_project(root,"Main.sol",index=ProjectIndex(root),additional_entries=("A.sol","Spare.sol"))
c=compile_project(p,load_trusted_compilers()[0]["0.8.38"])
def save(p,v):
    with p.open("x",encoding="utf8") as f:json.dump(v,f,indent=2);f.write("\n")
save(root/"solc.json",asdict(c))
s=run_slither(c,"production",project=p) if c.returncode==0 else {}
save(root/"slither.json",s)
shape=dict(rc=c.returncode,d3=s.get("d3"),graph_usable=s.get("graph_usable"),
           node_files=sorted({n["filename"] for n in s.get("nodes",[])}),coverage=s.get("contract_coverage"),
           receipts={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in (*sources,"solc.json","slither.json")},
           external_root=str(root),compiler=asdict(c.compiler),command=c.command)
save(OUT/"multi_input_probe.json",shape)
print(shape["rc"],shape["d3"],shape["graph_usable"],shape["node_files"],flush=True)
assert c.returncode==0 and s["d3"] and s["graph_usable"] and shape["node_files"]==sorted(sources)
