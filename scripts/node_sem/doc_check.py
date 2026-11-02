"""UTF-8 and newly written prose validation, outside the training runtime.

The caller explicitly declares Chinese prose with expect_cjk / --expect-cjk;
English headings cannot reveal whether Chinese was intended. Byte offsets refer
to the file BEFORE an append, and never suppress full-file UTF-8 validation.
"""
import argparse
import json
from pathlib import Path
import re
import sys


def _is_cjk(char):
    value = ord(char)
    return (0x3400 <= value <= 0x4DBF or 0x4E00 <= value <= 0x9FFF
            or 0xF900 <= value <= 0xFAFF or 0x20000 <= value <= 0x3134F)


def check(path, since_bytes=None, expect_cjk=False):
    """Raise ValueError on corruption; return a small JSON-safe check record."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("File is not strict UTF-8: {}".format(path)) from exc
    start = 0 if since_bytes is None else since_bytes
    if type(start) is not int or not 0 <= start <= len(raw):
        raise ValueError("since_bytes must be a valid nonnegative byte offset")
    try:
        fresh = raw[start:].decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("since_bytes splits a UTF-8 character") from exc
    if re.search(r"\?{3,}", fresh):
        raise ValueError("New content contains a run of at least three question marks")
    if "\ufffd" in fresh:
        raise ValueError("New content contains a Unicode replacement character")
    cjk = sum(_is_cjk(char) for char in fresh)
    if expect_cjk and not cjk:
        raise ValueError("Declared Chinese content contains no CJK characters")
    return dict(path=str(path),since_bytes=start,total_bytes=len(raw),
                checked_bytes=len(raw)-start,utf8=True,cjk_characters=cjk,
                expect_cjk=bool(expect_cjk),passed=True)


def parse_target(value):
    # A drive colon in C:\folder\file.md is not an append offset.
    path, separator, suffix = value.rpartition(":")
    if separator and path and re.fullmatch(r"-?[0-9]+", suffix):
        return path, int(suffix)
    return value, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-cjk", action="store_true",
                        help="Require CJK in each file's checked portion")
    parser.add_argument("targets", nargs="+", metavar="PATH[:SINCE_BYTES]")
    args = parser.parse_args(argv)
    failed = False
    for target in args.targets:
        path, offset = parse_target(target)
        try:
            result = check(path, offset, expect_cjk=args.expect_cjk)
        except (OSError, ValueError) as exc:
            result = dict(path=path,passed=False,error=str(exc))
            failed = True
        print(json.dumps(result, ensure_ascii=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
