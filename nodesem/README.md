# nodesem — node semantic features for HCG/DFG graphs

`nodesem` replaces the HGT input of each node (512 raw token IDs in MANDO-LLM) by
semantic features of the node's statement, and trains the same HGT over the
DFG-augmented graph with them. It reads the outputs of [`hcg`](../hcg/README.md) and
[`dfg`](../dfg/README.md).

| modality | dim | what it is |
|---|---:|---|
| `token_ids` | 512 | the HCG CodeT5+ token IDs (S0o raw Linear, S1o embedding bag) |
| `code` | 256 | CodeT5+ 110M embedding of the statement's exact AST text |
| `ctx` | 256 | the same encoder over CTX fields: definitions/uses, data-flow neighbours, state reads/writes, guards, calls, environment, function and contract summaries (256-token budget); `masked` replaces identifier spellings by binding roles |
| `static` | 245 | name-independent encoding of the statement facts (three-valued) |
| `teacher` | 384 | BGE embedding of a local LLM's description of the statement (summary + function intent) |
| `student` | 384 | per-fold MLP that predicts `teacher` from CTX + STATIC, so inference needs no LLM |

Configurations (`features.CONFIGS`):

| name | modalities | notes |
|---|---|---|
| S0o | token_ids | MANDO-LLM input (raw Linear) |
| S1o | token_ids | trainable 64-d token embedding bag |
| S2 | code | |
| S3 / S3m | code, ctx | S3m: masked CTX |
| S4 / S4m / S4g / S4-noG | code, ctx, static | m: masked CTX; g: gated fusion; noG: no HGT layers (G0 only) |
| S6 | S4 + teacher | upper bound with the LLM at inference |
| S5 | S4 + student | |
| S8 | S4 + student permuted within node types | control for S5 |

Every configuration runs on profile `G0` (HCG) and `G3R` (DFG L1–L3 + reverse).

## Layout

```
nodesem/
  inputs.py     task context: F0/F3 graphs, F3 layer audit, sources, recorded compiler versions
  text.py       CODE text per row
  facts/        statement facts: syntax (AST), cfg, guards, state (L2 evidence), summary,
                schema, extract (joins AST semantics with DFG evidence)
  context.py    CTX fields            static.py   STATIC vectors
  pipeline.py   analysis stage + stage functions writing the store
  store.py      per-task feature store (data/nodesem/...)
  encode.py     CodeT5+ / BGE encoders (pinned revisions)
  llm/          prompts, protocol + response cache, generate (llama.cpp), checks, post, teacher
  student.py    per-fold students
  features.py   specifications + carrier       model.py  adapters + model    init.py  initialization
  train.py      grouped nested CV on dfg.train
  __main__.py   CLI
```

## Usage

```bash
python -m hcg build && python -m dfg build      # prerequisites (with tokens, L1-L3)
python -m nodesem analyze                        # CPU, ~1-2 min per task
python -m nodesem encode                         # CodeT5+ (GPU recommended)
python -m nodesem describe --workers 4           # Qwen2.5-Coder-3B (GPU; hours for 7 classes)
python -m nodesem encode --teacher               # BGE
python -m nodesem train --configs S0o S2 S4 S6 S5 S8 --out runs/nodesem/all
python -m nodesem report runs/nodesem/all        # paired with S0o@G3R
```

`describe` needs `llama-cpp-python` built with CUDA and downloads the pinned GGUF
(`Qwen/Qwen2.5-Coder-3B-Instruct-GGUF`, q4_k_m, revision `f74adce6`, 2.1 GB). Responses
are cached per prompt in `data/nodesem/llm_cache/<key>/`; the key covers the prompt,
the GGUF SHA-256 and the decoding parameters. On reentrancy and access control the
prompts are identical to the earlier NodeSem run, so its cache
(`scripts/node_sem/artifacts/llm_v3/cache/describe_v2/` on the original machine)
can be copied into `llm_cache/` and is reused without regeneration.

- **Speed.** One process generates one response at a time, and with a 3B model most of
  each token is CPU-side work (JSON-schema constrained sampling, Python), so the GPU
  idles between tokens. `--workers N` runs N processes, each with its own model copy
  (about 3 GB of GPU memory each), on fixed shares of the pending prompts. A prompt's
  response does not depend on which worker or in which order it is generated, so the
  cache is the same for any N.
- **Interrupting.** Stop it at any time and rerun the same command. Sealed responses are
  reused as they are. A prompt cut off mid-generation has no sealed response: its
  directory is moved to `llm_cache/_interrupted/` and it is generated again from scratch.
  A lock file (`llm_cache/.lock`) keeps two runs off one cache.
- **`--limit N`** (smoke runs) generates at most N new responses. The teacher text is
  then partial: rows of prompts not generated yet are absent, and the store's summary
  records `teacher.complete: false`. The combined model refuses such a store unless
  `benchmark run --partial-teacher` is given.

Training uses `dfg.train` (folds, epoch engine, scoring). Per fold and profile every
configuration starts from the DFG fold initial state: graph and classifier tensors
are shared, input adapters are seeded from (fold seed, parameter, task, fold, profile,
spec); S5/S6/S8 take all S4 tensors from S4's initial state; S8 shares S5's
modality-dropout stream. Students are fitted per fold on that fold's inner split.

## Verification

`tests/nodesem/test_dataset_a.py` (needs `$MANDO_DATA_DIR`) checks, per category and task:

* the analysis stage equals the unmodified NodeSem producers on the same graphs
  (`reference/old_code.json`, all 14 tasks);
* reentrancy/access control against the sealed NodeSem artifacts (built from the
  authors' graphs): per-file code text, facts, CTX fields and STATIC vectors; every
  LLM prompt key is one of the 4,485 sealed keys (the union over the four tasks is
  exactly that set); fold-0 initial weights of S0o/S2/S4 × G0/G3R equal the sealed
  N-A digests.

Facts and CTX fields of 6 access-control nodes list state reads in a different order
than the sealed run: the order follows graph edge order, which depends on global node
ids. Their content is identical; the tests compare lists as multisets.

Encoders and the LLM run on a GPU in fp16 (as originally); vectors therefore match
earlier runs to fp16 precision, not bit for bit. Their code is unchanged from the
original NodeSem runs.
