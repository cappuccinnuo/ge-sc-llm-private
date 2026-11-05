"""Prompt 8D neutral, length-preserving lexical interventions.

This module never changes source files, graph attributes, labels or the frozen
TokenEncoder. Full tokenizer sequences (not padded/truncated 512-vectors) are
used for acceptance. C selection is declaration-backed and fails explicitly
when the requested count/length histogram cannot be matched.
"""
import hashlib
import bisect
from collections import Counter, defaultdict

from scripts.DFG.dfg_v2.diagnostics8c.inference import (
    MARKERS, identifiers, serialized_view)

ALGORITHM = "prompt8d-neutral-renaming-v1"
WORDS = ("alpha", "beta", "gamma", "delta", "theta", "sigma", "kappa", "omega", "Theta", "Sigma", "cedar", "marble", "pear")
# These supplement positive AST declaration recognition; the candidate set is
# never obtained merely by subtracting a short keyword list from all lexemes.
EXCLUDED_NAMES = frozenset("""
abi addmod address after alias anonymous apply as assembly assert auto balance
block blockhash bool break byte bytes call callcode calldata caller callvalue
case catch chainid coinbase constant constructor continue contract copyof days
default define delegatecall delete do ecrecover else emit enum ether event
external fallback false final finney fixed for from function gas gasleft gwei
hours if immutable implements import in indexed inline int interface internal
is keccak256 length let library log0 log1 log2 log3 log4 mapping match memory
minutes modifier msg mulmod new now of origin override payable pop pragma
private promise public pure push receive reference relocatable require return
returns revert ripemd160 seconds selfdestruct send sender sha256 sha3 static
staticcall storage string struct suicide super supports switch szabo this
throw timestamp transfer transient true try tx type typeof ufixed uint unchecked using
value var view virtual weeks wei while years
""".split()) | frozenset(
    ["uint%d" % i for i in range(8, 257, 8)] +
    ["int%d" % i for i in range(8, 257, 8)] +
    ["bytes%d" % i for i in range(1, 33)] +
    ["difficulty", "prevrandao", "basefee", "blobbasefee", "blobhash",
     "number", "gaslimit", "data", "sig", "code", "codehash",
     "encode", "encodePacked", "encodeWithSelector", "encodeWithSignature",
     "encodeCall", "decode", "selector", "creationCode", "runtimeCode",
     "interfaceId", "min", "max"])
DECLARATION_TYPES = frozenset((
    "variable_declaration", "state_variable_declaration", "parameter",
    "function_definition", "contract_declaration", "library_declaration",
    "interface_declaration", "struct_declaration", "enum_declaration",
    "event_definition", "event_paramater", "event_parameter",
    "modifier_definition", "error_declaration", "user_defined_type_definition",
))


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_marker(name):
    return any(marker in name for marker in MARKERS)


def token_ids(encoder, text, special_tokens=True):
    """Use the exact offline tokenizer, with truncation explicitly disabled."""
    tokenizer = getattr(encoder, "_tokenizer", encoder)
    return list(tokenizer(text, add_special_tokens=special_tokens,
                          truncation=False).input_ids)


def token_count(encoder, text):
    return len(token_ids(encoder, text, special_tokens=False))


def rewrite_node(code, mapping):
    """Generalized 8C span rewrite; C intentionally leaves marker names intact."""
    logical, offsets = serialized_view(code)
    edits = []
    for word, lo, hi in identifiers(logical):
        if word not in mapping:
            continue
        a, b = offsets[lo][0], offsets[hi - 1][1]
        if code[a:b] != word:
            raise ValueError("Identifier serialization is not an exact lexical span")
        edits.append((a, b, word, mapping[word]))
    pieces, end = [], 0
    for lo, hi, old, new in edits:
        pieces.extend((code[end:lo], new))
        end = hi
    pieces.append(code[end:])
    return "".join(pieces), edits


def marker_names(source):
    return list(dict.fromkeys(
        word for word, _, _ in identifiers(source) if is_marker(word)))


def declared_user_names(source):
    """Names with explicit declaration evidence, excluding builtins/globals.

    This is a lexical-name diagnostic, not alpha conversion or a binding/type
    checker. All occurrences of a selected spelling are rewritten consistently.
    A declaration does not override the conservative global/member exclusions.
    Parser acceptance is not Solidity compilation validation.
    """
    from scripts.DFG.frontend import parse, walk
    tree = parse(source)
    declarations = defaultdict(list)
    for node in walk(tree.root_node):
        if node.type not in DECLARATION_TYPES:
            continue
        name = node.child_by_field_name("name")
        if name is not None and name.type == "identifier":
            word = name.text.decode("utf-8")
            declarations[word].append(dict(
                role=node.type, start_byte=name.start_byte,
                end_byte=name.end_byte, line=name.start_point[0] + 1))
    ordered, rejected = [], {}
    for word, lo, hi in identifiers(source):
        if word in ordered or word in rejected:
            continue
        if word not in declarations:
            continue
        if is_marker(word):
            rejected[word] = "marker_identifier"
        elif word in EXCLUDED_NAMES:
            rejected[word] = "reserved_builtin_or_global_name"
        else:
            ordered.append(word)
    return dict(names=ordered, declarations=dict(declarations), rejected=rejected,
                policy="explicit AST declaration plus conservative builtin/global exclusions",
                compilation_verified=False, binding_scope="filewise lexical spelling")


def placebo_selection(source, encoder):
    """Strict C count and isolated token-length histogram matching."""
    required_names = marker_names(source)
    required = Counter(token_count(encoder, name) for name in required_names)
    user = declared_user_names(source)
    available = Counter(token_count(encoder, name) for name in user["names"])
    remaining, selected = dict(required), []
    for name in user["names"]:
        length = token_count(encoder, name)
        if remaining.get(length, 0):
            selected.append(name)
            remaining[length] -= 1
    shortages = {str(k): v for k, v in sorted(remaining.items()) if v}
    return dict(
        passed=not shortages, selected=selected,
        required_count=len(required_names), selected_count=len(selected),
        required_histogram={str(k): v for k, v in sorted(required.items())},
        available_histogram={str(k): v for k, v in sorted(available.items())},
        shortages=shortages, declaration_evidence={
            name: user["declarations"][name] for name in selected},
        exclusions=user["rejected"],
        policy=user["policy"],
        matching="unique filewise identifier spellings; exact isolated token count",
    )


class NeutralCandidates:
    """Fixed word list, deterministic enumeration; no performance-driven choice."""

    def __init__(self, encoder, suffixes=512, max_words=8):
        self.encoder = encoder
        self.suffixes, self.max_words = suffixes, max_words
        self.cache = {}
        self.built = False
        self.context_cache = {}

    def for_length(self, target):
        if not self.built:
            result = defaultdict(list)
            # Enumerate shorter word sequences first, then the fixed word order
            # and numeric suffix. Candidates contain none of the injected tags.
            for count in range(1, self.max_words + 1):
                for offset in range(len(WORDS)):
                    stem = "_".join(WORDS[(offset + i) % len(WORDS)]
                                    for i in range(count))
                    for suffix in range(self.suffixes):
                        for prefix in ("", "_", "__"):
                            name = prefix + stem + str(suffix)
                            result[token_count(self.encoder, name)].append(name)
            self.cache = dict(result)
            self.built = True
        return self.cache.get(target, ())

    def for_context(self, original):
        target = token_count(self.encoder, original)
        spaced = token_count(self.encoder, " " + original)
        dotted = token_count(self.encoder, "." + original)
        key = (target, spaced, dotted)
        if key not in self.context_cache:
            self.context_cache[key] = [name for name in self.for_length(target)
                if token_count(self.encoder, " " + name) == spaced
                and token_count(self.encoder, "." + name) == dotted]
        return self.context_cache[key]



def position_audit(code, mapping, encoder):
    """Prove edited occurrence token spans and all other token IDs stay fixed."""
    changed, edits = rewrite_node(code, mapping)
    tokenizer = getattr(encoder, "_tokenizer", encoder)
    before = tokenizer(code, add_special_tokens=True, truncation=False,
                       return_offsets_mapping=True)
    after = tokenizer(changed, add_special_tokens=True, truncation=False,
                      return_offsets_mapping=True)
    a, b = list(before.input_ids), list(after.input_ids)
    if len(a) != len(b):
        raise ValueError("Full node token count changed")
    def prepare_offsets(offsets):
        meaningful = [(i, s, e) for i, (s, e) in enumerate(offsets) if e > s]
        return ([i for i, s, e in meaningful], [s for i, s, e in meaningful], [e for i, s, e in meaningful])
    def overlapping(prepared, lo, hi):
        indices, starts, ends = prepared
        return indices[bisect.bisect_right(ends, lo):bisect.bisect_left(starts, hi)]
    old_offsets = prepare_offsets(before.offset_mapping)
    new_offsets = prepare_offsets(after.offset_mapping)
    touched, shift = set(), 0
    for lo, hi, old, new in edits:
        new_lo, new_hi = lo + shift, lo + shift + len(new)
        old_positions = overlapping(old_offsets, lo, hi)
        new_positions = overlapping(new_offsets, new_lo, new_hi)
        if old_positions != new_positions or not old_positions:
            raise ValueError("Edited occurrence changed token positions")
        touched.update(old_positions)
        shift += len(new) - len(old)
    if any(x != y for i, (x, y) in enumerate(zip(a, b)) if i not in touched):
        raise ValueError("Token outside edited identifier changed")
    return dict(full_token_count=len(a), edited_token_positions=len(touched),
                edited_occurrences=len(edits),
                unedited_token_ids_equal=True, occurrence_token_positions_equal=True)


def length_audit(node_codes, mapping, encoder):
    rows = []
    for identity, code in node_codes:
        changed, edits = rewrite_node(code, mapping)
        before = token_ids(encoder, code)
        after = token_ids(encoder, changed)
        if len(before) != len(after):
            raise ValueError("Full node token length differs at %r: %d -> %d" %
                             (identity, len(before), len(after)))
        positions = position_audit(code, mapping, encoder)
        rows.append(dict(node_identity=identity, position_proof=positions, before_length=len(before),
                         after_length=len(after), replacement_count=len(edits),
                         before_code_sha256=digest(code), after_code_sha256=digest(changed),
                         before_full_ids_sha256=digest(",".join(map(str, before))),
                         after_full_ids_sha256=digest(",".join(map(str, after))),
                         beyond_feature_window=len(before) > 512))
    return rows


def prepare_file(source, node_codes, encoder, mode="B", candidates=None, selected_names=None):
    """Create a deterministic map or fail, with no partial intervention accepted.

    node_codes is [(original_node_id, exact_serialized_code), ...]. All HCG rows
    of the file must be supplied; callers bind its frozen source/graph identity.
    """
    if mode not in ("B", "C", "B_full", "B_matched", "C_matched"):
        raise ValueError("Unknown intervention mode")
    node_codes = list(node_codes)
    if len({identity for identity, _ in node_codes}) != len(node_codes):
        raise ValueError("Duplicate node identity")
    all_names = {word for word, _, _ in identifiers(source)}
    selection = None
    names = marker_names(source)
    if mode == "C":
        selection = placebo_selection(source, encoder)
        if not selection["passed"]:
            raise ValueError("C exact count/length matching is infeasible: %r" %
                             selection["shortages"])
        names = selection["selected"]
    if mode in ("B_matched", "C_matched"):
        if selected_names is None or len(set(selected_names)) != len(selected_names):
            raise ValueError("Matched view requires unique explicit selected names")
        names = list(selected_names)
        allowed = set(marker_names(source)) if mode == "B_matched" else set(declared_user_names(source)["names"])
        if not set(names).issubset(allowed):
            raise ValueError("Matched selection contains ineligible names")
    elif selected_names is not None:
        raise ValueError("Explicit subset only allowed in matched views")
    inventory = {word for _, code in node_codes
                 for word, _, _ in identifiers(serialized_view(code)[0])}
    unknown_markers = sorted(name for name in inventory if is_marker(name) and name not in all_names)
    if unknown_markers:
        raise ValueError("Node marker absent from bound source: %r" % unknown_markers)
    candidates = candidates or NeutralCandidates(encoder)
    mapping, accepted, used = {}, [], set(all_names)
    by_name = defaultdict(list)
    original_lengths = {}
    for identity, code in node_codes:
        original_lengths[code] = len(token_ids(encoder, code))
        for name in {w for w, _, _ in identifiers(serialized_view(code)[0])}:
            by_name[name].append((identity, code))
    # Verify each candidate against all affected full node strings. Earlier
    # edits are checked independently here; the final all-name audit additionally
    # rejects interaction/cancellation or any shifted unaffected token.
    for name in names:
        target = token_count(encoder, name)
        affected = by_name.get(name, [])
        found = None
        attempts = 0
        for candidate in candidates.for_context(name):
            if candidate in used or candidate in EXCLUDED_NAMES or is_marker(candidate):
                continue
            attempts += 1
            trial = dict(mapping)
            trial[name] = candidate
            try:
                for _, code in affected:
                    position_audit(code, {name: candidate}, encoder)
            except ValueError:
                continue
            found = candidate
            break
        if found is None:
            raise ValueError("No neutral whole-node length-preserving candidate for " + name)
        mapping[name] = found
        used.add(found)
        accepted.append(dict(original=name, neutral=found,
                             original_token_count=target,
                             neutral_token_count=token_count(encoder, found),
                             candidate_attempts=attempts, affected_nodes=len(affected)))
    audit = length_audit(node_codes, mapping, encoder)
    return dict(algorithm=ALGORITHM, mode=mode, source_sha256=digest(source),
                mapping=mapping, identifiers=accepted, nodes=audit,
                changed_node_count=sum(row["replacement_count"] > 0 for row in audit),
                declaration_selection=selection, full_token_length_preserved=True,
                fixed_word_list=list(WORDS), candidate_suffixes=candidates.suffixes,
                candidate_max_words=candidates.max_words,
                candidate_prefixes=["", "_", "__"],
                check_uses_untruncated_ids=True, feature_dimension_not_a_length_check=True)


def matched_selection(source, encoder):
    """User-approved rigorous subset: both sides share exact length histogram."""
    full = marker_names(source)
    user = declared_user_names(source)
    marker_by_length, other_by_length = defaultdict(list), defaultdict(list)
    for name in full:
        marker_by_length[token_count(encoder, name)].append(name)
    for name in user["names"]:
        other_by_length[token_count(encoder, name)].append(name)
    counts = {length: min(len(names), len(other_by_length[length]))
              for length, names in marker_by_length.items()}
    marker_set = {name for length, count in counts.items()
                  for name in marker_by_length[length][:count]}
    other_set = {name for length, count in counts.items()
                 for name in other_by_length[length][:count]}
    markers = [name for name in full if name in marker_set]
    others = [name for name in user["names"] if name in other_set]
    pairs = []
    for length in sorted(counts):
        for marker, other in zip(marker_by_length[length][:counts[length]],
                                 other_by_length[length][:counts[length]]):
            pairs.append(dict(marker=marker, nonmarker=other, token_count=length))
    a = Counter(token_count(encoder, name) for name in markers)
    b = Counter(token_count(encoder, name) for name in others)
    if a != b or len(markers) != len(others):
        raise AssertionError("Matched count/length histograms disagree")
    return dict(
        marker_names=markers, nonmarker_names=others, pairs=pairs,
        matched_count=len(markers), full_marker_count=len(full),
        matched_histogram={str(k): v for k, v in sorted(a.items())},
        unmatched_marker_names=[name for name in full if name not in marker_set],
        strict_full_selection=placebo_selection(source, encoder),
        declaration_evidence={name: user["declarations"][name] for name in others},
        ordering="first source occurrence independently within each token-length stratum",
        zero_matched_file_retained=not markers,
    )


def prepare_bundle_file(source, node_codes, encoder, candidates=None):
    """CPU-only preflight for all three approved views; no model forward."""
    node_codes = list(node_codes)
    candidates = candidates or NeutralCandidates(encoder)
    matching = matched_selection(source, encoder)
    views = {}
    print("  prepare B_full markers=%d" % matching["full_marker_count"], flush=True)
    views["B_full"] = prepare_file(
        source, node_codes, encoder, mode="B_full", candidates=candidates)
    print("  prepare B_matched count=%d" % matching["matched_count"], flush=True)
    views["B_matched"] = prepare_file(
        source, node_codes, encoder, mode="B_matched", candidates=candidates,
        selected_names=matching["marker_names"])
    print("  prepare C_matched count=%d" % matching["matched_count"], flush=True)
    views["C_matched"] = prepare_file(
        source, node_codes, encoder, mode="C_matched", candidates=candidates,
        selected_names=matching["nonmarker_names"])
    return dict(algorithm=ALGORITHM, source_sha256=digest(source),
                matching=matching, views=views)


def prepare_all(plan_path, output):
    """Freeze all SolidiFI file maps once; readers verify these SHA-bound files."""
    import pickle
    import re
    import time
    from pathlib import Path
    from scripts.DFG.dfg_v2.diagnostics8c.common import checked_plan, write_new
    from scripts.DFG.integration.io import checked, sha256
    from scripts.DFG.dfg_v2.tokens import TokenEncoder
    plan = checked_plan(plan_path)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    encoder = None
    candidates = None
    files, totals, tokenizers = {}, Counter(), {}
    for task_id, task in plan["tasks"].items():
        record = task["record"]
        if record["task"] != "node":
            continue
        encoder = TokenEncoder(record["feature"])
        candidates = NeutralCandidates(encoder)
        feature = record["feature"]
        tokenizers[task_id] = encoder.provenance
        graph_ref = record["original_graph"]
        checked(graph_ref["path"], graph_ref["sha256"])
        with open(graph_ref["path"], "rb") as stream:
            graph = pickle.load(stream)
        node_codes = defaultdict(list)
        for identity, attrs in graph.nodes(data=True):
            node_codes[attrs["source_file"]].append((identity, attrs["code"]))
        files[task_id] = {}
        for filename in sorted(record["sources"]):
            if not re.fullmatch(r"buggy_\d+\.sol", filename):
                continue
            ref = record["sources"][filename]
            checked(ref["path"], ref["sha256"])
            source = Path(ref["path"]).read_text(encoding="utf-8")
            bundle = prepare_bundle_file(source, node_codes[filename], encoder, candidates)
            bundle.update(task_id=task_id, filename=filename, source=ref, graph=graph_ref,
                          feature=feature)
            path = output / task_id / (filename + ".json")
            write_new(path, bundle)
            files[task_id][filename] = dict(path=str(path.resolve()), sha256=sha256(path))
            totals["files"] += 1
            totals["nodes"] += len(node_codes[filename])
            totals["full_marker_names"] += bundle["matching"]["full_marker_count"]
            totals["matched_names_each_side"] += bundle["matching"]["matched_count"]
            totals["full_matching_failures"] += not bundle["matching"]["strict_full_selection"]["passed"]
            for mode, view in bundle["views"].items():
                totals[mode + "_changed_nodes"] += view["changed_node_count"]
            print("renaming preflight %s/%s: full=%d, matched=%d" %
                  (task_id, filename, bundle["matching"]["full_marker_count"],
                   bundle["matching"]["matched_count"]), flush=True)
    summary = dict(algorithm=ALGORITHM, files=files,
                   tasks={task: dict(files=records) for task, records in files.items()}, totals=dict(totals),
                   plan=dict(path=str(Path(plan_path).resolve()), sha256=sha256(plan_path)),
                   tokenizers=tokenizers, seconds=time.monotonic() - started,
                   training_count=0, forward_count=0,
                   all_untruncated_lengths_equal=True,
                   all_unedited_token_ids_equal=True,
                   all_edited_occurrence_token_positions_equal=True,
                   matching_approval="Prompt8D user-approved rigorous equal-count token-length matched subset")
    write_new(output / "preflight_summary.json", summary)
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    prepare_all(args.plan, args.out)
