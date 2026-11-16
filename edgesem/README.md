# edgesem — edge semantic enhancement for HCG/DFG graphs

`edgesem` gives the HGT edges meaning beyond their relation name. It adds three
semantic relations to the DFG graph F3 (L1–L3), describes every edge with a 74-bit
attribute vector, and trains an edge-aware HGT whose attention and messages read those
attributes. It reads the outputs of [`hcg`](../hcg/README.md) and
[`dfg`](../dfg/README.md); statement facts come from `nodesem.facts` (no NodeSem store
is needed).

**F4 = F3 + E1 relations** (built per file from the source and F3, F3 is never mutated):

| relation | from → to | evidence |
|---|---|---|
| `MOD_APPLY` | function → applied modifier | resolved modifier invocation |
| `CALL_SITE` | call statement → callee definition | unique same-file declaration (no name heuristics) |
| `GUARDS` | guard statement → guarded statement | require/if/early-exit/loop/modifier/internal checks, with operand classes and polarity |

**Edge attributes** (`uint8[74]`, `attributes/layout.py`): definition kind, write access
and operator, variable kind and value shape, CFG dominance/post-dominance, loop-carried
dependence, guard kind/operands, sinks, call kind, compiler-interval facts; fields a
relation cannot have are zero by rule, unknowns stay zero with a recorded reason. The
columns a model reads are frozen in `schema.py`: 50 **core** columns, and core ∪ 26
**context** columns for G4R-AC.

**Profiles** (all derived from a fresh G3R anchor of the fold):

| profile | directions | E1 relations | edge attributes | role |
|---|---|---|---|---|
| G3R | merged reverse | – | – | baseline (DFG G3R, EdgeSem anchor) |
| G3R-T | typed `REV_*` | – | – | typed directions |
| G4R | typed | ✓ | – | + semantic relations |
| G4R-P | typed | rewired | – | placebo: E1 edges rewired, degrees kept |
| G3R-TA | typed | – | core | attributes without E1 |
| G4R-A | typed | ✓ | core | full model |
| G4R-Api | typed | ✓ | core, permuted | placebo: attribute rows permuted within relation |
| G4R-AC | typed | ✓ | core + context | wider attributes |

## Layout

```
edgesem/
  schema.py        relations, families, profiles, frozen attribute columns, P2
  graph/           calls.py (call sites) · guards.py (guard evidence + audit) · f4.py (records, add_edges)
  attributes/      layout.py (bits, rules, row keys) · sources.py (CFG/declaration sources) · compute.py
  pipeline.py      build one task: F4 edges + attributes      store.py   data/edgesem/<dataset>/<category>/<task>/
  model/           relations.py · init.py (typed copy) · layers.py (edge-aware HGT) · placebo.py · build.py
  train.py         P2 grouped nested CV on dfg.train
  __main__.py      CLI
```

## Usage

```bash
python -m hcg build && python -m dfg build     # prerequisites (with tokens, L1-L3)
python -m edgesem build                        # CPU; minutes per task
python -m edgesem train --out runs/edgesem/all # GPU recommended; 8 profiles x folds x 14 tasks
python -m edgesem report runs/edgesem/all      # paired with G3R
```

`train` takes `--profiles`, `--folds`, `--seed`, `--features anonymous` (node tokens of
renamed identifiers; edge attributes stay original-view) and `--epochs` (smoke tests
only). It refuses a store built from another F3 graph and resumes an interrupted run.

**Protocol P2.** Folds, labels and node tokens are those of `dfg.train` for the same
task; the configuration is the DFG task config with patience 51, so every fit runs the
full 50-epoch OneCycle schedule and keeps the strict-minimum inner-validation checkpoint
(first tie) besides the last one. Per fold every profile is built from a fresh G3R
anchor constructed with the fold's constructor seed (10000 + fold + 1000·contract):
shared parameters are copied, typed and reverse relations take their anchor relation's
rows, new E1 rows are drawn from a sha256 seed of the canonical relation, the edge
encoder and the u/U attribute weights start at zero, and placebos use the constructor
seed. Fitting uses the fold's fit seed (constructor + 10⁶). EdgeSem's G3R is its own
baseline: `dfg.train` initializes G3R from the G0 family instead.

## Verification

`tests/edgesem/test_units.py` runs without data; it checks one reentrancy contract against
the sealed per-file F4 edges and attributes, and builds, validates, runs and reloads every
profile for both tasks. `tests/edgesem/test_dataset_a.py` (needs `$MANDO_DATA_DIR`) checks,
per category and task:

* F4 edges and edge attributes equal the unmodified EdgeSem producers on the same graphs
  (`reference/old_code.json`, all 14 tasks);
* against the sealed EdgeSem artifacts (built from the authors' graphs): F4 edges of
  reentrancy and access control (both tasks), edge attributes of their node tasks, and
  the initial weights of G3R, G3R-T, G4R, G4R-P, G3R-TA, G4R-A and G4R-Api on folds 0 and 9.

Endpoints are compared by position within their file (env nodes by their neighbourhood),
since global node ids differ between graph builds.

networkx ≥ 3.5 no longer lists the start node in `immediate_dominators`; the attribute
sources restore it, so dominance bits are identical across networkx versions (a unit
test simulates the new behaviour).
