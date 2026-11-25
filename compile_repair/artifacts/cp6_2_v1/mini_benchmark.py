"""CP6 mini-benchmark: chosen CP4 operators on single-file DAppSCAN bases.

Usage: python -B mini_benchmark.py <bases.jsonl.gz> <DAppSCAN-source dir> <per operator> <output dir> <summary.json> <operator,...>
(CP6.2: unbalanced_structure)
For each operator, take the first single-file bases (CP4 base order) where the CP4
operator has a site, each distinct file content once (later bases with the same SHA-256
are listed as repeated_contents_skipped); truth = this pipeline's graph of the unchanged base; damage = CP4's
build_mutation; repair = the production pipeline; score = evaluation.benchmark.score_graphs. A repaired standalone unit is compiled as a
one-file project (filename input.sol); its graph is translated back with the benchmark's
_single_file_wrapper_graph, which rejects any other filename.
"""
import gzip
import hashlib
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from compile_repair.core.model import CompilationUnit, Patch, SourceFile  # noqa: E402
from compile_repair.core.provenance import apply_patches  # noqa: E402
from compile_repair.core.store import ArtifactStore  # noqa: E402
from compile_repair.evaluation.benchmark import (SourceLayout, _single_file_wrapper_graph, build_mutation,  # noqa: E402
    mutation_sites, score_graphs)
from compile_repair.pipeline import repair_unit  # noqa: E402
from compile_repair.toolchain.solc import load_trusted_compilers  # noqa: E402

# Swarm/IPFS hashes of solc metadata (bzzr0, bzzr1, ipfs) embedded anywhere in a bytecode literal.
_METADATA_HASH = re.compile(r"(a165627a7a72305820|a265627a7a72315820|a2646970667358221220)[0-9a-f]{64}")
OPERATORS = tuple(sys.argv[6].split(","))
RECORDED = "DAppSCAN@66a56619c44770e05c2db600fa6468115ff0dcd5/DAppSCAN-source/"
bases_path, corpus, per_op, out, summary_path = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
out.mkdir(parents=True, exist_ok=False)
compilers, _, _ = load_trusted_compilers()


def masked(graph):
    """Mask embedded metadata hashes; they depend on the source-unit name, not on code."""
    return dict(graph, nodes=[dict(n, ir=[_METADATA_HASH.sub(r"\1" + "0" * 64, op) for op in n["ir"]])
                              for n in graph["nodes"]])


def run(name, raw):
    path = out / name / "input.sol"
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    store = ArtifactStore(out / name / "run")
    record = repair_unit(CompilationUnit("u", (SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw),)),
                         compilers, store, io.StringIO())
    graph = store.path / "units/u/graph.json"
    return record, json.loads(graph.read_bytes()) if graph.exists() else None, path


rows, counts, seen, repeated = [], {op: 0 for op in OPERATORS}, set(), []
with gzip.open(bases_path, "rt") as fp:
    bases = [json.loads(line) for line in fp]
for base in bases:
    if all(n >= per_op for n in counts.values()):
        break
    if base["corpus"] != "DAppSCAN" or base["input_count"] != 1:
        continue
    entry = corpus / base["entry"].split(RECORDED, 1)[1]
    if not entry.is_file():
        continue
    raw = entry.read_bytes()
    # Distinct contents only: a file shared by several CP4 units is one sample, not several.
    digest = hashlib.sha256(raw).hexdigest()
    if digest in seen:
        repeated.append(dict(unit_id=base.get("unit_id"), entry_sha256=digest))
        continue
    seen.add(digest)
    sites = mutation_sites(dict(base, project_root=None), {"": raw}, {"": SourceLayout(raw)}, [])
    wanted = [op for op in OPERATORS if op in sites and counts[op] < per_op]
    if not wanted:
        continue
    truth_record, truth, _ = run(base["entry_sha256"][:16] + "/truth", raw)
    if truth is None:
        continue
    for op in wanted:
        damaged_files, patch, damage = build_mutation(dict(base, project_root=None), {"": raw}, sites[op], op)
        damaged = damaged_files[""]
        record, graph, path = run(base["entry_sha256"][:16] + "/" + op, damaged)
        row = dict(operator=op, entry_sha256=base["entry_sha256"], truth_version=truth_record.selected_version,
                   status=record.status, reason=record.reason, selected_version=record.selected_version)
        if graph is not None:
            proof = next(iter(record.provenance.values()))
            repaired, trace = apply_patches(damaged, tuple(Patch(c.start, c.end, c.old, c.new, c.step, c.round, c.reason)
                                                       for c in proof.changes))
            schema = graph.get("schema")
            if schema == "compile-repair-project-graph-v1":
                # A repaired standalone unit compiles as a one-file project whose single proven
                # source is standalone/input.sol; translate it back to the standalone keys.
                graph = _single_file_wrapper_graph(graph, "input.sol")
            score = score_graphs(truth, graph, {"": raw}, {"": damaged}, {"": repaired}, {"": damage}, {"": trace}, 0, True)
            hashed = score_graphs(masked(truth), masked(graph), {"": raw}, {"": damaged}, {"": repaired},
                                  {"": damage}, {"": trace}, 0, True)
            row.update(level=proof.level, exact=score["exact"], exact_masking_metadata_hash=hashed["exact"], kept=score["kept"], cfg_edges=score["cfg_edges"],
                       calls=score["calls"], lost=score["lost"], removed_by_repair=score["removed_by_repair"],
                       repair_equals_original=repaired == raw, repaired_schema=schema)
        rows.append(row)
        counts[op] += 1
        print(op, row["status"], row.get("exact"), flush=True)
summary = {op: dict(samples=sum(r["operator"] == op for r in rows),
                    success=sum(r["operator"] == op and r["status"] == "success" for r in rows),
                    exact=sum(r["operator"] == op and r.get("exact") is True for r in rows),
                    exact_masking_metadata_hash=sum(r["operator"] == op and r.get("exact_masking_metadata_hash") is True
                                                    for r in rows),
                    restored_bytes=sum(r["operator"] == op and r.get("repair_equals_original") is True for r in rows))
           for op in OPERATORS}
summary_path.write_text(json.dumps(dict(summary=summary, repeated_contents_skipped=repeated, rows=rows), indent=1) + "\n", encoding="utf8")
print(json.dumps(summary))
