"""Build complete implemented DDG profiles from fixed HCG and exact sources."""
import argparse
from pathlib import Path
from scripts.labeling_v2.safe_graph import read_graph
from . import PROFILES
from .pipeline import build_graph
from .io import read_sources, write_bundle, sha256


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph", required=True)
    p.add_argument("--source-manifest")
    p.add_argument("--profile", choices=sorted(PROFILES), default="full_guard")
    p.add_argument("--output", required=True)
    p.add_argument("--max-iterations", type=int, default=100000)
    args = p.parse_args(argv)
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError("Output already exists: " + str(output))
    if args.profile != "baseline" and not args.source_manifest:
        p.error("enhancement requires --source-manifest with path/SHA per file")
    path = Path(args.graph).resolve(); before = sha256(path)
    graph = read_graph(path)
    inputs = {"graph_path": str(path), "graph_sha256": before}
    sources, metadata, used, missing = {}, {}, {}, []
    if args.source_manifest:
        inputs.update(source_manifest_path=str(Path(args.source_manifest).resolve()),
                      source_manifest_sha256=sha256(args.source_manifest))
        sources, metadata, used, missing = read_sources(args.source_manifest, graph)
    inputs.update(sources=used, missing_sources=missing)
    print("Building {}: {} nodes, {} edges".format(args.profile,len(graph),graph.number_of_edges()),flush=True)
    result, audit = build_graph(graph, sources, args.profile, metadata, args.max_iterations)
    if sha256(path) != before:
        raise AssertionError("Input changed during build")
    for rec in used.values():
        if sha256(rec["path"]) != rec["sha256"]:
            raise AssertionError("Source changed during build")
    if args.source_manifest and sha256(args.source_manifest) != inputs["source_manifest_sha256"]:
        raise AssertionError("Source manifest changed during build")
    result = write_bundle(output, result, audit, inputs)
    print("Wrote {}: {} nodes, {} edges; integration adapter required".format(
        result["graph"]["path"],result["nodes"],result["edges"]),flush=True)
    return result


if __name__ == "__main__":
    main()
