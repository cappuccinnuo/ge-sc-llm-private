"""AST projection-only tests. Fixtures are parser tests, not solc validation."""
import hashlib
import inspect
from pathlib import Path

import pytest

from scripts.DFG.frontend import SourceView, span
from scripts.DFG.models import Unsupported
from scripts.DFG.dfg_v2.projection_view import ProjectionView


def mapping_snapshot(view):
    return {
        "mapping": view.mapping,
        "ids": view.compat_ids,
        "nodes": {key: (node.start_point, node.end_point, node.sexp())
                  for key, node in view.compat_nodes.items()},
        "raw": sorted(view.raw_nodes),
        "source": view.compat_source,
        "functions": [(n.start_byte, n.end_byte, n.type) for n in view.functions],
    }


@pytest.mark.parametrize("pragma", ["^0.4.24", "^0.5.17", ">=0.5.0 <0.9.0"])
def test_mapping_matches_original_view_in_supported_modes(pragma):
    source = """pragma solidity %s;
// retained AST identities despite changed coordinates

contract C { uint x=1;
 function f(uint y) public returns(uint) { if (x>y) return x; return y; }
}""" % pragma
    old = SourceView(source, "a.sol")
    new = ProjectionView(source, "a.sol")
    assert new.mode is None
    assert new.sha256 == old.sha256
    assert mapping_snapshot(new) == mapping_snapshot(old)
    for node in old.functions:
        assert new.compat_key(span("a.sol", node)) == old.compat_key(span("a.sol", node))


@pytest.mark.parametrize("prefix", [
    "", "pragma solidity >=0.4.0 <0.9.0;",
    "pragma solidity >=0.5.0; pragma solidity <0.9.0;",
])
def test_only_lexical_scope_gate_is_removed(prefix):
    source = prefix + " contract C { uint x; function f() public { x=1; } }"
    with pytest.raises(Unsupported):
        SourceView(source, "a.sol")
    view = ProjectionView(source, "a.sol")
    assert view.mode is None
    assert view.mapping and view.functions


def test_projection_does_not_invent_mode_from_override():
    view = ProjectionView("contract C { uint x; }", "a.sol", mode="legacy")
    assert view.mode is None


def test_changed_executable_tokens_still_rejected(monkeypatch):
    from process_graphs.tree_sitter_codeviews.utils import preprocessor
    original = preprocessor.remove_comments
    monkeypatch.setattr(preprocessor, "remove_comments",
        lambda lang, source: original(lang, source).replace("x=1", "x=2"))
    with pytest.raises(Unsupported, match="Preprocessing changed executable tokens"):
        ProjectionView("contract C { uint x=1; }", "a.sol")


def test_parser_error_still_rejected():
    with pytest.raises(Unsupported, match="parser ERROR/MISSING"):
        ProjectionView("contract C { function f( {", "a.sol")


def test_constructor_has_one_documented_change_and_frozen_provenance():
    root = Path(__file__).resolve().parents[4]
    original_path = root / "scripts/DFG/frontend.py"
    copied_path = root / "scripts/DFG/dfg_v2/projection_view.py"
    expected = hashlib.sha256(original_path.read_bytes()).hexdigest()
    assert expected in copied_path.read_text()
    old = inspect.getsource(SourceView.__init__)
    new = inspect.getsource(ProjectionView.__init__)
    new = new.replace(
        "self.mode = None  # L2/L3 projection has no lexical-scope semantics.",
        "self.mode = scope_mode(source, self.tree.root_node, mode)")
    assert new == old
    assert ProjectionView.compat_key is SourceView.compat_key
