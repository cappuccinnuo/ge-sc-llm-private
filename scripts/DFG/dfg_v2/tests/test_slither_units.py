"""L2 statement counting does not change L1 events or any graph."""
import copy
import pytest
from scripts.DFG.dfg_v2.slither_align import _normalize, match_spans
from scripts.DFG.dfg_v2.slither_units import normalize_l2_units, unit_comparison

RAW = b"uint s; function f() { return s + s; s = s; }"
START = RAW.index(b"return")
END = RAW.index(b";", START)+1
FUNCTIONS = [{"start":8, "status":"supported"}]

def row(a, b=None, kind="READS_STATE", statement=None):
    return dict(file="x.sol", callable="x.sol:8", relation=kind,
                state=dict(start=0,end=7,name="s"), occurrence=dict(start=a,end=b or a+1),
                statement=statement or dict(file="x.sol",start=START,end=END,role="return_statement"))

def lexical(rows):
    return _normalize(rows, "v2", "L2", RAW, FUNCTIONS)

def refs():
    return [dict(event_id="r", name="s", kind="READ", span=[START,END])]

def test_repeated_read_collapses_only_inside_same_statement():
    a=RAW.index(b"s +"); b=a+4
    old=lexical([row(a),row(b)])
    units=normalize_l2_units(old,RAW)
    assert len(old)==2 and len(units)==1
    assert units[0]["span"]==[START,END]
    assert len(units[0]["evidence"])==2
    assert set(units[0]["lexical_event_ids"])=={e["event_id"] for e in old}
    assert len(match_spans(old,refs())[1])==1
    assert len(match_spans(units,refs())[1])==0

def test_reads_and_writes_and_different_statements_stay_separate():
    a=RAW.index(b"s +"); second=RAW.index(b"s =")
    rows=[row(a),row(a,kind="WRITES_STATE"),
          row(second,statement=dict(file="x.sol",start=second,end=second+6,role="expression_statement"))]
    assert len(normalize_l2_units(lexical(rows),RAW))==3

def test_union_fallback_records_outside_occurrence():
    a=RAW.index(b"s +")
    units=normalize_l2_units(lexical([row(a,statement=dict(file="x.sol",start=a+1,end=a+2,role="return_statement"))]),RAW)
    assert units[0]["span"]==[a,a+2]
    assert units[0]["anchor_rule"]=="statement_occurrence_union_fallback"

def test_missing_statement_does_not_guess_nearest():
    a=RAW.index(b"s +"); rows=[row(a),row(a+4)]
    for x in rows: x.pop("statement")
    units=normalize_l2_units(lexical(rows),RAW)
    assert len(units)==2
    assert all(x["anchor_rule"]=="occurrence_fallback" for x in units)

def test_conflicting_declaration_rejected_not_merged_by_name():
    a=RAW.index(b"s +"); rows=[row(a),row(a+4)]
    rows[1]["state"]=dict(start=1,end=7,name="s")
    with pytest.raises(ValueError,match="Ambiguous declaration"):
        normalize_l2_units(lexical(rows),RAW)

def test_different_callable_not_merged():
    a=RAW.index(b"s +"); rows=[row(a),row(a+4)]
    rows[1]["callable"]="x.sol:9"
    assert len(normalize_l2_units(lexical(rows),RAW))==2

def test_provenance_distinguishes_duplicate_from_anchor_change():
    a=RAW.index(b"s +"); old=lexical([row(a),row(a+4)])
    units=normalize_l2_units(old,RAW); m,extra,_=match_spans(old,refs())
    prior=[dict(event_id=extra[0]["event_id"],difference_id="old")]
    result=unit_comparison(old,units,refs(),match_spans(units,refs())[0],prior)
    assert result["duplicate_counting_resolved"]==1
    assert result["anchor_or_matching_resolved"]==0
    assert result["old_fp_resolution"][0]["old_difference_id"]=="old"

def test_wrong_old_identity_rejected():
    a=RAW.index(b"s +"); old=lexical([row(a),row(a+4)])
    with pytest.raises(ValueError,match="replay exactly"):
        unit_comparison(old,normalize_l2_units(old,RAW),refs(),[],[])

def test_input_evidence_not_mutated():
    a=RAW.index(b"s +"); old=lexical([row(a),row(a+4)]); before=copy.deepcopy(old)
    normalize_l2_units(old,RAW)
    assert old==before

def test_unit_id_does_not_depend_on_occurrence_order():
    a=RAW.index(b"s +"); old=lexical([row(a),row(a+4)])
    x=normalize_l2_units(old,RAW)[0];y=normalize_l2_units(list(reversed(old)),RAW)[0]
    assert x["event_id"]==y["event_id"] and x["lexical_event_ids"]==y["lexical_event_ids"]


def test_compare_file_binding_diagnostic_integration():
    from scripts.DFG.dfg_v2.slither_align import compare_file
    raw=b"contract C { uint s; function f() public { s = 1; } }"
    start=raw.index(b"s ="); fn=raw.index(b"function"); decl=raw.index(b"uint s")
    record=dict(file="x.sol",source_sha256="test",version="0.5.11",version_origin="metadata",
                status="compared",v2_scope={"L1":{"functions":[],"occurrences":[]}},
                slither_extraction={"occurrences":[dict(layer="L2",node=dict(start=start,end=start+5),
                    fact=[1,"s","WRITE"],declaration=dict(start=decl,end=decl+7),
                    function=dict(start=fn,end=len(raw)-2),tags=[])]},
                comparison={x:dict(extra=[],missing=[]) for x in ("L1","L2")})
    audit={"layers":{"L2":{"evidence":[],"files":{"x.sol":{"diagnostics":[dict(
        kind="state_binding_unresolved",reason="state_name_ambiguous",name="s",
        start=start,end=start+1,callable="x.sol:"+str(fn))]}}}}}
    result,differences=compare_file("task",record,raw,audit,"x.sol",{},[])
    assert len(differences)==1
    assert differences[0]["category"]=="v2_binding_unresolved"
    assert differences[0]["classification_evidence"]["binding_subtypes"][0]["reason"]=="state_name_ambiguous"


def test_enclosing_unit_read_does_not_become_a_body_read():
    from scripts.DFG.dfg_v2.slither_align import _access_overlaps
    candidate=dict(span=[10,90], evidence=[{"occurrence":{"start":12,"end":17}}])
    assert not _access_overlaps(candidate,[40,60])
    assert _access_overlaps(candidate,[12,20])


@pytest.mark.parametrize("change",["version","store","report",None])
def test_prior_alignment_binds_exact_reference_report_and_version(change):
    from scripts.DFG.dfg_v2.slither_align import validate_prior_binding
    prior={"version":"dfg-v2-slither-span-alignment-v3",
           "inputs":{"store":{"sha256":"s"},"report":{"sha256":"r"}}}
    if change=="version": prior["version"]="wrong"
    elif change: prior["inputs"][change]["sha256"]="wrong"
    if change:
        with pytest.raises(ValueError): validate_prior_binding(prior,"s","r")
    else: validate_prior_binding(prior,"s","r")
