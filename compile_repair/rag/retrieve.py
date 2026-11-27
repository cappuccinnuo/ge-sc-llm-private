"""Exact-key lookup, then BM25 (PROMPTS 3.4, CP7).

For each source the exact matches come first (ordered by BM25 score), then the best
remaining BM25 matches fill the list up to k. Embedding retrieval is not used here; it
is only an ablation (PROMPTS 3.4).

Filters applied before ranking:
- K1: the section must be in the docs of the query's compiler version;
- K2: the file's pragma interval must admit the version when both are known;
- K3: entries of the query's own project group are never candidates (leave one project
  out, PROMPTS 3.4); a K3 query without a group is rejected.
"""
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from compile_repair.rag.knowledge import message_template, split_first_line, template_terms
from compile_repair.toolchain.solc import version_tuple

BM25_K1, BM25_B = 1.2, 0.75
TITLE_WEIGHT = 3
_STOP = frozenset("a an and are as at be by for from has have in is it its not of on or that the this to was "
                  "with id did you your".split())


def _stem(word):
    """Light suffix stripping, so that "documented" and "documents" meet."""
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[:-len(suffix)]
    return word


def tokens(text):
    """Lower-case stemmed words; camelCase and snake_case identifiers are split into parts."""
    words = []
    for word in re.findall(r"[A-Za-z][A-Za-z0-9]*|[0-9]+", text.replace("_", " ")):
        parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+", word) or [word]
        words += [_stem(p.lower()) for p in parts if p.lower() not in _STOP]
    return words


class BM25:
    def __init__(self, entries):
        self.entries = entries
        self.lengths, self.postings = [], defaultdict(list)
        for position, entry in enumerate(entries):
            # Title words count TITLE_WEIGHT times (a section heading names its subject).
            counts = Counter(tokens(entry.text) + tokens(entry.title) * (TITLE_WEIGHT - 1))
            self.lengths.append(sum(counts.values()))
            for word, count in counts.items():
                self.postings[word].append((position, count))
        self.average = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0

    def scores(self, query, allowed=None):
        total, result = len(self.entries), defaultdict(float)
        for word in set(tokens(query)):
            postings = self.postings.get(word, ())
            if not postings:
                continue
            idf = math.log(1 + (total - len(postings) + 0.5) / (len(postings) + 0.5))
            for position, count in postings:
                if allowed is not None and position not in allowed:
                    continue
                norm = count + BM25_K1 * (1 - BM25_B + BM25_B * self.lengths[position] / self.average)
                result[position] += idf * count * (BM25_K1 + 1) / norm
        return result


@dataclass(frozen=True)
class Query:
    """What the agent knows about a failure: first lines or diagnostics, version, symbols."""
    errors: tuple = ()            # (kind or None, message) pairs, or first error lines (str)
    version: str = None
    symbols: tuple = ()           # missing identifiers (K2 exact keys)
    import_paths: tuple = ()      # unresolved import paths (K2 exact keys)
    categories: tuple = ()        # classifier categories of the errors (K3 exact keys)
    group: str = None             # project group (K3 leave-one-project)


@dataclass(frozen=True)
class Hit:
    entry_id: str
    source: str
    score: float
    match: str                    # "exact" or "bm25"


def _errors(query):
    return [split_first_line(e) if isinstance(e, str) else e for e in query.errors]


def _index(kb, source):
    if source not in kb.cache:
        entries = kb.by_source[source]
        kb.cache[source] = (BM25(entries), {e.entry_id: i for i, e in enumerate(entries)}, _key_index(entries))
    return kb.cache[source]


def _key_index(entries):
    keys = defaultdict(set)
    for position, entry in enumerate(entries):
        for key in entry.keys:
            keys[key].add(position)
    return keys


def _allowed(kb, source, query):
    entries = kb.by_source[source]
    if source == "K1" and query.version:
        return {i for i, e in enumerate(entries) if query.version in e.versions}
    if source == "K2" and query.version:
        version = version_tuple(query.version)
        return {i for i, e in enumerate(entries) if not e.payload.get("interval")
                or tuple(e.payload["interval"][0]) <= version < tuple(e.payload["interval"][1])}
    if source == "K3":
        if query.group is None:
            raise ValueError("A K3 query needs its project group (leave-one-project)")
        return {i for i, e in enumerate(entries) if e.group != query.group}
    return None


def query_keys(kb, query, source):
    """Exact keys and BM25 text of a query for one source."""
    templates = [((kind + ": ") if kind else "") + message_template(message, kb.vocabulary)
                 for kind, message in _errors(query)]
    # The classifier categories are part of the error key (PROMPTS 3.4: solc error type).
    text = " ".join(t.replace('"<id>"', " ") for t in templates) + " " + " ".join(query.categories)
    if any(kind == "F" for kind, _ in _errors(query)):
        # "F:" errors come only from the version-constraint reader (rules/environment.py),
        # so their subject is the `pragma solidity` version pragma.
        text += " solidity version pragma"
    if source == "K1":
        keys = {"term:" + t for template in templates for t in template_terms(template)}
    elif source == "K2":
        keys = {"symbol:" + s for s in query.symbols} | {"path:" + p for p in query.import_paths}
        text += " " + " ".join(query.symbols) + " " + " ".join(re.split(r"[/._@-]", " ".join(query.import_paths)))
    else:
        keys = {"template:" + t for t in templates} | {"category:" + c for c in query.categories}
    return keys, text


def retrieve(kb, query, k, sources=("K1", "K2", "K3")):
    """Top-k hits per source: exact key matches first, then BM25."""
    result = {}
    for source in sources:
        entries = kb.by_source[source]
        if not entries:
            result[source] = []
            continue
        bm25, _, key_index = _index(kb, source)
        allowed = _allowed(kb, source, query)
        keys, text = query_keys(kb, query, source)
        exact = set().union(*(key_index.get(key, set()) for key in keys)) if keys else set()
        if allowed is not None:
            exact &= allowed
        scores = bm25.scores(text, allowed)
        ranked = sorted(exact, key=lambda i: (-scores.get(i, 0.0), entries[i].entry_id))
        hits = [Hit(entries[i].entry_id, source, scores.get(i, 0.0), "exact") for i in ranked[:k]]
        if len(hits) < k:
            rest = sorted((i for i, s in scores.items() if s > 0 and i not in exact),
                          key=lambda i: (-scores[i], entries[i].entry_id))
            hits += [Hit(entries[i].entry_id, source, scores[i], "bm25") for i in rest[:k - len(hits)]]
        result[source] = hits
    return result
