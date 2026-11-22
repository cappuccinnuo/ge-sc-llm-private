"""CP4 evaluation on checked source copies, deterministic groups and Slither truth graphs."""
from collections import Counter, defaultdict, deque
from dataclasses import asdict
from functools import lru_cache
import hashlib
import json
import re
from pathlib import Path

from compile_repair.core.model import CompilationUnit, Patch, SourceFile
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import ArtifactStore, emit, read_checked_json, sha256
from compile_repair.pipeline import repair_unit
from compile_repair.rules.environment import mando_known_version
from compile_repair.toolchain.project import resolve_project
from compile_repair.toolchain.solc import lexical_tokens


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def group_and_split(corpus, identity):
    """Assign a portable project, address, CVE, or content identity to one fixed split."""
    namespace = "sha256" if corpus in ("MANDO", "SOChecker") else corpus
    group = namespace + ":" + identity
    prefix = _digest(("cp4-split-v1:" + group).encode())[:8]
    return group, "dev" if int(prefix, 16) % 5 == 0 else "test"


def stratified_sample(rows, limit, seed, name):
    """Rank units reproducibly and draw round-robin by corpus and compiler minor series."""
    if limit < 0:
        raise ValueError("Negative sample size")
    strata = defaultdict(list)
    for row in rows:
        stratum = (row["corpus"], row["series"])
        key = "{}:{}:{}".format(seed, name, row["unit_id"])
        strata[stratum].append((_digest(key.encode()), row["unit_id"], row))
    queues = deque(deque(row for _, _, row in sorted(strata[k])) for k in sorted(strata))
    draw = []
    while queues and len(draw) < limit:
        group = queues.popleft()
        draw.append(group.popleft())
        if group:
            queues.append(group)
    return draw


def environment_observation(base, entry, project, compilers, frozen_versions, store, journal, unit_id):
    """Run the normal environment stages on this entry; version hints must match its actual bytes."""
    raw = Path(entry).read_bytes()
    regression = "mando" if base["corpus"] == "MANDO" else None
    known = mando_known_version(raw, frozen_versions)[0] if regression else None
    sources = project.files if project else (SourceFile(str(entry), _digest(raw), raw, base["kind"]),)
    unit = CompilationUnit(unit_id, sources, known, regression)
    return repair_unit(unit, compilers, store, journal, project=project)


def control_observation(base, compilers, frozen_versions, store, journal):
    """Replay an unmodified input against its saved truth; report the exact reasons for a mismatch."""
    truth = read_checked_json(base["result"]["result_path"], base["result"]["result_sha256"])
    if sha256(base["graph_path"]) != base["graph_sha256"]:
        raise ValueError("Control truth graph changed: " + base["unit_id"])
    path = Path(base["entry"])
    if sha256(path) != base["entry_sha256"]:
        raise ValueError("Control input changed: " + str(path))
    project = resolve_project(base["project_root"], path, base["remappings"]) if base["project_root"] else None
    if project and [(f.path, f.sha256) for f in project.files] != [(f["path"], f["sha256"]) for f in truth["inputs"]]:
        raise ValueError("Control input closure changed: " + base["unit_id"])
    result = environment_observation(base, path, project, compilers, frozen_versions, store, journal, base["unit_id"])
    folder = store.path / "units" / result.unit_id
    graph = folder / "graph.json"
    actual = sha256(graph) if graph.is_file() else None
    checks = {"success": result.status == "success", "version": result.selected_version == base["version"],
              "settings": list(result.settings) == base["settings"], "graph_bytes": actual == base["graph_sha256"]}
    return {"unit_id": result.unit_id, "corpus": base["corpus"], "split": base["split"], "group": base["group"],
            "checks": checks, "passed": all(checks.values()), "expected_version": base["version"],
            "actual_version": result.selected_version, "expected_settings": base["settings"],
            "actual_settings": list(result.settings), "expected_graph_sha256": base["graph_sha256"],
            "actual_graph_sha256": actual, "result_path": str(folder / "result.json"),
            "result_sha256": sha256(folder / "result.json"), "reason": result.reason}


# These are compiler or input-format diagnostics. The analyzer-only category is
# represented by independently archived failures (CP4 authorization), never a mutation.
OPERATORS = {
    "unresolved_package_import": "remove an identified package and use its published import paths",
    "missing_relative_file": "remove a resolved relative dependency",
    "missing_base_contract": "delete the unique locally defined inherited base",
    "undeclared_identifier": "delete a referenced event declaration",
    "duplicate_definition": "copy a complete definition into its original scope",
    "multiple_license_or_pragma": "insert conflicting ABI coder directives on supported versions",
    "encoding": "insert an invalid UTF-8 byte in a Solidity text literal",
    "unbalanced_structure": "remove the closing brace of a top-level definition",
    "parser_error_other": "replace a declaration identifier with a comma",
    "type_error_other": "replace a branch condition with an integer expression",
    "codegen_only": "insert a bounded function with 18 simultaneously live locals",
    "closure_version_conflict": "give a dependency a pragma disjoint from the entry's pragma",
    "io_error": "replace an import literal with a non-local, nonexistent file reference",
    "docstring_error": "document an absent parameter on a named function",
    "syntax_error": "remove an explicit required function visibility",
    "unimplemented_feature": "assign a memory array of structs to storage on measured default generators",
    "unsupported_disjunction": "replace a pragma expression by a legal disjunction",
    "unsupported_expression": "replace a pragma expression by an unsupported token sequence",
    "unterminated_pragma": "remove the terminator of a Solidity pragma",
    "pragma_missing_semicolon_candidate": "remove a pragma terminator immediately before another directive or declaration",
    "declaration_error": "give a named function its enclosing contract's forbidden name",
    "standard_json_input": "wrap the checked source closure and effective settings as standard JSON",
}


class SourceLayout:
    """Lexical spans in a known compilable source. Strings and comments never create sites."""

    def __init__(self, raw):
        self.raw = raw
        self.tokens = list(lexical_tokens(raw))
        self.words = [t[3] for t in self.tokens]
        self.matches = {}
        stack = []
        for i, word in enumerate(self.words):
            if word in (b"{", b"(", b"["):
                stack.append(i)
            elif word in (b"}", b")", b"]") and stack:
                opening = stack.pop()
                self.matches[opening] = i
        self.definitions = []
        self.functions = []
        self.pragmas = []
        self.events = []
        self.conditions = []
        self.imports = []
        for i, word in enumerate(self.words):
            following = self.words[i+1:i+3]
            if word in (b"contract", b"interface", b"library") and following and self.tokens[i+1][2] == "word":
                opening = self._until(i+2, (b"{", b";", b"}"))
                if opening in self.matches and self.words[opening] == b"{":
                    start = i-1 if i and self.words[i-1] == b"abstract" else i
                    self.definitions.append((start, i+1, opening, self.matches[opening]))
            elif word == b"function" and len(following) == 2 and following[1] == b"(" and self.tokens[i+1][2] == "word":
                close = self.matches.get(i+2)
                if close is not None:
                    end = self._until(close+1, (b"{", b";", b"}"))
                    if end < len(self.words):
                        self.functions.append((i, i+1, close, end))
            elif word == b"pragma" and following[:1] == [b"solidity"]:
                end = self._until(i+2, (b";", b"{", b"}"))
                if end < len(self.words) and self.words[end] == b";":
                    self.pragmas.append((i, i+1, end))
            elif word == b"event" and len(following) == 2 and following[1] == b"(":
                end = self._until(i+2, (b";", b"{", b"}"))
                if end < len(self.words) and self.words[end] == b";":
                    self.events.append((i,i+1,end))
            elif word in (b"if", b"while") and following[:1] == [b"("] and i+1 in self.matches:
                self.conditions.append((i+1,self.matches[i+1]))
            elif word == b"import":
                end = self._until(i+1, (b";",))
                target = next((k for k in range(i+1,end) if self.tokens[k][2]=="string"), None)
                if target is not None:
                    self.imports.append(target)

    def _until(self, i, delimiters):
        while i < len(self.words) and self.words[i] not in delimiters:
            i += 1
        return i

    def string_contents(self):
        """Yield insertion offsets in Solidity text literals, excluding directives and inline assembly."""
        skip = set(self.imports)
        for i, word in enumerate(self.words):
            if word == b"pragma":
                skip.update(range(i, self._until(i + 1, (b";",))))
            elif word == b"assembly":
                opening = self._until(i + 1, (b"{", b";", b"}"))
                skip.update(range(i, self.matches.get(opening, opening) + 1))
        for i, (start, end, kind, value) in enumerate(self.tokens):
            if kind == "string" and i not in skip and (i == 0 or self.words[i - 1] != b"hex"):
                if len(value) >= 2 and value[:1] in (b"'", b'"') and value[:1] == value[-1:]:
                    yield start + 1

    def bounds(self, first, last):
        return self.tokens[first][0], self.tokens[last][1]

    def top_regions(self):
        """Return lexical top-level intervals for repair-locality checks, including free declarations."""
        result = []
        i = 0
        while i < len(self.words):
            start = i
            while i < len(self.words):
                token = self.words[i]
                if token == b";":
                    i += 1
                    break
                if token == b"{" and i in self.matches:
                    i = self.matches[i] + 1
                    if self.words[start] != b"import":
                        break
                    continue
                i += 1
            result.append(self.bounds(start,i-1))
        return result


def base_contents(base):
    """Load a checked closure with stable relative names; single-file graphs use the empty key."""
    record = read_checked_json(base["result"]["result_path"], base["result"]["result_sha256"])
    sources = {}
    for source in record["inputs"]:
        path = Path(source["path"])
        name = path.relative_to(base["project_root"]).as_posix() if base["project_root"] else ""
        data = path.read_bytes()
        if _digest(data) != source["sha256"] or name in sources:
            raise ValueError("Invalid source identity in " + base["unit_id"])
        sources[name] = data
    return sources


def _settings_object(settings):
    config = {}
    if "--optimize" in settings:
        config["optimizer"] = {"enabled":True}
    if "--via-ir" in settings:
        config["viaIR"] = True
    if "--evm-version" in settings:
        config["evmVersion"] = settings[settings.index("--evm-version")+1]
    return config


_STACK_FUNCTION = (b"\nfunction cp4StackDepth(uint x) public returns (uint) {\n" +
    b"".join(b"uint cp4v%d = x + %d;\n" % (i,i) for i in range(1,19)) +
    b"return " + b" + ".join(b"cp4v%d" % i for i in range(1,19)) + b";\n}\n")

# Each stable release in these inclusive ranges rejected this copy in the default
# generator. Do not extrapolate beyond the measured snapshot (CP4.1).
_STRUCT_COPY_REJECTED = frozenset(
    "0.{}.{}".format(minor, patch)
    for minor, first, last in ((4,12,26), (5,0,17), (6,0,12), (7,0,6), (8,0,38))
    for patch in range(first, last + 1))
_STRUCT_NAMES = {b"CP41Item", b"cp41Items", b"cp41Copy"}
_STRUCT_COPY = (b"\nstruct CP41Item { uint n; } CP41Item[] private cp41Items;\n"
                b"function cp41Copy() public { CP41Item[] memory m = new CP41Item[](1); cp41Items = m; }\n")


@lru_cache(maxsize=1)
def _benchmark_versions():
    from compile_repair.toolchain.solc import load_trusted_compilers
    compilers, _, _ = load_trusted_compilers()
    return tuple(compilers)


def _struct_copy_allowed(base, sources, name, offset, versions):
    from compile_repair.rules.environment import FLOOR, make_plan, ordered_candidates
    from compile_repair.toolchain.solc import version_tuple
    if "--via-ir" in base["settings"] or base["version"] not in _STRUCT_COPY_REJECTED:
        return False
    available = {v for v in versions if version_tuple(v) >= FLOOR}
    if base["version"] not in available:
        return False
    if available <= _STRUCT_COPY_REJECTED:
        return True
    # An expanded toolchain may add an unmeasured eligible compiler. Check the
    # actual plans on both byte sequences, retaining the original priority version.
    regression = "mando" if base.get("corpus") == "MANDO" else None
    candidates = set(ordered_candidates(make_plan(sources.values(), available, regression=regression)))
    if base.get("result"):
        record = read_checked_json(base["result"]["result_path"], base["result"]["result_sha256"])
        plan = record.get("plan") or {}
        candidates.update(v for group in plan.get("groups", ()) for v in group)
        if plan.get("priority"):
            candidates.add(plan["priority"])
    mutated = dict(sources)
    raw = sources[name]
    mutated[name] = raw[:offset] + _STRUCT_COPY + raw[offset:]
    changed = set(ordered_candidates(make_plan(mutated.values(), available, regression=regression)))
    return bool(candidates and changed and (candidates | changed) <= _STRUCT_COPY_REJECTED)


_NPM_PART = re.compile(r"[a-z0-9][a-z0-9._~-]*\Z")


def _package_layout(root, filename):
    """Identify the on-disk package root and its published name from an explicit layout."""
    parts = filename.split("/")
    for i in range(len(parts) - 2, -1, -1):
        part = parts[i]
        if (part.startswith("@") and _NPM_PART.fullmatch(part[1:]) and i + 2 < len(parts)
                and _NPM_PART.fullmatch(parts[i + 1])):
            return "/".join(parts[:i + 2]), "/".join(parts[i:i + 2]), "scoped package directory"
        if i and parts[i - 1] == "node_modules" and _NPM_PART.fullmatch(part):
            return "/".join(parts[:i + 1]), part, "installed node_modules package"
        if part in ("openzeppelin-solidity", "zeppelin-solidity") and parts[i + 1] == "contracts":
            return "/".join(parts[:i + 1]), part, "named legacy package with contracts directory"
        if part == "openzeppelin":
            # Vendors use this short directory name for several incompatible releases.
            # A local package manifest can identify the name and the actual package root.
            for end in (i + 2, i + 1):
                prefix = "/".join(parts[:end])
                manifest = root / prefix / "package.json"
                if not manifest.is_file() or root not in manifest.resolve().parents:
                    continue
                raw = manifest.read_bytes()
                try:
                    metadata = json.loads(raw)
                except (UnicodeError, ValueError):
                    continue
                if not isinstance(metadata, dict) or metadata.get("private"):
                    continue
                published = metadata.get("name")
                if published in ("@openzeppelin/contracts", "@openzeppelin/contracts-upgradeable",
                                 "@openzeppelin/contracts-ethereum-package", "openzeppelin-solidity", "zeppelin-solidity"):
                    return prefix, published, "package.json sha256 " + _digest(raw)
    return None


def _package_site(base, sources, imports):
    """Plan one deterministic package removal, including every incoming relative import."""
    from compile_repair.toolchain.project import source_unit_name
    root = Path(base["project_root"]).resolve()
    entry = next(iter(sources))
    links = []
    candidates = {}
    for row in imports:
        if not row.get("resolved"):
            continue
        owner = Path(row["source_path"]).relative_to(root).as_posix()
        target = Path(row["target_path"]).relative_to(root).as_posix()
        links.append((owner, target, row))
        if row["path"].startswith(("./", "../")) and target not in candidates:
            candidates[target] = _package_layout(root, target)
    for prefix, package, proof in sorted({v for v in candidates.values() if v}):
        # Keep the compilation entry even when it belongs to the imported package.
        members = {name for name in sources if name != entry and name.startswith(prefix + "/")}
        if not members:
            continue
        logical = {n: package + n[len(prefix):] for n in sorted(members)}
        physical = {n: "node_modules/" + path for n, path in logical.items()}
        if set(physical.values()) & (set(sources) - members):
            continue
        if any("/node_modules/" in path or any(c in path for c in ("\\", "'", '"', "\n", "\r"))
               for path in logical.values()):
            continue
        remap = package + "/=node_modules/" + package + "/"
        edits = {}
        compatible = True
        for owner, target, row in links:
            relative = row["path"].startswith(("./", "../"))
            if owner in members:
                if target not in members and relative:
                    compatible = False
                    break
                continue
            if target not in members:
                continue
            if not relative or not row["supported_literal"]:
                compatible = False
                break
            name = logical[target]
            mapped = source_unit_name(row["importer"], name, tuple(base["remappings"]) + (remap,))
            if mapped != physical[target]:
                compatible = False
                break
            a,b = row["literal_start"],row["literal_end"]
            token = sources[owner][a:b]
            if len(token) < 2 or token[1:-1].hex() != row["literal_hex"] or token[:1] != token[-1:]:
                raise ValueError("Import literal differs from checked project manifest")
            key = (owner, a, b)
            value = token[:1] + name.encode("utf8") + token[-1:]
            if key in edits and value != edits[key]:
                compatible = False
                break
            edits[key] = value
        if compatible and edits:
            return dict(package=package, layout_evidence=proof, logical_package_paths=logical,
                        file_renames=physical, remapping=remap, import_edits=edits)
    return None


def _sample_edits(base, sources, site, operator):
    """Return the damaged closure and every ordered patch, including deleted package files."""
    file, _, _, plan, action, _ = site
    if action != "package_dependency":
        mutated, patch, _ = build_mutation(base, sources, site, operator)
        return mutated, [(file,action,patch)]
    work = dict(sources)
    records = []
    grouped = defaultdict(list)
    for (name, start, end), replacement in sorted(plan["import_edits"].items(), reverse=True):
        patch = Patch(start, end, sources[name][start:end], replacement, operator, reason=OPERATORS[operator])
        grouped[name].append(patch)
        records.append((name,"edit",patch))
    for name, patches in grouped.items():
        work[name], _ = apply_patches(sources[name], patches)
    for name in sorted(plan["file_renames"]):
        original = work.pop(name)
        records.append((name,"delete_file",Patch(0,len(original),original,b"",operator,reason=OPERATORS[operator])))
    return work, records


def mutation_sites(base, sources, layouts, imports, versions=None):
    """Choose one deterministic, byte-anchored site per applicable operator in a verified closure.

    Return operator -> (file, start, end, replacement, action, stage). The wrapper's replacement
    is materialized only for sampled units. Missing operators are recorded as not applicable.
    """
    from compile_repair.rules.environment import pragma_interval
    from compile_repair.toolchain.solc import version_tuple
    version = version_tuple(base["version"])
    entry = next(iter(sources))
    result = {}
    definitions = defaultdict(list)
    bases = []
    struct_names_free = all(_STRUCT_NAMES.isdisjoint(layout.words) for layout in layouts.values())
    def site(op, file, start, end, replacement, stage="solc", action="edit"):
        result.setdefault(op,(file,start,end,replacement,action,stage))

    for file, layout in layouts.items():
        w,t,raw = layout.words,layout.tokens,sources[file]
        string_offset = next(layout.string_contents(), None)
        if string_offset is not None:
            site("encoding", file, string_offset, string_offset, b"\xff")
        for first,name,opening,close in layout.definitions:
            bounds=layout.bounds(first,close)
            definitions[w[name]].append((file,bounds))
            if b"is" in w[name+1:opening]:
                idx=name+1+w[name+1:opening].index(b"is")+1
                # Ignore identifiers inside the base's constructor arguments.
                while idx<opening:
                    if t[idx][2]=="word":
                        bases.append(w[idx])
                    idx=layout.matches[idx]+1 if w[idx]==b"(" and idx in layout.matches else idx+1
            end=t[close][1]
            site("duplicate_definition",file,end,end,("copy",bounds))
            site("unbalanced_structure",file,t[close][0],end,b"")
            site("parser_error_other",file,t[name][0],t[name][1],b",")
            if w[name-1]==b"contract":
                if b"cp4StackDepth" not in w:
                    site("codegen_only",file,t[close][0],t[close][0],_STACK_FUNCTION)
                offset = t[close][0]
                if struct_names_free and "unimplemented_feature" not in result:
                    available = versions if versions is not None else _benchmark_versions()
                    if _struct_copy_allowed(base, sources, file, offset, available):
                        site("unimplemented_feature", file, offset, offset, _STRUCT_COPY)
        for first,name,param_end,body in layout.functions:
            if b"cp4AbsentParameter" not in w:
                site("docstring_error",file,t[first][0],t[first][0],b"\n/// @param cp4AbsentParameter benchmark\n")
            for k in range(param_end+1,body):
                if w[k] in (b"public",b"external",b"internal",b"private"):
                    site("syntax_error",file,t[k][0],t[k][1],b"")
                    break
            if version >= (0,5,0):
                owner=next((w[n] for _,n,o,c in layout.definitions if o<first<c), None)
                if owner and w[name]!=owner:
                    site("declaration_error",file,t[name][0],t[name][1],owner)
        for left,right in layout.conditions:
            if right>left+1:
                site("type_error_other",file,t[left][1],t[right][0],b"uint256(1)")
        for first,name,end in layout.events:
            if w.count(w[name])>1:
                lo,hi=layout.bounds(first,end)
                site("undeclared_identifier",file,lo,hi,b"")
        for _,sol,end in layout.pragmas:
            lo,hi=t[sol][1],t[end][0]
            site("unsupported_expression",file,lo,hi,b" ^cp4Unknown","environment_plan")
            site("unsupported_disjunction",file,lo,hi,b" 0.5.17 || 0.8.0","environment_plan")
            site("unterminated_pragma",file,t[end][0],t[end][1],b"","environment_plan")
            if w[end+1:end+2] in ([b"import"],[b"pragma"],[b"contract"],[b"interface"],[b"library"],[b"abstract"]):
                site("pragma_missing_semicolon_candidate",file,t[end][0],t[end][1],b"","environment_plan")
            if version >= (0,7,4):
                site("multiple_license_or_pragma",file,t[end][1],t[end][1],b"\npragma abicoder v1;\npragma abicoder v2;\n")
            if file!=entry and layouts[entry].pragmas and "closure_version_conflict" not in result:
                interval=pragma_interval([sources[entry]])
                pin=next((v for v in ("0.4.12","0.8.38") if interval and not interval[0]<=version_tuple(v)<interval[1]),None)
                if pin:
                    site("closure_version_conflict",file,lo,hi,b" "+pin.encode(),"environment_plan")
        if layout.imports:
            k=layout.imports[0]
            if file==entry or base["project_root"]:
                stage="project_assembly" if base["project_root"] else "solc"
                site("io_error",file,t[k][0],t[k][1],b'"file:cp4_nonexistent_dependency.sol"',stage)
    for name in bases:
        if len(definitions[name])==1:
            file,(lo,hi)=definitions[name][0]
            site("missing_base_contract",file,lo,hi,b"")
    if base["project_root"]:
        root=Path(base["project_root"])
        for imp in imports:
            if not imp["resolved"]:
                continue
            target=Path(imp["target_path"]).relative_to(root).as_posix()
            if target==entry or target not in sources:
                continue
            op="missing_relative_file" if imp["path"].startswith(("./","../")) else "unresolved_package_import"
            site(op,target,0,len(sources[target]),b"","project_assembly","delete_file")
        package = _package_site(base, sources, imports)
        if package:
            result["unresolved_package_import"] = (entry, 0, 0, package, "package_dependency", "project_assembly")
    try:
        for data in sources.values():
            data.decode("utf8")
    except UnicodeDecodeError:
        pass
    else:
        site("standard_json_input",entry,0,len(sources[entry]),("wrap",),"input_format")
    return result


def build_mutation(base, sources, site, operator):
    """Apply the selected edit and return the resulting closure, exact patch and damage provenance."""
    file,lo,hi,replacement,action,stage=site
    raw=sources[file]
    if isinstance(replacement,tuple):
        if replacement[0]=="copy":
            a,b=replacement[1]
            replacement=b"\n"+raw[a:b]+b"\n"
        else:
            entries={name or "input.sol":{"content":data.decode("utf8")} for name,data in sources.items()}
            obj={"language":"Solidity","sources":entries,"settings":_settings_object(base["settings"])}
            replacement=json.dumps(obj,ensure_ascii=False,separators=(",",":")).encode()
    patch=Patch(lo,hi,raw[lo:hi],replacement,operator,reason=OPERATORS[operator])
    data,damage=apply_patches(raw,[patch])
    mutated=dict(sources)
    if action=="delete_file":
        del mutated[file]
    else:
        mutated[file]=data
    return mutated,patch,damage


def classify_trigger(stage, target, result, primary, selected_labels):
    """Classify using the primary cause after all environment candidates and the independent selected probe."""
    if result.status == "success":
        return "resolved_by_environment"
    if target in primary and (stage != "solc" or target in selected_labels):
        return "included"
    return "not_triggered"


def _materialize_closure(base, contents, store, directory):
    """Write only this sample's source copies and resolve its entry within the new directory."""
    if base["project_root"]:
        entry_name=Path(base["entry"]).relative_to(base["project_root"]).as_posix()
        for name,data in contents.items():
            store.write_bytes(directory+"/"+name,data)
        root=store.path/directory
        return root/entry_name,resolve_project(root,entry_name,base["remappings"])
    return store.write_bytes(directory+"/input.sol",contents[""]),None


def assess_mutation(base, operator, seed, sources, site, compilers, frozen_versions, output):
    """Construct, independently probe and classify one sample in a new external evidence directory."""
    from compile_repair.evaluation.report import classify_record, primary_causes
    from compile_repair.toolchain.project import compile_project
    from compile_repair.toolchain.solc import compile_file

    store=ArtifactStore(output)
    mutated, changes = _sample_edits(base, sources, site, operator)
    _, _, _, plan, action, stage = site
    entry, project = _materialize_closure(base, mutated, store, "damaged")
    edits = []
    for i, (name, kind, patch) in enumerate(changes):
        filename = "edit/replacement.bin" if len(changes) == 1 else "edit/{:04d}.bin".format(i)
        new_bytes = store.write_bytes(filename, patch.replacement)
        edits.append(dict(file=name, action=kind, start=patch.start, end=patch.end,
                          original_bytes_sha256=_digest(patch.expected), new_bytes_path=str(new_bytes),
                          new_bytes_sha256=_digest(patch.replacement), new_length=len(patch.replacement)))
    manifest = dict(operator=operator, target=operator, seed=seed, base_unit=base["unit_id"],
                    group=base["group"], split=base["split"], corpus=base["corpus"], series=base["series"],
                    truth_graph_sha256=base["graph_sha256"], version=base["version"], settings=base["settings"],
                    stage=stage, original_sha256={k:_digest(v) for k,v in sources.items()},
                    damaged_sha256={k:_digest(v) for k,v in mutated.items()})
    if action == "package_dependency":
        manifest.update({k:plan[k] for k in ("package","layout_evidence","file_renames","logical_package_paths","remapping")})
        manifest["edits"] = edits
    else:
        manifest["edit"] = edits[0]
    store.write_json("mutation.json",manifest)
    selected_labels=[];selected=None;selected_first=None
    with store.journal("invocations.jsonl") as journal:
        if stage=="solc":
            if project and project.issues:
                selected_first="selected copy has unresolved project imports"
            else:
                compiler=compilers[base["version"]]
                compiled=(compile_project(project,compiler,settings=tuple(base["settings"])) if project else
                          compile_file(entry,compiler,settings=tuple(base["settings"])))
                selected=asdict(compiled);selected_first=compiled.error_first_line
                emit(journal,dict(kind="selected_solc",**selected))
                if compiled.timed_out:
                    raise RuntimeError("Selected-version probe timed out")
                if compiled.returncode!=0:
                    inputs=[{"path":f.path} for f in project.files] if project else [{"path":str(entry)}]
                    probe={"status":"unrepaired","reason":"selected_probe","inputs":inputs,
                           "attempts":[{"stage":"environment","version":base["version"],"solc":selected}]}
                    selected_labels=sorted({r["category"] for r in classify_record(probe)})
        result=environment_observation(base,entry,project,compilers,frozen_versions,store,journal,"environment")
    record=asdict(result);failures=classify_record(record)
    primary=primary_causes(record,failures)["categories"]
    outcome=classify_trigger(stage,operator,result,primary,selected_labels)
    result_path=store.path/"units/environment/result.json"
    first=None
    for attempt in result.attempts:
        first=(attempt.get("error_first_line") or (attempt.get("solc") or {}).get("error_first_line") or
               (attempt.get("slither") or {}).get("error_first_line"))
        if first:
            break
    if not first and failures:
        first=failures[0].get("reason") or failures[0].get("basis") or result.reason
    observation=dict(unit_id=base["unit_id"],operator=operator,seed=seed,corpus=base["corpus"],
        series=base["series"],group=base["group"],split=base["split"],outcome=outcome,stage=stage,
        selected_attempted=selected is not None,selected_categories=selected_labels,
        selected_returncode=selected["returncode"] if selected is not None else None,
        selected_first_line=selected_first,environment_categories=primary,
        environment_any_categories=sorted({f["category"] for f in failures}),environment_first_line=first,
        environment_status=result.status,environment_reason=result.reason,environment_version=result.selected_version,
        environment_solc_calls=sum("solc" in a for a in result.attempts),
        environment_slither_calls=sum(bool(a.get("slither")) for a in result.attempts),
        result_path=str(result_path),result_sha256=sha256(result_path),
        mutation_path=str(store.path/"mutation.json"),mutation_sha256=sha256(store.path/"mutation.json"),
        journal_sha256=sha256(store.path/"invocations.jsonl"))
    store.write_json("observation.json",observation)
    return observation


def _damaged_ranges(mapping):
    """Intervals in original coordinates, including insertion anchors and removed terminal bytes."""
    intervals=[]
    cursor=0
    for s in mapping.segments:
        if s.original_start is None:
            intervals.append((cursor,cursor))
            continue
        if cursor < s.original_start:
            intervals.append((cursor,s.original_start))
        if s.kind!="original":
            intervals.append((s.original_start,s.original_end))
        cursor=s.original_end
    if cursor<mapping.original_length:
        intervals.append((cursor,mapping.original_length))
    return intervals


def _near(interval, edits, regions):
    left,right=interval
    for lo,hi in edits:
        if left<=hi and lo<=right:
            return True
        for start,end in regions:
            if start<=left<=end and start<=lo<end:
                return True
    return False


def _correspondence(original, damaged, repaired, damage_maps, repair_maps):
    from compile_repair.core.provenance import compose_offsets
    result={};near=True;levels=[]
    for name in set(original)|set(damaged)|set(repaired)|set(damage_maps)|set(repair_maps):
        before,middle,after=(part.get(name,b"") for part in (original,damaged,repaired))
        first,second=damage_maps.get(name),repair_maps.get(name)
        if not first and not second:
            if before!=middle or middle!=after or ((name in original)!=(name in repaired)):
                raise ValueError("Missing source provenance: "+name)
            continue
        if first is None:
            if before!=middle:raise ValueError("Missing damage record: "+name)
            first=apply_patches(before,())[1]
        if second is None:
            if middle!=after:raise ValueError("Missing repair record: "+name)
            second=apply_patches(middle,())[1]
        segments=compose_offsets(before,middle,after,first,second)
        result[name]=(first,second,segments)
        levels.append(second.level)
        edits=_damaged_ranges(first)
        additions=[s for s in segments if s.original_start is None and any(
            r.original_start is None and r.new_start<s.new_end and s.new_start<r.new_end for r in second.segments)]
        if additions:
            regions=SourceLayout(before).top_regions()
            for span in additions:
                left=max((s.original_end for s in segments if s.original_end is not None and s.new_end<=span.new_start),default=0)
                right=min((s.original_start for s in segments if s.original_start is not None and s.new_start>=span.new_end),default=len(before))
                near=near and _near((left,right),edits,regions)
    level="rewrite" if "rewrite" in levels else "additive" if "additive" in levels else "none"
    return result,near,level


def _identity(value):
    if isinstance(value,dict):
        return value.get("filename",""),tuple(value["key5"])
    return "",tuple(value)


def _nodes(graph):
    result={}
    for row in graph.get("nodes",[]):
        key=_identity(row)
        if key in result or len(key[1])!=5:
            raise ValueError("Invalid or duplicate graph node identity")
        result[key]=row
    return result


def _at_original(segments, offset):
    return next((s for s in segments if s.original_start is not None and s.original_start<=offset<s.original_end),None)


def _edges_and_calls(graph, keys):
    edges,calls=Counter(),Counter()
    for edge in graph.get("cfg_edges",[]):
        src,dst=_identity(edge["source"]),_identity(edge["target"])
        if src in keys and dst in keys:
            edges[(keys[src],keys[dst],edge["kind"])]+=1
    for call in graph.get("calls",[]):
        site=_identity(call["node"])
        if site in keys:
            detail={k:v for k,v in call.items() if k!="node"}
            calls[(keys[site],json.dumps(detail,sort_keys=True,ensure_ascii=False))]+=1
    return edges,calls


def _multiset_score(left,right):
    matched=sum((left&right).values())
    union=sum((left|right).values())
    return {"truth":sum(left.values()),"repaired":sum(right.values()),"matched":matched,
            "ratio":matched/union if union else 1.0}


_IR_BYTECODE = re.compile(r"(?<=:= )(?P<prefix>0x)?(?P<hex>[0-9a-fA-F]{8,})(?=\((?:string|bytes)\)$)")
_METADATA_KEYS = {b"ipfs", b"bzzr0", b"bzzr1", b"experimental", b"solc"}


def _cbor_item(data, pos):
    """Read a definite-length CBOR header. Bounds also limit work on invalid input."""
    tag = data[pos]
    pos += 1
    length = tag & 31
    if length < 24:
        return tag >> 5, length, pos
    if length > 27:
        raise ValueError("Indefinite or reserved CBOR length")
    size = 1 << (length - 24)
    if pos + size > len(data):
        raise ValueError("Truncated CBOR length")
    return tag >> 5, int.from_bytes(data[pos:pos + size], "big"), pos + size


def _solc_metadata(data):
    """Recognize the complete Solidity trailer map, checking keys, types and lengths."""
    try:
        major, count, pos = _cbor_item(data, 0)
        if major != 5 or not 0 < count <= len(_METADATA_KEYS):
            return False
        keys = set()
        for _ in range(count):
            major, size, pos = _cbor_item(data, pos)
            key = data[pos:pos + size]
            if major != 3 or len(key) != size or key not in _METADATA_KEYS or key in keys:
                return False
            pos += size
            keys.add(key)
            major, size, pos = _cbor_item(data, pos)
            if key == b"experimental":
                if major != 7 or size not in (20, 21):
                    return False
                continue
            value = data[pos:pos + size]
            if len(value) != size:
                return False
            pos += size
            if key == b"solc":
                if major == 3:
                    if not value.decode("utf8"):
                        return False
                elif major != 2 or size != 3:
                    return False
            elif major != 2 or size != (34 if key == b"ipfs" else 32):
                return False
        return pos == len(data)
    except (IndexError, ValueError):
        return False


def _without_metadata(match):
    digits = match.group("hex")
    if len(digits) % 2:
        return match.group()
    size = int(digits[-4:], 16)
    start = len(digits) - 2 * (size + 2)
    if start <= 0 or not size or not _solc_metadata(bytes.fromhex(digits[start:-4])):
        return match.group()
    return (match.group("prefix") or "") + digits[:start]


def normalized_node_ir(operations):
    """Keep application literals intact. Slither emits a type() operation before embedded code."""
    if not any("SOLIDITY_CALL type()(" in op for op in operations):
        return operations, False
    result = []
    changed = False
    for op in operations:
        value = _IR_BYTECODE.sub(_without_metadata, op) if ":=" in op else op
        result.append(value)
        changed |= value != op
    return result, changed


def _comparison_graph(graph, names, normalize):
    """Map observed file identities, including call destinations, into truth coordinates."""
    def reference(value):
        if isinstance(value, dict) and "filename" in value:
            return dict(value, filename=names.get(value["filename"], value["filename"]))
        return value

    nodes = []
    changed = 0
    for row in graph.get("nodes", ()):
        node = reference(row)
        if normalize:
            ir, did_change = normalized_node_ir(row["ir"])
            if did_change:
                changed += 1
                node = dict(node, ir=ir)
        nodes.append(node)
    if not names:
        return dict(graph, nodes=nodes), changed
    edges = [dict(edge, source=reference(edge["source"]), target=reference(edge["target"]))
             for edge in graph.get("cfg_edges", ())]
    calls = [dict(call, node=reference(call["node"]), callee=reference(call["callee"]))
             for call in graph.get("calls", ())]
    return dict(graph, nodes=nodes, cfg_edges=edges, calls=calls), changed


def score_graphs(truth, actual, original, damaged, repaired, damage_maps, repair_maps, solc_returncode, d3,
                 file_renames=None, normalize_creation_code=True):
    """Score actual graph facts under verified damage and repair provenance, without running tools.

    Source maps use project-relative names (the empty key for a single-file graph).
    Kept membership is based on the original node start. Edges and calls retain their
    multiplicities. Empty comparisons have ratio one; compilation and extra nodes are
    independently reported, so an absent result can never pass as an exact repair.
    """
    renames = file_renames or {}
    if any(old not in original or new not in repaired for old, new in renames.items()):
        raise ValueError("Rename must refer to existing original and repaired files")
    reverse = {new: old for old, new in renames.items()}
    aligned = {reverse.get(name, name): data for name, data in repaired.items()}
    if len(reverse) != len(renames) or len(aligned) != len(repaired):
        raise ValueError("Ambiguous scoring file rename")
    repaired = aligned
    truth, changed_truth = _comparison_graph(truth, {}, normalize_creation_code)
    changed_actual = 0
    if actual is not None:
        actual, changed_actual = _comparison_graph(actual, reverse, normalize_creation_code)
    maps,near,level=_correspondence(original,damaged,repaired,damage_maps,repair_maps)
    expected,observed=_nodes(truth),_nodes(actual or {})
    old_kept,new_kept={},{}
    matched=set();affected=deleted=lost=missing_kept=equal_kept=0
    for identity,row in expected.items():
        file,key=identity;offset=key[3]
        if file not in original or not 0<=offset<=len(original[file]):
            raise ValueError("Truth graph offset outside source")
        changed=False;can_recover=True;target=offset
        if file in maps:
            first,_,composed=maps[file]
            if offset==len(original[file]):
                if row["length"]!=0:raise ValueError("Nonempty truth node begins at EOF")
                target=len(repaired.get(file,b""))
            else:
                before=_at_original(first.segments,offset)
                changed=before is None or before.kind!="original"
                deleted+=int(before is None)
                span=_at_original(composed,offset)
                target=span.new_start+offset-span.original_start if span is not None else None
                can_recover=span is not None and span.kind in ("original","restored")
        mapped=(file,key[:3]+(target,)+key[4:])
        present=mapped in observed and file in repaired and target is not None
        same=present and all(row[k]==observed[mapped][k] for k in ("node_type","ir"))
        if present:
            matched.add(mapped)
        if changed:
            affected+=1
            lost+=int(not (same and can_recover))
        else:
            # Missing expected keys still contribute to the truth edge/call denominator.
            old_kept[identity]=mapped if present else ("absent",identity)
            if present:new_kept[mapped]=mapped
            else:missing_kept+=1
            equal_kept+=int(same)
    extra=set(observed)-matched
    only_added=True
    for file,key in extra:
        offset=key[3];length=observed[(file,key)]["length"]
        if file not in repaired or file not in maps or not 0<=offset<=offset+length<=len(repaired[file]):
            only_added=False;continue
        second=maps[file][1]
        if not length:
            offset=max(0,min(offset,len(repaired[file])-1));length=1
        parts=[s for s in second.segments if s.new_start<offset+length and offset<s.new_end]
        only_added=only_added and bool(parts) and all(s.original_start is None for s in parts)
    e1,c1=_edges_and_calls(truth,old_kept);e2,c2=_edges_and_calls(actual or {},new_kept)
    edges,calls=_multiset_score(e1,e2),_multiset_score(c1,c2)
    kept=len(old_kept)
    compiled=solc_returncode==0 and d3 is True
    return {"compiled":compiled,"kept":{"units":kept,"equal":equal_kept,"ratio":equal_kept/kept if kept else 1.0},
            "cfg_edges":edges,"calls":calls,"metadata_normalized":bool(changed_truth or changed_actual),
            "normalized_nodes":{"truth":changed_truth,"repaired":changed_actual},"affected_by_damage":affected,"affected_by_deletion":deleted,
            "lost":lost,"missing_kept":missing_kept,"added":len(extra),"added_only_in_repair_bytes":only_added,
            "added_bytes_near_damage":near,"change_level":level,
            "exact":bool(compiled and actual is not None and equal_kept==kept and not lost and not extra and
                         near and edges["ratio"]==1 and calls["ratio"]==1)}

def benchmark_entry(catalog, unit_id, operator, output, seed=20261122):
    """Run one control or one of the compiler/input operators on a catalogued base in a new store."""
    import gzip
    from compile_repair.toolchain.slither import check_profile
    from compile_repair.toolchain.solc import load_trusted_compilers
    opener=gzip.open if Path(catalog).suffix==".gz" else open
    with opener(catalog,"rt",encoding="utf8") as fp:
        base=next((r for r in (json.loads(line) for line in fp) if r["unit_id"]==unit_id),None)
    if base is None:
        raise ValueError("Unknown benchmark unit: "+unit_id)
    if operator!="control" and operator not in OPERATORS:
        raise ValueError("No live source operator for "+operator)
    check_profile("production")
    compilers,versions,_=load_trusted_compilers()
    if operator=="control":
        store=ArtifactStore(output)
        with store.journal("invocations.jsonl") as journal:
            result=control_observation(base,compilers,versions,store,journal)
        store.write_json("control.json",result)
        return {"status":"complete" if result["passed"] else "stopped","summary":result}
    sources=base_contents(base)
    layouts={n:SourceLayout(data) for n,data in sources.items()}
    imports=(json.loads(Path(base["result"]["result_path"]).with_name("project.json").read_bytes())["imports"]
             if base["project_root"] else [])
    sites=mutation_sites(base,sources,layouts,imports)
    if operator in sites:
        result=assess_mutation(base,operator,seed,sources,sites[operator],compilers,versions,output)
    else:
        result={"outcome":"not_applicable","unit_id":unit_id,"operator":operator,"reason":"no qualifying site: "+OPERATORS[operator]}
        ArtifactStore(output).write_json("observation.json",result)
    return {"status":"complete","summary":result}


def score_request(request_path, output):
    """Score checked files and recorded core edits from JSON; write one exclusive score receipt."""
    spec=json.loads(Path(request_path).read_bytes())
    def content(ref):
        if ref is None:
            return None
        raw=Path(ref["path"]).read_bytes()
        if _digest(raw)!=ref["sha256"]:
            raise ValueError("Score input SHA256 mismatch: "+ref["path"])
        return raw

    def decoded(value):
        if value.get("encoding")!="hex":
            raise ValueError("Expected a hexadecimal byte record")
        return bytes.fromhex(value["data"])

    def replay(before,after,changes):
        patches=[Patch(c["start"],c["end"],decoded(c["old"]),decoded(c["new"]),c["step"],
                       c.get("round",1),c.get("reason","")) for c in changes]
        result,record=apply_patches(before,patches)
        if result!=after:
            raise ValueError("Score edits do not explain the supplied bytes")
        return record

    original,damaged,repaired,first,second={},{},{},{},{}
    names=set()
    for row in spec["files"]:
        n=row["name"]
        if n in names:
            raise ValueError("Duplicate score source: "+n)
        names.add(n)
        for part,files in (("original",original),("damaged",damaged),("repaired",repaired)):
            raw=content(row.get(part))
            if raw is not None:
                name = spec.get("file_renames", {}).get(n, n) if part == "repaired" else n
                if name in files:
                    raise ValueError("Duplicate physical source in score request: " + name)
                files[name] = raw
        if row.get("damage_changes"):
            first[n]=replay(original.get(n,b""),damaged.get(n,b""),row["damage_changes"])
        if row.get("repair_changes"):
            second[n]=replay(damaged.get(n,b""),repaired.get(spec.get("file_renames", {}).get(n,n),b""),row["repair_changes"])
    truth=json.loads(content(spec["truth_graph"]))
    candidate=content(spec.get("repaired_graph"))
    actual=json.loads(candidate) if candidate is not None else None
    score=score_graphs(truth,actual,original,damaged,repaired,first,second,spec["solc_returncode"],spec["d3"],
                       file_renames=spec.get("file_renames"),normalize_creation_code=spec.get("normalize_creation_code",True))
    ArtifactStore(output).write_json("score.json",score)
    return {"status":"complete","summary":score}
