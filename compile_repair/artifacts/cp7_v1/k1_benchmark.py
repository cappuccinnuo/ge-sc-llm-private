"""CP7 K1 benchmark: does a correct documentation section reach the top k? (PROMPTS 4.7)

Usage: python -B k1_benchmark.py <docs root> <cp4 sample_receipts.jsonl.gz> <out.json> [--split dev]
Queries are the recorded first error lines of the included CP4 samples (artifacts/cp4_v1);
operators without a K1 truth (evaluation/report.py K1_TRUTH) are not scored. A sample is
scored only when its version's docs contain a correct section. k is chosen on dev.
"""
import collections
import gzip
import json
import sys
from pathlib import Path

from compile_repair.evaluation.report import K1_TRUTH, choose_k, hit_rates, k1_correct, receipt_queries, retrieval_hits
from compile_repair.rag.knowledge import KnowledgeBase, documentation_entries

KS = (1, 2, 3, 5, 8, 10)
docs, receipts_path, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
splits = {sys.argv[sys.argv.index("--split") + 1]} if "--split" in sys.argv else {"dev", "test"}
kb = KnowledgeBase(documentation_entries(docs))
with gzip.open(receipts_path, "rt", encoding="utf8") as fp:
    receipts = [json.loads(line) for line in fp]
samples = [s for s in receipt_queries(receipts, [p.name for p in docs.iterdir()]) if s["split"] in splits]
with_truth, skipped = [], collections.Counter()
for s in samples:
    if s["operator"] not in K1_TRUTH:
        skipped["no_k1_truth"] += 1
    elif not any(s["query"].version in e.versions and k1_correct(e, s["operator"]) for e in kb.by_source["K1"]):
        skipped["no_correct_section_in_version_docs"] += 1
    else:
        with_truth.append(s)
ranks = retrieval_hits(kb, with_truth, lambda entry, sample: k1_correct(entry, sample["operator"]), "K1", KS[-1])
rates = hit_rates(ranks, KS)
result = dict(k1_entries=len(kb.by_source["K1"]), vocabulary=len(kb.vocabulary), scored=len(ranks),
              skipped=dict(skipped), ks=KS, chosen_k=choose_k(rates, KS) if "dev" in splits else None, rates=rates)
out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf8")
print(json.dumps(dict(scored=len(ranks), skipped=dict(skipped), chosen_k=result["chosen_k"],
                      all={k: v for k, v in rates["all"].items()}), sort_keys=True))
for op in sorted(rates):
    if op != "all":
        print(op, {sp: (c["samples"], c["hit@1"], c["hit@5"], c["hit@10"]) for sp, c in rates[op].items()})
