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

The paper's second corpus (Sec. 5.1, Table 2): DAppSCAN and SolidiFI buggy contracts
mixed with clean SmartBugs Wild contracts at 1:1. The authors did not release the
mixture; `datasets/dataset_b.py` reconstructs it and `datasets/dataset_b.json` freezes
it (every contract with its source, path, SHA-256 and target, and every candidate
left out with the reason). Sources, all pinned in `sources/repos.py`:

| Source | Repository | What it provides |
|---|---|---|
| DAppSCAN | MANDO-Project/DASP-DAppSCAN-datasets (authors' release) | cleaned sources, line labels, `DASP_to_SWC.json`, per-category file lists |
| SolidiFI | DependableSystemsLab/SolidiFI-benchmark | injected bugs and BugLogs (Dataset A's folders) |
| clean | MANDO-Project/ge-sc, `data/smartbugs-wild-clean-contracts` | the paper's 2,742 SmartBugs Wild contracts no SmartBugs tool flags |

How the composition follows from the paper's numbers:

- The authors' per-category lists repeat a file once per labelled weakness. Without
  repeats they hold **614** files, the paper's "614 buggy solidity files".
- Table 2's buggy count of every category is that list **plus exactly 50**, the size of
  each SolidiFI folder: 72+50=122, 136+50=186, 108+50=158, 76+50=126, 113+50=163,
  36+50=86, 73+50=123.
- So every category holds its distinct DAppSCAN files, all 50 SolidiFI contracts and
  as many clean contracts. The paper does not say which clean contracts; they are
  drawn in a seeded order from the 2,742 (per category, as in Dataset A, whose clean
  contracts all come from this pool).
- 13 DAppSCAN category entries (11 files) crash inside the authors' builder
  (`UnboundLocalError` in its loop handling, one `AttributeError` in its call-graph
  code) and are left out with the reason, so six categories hold 2-8 contracts fewer
  than Table 2; time manipulation matches exactly.
- try/catch (Solidity >= 0.6) creates edges Dataset A never has; their names are
  inferred (`cfg/author_schema.py::INFERRED_SITES`: `next_line` as HGT edge type)
  rather than verified against the authors' graphs. Dataset A is unaffected.
- Labels: DAppSCAN files carry the authors' line labels of the category's SWC ids on
  their cleaned source; SolidiFI files their BugLog intervals; node labels follow the
  same endpoint rule as Dataset A.
- Against Table 2: built 1,902 contracts vs 1,928, 264,181 nodes vs 226,940 (+16%),
  49,855 vulnerable nodes vs 59,183 (-16%); per category nodes -5% to +33%,
  vulnerable nodes -31% to -4%. The node totals
  depend on which clean contracts are drawn, which the paper does not give; how it
  projected DAppSCAN labels onto nodes it does not say either.
- Identical texts under different DAppSCAN paths (a file in several audited
  snapshots of one project) are kept, as in the paper; evaluations should keep
  them on one side of a fold (the grouped protocol groups them).

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
