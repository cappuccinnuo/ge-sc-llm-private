# hcg: heterogeneous contract graphs from source

Upstream phase of the pipeline: raw Solidity → the graphs MANDO-LLM's HGT consumes,
for every vulnerability category of a dataset (Dataset A: all seven).

```bash
python -m hcg fetch                         # pinned SmartBugs + SolidiFI into data/ (or $MANDO_DATA_DIR)
python -m hcg build                         # Dataset A, all seven categories, with tokens
python -m hcg build --categories reentrancy --no-tokens
python -m pytest tests/hcg                  # unit tests; Dataset A tests need $MANDO_DATA_DIR
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

A build exits non-zero if its counts differ from the paper's Table 1 or if its
structure or contract labels differ from the authors' released graphs.

## Layout

```
hcg/
  __main__.py, pipeline.py   CLI; per-category orchestration and manifest
  datasets/registry.py       Dataset / Category; Dataset A and its contract-label rule
  sources/repos.py           pinned annotation repositories
  sources/annotations.py     SmartBugs / SolidiFI loading, preprocessing, projection
  cfg/builder.py             runs process_graphs, records edge creation sites
  cfg/author_schema.py       creation site -> authors' edge names; attribute encoding
  labels/projection.py       node labels, contract labels, line-level subset
  features/tokens.py         CodeT5+ tokenizer features (512, float32)
  verify.py                  comparison with reference graphs
  store/io.py                pickle / JSON I/O, output layout
```

A new dataset is one `Dataset` entry in `datasets/registry.py`: where its corpus is,
how a contract gets its 0/1 target, and optionally reference graphs and expected counts.

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

- DFG v2, NodeSem and EdgeSem still read the authors' graphs through their registered
  tasks (reentrancy and access control). Pointing them at these outputs and registering
  the other five categories is phase 2.
- Token features follow the specification recorded in `scripts/DFG/dfg_v2/RECON.md`;
  they were not compared with the frozen local token files, which are not in git.
