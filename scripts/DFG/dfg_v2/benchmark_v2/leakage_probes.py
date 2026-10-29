"""Frozen Prompt 8E leakage probes. These do not fit the HGT.

P2 uses binary node presence (one vote/name/node) on INNER TRAIN ONLY.
P3 fits a diagnostic LR; its char vocabulary is fitted on training files only.
"""
from collections import Counter
import warnings
import numpy as np

from ..diagnostics8c.inference import identifiers, serialized_view
from ..diagnostics8d.renaming import EXCLUDED_NAMES, rewrite_node
from ..diagnostics8c.scoring import confusion, metric_counts

VIEWS = ("original", "idN", "N-real")
PROTOCOL = dict(
    version="prompt8e-probes-v1",
    P2=dict(support_unit="distinct HCG nodes containing spelling, counted once per node",
            fit_files="frozen inner_train_files only", min_support=3, positive_fraction=0.5,
            test_rule="node OR exact enclosing function",
            labels=["orig", "C1"], threshold_pp=5.0,
            gate_aggregation="pooled OOF SolidiFI separately per task and label; all must pass",
            folds="reuse archived grouped node 10-fold; inner_val and outer_test labels never used for fitting"),
    P3=dict(samples="unique file/role/name/injected-declaration-status, no frequency weights",
            vocabulary="char 2-4 grams, case sensitive, TF-IDF fit on training files only",
            folds=5, split="GroupKFold with frozen duplicate-component IDs across all 128 identities",
            estimator=dict(C=1.0, solver="liblinear", class_weight="balanced",
                           max_iter=1000, random_state=1),
            threshold_auc=0.60, gate_aggregation="pooled OOF over all 128 files",
            interpretation="transductive real-name pool is frozen from all files as requested; no held-out-domain claim"),
    no_tuning_after_scores=True, hgt_training_executed=0)


def name_set(code, serialized=False):
    text = serialized_view(code)[0] if serialized else code
    return {word for word, _, _ in identifiers(text) if word not in EXCLUDED_NAMES}


def fit_name_memory(rows, train_files, label):
    selected = set(train_files)
    support, positive = Counter(), Counter()
    for row in rows:
        if row["file"] not in selected:
            continue
        names = name_set(row["own_code"], serialized=True)
        support.update(names)
        if row[label] == 1:
            positive.update(names)
    return {name: dict(support=n, positive=positive[name],
                       fraction=positive[name] / n)
            for name, n in sorted(support.items()) if n >= 3 and positive[name] / n >= 0.5}


def p2_fold(rows, fold, label):
    train, val, test = (set(fold[k]) for k in
                       ("inner_train_files", "inner_val_files", "outer_test_files"))
    if train & val or train & test or val & test:
        raise ValueError("Fold file partitions overlap")
    if train | val | test != {r["file"] for r in rows}:
        raise ValueError("Fold file population differs")
    memory = fit_name_memory(rows, train, label)
    names = set(memory)
    predictions = []
    for row in rows:
        if row["file"] not in test:
            continue
        pred = bool(names & (name_set(row["own_code"], serialized=True)
                            | name_set(row["function_code"] or "")))
        predictions.append({k: row[k] for k in
                            ("file", "source_sha256", "original_graph_node_id", "solidifi", label)})
        predictions[-1].update(prediction=int(pred), fold=fold["fold"])
    selected = [r for r in predictions if r["solidifi"]]
    metric = metric_counts(confusion((r[label], r["prediction"]) for r in selected))
    baseline = metric_counts(confusion((r[label], 1) for r in selected))
    return dict(fold=fold["fold"], learned_names=memory, predictions=predictions,
                metric=metric, all_positive=baseline)


def p2_all(rows, folds, label):
    output = [p2_fold(rows, fold, label) for fold in folds]
    predictions = [r for fold in output for r in fold["predictions"]]
    ids = [(r["file"], r["source_sha256"], r["original_graph_node_id"]) for r in predictions]
    expected = {(r["file"], r["source_sha256"], r["original_graph_node_id"]) for r in rows}
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError("OOF node identity missing or repeated")
    selected = [r for r in predictions if r["solidifi"]]
    metric = metric_counts(confusion((r[label], r["prediction"]) for r in selected))
    baseline = metric_counts(confusion((r[label], 1) for r in selected))
    delta = metric["buggy_f1"] - baseline["buggy_f1"]
    return dict(folds=output, pooled=metric, all_positive=baseline, delta_bf1_pp=delta,
                passed=delta <= 5.0, scored_nodes=len(selected))


def p1(inventories, mappings, pool):
    ordinary = {name for words in pool["roles"].values() for name in words}
    replacements = {v for mapping in mappings.values() for v in mapping.values()}
    seen = replacements & ordinary
    replacement_counts, ordinary_counts, unselected_counts = Counter(), Counter(), Counter()
    for key, inv in inventories.items():
        mapping = mappings.get(key, {})
        for row in inv["lexemes"]:
            word = mapping.get(row["word"], row["word"])
            stratum = "injected" if row["injected"] else "ordinary"
            if word in replacements:
                replacement_counts[stratum] += 1
            if word in ordinary:
                ordinary_counts[stratum] += 1
            if word in ordinary - replacements:
                unselected_counts[stratum] += 1
    def fraction(counts):
        n = sum(counts.values())
        return dict(counts=dict(counts), total=n,
                    injected_fraction=counts["injected"] / n if n else None)
    return dict(unique_replacements=len(replacements), witnessed=len(seen),
                ordinary_witness_rate=len(seen)/len(replacements) if replacements else None,
                unwitnessed=sorted(replacements - ordinary),
                replacement_occurrences=fraction(replacement_counts),
                all_pool_name_occurrences=fraction(ordinary_counts),
                unselected_pool_name_occurrences=fraction(unselected_counts),
                passed=bool(replacements) and replacements.issubset(ordinary))


def p3_samples(inventories, mappings, groups):
    rows = []
    for key, inv in sorted(inventories.items()):
        mapping = mappings.get(key, {})
        seen = set()
        for d in inv["declarations"]:
            word = d["word"]
            if word in EXCLUDED_NAMES:
                continue
            identity = (d["role"], word, d["injected"])
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(dict(file_id=key, group=groups[key], source_sha256=inv["source_sha256"],
                             role=d["role"], original=word, name=mapping.get(word, word),
                             target=int(d["injected"])))
    return rows


def run_p3(samples, n_splits=5):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import roc_auc_score
    names = np.array([r["name"] for r in samples], dtype=object)
    targets = np.array([r["target"] for r in samples], dtype=np.int64)
    groups = np.array([r["group"] for r in samples], dtype=object)
    predictions = np.full(len(samples), np.nan)
    assignments = np.full(len(samples), -1, dtype=int)
    folds = []
    for index, (train, test) in enumerate(GroupKFold(n_splits=n_splits).split(names, targets, groups)):
        if set(groups[train]) & set(groups[test]):
            raise AssertionError("P3 group leakage")
        if len(set(targets[train])) != 2 or len(set(targets[test])) != 2:
            raise ValueError("P3 fold lacks both classes")
        vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), lowercase=False)
        x = vec.fit_transform(names[train])
        model = LogisticRegression(**PROTOCOL["P3"]["estimator"])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(x, targets[train])
        if caught:
            raise RuntimeError("P3 fitting warning: " + "; ".join(str(w.message) for w in caught))
        probability = model.predict_proba(vec.transform(names[test]))[:, 1]
        predictions[test] = probability
        assignments[test] = index
        folds.append(dict(fold=index, auc=float(roc_auc_score(targets[test], probability)),
                          train=len(train), test=len(test), vocabulary=len(vec.vocabulary_),
                          train_groups=sorted(set(groups[train])),
                          test_groups=sorted(set(groups[test]))))
    if not np.isfinite(predictions).all() or (assignments < 0).any():
        raise AssertionError("P3 incomplete OOF")
    auc = float(roc_auc_score(targets, predictions))
    by_task = {}
    for task in sorted({r["file_id"].split("/")[0] for r in samples}):
        mask = np.array([r["file_id"].split("/")[0] == task for r in samples])
        by_task[task] = float(roc_auc_score(targets[mask], predictions[mask]))
    return dict(auc=auc, passed=auc <= 0.60, folds=folds, by_task_auc=by_task,
                samples=len(samples), classifier_fits=n_splits,
                predictions=[dict(row, fold=int(f), probability=float(p))
                             for row, f, p in zip(samples, assignments, predictions)])
