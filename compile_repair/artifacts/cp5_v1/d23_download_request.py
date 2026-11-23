"""Combine D23 release identities, actual HEAD results, declared sizes and proposed limits."""
from collections import defaultdict
import json

from registry_metadata import OUT, approved, digest, read, write

MIB=1024**2


def main():
    approved()
    plan=read(OUT/"release_candidates.json")
    header=read(OUT/"registry_head_summary.json")
    raw=(OUT/"registry_heads.jsonl").read_bytes()
    assert digest(raw)==header["journal_sha256"] and header["tarball_body_bytes"]==0
    heads=[json.loads(s) for s in raw.splitlines()]
    assert len(heads)==len(plan["selected_releases"])==header["requests"]
    packages=defaultdict(list)
    for row,h in zip(plan["selected_releases"],heads):
        assert h["package"]==row["package"] and h["version"]==row["version"] and h["http_status"]==200 and h["url"]==row["share_url"]
        packages[row["package"]].append(dict(version=row["version"],registry_url=h["url"],integrity=row["integrity"],
                                             packed_bytes=int(h["content_length"]) if h["content_length"] is not None else None,
                                             unpacked_bytes=row["unpacked_bytes"],reason=row["reason"]))
    def sums(vs,field):
        sizes=[r[field] for r in vs]
        return dict(known_bytes=sum(n for n in sizes if n is not None),known_releases=sum(n is not None for n in sizes),
                    unknown_releases=sum(n is None for n in sizes))
    all_rows=[r for vs in packages.values() for r in vs]
    info=dict(decision="D23",status="awaiting_specific_release_download_authorization",
              prompt="r2.22 §4.6g",metadata_authorization_sha256=digest((OUT/"authorization.json").read_bytes()),
              head_summary_sha256=digest((OUT/"registry_head_summary.json").read_bytes()),
              basis=plan["selection"],registry="https://registry.npmjs.org",cost_usd_limit=0,
              packages=len(packages),releases=len(heads),nominal_units=plan["scope_potential"],denominator=plan["coverage_denominator"],
              packed=sums(all_rows,"packed_bytes"),unpacked=sums(all_rows,"unpacked_bytes"),
              explicit_proposed_size_exception="Accept strict maximums where the official registry supplies no exact size; report observed bytes per archive before extraction and verify known lengths.",
              total_packed_limit_bytes=256*MIB,per_release_packed_limit_bytes=32*MIB,
              total_unpacked_regular_file_limit_bytes=1280*MIB,per_release_unpacked_regular_file_limit_bytes=64*MIB,
              safeguards="Only the listed release URLs. Streaming compressed-byte limit, registry SHA512 and saved SHA256, bounded unpacking, write .sol only below the external index root, never execute install scripts. Preserve an over-limit failure and stop. New release or larger budget requires approval.",
              storage="/home/zhao/SmartContract/corpora/compile-repair-npm-cp5-v1",external_uploads="package request paths only",
              by_package={p:dict(release_count=len(vs),versions=[v["version"] for v in vs],
                                  packed=sums(vs,"packed_bytes"),unpacked=sums(vs,"unpacked_bytes"),releases=vs)
                          for p,vs in packages.items()})
    write(OUT/"d23_download_request.json",info)
    print(info["packages"],info["releases"],info["packed"],info["unpacked"],flush=True)


if __name__=="__main__":main()
