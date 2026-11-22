"""Composition of Dataset B: which contracts each category holds, and why.

The paper (Sec. 5.1, Table 2) builds Dataset B by mixing DAppSCAN and SolidiFI buggy
contracts with clean SmartBugs Wild contracts at 1:1; "after mapping, we have 614
buggy solidity files". The authors' DAppSCAN release (MANDO-Project/
DASP-DAppSCAN-datasets) lists the DAppSCAN files of each category
(``dasp_categories/DASP_smart_contract_metadata.json``, their ``DASP_to_SWC.json``
applied to their labels, one entry per labelled weakness). Without repeated
entries those lists hold exactly 614 files, and Table 2's buggy count of every
category is that list plus exactly 50 contracts, the size of each SolidiFI folder.
The buggy side is therefore the paper's:

1. DAppSCAN: every distinct file the authors list for the category, as their
   cleaned source with their line labels for the category's SWC ids. Left out only
   when a stage cannot read it (the graph builder cannot produce the authors' graph
   format, or the DFG front end cannot parse it) or it has no line for the category.
2. SolidiFI: all 50 contracts of the category's folder (Dataset A's folders).

The clean side departs from the paper. Its SmartBugs Wild pool holds only Solidity
0.4/0.5 contracts while most DAppSCAN files are 0.6-0.8, so with Wild clean contracts
alone the pragma (and the newer syntax) predicts the target. Each buggy source
therefore gets clean counterparts of its own kind, as many as it has buggy files:

3. DAppSCAN-clean: DAppSCAN files of the release not listed for the category and
   without a labelled line of its SWC ids, i.e. files whose audit reported no such
   weakness (a weaker negative than a verified clean contract).
4. SmartBugs-Wild-clean: the 2,742 SmartBugs Wild contracts no SmartBugs tool flags
   (the authors' ge-sc repository; Dataset A's clean contracts all come from this
   pool), 50 per category, the counterparts of SolidiFI.

Clean files are drawn in seeded order per category, skipping files a stage cannot
read and text duplicates of a file already taken. Every DAppSCAN row records its
audited ``project`` (the report folder of the release); the grouped folds keep a
project on one side, since its files share code and style.

Corpus copies have LF line endings (``hcg.sources.composition.normalize``); the pool
files are CRLF, and the authors' Dataset A corpus holds them converted the same way.

Identical texts under different DAppSCAN paths (one file in several audited
snapshots of a project) are kept, as in the paper; evaluations must keep them on
one side of a fold (the grouped protocol does).

Seeded order: ``random.Random("B:<category>:<source>:<seed>")`` shuffles the
name-sorted candidates. ``compose`` needs the pinned sources (``hcg fetch --dataset
B``) and is run once to write ``dataset_b.json``; builds only read that document.
"""
import hashlib
import json
import random
import re
import tempfile
from pathlib import Path

from hcg.datasets.registry import DATASET_B, SOLIDIFI_FILE
from hcg.sources import composition, repos
from hcg.sources.annotations import dappscan_record, preprocess

DASP = "DASP-DAppSCAN-datasets"
DASP_SOURCE = DASP + "/DAppSCAN-source"
CLEAN_POOL = "ge-sc/data/smartbugs-wild-clean-contracts"
SOLIDIFI = "SolidiFI-benchmark/buggy_contracts"
CONTRACTS_PREFIX = "DAppSCAN-source/contracts/"
RULES = [
    "DAppSCAN: every distinct file of the authors' per-category list "
    "(dasp_categories/DASP_smart_contract_metadata.json), cleaned source + cleaned line labels "
    "for the category's SWC ids; left out only when a stage cannot read it (HCG builder, DFG "
    "front end) or without a line",
    "SolidiFI: all 50 contracts of the category's SolidiFI folder (Table 2 buggy count = "
    "distinct DAppSCAN files + 50 in every category)",
    "DAppSCAN-clean: as many as DAppSCAN buggy files, seeded order from the release's files not "
    "listed for the category and without a line labelled with its SWC ids",
    "SmartBugs-Wild-clean: as many as SolidiFI files, seeded order from the 2,742 SmartBugs Wild "
    "clean contracts (ge-sc/data/smartbugs-wild-clean-contracts)",
    "clean draws: per category independently; files a stage cannot read and preprocessed-text "
    "duplicates of a taken file skipped",
    "project: the DAppSCAN report folder of a file (DAppSCAN-source/contracts/<project>/...)",
    "corpus copies: CRLF -> LF (hcg.sources.composition.normalize)",
    "seeded order: random.Random('B:<category>:<source>:<seed>').shuffle(name-sorted candidates)",
]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _copy(path):
    """The bytes the corpus will hold (``composition.normalize``)."""
    return composition.normalize(Path(path).read_bytes())


def _hashes(path):
    return dict(origin_sha256=_sha(path), sha256=hashlib.sha256(_copy(path)).hexdigest())


def _text_key(path):
    return hashlib.sha256(preprocess(_copy(path).decode("utf8", errors="replace")).encode("utf8")).hexdigest()


def _unusable(path, name):
    """None if every stage can read the corpus copy, else why not.

    The HCG builder must produce the authors' graph format, and the DFG front end
    (dfg.graph.projection, which NodeSem and EdgeSem read through) must parse the file
    and find every graph node's text at its AST span. Dataset A passes both for every
    file; checking here keeps one unreadable file from stopping a whole category later.
    """
    from dfg.graph.projection import Projector, ProjectionView
    from hcg.cfg.builder import build_contract
    data = _copy(path)
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / name
        copy.write_bytes(data)
        try:
            graph = build_contract(copy)
        except Exception as error:  # noqa: BLE001 - every reason is recorded
            return "graph builder: %s" % repr(error)[:160]
        if graph.number_of_nodes() == 0:
            return "graph builder: no nodes"
        try:
            Projector(graph, ProjectionView(data.decode("utf8"), name))
        except Exception as error:  # noqa: BLE001
            return "DFG front end: %s" % repr(error)[:160]
    return None


def _order(names, category, source, seed):
    names = sorted(names)
    random.Random("B:%s:%s:%d" % (category, source, seed)).shuffle(names)
    return names


def _dappscan_file(label_root, path, swc_ids, category):
    """(row fields, records) of one DAppSCAN file of the release (``contracts/...`` path)."""
    if not path.startswith(CONTRACTS_PREFIX):
        raise ValueError("unexpected DAppSCAN path %s" % path)
    relative = Path(path[len(CONTRACTS_PREFIX):])
    origin = "%s/cleaned_SWCsource/%s/cleaned_%s" % (DASP_SOURCE, relative.parent.as_posix(), relative.name)
    label = "%s/DASP_cleaned_labels/%s.json" % (DASP_SOURCE, relative.with_suffix("").as_posix())
    records, kinds = dappscan_record([Path(label_root) / label], Path(label_root) / origin, swc_ids, category)
    name = "dappscan_%s_%s" % (hashlib.sha256(path.encode("utf8")).hexdigest()[:10], relative.name)
    return dict(name=name, origin=origin, label=label, swc=kinds, project=relative.parts[0]), records


def _dappscan(label_root, category, listed, swc_ids):
    taken, excluded = [], []
    for path in sorted(set(listed)):
        row, records = _dappscan_file(label_root, path, swc_ids, category)
        source = Path(label_root) / row["origin"]
        reason = ("no line labelled with %s" % "/".join(swc_ids)) if not records else _unusable(source, row["name"])
        if reason:
            excluded.append(dict(source="DAppSCAN", origin=row["origin"], reason=reason))
            continue
        taken.append(dict(name=row["name"], source="DAppSCAN", origin=row["origin"], target=1,
                          labels=[row["label"]], swc=row["swc"], project=row["project"], **_hashes(source)))
    return taken, excluded


def _dappscan_clean(label_root, category, others, swc_ids, count, seen, seed):
    """Up to ``count`` DAppSCAN files not listed for the category, in seeded order."""
    taken, excluded = [], []
    for path in _order(set(others), category, "DAppSCAN-clean", seed):
        if len(taken) == count:
            break
        row, records = _dappscan_file(label_root, path, swc_ids, category)
        source = Path(label_root) / row["origin"]
        key = _text_key(source)
        reason = ("labels a line with %s but is not listed" % "/".join(row["swc"])) if records else None
        reason = reason or (("same preprocessed text as %s" % seen[key]) if key in seen else None)
        reason = reason or _unusable(source, row["name"])
        if reason:
            excluded.append(dict(source="DAppSCAN-clean", origin=row["origin"], reason=reason))
            continue
        seen[key] = row["origin"]
        taken.append(dict(name=row["name"], source="DAppSCAN-clean", origin=row["origin"], target=0,
                          project=row["project"], pairs_with="DAppSCAN", **_hashes(source)))
    return taken, excluded


def _draw(label_root, candidates, count, source, target, seen, category, seed):
    """Up to ``count`` buildable files from ``candidates`` in seeded order (all if None);
    ``seen`` (text key -> origin) given: text duplicates of taken files are skipped."""
    taken, excluded = [], []
    ordered = sorted(candidates) if count is None else _order(candidates, category, source, seed)
    for origin in ordered:
        if count is not None and len(taken) == count:
            break
        path = Path(label_root) / origin
        key = _text_key(path)
        reason = ("same preprocessed text as %s" % seen[key]) if seen is not None and key in seen else None
        reason = reason or _unusable(path, Path(origin).name)
        if reason:
            excluded.append(dict(source=source, origin=origin, reason=reason))
            continue
        if seen is not None:
            seen[key] = origin
        taken.append(dict(name=Path(origin).name, source=source, origin=origin, target=target, **_hashes(path)))
    return taken, excluded


def compose_category(label_root, category, listed, release, swc_ids, seed=1, log=print):
    """``listed``: the category's DAppSCAN paths; ``release``: every DAppSCAN path listed."""
    paper = DATASET_B.reported[category.name]
    dappscan, excluded = _dappscan(label_root, category.name, listed, swc_ids)
    folder = "%s/%s" % (SOLIDIFI, category.solidifi_dir)
    solidifi, skipped = _draw(label_root, ["%s/%s" % (folder, p.name) for p in (Path(label_root) / folder).glob("*.sol")
                                           if SOLIDIFI_FILE.fullmatch(p.name)], None, "SolidiFI", 1, None,
                              category.name, seed)
    excluded += skipped
    seen = {_text_key(Path(label_root) / r["origin"]): r["origin"] for r in dappscan + solidifi}
    clean_dappscan, skipped = _dappscan_clean(label_root, category.name, set(release) - set(listed), swc_ids,
                                              len(dappscan), seen, seed)
    excluded += skipped
    pool = sorted(p.name for p in (Path(label_root) / CLEAN_POOL).glob("*.sol"))
    clean_wild, skipped = _draw(label_root, ["%s/%s" % (CLEAN_POOL, n) for n in pool], len(solidifi),
                                "SmartBugs-Wild-clean", 0, seen, category.name, seed)
    excluded += skipped
    for row in clean_wild:
        row["pairs_with"] = "SolidiFI"
    for buggy, clean, source in ((dappscan, clean_dappscan, "DAppSCAN"), (solidifi, clean_wild, "SolidiFI")):
        if len(clean) != len(buggy):
            raise ValueError("%s: only %d clean counterparts for %d %s files"
                             % (category.name, len(clean), len(buggy), source))
    buggy = len(dappscan) + len(solidifi)
    counts = dict(contracts=2 * buggy, vulnerable_contracts=buggy, dappscan=len(dappscan),
                  solidifi=len(solidifi), clean=buggy, dappscan_clean=len(clean_dappscan),
                  wild_clean=len(clean_wild), dappscan_listed=len(set(listed)),
                  dappscan_list_entries=len(listed), paper_contracts=paper["contracts"],
                  paper_vulnerable_contracts=paper["vulnerable_contracts"])
    log("[B/%s] DAppSCAN %d of %d + %d clean, SolidiFI %d + %d clean: %d contracts (paper %d)"
        % (category.name, len(dappscan), len(set(listed)), len(clean_dappscan), len(solidifi), len(clean_wild),
           2 * buggy, paper["contracts"]))
    return dict(counts=counts, contracts=sorted(dappscan + solidifi + clean_dappscan + clean_wild,
                                                key=lambda r: r["name"]),
                excluded=excluded)


def compose(label_root, seed=1, log=print):
    """The composition document of Dataset B from the pinned sources."""
    from hcg.cfg import author_schema
    commits = repos.verify(label_root, DATASET_B.sources)
    mapping = json.loads((Path(label_root) / DASP / "DASP_to_SWC.json").read_text(encoding="utf8"))
    listed = json.loads((Path(label_root) / DASP_SOURCE / "dasp_categories/DASP_smart_contract_metadata.json")
                        .read_text(encoding="utf8"))
    release = sorted({path for paths in listed.values() for path in paths})
    categories = {}
    for category in DATASET_B.categories:
        swc_ids = sorted(mapping[category.name], key=lambda s: int(re.sub(r"\D", "", s)))
        categories[category.name] = dict(swc=swc_ids, **compose_category(
            label_root, category, listed[category.name], release, swc_ids, seed, log))
    return dict(version=composition.VERSION, dataset=DATASET_B.name, seed=seed, rules=RULES,
                sources=commits, builder=dict(cfg_solidity_sha256=author_schema.CFG_SOLIDITY_SHA256),
                categories=categories)


def write(document, path):
    Path(path).write_text(json.dumps(document, indent=1, sort_keys=False) + "\n", encoding="utf8")
