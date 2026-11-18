"""Isolate native Slither alias binding from CompileRepair graph serialization."""
import hashlib,json,sys,time
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from compile_repair.toolchain.project import resolve_project,compile_project,slither_arguments
from compile_repair.toolchain.solc import load_trusted_compilers
from compile_repair.toolchain.slither import node_facts,contract_coverage,graph_facts,read_mapping,check_profile
from crytic_compile import CryticCompile
from slither import Slither
from slither.slithir.operations import HighLevelCall
B=Path(__file__).resolve().parent;F=ROOT/"compile_repair/tests/fixtures/cp3_alias_calls"
p=resolve_project(F,"Main.sol");c=load_trusted_compilers()[0]["0.8.38"]
compiled=compile_project(p,c)
record={"solc":asdict(compiled),"profile":check_profile("production"),"inputs":p.manifest(),
        "uses_production_graph_serializer_for_native_observation":False}
assert compiled.returncode==0
target,kwargs=slither_arguments(p,c);start=time.monotonic();cc=CryticCompile(target,**kwargs);s=Slither(cc,**kwargs)
record["slither"]={"command":{"target":target,"kwargs":kwargs},"constructed":True,"elapsed_seconds":time.monotonic()-start,
 "api_subprocess_returncodes_observed":False,"preceding_observed_solc_returncode":0,"cost_usd":0,
 "d3_a":node_facts(s,[f.path for f in p.files])["mapping_complete"],
 "d3_b":contract_coverage(s,[f.path for f in p.files])["complete"]}
def describe(obj):
 if obj is None:return None
 out={"type":type(obj).__name__,"name":getattr(obj,"name",None),"full_name":getattr(obj,"full_name",None)}
 try:out["mapping"]=read_mapping(obj.source_mapping)
 except (AttributeError,ValueError):pass
 return out
contracts=[];calls=[]
for contract in s.contracts:
 contracts.append(dict(describe(contract),functions=[describe(f) for f in contract.functions_declared]))
 for function in contract.functions_declared:
  for node in function.nodes:
   for ir in node.irs:
    if isinstance(ir,HighLevelCall):
     destination=ir.destination;ty=getattr(destination,"type",None)
     calls.append({"caller":describe(function),"node":read_mapping(node.source_mapping),"ir":str(ir),
       "destination":describe(destination),"destination_type":describe(getattr(ty,"type",ty)),
       "callee":describe(ir.function),"callee_contract":describe(getattr(ir.function,"contract_declarer",None))})
record["native_contracts"]=contracts;record["native_high_level_calls"]=calls
asts=[]
def walk(node,filename):
 if isinstance(node,dict):
  if node.get("nodeType") in ("ContractDefinition","VariableDeclaration","IdentifierPath","Identifier","MemberAccess"):
   asts.append({"filename":filename,**{k:node[k] for k in ("nodeType","id","name","memberName","referencedDeclaration","src","typeDescriptions","typeName") if k in node}})
  for value in node.values():walk(value,filename)
 elif isinstance(node,list):
  for value in node:walk(value,filename)
for unit in cc.compilation_units.values():
 for filename,ast in unit.asts.items():walk(ast,str(filename))
record["compiler_ast_declarations_and_references"]=asts
record["serialized_project_graph"]=graph_facts(s,p.root)
with (B/"alias_call_probe.json").open("x") as f:json.dump(record,f,indent=2);f.write("\n")
print(json.dumps({"d3":record["slither"],"calls":calls},indent=2))
