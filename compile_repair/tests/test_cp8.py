"""CP8: first-stage agent with a scripted LLM (PROMPTS 3.5, D8, D10)."""
import hashlib
import io
import json
import re

import pytest

from compile_repair.agents.llm import Budget, BudgetExhausted, HttpClient, Pricing, ScriptedClient
from compile_repair.agents.patch import PatchRejected, candidate_patches, parse_blocks
from compile_repair.agents.prompt import anonymize_message, blank_comments, build_view, repair_prompt
from compile_repair.agents.stage1 import Stage1
from compile_repair.agents.stage2 import agents_from_config
from compile_repair.cli import main
from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.rag.knowledge import Entry, KnowledgeBase
from compile_repair.tests.test_production import production_required, trusted_compilers

MAIN = (b"pragma solidity ^0.5.0;\n"
        b"import \"./lib/Helper.sol\";\n"
        b"// secret note about MyVault\n"
        b"contract MyVault is Helper {\n"
        b"  function f(uint x) public pure returns (uint) {\n"
        b"    if (x) { return 1; } /* inline */\n"
        b"    return 0;\n"
        b"  }\n"
        b"}\n")
HELPER = b"pragma solidity ^0.5.0;\ncontract Helper {}\n"
CONTENTS = {"contracts/MyVault.sol": MAIN, "contracts/lib/Helper.sol": HELPER}
ERRORS = {"contracts/MyVault.sol": [dict(kind="TypeError", line=6, category="type_error_other",
          message="Type uint256 is not implicitly convertible to expected type bool.", versions=["0.5.17"])]}
FIX = ("@@ REPLACE F1 6-6\n    6|     if (x) { return 1; }\n@@ WITH\n    if (x != 0) { return 1; }\n@@ END\n")


def _view():
    return build_view(CONTENTS, "contracts/MyVault.sol")


# ---- D10: the model's view -----------------------------------------------------------------

def test_view_hides_file_names_and_comments():
    view = _view()
    prompt = repair_prompt(view, ERRORS, "0.5.17", 10)
    assert "MyVault.sol" not in prompt and "Helper.sol" not in prompt and "contracts/" not in prompt
    assert "secret note" not in prompt and "inline" not in prompt
    assert 'import "F2";' in prompt and "contract MyVault is Helper" in prompt  # identifiers stay
    # Same lines; only import strings change length (line 2), comments keep their length.
    real = MAIN.decode().split("\n")
    assert len(view.lines["F1"]) == len(real)
    assert [i for i, (a, b) in enumerate(zip(view.lines["F1"], real)) if len(a) != len(b)] == [1]
    assert len(blank_comments(MAIN)) == len(MAIN) and blank_comments(MAIN).count(b"\n") == MAIN.count(b"\n")


def test_messages_are_anonymized():
    view = _view()
    message = 'Source "contracts/lib/Helper.sol" not found: File not found. Searched /tmp/x/contracts/lib/Helper.sol'
    shown = anonymize_message(message, view)
    assert "Helper.sol" not in shown and "F2" in shown


# ---- patch format, original-text check and D7 ----------------------------------------------

def test_valid_patch_becomes_byte_patches_on_the_real_file():
    edits, patches, summary = candidate_patches(FIX, _view(), CONTENTS, {"F1": [6]}, set(CONTENTS), 3)
    out, provenance = apply_patches(MAIN, patches["contracts/MyVault.sol"])
    assert out == edits["contracts/MyVault.sol"]
    assert b"if (x != 0) { return 1; }" in out and b"/* inline */" not in out and b"secret note" in out
    assert provenance.level == "rewrite" and patches["contracts/MyVault.sol"][0].step == "stage1"


@pytest.mark.parametrize("text,reason", [
    (FIX.replace("if (x)", "if (y)", 1), "does not match"),
    (FIX.replace("6-6\n    6|", "7-7\n    7|").replace("if (x) { return 1; }", "return 0;", 1), "without an error"),
    (FIX.replace("!= 0)", "!= 0) // fixed"), "comment"),
    (FIX.replace("F1", "F9", 1), "unknown file"),
    ("no blocks here", "no patch block"),
    ("@@ REPLACE F1 6-6\n    6|     if (x) { return 1; }\n@@ END\n", "without WITH"),
    (FIX + "@@ INSERT F1 BEFORE 9\ncontract C {}\n", "not closed"),
    (FIX + FIX, "overlap"),
])
def test_bad_patches_are_rejected(text, reason):
    with pytest.raises(PatchRejected, match=reason):
        candidate_patches(text, _view(), CONTENTS, {"F1": [6]}, set(CONTENTS), 1)


def test_insertions_need_no_error_line_and_imports_map_back():
    text = ('@@ INSERT F1 BEFORE 4\nimport "F2";\n@@ END\n'
            "@@ INSERT F2 BEFORE 3\ncontract Extra {}\n@@ END\n")
    edits, _, _ = candidate_patches(text, _view(), CONTENTS, {}, set(CONTENTS), 1)
    assert b'import "./lib/Helper.sol";\ncontract MyVault' in edits["contracts/MyVault.sol"]
    assert edits["contracts/lib/Helper.sol"] == HELPER + b"contract Extra {}\n"
    with pytest.raises(PatchRejected, match="may not be edited"):
        candidate_patches(text, _view(), CONTENTS, {}, {"contracts/MyVault.sol"}, 1)


# ---- client: budget, cache, records, keys --------------------------------------------------

def test_budget_is_checked_before_sending_and_cache_is_free(tmp_path):
    client = ScriptedClient(lambda s, p, i: "x" * 400, budget=Budget(10, 10 ** 6, 1.0), pricing=Pricing(1000.0, 1000.0),
                            cache_dir=tmp_path, max_output_tokens=100)
    first = client.complete("sys", "prompt", 2, "t")
    assert not first.cached and first.cost_usd > 0 and client.budget.calls == 1
    again = client.complete("sys", "prompt", 2, "t")
    assert again.cached and again.cost_usd == 0 and again.texts == first.texts and client.budget.calls == 1
    tight = ScriptedClient(lambda s, p, i: "", budget=Budget(10, 10, 1.0))
    with pytest.raises(BudgetExhausted):
        tight.complete("sys", "a long prompt " * 50, 3, "t")
    assert tight.prompts == []  # nothing was sent


class _FakeHttp(HttpClient):
    def _post(self, body, headers):
        self.sent = (body, headers)
        return dict(content=[dict(type="text", text="ok")], usage=dict(input_tokens=10, output_tokens=2))


def test_http_client_reads_the_key_from_the_environment_only(tmp_path, monkeypatch):
    client = _FakeHttp("model-x", "anthropic", Budget(5, 10 ** 6, 1.0), Pricing(3.0, 15.0), "CR_TEST_KEY",
                       cache_dir=tmp_path)
    with pytest.raises(RuntimeError, match="CR_TEST_KEY"):
        client.complete("s", "p", 1, "t")
    monkeypatch.setenv("CR_TEST_KEY", "sk-secret-value")
    result = client.complete("s", "p", 1, "t")
    assert result.texts == ("ok",) and client.sent[1]["x-api-key"] == "sk-secret-value"
    stored = json.dumps(client.records) + "".join(p.read_text() for p in tmp_path.iterdir())
    assert "sk-secret" not in stored and client.records[-1]["cost_usd"] == pytest.approx((10 * 3 + 2 * 15) / 1e6)


# ---- stage 1 in the pipeline (production compilers) -----------------------------------------

def _unit(tmp_path, raw, name="A.sol"):
    path = tmp_path / name
    path.write_bytes(raw)
    return path, CompilationUnit("u", (SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw),))


BOOL = (b"pragma solidity ^0.5.0;\ncontract A {\n  // owner check\n  function f(uint x) public pure returns (uint) {\n"
        b"    if (x) { return 1; }\n    return 0;\n  }\n}\n")
GOOD = "@@ REPLACE F1 5-5\n    5|     if (x) { return 1; }\n@@ WITH\n    if (x != 0) { return 1; }\n@@ END\n"
WORSE = "@@ REPLACE F1 5-5\n    5|     if (x) { return 1; }\n@@ WITH\n    if (x != y) { return 1; }\n@@ END\n"
STALE = GOOD.replace("if (x) {", "if (z) {", 1)


def _run(tmp_path, raw, answers, **agent_options):
    production_required()
    path, unit = _unit(tmp_path, raw)
    client = ScriptedClient(lambda s, p, i: answers[min(i, len(answers) - 1)] if callable(answers) is False
                            else answers(s, p, i))
    agent = Stage1(client, **agent_options)
    store = ArtifactStore(tmp_path / "run")
    record = repair_unit(unit, {"0.5.17": trusted_compilers()["0.5.17"]}, store, io.StringIO(), agent=agent)
    assert path.read_bytes() == raw
    return record, agent, client, store


def test_stage1_repairs_what_the_rules_cannot(tmp_path):
    record, agent, client, store = _run(tmp_path, BOOL, [STALE, WORSE, GOOD])
    assert record.status == "success"
    steps = {c.step for p in record.provenance.values() for c in p.changes}
    assert steps == {"stage1"} and next(iter(record.provenance.values())).level == "rewrite"
    rounds = json.loads((store.path / "units/u/repair_steps.json").read_text())
    stage1 = [s for s in rounds if s["step"] == 11 and s.get("operation") == "agent_round"]
    assert stage1[0]["valid"] == 2 and stage1[0]["rejected"][0]["reason"].startswith("original line")
    trials = [s for s in rounds if s["step"] == 11 and "agent" in s]
    assert len(trials) == 2 and sum(s["accepted"] for s in trials) == 1
    calls = json.loads((store.path / "units/u/llm_calls.json").read_text())
    assert calls["calls"][0]["purpose"] == "stage1_repair" and calls["calls"][0]["n"] == 3
    prompt = client.prompts[0]
    assert "A.sol" not in prompt and "owner check" not in prompt and str(tmp_path) not in prompt


def test_rejected_candidates_feed_the_next_round_and_the_stage_stalls(tmp_path):
    record, agent, client, store = _run(tmp_path, BOOL, [STALE], candidates=1)
    assert record.status != "success" and agent.stopped == "stalled" and len(client.prompts) == 2
    assert "A previous candidate was rejected (original line F1:5 does not match the file)" in client.prompts[1]


def test_budget_exhaustion_ends_the_stage_without_a_call(tmp_path):
    production_required()
    path, unit = _unit(tmp_path, BOOL)
    client = ScriptedClient(lambda s, p, i: GOOD, budget=Budget(0, 10 ** 6, 1.0))
    agent = Stage1(client)
    record = repair_unit(unit, {"0.5.17": trusted_compilers()["0.5.17"]}, ArtifactStore(tmp_path / "run"),
                         io.StringIO(), agent=agent)
    assert record.status != "success" and agent.stopped == "budget_exhausted" and client.prompts == []


def test_language_check_precedes_repair_for_unknown_text(tmp_path):
    def answer(system, prompt, index):
        return "OTHER" if prompt.startswith("Is the following text Solidity") else GOOD
    record, agent, client, store = _run(tmp_path, b"Hello, this is a short note.\nNothing here compiles.\n", answer)
    assert agent.stopped == "language_check_not_solidity" and len(client.prompts) == 1


def test_k3_never_shows_the_units_own_project(tmp_path):
    own = Entry("K3", "K3:own", "own", "TypeError: Type uint256 is not implicitly convertible", ("category:type_error_other",),
                group=str(tmp_path / "A.sol"), payload=dict(unit_id="x", version="0.5.17", errors=[["t", "own-error"]],
                                                           changes=[dict(step="stub", old="", new="OWN_SECRET")]))
    other = Entry("K3", "K3:other", "other", "TypeError: Type uint256 is not implicitly convertible",
                  ("category:type_error_other",), group="elsewhere",
                  payload=dict(unit_id="y", version="0.5.17", errors=[["t", "e"]],
                               changes=[dict(step="stage1", old="if (a)", new="if (a != 0)")]))
    kb = KnowledgeBase([own, other], vocabulary=())
    record, agent, client, store = _run(tmp_path, BOOL, [GOOD], knowledge=kb)
    assert record.status == "success" and "OWN_SECRET" not in client.prompts[0] and "if (a != 0)" in client.prompts[0]


def test_without_an_agent_nothing_changes(tmp_path):
    production_required()
    path, unit = _unit(tmp_path, BOOL)
    record = repair_unit(unit, {"0.5.17": trusted_compilers()["0.5.17"]}, ArtifactStore(tmp_path / "run"), io.StringIO())
    assert record.status == "unrepaired" and not (tmp_path / "run/units/u/llm_calls.json").exists()


CONFIG = dict(
    budget=dict(max_calls=5, max_tokens=100000, max_cost_usd=0.5),
    models=dict(main=dict(model="model-x", api="anthropic", key_env="CR_TEST_KEY",
                          pricing=dict(input_per_million=3.0, output_per_million=15.0))),
    stage1=dict(model="main", candidates=2))


def test_agent_config_names_the_key_variable_only(tmp_path):
    path = tmp_path / "agent.json"
    path.write_text(json.dumps(CONFIG))
    chain = agents_from_config(path)
    assert chain.stage1.candidates == 2 and chain.stage1.client.model == "model-x" and chain.stage2 is None
    assert chain.budget.max_cost_usd == 0.5
    bad_model = dict(CONFIG["models"]["main"], key="sk-ant-0123456789abcdefghij")
    for bad in (dict(CONFIG, models=dict(main=bad_model)), dict(CONFIG, extra=1),
                dict(CONFIG, stage1=dict(model="main", typo=1))):
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            agents_from_config(path)


def test_cli_records_the_agent_and_spends_nothing_on_clean_input(tmp_path):
    production_required()
    (tmp_path / "agent.json").write_text(json.dumps(CONFIG))
    source = tmp_path / "C.sol"
    source.write_bytes(b"pragma solidity ^0.5.0;\ncontract C {}\n")
    assert main(["repair", str(source), "--output", str(tmp_path / "out"), "--agent-config", str(tmp_path / "agent.json")]) == 0
    summary = json.loads((tmp_path / "out/summary.json").read_text())
    seal = json.loads((tmp_path / "out/seal.json").read_text())
    assert summary["llm_calls"] == 0 and summary["cost_usd"] == 0.0
    assert "CR_TEST_KEY" in json.dumps(seal) and seal["tools"]["agent"]["models"]["main"]["model"] == "model-x"
