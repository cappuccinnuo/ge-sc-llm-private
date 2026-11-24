"""Verify sealed import origins against the relocated working closure without starting a compiler."""
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
from measure import (HERE, ir_targets, jsonline, read_checked_json, save, sha256, emit, ProjectIndex, resolve_project)
from compile_repair.toolchain.project import project_command, slither_arguments
from compile_repair.core.model import Compiler


def original_root(absolute, relative):
    p, parts = Path(absolute), Path(relative).parts
    if not p.is_absolute() or not parts or p.parts[-len(parts):] != parts:
        raise ValueError("Import origin is not the declared physical source-unit path")
    return p.parents[len(parts)-1]


def checked_project(info):
    if not info:
        return None, {}
    root = Path(info["root"])
    index = ProjectIndex(root,tuple(Path(f["path"]) for f in info["files"]))
    fresh = resolve_project(root,info["entry"],info["remappings"],index,info.get("additional_entries",()))
    new = json.loads(json.dumps(fresh.manifest()))
    if {k:v for k,v in new.items() if k!="imports"} != {k:v for k,v in info.items() if k!="imports"}:
        raise ValueError("Working closure or source SHA differs")
    if len(new["imports"])!=len(info["imports"]) or fresh.issues:
        raise ValueError("Successful import closure differs")
    units = dict(info["source_units"])
    changed = Counter()
    origins = set()
    for old, current in zip(info["imports"],new["imports"]):
        reconstructed = dict(current)
        for path_field,unit_field in (("source_path","importer"),("target_path","target_source_unit")):
            physical = units[old[unit_field]]
            origins.add(str(original_root(old[path_field],physical)))
            if root/physical != Path(current[path_field]):
                raise ValueError("Recomputed import target differs")
            if old[path_field]!=current[path_field]:
                changed[path_field] += 1
            reconstructed[path_field]=old[path_field]
        if reconstructed!=old:
            raise ValueError("Other import field differs")
    if len(origins)>1:
        raise ValueError("Import origin roots disagree")
    exact = replace(fresh,imports=tuple(info["imports"]))
    assert json.loads(json.dumps(exact.manifest()))==info
    return exact,dict(changed)


def main():
    counters = {}
    with jsonline("ir_manifest_preflight") as out:
        for cohort in ("real_dev","benchmark","cp3"):
            tallies=Counter()
            for uid,corpus,op,path,digest,expected in ir_targets(cohort):
                rec=read_checked_json(path,digest)
                attempt=rec["attempts"][-1]
                old=attempt["slither"]
                changed, problem = {}, None
                try:
                    project,changed=checked_project(old.get("project"))
                    if project:
                        compiled=attempt["solc"]
                        compiler=Compiler(**compiled["compiler"])
                        if project_command(project,compiler,compiled["settings"])!=compiled["command"]:
                            raise ValueError("Recorded solc arguments differ")
                        target,kwargs=slither_arguments(project,compiler,compiled["settings"])
                        if target!=old["command"]["target"] or any(old["command"].get(k)!=v for k,v in kwargs.items()):
                            raise ValueError("Recorded Slither arguments differ")
                except (ValueError, KeyError, OSError, AssertionError) as exc:
                    problem=type(exc).__name__+": "+str(exc)
                    tallies[problem]+=1
                tallies["units"]+=1
                tallies["projects"]+=bool(old.get("project"))
                tallies["verified"]+=problem is None
                tallies["with_origin_paths"]+=bool(changed)
                emit(out,dict(unit_id=uid,scope=cohort,operator=op,result_sha256=digest,
                              changed_path_references=changed,problem=problem))
            counters[cohort]=dict(tallies)
    save(HERE/"ir_manifest_preflight.json",dict(scopes=counters,rows_sha256=sha256(HERE/"ir_manifest_preflight.jsonl"),
        method="Independently reconstruct all source SHA, byte ranges, VFS identifiers, physical targets and compiler arguments. Restore the exact origin paths retained by materialize_project for the historical Slither call. Only reads files."))


if __name__=="__main__":
    main()
