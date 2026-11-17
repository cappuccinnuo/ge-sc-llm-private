"""Read already-passed test evidence; archive CLI stores without rerunning tools."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(name, value):
    with (OUT / name).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def execute():
    equivalence = {}
    for mode in ("production", "mando"):
        receipt = json.loads((OUT / ("pytest_" + mode + ".json")).read_text())
        assert receipt["returncode"] == 0
        evidence = json.loads(gzip.decompress((OUT / ("test_evidence_" + mode + ".json.gz")).read_bytes()))
        found = {p:json.loads(raw) for p,raw in evidence.items()
                 if p.startswith("test_frozen_equivalence_all") and p.endswith("/equivalence.json")}
        assert len(found) == 2
        corpus = next(v for v in found.values() if v["compared"] == 846)
        fixtures = next(v for v in found.values() if v["compared"] != 846)
        assert fixtures["compared"] + len(fixtures["excluded"]) == len(list(
            (ROOT / "compile_repair/tests/fixtures").rglob("*.sol")))
        assert all(r["interval_equal"] and r["patches_equal"] for v in found.values() for r in v["records"])
        equivalence[mode] = dict(corpus=corpus, fixtures=fixtures, passed=True)
    assert equivalence["production"] == equivalence["mando"]
    write("equivalence.json", equivalence)
    receipt = json.loads((OUT / "pytest_production.json").read_text())
    temp = Path(receipt["temporary_directory"])
    stores = {}
    for kind, prefix, subdir in (("success", "test_real_byte_inputs_cli", "success"),
                                 ("unsupported", "test_real_union_stays", "unsupported")):
        folders = [p for p in temp.iterdir() if p.is_dir() and not p.is_symlink() and p.name.startswith(prefix)]
        assert len(folders) == 1
        stores[kind] = folders[0] / subdir
    members, rows = {}, []
    for kind, folder in stores.items():
        seal = json.loads((folder / "seal.json").read_text())
        for relative, expected in seal["files"].items():
            raw = (folder / relative).read_bytes()
            assert sha(raw) == expected, str(folder / relative)
            members[kind + "/" + relative] = raw
        members[kind + "/seal.json"] = (folder / "seal.json").read_bytes()
        for relative, expected in seal["implementation_sha256"].items():
            assert sha((ROOT / relative).read_bytes()) == expected
        records = [json.loads(line) for line in (folder / "manifest.jsonl").read_text().splitlines()]
        assert len(records) == (9 if kind == "success" else 1)
        for record in records:
            item = {k:record[k] for k in ("unit_id", "status", "selected_version", "settings", "flags")}
            item["input"] = record["inputs"][0]
            path = Path(item["input"]["path"])
            assert sha(path.read_bytes()) == item["input"]["sha256"]
            if kind == "success":
                last = record["attempts"][-1]
                assert last["solc"]["returncode"] == 0 and last["slither"]["d3"]
                assert last["slither"]["profile"] == "production"
                assert record["provenance"][str(path)]["level"] == "none"
                item.update(d3=True, compiler_sha256=last["solc"]["compiler"]["sha256"],
                            graph_sha256=sha((folder / "units" / record["unit_id"] / "graph.json").read_bytes()))
            else:
                assert record["flags"] == ["unsupported_version_constraints"]
                assert record["attempts"][0]["exception_type"] == "Unsupported"
                assert (folder / "invocations.jsonl").read_bytes() == b""
                item["expected_rejection"] = True
            rows.append(item)
    archive = OUT / "cli_probe_stores.tar.gz"
    with archive.open("xb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as zipped:
            with tarfile.open(mode="w", fileobj=zipped, format=tarfile.PAX_FORMAT) as tar:
                for name, raw in sorted(members.items()):
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = len(raw), 0o644, 0
                    tar.addfile(info, io.BytesIO(raw))
    expected = {p:sha(raw) for p, raw in members.items()}
    with tarfile.open(archive, "r:gz") as tar:
        observed = {m.name:sha(tar.extractfile(m).read()) for m in tar}
    assert observed == expected
    result = dict(passed=True, successful_cli_inputs=9, required_six_passed=True,
        unsupported_union=1, regression_6c_replays=0, rerun_count=0, rows=rows,
        archive_sha256=sha(archive.read_bytes()), archive_members=len(members),
        archive_readback_equal=True, member_sha256=expected, source_receipt="pytest_production.json",
        cost_usd=0, llm_calls=0)
    write("probes.json", result)
    print(json.dumps(dict(passed=True, corpus_equivalent=846, parseable_fixtures=fixtures["compared"],
                         excluded_fixtures=len(fixtures["excluded"]), cli_success=9, union_rejected=1,
                         versions={Path(r["input"]["path"]).name:r["selected_version"] for r in rows},
                         archive_members=len(members))), flush=True)


if __name__ == "__main__":
    execute()
