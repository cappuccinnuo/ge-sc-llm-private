"""Add measured templates without altering the sealed document-derived taxonomy."""
import collections,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from compile_repair.toolchain.solc import parse_diagnostics,classify_diagnostic,diagnostic_template,version_tuple
B=Path(__file__).resolve().parent;old=ROOT/"compile_repair/artifacts/cp3_v1/taxonomy.json"
table=json.loads(old.read_text())
rows=[json.loads(x) for x in (B/"diagnostic_invocations.jsonl").read_text().splitlines()]
standard={(r["version"],r["fixture"]):r for r in rows if r["kind"]=="standard_json_diagnostic_only"}
observed={};formats={};duplicates=collections.defaultdict(list)
for row in rows:
 if row["kind"]!="combined_json":continue
 version=row["compiler"]["version"]; fixture=row["fixture"]
 raw=(ROOT/"compile_repair/tests/fixtures/cp3_diagnostics"/(fixture+".sol")).read_bytes()
 for d in parse_diagnostics(row["stderr"]):
  classification=classify_diagnostic(d,raw)
  key=(classification["category"],classification["template"])
  record=observed.setdefault(key,{"category":key[0],"template":key[1],"verified_versions":set(),"fixtures":set(),
                                 "cli_kinds":set(),"location_formats":set(),"standard_json_type_evidence":[]})
  record["verified_versions"].add(version);record["fixtures"].add(fixture)
  record["cli_kinds"].add(d["kind"]);record["location_formats"].add(d["location_format"])
  for e in standard.get((version,fixture),{}).get("errors",[]):
   if diagnostic_template(e.get("message",""))==classification["template"]:
    record["standard_json_type_evidence"].append({"version":version,"type":e.get("type"),
      "error_code":e.get("errorCode"),"source_location_present":"sourceLocation" in e})
 if fixture=="missing_semicolon":
  errors=[d for d in parse_diagnostics(row["stderr"]) if d["kind"]!="Warning"]
  formats[version]=errors[0]["location_format"]
 if fixture.startswith("duplicate_"):
  duplicates[fixture].append({"version":version,"returncode":row["returncode"],
   "error_first_line":row["error_first_line"],"source_sha256":row["source_sha256"]})
for record in observed.values():
 for key in ("verified_versions","fixtures","cli_kinds","location_formats"):
  record[key]=sorted(record[key],key=version_tuple) if key=="verified_versions" else sorted(record[key])
for category in table["categories"]:
 matched=[r for r in observed.values() if r["category"]==category["category"]]
 category["observed_templates"]=matched
 category["verified_versions"]=sorted({v for r in matched for v in r["verified_versions"]},key=version_tuple)
 category["d6_route_status"]="candidate only; implementation outside CP3"
table.update(schema="cp3-taxonomy-v2-probed",previous_taxonomy_sha256=hashlib.sha256(old.read_bytes()).hexdigest(),
 observations_source="diagnostic_invocations.jsonl",compiler_format_probe={"fixture":"missing_semicolon",
 "every_supported_version_tested":92,"modern_location_first_version":"0.6.0","versions":formats},
 duplicate_directive_observations=dict(duplicates),
 codegen_evidence="codegen_probe_summary.json",
 project_graph_decision="project_identity_authorization.json",
 limitations=["Verified versions are exact tested sets, not inferred patch ranges.",
 "Standard JSON InternalCompilerError on malformed old input is supplementary API behavior, not the CLI diagnostic type.",
 "Generic compiler crashes are covered with explicitly synthetic type-interface tests; no crash frequency is inferred.",
 "Slither timeout support and pragma unions remain future changes; no automatic legal-source rewrite."])
with (B/"taxonomy_verified.json").open("x") as f:json.dump(table,f,ensure_ascii=False,indent=2);f.write("\n")
with (B/"template_observations.json").open("x") as f:json.dump(list(observed.values()),f,ensure_ascii=False,indent=2);f.write("\n")
assert len(table["categories"])==29 and len(table["breaking_changes"])==125
assert all(formats[v]==("legacy" if version_tuple(v)<(0,6,0) else "modern") for v in formats)
print(json.dumps({"categories":len(table["categories"]),"breaking_entries":len(table["breaking_changes"]),
 "observed_templates":len(observed),"version_formats":len(formats),"modern_start":"0.6.0"}))
