"""Check the definition pattern against the sealed neutral-insertion fixture."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from compile_repair.evaluation.benchmark import _COUNTER_DEFINITION

out = Path(__file__).resolve().parent
prior = out.parent / "cp4_4_v1"
manifest = prior / "review_inputs.json"
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(manifest) == json.loads((prior / "seal.json").read_bytes())["batch"][manifest.name]
inputs = json.loads(manifest.read_bytes())["partial"]
scratch = Path("/home/zhao/SmartContract/compile-repair-local/cp4_4_v1/review/partial")
result = {}
for case in ("truth", "A"):
    path = scratch / case / "graph.json"
    assert sha(path) == inputs[case]["graph.json"]
    matches = defaultdict(list)
    for node in json.loads(path.read_bytes())["nodes"]:
        for index, op in enumerate(node["ir"]):
            match = _COUNTER_DEFINITION.match(op)
            if match:
                matches[match[1]].append(dict(key5=node["key5"], index=index, ir=op))
    result[case] = dict(graph_sha256=sha(path), repeated={k:v for k,v in matches.items() if len(v)>1})
record = dict(prompt="r2.21 §4.6f.2–3", evidence=result,
              request="In ordinary scores treat explicit SlithIR write-through annotations (->destination) on a REF lvalue as uses. Count real binding definitions separately and dispute genuine multiple definitions.")
with (out / "definition_request.json").open("x", encoding="utf8") as f:
    json.dump(record, f, ensure_ascii=False, indent=2)
    f.write("\n")
print({case:list(row["repeated"]) for case,row in result.items()})
