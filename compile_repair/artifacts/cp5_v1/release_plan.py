"""Propose a version-bounded D23 list, then measure official tarball headers without reading release bodies."""
from collections import Counter,defaultdict
import gzip
import json
from pathlib import Path
import sys
import time

from registry_metadata import (HOST, OUT, STABLE, approved, connection, digest, integrity512, journal,
                               load_packument, read, route, write)


def key(version):
    return tuple(map(int,version.split(".")))


def spaced(items,n):
    if len(items)<=n:return items
    if n==1:return [items[-1]]
    return [items[round(i*(len(items)-1)/(n-1))] for i in range(n)]


def representatives(versions):
    """Select at most 12 stable releases before adding exact pins, spanning published major/minor series."""
    if len(versions)<=12:return versions
    by_major=defaultdict(list);by_minor={}
    for v in versions:
        major,minor,_=key(v)
        by_major[major].append(v)
        by_minor[major,minor]=v
    boundaries=sorted({v for release in by_major.values() for v in (release[0],release[-1])},key=key)
    if len(boundaries)>12:return spaced(boundaries,12)
    extra=[v for v in by_minor.values() if v not in boundaries]
    return sorted(boundaries+spaced(extra,12-len(boundaries)) if len(boundaries)<12 else boundaries,key=key)


def prepare():
    req,auth=approved()
    meta=read(OUT/"registry_get_summary.json")
    assert digest((OUT/"registry_gets.jsonl").read_bytes())==meta["journal_sha256"]
    observed=[json.loads(s) for s in (OUT/"registry_gets.jsonl").read_bytes().splitlines()]
    assert [r["name"] for r in observed]==[r["name"] for r in req["packages"]]
    units=[json.loads(s) for s in gzip.decompress((OUT/"measurement_units.jsonl.gz").read_bytes()).splitlines()]
    active=[];pins=defaultdict(set);frequency=Counter()
    for unit in units:
        names=set()
        for alias,p in unit["pending"].items():
            evidence=p["manifest_evidence"]
            candidates={r[1] for r in evidence}
            name=next(iter(candidates)) if len(candidates)==1 else alias
            names.add(name)
            for tier,real,version in evidence:
                if tier=="T1":pins[real].add(version)
        if names:active.append(names);frequency.update(names)
    packages={};available={};excluded=Counter()
    for row in observed:
        name=row["name"]
        obj=load_packument(row)
        exact_name=obj.get("name")==name
        stable={}
        for v,r in obj.get("versions",{}).items():
            if not exact_name or not STABLE.fullmatch(v):continue
            dist=r.get("dist",{});url=dist.get("tarball","");sri=integrity512(dist)
            if not sri or not url.startswith("https://"+HOST+"/"):continue
            route(url)
            if "/-/" not in url:continue
            stable[v]=dict(share_url=url,integrity=sri,unpacked_bytes=dist.get("unpackedSize"),
                           files=dist.get("fileCount"))
        if stable:available[name]=stable
        state=("not_found" if row["http_status"]==404 else "other_canonical_name" if not exact_name else
               "no_stable_sha512_release" if not stable else "verified_registry_name")
        excluded[state]+=1
        packages[name]=dict(state=state,canonical_name=row["canonical_name"],published=row["published_versions"],
                            stable=row["stable_versions"],eligible=len(stable),units=frequency[name],
                            metadata_sha256=row["json_sha256"])
    for name,vs in pins.items():
        if not set(vs)<=set(available.get(name,{})):
            raise ValueError("A measured lock pin lacks a verified SHA512 release: "+name)
    ranking=sorted(available,key=lambda p:(-frequency[p],p))
    scope=list(dict.fromkeys(ranking[:20]+sorted(pins)))
    selected=[]
    for name in scope:
        versions=sorted(available[name],key=key)
        choices=sorted(set(representatives(versions))|pins[name],key=key)
        for v in choices:
            selected.append(dict(package=name,version=v,reason="exact project lock" if v in pins[name] else "stable release representative",
                                 **available[name][v]))
    assert len(selected)<=auth["release_head_limit"]
    def covered(names):
        allowed=set(names)
        return sum(s<=allowed for s in active)
    info=dict(registry=HOST,lookup_states=excluded,candidates=packages,
              ranking=ranking,coverage_denominator=len(active),coverage_basis="whole-unit pending identities, owner-scoped npm aliases only; existence and SRI are insufficient to prove Solidity path compatibility",
              coverage={str(n):covered(ranking[:n]) for n in (5,10,20,40)},coverage_all=covered(ranking),
              proposed_packages=scope,scope_potential=covered(scope),
              selection="First 20 verified names by unit frequency plus every observed T1 pin. Per name up to 12 stable representatives: endpoints per major, then latest patch in spread minor series. Exact pins always included.",
              selected_releases=selected,packages_count=len(scope),release_count=len(selected))
    write(OUT/"release_candidates.json",info)
    print(len(scope),"packages",len(selected),"HEADs; nominally covered",info["scope_potential"],flush=True)


def headers():
    _,auth=approved()
    plan=read(OUT/"release_candidates.json");selected=plan["selected_releases"]
    assert len(selected)<=auth["release_head_limit"] and len({v["share_url"] for v in selected})==len(selected)
    conn=connection();start=time.monotonic()
    with (OUT/"registry_heads.jsonl").open("x") as log:
        for i,row in enumerate(selected):
            url=row["share_url"];path=route(url)
            assert "/-/" in path
            conn.request("HEAD",path,headers={"Host":HOST,"User-Agent":"CompileRepair-CP5/1","Accept-Encoding":"identity"})
            resp=conn.getresponse()
            info=dict(package=row["package"],version=row["version"],url=url,http_status=resp.status,
                      content_length=resp.getheader("Content-Length"),transfer_encoding=resp.getheader("Transfer-Encoding"),
                      etag=resp.getheader("ETag"),content_range=resp.getheader("Content-Range"),date=resp.getheader("Date"),body_bytes=0)
            # HEAD has no response payload under HTTP; tell the connection this response has finished.
            resp.close()
            journal(log,info)
            if resp.status!=200:raise ValueError("Release HEAD returned HTTP "+str(resp.status))
            if (i+1)%25==0:print("HEAD",i+1,flush=True)
    conn.close()
    write(OUT/"registry_head_summary.json",dict(requests=len(selected),elapsed_seconds=round(time.monotonic()-start,3),
          tarball_body_bytes=0,cost_usd=0,journal_sha256=digest((OUT/"registry_heads.jsonl").read_bytes())))
    print("checked",len(selected),"headers",flush=True)


if __name__=="__main__":
    {"plan":prepare,"head":headers}[sys.argv[1]]()
