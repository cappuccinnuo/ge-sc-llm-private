"""Stage F static-analysis candidates; no fixture claimed solc-validated."""
import csv,hashlib,json
import pytest
from scripts.DFG.models import Unsupported
from scripts.DFG.frontend import SourceView
from scripts.DFG.state.analyzer import analyze_source as old
from scripts.DFG.state.stage_f.analyzer import analyze_source,StageFCFGBuilder
from scripts.DFG.state.stage_f.frontend import StageFSourceView
from scripts.DFG.state.stage_f.versioning import interval
from scripts.DFG.call_binding import NON_BUILTIN,BUILTIN
def code(body,decl="uint s;",params="",pragma="0.5.17"):
 return "pragma solidity "+pragma+";contract A{"+decl+"function f("+params+") public returns(uint){"+body+"}}"
def result(src,name="f"):
 v,rs=analyze_source(src)
 for r in rs:
  fn=next(n for n in v.functions if r.function==v.file+":"+str(n.start_byte))
  nm=fn.child_by_field_name("name")
  if nm is not None and nm.text.decode()==name:return v,r
 raise AssertionError(name)
def facts(r):return {(f.definition.anchor.start,f.use.anchor.start,f.location_id,f.certainty) for f in r.facts}
def test_same_unit_inherited_scalar_restores_definition():
 src="pragma solidity 0.5.17;contract A{uint internal s;}contract B is A{function f() public returns(uint){s=1;return s;}}"
 _,before=old(src);assert before[0].status=="function_fallback"
 v,r=result(src);assert r.status=="supported_subset" and len(r.facts)==1
 assert r.facts[0].definition.location.root.contract.start==src.index("contract A")
 assert len(r.binding_evidence["scope"]["chain"])==2
def test_parameter_shadows_inherited_state():
 _,r=result("pragma solidity 0.5.17;contract A{uint s;}contract B is A{function f(uint s) public returns(uint){s=1;return s;}}")
 assert r.status=="supported_subset" and not r.ir.locations and not r.facts
@pytest.mark.parametrize("bases,extra",[
 ("A,C","contract C{uint t;}"),("Missing",""),("A","contract A{uint other;}")])
def test_non_closed_base_falls_back(bases,extra):
 _,r=result("pragma solidity 0.5.17;contract A{uint s;}"+extra+"contract B is "+bases+"{function f() public returns(uint){s=1;return s;}}")
 assert r.status=="function_fallback" and r.ir is None and not r.facts
def test_cycle_and_conflicting_state_rejected():
 for src in [
 "contract A is B{uint s;}contract B is A{function f() public returns(uint){return s;}}",
 "contract A{uint s;}contract B is A{uint s;function f() public returns(uint){s=1;return s;}}"]:
  _,r=result("pragma solidity 0.5.17;"+src);assert r.status=="function_fallback" and not r.facts
def test_private_base_not_silently_treated_as_global():
 _,r=result("pragma solidity 0.5.17;contract A{uint private s;}contract B is A{function f() public returns(uint){return s;}}")
 assert r.status=="function_fallback" and "private" in str(r.diagnostics)
def test_import_stays_fallback():
 _,r=result('pragma solidity 0.5.17;import "A.sol";contract B{uint s;function f() public returns(uint){s=1;return s;}}')
 assert r.status=="function_fallback"
def test_inherited_fake_revert_preserves_successor():
 src="pragma solidity 0.4.24;contract A{function revert() internal {}}contract B is A{uint s;function f() public returns(uint){s=1;revert();s=2;return s;}}"
 v,r=result(src);assert r.status=="supported_subset" and len(r.facts)==1
 assert v.raw[r.facts[0].definition.anchor.start:r.facts[0].definition.anchor.end]==b"s=2;"
 assert any(x["classification"]==NON_BUILTIN for x in r.binding_evidence["calls"])
def test_inherited_builtin_terminal_truncates():
 src="pragma solidity 0.5.17;contract A{uint s;}contract B is A{function f() public returns(uint){s=1;revert();return s;}}"
 _,r=result(src);assert r.status=="supported_subset" and not r.facts
 assert any(x["classification"]==BUILTIN for x in r.binding_evidence["calls"])
def test_fake_require_is_havoc_not_pure():
 src=code("s=1;require(true);return s;","uint s;function require(bool c) internal {}")
 _,r=result(src);assert r.status=="supported_subset" and not r.facts and r.unknown_reads
def test_require_keeps_nested_effect():
 src=code("s=1;require(g());return s;","uint s;function g() internal returns(bool){return true;}")
 _,r=result(src);assert not r.facts and any(e.kind=="HAVOC" for es in r.ir.events.values() for e in es)
def test_multiple_pragma_intersection_exact_ast_unchanged():
 src="pragma solidity >=0.4.20 <0.6.0;"+code("s=1;require(true);return s;")
 v,r=result(src);assert v.version_interval==((0,5,17),(0,5,18));assert len(r.facts)==1
 assert v.source==src
def test_multiple_pragma_opaque_call_retains_havoc():
 src="pragma solidity >=0.4.20 <0.6.0;"+code("s=1;g();return s;","uint s;function g() internal {}")
 _,r=result(src);assert r.status=="supported_subset" and not r.facts
@pytest.mark.parametrize("pragma",["^0.4.0",">=0.5.17"])
def test_wide_pragma_does_not_pick_convenient_version(pragma):
 _,r=result(code("s=1;require(true);return s;",pragma=pragma))
 assert r.status=="supported_subset" and not r.facts and r.unknown_reads
def metadata(tmp_path,src,version):
 origin=tmp_path/"dataset/example.sol";origin.parent.mkdir();origin.write_text(src)
 path=tmp_path/"versions.csv"
 with path.open("w") as f:
  w=csv.DictWriter(f,fieldnames=["file","compiled version"]);w.writeheader();w.writerow({"file":"dataset/example.sol","compiled version":version})
 return {"source_path":str(origin),"source_sha256":hashlib.sha256(src.encode()).hexdigest(),"csv_path":str(path),
         "csv_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"row_file":"dataset/example.sol","version":version}
def test_recorded_compiler_only_for_identical_source(tmp_path):
 src=code("s=1;require(true);return s;",pragma="^0.4.0");m=metadata(tmp_path,src,"0.4.24")
 v,rs=analyze_source(src,metadata=m);assert len(rs[0].facts)==1
 assert v.version_evidence["kind"]=="dataset_recorded_compiled_version" and not v.version_evidence["independently_compiled"]
 with pytest.raises(Unsupported):analyze_source(src+" ",metadata=m)
def test_metadata_contradicts_pragma(tmp_path):
 src=code("return 0;");m=metadata(tmp_path,src,"0.4.24")
 with pytest.raises(Unsupported,match="contradicts"):analyze_source(src,metadata=m)
@pytest.mark.parametrize("expr",["^0.4.0 || ^0.5.0",">=0.5.17 <0.5.0"])
def test_bad_intersection_fails(expr):
 with pytest.raises(Unsupported):analyze_source(code("return 0;",pragma=expr))
def test_no_inheritance_old_facts_and_ast_mapping_preserved():
 src=code("s=1;if(c){s=2;}return s;",params="bool c")
 a,br=old(src);b,ar=analyze_source(src)
 assert facts(br[0])==facts(ar[0]);assert a.mapping==b.mapping and a.compat_ids==b.compat_ids
def test_loop_kill_remains_and_later_write_not_earlier_read():
 _,r=result(code("s=1;while(s>0){s--;}return s;"));assert len(r.facts)==6
 _,r=result(code("uint a=s;s=1;return a;"));assert not r.facts

def test_nonbuiltin_revert_statement_is_opaque_effect_not_silent_pure():
 src="pragma solidity 0.4.24;contract A{uint s;function revert() internal{s=2;}function f() public returns(uint){s=1;revert();return s;}}"
 v,r=result(src)
 assert r.status=="supported_subset"
 assert any(d["classification"]==NON_BUILTIN for d in r.binding_evidence["calls"])
 assert not r.facts
 assert any(e.kind=="HAVOC" for es in r.ir.events.values() for e in es)
 assert any(u["origin"].startswith("HAVOC") for u in r.unknown_reads)
