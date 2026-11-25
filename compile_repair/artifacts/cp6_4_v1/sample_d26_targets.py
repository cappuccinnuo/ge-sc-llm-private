"""Per-project sample of the D26 targets that the first local run did not reach (PROMPTS r2.34).

Usage: python -B sample_d26_targets.py <targets.json> <d26_observed_units.jsonl.gz> <per project> <out.json>
Frequency is judged by distinct projects, so each project root contributes at most N units
(in selector order) beyond those already observed. A unit whose entry SHA-256 and path inside
its project equal a unit of another corpus already kept (the Trace copy of a DAppSCAN audit)
is a duplicate and is skipped.
"""
import collections
import gzip
import json
import sys
from pathlib import Path

targets = json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
with gzip.open(sys.argv[2], "rt", encoding="utf8") as fp:
    observed = {json.loads(line)["unit_id"] for line in fp}
limit, out = int(sys.argv[3]), Path(sys.argv[4])
seen_content, taken, kept, skipped = set(), collections.Counter(), [], collections.Counter()
for target in targets:
    inside = Path(target["path"]).relative_to(target["project_root"]).as_posix()
    content = (Path(target["project_root"]).name, inside, target["sha"])
    if target["unit_id"] in observed:
        seen_content.add(content)
        skipped["already_observed"] += 1
        continue
    if content in seen_content:
        skipped["duplicate_of_another_corpus"] += 1
        continue
    seen_content.add(content)
    if taken[target["project_root"]] >= limit:
        skipped["beyond_per_project_limit"] += 1
        continue
    taken[target["project_root"]] += 1
    kept.append(target)
out.write_text(json.dumps(kept, indent=1) + "\n", encoding="utf8")
print(json.dumps(dict(sampled=len(kept), per_project=dict(taken), skipped=dict(skipped))))
