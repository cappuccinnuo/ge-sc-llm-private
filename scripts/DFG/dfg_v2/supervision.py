"""File-based supervision for the fixed v2 graph.

Adapted from scripts/DFG/experiments/paper_runtime.py::Supervision.
Source SHA256: 319159bec961320307083f63dea2f4fb5eed3559db401c542bcd0af6eca6218e
Node supervision additionally excludes auxiliary nodes. Contract supervision
keeps the original file-batch interface; model construction filters pool rows.
G0 parity against the original class is covered in test_model.py.
"""
import torch

from scripts.DFG.experiments.common import digest
from scripts.DFG.experiments.paper_runtime import FORWARD_SCOPE
from . import AUX_NODE_TYPES
from .model import validate_registration


class DfgV2Supervision:
    def __init__(self, model, task, files):
        if task not in ("node", "contract") or task != model.dfg_task:
            raise ValueError("Supervision task does not match model")
        self.task, self.files = task, sorted(files)
        selected = set(self.files)
        if len(selected) != len(self.files):
            raise ValueError("Duplicate supervised files")
        population = {d["source_file"] for _, d in model.nx_graph.nodes(data=True)
                      if d["node_type"] not in AUX_NODE_TYPES}
        if not selected or not selected <= population:
            raise ValueError("Absent/empty supervised files")
        included = [d["source_file"] in selected and
                    (task != "node" or d["node_type"] not in AUX_NODE_TYPES)
                    for _, d in model.nx_graph.nodes(data=True)]
        self.full_ids = [n for (n, _), include in zip(model.nx_graph.nodes(data=True), included) if include]
        self.mask = torch.tensor(included, dtype=torch.bool, device=model.device)
        self.manifest = {"task": task, "files": self.files, "model_node_ids": self.full_ids,
                         "forward_scope": FORWARD_SCOPE,
                         "supervision": "node_mask" if task == "node" else "file_batch"}
        self.manifest["sha256"] = digest(self.manifest)

    def targets(self, model, graph_labels):
        values = [model.node_labels[n] for n in self.full_ids] if self.task == "node" else [graph_labels[f] for f in self.files]
        return torch.tensor(values, dtype=torch.long, device=model.device)

    def forward(self, model):
        validate_registration(model, deep=False)
        return model()[self.mask] if self.task == "node" else model(self.files)[0]
