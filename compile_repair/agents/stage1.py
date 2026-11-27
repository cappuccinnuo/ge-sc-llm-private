"""First-stage agent (PROMPTS 3.5, D8): one template, RAG, checked patches, N candidates.

The pipeline owns compilation and acceptance; this module owns what the model is asked
and how its answers become candidate patches. Per round:
1. build the view and the prompt from the current best state's errors (agents/prompt.py);
2. ask for N completions (agents/llm.py, metered and cached);
3. turn each completion into byte patches or reject it (agents/patch.py);
4. the pipeline compiles each valid candidate on a copy and keeps the one with the
   fewest errors (then the fewest changed bytes), under the usual acceptance rule;
5. rejected candidates and their errors go into the next round's prompt.
The stage ends when the rounds or the budget run out, or after `stall_rounds`
consecutive rounds that the pipeline did not accept (PROMPTS 3.5 item 6); the second
stage (agents/stage2.py) then takes over from the best state reached.

Language check (r2.16): for an input whose language is unknown and whose errors all
belong to the parser phase (the pipeline's D27 phase table), one short call first asks whether the text is Solidity; any answer
but SOLIDITY ends the stage without a repair call.
"""
from dataclasses import dataclass, field

from compile_repair.agents.llm import BudgetExhausted
from compile_repair.agents.patch import PatchRejected, candidate_patches
from compile_repair.agents.prompt import (LANGUAGE_SYSTEM, SYSTEM, build_view, error_lines, knowledge_block,
    knowledge_query, language_prompt, repair_prompt)

# Defaults until CP8's small authorized sample decides them (PROMPTS 3.5 item 1: the window
# is chosen on the benchmark); k = 5 is CP7's choice.
WINDOW, CANDIDATES, ROUNDS, STALL_ROUNDS, K = 10, 3, 4, 2, 5


@dataclass
class Stage1:
    client: object
    knowledge: object = None
    window: int = WINDOW
    candidates: int = CANDIDATES
    rounds: int = ROUNDS
    stall_rounds: int = STALL_ROUNDS
    k: int = K
    history: list = field(default_factory=list)
    used_rounds: int = 0
    stalled: int = 0
    stopped: str = None

    def reset(self):
        """Start a new unit: no history, full rounds (the budget is shared across units)."""
        self.history, self.used_rounds, self.stalled, self.stopped = [], 0, 0, None

    def active(self):
        return self.stopped is None

    @property
    def records(self):
        return self.client.records

    @property
    def budget(self):
        return self.client.budget

    def language_ok(self, view, language_status, parser_only):
        """True unless the r2.16 check applies and the model says the text is not Solidity."""
        if language_status != "unknown" or not parser_only:
            return True, None
        try:
            answer = self.client.complete(LANGUAGE_SYSTEM, language_prompt(view), 1, "language_check")
        except BudgetExhausted:
            self.stopped = "budget_exhausted"
            return False, dict(language_check="budget_exhausted")
        verdict = answer.texts[0].strip().upper()
        if not verdict.startswith("SOLIDITY"):
            self.stopped = "language_check_not_solidity"
            return False, dict(language_check=verdict[:40])
        return True, dict(language_check="SOLIDITY")

    def propose(self, contents, entry, diagnostics, version, editable, issues, group, round_no,
                language_status="solidity", parser_only=False):
        """Candidates for one round: [(edits, patches, evidence)] plus the round's evidence."""
        if not self.active():
            return [], dict(stopped=self.stopped)
        if self.used_rounds >= self.rounds:
            self.stopped = "rounds_exhausted"
            return [], dict(stopped=self.stopped)
        view = build_view(contents, entry)
        evidence = dict(round=self.used_rounds + 1, version=version, files=len(view.ids))
        if self.used_rounds == 0:
            ok, check = self.language_ok(view, language_status, parser_only)
            if check:
                evidence.update(check)
            if not ok:
                evidence["stopped"] = self.stopped
                return [], evidence
        knowledge, hit_ids = knowledge_block(self.knowledge, knowledge_query(diagnostics, version, issues, group), self.k)
        prompt = repair_prompt(view, diagnostics, version, self.window, knowledge, self.history[-self.candidates:])
        try:
            answer = self.client.complete(SYSTEM, prompt, self.candidates, "stage1_repair")
        except BudgetExhausted:
            self.stopped = "budget_exhausted"
            evidence["stopped"] = self.stopped
            return [], evidence
        self.used_rounds += 1
        allowed = error_lines(diagnostics, view)
        candidates, rejected = [], []
        for index, text in enumerate(answer.texts):
            try:
                edits, patches, summary = candidate_patches(text, view, contents, allowed, editable, round_no)
            except PatchRejected as exc:
                rejected.append(dict(candidate=index, reason=str(exc)))
                self.history.append(dict(reason=str(exc), patch=text, errors=[]))
                continue
            candidates.append((edits, patches, dict(summary, candidate=index, votes=1, stage=1, text=text)))
        evidence.update(request_sha256=answer.request_sha256, cached=answer.cached, cost_usd=round(answer.cost_usd, 6),
                        input_tokens=answer.input_tokens, output_tokens=answer.output_tokens,
                        knowledge=hit_ids, rejected=rejected, valid=len(candidates))
        return candidates, evidence

    def observe(self, accepted, outcomes):
        """Feed the pipeline's verdicts back: non-chosen candidates enter the history.

        `outcomes` holds (candidate summary, reason, error lines) per candidate not chosen.
        """
        for summary, reason, errors in outcomes:
            self.history.append(dict(reason=reason, patch=summary["text"], errors=errors))
        self.stalled = 0 if accepted else self.stalled + 1
        if self.stalled >= self.stall_rounds:
            self.stopped = "stalled"

