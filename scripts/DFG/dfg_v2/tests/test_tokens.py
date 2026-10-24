"""Prompt 4 tokenizer recipe/provenance tests; no downloads or model weights."""
import copy
import hashlib
import json
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.DFG.dfg_v2 import tokens
from scripts.DFG.experiments.prepare import cached_tokenizer as frozen_cached_tokenizer
from scripts.encode_tokenizer_features import encode_ids


class FakeTokenizer:
    pad_token_id = 0

    def __init__(self):
        self.calls = []

    def __call__(self, code, **kwargs):
        self.calls.append((code, dict(kwargs)))
        assert kwargs == {"add_special_tokens": True}
        return SimpleNamespace(input_ids=[1] + [ord(c) + 10 for c in code] + [2])


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    asset = tmp_path / "tokenizer_config.json"
    asset.write_text('{"test": true}\n', encoding="utf8")

    def current():
        return {str(asset): hashlib.sha256(asset.read_bytes()).hexdigest()}

    fake = FakeTokenizer()
    loads = []
    def loader():
        loads.append(True)
        return fake
    monkeypatch.setattr(tokens, "tokenizer_assets", current)
    monkeypatch.setattr(tokens, "cached_tokenizer", loader)
    feature = dict(tokens.RECIPE)
    feature.update(model=tokens.TOKENIZER, revision=tokens.REVISION,
                   tokenizer_class="FakeTokenizer", asset_hashes=current())
    return SimpleNamespace(feature=feature, fake=fake, loads=loads,
                           asset=asset, current=current)


def test_exact_text_special_tokens_and_frozen_format(fixture):
    encoder = tokens.TokenEncoder(fixture.feature)
    code = '"require(msg.sender == owner);\\n"'
    value = encoder(code)
    expected = encode_ids([1] + [ord(c) + 10 for c in code] + [2], 512, 0)
    assert fixture.fake.calls == [(code, {"add_special_tokens": True})]
    assert type(value) is np.ndarray
    assert value.dtype == np.float32 and value.shape == (512,)
    assert np.array_equal(value, expected)
    assert value[0] == 1 and value[len(code) + 1] == 2
    assert np.count_nonzero(value[len(code) + 2:]) == 0


def test_complete_ids_then_slice_not_tokenizer_truncation(fixture):
    encoder = tokens.TokenEncoder(fixture.feature)
    code = "x" * 600
    result = encoder(code)
    assert fixture.fake.calls == [(code, {"add_special_tokens": True})]
    assert result[0] == 1
    assert np.all(result[1:] == ord("x") + 10)
    assert 2 not in result  # The EOS beyond the 512-ID boundary is sliced away.


@pytest.mark.parametrize("code", ["", "msg.sender", "now", "gasleft",
                                 '"escaped\\\\n"', " \t\n", "\u03bb"])
def test_repeat_and_reused_encode_ids_equivalence(fixture, code):
    encoder = tokens.TokenEncoder(fixture.feature)
    first, second = encoder(code), encoder(code)
    expected = encode_ids(fixture.fake(code, add_special_tokens=True).input_ids, 512, 0)
    assert np.array_equal(first, second) and np.array_equal(first, expected)
    assert first is not second
    first[0] = 999
    assert second[0] == 1


@pytest.mark.parametrize("bad", [None, b"msg.sender", 1, ["msg.sender"]])
def test_nontext_code_rejected(fixture, bad):
    encoder = tokens.TokenEncoder(fixture.feature)
    with pytest.raises(TypeError, match="exact code text"):
        encoder(bad)
    assert fixture.fake.calls == []


@pytest.mark.parametrize("field,value", [
    ("model", "different/model"), ("revision", "latest"),
    ("scheme", "embedding"), ("node_feature", "nodetype"),
    ("feature_size", 1024), ("dtype", "int64"),
    ("add_special_tokens", False), ("padding_id", 1),
    ("local_files_only", False), ("model_weights_loaded", True),
])
def test_recipe_identity_mismatch_rejected_before_loading(fixture, field, value):
    fixture.feature[field] = value
    with pytest.raises(ValueError, match="mismatch"):
        tokens.TokenEncoder(fixture.feature)
    assert fixture.loads == []


def test_recipe_required_fields_not_silently_defaulted(fixture):
    del fixture.feature["add_special_tokens"]
    with pytest.raises(ValueError, match="add_special_tokens"):
        tokens.TokenEncoder(fixture.feature)
    assert fixture.loads == []


@pytest.mark.parametrize("feature", [None, "feature.json", []])
def test_feature_must_be_manifest_dictionary(feature):
    with pytest.raises(TypeError, match="feature dictionary"):
        tokens.TokenEncoder(feature)


@pytest.mark.parametrize("assets", [{}, None, {"relative.json": "a" * 64},
                                   {"/tmp/config.json": "not-sha256"}])
def test_missing_or_malformed_asset_manifest_rejected(fixture, assets):
    fixture.feature["asset_hashes"] = assets
    with pytest.raises(ValueError, match="asset"):
        tokens.TokenEncoder(fixture.feature)
    assert fixture.loads == []


def test_asset_hash_mismatch_rejected_before_loading(fixture):
    fixture.asset.write_text("changed", encoding="utf8")
    with pytest.raises(ValueError, match="SHA256"):
        tokens.TokenEncoder(fixture.feature)
    assert fixture.loads == []


def test_missing_asset_fails_without_loader_fallback(fixture):
    fixture.asset.unlink()
    with pytest.raises(FileNotFoundError):
        tokens.TokenEncoder(fixture.feature)
    assert fixture.loads == []


def test_unbound_extra_cached_asset_is_rejected(fixture, monkeypatch):
    monkeypatch.setattr(tokens, "tokenizer_assets",
                        lambda: dict(fixture.current(), extra="a" * 64))
    with pytest.raises(ValueError, match="asset set"):
        tokens.TokenEncoder(fixture.feature)
    assert fixture.loads == []


def test_assets_rechecked_after_loading(fixture, monkeypatch):
    def changing_loader():
        fixture.asset.write_text("changed during load", encoding="utf8")
        return fixture.fake
    monkeypatch.setattr(tokens, "cached_tokenizer", changing_loader)
    with pytest.raises(ValueError, match="SHA256"):
        tokens.TokenEncoder(fixture.feature)


def test_verify_assets_detects_later_change(fixture):
    encoder = tokens.TokenEncoder(fixture.feature)
    assert encoder.verify_assets()
    fixture.asset.write_text("later change", encoding="utf8")
    with pytest.raises(ValueError, match="SHA256"):
        encoder.verify_assets()


def test_offline_frozen_loader_flags(fixture, monkeypatch):
    calls = []
    def from_pretrained(*args, **kwargs):
        calls.append((args, kwargs))
        assert os.environ["HF_HUB_OFFLINE"] == "1"
        assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
        assert os.environ["TOKENIZERS_PARALLELISM"] == "false"
        return fixture.fake
    monkeypatch.setitem(sys.modules, "transformers",
                        SimpleNamespace(AutoTokenizer=SimpleNamespace(
                            from_pretrained=from_pretrained)))
    monkeypatch.setattr(tokens, "cached_tokenizer", frozen_cached_tokenizer)
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "TOKENIZERS_PARALLELISM"):
        monkeypatch.setenv(name, "wrong")
    tokens.TokenEncoder(fixture.feature)
    assert calls == [((tokens.TOKENIZER,), {
        "revision": tokens.REVISION, "local_files_only": True,
        "trust_remote_code": False})]


def test_unavailable_local_tokenizer_propagates_no_alternate_load(fixture, monkeypatch):
    def loader():
        raise FileNotFoundError("local snapshot unavailable")
    monkeypatch.setattr(tokens, "cached_tokenizer", loader)
    with pytest.raises(FileNotFoundError, match="snapshot unavailable"):
        tokens.TokenEncoder(fixture.feature)


@pytest.mark.parametrize("pad", [None, 1])
def test_tokenizer_padding_mismatch_rejected(fixture, pad):
    fixture.fake.pad_token_id = pad
    with pytest.raises(ValueError, match="padding ID"):
        tokens.TokenEncoder(fixture.feature)


def test_tokenizer_class_mismatch_rejected(fixture):
    fixture.feature["tokenizer_class"] = "UnexpectedTokenizer"
    with pytest.raises(ValueError, match="class mismatch"):
        tokens.TokenEncoder(fixture.feature)


def test_provenance_is_serializable_bound_and_defensive_copy(fixture):
    original = copy.deepcopy(fixture.feature)
    encoder = tokens.TokenEncoder(fixture.feature)
    provenance = encoder.provenance
    assert provenance["asset_hashes"] == original["asset_hashes"]
    assert provenance["model"] == tokens.TOKENIZER
    assert provenance["revision"] == tokens.REVISION
    assert provenance["tokenization_truncation"] is False
    assert provenance["network_used"] is False
    assert provenance["model_weights_loaded"] is False
    for record in provenance["implementation"].values():
        assert tokens.sha256(record["path"]) == record["sha256"]
    json.dumps(provenance)
    provenance["asset_hashes"].clear()
    fixture.feature["asset_hashes"].clear()
    assert encoder.provenance["asset_hashes"] == original["asset_hashes"]
    assert encoder.verify_assets()
