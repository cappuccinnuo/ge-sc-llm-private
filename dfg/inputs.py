"""HCG outputs -> per-task DFG inputs: graph, exact sources, version metadata, token encoder.

A *task* is one graph of one category built by ``python -m hcg build``:

* ``<category>_contract``: ``contract_level.gpickle`` (all contracts),
* ``<category>_node``: ``line_level.gpickle`` (vulnerable contracts, node labels).

Sources are read as raw UTF-8 bytes (CRLF and all coordinates preserved). Version
metadata is attached only where the dataset records a compiled version for a byte-
identical copy of the file: SmartBugs-curated ``versions.csv``, row
``dataset/<category>/<file>``. Every other file falls back to its pragma.
"""
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from hcg.datasets.registry import get_dataset
from hcg.features.tokens import REVISION, TOKENIZER, WIDTH, encode_ids, load_tokenizer, pad_id
from hcg.store.io import read_gpickle, sha256

REPO = Path(__file__).resolve().parents[1]
TASKS = {"contract": "contract_level.gpickle", "node": "line_level.gpickle"}
VERSIONS_REPO = "smartbug-dataset"


@dataclass
class TaskInput:
    task_id: str
    dataset: str
    category: str
    task: str            # "contract" or "node"
    graph_path: Path
    graph: object
    sources: dict        # file name -> exact source text
    metadata: dict       # file name -> version record or None


def task_id(category, task):
    return category + "_" + task


def hcg_dir(hcg_root, dataset, category):
    return Path(hcg_root) / dataset / category


def version_records(dataset, category, files, label_root):
    """Recorded compiler versions for files whose SmartBugs copy is byte-identical."""
    root = Path(label_root) / VERSIONS_REPO
    table = root / "versions.csv"
    if not table.is_file():
        raise FileNotFoundError("versions.csv not found; run `python -m hcg fetch`: " + str(table))
    with table.open(encoding="utf8", newline="") as stream:
        rows = {row["file"]: row["compiled version"] for row in csv.DictReader(stream)}
    corpus = get_dataset(dataset).corpus(REPO, category)
    table_sha = sha256(table)
    records = {}
    for name in files:
        row = "dataset/%s/%s" % (category, name)
        candidate = root / row
        if row not in rows or not candidate.is_file():
            continue
        digest = sha256(candidate)
        if digest != sha256(corpus / name):
            continue
        records[name] = dict(csv_path=str(table.resolve()), csv_sha256=table_sha,
                             source_path=str(candidate.resolve()), source_sha256=digest,
                             row_file=row, version=rows[row])
    return records


def load_task(hcg_root, dataset, category, task, label_root):
    """Load one task's original HCG with its sources and version metadata."""
    if task not in TASKS:
        raise ValueError("task must be one of %s" % sorted(TASKS))
    path = hcg_dir(hcg_root, dataset, category) / TASKS[task]
    if not path.is_file():
        raise FileNotFoundError("HCG graph missing; run `python -m hcg build`: " + str(path))
    graph = read_gpickle(path)
    files = sorted({data["source_file"] for _, data in graph.nodes(data=True)})
    corpus = get_dataset(dataset).corpus(REPO, category)
    sources = {name: (corpus / name).read_bytes().decode("utf8") for name in files}
    metadata = {name: None for name in files}
    metadata.update(version_records(dataset, category, files, label_root))
    return TaskInput(task_id(category, task), dataset, category, task, path, graph, sources, metadata)


class TokenEncoder:
    """Node feature for auxiliary ``env_source`` nodes; same recipe as HCG node tokens."""

    def __init__(self, tokenizer=None):
        self._tokenizer = tokenizer if tokenizer is not None else load_tokenizer()
        self._pad = pad_id(self._tokenizer)
        self.provenance = dict(model=TOKENIZER, revision=REVISION, width=WIDTH, scheme="ids",
                               add_special_tokens=True, padding_id=self._pad)

    def __call__(self, code):
        if not isinstance(code, str):
            raise TypeError("TokenEncoder requires code text")
        ids = self._tokenizer(code, add_special_tokens=True).input_ids
        return encode_ids(ids, WIDTH, self._pad)


def has_tokens(graph):
    for _, data in graph.nodes(data=True):
        token = data.get("token")
        return isinstance(token, np.ndarray) and token.shape == (WIDTH,)
    return False
