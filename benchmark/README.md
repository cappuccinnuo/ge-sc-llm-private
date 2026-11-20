# benchmark — the rebuilt pipeline from source to detection, against the paper

`benchmark` runs the MANDO-LLM baseline end to end on the graphs `hcg` rebuilds from
the Solidity sources and puts the results next to the paper's tables (MANDO-LLM,
TOSEM 2025; Dataset A: Table 3 contract level, Table 5 line level; Dataset B:
Tables 4 and 6, `--dataset B`). It also runs the
two-phase detector the paper describes but does not evaluate (contract model, then line
model on the flagged contracts) and scores everything on source lines as well as on
graph nodes.

```bash
python -m hcg fetch && python -m hcg build             # graphs of all 7 categories, CodeT5+ tokens
python -m benchmark run --out runs/benchmark/full      # every protocol, profile G0
python -m benchmark report runs/benchmark/full         # rescore and rewrite report.md
```

On the RTX 5080: `docker/run.sh docker/benchmark.sh` does all of it (environment check,
unit tests, fetch, build, run); `QUICK=1` first checks the plumbing on one category in a
few minutes. Narrower runs: `--categories`, `--protocols`, `--folds`, `--epochs`,
`--profiles` (other DFG profiles than G0 need `python -m dfg build`). Finished fits are
skipped, so an interrupted run resumes. `--folds` does not apply to `upstream`.

## What is trained

| protocol | how folds and checkpoints are chosen |
|---|---|
| `paper` | as the authors' trainers and paper Sec. 5.3: seeded `StratifiedKFold(5)` over the contracts / `KFold(10)` over the vulnerable contracts; the held-out fold selects the best checkpoint (validation loss, patience 7, δ 0.001) and is scored; fold scores are averaged. The folds equal those of `mando/graph_classifier.py` / `mando/node_classifier.py` with the same seed. |
| `grouped` | the project's protocol (`dfg.train`): duplicate groups never straddle roles, the checkpoint is chosen on an inner validation split, the held-out fold is only scored. |
| `upstream` | the authors' trainers themselves, unmodified, on the same graphs and folds (`benchmark/upstream.py`): checks that the dfg engine reproduces them. |

Under `paper` and `grouped` three tracks are fitted with `dfg.train.runner.run_task`
(profile G0 = the MANDO-LLM HGT, hidden 128, 2 layers, 8 heads, the paper's learning
rates):

| track | graph | fitted on | scored on |
|---|---|---|---|
| `contract` | `contract_level` (all contracts) | contracts | held-out contracts |
| `line` | `line_level` (vulnerable contracts) | their nodes | held-out nodes |
| `cascade` | `contract_level` | nodes of the vulnerable training contracts | nodes of every held-out contract |

`cascade` uses the `contract` track's folds, so on each fold both phases see the same
unseen contracts.

## What is scored

* **Contract level** — Buggy-F1 and Macro-F1 of the held-out contracts (Table 3 / 4).
* **Line level, nodes** — Buggy-F1 of the held-out nodes of vulnerable contracts: what
  the paper calls line level (Table 5).
* **Line level, source lines** — the same predictions on lines. A node speaks for its
  label endpoints (first and last preprocessed line, the rule that labelled it); a line
  is predicted vulnerable when a node predicted vulnerable speaks for it, and is
  vulnerable when a target-category annotation covers it. Annotated lines no node
  speaks for count as misses (`line coverage` reports how many are reachable at all);
  `contracts hit` is the share of vulnerable contracts with at least one annotated line
  flagged.
* **By source** — the contract, line and detector scores restricted to one source's
  vulnerable contracts (SolidiFI, SmartBugs-curated, DAppSCAN; with all clean
  contracts where the task needs them), pooled over folds. SolidiFI's injected
  templates make its scores near-perfect; the other sources show real-world code.
* **End to end** — the detector: lines of the contracts the contract model flags.
  Two references isolate the phases: the line model gated by the true contract label
  (`true contract gate`) and not gated at all (`no gate`).

All scores are fold means (± SD) of the best checkpoint, in percent.

## Output

```
runs/benchmark/<name>/
  hcg/                     the graphs (docker/benchmark.sh builds them here; else --hcg)
  run.json                 settings, code commit, SHA-256 of the hcg outputs per category
  paper/ grouped/          <category>_<track>/fold_<k>/<profile>/{result,predictions,history}.json
  upstream/                <category>_<contract|line>/{result.json,train.log,model_fold<k>/}
  evaluation.json          every score above
  report.md                the tables, with the paper's numbers and Δ = ours − paper
  findings/<protocol>/<profile>/<category>.json
                           the detector's verdict per contract: probability, flagged lines and
                           annotated lines in original line numbers
  benchmark.log            console output of docker/benchmark.sh
```

## Comparing with the paper

* The paper rows are in `paper.py` (transcribed from the PDF; Table 1 totals agree with
  `hcg`). The comparison row is `codet5p-770m`, the tokenizer the pipeline uses; the best
  of the paper's three tokenizer rows is shown next to it.
* Contract-level graphs and contract labels equal the authors' released graphs. The
  line-level graph is the HCG of the vulnerable contracts, as the paper describes; the
  authors' released line-level asset is CFG-only.
* Node labels follow the public-annotation policy of `hcg` (`hcg/README.md`): they
  differ from the authors' labels on a documented set of nodes, so node scores are not
  on identical labels.
* Under `paper` the held-out fold also selects the checkpoint, which favours the score;
  `grouped` shows the same models without that and without duplicate leakage.
* One seed (1) per run; `--seed` changes folds (paper) and initialization.

## Layout

```
benchmark/
  paper.py      the paper's numbers
  folds.py      fold plans (paper, cascade); validation
  lines.py      node predictions -> source lines, line scores, original line numbers
  tracks.py     tracks per category and protocol; training through dfg.train; run.json
  upstream.py   the authors' trainers
  evaluate.py   scores, detector, findings
  report.py     report.md
  __main__.py   CLI
```
