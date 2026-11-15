"""Audit CP1 sample cases: seals, plan candidate sets, attempt ordering and outcomes.
Usage: verify_cp1_cases.py <cases_dir> <repo> <out.json>"""
import collections, hashlib, json, os, sys
C, repo, outp = sys.argv[1:4]
A = os.path.join(repo, "compile_repair/artifacts")
V = lambda s: tuple(int(x) for x in s.split("."))
recon = json.load(open(os.path.join(A, "cp0_v2/recon.json")))
by_path = {x["path"]: x for x in recon["inputs"]}
acc = {json.loads(l)["case"].split("/")[-1]: json.loads(l) for l in open(os.path.join(A, "cp1_sample_v1/acceptance.jsonl"))}
out = collections.OrderedDict(); st = collections.Counter(); problems = []; jobs = []
for case in sorted(os.listdir(C)):
    d = os.path.join(C, case)
    seal = json.load(open(os.path.join(d, "seal.json")))
    files = seal.get("files") or {}
    for f, v in files.items():
        h = v["sha256"] if isinstance(v, dict) else v
        p = os.path.join(d, f)
        if not os.path.exists(p) or hashlib.sha256(open(p, "rb").read()).hexdigest() != h:
            problems.append([case, "seal", f])
    st["seal_files"] += len(files)
    trust = json.load(open(os.path.join(d, "trust.json")))
    res = json.load(open(os.path.join(d, "units/input_0001/result.json")))
    rec = json.load(open(os.path.join(d, "units/input_0001/input_record.json")))
    rel = os.path.relpath(rec["path"], "/home/zhao/SmartContract/ge-sc-llm-compile")
    x = by_path[rel]
    plan = res["plan"]
    ordered = ([plan["priority"]] if plan["priority"] else []) + [v for g in plan["groups"] for v in g]
    # supported set from the actual compilers the case recorded in its seal tools
    tools = seal.get("tools") or {}
    comp = tools.get("compilers") or {}
    supported = sorted((v for v in comp if (0, 4, 12) <= V(v) < (0, 9, 0)), key=V)
    st["supported_92"] += len(supported) == 92
    iv = x["interval"]
    if iv and not plan["override"]:
        want = [v for v in supported if V(v) >= max(tuple(iv[0]), (0, 4, 12)) and V(v) < tuple(iv[1])]
        if sorted(set(ordered), key=V) != want:
            problems.append([case, "candidate_set", rel, len(ordered), len(want)])
    # attempts follow ordered candidates; all but last failed
    seen = []
    for i, a in enumerate(res["attempts"]):
        if not seen or seen[-1] != a["version"]:
            seen.append(a["version"])
        ok = a["solc"]["returncode"] == 0 and a["slither"] and a["slither"].get("d3")
        last = i == len(res["attempts"]) - 1
        if ok and not last:
            problems.append([case, "success_not_last", a["version"]])
        if res["status"] == "success" and last and not ok:
            problems.append([case, "last_not_success"])
        if a["settings"]:
            st["settings_attempts"] += 1
    if seen != ordered[:len(seen)]:
        problems.append([case, "attempt_order", seen[:5], ordered[:5]])
    sel = res["selected_version"]
    st[res["status"]] += 1
    st["solc_calls"] += len(res["attempts"])
    st["slither_calls"] += sum(1 for a in res["attempts"] if a["slither"])
    if sel:
        if iv and not (tuple(iv[0]) <= V(sel) < tuple(iv[1])):
            problems.append([case, "outside_interval", sel])
        if V(sel) < (0, 4, 12):
            problems.append([case, "below_floor", sel])
        if sel == x["selection"]["ascending"]:
            st["same_as_cp0"] += 1
        else:
            st["differs_from_cp0"] += 1
            out.setdefault("differences", []).append({"case": case, "path": rel, "cp0": x["selection"]["ascending"], "cp1": sel,
                "cp0_inventory_had": sel in (recon.get("compilers") or [])})
    st["flags:" + ",".join(sorted(res["flags"]))] += 1
    jobs.append({"case": case, "path": os.path.join(repo, rel), "ordered": ordered, "status": res["status"],
                 "selected": sel, "attempted": seen, "reason": res["reason"]})
    if acc[case]["selected_version"] != sel or acc[case]["path"] != rel:
        problems.append([case, "acceptance_mismatch"])
out["stats"] = dict(st); out["problems"] = problems
json.dump(jobs, open(outp, "w"))
print(json.dumps(out, indent=1))
