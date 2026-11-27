"""Second-stage multi-agent repair and the stage chain (PROMPTS 3.6, D8).

Stage 2 starts from the best state stage 1 reached (the pipeline's current state), with
every patch stage 1 tried and why it failed. Per round:
1. failure analysis: one model reads the rejected patches and their errors and answers
   CAUSE / NEED / SYMBOLS (agents/prompt.py analysis_prompt);
2. context: the proposers' view is widened as NEED asks: whole other project files
   (first those declaring SYMBOLS), K2 library files, more K1 documentation; this is a
   deterministic tool step driven by the analysis, not another model call;
3. 2-3 proposers on different models each write one patch, independently (no proposer
   sees another's answer);
4. the pipeline adjudicates: compile, D3, D7 (agents/patch.py), fewest errors, then
   most votes (identical resulting files count as one patch with several votes, the
   Agentless rule), then fewest changed bytes;
5. if no proposal is accepted, one exchange round: each proposer sees the other patches
   and their errors and revises once; if that also fails the stage ends (unrepaired).
After an accepted proposal the unit goes back through the rules, and stage 2 starts a
new round from the new state, up to `rounds`. A shared Budget bounds every model.

AgentChain runs stage 1 until it stops, then stage 2; `agents_from_config` builds the
chain from a JSON file (docs/AGENT_INTERFACE.md).
"""
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from compile_repair.agents.llm import Budget, BudgetExhausted, HttpClient, Pricing
from compile_repair.agents.patch import PatchRejected, candidate_patches
from compile_repair.agents.prompt import (ANALYSIS_SYSTEM, SYSTEM, analysis_prompt, build_view, error_lines,
    exchange_section, expanded_context, knowledge_block, knowledge_query, parse_analysis, repair_prompt)
from compile_repair.agents.stage1 import Stage1
from compile_repair.rag.knowledge import KnowledgeBase

WINDOW, ROUNDS, K, CONTEXT_LIMIT = 20, 2, 5, 12000


@dataclass
class Stage2:
    analyst: object
    proposers: list
    knowledge: object = None
    window: int = WINDOW
    rounds: int = ROUNDS
    k: int = K
    context_limit: int = CONTEXT_LIMIT
    analysis: bool = True          # ablation: no failure analysis
    exchange: bool = True          # ablation: no exchange round
    attempts: list = field(default_factory=list)
    used_rounds: int = 0
    phase: str = "propose"
    last: dict = field(default_factory=dict)
    stopped: str = None

    def reset(self, attempts=()):
        self.attempts, self.used_rounds, self.phase, self.last, self.stopped = list(attempts), 0, "propose", {}, None

    def active(self):
        return self.stopped is None

    def _ask(self, client, system, prompt, purpose):
        try:
            return client.complete(system, prompt, 1, purpose)
        except BudgetExhausted:
            self.stopped = "budget_exhausted"
            return None

    def propose(self, contents, entry, diagnostics, version, editable, issues, group, round_no,
                language_status="solidity", parser_only=False):
        if not self.active():
            return [], dict(stage=2, stopped=self.stopped)
        if self.phase == "propose" and self.used_rounds >= self.rounds:
            self.stopped = "rounds_exhausted"
            return [], dict(stage=2, stopped=self.stopped)
        view = build_view(contents, entry)
        query = knowledge_query(diagnostics, version, issues, group)
        evidence = dict(stage=2, phase=self.phase, round=self.used_rounds + (self.phase == "propose"), version=version)
        extra, calls = [], []
        if self.phase == "propose":
            self.used_rounds += 1
            self.last = {}
            analysis = dict(cause="", need=list(("files", "library", "docs")), symbols=[])
            if self.analysis:
                answer = self._ask(self.analyst, ANALYSIS_SYSTEM,
                                   analysis_prompt(view, diagnostics, version, self.window, self.attempts[-8:]),
                                   "stage2_analysis")
                if answer is None:
                    return [], dict(evidence, stopped=self.stopped)
                analysis = parse_analysis(answer.texts[0])
                calls.append(dict(purpose="analysis", request_sha256=answer.request_sha256, cost_usd=answer.cost_usd))
            self.context = [("Failure analysis", analysis["cause"])] if analysis["cause"] else []
            self.context += expanded_context(view, diagnostics, analysis, self.knowledge, query, self.k,
                                             self.context_limit)
            evidence.update(analysis=analysis, context_sections=[title for title, _ in self.context])
        knowledge, hit_ids = knowledge_block(self.knowledge, query, self.k)
        allowed = error_lines(diagnostics, view)
        texts = []
        for index, client in enumerate(self.proposers):
            extra = list(self.context)
            if self.phase == "exchange":
                own = self.last.get(index)
                others = [v for i, v in sorted(self.last.items()) if i != index]
                extra.append(("Exchange", exchange_section(own, others)))
            prompt = repair_prompt(view, diagnostics, version, self.window, knowledge, (), extra)
            answer = self._ask(client, SYSTEM, prompt, "stage2_%s" % self.phase)
            if answer is None:
                break
            calls.append(dict(purpose=self.phase, proposer=index, model=client.model,
                              request_sha256=answer.request_sha256, cost_usd=answer.cost_usd))
            texts.append((index, client.model, answer.texts[0]))
        candidates, rejected, seen = [], [], {}
        for index, model, text in texts:
            try:
                edits, patches, summary = candidate_patches(text, view, contents, allowed, editable, round_no, "stage2")
            except PatchRejected as exc:
                rejected.append(dict(proposer=index, model=model, reason=str(exc)))
                self.last[index] = dict(reason=str(exc), patch=text, errors=[])
                self.attempts.append(dict(reason=str(exc), patch=text, errors=[]))
                continue
            key = hashlib.sha256(json.dumps({n: e.hex() for n, e in sorted(edits.items())}).encode()).hexdigest()
            if key in seen:  # identical resulting files: one patch, one more vote
                seen[key][2]["votes"] += 1
                seen[key][2]["proposers"].append(index)
                continue
            seen[key] = (edits, patches, dict(summary, candidate=index, proposers=[index], votes=1, stage=2,
                                              model=model, text=text))
            candidates.append(seen[key])
        evidence.update(calls=calls, knowledge=hit_ids, rejected=rejected, valid=len(candidates),
                        votes=[c[2]["votes"] for c in candidates])
        if self.stopped:
            evidence["stopped"] = self.stopped
        return candidates, evidence

    def observe(self, accepted, outcomes):
        for summary, reason, errors in outcomes:
            item = dict(reason=reason, patch=summary["text"], errors=errors)
            self.attempts.append(item)
            for proposer in summary.get("proposers", ()):
                self.last[proposer] = item
        if accepted:
            self.phase = "propose"
        elif self.phase == "propose" and self.exchange and self.last:
            self.phase = "exchange"
        else:
            self.stopped = "exchange_failed" if self.phase == "exchange" else "stalled"


class AgentChain:
    """Stage 1, then stage 2 from the best state; one budget and one call record for both."""

    def __init__(self, stage1, stage2=None, description=None):
        self.stage1, self.stage2, self.description = stage1, stage2, description
        self.current = stage1

    @property
    def records(self):
        return self.stage1.records

    @property
    def budget(self):
        return self.stage1.budget

    def reset(self):
        self.stage1.reset()
        if self.stage2 is not None:
            self.stage2.reset()
        self.current, self.started2 = self.stage1, False

    def active(self):
        return self.stage1.active() or (self.stage2 is not None and self.stage2.active())

    @property
    def stopped(self):
        if self.active():
            return None
        parts = ["stage1:%s" % self.stage1.stopped]
        if self.stage2 is not None:
            parts.append("stage2:%s" % self.stage2.stopped)
        return ", ".join(parts)

    def propose(self, *args, **kwargs):
        if self.stage1.active():
            self.current = self.stage1
            candidates, evidence = self.stage1.propose(*args, **kwargs)
            if candidates or self.stage1.active() or self.stage2 is None:
                return candidates, dict(evidence, stage=1)
        if not self.started2:
            # Stage 2 starts from the best state with everything stage 1 tried (PROMPTS 3.6 item 6);
            # it does not run on text the language check rejected or after the budget ran out.
            self.stage2.reset(self.stage1.history)
            self.started2 = True
            if self.stage1.stopped in ("language_check_not_solidity", "budget_exhausted"):
                self.stage2.stopped = "skipped:" + self.stage1.stopped
        self.current = self.stage2
        return self.stage2.propose(*args, **kwargs)

    def observe(self, accepted, outcomes):
        if self.current.active():
            self.current.observe(accepted, outcomes)


# ---- configuration (docs/AGENT_INTERFACE.md) ---------------------------------------------

TOP_KEYS = {"budget", "cache_dir", "knowledge", "models", "stage1", "stage2"}
MODEL_KEYS = {"model", "api", "key_env", "base_url", "pricing", "temperature", "max_output_tokens", "timeout"}
STAGE1_KEYS = {"model", "window", "candidates", "rounds", "stall_rounds", "k"}
STAGE2_KEYS = {"analyst", "proposers", "window", "rounds", "k", "context_limit", "analysis", "exchange"}


def _looks_like_key(value):
    if isinstance(value, dict):
        return any(_looks_like_key(v) for v in value.values())
    if isinstance(value, list):
        return any(_looks_like_key(v) for v in value)
    return isinstance(value, str) and len(value) > 20 and value.startswith(("sk-", "sk_", "sk-ant-"))


def _check(keys, allowed, where):
    unknown = set(keys) - allowed
    if unknown:
        raise ValueError("Unknown keys in %s: %s" % (where, sorted(unknown)))


def agents_from_config(path):
    """AgentChain from a JSON configuration (schema in docs/AGENT_INTERFACE.md)."""
    config = json.loads(Path(path).read_text(encoding="utf8"))
    if _looks_like_key(config):
        raise ValueError("The configuration must name the key's environment variable, not contain a key")
    _check(config, TOP_KEYS, "the configuration")
    budget, records = Budget(**config["budget"]), []
    clients = {}
    for name, spec in config["models"].items():
        _check(spec, MODEL_KEYS, "models.%s" % name)
        clients[name] = HttpClient(spec["model"], spec["api"], budget, Pricing(**spec["pricing"]), spec["key_env"],
                                   base_url=spec.get("base_url"), timeout=spec.get("timeout", 120),
                                   cache_dir=config.get("cache_dir"), records=records,
                                   max_output_tokens=spec.get("max_output_tokens", 2048),
                                   temperature=spec.get("temperature", 0.8))
    knowledge = KnowledgeBase.load(config["knowledge"]) if config.get("knowledge") else None
    first = config["stage1"]
    _check(first, STAGE1_KEYS, "stage1")
    stage1 = Stage1(clients[first["model"]], knowledge, **{k: v for k, v in first.items() if k != "model"})
    stage2 = None
    if config.get("stage2"):
        second = config["stage2"]
        _check(second, STAGE2_KEYS, "stage2")
        if not 1 <= len(second["proposers"]) <= 3:
            raise ValueError("stage2.proposers names 1-3 models (2-3 different models per D8; 1 is an ablation)")
        stage2 = Stage2(clients[second["analyst"]], [clients[n] for n in second["proposers"]], knowledge,
                        **{k: v for k, v in second.items() if k not in ("analyst", "proposers")})
    models = {name: {k: v for k, v in spec.items()} for name, spec in config["models"].items()}
    description = dict(models=models, stage1=first, stage2=config.get("stage2"), budget=config["budget"],
                       heterogeneous=stage2 is not None and len({clients[n].model for n in config["stage2"]["proposers"]}) > 1,
                       knowledge_counts=None if knowledge is None else {s: len(e) for s, e in knowledge.by_source.items()})
    return AgentChain(stage1, stage2, description)
