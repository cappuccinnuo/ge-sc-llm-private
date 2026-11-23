"""CP5 §1. Offline census over frozen CP3 attributions, acquisition manifests and verified sources."""
from collections import Counter, defaultdict
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote, urlsplit

from compile_repair.rules import environment
from compile_repair.toolchain import project

OUT = Path(__file__).resolve().parent
ART = OUT.parent
TARGET = {"unresolved_package_import", "missing_relative_file", "standard_json_input",
          "io_error", "closure_version_conflict"}
CONFIG = ("package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "remappings.txt",
          "foundry.toml", "hardhat.config.*", "truffle-config.*")
LOCAL_PREFIX = {"lib", "interfaces", "contracts"}
NPM_NAME = re.compile(r"(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*\Z", re.ASCII)
SEMVER = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:[-+][0-9A-Za-z.+-]+)?\Z")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(path, digest):
    raw = Path(path).read_bytes()
    if sha(raw) != digest:
        raise ValueError("Frozen input changed: "+str(path))
    return raw


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open("x", encoding="utf8") as fp:
        json.dump(value,fp,indent=2,ensure_ascii=False,sort_keys=True)
        fp.write("\n")


def rows(raw):
    return list(map(json.loads,raw.splitlines()))


def kind(name):
    if name in CONFIG:return name
    for prefix in ("hardhat.config.", "truffle-config."):
        if name.startswith(prefix):return prefix+"*"
    return None


def package_path(path):
    """Preserve bare prefixes as evidence, including non-npm paths, and recognize relative node_modules imports."""
    if "://" in path or path.startswith(("/", "\\")):
        return None
    parts=path.split("/")
    if "node_modules" in parts:
        i=len(parts)-1-parts[::-1].index("node_modules")
        parts=parts[i+1:]
    elif path.startswith("."):
        return None
    if not parts or not parts[0] or parts[0] in (".",".."):return None
    count=2 if parts[0].startswith("@") and len(parts)>1 else 1
    return "/".join(parts[:count]),"/".join(parts[count:])


@lru_cache(maxsize=30000)
def source_facts(path,digest):
    return facts(checked(path,digest))


def facts(raw):
    try:
        masked=environment.code_only(raw)
        pragmas=[re.sub(r"\s+", " ", masked[a:b].decode("latin1").strip())
                 for a,b in environment._pragma_spans(raw)]
    except environment.Unsupported:
        pragmas=["<unsupported pragma directive>"]
    return tuple(imp["path"] for imp in project.import_directives(raw) if imp["supported_literal"]),tuple(pragmas)


def registry_name(url):
    if not isinstance(url,str):return None
    u=urlsplit(url)
    if u.hostname != "registry.npmjs.org" or "/-/" not in u.path:return None
    return unquote(u.path.lstrip("/").split("/-/")[0])


def source_identity(spec, requested):
    if isinstance(spec,str) and spec.startswith("npm:"):
        spec=spec[4:]
        start=spec.find("@",1 if spec.startswith("@") else 0)
        if start==-1:return spec,"*"
        return spec[:start],spec[start+1:]
    return requested,spec


class ProjectInventory:
    def __init__(self, roots):
        self.files=defaultdict(dict)
        self.configs=defaultdict(list)
        self.acquisitions={}
        self.registry_seen=defaultdict(set)
        self.locks={}
        self.packages={}
        self.suffixes=defaultdict(lambda:defaultdict(list))
        roots={Path(r) for r in roots}
        for corpus in ("DAppSCAN","Trace"):
            base=ART/"cp3_v1/acquisition"/corpus
            receipt=read(base/"receipt.json")
            raw=checked(base/"manifest.jsonl.gz",receipt["manifest_sha256"])
            self.acquisitions[corpus]=dict(commit=receipt["commit"],manifest_sha256=receipt["manifest_sha256"],
                                           files=receipt["files"])
            for item in rows(gzip.decompress(raw)):
                path=Path(item["absolute_path"])
                root=next((p for p in path.parents if p in roots),None)
                if root is None:continue
                key=str(root);name=path.relative_to(root).as_posix()
                self.files[key][name]=item["sha256"]
                if path.suffix==".sol":self.suffixes[key][path.name].append(name)
                typ=kind(path.name)
                if not typ:continue
                rawconf=checked(path,item["sha256"])
                record=dict(file=name,kind=typ,sha256=item["sha256"])
                if typ=="package.json":
                    d=json.loads(rawconf)
                    sections={s:d.get(s,{}) for s in ("dependencies","devDependencies","peerDependencies","optionalDependencies")}
                    # Only npm dependency names and specifiers are needed. Private URL credentials are never emitted.
                    self.packages[key,str(path.parent)]=sections
                    record["section_sizes"]={k:len(v) for k,v in sections.items()}
                    record["npm_aliases"]={k:sorted(n for n,spec in deps.items() if isinstance(spec,str) and spec.startswith("npm:"))
                                           for k,deps in sections.items()}
                elif typ=="package-lock.json":
                    d=json.loads(rawconf);lock={}
                    for location,v in d.get("packages",{}).items():
                        if v.get("resolved"):
                            registry=registry_name(v["resolved"])
                            if registry:self.registry_seen[registry].add(v.get("version",""))
                        if location:lock[location]=v.get("version",""),registry_name(v.get("resolved"))
                    if not d.get("packages"):
                        for pack,v in d.get("dependencies",{}).items():
                            lock["node_modules/"+pack]=v.get("version",""),registry_name(v.get("resolved"))
                    self.locks[key,str(path.parent)]=lock
                    record["lockfile_version"]=d.get("lockfileVersion")
                elif typ in ("yarn.lock","pnpm-lock.yaml"):
                    raise ValueError("An additional lockfile schema needs measurement: "+str(path))
                else:
                    record["bytes"]=len(rawconf)
                self.configs[key].append(record)

    def tier(self,root,importer,pack):
        if not root:return ("T3",pack,"")
        current=(Path(root)/importer).parent
        ancestors=[x for x in (current,*current.parents) if x==Path(root) or Path(root) in x.parents]
        manifest=next((self.packages[root,str(x)] for x in ancestors if (root,str(x)) in self.packages),{})
        spec=next((deps[pack] for deps in manifest.values() if pack in deps),None)
        real,spec=source_identity(spec,pack)
        for owner in ancestors:
            lock=self.locks.get((root,str(owner)),{})
            if not lock:continue
            for parent in ancestors:
                if parent!=owner and owner not in parent.parents:continue
                loc=(parent/"node_modules"/pack).relative_to(owner).as_posix()
                version,registered=lock.get(loc,("",""))
                if SEMVER.fullmatch(version) and (not registered or registered==real):
                    return ("T1",real,version)
            break
        if isinstance(spec,str) and (spec=="*" or re.fullmatch(r"[0-9vVxX.*~^<>=| +\-a-zA-Z]+",spec) and re.search(r"\d",spec)):
            return ("T2",real,spec)
        return ("T3",real,"")

    @lru_cache(maxsize=50000)
    def copy_roots(self,root,pack,tail):
        if not root or not tail or ".." in tail.split("/"):return frozenset()
        result=set()
        for fn in self.suffixes[root].get(tail.split("/")[-1],()):
            if fn==tail:result.add(".")
            elif fn.endswith("/"+tail):result.add(fn[:-len(tail)-1])
        return frozenset(result)


def census():
    assert read(OUT/"self_summary.json")["passed"]==16136
    cp41=ART/"cp4_1_v1"
    attest=read(cp41/"migration_stop_seal.json")["batch_files_excluding_this_seal"]["cp3_attributions.jsonl.gz"]["sha256"]
    attributions=rows(gzip.decompress(checked(cp41/"cp3_attributions.jsonl.gz",attest)))
    frozen=ART/"cp3_continue_v1";catalog_hash=read(frozen/"evidence_seal.json")["files"]["unit_inventory.jsonl"]["sha256"]
    catalog={r["unit_id"]:r for r in rows(checked(frozen/"unit_inventory.jsonl",catalog_hash))}
    assert len(catalog)==len(attributions)==31307
    selected=[u for u in attributions if TARGET.intersection(set(u["primary"]["categories"])|set(u["any_categories"]))]
    roots=sorted({catalog[r["unit_id"]]["project_root"] for r in selected if catalog[r["unit_id"]]["project_root"]})
    index=ProjectInventory(roots)
    measured=[]; imports=defaultdict(lambda:defaultdict(set))
    for row in selected:
        uid=row["unit_id"];unit=catalog[uid];root=unit["project_root"];entry=Path(unit["path"])
        assert row["entry_sha256"]==unit["entry_sha256"]
        result=row["selected_result"]
        record=json.loads(checked(result["result_path"],result["result_sha256"]))
        ins={r["path"]:r["sha256"] for r in record["inputs"]}
        assert ins[str(entry)]==unit["entry_sha256"]
        closure={Path(k).relative_to(root).as_posix() if root else entry.name for k in ins}
        wrapper=None
        outside=set()
        if "standard_json_input" in row["any_categories"] or "standard_json_input" in row["primary"]["categories"]:
            raw=checked(entry,unit["entry_sha256"])
            meta=project.standard_json_input(raw)
            assert meta,uid
            obj=project._input_json(raw)
            sources=obj.get("sources",obj)
            if not isinstance(sources,dict) or set(sources)!=set(meta["source_names"]):sources=obj
            assert set(sources)==set(meta["source_names"])
            settings=obj.get("settings",{})
            wrapper=dict(source_count=len(sources),settings_keys=meta["settings_keys"],
                         urls=sum("urls" in v for v in sources.values()),keccak256=sum("keccak256" in v for v in sources.values()),
                         sources_without_content=sum(not isinstance(v.get("content"),str) for v in sources.values()))
            remaps=settings.get("remappings",[]) if isinstance(settings,dict) else []
            parts=[(n,facts(v["content"].encode())) for n,v in sources.items() if isinstance(v.get("content"),str)]
            closure=set(sources)
        else:
            parts=[(Path(n).relative_to(root).as_posix() if root else entry.name,source_facts(n,digest))
                   for n,digest in ins.items()]
            remaps=()
        package_paths=defaultdict(set);unresolved=defaultdict(set);owners=defaultdict(set); local=defaultdict(set)
        for name,(paths,pragmas) in parts:
            for path in paths:
                identity=package_path(path)
                if identity is None:
                    if "://" in path or path.startswith("/"):
                        outside.add(path.split(":",1)[0] if "://" in path else "<absolute>")
                    continue
                pack,tail=identity
                package_paths[pack].add(path)
                try:target=project.source_unit_name(name,path,remaps)
                except ValueError:target=None
                if target in closure or (not wrapper and root and target in index.files[root]):
                    local[pack].add(tail)
                    continue
                unresolved[pack].add(tail);owners[pack].add(name)
                imports[pack][path].update(pragmas or ["<no pragma>"])
        # CP3 also reports import paths discovered when its resolver cannot parse the literal.
        for attempt in record["attempts"]:
            for issue in attempt.get("issues",[]):
                if issue.get("category")!="unresolved_package_import":continue
                path=issue["path"];identity=package_path(path)
                if identity:
                    pack,tail=identity;package_paths[pack].add(path);unresolved[pack].add(tail);owners[pack].add(issue["importer"])
        evidence={}
        for pack,tails in unresolved.items():
            tiers=sorted({index.tier(root,n,pack) for n in owners[pack]})
            dirs=set.intersection(*(set(index.copy_roots(root,pack,t)) for t in tails))
            evidence[pack]=dict(paths=sorted(tails),manifest_evidence=tiers,common_directories=sorted(dirs))
        measured.append(dict(unit_id=uid,corpus=row["corpus"],entry_sha256=unit["entry_sha256"],result_sha256=result["result_sha256"],
                             project_root=root,primary=sorted(TARGET.intersection(row["primary"]["categories"])),
                             any_candidate=sorted(TARGET.intersection(row["any_categories"])),all_prefixes=sorted(package_paths),
                             resolved_prefixes=sorted(local),pending=evidence,wrapper=wrapper,external_schemes=sorted(outside)))
    return measured,roots,index,imports,dict(attributions_sha256=attest,inventory_sha256=catalog_hash,acquisition=index.acquisitions)

def prefix_class(name):
    if name in LOCAL_PREFIX or name.lower().endswith(".sol"):
        return "project_style_prefix"
    if not NPM_NAME.fullmatch(name):
        return "outside_canonical_npm_syntax"
    return "registry_candidate"


def coverage(units, key, order):
    sets=[set(u[key]) for u in units]
    active=[s for s in sets if s]
    def data(n):
        lookup=set(order[:n])
        return dict(prefixes=len(lookup),fully_covered=sum(s<=lookup for s in active),
                    denominator=len(active),any_covered=sum(bool(s&lookup) for s in active))
    result={str(n):data(n) for n in (5,10,20,40)}
    result["all"]=data(len(order))
    return result


def aggregate(units,roots,index,imports,inputs):
    assert units and len(units)==len({u["unit_id"] for u in units})
    packages=Counter(p for u in units for p in u["pending"])
    all_prefixes=Counter(p for u in units for p in u["all_prefixes"])
    ranked=sorted(packages,key=lambda p:(-packages[p],p))
    plausible=[p for p in ranked if prefix_class(p)=="registry_candidate"]
    local_evidence={p:sorted(index.registry_seen[p]) for p in plausible if p in index.registry_seen}
    tiers=Counter();pair_tiers=Counter();tiers_by_root=defaultdict(list)
    copies=Counter();wrappers=[];pkg_tiers=defaultdict(Counter);by_corpus=Counter()
    for u in units:
        by_corpus[u["corpus"]]+=1
        if u["wrapper"] is not None:wrappers.append(u["wrapper"])
        found=[];matched=[]
        for pack,detail in u["pending"].items():
            levels=detail["manifest_evidence"]
            # A whole-unit tier must cover every requested package in the unit.
            tier=max((v[0] for v in levels),default="T3")
            if tier=="T1" and len({tuple(v[1:]) for v in levels})>1:tier="conflicting_T1"
            detail["tier"]=tier
            pair_tiers[tier]+=1;pkg_tiers[pack][tier]+=1;found.append(tier)
            dirs=detail["common_directories"]
            detail["directory_basis"]={d:("node_modules" if ("/node_modules/"+pack+"/") in ("/"+d+"/")
                                           else "lib" if ("/lib/"+pack+"/") in ("/"+d+"/") else "suffix") for d in dirs}
            matched.append(len(dirs))
        u["tier"]=max(found) if found else "no_pending_package"
        tiers[u["tier"]]+=1
        if u["project_root"]:tiers_by_root[u["project_root"]].append(u["tier"])
        if matched:
            bucket=("all_unique" if all(n==1 for n in matched) else "all_covered_with_ambiguity"
                    if all(matched) else "only_some" if any(matched) else "none")
            copies[bucket]+=1
    project_tiers=Counter()
    for root in roots:
        active=[t for t in tiers_by_root[root] if t!="no_pending_package"]
        project_tiers[max(active) if active else "no_pending_package"]+=1
    config_counts={k:sum(any(x["kind"]==k for x in rows) for rows in index.configs.values()) for k in CONFIG}
    tier_spec={}
    for pack in ranked:
        specs=Counter(tuple(v) for u in units if pack in u["pending"] for v in u["pending"][pack]["manifest_evidence"])
        tier_spec[pack]=[dict(tier=k[0],registry_name=k[1],specifier=k[2],unit_count=v) for k,v in sorted(specs.items())]
    def distribution(key):
        return dict(Counter(r[key] for r in wrappers))
    out=dict(inputs=inputs,selection="union of target primary and any-candidate CP4.1 CP3 attributions",
             selected_units=len(units),by_corpus=by_corpus,physical_projects=len(roots),
             standalone_units=sum(not u["project_root"] for u in units),
             selected_by_primary={c:sum(c in u["primary"] for u in units) for c in sorted(TARGET)},
             selected_by_any_candidate={c:sum(c in u["any_candidate"] for u in units) for c in sorted(TARGET)},
             primary_union=sum(bool(u["primary"]) for u in units),
             any_candidate_union=sum(bool(u["any_candidate"]) for u in units),
             configs=dict(project_counts=config_counts,records=dict(index.configs)),
             tier_definition="T1 needs a reachable lock installation and exact release, T2 an applicable dependency spec. Weakest package tier per unit and per project; no pending package is separate.",
             identity=dict(units=tiers,projects=project_tiers,unit_package_pairs=pair_tiers,specifiers=tier_spec),
             copy_coverage=dict(units=copies,basis="common physical directory covering every requested path of each prefix; no compiler or semantic identity claim"),
             wrappers=dict(units=len(wrappers),sources_total=sum(r["source_count"] for r in wrappers),
                           source_count_distribution=distribution("source_count"),settings_key_units=Counter(k for r in wrappers for k in r["settings_keys"]),
                           urls_sources=sum(r["urls"] for r in wrappers),keccak256_sources=sum(r["keccak256"] for r in wrappers),
                           urls_units=sum(bool(r["urls"]) for r in wrappers),keccak256_units=sum(bool(r["keccak256"]) for r in wrappers),
                           sources_without_content=sum(r["sources_without_content"] for r in wrappers)),
             pending_prefixes=dict(units_by_prefix=dict(packages),classification={p:prefix_class(p) for p in ranked},
                                   order_by_unit_count=ranked,plausible_registry_order=plausible,
                                   recorded_registry_versions=local_evidence,registry_existence="unverified except for tarball URLs in checked local package-lock snapshots"),
             coverage=dict(all_observed_prefixes=coverage(units,"all_prefixes",sorted(all_prefixes,key=lambda p:(-all_prefixes[p],p))),
                           pending_all_prefixes=coverage(units,"pending",ranked),
                           pending_npm_candidate_prefixes=coverage(units,"pending",plausible)),
             importer_pragmas={p:{n:sorted(v) for n,v in paths.items()} for p,paths in imports.items()},
             external_imports=dict(units=sum(bool(u["external_schemes"]) for u in units),
                                   schemes=Counter(s for u in units for s in u["external_schemes"])),
             scope="offline CP3 acquisition only; an importer pragma describes the importing file, not the missing file")
    with (OUT/"measurement_units.jsonl.gz").open("xb") as f,gzip.GzipFile(fileobj=f,mode="wb",filename="",mtime=0) as stream:
        for u in units:stream.write((json.dumps(u,sort_keys=True,separators=(",",":"))+"\n").encode())
    out["units_sha256"]=sha((OUT/"measurement_units.jsonl.gz").read_bytes())
    write(OUT/"measurement.json",out)
    print({k:out[k] for k in ("selected_units","primary_union","physical_projects","standalone_units","copy_coverage")})
    print("manifest counts",config_counts,"tier counts",tiers,"packages",len(ranked),"registry candidates",len(plausible))
    print("wrappers",out["wrappers"]["units"],"selected corpora",by_corpus,flush=True)

if __name__=="__main__":aggregate(*census())
