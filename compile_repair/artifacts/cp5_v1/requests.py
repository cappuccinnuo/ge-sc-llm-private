"""Write the measured D22 request and the bounded registry-metadata prerequisite for D23."""
from pathlib import Path
from urllib.parse import quote
import json

from measurement import OUT, read, sha, write


def main():
    data=read(OUT/"measurement.json")
    common=dict(prompt="r2.22 §4.6g.1",date="2026-11-23",measurement_sha256=sha((OUT/"measurement.json").read_bytes()),
                response_required=True,no_release_archives_fetched=True,cost_usd_limit=0)
    write(OUT/"d22_request.json",dict(common,decision="D22",status="awaiting_user_decision",
          proposed="Read project-owned manifests as version evidence. T1 uses precise lockfile releases, T2 uses declared ranges, T3 uses releases in the frozen index and marks successful compatible choices inferred.",
          checks=["import paths and transitive closure","pragma intersection among 92 supported compilers",
                  "symbols","solc and production Slither D3","provenance and additive-byte check"],
          population=data["selected_units"],tiers=data["identity"]["units"],package_evidence=data["identity"]["unit_package_pairs"],
          scope_note="Manifest npm aliases are scoped to their owner. A matching string in a different project alone does not inherit the alias. Dev selects the release tie-break; test only reports."))
    prefix=data["pending_prefixes"]
    names=sorted(p for p,c in prefix["classification"].items() if c!="project_style_prefix")
    known=prefix["recorded_registry_versions"]
    items=[dict(name=p,units=prefix["units_by_prefix"][p],kind=prefix["classification"][p],
                registry_url="https://registry.npmjs.org/"+quote(p,safe="@"),
                releases_evidenced_in_local_lock=known.get(p,[]))
           for p in names]
    draft=dict(common,decision="D23",status="preliminary_only_not_an_authorization",
               prerequisite="Read-only registry metadata or a user-provided equivalent snapshot. Local checkout has no complete release history, archive Content-Length or reliable unpacked sizes.",
               registry="https://registry.npmjs.org",local_only=True,packages=items,
               selection_proposal="Present a bounded recommendation from the most frequent import identities, keeping all observed T1 pins and multiple stable releases covering historical compiler eras. Report actual versions, counts, known sizes and unknowns before requesting archive authorization.",
               release_count=None,total_compressed_bytes=None,total_unpacked_bytes=None,
               note="Counts and sizes are unknown, not zero; prefix coverage measures potential reach, not repair success.")
    write(OUT/"d23_request_preliminary.json",draft)
    write(OUT/"registry_metadata_request.json",dict(common,status="awaiting_user_authorization",registry="https://registry.npmjs.org",
          methods=["GET package metadata for the named candidates","HEAD official tarball URLs for at most 500 proposed releases, only to inspect published lengths"],
          packages=items,package_get_limit=len(names),tarball_head_limit=500,wire_body_limit_bytes=128*1024**2,
          decoded_metadata_limit_bytes=512*1024**2,release_payload_limit_bytes=0,redirects="same-host https only",
          request_data="package names and registry-provided archive paths only; no corpus bytes, file paths or credentials",
          not_published="Retain explicit status per missing name or size. Do not substitute an estimate for a verified measurement.",
          storage="External local cp5_v1 registry-metadata directory; commit only counts, URLs, hashes and request receipts. Separate D23 approval before any tarball download, extraction or installation."))
    print(len(items),"metadata names;",len(known),"have registry evidence in local locks")

if __name__=="__main__":main()
