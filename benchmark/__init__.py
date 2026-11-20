"""End-to-end benchmark of the rebuilt pipeline against the MANDO-LLM paper.

Layers (each imports only from those above it):

    paper.py      the paper's Dataset A results (Tables 3 and 5)
    folds.py      fold plans: paper protocol, grouped protocol, two-phase cascade
    lines.py      node predictions -> source lines; line-level scores
    tracks.py     what is trained per category and protocol; training via dfg.train
    upstream.py   the authors' own trainers on the same graphs
    audit.py      node labels vs the authors' released labels
    evaluate.py   scores, two-phase detector, per-contract findings of a run
    report.py     report.md next to the paper's numbers
    __main__.py   CLI: run, report
"""
__version__ = "1.0.0"
