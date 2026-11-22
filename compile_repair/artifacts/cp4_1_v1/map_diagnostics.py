"""Bind each old CLI template to its source witness or its recorded reason for retention."""
from collections import Counter
from batch import *
from compile_repair.toolchain.solc import classify_diagnostic, parse_diagnostics

catalog = load("old_other_templates.json")["templates"]
oracle = load("diagnostic_oracle.json")
fixture_path = ROOT/"compile_repair/tests/fixtures/cp4_1/diagnostics.json"
fixtures = json.loads(checked(fixture_path, oracle["fixtures_sha256"]))
expected = {}
results = []
observations = list(rows(OUT/"standard_json_observations.jsonl.gz"))
for item in fixtures:
    i, template = item["id"], item["template"]
    witness = oracle["type_matches"][str(i)]
    ref = next(iter(catalog[template]["examples"].values()))
    provenance = "exact_standard_json" if i != 55 else "version_rejection_across_compiler_releases"
    reason = ""
    if i == 22:
        provenance = "retained_other"
        reason = "The handwritten return with zero values yielded 'Return arguments required.'; none of its typed observations has the archived wrong-arity message."
    if i == 36:
        provenance = "historical_diagnostic_only"
        reason = "The old 0.4.12 tool reports an internal compiler error followed only by std::exception; the user approved a textual witness."
        ref = catalog[template]["examples"]["cp3"]
        record = json.loads(checked(ref["record"]["result_path"], ref["record"]["result_sha256"]))
        assert any(template == classify_diagnostic(d)["template"] for a in record["attempts"] if a.get("solc") for d in parse_diagnostics(a["solc"]["stderr"]))
    if i == 41:
        provenance = "typed_message_family"
        reason = "Both the CLI receipt and the handwritten data-location case report a struct member unavailable outside of storage; only the receiver name/location differs."
        witness = [dict(version=o["version"],type=d["type"],code=d["error_code"],request_sha256=o["request_sha256"])
                   for o in observations if o["id"]==i for d in o["diagnostics"]
                   if d["message"].startswith('Member "') and " is not available in struct " in d["message"]
                   and d["message"].endswith(" outside of storage.")]
        assert witness and all(row["type"]=="TypeError" for row in witness)
    types = sorted({row["type"] for row in witness})
    if i in (9,10,88,89,90) or 60<=i<=86: category = "abi_coder_required"
    elif i in (26,27,28,48): category = "file_level_member"
    elif i==55: category = "version_mismatch"
    elif i==36: category = "internal_compiler_error"
    elif i==22: category = "other"
    else:
        assert len(types)==1,(i, types)
        category = {"ParserError":"parser_error_other","TypeError":"type_error_other",
                    "SyntaxError":"syntax_error","DeclarationError":"declaration_error"}[types[0]]
    diagnostic = classify_diagnostic(dict(kind="Error",message=template), b"contract Witness {}")
    if diagnostic["category"] != category:
        raise ValueError((i,template,category,diagnostic["category"]))
    expected[str(i)] = category
    results.append(dict(id=i,template=template,category=category,standard_json_types=types,provenance=provenance,
                        reason=reason,example=ref,witness=witness,counts=catalog[template]["counts"]))
saved("diagnostic_mapping.json", dict(rows=results,coverage=Counter(r["provenance"] for r in results),
    raw_observations_sha256=sha((OUT/"standard_json_observations.jsonl.gz").read_bytes()),
    classifier_sha256=sha((ROOT/"compile_repair/toolchain/solc.py").read_bytes())))
target = fixture_path.with_name("expected_categories.json")
with target.open("x",encoding="utf8") as fp:
    json.dump(expected,fp,indent=2);fp.write("\n")
print("all templates assigned",len(results),dict(Counter(r["provenance"] for r in results)))
