"""Frozen file-level nested splits and semantic paired initialization.

Codex 2026-10-12. No graph/label/model-core mutations. The caller must construct
both models freshly before paired_initialize; this helper never reads a trained
checkpoint. Evaluation must separately enforce training schema coverage.
"""
import hashlib
import json
import math
import re

PROTOCOL_VERSION = "ddg-nested-paired-v1"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode("utf8")).hexdigest()


def _doc_digest(doc):
    return _digest({k: v for k, v in doc.items() if k != "split_sha256"})


def make_fold_document(file_labels, task, prepared_manifest_sha256, seed=1,
                       inner_fraction=0.2):
    """Return 5 contract / 10 buggy-only node outer folds with nested holdouts.

    file_labels is a filename -> binary graph-label dict, never node labels.
    Seeds and populations are fixed independently of E0/E1 graph relations.
    """
    from sklearn.model_selection import KFold, StratifiedKFold, train_test_split
    if task not in ("node", "contract"):
        raise ValueError("task must be node or contract")
    if not 0 < inner_fraction < 1:
        raise ValueError("inner_fraction must lie strictly between zero and one")
    labels = dict(file_labels)
    if not labels or any(not isinstance(f, str) or not f for f in labels):
        raise ValueError("Nonempty unique filenames required")
    if any(type(y) is not int or y not in (0, 1) for y in labels.values()):
        raise ValueError("Graph labels must be binary integers")
    if task == "node" and set(labels.values()) != {1}:
        raise ValueError("Node task requires the frozen buggy-contract population")
    files = sorted(labels)
    ys = [labels[f] for f in files]
    k = 10 if task == "node" else 5
    if len(files) < k:
        raise ValueError("Too few files for required outer folds")
    if task == "contract":
        if min(ys.count(0), ys.count(1)) < k:
            raise ValueError("Each graph class requires at least five files")
        outer = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
        iterator = outer.split(files, ys)
    else:
        outer = KFold(n_splits=k, shuffle=True, random_state=seed)
        iterator = outer.split(files)
    folds = []
    for fold, (train_index, test_index) in enumerate(iterator):
        outer_train = [files[int(i)] for i in train_index]
        inner_seed = int(seed) * 1009 + fold + 1
        stratify = [labels[f] for f in outer_train] if task == "contract" else None
        inner_train, inner_val = train_test_split(
            outer_train, test_size=inner_fraction, random_state=inner_seed,
            shuffle=True, stratify=stratify)
        folds.append({"fold": fold, "inner_seed": inner_seed,
                      "inner_train_files": sorted(inner_train),
                      "inner_val_files": sorted(inner_val),
                      "outer_test_files": sorted(files[int(i)] for i in test_index)})
    doc = {"protocol_version": PROTOCOL_VERSION, "task": task,
           "prepared_manifest_sha256": str(prepared_manifest_sha256),
           "seed": int(seed), "inner_fraction": float(inner_fraction),
           "k_folds": k, "files": files,
           "file_labels": {f: labels[f] for f in files},
           "note": "File-level nested CV; inner validation selects checkpoints. "
                   "Outer test is used only after fitting. This is not template "
                   "deduplication and is not an author-published fold manifest.",
           "folds": folds}
    doc["split_sha256"] = _doc_digest(doc)
    validate_fold_document(doc)
    return doc


def validate_fold_document(doc):
    """Reject drift, overlaps, omitted files, duplicates, or incomplete outer CV."""
    if doc.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("Unsupported fold protocol")
    if doc.get("split_sha256") != _doc_digest(doc):
        raise ValueError("Split document hash mismatch")
    task = doc.get("task")
    if task not in ("node", "contract"):
        raise ValueError("Bad split task")
    k = 10 if task == "node" else 5
    files = doc.get("files", [])
    if not files or len(files) != len(set(files)) or files != sorted(files):
        raise ValueError("Bad file population")
    population = set(files)
    labels = doc.get("file_labels", {})
    if set(labels) != population or any(type(y) is not int or y not in (0, 1)
                                        for y in labels.values()):
        raise ValueError("Invalid frozen file labels")
    if task == "node" and set(labels.values()) != {1}:
        raise ValueError("Node population must contain only buggy files")
    folds = doc.get("folds", [])
    if doc.get("k_folds") != k or [f.get("fold") for f in folds] != list(range(k)):
        raise ValueError("Missing, repeated or unordered folds")
    test_counts = {f: 0 for f in files}
    for fold in folds:
        groups = []
        for key in ("inner_train_files", "inner_val_files", "outer_test_files"):
            values = fold.get(key, [])
            if not values or len(values) != len(set(values)) or values != sorted(values):
                raise ValueError("Empty, repeated or unordered file split: " + key)
            groups.append(set(values))
            if task == "contract" and {labels.get(f) for f in values} != {0, 1}:
                raise ValueError("Both graph classes must be represented in each split")
        if any(groups[i] & groups[j] for i in range(3) for j in range(i + 1, 3)):
            raise ValueError("Train/validation/test file overlap")
        if set.union(*groups) != population:
            raise ValueError("Fold does not partition the frozen file population")
        for f in groups[2]:
            test_counts[f] += 1
    if set(test_counts.values()) != {1}:
        raise ValueError("Each file must occur in exactly one outer test fold")
    return doc


def _state_digest(state):
    h = hashlib.sha256()
    for name, value in sorted(state.items()):
        value = value.detach().cpu().contiguous()
        h.update(name.encode())
        h.update(str(value.dtype).encode())
        h.update(str(tuple(value.shape)).encode())
        h.update(value.numpy().tobytes())
    return h.hexdigest()


def _validate_schema(mapping, canonical=False):
    if set(mapping.values()) != set(range(len(mapping))):
        raise ValueError("Type indices must be unique contiguous integers")
    if canonical and any(not isinstance(k, tuple) or len(k) != 3 for k in mapping):
        raise ValueError("Expected canonical relation triples")


def paired_initialize(e0_model, e1_model, seed=1):
    """Copy *fresh* E0 weights to E1 by node name and canonical relation.

    Both supplied models must be newly constructed, without optimization or
    checkpoint loading. No E0 trained checkpoint is read or accepted here.
    E0 is left unchanged. E1-only DATA_DEF_USE relation slices receive isolated
    deterministic initial draws; classifier and common HGT/adaptation parameters
    are exactly equal by semantic identity even when integer type IDs differ.
    """
    import torch
    nodes0, nodes1 = e0_model.ntypes_dict, e1_model.ntypes_dict
    edges0, edges1 = e0_model.etypes_dict, e1_model.etypes_dict
    for mapping in (nodes0, nodes1):
        _validate_schema(mapping)
    for mapping in (edges0, edges1):
        _validate_schema(mapping, canonical=True)
    if set(nodes0) != set(nodes1):
        raise ValueError("Paired graph node type sets differ")
    if not set(edges0).issubset(edges1):
        raise ValueError("E1 removed an E0 canonical relation")
    if any(edge[1] == "DATA_DEF_USE" for edge in edges0):
        raise ValueError("E0 must be an unenhanced baseline")
    for nodes, edges in ((nodes0, edges0), (nodes1, edges1)):
        if any(edge[0] not in nodes or edge[2] not in nodes for edge in edges):
            raise ValueError("Canonical relation references unknown node types")
    new_edges = set(edges1) - set(edges0)
    if any(edge[1] != "DATA_DEF_USE" for edge in new_edges):
        raise ValueError("Only forward DATA_DEF_USE relations may be added")
    source = {k: v.detach().cpu().clone() for k, v in e0_model.state_dict().items()}
    target = {k: v.detach().cpu().clone() for k, v in e1_model.state_dict().items()}
    initial_e0_hash = _state_digest(source)
    if set(source) != set(target):
        raise ValueError("Paired architectures have different state keys")
    inverse1 = {index: name for name, index in nodes1.items()}
    shared0, shared1, new_state = {}, {}, {}
    node_pattern = re.compile(r"^(adapt_ws)\.(\d+)\.(.+)$")
    layer_node_pattern = re.compile(
        r"^(gcs\.\d+\.(?:k_linears|q_linears|v_linears|a_linears|norms))\.(\d+)\.(.+)$")
    for name, value in target.items():
        if re.match(r"^gcs\.\d+\.relation_(pri|att|msg)$", name):
            if value.shape[0] != len(edges1) or source[name].shape[0] != len(edges0):
                raise ValueError("Relation tensor/schema mismatch: " + name)
            if value.shape[1:] != source[name].shape[1:]:
                raise ValueError("Relation tensor shapes differ: " + name)
            for edge, index in sorted(edges1.items()):
                identity = name + "|" + json.dumps(edge)
                if edge in edges0:
                    value[index].copy_(source[name][edges0[edge]])
                    shared0[identity] = source[name][edges0[edge]]
                    shared1[identity] = value[index]
                else:
                    relation_seed = int(_digest([int(seed), name, edge])[:15], 16)
                    with torch.random.fork_rng(devices=[]):
                        torch.manual_seed(relation_seed)
                        if name.endswith("relation_pri"):
                            value[index].fill_(1)
                        else:
                            # Match the original HGT full relation-bank Xavier
                            # distribution, not the fan dimensions of a 3D slice.
                            fan_in, fan_out = torch.nn.init._calculate_fan_in_and_fan_out(value)
                            bound = math.sqrt(6.0 / float(fan_in + fan_out))
                            value[index].uniform_(-bound, bound)
                    new_state[identity] = value[index]
        elif re.match(r"^gcs\.\d+\.skip$", name):
            if value.shape != (len(nodes1),) or source[name].shape != (len(nodes0),):
                raise ValueError("Skip vector/schema mismatch")
            for node, index in nodes1.items():
                identity = name + "|" + node
                value[index].copy_(source[name][nodes0[node]])
                shared0[identity] = source[name][nodes0[node]]
                shared1[identity] = value[index]
        else:
            match = node_pattern.match(name) or layer_node_pattern.match(name)
            if match:
                prefix, index, suffix = match.groups()
                node = inverse1[int(index)]
                source_name = prefix + "." + str(nodes0[node]) + "." + suffix
                identity = prefix + "|" + node + "|" + suffix
            else:
                source_name = name
                identity = name
            if value.shape != source[source_name].shape:
                raise ValueError("Common parameter shape mismatch: " + name)
            value.copy_(source[source_name])
            shared0[identity] = source[source_name]
            shared1[identity] = value
    if _state_digest(shared0) != _state_digest(shared1):
        raise AssertionError("Semantically shared initial weights differ")
    e1_model.load_state_dict(target, strict=True)
    if _state_digest(e0_model.state_dict()) != initial_e0_hash:
        raise AssertionError("Paired initialization mutated E0")
    return {"protocol_version": PROTOCOL_VERSION, "new_relation_seed": int(seed),
            "initialization_source": "fresh E0 constructor state; no trained checkpoint",
            "e0_state_sha256": initial_e0_hash,
            "e1_state_sha256": _state_digest(e1_model.state_dict()),
            "shared_semantic_sha256": _state_digest(shared0),
            "new_relations_sha256": _state_digest(new_state),
            "shared_tensor_count": len(shared0),
            "new_canonical_relations": [list(e) for e in sorted(new_edges)],
            "node_type_alignment": {n: [nodes0[n], nodes1[n]] for n in sorted(nodes0)},
            "e0_canonical_order": [list(e) for e, _ in sorted(edges0.items(), key=lambda x: x[1])],
            "e1_canonical_order": [list(e) for e, _ in sorted(edges1.items(), key=lambda x: x[1])],
            "e0_parameters": sum(p.numel() for p in e0_model.parameters()),
            "e1_parameters": sum(p.numel() for p in e1_model.parameters())}
