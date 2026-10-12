import pytest
from scripts.DFG.frontend import parse_source, span, walk
from scripts.DFG.models import Unsupported

@pytest.mark.parametrize("pragma,expected", [
    ("^0.4.25","legacy"), (">=0.4.24 <0.5.0","legacy"),
    ("^0.5.17","modern"), ("0.8.19","modern"),
])
def test_versions(pragma, expected):
    assert parse_source("pragma solidity "+pragma+"; contract C {}").mode == expected

def test_ambiguous_versions_and_missing():
    for p in ("", "pragma solidity >=0.4.25 <0.9.0;"):
        with pytest.raises(Unsupported): parse_source(p+" contract C {}")

def test_utf8_crlf_comments_and_exact_anchors():
    s='pragma solidity ^0.5.17;\r\n// comment\r\ncontract C {\r\nfunction f(uint x) public returns(uint) {\r\n/* unicode: \u4e2d */ uint y=x; y=x+1; return y;\r\n}}\r\n'
    v=parse_source(s)
    statements=[n for n in walk(v.tree.root_node)
                if n.type=="expression_statement"]
    assert len(statements)==1
    k=v.compat_key(span(v.file,statements[0]))
    assert v.compat[k[0]:k[1]]==b"y=x+1;"
    assert v.compat_ids[k] >= 5

def test_experimental_scope():
    assert parse_source('pragma solidity ^0.4.25; pragma experimental "v0.5.0"; contract C {}').mode == "modern"

def test_literal_guard_rejects_changed_string(monkeypatch):
    from process_graphs.tree_sitter_codeviews.utils import preprocessor
    original = preprocessor.remove_comments
    monkeypatch.setattr(preprocessor, "remove_comments",
                        lambda lang, src: original(lang, src).replace('"OK"', '"NO"'))
    with pytest.raises(Unsupported, match="executable tokens"):
        parse_source('pragma solidity ^0.5.17; contract C {function f(uint x) public {require(x>0,"OK");}}')

def test_multiple_conflicting_pragmas():
    with pytest.raises(Unsupported):
        parse_source('pragma solidity ^0.4.25; pragma solidity ^0.5.17; pragma experimental "v0.5.0"; contract C {}')
