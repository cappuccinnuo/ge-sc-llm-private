"""CP5 §0. Compare each checked CP4 base to itself and stop on the first mismatch."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

from compile_repair.evaluation import benchmark

OUT = Path(__file__).resolve().parent
ART = OUT.parent
CATALOG = ART / "cp4_v1/bases.jsonl.gz"
PREVIOUS = ART / "cp4_5_v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked(path, digest):
    raw = Path(path).read_bytes()
    if sha(raw) != digest:
        raise ValueError("SHA256 mismatch for " + str(path))
    return raw


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open("x", encoding="utf8") as fp:
        json.dump(value, fp, ensure_ascii=False, sort_keys=True, indent=2)
        fp.write("\n")


def rejected_history():
    """Report the first and accepted runs separately; migrations have two proofs."""
    batch = read(PREVIOUS/"seal.json")["batch"]
    result = {}
    for run in ("", "continuation/"):
        records = {}
        for mode,expected in (("exact",14196),("moves",200),("migration",114)):
            filename = run + mode + ".jsonl.gz"
            raw = checked(PREVIOUS/filename,batch[filename])
            counts, causes, migrations = Counter(), Counter(), Counter()
            n = 0
            for line in gzip.decompress(raw).splitlines():
                s = json.loads(line)["score"]
                proof = s["counter_correspondence"]
                counts[proof["status"]] += 1
                if proof["status"] == "rejected":causes[proof["reason"]] += 1
                if mode == "migration":migrations[s["migration_counters"]["status"]] += 1
                n += 1
            assert n == expected
            records[mode] = dict(rows=n, status=counts, rejected=counts["rejected"], reasons=causes,
                                 migration_full_status=migrations, sha256=batch[filename])
        result[run.rstrip("/") or "first"] = records
    write(OUT/"historical_status.json", result)


def diagnose(graph, sources):
    graph,_ = benchmark._comparison_graph(graph, {}, True)
    expected = benchmark._nodes(graph)
    facts = {key:benchmark._ordinary_node_names(key,key,row,row,{},None,sources,sources) for key,row in expected.items()}
    _,disputed,_ = benchmark._definition_anchors(facts)
    details = defaultdict(list)
    for key, node in expected.items():
        for index,op in enumerate(node["ir"]):
            name = benchmark._ordinary_definition(op,node["ir"],index)
            identity = (key[0] if name and name.startswith("switch_expr_") else None,name)
            if identity in disputed:
                # The source corpus is local-only; keep instruction hashes and generated binding identities.
                match = benchmark._COUNTER_DEFINITION.match(op)
                kind = match[0].split()[-1] if match else "switch_definition"
                details[identity].append(dict(file=key[0],key5=key[1],ir_index=index,operator=kind,sha256=sha(op.encode())))
    return [dict(scope=k[0],name=k[1],definitions=details[k]) for k in sorted(disputed,key=str)]


def main():
    start = time.monotonic()
    info = read(ART/"cp4_v1/seal.json")["artifacts"][CATALOG.name]
    raw = checked(CATALOG,info["sha256"])
    bases = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    assert len(raw)==info["bytes"] and len(bases)==len({r["unit_id"] for r in bases})==16136
    code = Path(benchmark.__file__)
    digest = read(PREVIOUS/"seal.json")["deliverables"]["evaluation/benchmark.py"]
    checked(code,digest)
    n = 0
    counts = Counter()
    mismatch = None
    output = OUT/"self_scores.jsonl.gz"
    with output.open("xb") as file, gzip.GzipFile(fileobj=file,filename="",mode="wb",mtime=0) as stream:
        for base in bases:
            g = json.loads(checked(base["graph_path"],base["graph_sha256"]))
            result = json.loads(checked(base["result"]["result_path"],base["result"]["result_sha256"]))
            attempt = result["attempts"][-1]
            assert result["status"]=="success" and attempt["solc"]["returncode"]==0 and attempt["slither"]["d3"]
            content = benchmark.base_contents(base)
            score = benchmark.score_graphs(g,g,content,content,content,{},{},0,True)
            proof = score["counter_correspondence"]
            counts[proof["status"]] += 1
            n += 1
            row = dict(ordinal=n,unit_id=base["unit_id"],corpus=base["corpus"],graph_sha256=base["graph_sha256"],
                       result_sha256=base["result"]["result_sha256"],score=score)
            stream.write((json.dumps(row,sort_keys=True,separators=(",",":"))+"\n").encode())
            if (not score["exact"] or proof["status"]!="identical" or
                    proof["nodes"]["name_mismatch"] or proof["nodes"]["disputed"]):
                mismatch = dict(row, disputed_bindings=diagnose(g,content), graph_path=base["graph_path"])
                write(OUT/"self_mismatch.json",mismatch)
                break
            if n % 1000 == 0:print(n,flush=True)
    summary = dict(expected=16136,checked=n,passed=n-int(mismatch is not None),untested=16136-n,status_counts=counts,
                   stopped_at=mismatch and mismatch["unit_id"],base_catalog_sha256=info["sha256"],scorer_sha256=digest,
                   stream_sha256=sha(output.read_bytes()),no_compilation=True,elapsed_seconds=round(time.monotonic()-start,3))
    write(OUT/"self_summary.json",summary)
    print(summary,flush=True)
    return 2 if mismatch else 0

if __name__ == "__main__":
    rejected_history()
    sys.exit(main())
