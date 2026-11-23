# hcg: heterogeneous contract graphs from source

Upstream phase of the pipeline: raw Solidity → the graphs MANDO-LLM's HGT consumes,
for every vulnerability category of a dataset (Datasets A and B: all seven).

```bash
python -m hcg fetch                         # pinned SmartBugs + SolidiFI into data/ (or $MANDO_DATA_DIR)
python -m hcg build                         # Dataset A, all seven categories, with tokens
python -m hcg build --categories reentrancy --no-tokens
python -m hcg fetch --dataset B             # + the authors' DAppSCAN release and the clean pool
python -m hcg build --dataset B             # assembles data/corpus/B, then builds
python -m pytest tests/hcg                  # unit tests; dataset tests need $MANDO_DATA_DIR
```

Output, per category, under `data/hcg/<dataset>/<category>/` (git-ignored):

| File | Content |
|---|---|
| `contract_level.gpickle` | all contracts; node labels; `token` (512) unless `--no-tokens` |
| `line_level.gpickle` | contracts with target 1, nodes renumbered 0..n-1 |
| `graph_labels.json` | `[{contract_name, targets}]` |
| `annotations.json` | annotations in original and preprocessed lines |
| `line_node_ids.json` | line-level node i → contract-level node id |
| `manifest.json` | counts, edge types, label-source commits, tokenizer revision, checks, SHA-256 |

A Dataset A build exits non-zero if its counts differ from the paper's Table 1 or if
its structure or contract labels differ from the authors' released graphs. Dataset B
has no released graphs; its manifest and console show the paper's Table 2 counts
next to the built ones.

## Layout

```
hcg/
  __main__.py, pipeline.py   CLI; per-category orchestration and manifest
  datasets/registry.py       Dataset / Category; Datasets A and B, contract-label rule, paper counts
  datasets/dataset_b.py      the rules that compose Dataset B (writes dataset_b.json)
  datasets/dataset_b.json    the committed composition of Dataset B
  sources/repos.py           pinned source repositories (partial checkout for the large ones)
  sources/composition.py     composed corpora: read, assemble and hash-check a composition
  sources/annotations.py     SmartBugs / SolidiFI / DAppSCAN loading, preprocessing, projection
  cfg/builder.py             runs process_graphs, records edge creation sites
  cfg/author_schema.py       creation site -> authors' edge names; attribute encoding
  labels/projection.py       node labels, contract labels, line-level subset
  features/tokens.py         CodeT5+ tokenizer features (512, float32)
  verify.py                  comparison with reference graphs
  store/io.py                pickle / JSON I/O, output layout
```

A new dataset is one `Dataset` entry in `datasets/registry.py`: where its corpus is,
how a contract gets its 0/1 target, which pinned sources it reads, and optionally
reference graphs and expected counts. A dataset assembled from several sources also
has a committed composition document.

## Dataset B

Built from the paper's second corpus (Sec. 5.1, Table 2): the paper's DAppSCAN and
SolidiFI buggy contracts, each buggy source 1:1 with clean contracts of its own kind.
The authors did not release the mixture; `datasets/dataset_b.py` composes it and
`datasets/dataset_b.json` freezes it (every contract with its source, path, SHA-256,
target, project and clean pairing, and every candidate left out with the reason).
Sources, all pinned in `sources/repos.py`:

| Source | Repository | What it provides |
|---|---|---|
| DAppSCAN | MANDO-Project/DASP-DAppSCAN-datasets (authors' release) | cleaned sources, line labels, `DASP_to_SWC.json`, per-category file lists |
| SolidiFI | DependableSystemsLab/SolidiFI-benchmark | injected bugs and BugLogs (Dataset A's folders) |
| SmartBugs Wild | MANDO-Project/ge-sc, `data/smartbugs-wild-clean-contracts` | the paper's 2,742 SmartBugs Wild contracts no SmartBugs tool flags |

**Buggy side: the paper's.**

- The authors' per-category lists repeat a file once per labelled weakness. Without
  repeats they hold **614** files, the paper's "614 buggy solidity files".
- Table 2's buggy count of every category is that list **plus exactly 50**, the size of
  each SolidiFI folder: 72+50=122, 136+50=186, 108+50=158, 76+50=126, 113+50=163,
  36+50=86, 73+50=123.
- So every category holds its distinct DAppSCAN files and all 50 SolidiFI contracts.
  17 DAppSCAN category entries (15 files) are left out with the reason: 11 files
  crash inside the authors' builder (`UnboundLocalError` in its loop handling, one
  `AttributeError` in its call-graph code), 2 cannot be read by the DFG front end
  that NodeSem and EdgeSem use (a parser error; an ambiguous multi-line string) and 2
  contain a guard EdgeSem cannot place on a graph node (a `do ... while` condition,
  for which the authors' builder has no node; EdgeSem refuses a task with one). Six
  categories hold 2-5 buggy contracts fewer than Table 2; time manipulation matches.

**Clean side: counterparts per buggy source (not the paper's).** The paper draws every
clean contract from SmartBugs Wild, but that pool holds only Solidity 0.4/0.5 (1,801
and 794 files, 147 without a pragma) while 45-77% of each category's DAppSCAN files
are 0.6-0.8. With it, `pragma >= 0.6` alone predicts the target (63-80 Buggy-F1 on
DAppSCAN vs clean, no model). So:

- **DAppSCAN-clean** (as many as the category's DAppSCAN files): files of the release
  not listed for the category and without a labelled line of its SWC ids, i.e. files
  whose audit reported no such weakness. A weaker negative than a verified clean
  contract, but the same projects, era and style. The pragma rule now scores 41-65
  Buggy-F1 on DAppSCAN vs DAppSCAN-clean, at or below calling everything vulnerable
  (66.7).
- **SmartBugs-Wild-clean** (50 per category): the counterparts of SolidiFI.
- Every DAppSCAN row (buggy or clean) records its audited `project`, the report folder
  of the release (`DAppSCAN-source/contracts/<project>/...`); the grouped folds keep a
  project on one side (`dfg.train.splits`, project pairs). Rows of a clean source carry
  `pairs_with`, and the benchmark scores each buggy source against its own
  counterparts (`benchmark.evaluate.by_source`).
- Clean files are drawn in seeded order per category; files a stage cannot read and
  text duplicates of a file already taken are skipped and the next one drawn.

**Labels.** DAppSCAN files carry the authors' line labels of the category's SWC ids on
their cleaned source; SolidiFI files their BugLog intervals. Node labels use the
`statement` rule (`labels/projection.py`): the endpoint hits of Dataset A's rule, and
for an annotated line no endpoint hits, the smallest statement containing it, else the
declaration whose signature contains it. DAppSCAN audits label lines inside multi-line
statements and signatures, which the endpoint rule reaches only 65-80% of:

| | endpoint rule | + statement | + signature | vulnerable nodes added |
|---|---|---|---|---|
| DAppSCAN annotated lines reached | 64.8-80.0% | 81.1-98.1% | 88.5-98.9% | 0-9 per category |

The nodes themselves barely change: the missed lines mostly belong to nodes another
annotated line already marks. The 1-12% still unreached are body lines without a
node of their own (`emit`, `assembly`/`unchecked` blocks, closing braces): a gap of the
authors' graph builder, not of the labelling. Each build records the lines every step
reached in `manifest.json` (`annotated_lines_reached`, overall and per source).

**Other notes.**

- Corpus copies have LF line endings: the SmartBugs Wild pool files are CRLF, and the
  authors' Dataset A corpus holds the same files converted (422 of 423).
- try/catch (Solidity >= 0.6) creates edges Dataset A never has; their names are
  inferred (`cfg/author_schema.py::INFERRED_SITES`: `next_line` as HGT edge type)
  rather than verified against the authors' graphs. Dataset A is unaffected.
- Built 1,894 contracts (Table 2: 1,928), 301,439 nodes (226,940; the clean side
  differs from the paper's) and 49,869 vulnerable nodes (59,183, -16%; per category
  -31% to -4%; how the paper projected DAppSCAN labels onto nodes it does not say).
- Identical texts under different DAppSCAN paths (a file in several audited
  snapshots of one project) are kept, as in the paper; the grouped protocol keeps
  them, and every project, on one side of a fold.

`python -m hcg compose --dataset B` rewrites the composition from the pinned sources;
`tests/hcg/test_dataset_b.py` checks that this reproduces the committed file.

## Equivalence with the authors' graphs (Dataset A)

Every category, rebuilt from `experiments/ge-sc-data/source_code/<category>/source_files`,
is identical to `data/upstream_mando_llm/graph_detection/<category>_tree_sitter_cfg_cg_compressed_graphs.gpickle`
once contracts are aligned by name: all nodes and node attributes (`code`, `label`,
`method`, `type_label`, `node_type`, `node_source_code_lines`, `source_file`), all edges with all
attributes and multiplicities, the graph attribute, and `graph_labels.json`. The
contract order differs (theirs is directory order, ours is sorted by name).

How the format was recovered:

- **Edge names.** The released `CFG_solidity.py` (here and in the authors' TOSEM-release
  branch) emits plain `next` for most control flow; the authors' graphs use
  `next_line`, `first_next_line`, `pos_next`, `neg_next`, `end_if`. The builder records
  the line of `CFG_solidity.py` that creates each edge; each (line, emitted name) maps
  to exactly one authors' `(controlflow_type, edge_type)` over 248,000 edges in seven
  categories (`cfg/author_schema.py::SITE_TABLE`). The table is tied to the pinned file
  (SHA-256 checked); an edge from a line not in the table stops the build.
- **Attributes** are stored as a DOT round trip leaves them: strings quoted with `"`
  and newlines escaped, line coverage `[[first, last]]`, `end_if`/`end_loop` reduced to
  their zero-based root marker, string multi-edge keys, graph name `G`.
- `process_graphs/` is not modified (DFG v2, NodeSem and EdgeSem import it, and its
  narrow `end_if` span fix stays in place for them); hcg converts its output.

## Labels

Public-annotation policy of `Test_code/label_pipeline` (2026-10-10), ported unchanged:
contract targets from the dataset's rule (Dataset A: SolidiFI `buggy_N.sol` and SmartBugs
files with a target-category record; identical to the authors' labels in all seven
categories); node labels from the endpoints of each node intersected with target-category
annotations projected into preprocessed lines. Reproduced exactly per category:
`annotations_preprocessed.json`, and the set of nodes whose label differs from the
authors' (137 / 327 / 0 / 491 / 216 / 220 / 91 nodes; positives 3114 / 5722 / 4106 /
10889 / 6784 / 6020 / 2435 in alphabetical category order).

## Not covered

- The training stages (`dfg`, `nodesem`, `edgesem`, `benchmark`) have been run on
  Dataset A only; Dataset B's graphs are in the same format but untested there.
- Token features follow the specification recorded in `scripts/DFG/dfg_v2/RECON.md`;
  they were not compared with the frozen local token files, which are not in git.
