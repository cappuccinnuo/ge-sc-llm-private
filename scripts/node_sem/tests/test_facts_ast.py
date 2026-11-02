"""Real parser oracles; compilation was not performed by these unit tests."""
import unittest
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.node_sem.facts_ast import AstSemantics, key, shape
from scripts.node_sem.facts_schema import new_facts, validate


def analyze(body, members="", params="uint p, address payable a", version="^0.5.0"):
    source="pragma solidity "+version+"; contract C { "+members+" function f("+params+") public { "+body+" } }"
    return AstSemantics(ProjectionView(source,"oracle.sol"))


def find(sem,text,kind="expression_statement"):
    rows=[n for n in sem.nodes if n.type==kind and sem.text(n)==text]
    assert len(rows)==1,(kind,text,len(rows))
    return rows[0]


class FactsAstTests(unittest.TestCase):
    def facts(self,sem,text,kind="expression_statement",node_kind="statement"):
        row=new_facts(node_kind)
        row.update(sem.base_facts(find(sem,text,kind),node_kind))
        validate(row)
        return row

    def test_invoked_value_chain_and_parameter(self):
        sem=analyze("msg.sender.call.value(p)();")
        f=self.facts(sem,"msg.sender.call.value(p)();")["external"]
        self.assertEqual(f["kinds"],["call"])
        self.assertTrue(f["value_attached"])
        self.assertEqual(f["target_classes"],["msg.sender"])
        self.assertEqual(f["value_class"],"param")
        self.assertEqual(f["return_handling"],"ignored")

    def test_uninvoked_builder_not_external(self):
        sem=analyze("a.call.value(1 ether); a.send(1);")
        f=self.facts(sem,"a.call.value(1 ether);")["external"]
        self.assertEqual(f["kinds"],[])
        self.assertTrue(f["uninvoked_call_value"])
        self.assertEqual(f["return_handling"],"not_applicable")
        self.assertEqual(self.facts(sem,"a.send(1);")["external"]["kinds"],["send"])

    def test_brace_value_same_behavior_as_legacy(self):
        old=analyze("a.call.value(p)();")
        new=analyze("a.call{value:p}();")
        self.assertEqual(self.facts(old,"a.call.value(p)();"),self.facts(new,"a.call{value:p}();"))

    def test_negated_send_parser_shape(self):
        sem=analyze("if (!a.send(p)) revert();")
        row=self.facts(sem,"if (!a.send(p)) revert();","if_statement","condition")
        self.assertEqual(row["external"]["return_handling"],"checked_in_if")
        self.assertEqual(row["external"]["kinds"],["send"])
        self.assertNotIn("exit",row["syntax"])

    def test_check_in_require(self):
        sem=analyze("require(a.send(p));")
        row=self.facts(sem,"require(a.send(p));",node_kind="condition")
        self.assertEqual(row["external"]["return_handling"],"checked_in_require")

    def test_tuple_assigned_not_checked(self):
        sem=analyze('(bool ok,) = a.call("");')
        row=self.facts(sem,'(bool ok,) = a.call("");',"variable_declaration_statement")
        self.assertEqual(row["external"]["return_handling"],"assigned_unchecked")

    def test_result_binding_checked_and_killed(self):
        for tail,expected in (("require(ok);","assigned_checked"),("ok=false; require(ok);","assigned_unchecked")):
            sem=analyze('(bool ok,) = a.call(""); '+tail)
            row=self.facts(sem,'(bool ok,) = a.call("");',"variable_declaration_statement")
            self.assertEqual(row["external"]["return_handling"],expected)

    def test_result_shadow_is_not_original_result(self):
        sem=analyze('(bool ok,) = a.call(""); { bool ok=true; require(ok); }')
        row=self.facts(sem,'(bool ok,) = a.call("");',"variable_declaration_statement")
        self.assertEqual(row["external"]["return_handling"],"assigned_unchecked")

    def test_small_integer_and_param_arithmetic(self):
        sem=analyze("uint8 v=0; v=v+p;")
        row=self.facts(sem,"v=v+p;")
        self.assertEqual(row["arith"]["ops"],["+"])
        self.assertTrue(row["arith"]["small_int"])
        self.assertTrue(row["arith"]["from_param"])
        self.assertEqual(row["arith"]["sinks"],["local"])

    def test_state_compound_and_unchecked_block(self):
        sem=analyze("unchecked { balances[msg.sender]-=p; }","mapping(address=>uint) balances;",version="^0.8.0")
        row=self.facts(sem,"balances[msg.sender]-=p;")
        self.assertEqual(row["arith"]["ops"],["-"])
        self.assertTrue(row["arith"]["on_state"])
        self.assertTrue(row["arith"]["in_unchecked"])
        self.assertIn("sub_assign",row["syntax"])

    def test_loop_transfer_state_bound(self):
        sem=analyze("for(uint i=0;i<users.length;i++) users[i].transfer(1);","address payable[] users;")
        row=self.facts(sem,"users[i].transfer(1);")
        self.assertEqual(row["loop"]["bound"],"state")
        self.assertEqual(row["external"]["kinds"],["transfer"])

    def test_constant_loop_bound(self):
        sem=analyze("for(uint i=0;i<3;i++) a.send(1);")
        self.assertEqual(self.facts(sem,"a.send(1);")["loop"]["bound"],"constant")

    def test_state_array_mutation_type_checked(self):
        sem=analyze("list.push(p); list.length=0; delete list;","uint[] list;")
        for text in ("list.push(p);","list.length=0;","delete list;"):
            node=find(sem,text)
            self.assertTrue(sem.array_size_change(node))
            self.assertEqual(sem.base_facts(node)["external"]["kinds"],[])

    def test_contract_push_not_array_mutation(self):
        source='pragma solidity ^0.5.0; contract X { function push(uint x) public {} } contract C { X target; function f() public { target.push(1); } }'
        sem=AstSemantics(ProjectionView(source,"oracle.sol"))
        node=find(sem,"target.push(1);")
        self.assertFalse(sem.array_size_change(node))
        self.assertEqual(sem.base_facts(node)["external"]["kinds"],["member"])

    def test_library_function_not_external(self):
        source='pragma solidity ^0.5.0; library L { function add(uint x) internal pure returns(uint) { return x+1; } } contract C { function f(uint p) public { L.add(p); } }'
        sem=AstSemantics(ProjectionView(source,"oracle.sol"))
        node=find(sem,"L.add(p);")
        self.assertEqual(sem.base_facts(node)["external"]["kinds"],[])
        call=node.named_children[0]
        self.assertEqual(sem.resolve_callable(call).type,"function_definition")

    def test_legacy_and_case_only_constructors(self):
        source='pragma solidity ^0.4.24; contract Wallet { function Wallet() public {} function wallet() public {} }'
        sem=AstSemantics(ProjectionView(source,"oracle.sol"))
        contexts=[sem.function_context(n) for n in sem.functions]
        self.assertTrue(contexts[0]["is_constructor"])
        self.assertFalse(contexts[0]["name_case_only_differs_from_contract"])
        self.assertFalse(contexts[1]["is_constructor"])
        self.assertTrue(contexts[1]["name_case_only_differs_from_contract"])

    def test_delegate_and_fallback(self):
        source='pragma solidity ^0.5.0; contract C { address target; function() external payable { target.delegatecall(msg.data); } }'
        sem=AstSemantics(ProjectionView(source,"oracle.sol"))
        row=self.facts(sem,"target.delegatecall(msg.data);")
        self.assertEqual(row["external"]["kinds"],["delegatecall"])
        self.assertEqual(row["external"]["data_class"],"msg.data")
        self.assertEqual(row["external"]["target_classes"],["state"])
        self.assertTrue(row["function_ctx"]["is_fallback"])

    def test_env_hash_and_arithmetic(self):
        sem=analyze("uint r=uint(keccak256(abi.encodePacked(block.timestamp)))%2;")
        row=self.facts(sem,"uint r=uint(keccak256(abi.encodePacked(block.timestamp)))%2;","variable_declaration_statement")
        self.assertIn("block.timestamp",row["env"]["keys"])
        self.assertIn("hash",row["env"]["uses"])
        self.assertIn("%",row["arith"]["ops"])
        self.assertIn("abi_encode",row["syntax"])

    def test_condition_does_not_take_body_arithmetic(self):
        sem=analyze("if(p>0) { x=x+msg.value; }","uint x;")
        row=self.facts(sem,"if(p>0) { x=x+msg.value; }","if_statement","condition")
        self.assertEqual(row["arith"]["ops"],[])
        self.assertEqual(row["env"]["keys"],[])
        self.assertNotIn("state",sem.operand_classes(find(sem,"if(p>0) { x=x+msg.value; }","if_statement")))

    def test_builtin_shadowing(self):
        sem=analyze("selfdestruct(a);","function selfdestruct(address x) internal {}")
        self.assertEqual(self.facts(sem,"selfdestruct(a);")["external"]["kinds"],[])

    def test_normalized_exit_and_hash(self):
        old=analyze('sha3("x"); throw;',version="^0.4.24",params="")
        new=analyze('keccak256("x"); revert();',params="")
        self.assertEqual(old.syntax(find(old,'sha3("x");')),new.syntax(find(new,'keccak256("x");')))
        self.assertEqual(old.syntax(find(old,"throw;","expression_statement")),new.syntax(find(new,"revert();","revert_statement")))

    def test_shapes(self):
        expected={"mapping(address=>uint)":"mapping","address[]":"array","uint128":"integer","address payable":"address","bool":"bool","bytes32":"bytes_string","C":"struct_contract"}
        for name,value in expected.items():self.assertEqual(shape(name),value)

    def test_shadowing_identity(self):
        sem=analyze("uint x=1; { uint x=2; x=x+1; } x=x+2;")
        inner=find(sem,"x=x+1;")
        outer=find(sem,"x=x+2;")
        self.assertNotEqual(key(sem.resolve_identifier(next(sem.identifiers(inner)))["declaration"]),key(sem.resolve_identifier(next(sem.identifiers(outer)))["declaration"]))

    def test_bodyless_function_enumerated(self):
        source='pragma solidity ^0.5.0; interface I { function f(uint x) external; }'
        sem=AstSemantics(ProjectionView(source,"oracle.sol"))
        self.assertEqual(len(sem.functions),1)
        self.assertEqual(sem.base_facts(sem.functions[0],"function")["function_ctx"]["visibility"],"external")

    def test_unknown_amount_not_none(self):
        sem=analyze("a.transfer(getAmount());", "function getAmount() internal returns(uint) { return 1; }")
        row=self.facts(sem,"a.transfer(getAmount());")
        self.assertEqual(row["external"]["value_class"],"unknown")
        self.assertTrue(row["external"]["value_attached"])
        self.assertEqual(row["unresolved"]["call_value_class_unknown"],1)

    def test_mixed_return_outcomes_unknown(self):
        sem=analyze("a.call(abi.encode(require(a.send(p))));")
        row=self.facts(sem,"a.call(abi.encode(require(a.send(p))));")
        self.assertEqual(row["external"]["return_handling"],"unknown")
        self.assertEqual(row["unresolved"]["mixed_call_return_handling"],1)

    def test_legacy_constant_not_modifier(self):
        source='pragma solidity ^0.4.24; contract C { function f() public constant returns(uint) { return 1; }}'
        sem=AstSemantics(ProjectionView(source,"oracle.sol"))
        context=sem.function_context(sem.functions[0])
        self.assertTrue(context["read_only"])
        self.assertFalse(context["has_modifier"])

    def test_constructor_payable_unnamed_ast_token(self):
        source='pragma solidity ^0.8.0; contract C { constructor() payable {} }'
        sem=AstSemantics(ProjectionView(source,"oracle.sol"))
        self.assertTrue(sem.function_context(sem.functions[0])["payable"])

    def test_equality_hash_postfix_shape(self):
        sem=analyze("require(h==sha3(p));", "bytes32 h;", version="^0.4.24")
        row=self.facts(sem,"require(h==sha3(p));",node_kind="condition")
        self.assertIn("hash",row["syntax"])

    def test_explicit_computed_callee_not_reinterpreted(self):
        sem=analyze("(p+sha3)(p);")
        row=self.facts(sem,"(p+sha3)(p);")
        self.assertNotIn("hash",row["syntax"])

    def test_function_pointer_shadows_internal_callable(self):
        source='pragma solidity ^0.5.0; contract C { function check() internal {} function f(function() internal check) public { check(); } }'
        sem=AstSemantics(ProjectionView(source,"oracle.sol"))
        call=find(sem,"check();").named_children[0]
        self.assertIsNone(sem.resolve_callable(call))

    def test_sink_uses_exact_declaration_not_spelling(self):
        from types import SimpleNamespace
        sem=analyze("uint x=1; { uint x=2; a.transfer(x); }")
        declarations=[n for n in sem.nodes if n.type=="variable_declaration" and sem.text(n.child_by_field_name("name"))=="x"]
        outer=declarations[0]
        symbol=SimpleNamespace(name="x",declaration=SimpleNamespace(start=outer.start_byte,end=outer.end_byte))
        node=find(sem,"a.transfer(x);")
        self.assertEqual(sem.sink(node,symbol),"other")
        inner=declarations[1]
        symbol.declaration=SimpleNamespace(start=inner.start_byte,end=inner.end_byte)
        self.assertEqual(sem.sink(node,symbol),"call_value")

    def test_condition_overwrite_not_a_result_check(self):
        sem=analyze('(bool ok,) = a.call(""); require(ok=true);')
        row=self.facts(sem,'(bool ok,) = a.call("");',"variable_declaration_statement")
        self.assertEqual(row["external"]["return_handling"],"assigned_unchecked")

    def test_address_this_target(self):
        sem=analyze('address(this).call("");')
        row=self.facts(sem,'address(this).call("");')
        self.assertEqual(row["external"]["target_classes"],["this"])

    def test_constant_address_target(self):
        sem=analyze('DEST.transfer(1);','address payable constant DEST=address(0);')
        row=self.facts(sem,'DEST.transfer(1);')
        self.assertEqual(row["external"]["target_classes"],["literal"])

    def test_forwarded_result_not_ignored(self):
        sem=analyze('return a.send(p);')
        row=self.facts(sem,'return a.send(p);','return_statement')
        self.assertEqual(row["external"]["return_handling"],"unknown")
        self.assertEqual(row["unresolved"]["call_return_context_unknown"],1)

    def test_result_passed_to_other_call_not_assigned(self):
        sem=analyze('bool x=consume(a.send(p));','function consume(bool v) internal returns(bool) { return v; }')
        row=self.facts(sem,'bool x=consume(a.send(p));','variable_declaration_statement')
        self.assertEqual(row["external"]["return_handling"],"unknown")

    def test_using_library_extension_not_external(self):
        source='pragma solidity ^0.5.0; library L { function add(uint x,uint y) internal pure returns(uint) { return x+y; } } contract C { using L for uint; function f(uint x,uint y) public { uint z=x.add(y); } }'
        sem=AstSemantics(ProjectionView(source,"oracle.sol"))
        row=self.facts(sem,"uint z=x.add(y);","variable_declaration_statement")
        self.assertEqual(row["external"]["kinds"],[])
        call=next(n for n in sem.nodes if n.type=="call_expression")
        self.assertEqual(sem.text(sem.resolve_callable(call).child_by_field_name("name")),"add")

    def test_using_library_type_mismatch_not_resolved(self):
        source='pragma solidity ^0.5.0; library L { function add(uint x,uint y) internal pure returns(uint) { return x+y; } } contract C { using L for uint; function f(address x,uint y) public { x.add(y); } }'
        sem=AstSemantics(ProjectionView(source,"oracle.sol"))
        call=next(n for n in sem.nodes if n.type=="call_expression")
        self.assertIsNone(sem.resolve_callable(call))


if __name__=="__main__":unittest.main()
