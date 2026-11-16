"""Graph-build-independent digests of EdgeSem outputs.

Global node ids differ between graph builds, so endpoints are compared by (file, index of
the node among that file's non-auxiliary nodes in graph order); an env_source node by its
file and the sorted set of its neighbours' positions and relations (unique per file).
"""
import collections
import hashlib
import json


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def positions(nodes):
    """[(node id, file, node_type)] in graph order -> {node id: (file, index)} without env nodes."""
    out, seen = {}, collections.Counter()
    for node, file, node_type in nodes:
        if node_type != "env_source":
            out[node] = (file, seen[file])
            seen[file] += 1
    return out


def graph_positions(graph):
    return positions((n, d["source_file"], d["node_type"]) for n, d in graph.nodes(data=True))


def _parse(key):
    file, rest = key.split("::", 1)
    ends, relation, ordinal = rest.rsplit("::", 2)
    src, dst = ends.split("->")
    return file, int(src), int(dst), relation, ordinal


def _env_signatures(parsed, pos):
    neighbours = collections.defaultdict(set)
    for _, src, dst, relation, _ in parsed:
        for a, b in ((src, dst), (dst, src)):
            if a not in pos:
                neighbours[a].add((relation, str(pos.get(b, "ENV"))))
    return {a: str(sorted(v)) for a, v in neighbours.items()}


def f4_digest(edges, pos):
    return digest(sorted(json.dumps([e["relation"], e["file"], pos[e["src"]], pos[e["dst"]], e["src_anchor"],
                                     e["dst_anchor"], e["rule"], e.get("kind"), e["evidence"]], sort_keys=True)
                         for e in edges))


def attribute_digest(keys, matrix, pos):
    parsed = [_parse(k) for k in keys]
    env = _env_signatures(parsed, pos)

    def end(node):
        return str(pos[node]) if node in pos else "ENV" + env[node]

    return digest(sorted(json.dumps([f, end(s), end(d), rel, o, bytes(v).hex()])
                         for (f, s, d, rel, o), v in zip(parsed, matrix)))
