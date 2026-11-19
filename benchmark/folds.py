"""Fold plans of the benchmark, in the document format ``dfg.train.runner`` consumes.

Every plan has ``folds[k][role]`` for the roles ``inner_train_files`` (fitted),
``inner_val_files`` (best checkpoint and early stopping) and ``outer_test_files``
(scored); each file is in exactly one outer-test set.

* **paper** reproduces the evaluation of the authors' trainers
  (``mando/graph_classifier.py``, ``mando/node_classifier.py``) and of the paper
  (Sec. 5.3): contracts are split by seeded ``StratifiedKFold(5)`` over the name-sorted
  contracts (contract level) or ``KFold(10)`` over the name-sorted vulnerable contracts
  (line level); the held-out fold is both the validation set that selects the
  checkpoint and the set that is scored, and the scores of the folds are averaged.
* **grouped** is the project's protocol (``dfg.train.splits``): duplicate groups never
  straddle roles and the checkpoint is selected on an inner validation split.
* **cascade** derives the two-phase plan from a contract plan: the contract model
  uses it unchanged, the line model is fitted and validated on the vulnerable
  contracts of the same roles and scored on every held-out contract, so both phases
  see exactly the same unseen contracts.
"""
import collections

from sklearn.model_selection import KFold, StratifiedKFold

ROLES = ("inner_train_files", "inner_val_files", "outer_test_files")
K_FOLDS = {"contract": 5, "line": 10}
VERSION = "benchmark-folds-v1"


def _document(task_id, protocol, files, seed, splits):
    folds = [{"fold": k, "inner_train_files": sorted(train), "inner_val_files": sorted(val),
              "outer_test_files": sorted(test)} for k, (train, val, test) in enumerate(splits)]
    return {"version": VERSION, "protocol": protocol, "task_id": task_id, "k_folds": len(folds),
            "seed": seed, "files": sorted(files), "folds": folds}


def paper_contract(task_id, file_labels, seed=1):
    """Seeded StratifiedKFold(5) over the name-sorted contracts, as graph_classifier."""
    files = sorted(file_labels)
    labels = [int(file_labels[f]) for f in files]
    splitter = StratifiedKFold(n_splits=K_FOLDS["contract"], shuffle=True, random_state=seed)
    splits = []
    for train, test in splitter.split(files, labels):
        held_out = [files[i] for i in test]
        splits.append(([files[i] for i in train], held_out, held_out))
    return validate(_document(task_id, "paper", files, seed, splits), files, "paper")


def paper_line(task_id, files, seed=1):
    """Seeded KFold(10) over the name-sorted vulnerable contracts, as node_classifier."""
    files = sorted(files)
    splitter = KFold(n_splits=K_FOLDS["line"], shuffle=True, random_state=seed)
    splits = []
    for train, test in splitter.split(files):
        held_out = [files[i] for i in test]
        splits.append(([files[i] for i in train], held_out, held_out))
    return validate(_document(task_id, "paper", files, seed, splits), files, "paper")


def cascade(task_id, contract_plan, file_labels):
    """Line-model plan of a two-phase run: vulnerable train/validation, all held-out files."""
    splits = []
    for split in contract_plan["folds"]:
        vulnerable = [[f for f in split[role] if file_labels[f] == 1] for role in ROLES[:2]]
        if not all(vulnerable):
            raise ValueError("%s fold %d has no vulnerable contract to fit or validate the line "
                             "model" % (task_id, split["fold"]))
        splits.append((vulnerable[0], vulnerable[1], split["outer_test_files"]))
    protocol = contract_plan.get("protocol", "grouped")
    document = _document(task_id, protocol, contract_plan["files"], contract_plan["seed"], splits)
    document["derived_from"] = contract_plan["task_id"]
    for mine, theirs in zip(document["folds"], contract_plan["folds"]):
        if mine["outer_test_files"] != sorted(theirs["outer_test_files"]):
            raise ValueError("cascade plan does not hold out the contract plan's files")
    return validate(document, contract_plan["files"], protocol)


def validate(document, files, protocol):
    """Outer-test sets partition ``files``; no file is fitted and held out in one fold."""
    seen = collections.Counter()
    for k, split in enumerate(document["folds"]):
        if split["fold"] != k:
            raise ValueError("fold order differs")
        train, val, test = (set(split[role]) for role in ROLES)
        if not train or not val or not test:
            raise ValueError("fold %d has an empty role" % k)
        if train & test or train & val:
            raise ValueError("fold %d fits a file it validates or scores" % k)
        if protocol == "paper" and not val <= test:
            raise ValueError("paper protocol validates on (part of) the held-out fold")
        if protocol != "paper" and val & test:
            raise ValueError("fold %d validates on a scored file" % k)
        seen.update(test)
    if seen != collections.Counter(sorted(files)):
        raise ValueError("outer-test sets must cover every file exactly once")
    return document
