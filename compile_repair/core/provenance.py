"""PROMPTS 3.7/4.3: replayable byte edits, compact offset maps and node marks.

Patch ranges refer to the current copy at that round. Equal-size rewrites retain
positional correspondence; deleted/replaced unequal-size bytes have no mapping.
"""
import hashlib
from compile_repair.core.model import Change, Patch, Provenance, Segment


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def apply_patches(original, patches):
    """Apply ordered, preimage-checked byte patches; return copy and provenance.

    Reject non-byte content, invalid ranges or stale expected bytes. Insertions
    retain all original bytes; any nonempty replacement/deletion is a rewrite.
    """
    if not isinstance(original, bytes):
        raise TypeError("Source content must be bytes")
    current, origins, kinds, changes = original, list(range(len(original))), ["original"] * len(original), []
    for patch in patches:
        if not isinstance(patch.expected, bytes) or not isinstance(patch.replacement, bytes):
            raise TypeError("Patch contents must be bytes")
        a, b = patch.start, patch.end
        if not 0 <= a <= b <= len(current) or current[a:b] != patch.expected:
            raise ValueError("Patch range/preimage does not match the current copy")
        if patch.expected == patch.replacement:
            continue
        kind = "added" if a == b else "rewritten"
        new_origins = origins[a:b] if b - a == len(patch.replacement) else [None] * len(patch.replacement)
        origins[a:b] = new_origins
        kinds[a:b] = [kind] * len(patch.replacement)
        current = current[:a] + patch.replacement + current[b:]
        changes.append(Change(a, b, patch.expected, patch.replacement, patch.step, patch.round, patch.reason))
    segments = []
    start = 0
    while start < len(current):
        end = start + 1
        while end < len(current) and kinds[end] == kinds[start] and (
                origins[start] is None and origins[end] is None or
                origins[start] is not None and origins[end] == origins[start] + end - start):
            end += 1
        old = origins[start]
        segments.append(Segment(start, end, old, None if old is None else old + end - start, kinds[start]))
        start = end
    level = "rewrite" if any(c.end > c.start for c in changes) else "additive" if changes else "none"
    evidence = Provenance(_sha(original), _sha(current), len(original), len(current), level,
                          tuple(changes), tuple(segments))
    return current, evidence


def check_additive(original, current, provenance):
    """Verify every original byte occurs unchanged and in order via the map.

    Return False on changed, duplicated, missing or reordered original bytes;
    this checks provenance, not just whether the original is a subsequence.
    """
    expected = 0
    for span in provenance.segments:
        if span.kind == "added":
            if span.original_start is not None:
                return False
            continue
        if span.kind != "original" or span.original_start != expected:
            return False
        if current[span.new_start:span.new_end] != original[span.original_start:span.original_end]:
            return False
        expected = span.original_end
    return expected == len(original)


def verify_provenance(original, current, provenance):
    """Replay all edits and compare bytes AND maps; raise on unexplained change."""
    patches = [Patch(c.start, c.end, c.old, c.new, c.step, c.round, c.reason) for c in provenance.changes]
    replay, expected = apply_patches(original, patches)
    if replay != current or expected != provenance:
        raise ValueError("Working copy/provenance mismatch")
    if provenance.level in ("none", "additive") and not check_additive(original, current, provenance):
        raise ValueError("Original bytes were not preserved")
    return True


def original_to_new(provenance, offset):
    """Map an original byte to the copy; return None if an unequal rewrite removed it."""
    if not 0 <= offset < provenance.original_length:
        raise ValueError("Original byte offset outside source")
    for span in provenance.segments:
        if span.original_start is not None and span.original_start <= offset < span.original_end:
            return span.new_start + offset - span.original_start
    return None


def mark_span(provenance, start, length):
    """Classify a valid byte span; mixed kinds or a deleted-byte join are rewritten.

    Zero-length nodes use the byte at start, or the preceding byte at EOF. Empty
    unchanged source is original. Invalid/missing offsets fail explicitly.
    """
    if not isinstance(start, int) or not isinstance(length, int) or start < 0 or length < 0 or start + length > provenance.result_length:
        raise ValueError("Node span outside working copy")
    if provenance.result_length == 0:
        return "original" if provenance.level == "none" else "rewritten"
    end = start + length
    if length == 0:
        start = min(start, provenance.result_length - 1)
        end = start + 1
    spans = [s for s in provenance.segments if s.new_start < end and start < s.new_end]
    kinds = {s.kind for s in spans}
    if len(kinds) != 1:
        return "rewritten"
    if kinds == {"original"} and any(a.original_end != b.original_start for a, b in zip(spans, spans[1:])):
        return "rewritten"
    return next(iter(kinds))


def compose_offsets(original, damaged, repaired, damage, repair):
    """Compose two verified byte maps, including byte-exact restorations between matching anchors.

    Return ordered segments in repaired coordinates. A restored interval has original
    coordinates; unrelated insertions remain unmapped even if they contain the same bytes.
    These scoring segments do not change either original patch log or its change level.
    """
    verify_provenance(original, damaged, damage)
    verify_provenance(damaged, repaired, repair)
    anchors = []
    for second in repair.segments:
        if second.original_start is None:
            continue
        for first in damage.segments:
            if first.original_start is None:
                continue
            lo = max(first.new_start, second.original_start)
            hi = min(first.new_end, second.original_end)
            if lo >= hi:
                continue
            old = first.original_start + lo - first.new_start
            new = second.new_start + lo - second.original_start
            size = hi - lo
            kind = "original" if first.kind == second.kind == "original" else "rewritten"
            if kind == "rewritten" and original[old:old+size] == repaired[new:new+size]:
                kind = "restored"
            anchors.append(Segment(new, new+size, old, old+size, kind))

    result = []
    old_end = new_end = 0
    # The sentinel supplies the right boundary for terminal or whole-file deletions.
    for span in anchors + [Segment(len(repaired), len(repaired), len(original), len(original), "end")]:
        old_start, new_start = span.original_start, span.new_start
        if new_start > new_end:
            bounded_left = old_end == new_end == 0 or (
                old_end > 0 and new_end > 0 and original[old_end-1] == repaired[new_end-1])
            bounded_right = old_start == len(original) and new_start == len(repaired) or (
                old_start < len(original) and new_start < len(repaired) and original[old_start] == repaired[new_start])
            exact = (bounded_left and bounded_right and old_start-old_end == new_start-new_end
                     and original[old_end:old_start] == repaired[new_end:new_start])
            result.append(Segment(new_end, new_start, old_end if exact else None,
                                  old_start if exact else None, "restored" if exact else "added"))
        if span.kind != "end":
            result.append(span)
        old_end, new_end = span.original_end, span.new_end
    return tuple(result)
