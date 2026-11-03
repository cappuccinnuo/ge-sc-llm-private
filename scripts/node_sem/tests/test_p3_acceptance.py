"""Independent acceptance checks for lexical leaks and stored STATIC changes."""
from collections import Counter
import numpy as np
import pytest
from scripts.node_sem.p3_acceptance import masked_identifiers, verify_static
from scripts.node_sem.static_profile import encode, load_schema
from scripts.node_sem.facts_schema import new_facts


def test_masked_scan_accepts_schema_reserved_and_placeholders():
    fields = {"STMT":["STATE1 = PARAM2 + LOCAL3; require(msg.sender == STATE2);"],
              "STATE_DECL":["read_functions=many", "write_functions=zero"],
              "STATE_W":["STATE1:scalar:auth"],"LOOP":["bound:param_local"],"FUNC":["function FUNC1(uint PARAM1) public"]}
    assert not masked_identifiers(fields)


def test_masked_scan_rejects_unconverted_names_and_invalid_placeholders():
    assert masked_identifiers({"STMT":["owner_txorigin7=LOCAL0;"]}) == Counter(
        {"owner_txorigin7":1,"LOCAL0":1})


def test_masked_scan_distinguishes_literals_from_identifiers():
    assert not masked_identifiers({"STMT":['require(LOCAL1, "a retained message"); LOCAL2=0xAbcd;']})


def test_static_acceptance_rejects_changed_bit_and_preserves_unknown_onehot():
    schema=load_schema()
    rows=[{"facts":new_facts("statement")}]
    values=np.stack([encode(rows[0],schema)]).astype(np.float32)
    verify_static(rows,values,schema)
    corrupted=values.copy();corrupted[0,0]=1-corrupted[0,0]
    with pytest.raises(ValueError,match="differs"):verify_static(rows,corrupted,schema)


def test_ctx_fields_seal_uses_named_sidecar_and_rejects_tampering(tmp_path):
    from scripts.node_sem.p3_acceptance import sealed_fields
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref, write
    p=tmp_path/"ctx_fields.manifest.json"
    write(p, {"rows":[]})
    write(p.with_suffix(".seal.json"), {"manifest":ref(p)})
    assert sealed_fields(p)=={"rows":[]}
    p.write_text('{"rows":[1]}', encoding="utf8")
    with pytest.raises(ValueError,match="seal"):sealed_fields(p)
