"""Archive checks allow new code, never changed recorded assets."""
import pytest
from scripts.DFG.integration.archive import verify_recorded_files, verify
from scripts.DFG.integration.io import sha256, write_json


def test_new_sidecar_allowed_but_changed_recorded_file_refused(tmp_path):
    code=tmp_path/"code.py";code.write_text("x=1")
    asset=tmp_path/"graph.dat";asset.write_bytes(b"fixed")
    plan={"runtime":{str(code):sha256(code)},"frozen":{str(asset):sha256(asset)}}
    (tmp_path/"new_sidecar.py").write_text("x=2")
    assert verify_recorded_files(plan)==2
    code.write_text("x=3")
    with pytest.raises(ValueError,match="SHA256"):verify_recorded_files(plan)


def test_conflicting_and_missing_recorded_hash_maps_refused(tmp_path):
    code=tmp_path/"code.py";code.write_text("fixed")
    h=sha256(code)
    with pytest.raises(ValueError,match="Conflicting"):
        verify_recorded_files({"runtime":{str(code):h},"historical_runtime":{str(code):"bad"},"frozen":{str(code):h}})
    with pytest.raises(ValueError,match="Missing"):
        verify_recorded_files({"runtime":{},"frozen":{str(code):h}})


def test_bad_seal_and_unknown_plan_refused(tmp_path):
    write_json(tmp_path/"plan.json",{"version":"unknown"})
    write_json(tmp_path/"plan.seal.json",{"sha256":"bad"})
    with pytest.raises(ValueError,match="seal"):verify(tmp_path)
    write_json(tmp_path/"plan.seal.json",{"sha256":sha256(tmp_path/"plan.json")})
    with pytest.raises(ValueError,match="Unsupported"):verify(tmp_path)
