"""What the benchmark trains for one category under one protocol, and the training.

| track      | dfg task   | graph                  | fitted / validated on            | scored on                  |
|------------|------------|------------------------|----------------------------------|----------------------------|
| `contract` | `contract` | `contract_level`       | contracts                        | held-out contracts         |
| `line`     | `node`     | `line_level`           | nodes of vulnerable contracts    | their held-out nodes       |
| `cascade`  | `node`     | `contract_level`       | nodes of vulnerable contracts    | nodes of every held-out contract |

`contract` and `line` are the paper's two experiments (Tables 3 and 5). `cascade` is
the line model of the two-phase detector (paper Sec. 4.5): trained like `line`, but on
the contract plan's folds and scored on every held-out contract, so that
``benchmark.evaluate`` can gate it with the `contract` model of the same fold.

Fits run through ``dfg.train.runner.run_task`` unchanged: profile G0 is the
MANDO-LLM HGT on the hcg graphs (CodeT5+ token features), other DFG profiles need
``python -m dfg build``. Results land in ``<out>/<protocol>/<category>_<track>/``.

``labels="author"`` (Dataset A) trains on the authors' released node labels instead
of the public-annotation ones (``benchmark.audit.transplant``): the only change.
"""
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from benchmark import audit
from benchmark import folds as plans
from dfg.train.runner import TaskData, run_task
from hcg.store.io import sha256

REPO = Path(__file__).resolve().parents[1]
PROTOCOLS = ("paper", "grouped")
TRACKS = ("contract", "line", "cascade")
LABELS = ("public", "author")


@dataclass(frozen=True)
class Roots:
    hcg: Path
    dfg: Path
    label_root: Path


class Track:
    """One trained unit: the interface ``run_task`` reads (task, task_id, folds, graphs)."""

    def __init__(self, category, name, protocol, source, folds, labels="public"):
        if name not in TRACKS or protocol not in PROTOCOLS or labels not in LABELS:
            raise ValueError("unknown track %r, protocol %r or labels %r" % (name, protocol, labels))
        self.category, self.name, self.protocol = category, name, protocol
        self.task = "contract" if name == "contract" else "node"
        self.task_id = "%s_%s" % (category, name)
        self.folds, self._source = folds, source
        self.file_labels = source.file_labels
        self.feature_summary = source.feature_summary
        self.groups = source.groups
        self.labels, self._relabelled = labels, {}

    def graph(self, profile):
        graph = self._source.graph(profile)
        if self.labels == "public" or self.task == "contract":
            return graph                       # contract targets are the same under both
        if profile not in self._relabelled:
            reference = audit.author_graph(self.category, "contract" if self.name == "cascade" else "node")
            self._relabelled[profile] = audit.transplant(graph, reference)[0]
        return self._relabelled[profile]


class CategoryData:
    """The contract- and line-level task data of one category (graphs, labels, grouped folds)."""

    def __init__(self, dataset, category, roots, log=print):
        self.category = category
        self.contract = TaskData(dataset, category, "contract", roots.hcg, roots.dfg, roots.label_root, log=log)
        self.line = TaskData(dataset, category, "node", roots.hcg, roots.dfg, roots.label_root, log=log)

    def tracks(self, protocol, seed=1, labels="public", names=TRACKS):
        c = self.category
        if protocol == "paper":
            contract_plan = plans.paper_contract(c + "_contract", self.contract.file_labels, seed)
            line_plan = plans.paper_line(c + "_line", self.line.folds["files"], seed)
        elif protocol == "grouped":
            contract_plan, line_plan = self.contract.folds, self.line.folds
        else:
            raise ValueError("unknown protocol " + protocol)
        if contract_plan["files"] != sorted(self.contract.file_labels):
            raise ValueError("%s: contract graph and graph_labels.json list different contracts" % c)
        cascade_plan = plans.cascade(c + "_cascade", contract_plan, self.contract.file_labels)
        built = [Track(c, "contract", protocol, self.contract, contract_plan, labels),
                 Track(c, "line", protocol, self.line, line_plan, labels),
                 Track(c, "cascade", protocol, self.contract, cascade_plan, labels)]
        return [t for t in built if t.name in names]


def train(tracks, out_root, profiles=("G0",), folds=None, seed=1, device="cpu",
          config_overrides=None, log=print):
    """Fit every (track, fold, profile) not done yet; ``folds`` filters fold indices."""
    for track in tracks:
        chosen = None if folds is None else [k for k in folds if k < track.folds["k_folds"]]
        log("[%s] %s: %d folds" % (track.protocol, track.task_id,
                                   track.folds["k_folds"] if chosen is None else len(chosen)))
        run_task(track, Path(out_root) / track.protocol, profiles, chosen, seed, device,
                 config_overrides, save_checkpoints=False, log=log)


def run_manifest(out_root, dataset, categories, roots, settings):
    """Record what a run was built from; refuse to extend a run made from other graphs."""
    graphs = {}
    for category in categories:
        manifest = Path(roots.hcg) / dataset / category / "manifest.json"
        graphs[category] = dict(manifest_sha256=sha256(manifest),
                                outputs=json.loads(manifest.read_text())["output_sha256"])
    document = dict(dataset=dataset, settings=settings, hcg=graphs, commit=_commit())
    path = Path(out_root) / "run.json"
    if path.is_file():
        old = json.loads(path.read_text())
        if old["settings"].get("labels", "public") != settings.get("labels", "public"):
            raise ValueError("%s was trained on %s labels; use another --out"
                             % (out_root, old["settings"].get("labels", "public")))
        for category, built in graphs.items():
            if category in old["hcg"] and old["hcg"][category]["outputs"] != built["outputs"]:
                raise ValueError("%s: %s was trained on other hcg graphs; use another --out"
                                 % (out_root, category))
        old["hcg"].update(graphs)
        old.setdefault("history", []).append(dict(settings=settings, commit=document["commit"]))
        document = old
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n")
    return document


def _commit():
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
