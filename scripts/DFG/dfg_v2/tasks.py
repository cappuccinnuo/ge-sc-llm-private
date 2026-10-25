"""Frozen category registry and reproducible file-level nested folds.

Prompt 5: references are pinned, never inferred by replacing path names.
source_metadata_manifest is required because the historical task manifest does
not embed the later verified version metadata used by L1/L2/L3.
"""
import copy
import re
from pathlib import Path

from scripts.DFG.integration.io import checked, read_json
from scripts.DFG.experiments.protocol import make_fold_document, validate_fold_document
from scripts.labeling_v2.safe_graph import read_graph

# Future categories are deliberately not registered:
# arithmetic, denial_of_service, front_running, time_manipulation,
# unchecked_low_level_calls.
REGISTRY = {'access_control': {'category': 'access_control',
                    'tasks': {'contract': {'folds': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/splits/contract_folds.json',
                                                     'sha256': '090cb6ae49e2f77894750c2c42e1952d3ff17a681b8238d84e2eb03fb6ba965f'},
                                           'labels': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/graph_labels.json',
                                                      'sha256': '6002778325eca7b981f3a1f996a31c34ccfa1d83b5166d3c28ee37c974384649'},
                                           'prepared_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/manifest.json',
                                                                 'sha256': '53d260f9d5fbc8cc05bb12e07bfc482b846a4ad83d2b916e06c0df7a58621e1e'},
                                           'source_metadata_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build/access_control_author_contract/sources.json',
                                                                        'sha256': 'c325e8b58ac1378f1bd04d3e38a9c6240fbce6ee672583627a7760d1d3987a82'},
                                           'source_task_id': 'access_control_author_contract',
                                           'source_task_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/prepared/access_control_author_contract/fold_0/task.json',
                                                                    'sha256': 'c048af31d664c456beb93b6465cddfb430f07226536fcb4e3c220d7a07175003'}},
                              'node': {'folds': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/splits/node_folds.json',
                                                 'sha256': '201a668dbfb4319ae373f8452ceb9e12b54aa909c62a080e3fae820b8e9039eb'},
                                       'labels': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/graph_labels.json',
                                                  'sha256': '6002778325eca7b981f3a1f996a31c34ccfa1d83b5166d3c28ee37c974384649'},
                                       'prepared_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/manifest.json',
                                                             'sha256': '53d260f9d5fbc8cc05bb12e07bfc482b846a4ad83d2b916e06c0df7a58621e1e'},
                                       'source_metadata_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build/access_control_author_node/sources.json',
                                                                    'sha256': '40e97cc7351ab127eda3e5f0272100aba473bd3aca1fe80c836f4ec62cf681a4'},
                                       'source_task_id': 'access_control_author_node',
                                       'source_task_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/prepared/access_control_author_node/fold_0/task.json',
                                                                'sha256': '9b86577f58240af3e022391ef54e7dda77053f25c7e5727c3bf2ff7cd2577b61'}}}},
 'reentrancy': {'category': 'reentrancy',
                'tasks': {'contract': {'folds': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/splits/contract_folds.json',
                                                 'sha256': 'd679dfbdd78b510167063de23e8e1dbfb41d577690b8e7371ca819f7be79986d'},
                                       'labels': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/graph_labels.json',
                                                  'sha256': '2f294a72c70680695f1bb5a5aab2a81e581795e0859a5dbf705acb36c2d650b9'},
                                       'prepared_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/manifest.json',
                                                             'sha256': '4ce2108569f003778f7d8f4d11ada89c6ead9d5fe759c394a86d92d9229aeb07'},
                                       'source_metadata_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build/reentrancy_author_contract/sources.json',
                                                                    'sha256': '05bc49e58840478d13f0974248201fafcd50a06922e28bd1f10a1a7679a65f5b'},
                                       'source_task_id': 'reentrancy_author_contract',
                                       'source_task_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/prepared/reentrancy_author_contract/fold_0/task.json',
                                                                'sha256': 'ed5132c69bc64ecbdc5a5cc154b65d00382ce5c5cd6c10814317e943ab237122'}},
                          'node': {'folds': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/splits/node_folds.json',
                                             'sha256': '6c66b36db74f9905d311609117d50d41b987cf5dac82c000b6f3c620c26f015f'},
                                   'labels': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/graph_labels.json',
                                              'sha256': '2f294a72c70680695f1bb5a5aab2a81e581795e0859a5dbf705acb36c2d650b9'},
                                   'prepared_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/manifest.json',
                                                         'sha256': '4ce2108569f003778f7d8f4d11ada89c6ead9d5fe759c394a86d92d9229aeb07'},
                                   'source_metadata_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build/reentrancy_author_node/sources.json',
                                                                'sha256': '15a07b55d59891d6d652355db9e699a501cd2a0f195c3bbc4e7a1ae91efda0bc'},
                                   'source_task_id': 'reentrancy_author_node',
                                   'source_task_manifest': {'path': '/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/prepared/reentrancy_author_node/fold_0/task.json',
                                                            'sha256': 'afd7003d806730f15a72beade2afbb1dcea09a26d3c0fdbafe4944abbedead45'}}}}}


def checked_ref(ref):
    if not isinstance(ref, dict) or set(("path", "sha256")) - set(ref):
        raise ValueError("Reference requires path and sha256")
    return checked(ref["path"], ref["sha256"])


def read_labels(ref):
    data = read_json(checked_ref(ref))
    if not isinstance(data, list):
        raise ValueError("Expected graph label records")
    labels = {}
    for row in data:
        name, value = row.get("contract_name"), row.get("targets")
        if not isinstance(name, str) or not name or name in labels:
            raise ValueError("Missing or duplicate graph label identity")
        if type(value) is not int or value not in (0, 1):
            raise ValueError("Graph label must be a binary integer")
        labels[name] = value
    return labels


def _bound_record(category, task, record):
    out = copy.deepcopy(record)
    for key in ("source_task_manifest", "source_metadata_manifest",
                "prepared_manifest", "labels", "folds"):
        checked_ref(out[key])
    source = read_json(out["source_task_manifest"]["path"])
    prepared = read_json(out["prepared_manifest"]["path"])
    if source.get("task_id") != out["source_task_id"] or source.get("task") != task:
        raise ValueError("Frozen task identity differs")
    if prepared.get("category") != category or source.get("cohort") != prepared.get("cohort"):
        raise ValueError("Frozen category/cohort identity differs")
    for key, pathkey, shakey in (
            ("labels", "labels_path", "labels_sha256"),
            ("prepared_manifest", "source_prepared_manifest", "source_prepared_manifest_sha256")):
        if (Path(source[pathkey]).resolve() != Path(out[key]["path"]).resolve()
                or source[shakey] != out[key]["sha256"]):
            raise ValueError("Frozen task reference differs: " + key)
    fold = validate_fold_document(read_json(out["folds"]["path"]))
    if (fold["task"] != task or fold["prepared_manifest_sha256"] != out["prepared_manifest"]["sha256"]
            or fold["seed"] != 1 or fold["inner_fraction"] != .2):
        raise ValueError("Frozen nested fold protocol differs")
    out.update(task_id=category + "_" + task, category=category, task=task)
    return out


def get_tasks(task_ids=None, registry=None):
    """Return public-task-id -> bound record, optionally expanding category IDs."""
    registry = REGISTRY if registry is None else registry
    if not isinstance(registry, dict) or not registry:
        raise ValueError("Nonempty category registry required")
    available = {}
    for category, row in registry.items():
        if (not isinstance(category, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", category)
                or row.get("category") != category):
            raise ValueError("Invalid category identity")
        if set(row.get("tasks", ())) != {"contract", "node"}:
            raise ValueError("Each category requires contract and node task references")
        for task, record in row["tasks"].items():
            available[category + "_" + task] = (category, task, record)
    if isinstance(task_ids, str):
        task_ids = task_ids.split(",")
    requested = list(available) if task_ids is None else list(task_ids)
    selected = []
    for identity in requested:
        if identity in registry:
            expanded = [identity + "_contract", identity + "_node"]
        elif identity in available:
            expanded = [identity]
        else:
            raise ValueError("Unknown registered task/category: " + str(identity))
        if set(selected) & set(expanded):
            raise ValueError("Duplicate selected task")
        selected.extend(expanded)
    if not selected:
        raise ValueError("At least one task must be selected")
    return {tid: _bound_record(*available[tid]) for tid in sorted(selected)}


def task_population(record):
    """Read exact graph filenames, independently of node labels or DDG edges."""
    source = read_json(checked_ref(record["source_task_manifest"]))
    ref = source["graphs"]["HCG"]
    graph = read_graph(checked_ref(ref))
    files = sorted({d["source_file"] for _, d in graph.nodes(data=True)})
    labels = read_labels(record["labels"])
    if not files or any(f not in labels for f in files):
        raise ValueError("Original graph file missing from graph labels")
    population = {f: labels[f] for f in files}
    if record["task"] == "node" and set(population.values()) != {1}:
        raise ValueError("Node task original graph must contain only buggy files")
    return population


def make_folds(category, registry=None):
    """Rebuild 5/10 nested folds in memory; never write or replace frozen splits."""
    records = get_tasks([category], registry=registry)
    result = {}
    for tid, record in records.items():
        document = make_fold_document(task_population(record), record["task"],
            record["prepared_manifest"]["sha256"], seed=1, inner_fraction=.2)
        frozen = read_json(checked_ref(record["folds"]))
        if document != frozen:
            raise ValueError("Rebuilt nested folds differ from frozen document: " + tid)
        result[tid] = document
    return result
