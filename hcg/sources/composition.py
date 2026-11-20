"""Composed corpora: a committed list of which source files make up each category.

Dataset A's corpus is checked into the repository. A composed dataset (Dataset B)
is instead described by a composition document committed next to the registry
(``hcg/datasets/dataset_b.json``): for every category, every contract with its
corpus name, source, path inside the pinned source checkout (``origin``), SHA-256
and 0/1 target, plus the candidates left out and why. ``assemble`` copies exactly
those files into the corpus directory (git-ignored) and checks every hash, so a
build always sees the committed selection, whatever machine it runs on.

Copies are written with LF line endings (``normalize``), as the authors' Dataset A
corpus holds the SmartBugs Wild pool files (which are CRLF); the HCG node text and
the DFG/NodeSem source views must agree byte for byte.

Row fields: ``name``, ``source`` (DAppSCAN | SolidiFI | SmartBugs-Wild-clean),
``origin``, ``origin_sha256`` (the source file), ``sha256`` (the corpus copy),
``target``; DAppSCAN rows also ``labels`` (the line-label
files: its own and those of identical copies left out) and ``swc`` (the category's SWC
ids its labels carry).
"""
import hashlib
import json
from pathlib import Path

VERSION = "hcg-composition-v1"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize(data):
    """The corpus copy of a source file's bytes: CRLF line endings become LF."""
    return data.replace(b"\r\n", b"\n")


def load(path):
    document = json.loads(Path(path).read_text(encoding="utf8"))
    if document.get("version") != VERSION:
        raise SystemExit("%s is not a %s document" % (path, VERSION))
    return document


def entries(document, category):
    try:
        return document["categories"][category]["contracts"]
    except KeyError:
        raise SystemExit("composition has no category %r" % category) from None


def assemble(document, category, label_root, corpus_dir):
    """Make ``corpus_dir`` hold exactly the category's files; return their names."""
    corpus_dir = Path(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    rows = entries(document, category)
    names = {row["name"] for row in rows}
    if len(names) != len(rows):
        raise ValueError("composition of %s repeats a corpus name" % category)
    for stray in corpus_dir.glob("*.sol"):
        if stray.name not in names:
            stray.unlink()
    for row in rows:
        target = corpus_dir / row["name"]
        if target.is_file() and _sha(target) == row["sha256"]:
            continue
        origin = Path(label_root) / row["origin"]
        if not origin.is_file():
            raise SystemExit("%s is missing; run: python -m hcg fetch --dataset %s"
                             % (origin, document["dataset"]))
        data = origin.read_bytes()
        if hashlib.sha256(data).hexdigest() != row["origin_sha256"]:
            raise ValueError("%s does not match its composition hash" % origin)
        copy = normalize(data)
        if hashlib.sha256(copy).hexdigest() != row["sha256"]:
            raise ValueError("the corpus copy of %s does not match its composition hash" % origin)
        target.write_bytes(copy)
    return sorted(names)


def targets(document, category):
    return {row["name"]: int(row["target"]) for row in entries(document, category)}
