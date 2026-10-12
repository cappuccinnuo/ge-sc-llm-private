#!/usr/bin/env bash
# Re-run the exact command that produced 99.0043, several times, to show how much of
# that figure is run-to-run variance rather than a different setup.
#
# Nothing is varied between runs: same graph file, same --seed 1. torch.manual_seed
# fixes the weight init and the KFold shuffle, but cuDNN kernel selection and the
# non-deterministic scatter-adds inside DGL's message passing are not pinned, so
# repeated runs do not land on the same number.
set -u
REPO=/home/zhao/SmartContract/ge-sc-llm
BASE="${REPO}/experiments/ge-sc-data/source_code/reentrancy"
N="${1:-3}"

for i in $(seq 1 "${N}"); do
  echo "--- run ${i}/${N} ---"
  bash "${REPO}/scripts/train_linelevel.sh" \
    "${BASE}/linelevel_tokenizer_ids.gpickle" inside_token "repeat_${i}" 2>&1 \
    | grep -E "Average (Buggy|Macro) F1"
done
