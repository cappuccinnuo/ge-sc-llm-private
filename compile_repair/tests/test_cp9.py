"""CP9: second-stage multi-agent repair with scripted models (PROMPTS 3.6, D8)."""
import hashlib
import io
import json

import pytest

from compile_repair.agents.llm import Budget, ScriptedClient
from compile_repair.agents.prompt import build_view, expanded_context, knowledge_query, parse_analysis
from compile_repair.agents.stage1 import Stage1
from compile_repair.agents.stage2 import AgentChain, Stage2, agents_from_config
from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.rag.knowledge import Entry, KnowledgeBase
from compile_repair.tests.test_cp8 import BOOL, GOOD, STALE, WORSE
from compile_repair.tests.test_production import production_required, trusted_compilers

ANALYSIS = "CAUSE: x is uint; a condition needs a bool comparison.\nNEED: docs\nSYMBOLS: none\n"
SHORT = GOOD.replace("x != 0", "x > 0")  # also compiles; one byte shorter


def _chain(stage1_answer, proposer_answers, budget=None, **stage2_options):
    """Stage 1 on model "s1", analyst "an", proposers "A", "B", ... with one shared budget and record."""
    budget, records = budget or Budget(1000, 10 ** 9, 1.0), []
    def client(model, answer):
        return ScriptedClient(answer, budget=budget, model=model, records=records)
    stage1 = Stage1(client("s1", stage1_answer), candidates=1)
    proposers = [client(m, a) for m, a in proposer_answers]
    analyst = client("an", lambda s, p, i: ANALYSIS)
    return AgentChain(stage1, Stage2(analyst, proposers, **stage2_options)), proposers, analyst


def _run(tmp_path, chain, raw=BOOL):
    production_required()
    path = tmp_path / "A.sol"
    path.write_bytes(raw)
    unit = CompilationUnit("u", (SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw),))
    store = ArtifactStore(tmp_path / "run")
    record = repair_unit(unit, {"0.5.17": trusted_compilers()["0.5.17"]}, store, io.StringIO(), agent=chain)
    assert path.read_bytes() == raw
    steps = json.loads((store.path / "units/u/repair_steps.json").read_text())
    calls = json.loads((store.path / "units/u/llm_calls.json").read_text())
    return record, steps, calls


def _fixed(text):
    return lambda s, p, i: text


def test_stage2_takes_over_after_stage1_stalls(tmp_path):
    chain, proposers, analyst = _chain(_fixed(STALE), [("A", _fixed(WORSE)), ("B", _fixed(GOOD))])
    record, steps, calls = _run(tmp_path, chain)
    assert record.status == "success"
    assert {c.step for p in record.provenance.values() for c in p.changes} == {"stage2"}
    rounds = [s for s in steps if s.get("operation") == "agent_round"]
    assert [r["stage"] for r in rounds] == [1, 1, 2]
    assert rounds[2]["analysis"]["cause"].startswith("x is uint") and rounds[2]["valid"] == 2
    purposes = [c["purpose"] for c in calls["calls"]]
    assert purposes == ["stage1_repair", "stage1_repair", "stage2_analysis", "stage2_propose", "stage2_propose"]
    # The analysis read what stage 1 tried; the proposers never see each other's answers.
    assert "Rejected repair attempts" in analyst.prompts[0] and "original line F1:5 does not match" in analyst.prompts[0]
    assert all("x != y" not in p and "Another proposer" not in p for p in proposers[1].prompts)
    assert "Failure analysis:\nx is uint" in proposers[0].prompts[0]


def test_identical_patches_vote(tmp_path):
    chain, _, _ = _chain(_fixed(STALE), [("A", _fixed(GOOD)), ("B", _fixed(SHORT)), ("C", _fixed(GOOD))])
    record, steps, _ = _run(tmp_path, chain)
    assert record.status == "success"
    rounds = [s for s in steps if s.get("operation") == "agent_round" and s["stage"] == 2]
    assert rounds[0]["votes"] == [2, 1]
    new = b"".join(c.new for p in record.provenance.values() for c in p.changes)
    assert b"x != 0" in new  # two votes beat one shorter patch


def test_exchange_round_shows_the_other_patches_and_can_succeed(tmp_path):
    def revising(good):
        return lambda s, p, i: good if "All proposals failed" in p else WORSE
    chain, proposers, _ = _chain(_fixed(STALE), [("A", revising(GOOD)), ("B", revising(GOOD))])
    record, steps, _ = _run(tmp_path, chain)
    assert record.status == "success"
    phases = [s["phase"] for s in steps if s.get("operation") == "agent_round" and s["stage"] == 2]
    assert phases == ["propose", "exchange"]
    exchange = proposers[0].prompts[1]
    assert "Your patch" in exchange and "Another proposer's patch" in exchange and "Resulting errors" in exchange


def test_failed_exchange_ends_unrepaired(tmp_path):
    chain, proposers, _ = _chain(_fixed(STALE), [("A", _fixed(WORSE)), ("B", _fixed(STALE))])
    record, steps, calls = _run(tmp_path, chain)
    assert record.status != "success" and chain.stage2.stopped == "exchange_failed"
    assert chain.stopped == "stage1:stalled, stage2:exchange_failed"
    assert [s["reason"] for s in steps if s.get("operation") == "agent_end"] == [chain.stopped]
    assert len(proposers[0].prompts) == 2  # one proposal, one revision


@pytest.mark.parametrize("options,purposes", [
    (dict(analysis=False), ["stage2_propose", "stage2_propose", "stage2_exchange", "stage2_exchange"]),
    (dict(exchange=False), ["stage2_analysis", "stage2_propose", "stage2_propose"]),
])
def test_ablations_drop_their_step(tmp_path, options, purposes):
    chain, _, _ = _chain(_fixed(STALE), [("A", _fixed(WORSE)), ("B", _fixed(WORSE))], **options)
    record, _, calls = _run(tmp_path, chain)
    assert [c["purpose"] for c in calls["calls"] if c["purpose"].startswith("stage2")] == purposes


def test_shared_budget_stops_stage2(tmp_path):
    chain, _, _ = _chain(_fixed(STALE), [("A", _fixed(GOOD))], budget=Budget(3, 10 ** 9, 1.0))
    record, _, calls = _run(tmp_path, chain)
    assert record.status != "success" and chain.stage2.stopped == "budget_exhausted"
    assert calls["budget"]["calls"] == 3 and len(calls["calls"]) == 3


def test_stage2_does_not_run_on_text_that_is_not_solidity(tmp_path):
    def answer(s, p, i):
        return "OTHER" if p.startswith("Is the following text Solidity") else GOOD
    chain, proposers, analyst = _chain(answer, [("A", _fixed(GOOD))])
    record, _, calls = _run(tmp_path, chain, b"Just a sentence.\nAnd another one.\n")
    assert chain.stage2.stopped == "skipped:language_check_not_solidity" and analyst.prompts == []
    assert [c["purpose"] for c in calls["calls"]] == ["language_check"]


# ---- analysis parsing and context expansion -------------------------------------------------

def test_analysis_lines_are_parsed_leniently():
    found = parse_analysis("Some preamble\nCAUSE: Helper is a struct\nNEED: files and library\nSYMBOLS: Helper, Info")
    assert found == dict(cause="Helper is a struct", need=["files", "library"], symbols=["Helper", "Info"])
    assert parse_analysis("nothing") == dict(cause="", need=[], symbols=[])


def test_context_expansion_follows_the_analysis():
    contents = {"a/Main.sol": b"pragma solidity ^0.5.0;\nimport \"./Lib.sol\";\ncontract M is Base {}\n",
                "a/Lib.sol": b"pragma solidity ^0.5.0;\n// the base\ncontract Base { uint v; }\n",
                "a/Other.sol": b"contract Unrelated {}\n"}
    view = build_view(contents, "a/Main.sol")
    diagnostics = {"a/Main.sol": [dict(kind="TypeError", line=3, message='Identifier "Base" wrong.', category="other")]}
    library = Entry("K2", "K2:lib@1/Base.sol", "lib@1 Base.sol", "Base", ("symbol:Base",), payload=dict(interval=None))
    kb = KnowledgeBase([library], vocabulary=())
    query = knowledge_query(diagnostics, "0.5.17", (), "g")
    sections = expanded_context(view, diagnostics, dict(cause="", need=["files", "library"], symbols=["Base"]),
                                kb, query, 5, 10000)
    titles = [t for t, _ in sections]
    assert titles[0] == "Whole file F2" and "Whole file F3" in titles and "[K2] lib@1 Base.sol" in titles
    assert "the base" not in json.dumps(sections)  # comments stay blanked
    assert expanded_context(view, diagnostics, dict(cause="", need=[], symbols=[]), kb, query, 5, 10000) == []
    limit = len(dict(sections)["Whole file F2"]) + 5
    small = expanded_context(view, diagnostics, dict(cause="", need=["files"], symbols=["Base"]), kb, query, 5, limit)
    assert [t for t, _ in small] == ["Whole file F2"]  # the declaring file first; the limit drops the rest


# ---- configuration --------------------------------------------------------------------------

def _model(name):
    return dict(model=name, api="openai" if name.startswith("gpt") else "anthropic", key_env="KEY_" + name.upper().replace("-", "_"),
                pricing=dict(input_per_million=1.0, output_per_million=2.0))


def test_config_builds_a_heterogeneous_chain_with_one_budget(tmp_path):
    config = dict(budget=dict(max_calls=50, max_tokens=10 ** 6, max_cost_usd=10.0),
                  models={"a": _model("model-a"), "b": _model("gpt-b"), "c": _model("model-c")},
                  stage1=dict(model="a"), stage2=dict(analyst="a", proposers=["a", "b", "c"], window=25))
    path = tmp_path / "agents.json"
    path.write_text(json.dumps(config))
    chain = agents_from_config(path)
    clients = [chain.stage1.client, chain.stage2.analyst] + chain.stage2.proposers
    assert len({id(c.budget) for c in clients}) == 1 and len({id(c.records) for c in clients}) == 1
    assert [c.model for c in chain.stage2.proposers] == ["model-a", "gpt-b", "model-c"]
    assert chain.stage2.window == 25 and chain.description["heterogeneous"] is True
    for bad in (dict(config, stage2=dict(analyst="a", proposers=["a", "b", "c", "a"])),
                dict(config, stage2=dict(analyst="a", proposers=[], window=1)),
                dict(config, stage2=dict(analyst="a", proposers=["a"], vote=True))):
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            agents_from_config(path)
