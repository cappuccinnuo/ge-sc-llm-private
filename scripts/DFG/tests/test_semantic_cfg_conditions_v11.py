"""Supplemental D1 condition-extra tests; parser-tested, NOT solc-verified."""
import pytest
from scripts.DFG.frontend import walk, text
from scripts.DFG.tests.test_semantic_cfg_v11 import analyzed, return_definitions, snippet
from scripts.DFG.tests.test_semantic_cfg import block_for


@pytest.mark.parametrize('conditional,expected_reads', [
    ('if(/*before*/p){x=1;}else{x=2;}', {'p'}),
    ('if(p/*after*/){x=1;}else{x=2;}', {'p'}),
    ('if(/*before*/p/*after*/){x=1;}else{x=2;}', {'p'}),
    ('if/*a*/(/*b*/p/*c*/)/*d*/{x=1;}/*e*/else/*f*/{x=2;}', {'p'}),
    ('if(//before\np //after\n){x=1;}else{x=2;}', {'p'}),
    ('if((/*left*/p)&&(q/*right*/)){x=1;}else{x=2;}', {'p', 'q'}),
])
def test_condition_comments_preserve_read_events_and_parameter_def_use(conditional, expected_reads):
    view, ir, rd = analyzed(conditional + 'return x;')
    node = next(n for n in walk(view.tree.root_node) if n.type == 'if_statement')
    actual_condition = node.child_by_field_name('condition')
    assert 'comment' not in actual_condition.type
    assert text(view.source, actual_condition)
    head = block_for(view, ir, conditional)
    assert {ir.symbols[s].name for e in ir.blocks[head].events for s in e.reads} == expected_reads
    facts = [f for f in rd.facts if snippet(view, f.use.anchor) == conditional]
    assert {ir.symbols[f.symbol].name for f in facts} == expected_reads
    assert all(f.definition.anchor.role == 'function_definition' for f in facts)
    assert return_definitions(view, rd) == {'x=1;', 'x=2;'}
