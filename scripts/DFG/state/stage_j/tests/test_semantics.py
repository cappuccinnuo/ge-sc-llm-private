"""Parser/static-analysis fixtures, NOT claimed solc-compiled."""
import pytest
from scripts.DFG.models import Unsupported
from scripts.DFG.frontend import text
from scripts.DFG.state.stage_f.analyzer import analyze_source as old
from scripts.DFG.state.stage_j.analyzer import analyze_source
from scripts.DFG.state.stage_j.binding import ClosedScopeJ
from scripts.DFG.state.stage_f.frontend import StageFSourceView

def pick(src,name="f",**kwargs):
    v,rs,recs=analyze_source(src,**kwargs)
    names={v.file+":"+str(n.start_byte):text(v.source,n.child_by_field_name("name"))
           for n in v.functions if n.child_by_field_name("name") is not None}
    r=next(x for x in rs if names.get(x.function)==name)
    return v,r,next(x for x in recs if x["function"]==r.function)

def pair_text(v,r):
    return {(v.raw[f.definition.anchor.start:f.definition.anchor.end].decode(),
             v.raw[f.use.anchor.start:f.use.anchor.end].decode()) for f in r.facts}

def code(body,decl="uint s;",mods="",suffix=""):
    return "pragma solidity 0.5.17;contract C{"+decl+mods+"function f() public "+suffix+" returns(uint){"+body+"}}"

def test_unique_multiple_inherited_state_restored():
    src="pragma solidity 0.5.17;contract A{uint s;}contract B{uint t;}contract C is A,B{function f() public returns(uint){s=1;t=2;return s+t;}}"
    assert old(src)[1][0].ir is None
    v,r,rec=pick(src)
    assert rec["recovered"] and len(r.facts)==2
    assert [x["name"] for x in r.binding_evidence["scope"]["chain"]]==["C","B","A"]
    assert len({x.root.id for x in r.ir.locations.values()})==2

def test_diamond_common_state_deduplicated():
    src="pragma solidity 0.5.17;contract A{uint s;}contract B is A{}contract D is A{}contract C is B,D{function f() public returns(uint){s=1;return s;}}"
    _,r,rec=pick(src);assert rec["recovered"] and len(r.facts)==1
    assert [x["name"] for x in r.binding_evidence["scope"]["chain"]]==["C","D","B","A"]

def test_interface_without_body_can_be_ancestor():
    src="pragma solidity 0.5.17;interface I{function f() external returns(uint);}contract C is I{uint s;function f() public returns(uint){s=1;return s;}}"
    _,r,rec=pick(src);assert rec["recovered"] and len(r.facts)==1

@pytest.mark.parametrize("fragment",[
 "contract A is B{}contract B is A{}contract C is A",
 "contract A{}contract B is A{}contract C is B,A",
 "contract A{uint s;}contract B{uint s;}contract C is A,B",
 "contract A{}contract C is Missing",
 "contract A{}contract C is A,A",
 "library A{}contract C is A",
 "interface A{uint s;}contract C is A",
 "contract A{}contract C is A(1)",
])
def test_bad_or_ambiguous_hierarchy_leaves_no_partial_results(fragment):
    src="pragma solidity 0.5.17;"+fragment+"{function f() public returns(uint){s=1;return s;}}"
    _,r,rec=pick(src)
    assert r.ir is None and not r.facts and not rec["recovered"]

def test_import_still_fallback():
    _,r,_=pick('pragma solidity 0.5.17;import "x.sol";contract C{uint s;function f() public returns(uint){s=1;return s;}}')
    assert r.ir is None and not r.facts

def test_private_ancestor_not_promoted_to_visible_state():
    src="pragma solidity 0.5.17;contract A{uint private s;}contract B{}contract C is A,B{function f() public returns(uint){s=1;return s;}}"
    _,r,_=pick(src);assert r.ir is None and not r.facts

def test_later_inherited_revert_declaration_not_builtin_terminal():
    src="pragma solidity 0.4.24;contract A{uint s;}contract B{function revert() internal{}}contract C is A,B{function f() public returns(uint){s=1;revert();s=2;return s;}}"
    v,r,rec=pick(src)
    assert rec["recovered"] and ("s=2;","return s;") in pair_text(v,r)
    assert ("s=1;","return s;") not in pair_text(v,r)

def test_frozen_success_result_kept():
    src=code("s=1;return s;")
    v,r,rec=pick(src);ov,ors=old(src)
    assert not rec["recovered"] and rec["route"]=="frozen_stage_f_reused"
    assert pair_text(v,r)==pair_text(ov,ors[0])

def test_prefix_modifier_state_definition_reaches_body():
    src=code("return s;",mods="modifier init(){s=7;_;}",suffix="init")
    v,r,rec=pick(src);assert rec["recovered"]
    assert pair_text(v,r)=={("s=7;","return s;")}
    assert r.binding_evidence["modifier"]["execution"]=="prefix then function body; no suffix"

def test_guard_modifier_read_is_entry_unknown_not_fake_definition():
    src=code("return s;",mods="modifier guard(){require(s>0);_;}",suffix="guard")
    _,r,rec=pick(src)
    assert rec["recovered"] and not r.facts and r.unknown_reads

def test_function_local_does_not_shadow_modifier_state():
    src=code("uint s=2;return s;",mods="modifier init(){s=7;_;}",suffix="init")
    _,r,rec=pick(src)
    events=[e for es in r.ir.events.values() for e in es]
    assert rec["recovered"] and sum(e.kind=="WRITE" for e in events)==1 and not r.facts

def test_inherited_modifier_has_unique_source_binding():
    src="pragma solidity 0.5.17;contract A{uint s;modifier init(){s=3;_;}}contract B{}contract C is A,B{function f() public init returns(uint){return s;}}"
    v,r,rec=pick(src);assert rec["recovered"] and pair_text(v,r)=={("s=3;","return s;")}

@pytest.mark.parametrize("modifier,invocation",[
 ("modifier m(uint a){_;}","m(1)"),
 ("modifier m(){_;s=4;}","m"),
 ("modifier m(){_;_;}","m"),
 ("modifier m(){if(s>0){_;}}","m"),
 ("modifier m(){uint x=1;_;}","m"),
 ("modifier m(){g();_;}","m"),
 ("modifier m(){require(g());_;}","m"),
 ("modifier m(){require(s++>0);_;}","m"),
 ("modifier m(){_;} modifier n(){_;}","m n"),
 ("modifier m(){return;_;}","m"),
])
def test_modifier_unsupported_function_atomic_fallback(modifier,invocation):
    _,r,rec=pick(code("s=1;return s;",mods=modifier,suffix=invocation))
    assert r.ir is None and not r.facts and not rec["recovered"]
    assert rec["partial_facts_published"] is False

def test_fake_require_in_modifier_rejected():
    src=code("return s;",decl="uint s;function require(bool c) internal{}",mods="modifier m(){require(s>0);_;}",suffix="m")
    _,r,_=pick(src);assert r.ir is None and not r.facts

def test_modifier_mode_off_preserves_fallback():
    _,r,_=pick(code("return s;",mods="modifier m(){s=1;_;}",suffix="m"),enable_modifiers=False)
    assert r.ir is None and not r.facts

def test_return_termination_kept_after_prefix():
    src=code("return s;s=9;",mods="modifier m(){s=1;_;}",suffix="m")
    v,r,_=pick(src);assert pair_text(v,r)=={("s=1;","return s;")}
    writes=[e for bid,es in r.ir.events.items() if bid in r.reachable for e in es if e.kind=="WRITE"]
    assert len(writes)==1

def test_loop_fixpoint_and_kill_retained():
    src="pragma solidity 0.5.17;contract A{uint s;}contract B{}contract C is A,B{function f() public returns(uint){s=1;while(s>0){s--;}s=4;return s;}}"
    v,r,rec=pick(src);assert rec["recovered"]
    assert ("s=4;","return s;") in pair_text(v,r)
    assert ("s=1;","return s;") not in pair_text(v,r)

def test_legacy_constructor_is_not_counted_as_runtime_recovery():
    src="pragma solidity 0.4.24;contract A{uint s;}contract B{}contract C is A,B{function C() public{s=1;require(s>0);}function f() public returns(uint){return s;}}"
    _,r,rec=pick(src,"C")
    assert rec["recovered"] and not rec["runtime_function"]

def test_inheritance_declaration_order_does_not_change_state_binding():
    a="contract A{uint s;}contract B{}"
    c="contract C is A,B{function f() public returns(uint){s=1;return s;}}"
    for src in ["pragma solidity 0.5.17;"+a+c,"pragma solidity 0.5.17;"+c+a]:
        _,r,rec=pick(src);assert rec["recovered"] and len(r.facts)==1

def test_modifier_declaration_after_function_and_parameter_shadow():
    src="pragma solidity 0.5.17;contract C{uint s;function f(uint s) public m returns(uint){return s;}modifier m(){s=1;_;}}"
    _,r,rec=pick(src)
    assert rec["recovered"] and not r.facts
    assert sum(e.kind=="WRITE" for es in r.ir.events.values() for e in es)==1
