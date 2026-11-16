"""Pickle/JSON I/O and the per-category output layout.

Graphs are written with pickle protocol 4 so the legacy Python 3.7 environment can
still load them (protocol 5, used by the authors' files, needs Python 3.8+).
networkx 3 removed read_gpickle/write_gpickle; these are the same thin wrappers.
"""
import hashlib
import json
import pickle
from dataclasses import dataclass
from pathlib import Path

PROTOCOL = 4


def read_gpickle(path):
    with open(path, "rb") as handle:
        return pickle.load(handle)


def write_gpickle(obj, path, protocol=PROTOCOL):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(obj, handle, protocol=protocol)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


@dataclass(frozen=True)
class CategoryOutput:
    """Files written for one category: <root>/<dataset>/<category>/..."""
    directory: Path

    @property
    def contract_level(self):
        return self.directory / "contract_level.gpickle"

    @property
    def line_level(self):
        return self.directory / "line_level.gpickle"

    @property
    def graph_labels(self):
        return self.directory / "graph_labels.json"

    @property
    def annotations(self):
        return self.directory / "annotations.json"

    @property
    def line_node_ids(self):
        return self.directory / "line_node_ids.json"

    @property
    def manifest(self):
        return self.directory / "manifest.json"
