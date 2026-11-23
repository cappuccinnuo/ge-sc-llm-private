"""Read back the CP5 stop point. No registry or compiler calls."""
import ast
import base64
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
MOD = ROOT/"compile_repair"
BASE = "26f44492c093311257f7b3de41ba3bee2e703ea3"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def functions(raw):
    tree = ast.parse(raw)
    entries = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            entries[node.name] = node
        if isinstance(node, ast.ClassDef):
            entries.update({node.name + "." + f.name: f for f in node.body if isinstance(f, ast.FunctionDef)})
    return entries


def previous(path):
    ref = BASE+":"+path.relative_to(ROOT).as_posix()
    r = subprocess.run(["git", "show", ref], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return r.stdout if r.returncode == 0 else b""


def main():
    artifacts = OUT/"d23"
    approval = read(artifacts/"authorization.json")
    request = read(OUT/"d23_download_request.json")
    assert digest((OUT/"d23_download_request.json").read_bytes()) == approval["request_sha256"]
    receipts = list(map(json.loads, (artifacts/"download.jsonl").read_bytes().splitlines()))
    stop = read(artifacts/"transport_stop.json")
    assert digest((artifacts/"download.jsonl").read_bytes()) == stop["prior_journal_sha256"]
    assert digest((artifacts/"download.log").read_bytes()) == stop["prior_log_sha256"]
    root = Path(approval["storage"])
    named = [(n,v) for n,p in request["by_package"].items() for v in p["releases"]]
    assert len(named) == 172 and len(receipts) == stop["verified_releases"]
    actual = []
    for (package, release), r in zip(named, receipts):
        assert (r["package"],r["version"]) == (package,release["version"]) and r["url"] == release["registry_url"]
        p = Path(r["path"])
        assert p.resolve().parent == root/"archives" and p.is_file()
        raw = p.read_bytes()
        assert len(raw) == r["packed_bytes"] <= approval["per_release_packed_limit_bytes"]
        assert r["verified"] and r["http_status"] == 200 and digest(raw) == r["sha256"]
        sri = "sha512-"+base64.b64encode(hashlib.sha512(raw).digest()).decode()
        assert sri == r["expected_integrity"] == r["integrity"] == release["integrity"]
        actual.append(p)
    assert set(actual) == set((root/"archives").iterdir())
    total = sum(r["packed_bytes"] for r in receipts)
    assert total == stop["verified_packed_bytes"] <= approval["total_packed_limit_bytes"]
    paths = sorted(p for p in MOD.rglob("*.py") if not {"artifacts","tests","docs"}.intersection(p.relative_to(MOD).parts))
    assert len(paths) == 18
    changed = {}
    for p in paths:
        before, after = previous(p), p.read_bytes()
        if before == after:
            continue
        left,right = functions(before),functions(after)
        names = sorted(k for k in left.keys() | right.keys()
                       if k not in left or k not in right or ast.dump(left[k]) != ast.dump(right[k]))
        additions = removals = 0
        for tag, a, b, c, d in difflib.SequenceMatcher(None,before.splitlines(),after.splitlines(),autojunk=False).get_opcodes():
            if tag != "equal":
                additions += d-c
                removals += b-a
        changed[p.relative_to(MOD).as_posix()] = dict(added_lines=additions,removed_lines=removals,functions=names,
                                                      sha256=digest(after))
    allowed = {"pipeline.py","cli.py","toolchain/project.py","rules/dependencies.py","evaluation/report.py","evaluation/benchmark.py"}
    assert set(changed) == allowed
    assert set(changed["evaluation/benchmark.py"]["functions"]) == {"dependency_repair_observation","environment_observation"}
    frozen = read(OUT.parent/"cp3_continue_v1/baseline.json")["code_refs"]
    mando = "/home/zhao/miniconda3/envs/mando/bin/python"
    now = json.loads(subprocess.check_output([mando,"-B","-c",
        "import json;from scripts.DFG.dfg_v2.experiment.run import _code_refs;print(json.dumps(_code_refs()))"], cwd=ROOT))
    assert now == frozen
    reference = OUT.parent/"cr_store_mando_v5"
    ref_seal = read(reference/"seal.json")["files"]
    replay = read(OUT/"mando_regression.json")
    assert replay["passed"]
    units = list(map(json.loads, (OUT/"mando_regression.jsonl").read_bytes().splitlines()))
    assert len(units) == 846 and all(u["passed"] for u in units)
    good = [u for u in units if u["status"] == "success"]
    assert len(good) == 843 and all(u["d3"] and not u["steps_2_to_4"] and
          u["graph_sha256"] == ref_seal["units/"+u["unit_id"]+"/graph.json"] for u in good)
    tests = {n:read(OUT/"implementation_checks"/(n+"_tests.json")) for n in ("mando","production")}
    tests["dfg"] = read(OUT/"dfg_tests.json")
    assert all(t["returncode"] == 0 for t in tests.values())
    scores = list(map(json.loads,(OUT/"dev_probes.jsonl").read_bytes().splitlines()))
    assert len(scores)==4 and all(s["split"]=="dev" and s["score"]["removed_by_repair"]==0 for s in scores)
    result = dict(status="partial_awaiting_two_decisions", base=BASE, code=changed, modules=len(paths),
                  unchanged_dfg_refs=len(frozen), frozen_scoring_functions_unchanged=True,
                  releases_verified=len(actual), packed_bytes=total, remaining=len(named)-len(actual),
                  verified_release_elapsed_seconds=round(sum(r["elapsed_seconds"] for r in receipts),3),
                  mando_graphs_equal=len(good), mando_historical_failures=len(units)-len(good),
                  tests=tests, dev_probe_statuses=dict(Counter(s["status"] for s in scores)),
                  llm_calls=0, cost_usd=0)
    with (OUT/"checkpoint_audit.json").open("x",encoding="utf8") as fp:
        json.dump(result,fp,indent=2,ensure_ascii=False,sort_keys=True)
        fp.write("\n")
    print(result["status"],len(actual),total,len(good),len(frozen),len(paths))


if __name__ == "__main__":
    main()
