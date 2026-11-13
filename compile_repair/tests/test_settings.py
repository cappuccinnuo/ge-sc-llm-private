"""CP0.1 C continuation: settings whitelist, crash diagnostics and stable IR."""
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace as Item

import pytest

from compile_repair.core.model import Compilation, Compiler
from compile_repair.toolchain.solc import command, compile_file, error_first_line, validate_settings
from compile_repair.toolchain.slither import node_facts, run_slither

SOURCE = Path(__file__).parent / "fixtures/counter.sol"
COMPILER = Compiler("0.8.24", "/explicit/solc", "unused")


@pytest.mark.parametrize("settings", [(), ("--via-ir",), ("--evm-version", "cancun"),
    ("--via-ir", "--evm-version", "cancun"), ("--evm-version", "cancun", "--via-ir")])
def test_settings_keep_token_order_and_default_command(settings):
    default = command(SOURCE, COMPILER)
    assert command(SOURCE, COMPILER, settings=settings) == default + list(settings)
    assert validate_settings(list(settings)) == settings


@pytest.mark.parametrize("settings", ["--via-ir", None, (1,), ("--optimize",),
    ("--evm-version",), ("--evm-version", "--via-ir"),
    ("--evm-version", "cancun --optimize"), ("--evm-version", "cancun\n--via-ir"),
    ("--evm-version=cancun",), ("--via-ir", "true"), ("--via-ir", "--via-ir"),
    ("--evm-version", "cancun", "--evm-version", "paris"), ("--base-path", "/tmp")])
def test_rejected_settings_never_reach_source_or_process(settings):
    with pytest.raises(ValueError):
        compile_file("/nonexistent/input.sol", COMPILER, settings=settings)
    with pytest.raises(ValueError):
        command(SOURCE, COMPILER, settings=settings)


def test_compilation_default_and_regression_rejects_settings_before_execution():
    record = Compilation(str(SOURCE), "unused", COMPILER, [], "/tmp", 0, None, "", "", 0.0, False)
    assert record.settings == ()
    changed = Compilation(str(SOURCE), "unused", COMPILER, [], "/tmp", 0, None, "", "", 0.0, False,
                          settings=("--via-ir",))
    assert json.loads(json.dumps(asdict(changed)))["settings"] == ["--via-ir"]
    with pytest.raises(ValueError, match="regression_6c does not accept"):
        run_slither(changed, profile="regression_6c")


def test_reviewed_solc_error_texts_include_crash_what_message():
    # PROMPTS r2.5 1.8: meaningful lines from the actual 0.8.24/0.8.26 diagnostics.
    ordinary = ('Error: Undeclared identifier. Did you mean "blockhash"?\n'
                ' --> compile_repair/tests/fixtures/features/h0824_blob.sol:3:92:\n')
    assert error_first_line(ordinary) == ordinary.splitlines()[0]
    crash = ('Unimplemented feature:\n'
             'Dynamic exception type: boost::wrapexcept<solidity::langutil::UnimplementedFeatureError>\n'
             'std::exception::what: Require with a custom error is only available using the via-ir pipeline.\n')
    assert error_first_line(crash) == ("Unimplemented feature: " + crash.splitlines()[-1])
    assert error_first_line("Warning: banner\nError: ordinary") == "Error: ordinary"
    assert error_first_line("") is None


def facts_for(irs):
    node = Item(type="EXPRESSION", source_mapping={"filename_absolute": str(SOURCE.resolve()),
                                                 "start": 10, "length": 5}, irs=irs)
    function = Item(full_name="f()", nodes=[node])
    model = Item(contracts=[Item(name="C", functions_and_modifiers_declared=[function])],
                 compilation_units=[])
    return node_facts(model, [SOURCE])


class ObjectIR:
    def __init__(self, address):
        self.address = address

    def __str__(self):
        return "x(<module.Type object at 0x%s>) = <module.Other object at 0xAB12> + 0x1234" % self.address


def test_ir_object_repr_is_stable_and_counts_every_replacement():
    first, second = [facts_for([ObjectIR(address), "ordinary 0xfeed"]) for address in ("1abc", "2DEF")]
    assert first == second and first["mapping_complete"]
    assert first["counts"]["ir_object_repr_replacements"] == 2
    assert first["counts"]["ir_object_repr_unresolved"] == 0
    assert first["nodes"][0]["ir"] == ["x(<module.Type>) = <module.Other> + 0x1234", "ordinary 0xfeed"]
    assert first["ir_diagnostics"] == []


@pytest.mark.parametrize("text", ["<module.Type object at 0xnothex>", "<Type object at 0x1234>",
    "<module.Type object at 0x1234", "unrecognized object at 0xabc"])
def test_unrecognized_object_repr_fails_d3_a_with_location(text):
    result = facts_for([text])
    assert not result["mapping_complete"]
    assert result["counts"]["ir_object_repr_unresolved"] == 1
    assert result["ir_diagnostics"] == [{"key5": ["C", "f()", "EXPRESSION", 10, 1],
        "ir_index": 0, "reason": "Residual object address in IR", "ir": text}]
