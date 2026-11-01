"""Validated, ordered feature specifications (Python 3.7 compatible).

A specification may contain null manifest references as a configuration
template. Runtime carrier assembly must reject unbound references. Token IDs
remain 512-dimensional; only raw S0 omits the modality-presence prefix.
"""
import copy
import hashlib
import json
import math

from . import MODALITIES, TOKEN_IDS, VIEWS


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(field + " must be a positive integer")


def _reference(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("manifest must be a sealed reference or null template")
    if set(value) != {"path", "sha256"}:
        raise ValueError("manifest reference requires exactly path and sha256")
    path, sha = value["path"], value["sha256"]
    if not isinstance(path, str) or not path:
        raise ValueError("manifest reference path must be nonempty")
    if (not isinstance(sha, str) or len(sha) != 64
            or any(char not in "0123456789abcdef" for char in sha)):
        raise ValueError("manifest reference requires lowercase SHA256")
    return copy.deepcopy(value)


class FeatureSpec:
    """Immutable field interface; returned modality dictionaries are copies."""

    __slots__ = ("_name", "_view", "_modalities", "_token_mode", "_fusion",
                 "_modality_dropout", "_layers")

    def __init__(self, name, view, modalities, token_mode, fusion,
                 modality_dropout=0.0, layers=None):
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a nonempty string")
        if view not in VIEWS:
            raise ValueError("unknown feature view")
        if not isinstance(modalities, (list, tuple)) or not modalities:
            raise ValueError("modalities must be a nonempty ordered list")
        parsed = []
        for item in modalities:
            if not isinstance(item, dict) or set(item) != {
                    "name", "dim", "manifest", "normalize"}:
                raise ValueError("modality requires name, dim, manifest, normalize")
            if item["name"] not in MODALITIES:
                raise ValueError("unknown modality")
            _positive_int(item["dim"], "modality dim")
            if type(item["normalize"]) is not bool:
                raise ValueError("normalize must be boolean")
            parsed.append(dict(name=item["name"], dim=item["dim"],
                               manifest=_reference(item["manifest"]),
                               normalize=item["normalize"]))
        names = [item["name"] for item in parsed]
        if len(set(names)) != len(names):
            raise ValueError("duplicate modality")
        if token_mode not in ("raw_linear", "embed_pool", "none"):
            raise ValueError("unknown token_mode")
        if fusion not in ("raw_linear", "concat", "gated"):
            raise ValueError("unknown fusion")
        if (isinstance(modality_dropout, bool)
                or not isinstance(modality_dropout, (int, float))
                or not math.isfinite(modality_dropout)
                or not 0.0 <= modality_dropout < 1.0):
            raise ValueError("modality_dropout must be finite and in [0,1)")
        if layers is not None and (
                isinstance(layers, bool) or not isinstance(layers, int) or layers < 0):
            raise ValueError("layers must be None or a nonnegative integer")
        token = next((item for item in parsed if item["name"] == TOKEN_IDS), None)
        if token is not None and (token["dim"] != 512 or token["normalize"]):
            raise ValueError("TOKEN_IDS requires dim=512 and normalize=false")
        if (token is None) != (token_mode == "none"):
            raise ValueError("token_mode disagrees with TOKEN_IDS presence")
        if token_mode == "raw_linear" or fusion == "raw_linear":
            if (token_mode != "raw_linear" or fusion != "raw_linear"
                    or names != [TOKEN_IDS] or modality_dropout != 0):
                raise ValueError("raw_linear requires only TOKEN_IDS and no dropout")
        if name == "S0" and (token_mode != "raw_linear" or names != [TOKEN_IDS]):
            raise ValueError("S0 must use the unmodified raw_linear TOKEN_IDS baseline")
        self._name = name
        self._view = view
        self._modalities = tuple(parsed)
        self._token_mode = token_mode
        self._fusion = fusion
        self._modality_dropout = float(modality_dropout)
        self._layers = layers

    @property
    def name(self):
        return self._name

    @property
    def view(self):
        return self._view

    @property
    def modalities(self):
        return copy.deepcopy(self._modalities)

    @property
    def token_mode(self):
        return self._token_mode

    @property
    def fusion(self):
        return self._fusion

    @property
    def modality_dropout(self):
        return self._modality_dropout

    @property
    def layers(self):
        return self._layers

    def to_json(self):
        return dict(name=self.name, view=self.view,
                    modalities=list(self.modalities), token_mode=self.token_mode,
                    fusion=self.fusion, modality_dropout=self.modality_dropout,
                    layers=self.layers)

    @classmethod
    def from_json(cls, value):
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict) or set(value) != {
                "name", "view", "modalities", "token_mode", "fusion",
                "modality_dropout", "layers"}:
            raise ValueError("FeatureSpec fields are incomplete or unknown")
        return cls(**copy.deepcopy(value))

    def digest(self):
        raw = json.dumps(self.to_json(), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def layout(self):
        raw = self.token_mode == "raw_linear"
        offset = 0 if raw else len(self._modalities)
        result = {}
        for index, item in enumerate(self._modalities):
            result[item["name"]] = dict(
                presence=None if raw else index,
                start=offset, stop=offset + item["dim"])
            offset += item["dim"]
        return result

    def carrier_dim(self):
        prefix = 0 if self.token_mode == "raw_linear" else len(self._modalities)
        return prefix + sum(item["dim"] for item in self._modalities)
