"""CP2.3: byte-level pragma location, frozen semantics and real CLI inputs."""
import hashlib
import json
import re
from pathlib import Path

import pytest

from compile_repair.cli import main
from compile_repair.core.provenance import apply_patches, verify_provenance
from compile_repair.core.store import read_checked_json
from compile_repair.rules.environment import infer_interval, make_plan, pragma_interval, pragma_patches
from compile_repair.tests.test_production import production_required
from compile_repair.toolchain.solc import CP0_SHA256
from scripts.DFG.frontend import parse
from scripts.DFG.models import Unsupported
from scripts.DFG.state.stage_f.versioning import interval as frozen_interval

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "compile_repair/tests/fixtures"
NEW = FIXTURES / "pragma_inputs"
FEATURES = ("f0813_using_global", "f0819_user_operator", "f0828_transient",
            "h0822_file_event", "h0829_layout_at")


def outcome(fn):
    try:
        return {"value": fn(), "exception_type": None}
    except Unsupported as exc:
        return {"value": None, "exception_type": type(exc).__name__}


def compare_frozen(path, root, text):
    raw = path.read_bytes()
    original = outcome(lambda: frozen_interval(text, root))
    actual = outcome(lambda: pragma_interval([raw]))
    assert actual == original, str(path)
    old_spans = tuple(reversed([(node.start_byte, node.end_byte) for node in root.named_children
        if node.type == "pragma_directive" and
        re.match(rb"pragma\s+solidity\b", raw[node.start_byte:node.end_byte])]))
    patches = pragma_patches(raw)
    spans = tuple((patch.start, patch.end) for patch in patches)
    assert spans == old_spans, str(path)
    assert all(p.expected == raw[p.start:p.end] and
               p.replacement == re.sub(rb"[^\r\n]", b" ", p.expected) for p in patches)
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(raw).hexdigest(),
            "interval": actual, "spans": spans, "interval_equal": True, "patches_equal": True}


def test_frozen_equivalence_all_846_sources(tmp_path):
    cp0 = read_checked_json(ROOT / "compile_repair/artifacts/cp0_v2/recon.json", CP0_SHA256)
    assert len(cp0["inputs"]) == 846
    records = []
    for row in cp0["inputs"]:
        path = ROOT / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        text = path.read_bytes().decode("utf8")
        records.append(compare_frozen(path, parse(text).root_node, text))
    (tmp_path / "equivalence.json").write_text(json.dumps({"compared": len(records), "records": records}, indent=2))


def test_frozen_equivalence_all_parseable_fixtures(tmp_path):
    records, excluded = [], []
    for path in sorted(FIXTURES.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf8")
            root = parse(text).root_node
        except (Unsupported, UnicodeDecodeError) as exc:
            excluded.append({"path": str(path.relative_to(ROOT)), "exception_type": type(exc).__name__,
                             "message": str(exc)})
            continue
        records.append(compare_frozen(path, root, text))
    assert records
    (tmp_path / "equivalence.json").write_text(json.dumps(
        {"compared": len(records), "records": records, "excluded": excluded}, indent=2))


@pytest.mark.parametrize("expression", [
    "^0.0.3", "^0.4.12", "^1.2.3", "~0.5.1", "=0.5.2", "0.5.2",
    ">=0.4.12 <=0.5.3", ">0.4.12 <0.5.0", "^0.4.0 || ^0.5.0",
    ">=0.5.0 <0.5.0", "*", "0.5", ">=0.5.0 nonsense",
])
def test_constraint_semantics_and_exception_type(expression):
    raw = ("pragma solidity " + expression + "; contract C {}").encode()
    # The reference expression evaluator needs only a pragma node; parser error
    # recovery must not determine whether the expression semantics are tested.
    class Directive:
        type = "pragma_directive"
        start_byte = 0
        end_byte = raw.index(b";") + 1
    class Root:
        named_children = [Directive()]
    assert outcome(lambda: pragma_interval([raw])) == outcome(
        lambda: frozen_interval(raw.decode(), Root()))


def test_masked_lookalikes_and_top_level_brace_depth():
    raw = (NEW / "masked_pragma.sol").read_bytes()
    assert pragma_interval([raw]) == ((0, 5, 0), (0, 6, 0))
    assert len(pragma_patches(raw)) == 1
    nested = (NEW / "nested_pragma.sol").read_bytes()
    assert pragma_interval([nested]) == ((0, 5, 0), (0, 6, 0))
    assert len(pragma_patches(nested)) == 1
    assert pragma_interval([b"contract C { pragma solidity ^0.4.0; }"]) is None
    assert pragma_patches(b"contract C { pragma solidity ^0.4.0; }") == ()
    for name in (b"xpragma", b"$pragma", b"pragma soliditySuffix"):
        assert pragma_interval([name + b" solidity ^0.4.0;"]) is None


def test_intersection_and_patch_bytes_preserve_offsets_and_non_utf8():
    raw = b"// caf\xe9\r\npragma solidity\r\n0.4.10; pragma solidity >=0.4.0;\r\ncontract C {}"
    assert pragma_interval([raw]) == ((0, 4, 10), (0, 4, 11))
    plan = make_plan([raw], ["0.4.12"])
    assert plan.override
    patches = pragma_patches(raw)
    assert [p.start for p in patches] == sorted([p.start for p in patches], reverse=True)
    copy, provenance = apply_patches(raw, patches)
    verify_provenance(raw, copy, provenance)
    assert len(copy) == len(raw) and copy[:raw.index(b"pragma")] == raw[:raw.index(b"pragma")]
    assert copy.index(b"contract") == raw.index(b"contract")
    assert [(i,b) for i,b in enumerate(copy) if b in (10,13)] == [(i,b) for i,b in enumerate(raw) if b in (10,13)]
    assert pragma_interval([copy]) is None
    with pytest.raises(Unsupported):
        pragma_interval([raw, b"pragma solidity ^0.5.0;"])


@pytest.mark.parametrize("raw", [
    b"pragma solidity ^0.5.0",
    b"pragma solidity ^0.5.0 contract C {}",
])
def test_unterminated_top_level_pragma_is_not_silently_ignored(raw):
    with pytest.raises(Unsupported):
        pragma_interval([raw])


def test_non_utf8_without_pragma_reaches_documented_inference():
    raw = b"contract C { function f() public { unchecked { uint x = 1; } } }\xff"
    inferred, evidence = infer_interval([raw])
    assert inferred == ((0,8,0), (0,9,0))
    assert [r["name"] for r in evidence] == ["unchecked_introduced"]
    assert make_plan([raw], ["0.8.0"]).origin == "no_pragma_inferred"


def test_real_byte_inputs_cli(tmp_path):
    production_required()
    paths = [FIXTURES / "features" / (name + ".sol") for name in FEATURES]
    paths += [NEW / name for name in ("latin1_comment.sol", "masked_pragma.sol", "two_pragmas.sol", "no_pragma_latin1.sol")]
    output = tmp_path / "success"
    rc = main(["repair"] + list(map(str, paths)) + ["--output", str(output)])
    assert rc == 0
    records = [json.loads(line) for line in (output / "manifest.jsonl").read_text().splitlines()]
    assert len(records) == 9
    for record, path in zip(records, paths):
        assert record["status"] == "success"
        assert record["attempts"][-1]["slither"]["profile"] == "production"
        assert record["attempts"][-1]["slither"]["d3"]
        assert record["attempts"][-1]["solc"]["returncode"] == 0
        assert record["flags"] in ([], ["no_pragma_guess"])
        assert record["provenance"][str(path)]["level"] == "none"
        assert (output / "units" / record["unit_id"] / "input.sol").read_bytes() == path.read_bytes()


def test_real_union_stays_unsupported_cli(tmp_path):
    production_required()
    output = tmp_path / "unsupported"
    assert main(["repair", str(NEW / "union_pragma.sol"), "--output", str(output)]) == 2
    record = json.loads((output / "units/input_0001/result.json").read_text())
    assert record["status"] == "unrepaired"
    assert record["flags"] == ["unsupported_version_constraints"]
    assert record["attempts"][0]["exception_type"] == "Unsupported"
    assert len(record["attempts"]) == 1
    assert (output / "invocations.jsonl").read_bytes() == b""
