# Stage H2: complete E3a ablation

This runner uses H1's already saved E3a untrained states; it never prepares new
initializations, changes H1/G, or trains E2/E3b. Exactly 26 fresh fits plus four
audited Stage G fold0 references. Three-variant reporting covers 90 formal fits.

The H1-specific read-only archive verifier accepts archive descendant commits
only when sealed runtime source, inputs and receipts remain identical. The old
reserved H2 plan remains execution_authorized=false. This batch has its own
authorization, plan/seal and runtime binding.

Frozen per-task manifest values are authoritative:
contract initial_lr=.0005, max_lr=.01, weight_decay=5e-6;
node initial_lr=.0002, max_lr=.005, weight_decay=0.
Same original fit, adapter, full fixed graph, train supervision, 50-epoch maximum,
patience7/delta.001, strict minimum validation loss best. Last is separate.
All metrics are CV validation; node metrics count HCG nodes.
No automatic failure retry, CPU fallback or reduced graph/model.

## Commands

Run from ge-sc-llm-ddg-v11 in the existing mando environment:

~~~bash
export PYTHONPATH=/home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m scripts.DFG.experiments.e23_h2.control verify
python -u -B -m scripts.DFG.experiments.e23_h2.control run
python -B -m scripts.DFG.experiments.e23_h2.control summarize
~~~

The existing sealed batch must never be sealed again.
Successful verified fits are reused. Failed/partial attempts block continuation;
after investigation an explicitly authorized retry takes the exact identity:
--retry reentrancy_author_contract/fold_1/E3a
This reruns that whole fit from the original state; it is not an epoch resume.

Default output: ../artifacts/paper_kfold/stage_h2_v1/
The run's controller.log and each runs/task/fold/E3a/attempt_NNN.log can be
followed with tail -F. Model training is single GPU and serial.

report.py verifies frozen labels/identities independently and aligns predictions
by task, cohort, file and original node identity. Source SHA is retained in OOF
and file/error exports. E0/E1 remain historical references, not same-initialization
controlled contrasts. No seven-class or independent-test claim.
