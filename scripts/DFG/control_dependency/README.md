# Restricted control-dependence extension

Implemented by Codex. This is a sidecar to the frozen HCG + four DDG relation
pipeline. It only proposes `CONTROL_DEPENDENCE` facts; its virtual CFG nodes and
exits never become HCG nodes. No labels, features, predictions or vulnerability
categories participate in semantic analysis.

## Core API

```python
from scripts.DFG.state.stage_k.profile import SupportedSourceView
from scripts.DFG.control_dependency.analysis import analyze_view
view = SupportedSourceView(source, file, metadata)
results = analyze_view(view)
```

Each `ControlResult` is `analyzed` with an analysis IR and facts, or
`function_fallback` with `ir=None` and `facts=[]`. Every fact carries exact raw
AST spans, source SHA, function identity, branch role, a valid CFG witness, and
modifier context where applicable. Projection/fusion is independent of the
analysis. A missing exact HCG endpoint is audited; it is never guessed from the
nearest line. Failed analysis never deletes a sample or its existing DDG edges.

## Supported semantics

- Closed same-source scope and bounded inheritance reuse Stage J's declaration
  evidence and Stage K's supported version interval; no invented exact compiler.
- A separate declaration-only lexical table accepts reference-typed parameters
  for binding checks, without extending the scalar DDG or inferring new dataflow.
- Confirmed builtin `require` / `assert`, ordinary `if` / `else`, early return,
  confirmed revert/selfdestruct/suicide, and the existing single parameterless
  straight-line prefix modifier subset.
- Explicit normal and exceptional exits join an analysis-only unified EXIT.
- Known address call/send/staticcall return a success flag; transfer has an
  explicit exceptional outcome. Known user-function/function-pointer declarations
  are atomic opaque may-return/may-revert calls, never guard sources. Calls in
  predicates/arguments needing expression sequencing are conservatively rejected.
- Literal `true` and `false`, possibly parenthesized, prune impossible branches.
  No general expression solving or path feasibility inference is performed.
- Direct edge/postdominator control dependence. No transitive closure is added.
  An ordinary `if` does not control statements after its normal merge unless an
  actual exit path makes those statements control-dependent.

## Explicit limits

This is an **explicit-control** model, not a complete EVM exception CFG. Implicit
exceptions from gas, bounds and arithmetic are outside its profile. Known opaque
calls have no body or nontermination summary. Loops, try/assembly, unresolved
imports/callees, ambiguous overloads, effectful short circuit and unsupported
modifier contexts fall back by function. No full Solidity binding/type system is
claimed. Branch polarity remains evidence only, not a new HGT edge feature.

The installed grammar incorrectly groups the surface form
`!msg.sender.send(amount)` as `(!msg.sender).send(amount)`. This form remains an
explicit fallback. The separate spelling `!(msg.sender.send(amount))` is tested
and supported. The implementation does not repair source text or guess the AST.

## Validation

```bash
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
conda activate mando
python -B -m unittest scripts.DFG.control_dependency.tests.test_semantics -v
```

Core implementation run: 38 passed, 0 failed, 0 skipped, no warnings. This does
not replace the parent task's combined projection/model/project regression run.
All Solidity fixtures are parser/source-level tests; **no solc compilation or
exploitability validation was executed**. Initial test failure and the parser
probe are recorded as execution observations, not fabricated original logs, in
`../experiments/artifacts/guard_extension_v1/semantic_implementation_notes.json`.
