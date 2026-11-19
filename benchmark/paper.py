"""Reference results of the MANDO-LLM paper (TOSEM 2025) on Dataset A.

Values in percent, fold means as the paper reports them, categories in the order of
``CATEGORIES``. Table 3 is the contract level (Buggy-F1 and Macro-F1, 5-fold), Table 5
the line level (Buggy-F1 only, 10-fold, vulnerable contracts only). The rows were
transcribed from the PDF at https://daoyuan14.github.io/papers/TOSEM25_MANDO-LLM.pdf;
Table 1 totals of the same transcription (846 contracts, 113,449 nodes) agree with
``hcg.datasets.registry``. Check them against the PDF before citing.

The pipeline encodes nodes with the CodeT5+ 770M tokenizer, so ``SAME_TOKENIZER`` is
the paper row a rebuilt baseline is compared with; the best of the three MANDO-LLM
rows is reported next to it because the paper names no default tokenizer.
"""

CATEGORIES = ("access_control", "arithmetic", "denial_of_service", "front_running",
              "reentrancy", "time_manipulation", "unchecked_low_level_calls")
SOURCE = "MANDO-LLM, ACM TOSEM 2025, Tables 3 and 5 (Dataset A)"
SAME_TOKENIZER = "codet5p-770m"
LLM_ROWS = ("solidity-t5", "starcoder", "codet5p-770m")

# Table 3: contract level.
CONTRACT = {
    "MANDO-HGT": dict(buggy_f1=(86.36, 83.59, 88.61, 93.28, 92.44, 92.37, 82.97),
                      macro_f1=(85.63, 82.35, 87.87, 93.17, 92.17, 91.97, 82.53)),
    "solidity-t5": dict(buggy_f1=(87.13, 88.02, 90.45, 91.61, 92.43, 95.47, 86.65),
                        macro_f1=(86.12, 87.42, 90.23, 90.94, 92.23, 94.91, 85.72)),
    "starcoder": dict(buggy_f1=(87.60, 84.97, 88.61, 93.29, 94.26, 96.18, 82.33),
                      macro_f1=(86.31, 82.95, 87.69, 93.18, 94.30, 95.97, 81.44)),
    "codet5p-770m": dict(buggy_f1=(86.71, 86.82, 91.20, 95.42, 91.67, 95.14, 82.23),
                         macro_f1=(85.63, 85.64, 89.90, 95.54, 91.49, 94.56, 82.09)),
}

# Table 5: line level (node classification on the vulnerable contracts).
LINE = {
    "MANDO-HGT": dict(buggy_f1=(86.55, 84.82, 86.53, 90.66, 85.06, 94.20, 88.79)),
    "solidity-t5": dict(buggy_f1=(95.39, 95.42, 98.23, 94.69, 95.41, 97.29, 96.18)),
    "starcoder": dict(buggy_f1=(96.49, 93.96, 98.11, 95.66, 94.26, 96.17, 94.97)),
    "codet5p-770m": dict(buggy_f1=(94.53, 94.33, 98.19, 94.95, 96.78, 96.40, 96.62)),
}

TABLES = {"contract": CONTRACT, "line": LINE}


def value(level, row, metric, category):
    """One paper number, or None when the table has no such metric."""
    values = TABLES[level][row].get(metric)
    return None if values is None else values[CATEGORIES.index(category)]


def best_llm(level, metric, category):
    """(row, value) of the best MANDO-LLM tokenizer row for one category."""
    scored = [(value(level, row, metric, category), row) for row in LLM_ROWS]
    scored = [(v, row) for v, row in scored if v is not None]
    if not scored:
        return None, None
    best, row = max(scored)
    return row, best


def mean(level, row, metric):
    values = TABLES[level][row].get(metric)
    return None if values is None else sum(values) / len(values)
