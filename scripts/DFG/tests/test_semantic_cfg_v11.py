"""D1 comment/if repair regressions.

Real-source fixtures are parser/semantic tests; no local solc compilation has
been performed. Malformed AST proxies are explicitly parser-robustness tests,
not claims that Solidity permits their shapes.
"""
import pytest
import numpy as np
from scripts.DFG.frontend import parse_source, walk, text
from scripts.DFG.semantic_cfg import analyze, CFGBuilder
from scripts.DFG.models import Unsupported, DDGConfig
from scripts.DFG.reaching_definitions import solve
from scripts.DFG.pipeline import augment
from scripts.DFG.configuration import prepare_graph
from scripts.DFG.graph_audit import fingerprint, assert_augmented, frozen
from scripts.DFG.tests.test_semantic_cfg import block_for, reach
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source


def source(body):
    return ('pragma solidity ^0.5.17; contract C {'
            'function f(uint a,bool p,bool q,address payable beneficiary) '
            'public returns(uint){uint x=a;' + body + '}}')


def analyzed(body):
    s = source(body)
    view = parse_source(s, 'if_comments.sol')
    result = analyze(view)
    assert len(result.functions) == 1, result.diagnostics
    assert not any(d['kind'] == 'function_fallback' for d in result.diagnostics)
    ir = result.functions[0]
    return view, ir, solve(ir)


def snippet(view, anchor):
    return view.raw[anchor.start:anchor.end].decode('utf8')


def return_definitions(view, rd):
    last = max(f.use.anchor.start for f in rd.facts
               if snippet(view, f.use.anchor) == 'return x;')
    return {snippet(view, f.definition.anchor) for f in rd.facts
            if f.use.anchor.start == last and snippet(view, f.use.anchor) == 'return x;'}


@pytest.mark.parametrize('conditional', [
    'if(p){x=1;}else{x=2;}',
    'if(p){x=1;}/* between branches */else{x=2;}',
    'if(p){x=1;}/* first\n second */else{x=2;}',
    'if(p){x=1;} // line comment\n else{x=2;}',
    'if(p)/*before then*/{x=1;}/*between*/else/*before else body*/{x=2;}',
    'if(p){/*then interior*/x=1;}else{/*else interior*/x=2;}',
    'if(p) x=1; else x=2;',
    'if(p) x=1; /*between unbraced*/ else x=2;',
])
def test_then_else_union_cfg_and_comment_invariance(conditional):
    view, ir, rd = analyzed(conditional + 'return x;')
    # Both branch definitions reach the join, and the pre-if definition is killed.
    assert return_definitions(view, rd) == {'x=1;', 'x=2;'}
    head = block_for(view, ir, conditional)
    then = block_for(view, ir, 'x=1;')
    other = block_for(view, ir, 'x=2;')
    join = block_for(view, ir, 'return x;')
    assert ir.blocks[head].successors == {then, other}
    assert ir.blocks[then].successors == {join}
    assert ir.blocks[other].successors == {join}
    assert then not in reach(ir, other) and other not in reach(ir, then)
    assert len(rd.facts) == 4  # a->x init, p->if, two x writes->return.


@pytest.mark.parametrize('conditional', [
    'if(p){x=1;}', 'if(p)/*before*/{x=1;}',
    'if(p){/*inside*/x=1;}', 'if(p) x=1;',
])
def test_no_else_keeps_false_path_and_initial_definition(conditional):
    view, ir, rd = analyzed(conditional + '/*after no else*/return x;')
    assert return_definitions(view, rd) == {'uint x=a;', 'x=1;'}
    assert ir.blocks[block_for(view, ir, conditional)].successors == {
        block_for(view, ir, 'x=1;'), block_for(view, ir, 'return x;')}


@pytest.mark.parametrize('conditional,expected', [
    ('if(p){if(q){x=1;}/*inner*/else{x=2;}}/*outer*/else{x=3;}',
     {'x=1;', 'x=2;', 'x=3;'}),
    ('if(p) if(q)x=1;/*nearest*/else x=2;',
     {'uint x=a;', 'x=1;', 'x=2;'}),
    ('if(p){if(q)x=1;}/*outer*/else x=2;',
     {'uint x=a;', 'x=1;', 'x=2;'}),
])
def test_nested_and_dangling_else_bind_to_ast_not_text(conditional, expected):
    view, ir, rd = analyzed(conditional + 'return x;')
    assert return_definitions(view, rd) == expected
    assert sum(1 for n in walk(view.tree.root_node) if n.type == 'if_statement') == 2


def test_join_then_redefinition_kills_both_branch_definitions():
    view, ir, rd = analyzed('if(p){x=1;}/*between*/else{x=2;}x=3;return x;')
    assert return_definitions(view, rd) == {'x=3;'}
    final_write = block_for(view, ir, 'x=3;')
    assert ir.blocks[block_for(view, ir, 'x=1;')].successors == {final_write}
    assert ir.blocks[block_for(view, ir, 'x=2;')].successors == {final_write}


def test_real_builtin_termination_retains_reads_not_unreachable_defs():
    view, ir, rd = analyzed(
        'if(p){selfdestruct(beneficiary);x=99;}/*between*/else{x=2;}return x;')
    terminator = block_for(view, ir, 'selfdestruct(beneficiary);')
    dead = block_for(view, ir, 'x=99;')
    assert ir.blocks[terminator].successors == set()
    assert dead not in rd.reachable
    assert return_definitions(view, rd) == {'x=2;'}
    assert any(ir.symbols[f.symbol].name == 'beneficiary'
               and snippet(view, f.use.anchor) == 'selfdestruct(beneficiary);'
               for f in rd.facts)
    assert not any(snippet(view, f.definition.anchor) == 'x=99;' for f in rd.facts)


def test_branch_return_is_not_connected_to_join():
    view, ir, rd = analyzed('if(p){return x;}/*between*/else{x=2;}return x;')
    returns = [k for k, b in ir.blocks.items() if any(e.kind == 'return' for e in b.events)]
    assert len(returns) == 2
    assert all(not ir.blocks[k].successors for k in returns)
    assert return_definitions(view, rd) == {'x=2;'}


class MalformedIf:
    """Only for robust rejection; wraps a real parsed if but corrupts child shape."""
    def __init__(self, original, kind):
        self.original = original
        self.children = list(original.children)
        self.fields = [original.field_name_for_child(i) for i in range(len(self.children))]
        bodies = [i for i, f in enumerate(self.fields) if f == 'body']
        otherwise = next(i for i, c in enumerate(self.children) if c.type == 'else')
        if kind == 'extra_body':
            self.children.append(self.children[bodies[-1]])
            self.fields.append('body')
        elif kind == 'missing_else_body':
            del self.children[bodies[-1]]; del self.fields[bodies[-1]]
        elif kind == 'two_bodies_without_else':
            del self.children[otherwise]; del self.fields[otherwise]
        elif kind == 'bodies_before_else':
            c, f = self.children.pop(bodies[-1]), self.fields.pop(bodies[-1])
            self.children.insert(otherwise, c); self.fields.insert(otherwise, f)
        elif kind == 'duplicate_else':
            self.children.append(self.children[otherwise]); self.fields.append('else')
        elif kind == 'unknown_named_child':
            self.children.append(self.children[bodies[-1]]); self.fields.append(None)
    def __getattr__(self, name):
        return getattr(self.original, name)
    def field_name_for_child(self, i):
        return self.fields[i]


@pytest.mark.parametrize('kind', ['extra_body', 'missing_else_body',
    'two_bodies_without_else', 'bodies_before_else', 'duplicate_else', 'unknown_named_child'])
def test_ambiguous_ast_shape_is_rejected_not_silently_flattened(kind):
    # Parser-only robustness: never silently truncate a third body.
    view = parse_source(source('if(p){x=1;}else{x=2;}return x;'), 'if_comments.sol')
    builder = CFGBuilder(view, view.functions[0])
    node = next(n for n in walk(view.tree.root_node) if n.type == 'if_statement')
    with pytest.raises(Unsupported, match='[Ii]f'):
        builder.statement(MalformedIf(node, kind), {builder.new()})


def test_augmented_hcg_keeps_ids_labels_features_and_all_base_edges():
    s = source('if(p){x=1;}/*between*/else{x=2;}return x;')
    g = generate_cfg_from_source(s, 'if_comments.sol')
    for n, data in g.nodes(data=True):
        data['token'] = np.arange(512, dtype=np.float32) + n
        data['node_info_vulnerabilities'] = [{'lines': [19]}] if n % 2 else None
    u, v = next(iter(g.edges()))
    g.add_edge(u, v, key='original_parallel', edge_type='next')
    before = fingerprint(g)
    enhanced, audit = augment(g, {'if_comments.sol': s})
    assert fingerprint(g) == before
    assert_augmented(g, enhanced)
    assert frozen(list(g.nodes(data=True))) == frozen(list(enhanced.nodes(data=True)))
    assert not any(d['kind'] == 'function_fallback'
                   for d in audit['files']['if_comments.sol']['diagnostics'])
    pairs = {(enhanced.nodes[u]['code'], enhanced.nodes[v]['code'])
             for u, v, d in enhanced.edges(data=True) if d['edge_type'] == 'DATA_DEF_USE'}
    assert {('x=1;', 'return x;'), ('x=2;', 'return x;')} <= pairs
    assert ('uint x=a;', 'return x;') not in pairs
    baseline, _ = prepare_graph(g, config=DDGConfig(use_ddg=False))
    assert fingerprint(baseline) == before
