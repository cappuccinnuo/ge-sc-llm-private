"""Model clients, response cache, budget and call records (PROMPTS 3.5, D12).

A client turns one prompt into N completions. Every call is metered against a Budget
(calls, tokens, cost in USD) checked before the request is sent, cached by the SHA-256
of its canonical request (a cached answer costs nothing and is reproducible), and
recorded: model, request hash, cache hit, tokens, cost, elapsed time, error. Keys are
read only from environment variables and never enter a request record, cache entry
or log.

HttpClient speaks the Anthropic Messages API and the OpenAI-compatible chat API; which
model, API and cost cap are used is D12 (the user's decision). ScriptedClient replays
fixed answers for tests and for runs without authorization; it is the only client
that runs without a key.
"""
import hashlib
import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


class BudgetExhausted(Exception):
    """The next call would exceed the authorized calls, tokens or cost."""


@dataclass
class Budget:
    max_calls: int
    max_tokens: int
    max_cost_usd: float
    calls: int = 0
    tokens: int = 0
    cost_usd: float = 0.0

    def check(self, estimated_tokens, estimated_cost):
        if (self.calls + 1 > self.max_calls or self.tokens + estimated_tokens > self.max_tokens
                or self.cost_usd + estimated_cost > self.max_cost_usd + 1e-12):
            raise BudgetExhausted(dict(calls=self.calls, tokens=self.tokens, cost_usd=round(self.cost_usd, 6)))

    def charge(self, tokens, cost):
        self.calls += 1
        self.tokens += tokens
        self.cost_usd += cost

    def snapshot(self):
        return dict(calls=self.calls, tokens=self.tokens, cost_usd=round(self.cost_usd, 6),
                    max_calls=self.max_calls, max_tokens=self.max_tokens, max_cost_usd=self.max_cost_usd)


@dataclass(frozen=True)
class Completion:
    texts: tuple
    model: str
    request_sha256: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cached: bool
    elapsed_seconds: float


@dataclass(frozen=True)
class Pricing:
    """USD per million input and output tokens (from the provider's price list, D12)."""
    input_per_million: float
    output_per_million: float

    def cost(self, input_tokens, output_tokens):
        return (input_tokens * self.input_per_million + output_tokens * self.output_per_million) / 1e6


def request_sha256(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf8")).hexdigest()


class Client:
    """Shared metering, cache and records; subclasses implement `_send`."""
    model = None

    def __init__(self, budget, pricing, cache_dir=None, max_output_tokens=2048, temperature=0.8, records=None):
        """`budget` and `records` may be shared by several clients (stage 2's models)."""
        self.budget, self.pricing = budget, pricing
        self.cache = Path(cache_dir) if cache_dir else None
        self.max_output_tokens, self.temperature = max_output_tokens, temperature
        self.records = records if records is not None else []

    def complete(self, system, prompt, n, purpose):
        request = dict(model=self.model, system=system, prompt=prompt, n=n, temperature=self.temperature,
                       max_output_tokens=self.max_output_tokens)
        digest = request_sha256(request)
        started = time.monotonic()
        record = dict(purpose=purpose, model=self.model, request_sha256=digest, n=n)
        cached = self._cached(digest)
        if cached is not None:
            result = Completion(tuple(cached["texts"]), self.model, digest, cached["input_tokens"],
                                cached["output_tokens"], 0.0, True, time.monotonic() - started)
            self.records.append(dict(record, cached=True, input_tokens=result.input_tokens,
                                     output_tokens=result.output_tokens, cost_usd=0.0, error=None))
            return result
        estimate_in = (len(system) + len(prompt)) // 3 + 1
        self.budget.check(estimate_in * n + self.max_output_tokens * n,
                          self.pricing.cost(estimate_in * n, self.max_output_tokens * n))
        try:
            texts, input_tokens, output_tokens = self._send(system, prompt, n)
        except Exception as exc:  # recorded, then raised to the caller
            self.records.append(dict(record, cached=False, error="%s: %s" % (type(exc).__name__, str(exc)[:200]),
                                     elapsed_seconds=time.monotonic() - started))
            raise
        cost = self.pricing.cost(input_tokens, output_tokens)
        self.budget.charge(input_tokens + output_tokens, cost)
        result = Completion(tuple(texts), self.model, digest, input_tokens, output_tokens, cost, False,
                            time.monotonic() - started)
        if self.cache is not None:
            self.cache.mkdir(parents=True, exist_ok=True)
            (self.cache / (digest + ".json")).write_text(json.dumps(dict(
                request=request, texts=list(texts), input_tokens=input_tokens, output_tokens=output_tokens),
                ensure_ascii=False, sort_keys=True), encoding="utf8")
        self.records.append(dict(record, cached=False, input_tokens=input_tokens, output_tokens=output_tokens,
                                 cost_usd=round(cost, 6), elapsed_seconds=round(result.elapsed_seconds, 3),
                                 error=None))
        return result

    def _cached(self, digest):
        if self.cache is None or not (self.cache / (digest + ".json")).exists():
            return None
        return json.loads((self.cache / (digest + ".json")).read_text(encoding="utf8"))

    def _send(self, system, prompt, n):
        raise NotImplementedError


class ScriptedClient(Client):
    """Replays answers: `answer(system, prompt, index)` gives the index-th completion."""

    def __init__(self, answer, budget=None, pricing=Pricing(0.0, 0.0), model="scripted", **kwargs):
        super().__init__(budget or Budget(10 ** 6, 10 ** 12, 0.0), pricing, **kwargs)
        self.answer, self.model = answer, model
        self.prompts = []

    def _send(self, system, prompt, n):
        self.prompts.append(prompt)
        texts = [self.answer(system, prompt, i) for i in range(n)]
        return texts, (len(system) + len(prompt)) // 4 + 1, sum(len(t) for t in texts) // 4 + 1


class HttpClient(Client):
    """Anthropic Messages API (`api="anthropic"`) or an OpenAI-compatible chat API (`api="openai"`).

    The key is read from `key_env` at call time. Anthropic has no `n`; N completions are
    N requests in one metered call.
    """

    def __init__(self, model, api, budget, pricing, key_env, base_url=None, timeout=120, **kwargs):
        if api not in ("anthropic", "openai"):
            raise ValueError("api must be 'anthropic' or 'openai'")
        super().__init__(budget, pricing, **kwargs)
        self.model, self.api, self.key_env, self.timeout = model, api, key_env, timeout
        self.base_url = base_url or ("https://api.anthropic.com/v1/messages" if api == "anthropic"
                                     else "https://api.openai.com/v1/chat/completions")

    def _key(self):
        key = os.environ.get(self.key_env)
        if not key:
            raise RuntimeError("Environment variable %s is not set" % self.key_env)
        return key

    def _post(self, body, headers):
        request = urllib.request.Request(self.base_url, data=json.dumps(body).encode("utf8"),
                                         headers=dict(headers, **{"content-type": "application/json"}))
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf8"))

    def _send(self, system, prompt, n):
        if self.api == "anthropic":
            headers = {"x-api-key": self._key(), "anthropic-version": "2023-06-01"}
            texts, used_in, used_out = [], 0, 0
            for _ in range(n):
                answer = self._post(dict(model=self.model, max_tokens=self.max_output_tokens,
                                         temperature=self.temperature, system=system,
                                         messages=[dict(role="user", content=prompt)]), headers)
                texts.append("".join(b.get("text", "") for b in answer["content"] if b.get("type") == "text"))
                used_in += answer["usage"]["input_tokens"]
                used_out += answer["usage"]["output_tokens"]
            return texts, used_in, used_out
        answer = self._post(dict(model=self.model, n=n, max_tokens=self.max_output_tokens,
                                 temperature=self.temperature,
                                 messages=[dict(role="system", content=system), dict(role="user", content=prompt)]),
                            {"authorization": "Bearer " + self._key()})
        return ([c["message"]["content"] or "" for c in answer["choices"]],
                answer["usage"]["prompt_tokens"], answer["usage"]["completion_tokens"])
