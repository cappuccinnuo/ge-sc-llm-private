"""Feature identity, deterministic layout and baseline constraints."""
import copy
import json
from pathlib import Path

import pytest

from scripts.node_sem import ANON, CODE, CTX, TOKEN_IDS, VERSION
from scripts.node_sem.feature_spec import FeatureSpec


def modality(name=TOKEN_IDS, dim=512, manifest=None, normalize=False):
    return dict(name=name, dim=dim, manifest=manifest, normalize=normalize)


def s1(**changes):
    args = dict(name="S1", view=ANON, modalities=[modality()],
                token_mode="embed_pool", fusion="concat",
                modality_dropout=0.0, layers=None)
    args.update(changes)
    return FeatureSpec(**args)


def test_templates_roundtrip_and_stable_canonical_digest():
    assert VERSION == "nodesem-v1"
    root = Path(__file__).resolve().parents[1]
    for name in ("S0", "S1"):
        data = json.loads((root / "configs" / (name + ".json")).read_text())
        spec = FeatureSpec.from_json(data)
        assert spec.to_json() == data
        reordered = dict(reversed(list(data.items())))
        assert spec.digest() == FeatureSpec.from_json(reordered).digest()
        assert spec.digest() == FeatureSpec.from_json(json.dumps(data)).digest()
        assert len(spec.digest()) == 64


def test_layout_keeps_order_presence_prefix_and_raw_baseline():
    raw = FeatureSpec("S0", ANON, [modality()], "raw_linear", "raw_linear")
    assert raw.layout() == {TOKEN_IDS: dict(presence=None, start=0, stop=512)}
    assert raw.carrier_dim() == 512
    embedded = s1()
    assert embedded.layout() == {TOKEN_IDS: dict(presence=0, start=1, stop=513)}
    assert embedded.carrier_dim() == 513
    mixed = s1(name="future", modalities=[
        modality(CODE, 256, normalize=True),
        modality(CTX, 256, normalize=True),
    ], token_mode="none")
    assert mixed.layout() == {
        CODE: dict(presence=0, start=2, stop=258),
        CTX: dict(presence=1, start=258, stop=514),
    }
    assert mixed.carrier_dim() == 514
    swapped = s1(name="future", modalities=list(reversed(mixed.modalities)),
                 token_mode="none")
    assert swapped.digest() != mixed.digest()


def test_manifest_identity_part_of_digest_and_copies_do_not_mutate_spec():
    reference = dict(path="/sealed/token.json", sha256="a" * 64)
    original = [modality(manifest=reference)]
    spec = s1(modalities=original)
    digest = spec.digest()
    reference["path"] = "/changed"
    original[0]["dim"] = 20
    copied = spec.modalities
    copied[0]["manifest"]["sha256"] = "b" * 64
    spec.to_json()["modalities"][0]["dim"] = 100
    assert spec.digest() == digest
    with pytest.raises(AttributeError):
        spec.layers = 0
    changed = spec.to_json()
    changed["modalities"][0]["manifest"]["sha256"] = "b" * 64
    assert FeatureSpec.from_json(changed).digest() != digest


@pytest.mark.parametrize("changes", [
    {"name": ""},
    {"view": "unknown"},
    {"modalities": []},
    {"modalities": [modality(), modality()]},
    {"modalities": [modality("unknown")]},
    {"modalities": [modality(dim=511)]},
    {"modalities": [modality(dim=True)]},
    {"modalities": [modality(normalize=True)]},
    {"modalities": [modality(CODE, -1)], "token_mode": "none"},
    {"modalities": [dict(name=TOKEN_IDS, dim=512, manifest=None)]},
    {"modalities": [modality(manifest={"path": "/x", "sha256": "INVALID"})]},
    {"modalities": [modality(manifest={"path": "/x", "sha256": "a"*64, "extra": 1})]},
    {"token_mode": "none"},
    {"token_mode": "invalid"},
    {"fusion": "unknown"},
    {"fusion": "raw_linear"},
    {"modality_dropout": float("nan")},
    {"modality_dropout": True},
    {"modality_dropout": -0.1},
    {"modality_dropout": 1.0},
    {"layers": -1},
    {"layers": False},
    {"layers": 1.5},
    {"name": "S0"},
])
def test_invalid_spec_rejected(changes):
    with pytest.raises((ValueError, TypeError)):
        s1(**changes)


def test_raw_requires_single_token_without_dropout_and_preserves_zero_layers():
    raw = dict(name="S0", view=ANON, modalities=[modality()],
               token_mode="raw_linear", fusion="raw_linear")
    assert FeatureSpec(**raw).carrier_dim() == 512
    for changes in (
            dict(fusion="concat"),
            dict(modality_dropout=0.1),
            dict(modalities=[modality(), modality(CODE, 256)])):
        damaged = dict(raw, **changes)
        with pytest.raises(ValueError):
            FeatureSpec(**damaged)
    assert s1(layers=0).layers == 0
    assert s1(layers=None).layers is None
    assert s1(layers=0).digest() != s1(layers=None).digest()


def test_json_rejects_unknown_or_missing_fields():
    data = s1().to_json()
    for damaged in (dict(data, surprise=True), {k:v for k,v in data.items() if k != "layers"}):
        with pytest.raises(ValueError):
            FeatureSpec.from_json(damaged)
