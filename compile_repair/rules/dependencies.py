"""CP5 offline, content-verified package releases and deterministic import repairs."""
import base64
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import tarfile

from compile_repair.rules.environment import pragma_interval
from compile_repair.toolchain.project import import_directives, source_unit_name
from compile_repair.toolchain.solc import lexical_tokens
from scripts.DFG.models import Unsupported


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json_bytes(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))+"\n").encode()


def _write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as fp:
        fp.write(raw)


def _safe_name(name):
    if not isinstance(name,str) or not name or "\0" in name or "\\" in name or name.startswith("/") or ":" in name:
        raise ValueError("Unsafe package file path")
    parts=name.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ValueError("Unnormalized package file path")
    return name


def _signatures(tokens):
    """Index lexical function parameter lists without claiming ABI type resolution."""
    result=[]
    for i,t in enumerate(tokens[:-2]):
        if t!=b"function" or not re.fullmatch(rb"[\w$]+",tokens[i+1]) or tokens[i+2]!=b"(":
            continue
        depth=1
        for end in range(i+3,len(tokens)):
            depth+=int(tokens[end]==b"(")-int(tokens[end]==b")")
            if depth==0:
                result.append((tokens[i+1]+b"("+b" ".join(tokens[i+3:end])+b")").decode("latin1"))
                break
    return sorted(set(result))


def source_declarations(data):
    """Return source-unit declarations available for named and namespace imports."""
    tokens=[v for _,_,_,v in lexical_tokens(data)]
    symbols=set()
    depth=0
    for i,t in enumerate(tokens):
        if depth==0 and t in (b"contract",b"interface",b"library",b"struct",b"enum",b"type",b"error",b"event",b"function"):
            if i+1<len(tokens) and re.fullmatch(rb"[a-zA-Z_$][\w$]*",tokens[i+1]):
                symbols.add(tokens[i+1].decode("ascii"))
        if depth==0 and t==b"constant" and i+1<len(tokens) and re.fullmatch(rb"[a-zA-Z_$][\w$]*",tokens[i+1]):
            symbols.add(tokens[i+1].decode("ascii"))
        depth+=int(t==b"{")-int(t==b"}")
    return sorted(symbols),_signatures(tokens)


def _indexed_source(data):
    try:
        interval=pragma_interval((data,))
        constraint=dict(interval=interval,unsupported=None)
    except Unsupported as e:
        constraint=dict(interval=None,unsupported=str(e))
    symbols,functions=source_declarations(data)
    return dict(sha256=_sha(data),size=len(data),pragma=constraint,imports=list(import_directives(data)),
                declarations=symbols,function_signatures=functions)


def build_index(catalog, output, catalog_sha256):
    """Build an exclusive offline index from a pinned archive inventory. Only regular Solidity files are written."""
    raw=Path(catalog).read_bytes()
    if _sha(raw)!=catalog_sha256:
        raise ValueError("Package inventory SHA256 mismatch")
    records=json.loads(raw)
    dest=Path(output).resolve()
    dest.mkdir(parents=True,exist_ok=False)
    packages={};expanded=0
    for r in records["releases"]:
        name,version=r["package"],r["version"]
        _safe_name(name);_safe_name(version)
        if not re.fullmatch(r"(?:@[A-Za-z0-9._~-]+/)?[A-Za-z0-9._~-]+",name) or not re.fullmatch(r"\d+\.\d+\.\d+",version):
            raise ValueError("Invalid package identity")
        releases=packages.setdefault(name,{})
        if version in releases:
            raise ValueError("Duplicate package release")
        archive=Path(r["path"]).read_bytes()
        sri="sha512-"+base64.b64encode(hashlib.sha512(archive).digest()).decode("ascii")
        if len(archive)!=r["packed_bytes"] or _sha(archive)!=r["sha256"] or sri!=r["expected_integrity"] or not r["verified"]:
            raise ValueError("Archive verification failed: "+name+"@"+version)
        files={};total=0;skipped_links=0;top_dirs=set()
        folder="files/"+name+"@"+version
        with tarfile.open(fileobj=io.BytesIO(archive),mode="r|gz") as tar:
            for member in tar:
                if not member.isfile():
                    if member.name.endswith(".sol") and (member.issym() or member.islnk()):
                        skipped_links+=1
                    continue
                total+=member.size
                if total>records["per_release_unpacked_limit_bytes"] or expanded+total>records["total_unpacked_limit_bytes"]:
                    raise ValueError("Approved unpacked-byte limit reached")
                if not member.name.endswith(".sol"):continue
                rawname=_safe_name(member.name)
                prefix,sep,path=rawname.partition("/")
                top_dirs.add(prefix)
                if not sep or len(top_dirs)>1 or path in files:
                    raise ValueError("Ambiguous or duplicate npm source layout: "+rawname)
                fp=tar.extractfile(member)
                with fp:data=fp.read()
                if len(data)!=member.size:raise ValueError("Truncated package source")
                _write(dest/folder/path,data)
                files[path]=_indexed_source(data)
        if r.get("registry_unpacked_bytes") is not None and total!=r["registry_unpacked_bytes"]:
            raise ValueError("Published unpacked size differs: "+name+"@"+version)
        releases[version]=dict(path=folder,registry_url=r["url"],integrity=sri,archive_sha256=r["sha256"],
                               unpacked_bytes=total,skipped_solidity_links=skipped_links,files=files)
        expanded+=total
    body=_json_bytes(dict(schema="compile-repair-dependencies-v1",archive_catalog_sha256=catalog_sha256,packages=packages))
    _write(dest/"index.json",body)
    seal=dict(schema="compile-repair-dependencies-v1",index_sha256=_sha(body),archive_catalog_sha256=catalog_sha256,
              releases=len(records["releases"]),packages=len(packages),unpacked_bytes=expanded,
              solidity_files=sum(len(v["files"]) for vs in packages.values() for v in vs.values()))
    _write(dest/"seal.json",_json_bytes(seal))
    return dict(seal,status="complete")


class OfflineIndex:
    """Open a sealed read-only package index and verify source bytes on each materialization."""
    def __init__(self, path):
        self.root=Path(path).resolve()
        self.seal=json.loads((self.root/"seal.json").read_bytes())
        raw=(self.root/"index.json").read_bytes()
        if self.seal["schema"]!="compile-repair-dependencies-v1" or _sha(raw)!=self.seal["index_sha256"]:
            raise ValueError("Dependency index seal mismatch")
        self.packages=json.loads(raw)["packages"]

    def content(self, name, version, path):
        """Return checked Solidity bytes within the sealed release directory."""
        release=self.packages[name][version]
        location=self.root/_safe_name(release["path"])/_safe_name(path)
        if location.resolve()!=location or self.root not in location.parents:
            raise ValueError("Dependency source escapes index")
        raw=location.read_bytes()
        if _sha(raw)!=release["files"][path]["sha256"]:
            raise ValueError("Dependency source SHA256 mismatch")
        return raw

def package_spec(path):
    """Split a source import into npm identity and suffix, including relative node_modules paths."""
    parts=path.split("/")
    if "node_modules" in parts:
        parts=parts[len(parts)-parts[::-1].index("node_modules"):]
    elif path.startswith((".","/")) or ":" in path:
        return None
    n=2 if parts and parts[0].startswith("@") else 1
    if len(parts)<=n or any(p in ("",".","..") for p in parts):
        return None
    name="/".join(parts[:n])
    return (name,"/".join(parts[n:])) if re.fullmatch(r"(?:@[\w.~-]+/)?[\w.~-]+",name,re.ASCII) else None


def _version(v):
    return tuple(int(x) for x in v.split("."))


def _comparator(v, op, literal):
    parts=literal.lstrip("v").split(".")
    if len(parts)>3:return False
    nums=[]
    for p in parts:
        if p.lower() in ("x","*"):break
        if not p.isdigit():return False
        nums.append(int(p))
    if not nums:return op in ("","=","~","^")
    lo=tuple((nums+[0,0,0])[:3])
    if op=="^":
        nonzero=next((i for i,x in enumerate(nums) if x),len(nums)-1)
        pivot=min(nonzero,len(nums)-1)
    elif op=="~":pivot=min(1,len(nums)-1)
    else:pivot=len(nums)-1
    hi=lo[:pivot]+(lo[pivot]+1,)+(0,)*(2-pivot)
    if op in ("^","~"):return lo<=v<hi
    if op in ("","="):return lo<=v<hi if len(nums)<3 else v==lo
    if op==">=":return v>=lo
    if op=="<":return v<lo
    if op==">":return v>=hi if len(nums)<3 else v>lo
    return v<hi if len(nums)<3 else v<=lo


def release_in_range(version, spec):
    """Check stable npm releases against comparators, unions, hyphens, wildcards, tilde and caret ranges."""
    if not isinstance(spec,str):return False
    v=_version(version)
    for branch in spec.split("||"):
        branch=branch.strip()
        if not branch:return True
        hyphen=re.fullmatch(r"(\S+)\s+-\s+(\S+)",branch)
        if hyphen:
            if _comparator(v,">=",hyphen[1]) and _comparator(v,"<=",hyphen[2]):return True
            continue
        expr=re.compile(r"(>=|<=|>|<|=|\^|~)?\s*(v?(?:[0-9]+|[xX*])(?:\.(?:[0-9]+|[xX*])){0,2})")
        parts=list(expr.finditer(branch))
        if parts and not expr.sub("",branch).strip() and all(_comparator(v,m[1] or "",m[2]) for m in parts):return True
    return False


def _owned_file(folder, name):
    p=folder/name
    return p if p.is_file() and p.resolve()==p else None


def _manifest_alias(name, spec):
    if not isinstance(spec,str) or not spec.startswith("npm:"):return name,spec
    body=spec[4:];i=body.find("@",1 if body.startswith("@") else 0)
    return (body,"*") if i<0 else (body[:i],body[i+1:])


def _yaml_pins(text,owner,package,spec):
    """Read only direct workspace/importer pins, never execute or infer versions from unrelated packages."""
    # Yarn classic and Berry use top-level descriptor groups with an indented version field.
    if owner.name=="yarn.lock":
        pins=set();active=False
        for line in text.splitlines():
            if line and not line[0].isspace() and line.rstrip().endswith(":"):
                keys=[k.strip().strip("'\042") for k in line.strip()[:-1].split(", ")]
                active=any(k in (package+"@"+str(spec),package+"@npm:"+str(spec)) for k in keys)
            elif active:
                m=re.fullmatch(r"\s+version(?::|\s)\s*['\042]?(\d+\.\d+\.\d+)['\042]?\s*",line)
                if m:pins.add(m[1])
        return pins
    return set()


def manifest_identities(root, importer, requested, mask_versions=False):
    """Read static dependency evidence only in ancestor manifests inside the supplied project."""
    root=Path(root).resolve()
    folder=(root/importer).parent
    ancestors=[p for p in (folder,)+tuple(folder.parents) if p==root or root in p.parents]
    spec=None;receipts=[]
    def checked_manifest(path):
        raw=path.read_bytes()
        receipts.append(dict(path=path.relative_to(root).as_posix(),sha256=_sha(raw)))
        return raw
    manifest_dir=None
    for directory in ancestors:
        manifest=_owned_file(directory,"package.json")
        if manifest:
            obj=json.loads(checked_manifest(manifest))
            manifest_dir=directory
            specs={obj[k][requested] for k in ("dependencies","optionalDependencies","devDependencies","peerDependencies")
                   if isinstance(obj.get(k),dict) and isinstance(obj[k].get(requested),str)}
            if len(specs)>1:raise ValueError("Conflicting manifest version ranges")
            spec=next(iter(specs),None)
            break
    real,version_range=_manifest_alias(requested,spec)
    if mask_versions:
        # The reference experiment keeps package aliases and withholds both lock pins and ranges.
        return dict(package=real, tier="T3", spec=None, manifests=receipts)
    pins=set()
    for directory in ancestors:
        lock=_owned_file(directory,"package-lock.json")
        if lock:
            obj=json.loads(checked_manifest(lock));installed=obj.get("packages")
            if isinstance(installed,dict):
                paths=[(p/"node_modules"/requested).relative_to(directory).as_posix() for p in ancestors
                       if p==directory or directory in p.parents]
                entry=next((installed[k] for k in paths if k in installed),{})
            else:entry=obj.get("dependencies",{}).get(requested,{})
            if isinstance(entry,dict) and "version" in entry:
                locked_name, pin = _manifest_alias(requested, entry["version"])
                declared_name = entry.get("name", locked_name)
                if not isinstance(declared_name, str) or not re.fullmatch(r"(?:@[\w.~-]+/)?[\w.~-]+", declared_name, re.ASCII):
                    raise ValueError("Invalid locked package identity")
                if declared_name != requested:
                    if real not in (requested, declared_name):
                        raise ValueError("Lockfile package name conflicts with manifest alias")
                    real = declared_name
                if isinstance(pin,str) and re.fullmatch(r"\d+\.\d+\.\d+",pin):pins.add(pin)
                elif pin:raise ValueError("Unsupported locked dependency identity")
            break
        yarn=_owned_file(directory,"yarn.lock")
        pnpm=_owned_file(directory,"pnpm-lock.yaml")
        if yarn or pnpm:
            if yarn:pins.update(_yaml_pins(checked_manifest(yarn).decode(),yarn,requested,spec))
            if pnpm:
                text=checked_manifest(pnpm).decode()
                workspace=(manifest_dir or folder).relative_to(directory).as_posix()
                pins.update(_pnpm_pins(text,workspace,requested))
            break
    if len(pins)>1:raise ValueError("Conflicting locked package versions")
    return dict(package=real,tier="T1" if pins else "T2" if spec is not None else "T3",
                spec=next(iter(pins)) if pins else version_range,manifests=receipts)


def _pnpm_pins(text, workspace, name):
    # pnpm v6/v9 importer maps. Legacy single-project locks have the dependency maps at their root.
    stack=[];pins=set()
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):continue
        m=re.match(r"^( *)([^:#]+):(?:\s+(.*?))?\s*$",line)
        if not m:continue
        indent=len(m[1]);key=m[2].strip().strip("'\042");value=(m[3] or "").split(" #")[0].strip("'\042")
        while stack and stack[-1][0]>=indent:stack.pop()
        parents=[k for _,k in stack]
        if parents[:2]==["importers",workspace]:parents=parents[2:]
        elif workspace!="." or "importers" in parents:parents=[]
        accepted=any(parents==[s] and key==name or parents==[s,name] and key=="version"
                     for s in ("dependencies","devDependencies","optionalDependencies"))
        if accepted and re.fullmatch(r"\d+\.\d+\.\d+(?:\(.*\))?",value):
            pins.add(value.partition("(")[0])
        if not value:stack.append((indent,key))
    return pins


def import_symbols(data, directive):
    """Return explicit source-side names, including actual members used through a namespace alias."""
    tokens=[v for _,_,_,v in lexical_tokens(data[directive["start"]:directive["end"]])]
    symbols=set()
    if b"{" in tokens and b"}" in tokens:
        names=tokens[tokens.index(b"{")+1:tokens.index(b"}")]
        take=True
        for t in names:
            if t==b",":take=True
            elif take:symbols.add(t.decode("latin1"));take=False
    elif b"as" in tokens:
        at=tokens.index(b"as")+1
        if at<len(tokens):
            alias=tokens[at]
            all_tokens=[v for _,_,_,v in lexical_tokens(data)]
            symbols.update(all_tokens[i+2].decode("latin1") for i in range(len(all_tokens)-2)
                           if all_tokens[i:i+2]==[alias,b"."])
    return symbols


def compatible_compilers(contents, versions):
    """Keep supported installed versions in the intersection of actual source pragmas."""
    from compile_repair.rules.environment import candidate_versions
    try:
        groups = candidate_versions(pragma_interval(contents), versions)
    except Unsupported:
        return ()
    return tuple(groups["primary"] + groups["later_series_only_after_primary_failure"])


def _suffix_rank(request, candidate):
    wanted = [p for p in request.split("/") if p not in ("", ".", "..")]
    present = candidate.split("/")
    if not wanted or wanted[-1].casefold() != present[-1].casefold():
        return None
    def common(left, right):
        count = 0
        for a, b in zip(reversed(left), reversed(right)):
            if a != b:
                break
            count += 1
        return count
    exact = common(wanted, present)
    folded = common([p.casefold() for p in wanted], [p.casefold() for p in present])
    if exact >= 2:
        return 0, -exact
    if folded >= 2 or folded == len(wanted) and wanted[-1] != present[-1]:
        return 1, -folded
    return 2, -exact


def relative_repairs(project, index, versions, previous=None, round_number=1):
    """Propose only source- and pragma-supported changes to quoted import paths."""
    from compile_repair.core.model import Patch
    from compile_repair.core.provenance import apply_patches, verify_provenance
    root = Path(project.root)
    contents = {Path(f.path): f.content for f in project.files}
    for name, raw in (previous or {}).items():
        contents[root / name] = raw
    declarations = {p: set(source_declarations(raw)[0]) for p, raw in contents.items()}
    by_basename = {}
    for path in index.entries:
        by_basename.setdefault(path.name.casefold(), []).append(path)
    edits, evidence = {}, []
    for row in project.issues:
        spelling = row.get("path", "")
        if (row.get("category") not in ("missing_relative_file", "io_error") or
                not spelling.startswith(("./", "../")) or package_spec(spelling) or
                row.get("importer", "").startswith(".compile_repair/deps/") or not row.get("supported_literal")):
            continue
        importer = Path(row["source_path"])
        raw = contents[importer]
        paths = [p for p in by_basename.get(posixpath.basename(spelling).casefold(), ())
                 if p != importer and p.resolve() == p and root in p.parents]
        selected_symbols = import_symbols(raw, row)
        tokens = {v.decode("ascii") for _, _, kind, v in lexical_tokens(raw)
                  if kind == "word" and v.isascii()}
        known = set().union(*declarations.values()) if declarations else set()
        choices = []
        for p in paths:
            candidate_data = contents[p] if p in contents else p.read_bytes()
            exported = set(source_declarations(candidate_data)[0])
            required = selected_symbols or (tokens & exported - known)
            if not required or not required <= exported:
                continue
            if not compatible_compilers([f.content for f in project.files] + [candidate_data], versions):
                continue
            name = p.relative_to(root).as_posix()
            rank = _suffix_rank(spelling, name)
            if rank is not None:
                choices.append((rank, name, sorted(required)))
        choices.sort()
        best = [c for c in choices if c[0] == choices[0][0]]
        info = dict(importer=row["importer"], line=row["line"], path=spelling, candidates=choices)
        evidence.append(info)
        if len(best) != 1:
            info["reason"] = "ambiguous_candidates" if best else "no_compatible_candidate"
            continue
        target = best[0][1]
        new_path = posixpath.relpath(target, posixpath.dirname(row["importer"]) or ".")
        if not new_path.startswith(("./", "../")):
            new_path = "./" + new_path
        start, end = row["literal_start"] + 1, row["literal_end"] - 1
        quote = raw[start-1:start]
        expected = bytes.fromhex(row["literal_hex"])
        if quote not in (b"'", b'"') or raw[end:end+1] != quote or raw[start:end] != expected:
            raise ValueError("Import literal span does not match checked source")
        replacement = new_path.encode("utf8").replace(b"\\", b"\\\\").replace(quote, b"\\" + quote)
        name = importer.relative_to(root).as_posix()
        patch = Patch(start, end, expected, replacement, "relative_import", round_number,
                      "unique compatible path at import line " + str(row["line"]))
        edits.setdefault(name, {})[(start, end)] = patch
        info.update(selected=target, literal_span=[start, end])
    changes, patches = {}, {}
    for name, spans in edits.items():
        ordered = tuple(spans[k] for k in sorted(spans, reverse=True))
        before = contents[root / name]
        after, trace = apply_patches(before, ordered)
        verify_provenance(before, after, trace)
        changes[name], patches[name] = after, ordered
    return changes, patches, evidence


def _release_sources(offline, name, version, roots):
    """Check the complete relative dependency closure of the requested release files."""
    release = offline.packages[name][version]
    files, todo = {}, list(roots)
    while todo:
        path, required = todo.pop()
        info = release["files"].get(path)
        if info is None or not required <= set(info["declarations"]):
            return None, {"reason": "missing_release_path" if info is None else "missing_exported_symbol",
                          "path": path, "required": sorted(required)}
        if path in files:
            continue
        raw = offline.content(name, version, path)
        files[path] = raw
        for imp in info["imports"]:
            if not imp["supported_literal"]:
                return None, {"reason": "unsupported_import_literal", "path": imp["path"]}
            spelling = imp["path"]
            if spelling.startswith(("./", "../")) and package_spec(spelling) is None:
                target = posixpath.normpath(posixpath.join(posixpath.dirname(path), spelling))
                if target.startswith("../") or target == "..":
                    return None, {"reason": "relative_import_escapes_release", "path": spelling}
                todo.append((target, import_symbols(raw, imp)))
    return files, None


def dependency_choices(project, inventory, offline, versions, overlays, policy, evidence, preferred=None,
                       existing_releases=None, mask_versions=False):
    """Yield offline release combinations, including transitive packages and each identity constraint.

    A compatible lexical candidate still requires the pipeline's actual compiler and D3 check.
    No source directory in the original project is used for storing a release.
    """
    from compile_repair.toolchain.project import resolve_project
    if policy not in ("latest", "oldest", "closest"):
        raise ValueError("Unknown dependency version policy")
    root = Path(project.root)
    initial = compatible_compilers([f.content for f in project.files], versions)
    if not initial:
        evidence.append(dict(reason="empty_unit_compiler_intersection"))
        return
    target_minor = _version(preferred if preferred in initial else initial[0])[:2]

    def walk(current, chosen, added, mappings, pending_skip):
        rows = {}
        current_bytes = {f.path: f.content for f in current.files}
        for issue in current.issues:
            spec = package_spec(issue.get("path", ""))
            if spec and issue.get("supported_literal") and spec[0] not in pending_skip:
                rows.setdefault(spec[0], []).append((issue, spec[1]))
        if not rows:
            if added and not any(r.get("importer", "").startswith(".compile_repair/deps/") for r in current.issues):
                yield current, added, chosen
            return
        requested = min(rows)
        imports = rows[requested]
        try:
            identities = [manifest_identities(root, imp["importer"], requested, mask_versions) for imp, _ in imports]
        except (ValueError, UnicodeError) as exc:
            evidence.append(dict(requested=requested, reason="invalid_manifest", detail=str(exc)))
            return
        names = {i["package"] for i in identities}
        if len(names) != 1:
            evidence.append(dict(requested=requested, reason="conflicting_package_identities"))
            return
        name = names.pop()
        releases = offline.packages.get(name, {})
        prior = chosen.get(name)
        possible = [v for v in releases if (not prior or v == prior["version"]) and all(
            i["tier"] == "T3" or (i["tier"] == "T1" and i["spec"] == v) or
            (i["tier"] == "T2" and release_in_range(v, i["spec"])) for i in identities)]
        checked, rejections = [], {}
        for version in possible:
            folder = ".compile_repair/deps/" + name + "@" + version + "/"
            if (root / folder).exists() or (root / ".compile_repair").is_symlink():
                rejections[version] = dict(reason="reserved_release_directory_in_use")
                continue
            requested_files = [(tail, import_symbols(current_bytes[imp["source_path"]], imp))
                               for imp, tail in imports]
            files, issue = _release_sources(offline, name, version, requested_files)
            if issue is not None:
                rejections[version] = issue
                continue
            combined = compatible_compilers([f.content for f in current.files] + list(files.values()), versions)
            if not combined:
                rejections[version] = dict(reason="empty_release_pragma_intersection")
                continue
            distance = min(abs(_version(v)[0]-target_minor[0])*1000 +
                           abs(_version(v)[1]-target_minor[1]) for v in combined)
            checked.append((version, distance, folder, files))
        checked.sort(key=lambda r: _version(r[0]), reverse=policy != "oldest")
        evidence.append(dict(requested=requested, package=name, identities=identities,
                             in_index=bool(releases), matching_identity=len(possible), rejections=rejections,
                             compatible=[r[0] for r in checked]))
        if not checked:
            yield from walk(current, chosen, added, mappings, pending_skip | {requested})
            return
        for version, distance, folder, files in checked:
            fresh = {folder + path: raw for path, raw in files.items()}
            extended = dict(added)
            extended.update(fresh)
            remaps = list(mappings)
            for imp, tail in imports:
                vfs = source_unit_name(imp["importer"], imp["path"])
                if not vfs.endswith("/" + tail):
                    raise ValueError("Package suffix differs from compiler source unit")
                token = vfs[:-len(tail)] + "=" + folder
                if token not in remaps:
                    remaps.append(token)
            if extended == added and remaps == list(mappings):
                continue
            working = dict(overlays)
            working.update(extended)
            candidate = resolve_project(root, project.entry, remaps, inventory,
                                        project.additional_entries, working)
            # An existing project import must keep its bytes if the same prefix
            # is now served by a release. Reject mixed package identities.
            stable = {(r["source_path"], r["start"]): r for r in candidate.imports}
            after = {f.path: f.sha256 for f in candidate.files}
            shadowed = False
            for row in current.imports:
                if not row["resolved"]:
                    continue
                change = stable.get((row["source_path"], row["start"]))
                if change and (not change["resolved"] or
                               after.get(change["target_path"]) != hashlib.sha256(current_bytes[row["target_path"]]).hexdigest()):
                    shadowed = True
                    break
            if shadowed or not compatible_compilers([f.content for f in candidate.files], versions):
                rejections[version] = dict(reason="existing_import_would_change" if shadowed else "empty_closure_pragma_intersection")
                continue
            selection = dict(chosen)
            release = releases[version]
            receipts = (prior["identities"] if prior else []) + identities
            tier = max(i["tier"] for i in receipts)
            selection[name] = dict(version=version, tier=tier, inferred=tier == "T3",
                                   identities=receipts, integrity=release["integrity"],
                                   archive_sha256=release["archive_sha256"], compiler_series_distance=distance)
            yield from walk(candidate, selection, extended, remaps, pending_skip)
    yield from walk(project, dict(existing_releases or {}), {}, list(project.remappings), set())
