"""Reference results of the MANDO-LLM paper (TOSEM 2025) on Datasets A and B.

Values in percent, fold means as the paper reports them, categories in the order of
``CATEGORIES``. Contract level: Buggy-F1 and Macro-F1, 5-fold (Dataset A Table 3,
Dataset B Table 4). Line level: 10-fold on the vulnerable contracts, Buggy-F1
(Dataset A Table 5) and Buggy-F1 / Macro-F1 (Dataset B Table 6). The rows were
transcribed from the PDF at https://daoyuan14.github.io/papers/TOSEM25_MANDO-LLM.pdf;
Table 1 totals of the same transcription (846 contracts, 113,449 nodes) agree with
``hcg.datasets.registry``. Check them against the PDF before citing.

The pipeline encodes nodes with the CodeT5+ 770M tokenizer, so ``SAME_TOKENIZER`` is
the paper row a rebuilt baseline is compared with; the best of the three MANDO-LLM
rows is reported next to it because the paper names no default tokenizer.
"""

CATEGORIES = ("access_control", "arithmetic", "denial_of_service", "front_running",
              "reentrancy", "time_manipulation", "unchecked_low_level_calls")
SAME_TOKENIZER = "codet5p-770m"
LLM_ROWS = ("solidity-t5", "starcoder", "codet5p-770m")

DATASETS = {
    "A": dict(
        source="MANDO-LLM, ACM TOSEM 2025, Tables 3 and 5 (Dataset A)",
        tables={"contract": "Table 3", "line": "Table 5"},
        contract={
            "MANDO-HGT": dict(buggy_f1=(86.36, 83.59, 88.61, 93.28, 92.44, 92.37, 82.97),
                              macro_f1=(85.63, 82.35, 87.87, 93.17, 92.17, 91.97, 82.53)),
            "solidity-t5": dict(buggy_f1=(87.13, 88.02, 90.45, 91.61, 92.43, 95.47, 86.65),
                                macro_f1=(86.12, 87.42, 90.23, 90.94, 92.23, 94.91, 85.72)),
            "starcoder": dict(buggy_f1=(87.60, 84.97, 88.61, 93.29, 94.26, 96.18, 82.33),
                              macro_f1=(86.31, 82.95, 87.69, 93.18, 94.30, 95.97, 81.44)),
            "codet5p-770m": dict(buggy_f1=(86.71, 86.82, 91.20, 95.42, 91.67, 95.14, 82.23),
                                 macro_f1=(85.63, 85.64, 89.90, 95.54, 91.49, 94.56, 82.09)),
        },
        line={
            "MANDO-HGT": dict(buggy_f1=(86.55, 84.82, 86.53, 90.66, 85.06, 94.20, 88.79)),
            "solidity-t5": dict(buggy_f1=(95.39, 95.42, 98.23, 94.69, 95.41, 97.29, 96.18)),
            "starcoder": dict(buggy_f1=(96.49, 93.96, 98.11, 95.66, 94.26, 96.17, 94.97)),
            "codet5p-770m": dict(buggy_f1=(94.53, 94.33, 98.19, 94.95, 96.78, 96.40, 96.62)),
        }),
    "B": dict(
        source="MANDO-LLM, ACM TOSEM 2025, Tables 4 and 6 (Dataset B)",
        tables={"contract": "Table 4", "line": "Table 6"},
        contract={
            "MANDO-HGT": dict(buggy_f1=(83.63, 80.99, 87.88, 88.46, 88.52, 87.97, 82.35),
                              macro_f1=(81.63, 81.14, 87.49, 87.98, 89.33, 87.74, 81.99)),
            "solidity-t5": dict(buggy_f1=(92.30, 88.89, 90.91, 90.20, 89.55, 94.12, 88.37),
                                macro_f1=(91.80, 89.18, 90.47, 90.00, 89.22, 94.28, 89.64)),
            "starcoder": dict(buggy_f1=(86.79, 89.47, 90.91, 90.57, 88.89, 94.12, 83.33),
                              macro_f1=(85.61, 89.33, 90.62, 90.18, 89.37, 94.28, 83.67)),
            "codet5p-770m": dict(buggy_f1=(85.71, 84.93, 94.12, 88.00, 92.54, 97.14, 88.46),
                                 macro_f1=(85.71, 85.32, 93.73, 88.23, 92.30, 97.06, 87.98)),
        },
        line={
            "MANDO-HGT": dict(buggy_f1=(59.59, 77.67, 61.68, 80.40, 77.20, 76.43, 90.67),
                              macro_f1=(76.73, 84.27, 76.79, 83.44, 83.84, 82.79, 94.53)),
            "solidity-t5": dict(buggy_f1=(75.29, 88.21, 71.31, 92.79, 85.47, 82.38, 87.93),
                                macro_f1=(86.13, 91.44, 82.29, 94.40, 89.60, 87.11, 92.85)),
            "starcoder": dict(buggy_f1=(71.69, 88.47, 67.35, 92.82, 83.40, 82.26, 91.14),
                              macro_f1=(84.02, 91.71, 79.90, 94.43, 88.02, 87.15, 94.80)),
            "codet5p-770m": dict(buggy_f1=(71.78, 87.65, 72.40, 91.73, 84.77, 82.54, 89.32),
                                 macro_f1=(84.08, 91.15, 83.08, 93.54, 89.12, 87.27, 93.72)),
        }),
}


def tables(dataset):
    try:
        return DATASETS[dataset]
    except KeyError:
        raise SystemExit("benchmark/paper.py has no tables for Dataset %s" % dataset) from None


def value(dataset, level, row, metric, category):
    """One paper number, or None when the table has no such metric."""
    values = tables(dataset)[level][row].get(metric)
    return None if values is None else values[CATEGORIES.index(category)]


def best_llm(dataset, level, metric, category):
    """(row, value) of the best MANDO-LLM tokenizer row for one category."""
    scored = [(value(dataset, level, row, metric, category), row) for row in LLM_ROWS]
    scored = [(v, row) for v, row in scored if v is not None]
    if not scored:
        return None, None
    best, row = max(scored)
    return row, best
