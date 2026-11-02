"""Original-only and source/evidence boundary regression checks."""
import ast
from pathlib import Path
import pytest
from scripts.node_sem.facts import extract, extract_source, statistics


def test_current_policy_rejects_anonymous_before_loading_any_input():
    with pytest.raises(ValueError, match="only original"):
        extract("fictional_node", "anonymous")


def test_production_has_no_dataset_class_dispatch_or_target_field_reads():
    root = Path(__file__).resolve().parents[1]
    forbidden = {"reentrancy", "access_control", "arithmetic", "denial_of_service",
                 "front_running", "time_manipulation", "unchecked_low_level_calls"}
    targets = {"node_info_vulnerabilities", "type_label", "method", "label"}
    for name in ("facts.py", "facts_schema.py", "facts_ast.py", "facts_guards.py", "facts_cfg.py", "facts_io.py"):
        tree = ast.parse((root/name).read_text(encoding="utf8"))
        strings = [n.s for n in ast.walk(tree) if isinstance(n,ast.Str)]
        assert not forbidden.intersection(strings), name
        assert not targets.intersection(strings), name


def test_source_only_mode_never_claims_sealed_dataflow_or_order_support():
    rows,audit=extract_source("pragma solidity ^0.5.11; contract C { uint x; function f(uint y) public { x=y; } }")
    assert audit["view"] == "original"
    for row in rows.values():
        for group in ("dfg","order","state"):
            if row[group]:
                assert row[group]["status"] == "unknown"
    stats=statistics(rows)
    assert stats["unknown"]["order"]["count"] == stats["unknown"]["order"]["applicable"]


def test_no_absolute_source_coordinates_or_spelling_ids_in_features():
    rows,_=extract_source("pragma solidity ^0.5.11; contract C { function f(uint y) public { uint z=y+1; return; } }", "private_source.sol")
    def walk(value):
        if isinstance(value,dict):
            for k,v in value.items():
                assert k not in {"file","line","start","end","declaration","symbol_id"}
                if k!="provenance":
                    walk(v)
        elif isinstance(value,list):
            for item in value:walk(item)
        elif isinstance(value,str):
            assert "private_source.sol" not in value
    for row in rows.values():walk(row)
