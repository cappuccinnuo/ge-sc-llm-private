# combined — the proposed method in one model

`combined` puts the three enhancements into one HGT and trains it against the
MANDO-LLM baseline. It reads the outputs of [`hcg`](../hcg/README.md),
[`dfg`](../dfg/README.md), [`nodesem`](../nodesem/README.md) and
[`edgesem`](../edgesem/README.md), and trains through [`benchmark`](../benchmark/README.md)
as profile **FULL**.

| part | from | what it adds over G0 |
|---|---|---|
| graph | DFG `G3R` | data-flow layers L1–L3 (def-use, state reads/writes, environment flow), merged reverse edges |
| edges | EdgeSem `G4R-AC` | typed directions, the E1 relations MOD_APPLY / CALL_SITE / GUARDS, core + context edge attributes in an edge-aware HGT |
| nodes | NodeSem `S6` | CODE + CTX + STATIC + LLM-teacher modalities in place of the 512 raw token IDs |

## Construction and initialization (`model.py`)

1. The task's DFG F3 graph is carried with S6's inputs: each node's `token` becomes the
   S6 carrier vector (`nodesem.features.carry`).
2. EdgeSem builds its G4R-AC model on that graph (`edgesem.model.build.make_edge_model`).
3. Its input Linears are replaced by NodeSem adapters, one per node type.

Each part starts exactly where it starts in its single-stage run:

- every graph, relation, edge-encoder and classifier tensor comes from EdgeSem's G4R-AC
  fold initialization;
- every adapter tensor comes from NodeSem's S6@G3R fold initialization (S4 tensors from
  S4's seeds, the teacher projection new), computed on the same carried graph.

`tests/combined/test_units.py` checks both against the stages' own constructors.
A cascade track (node model on the contract graph) uses the node task's adapter seeds.

## Training (`train.py`) and protocol

`python -m benchmark run --profiles G0 FULL` trains both profiles on every track
(contract, line, cascade) with the same folds, supervision, epoch engine, checkpoint
selection and task configuration (`dfg.train`). The two arms differ only in the model.
EdgeSem's single-stage runs used a fixed 50 epochs (patience 51); here both arms use
the benchmark's default configuration. NodeSem's modality dropout is seeded from the
fold's fit seed. Results go to `<run>/grouped/<category>_<track>/fold_<k>/FULL/`, next to
G0, and resume. `full.json` records the stage inputs; a run refuses to mix them.

Only the grouped protocol is used: duplicate- and (Dataset B) project-disjoint
folds, with the checkpoint selected on inner validation. S6 needs the LLM
descriptions at prediction time too, so `nodesem describe` runs on every contract.

## Comparison over seeds (`compare.py`)

`python -m combined compare --runs <seed run> ... --out <dir>` pairs FULL with G0 per
(seed, fold) on the same held-out files. It runs a two-sided Wilcoxon signed-rank test
(Holm over categories) and reports pooled scores as mean ± sd over seeds.

| metric | population | role |
|---|---|---|
| `line_dappscan` | line track, nodes of DAppSCAN contracts | main metric: real-world line level |
| `line_all` | line track, every held-out node | dominated by SolidiFI's templates |
| `contract_dappscan` | contract track, DAppSCAN vs DAppSCAN-clean | real-world contract level |
| `contract_all` | contract track, every held-out contract | |

## Usage

```bash
QUICK=1 docker/run.sh docker/method.sh   # plumbing: time_manipulation, fold 0, 2 epochs, 1 seed
docker/run.sh docker/method.sh           # all 7 categories, seeds 1 2 3 -> runs/method/b/compare.md
```

`docker/method.sh` regenerates every stage from the Solidity sources into the run
directory, then trains and compares (details in [`docker/README.md`](../docker/README.md)).

## Layout

```
combined/
  __init__.py    profile names (FULL = G3R + G4R-AC + S6)
  model.py       carry S6 inputs, build on EdgeSem G4R-AC, NodeSem adapters, joint initialization, validation
  train.py       one benchmark track: folds -> fit -> score -> result files (dfg.train engine)
  compare.py     FULL vs G0 over seeds: paired (seed, fold) tests, pooled scores, compare.md
  __main__.py    CLI: python -m combined compare
```
