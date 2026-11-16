"""TODO docstring."""
import copy
import hashlib
import json
import math

from nodesem.schema import MODALITIES, TOKEN_IDS, VIEWS



# ----------------------------------------------------------------------
# node_sem/carrier (picked: VERSION, MODALITY_VERSION, _sha_text)
VERSION = "nodesem-carrier-v1"

MODALITY_VERSION = "nodesem-modality-v1"

def _sha_text(value):
    if not isinstance(value, str):
        raise ValueError("Feature code must be a string")
    return hashlib.sha256(value.encode("utf8")).hexdigest()


# ----------------------------------------------------------------------
# node_sem/feature_spec
# Validated, ordered feature specifications (Python 3.7 compatible).
#
# A specification may contain null manifest references as a configuration
# template. Runtime carrier assembly must reject unbound references. Token IDs
# remain 512-dimensional; only raw S0 omits the modality-presence prefix.
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
                or not 0.0 <= modality_dropout <= 1.0):
            raise ValueError("modality_dropout must be finite and in [0,1]")
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


# ----------------------------------------------------------------------
# Feature configurations (the S-series of the NodeSem experiments).
def _modality(name, dim, normalize):
    return dict(name=name, dim=dim, manifest=None, normalize=normalize)


_CODE, _CTX, _STATIC = _modality("code", 256, True), _modality("ctx", 256, True), _modality("static", 245, False)


def _config(name, modalities, token_mode="none", fusion="concat", dropout=0.1, layers=None, view="original"):
    return dict(name=name, view=view, modalities=modalities, token_mode=token_mode, fusion=fusion,
                modality_dropout=dropout, layers=layers)


CONFIGS = {
    "S0o": _config("S0o", [_modality("token_ids", 512, False)], token_mode="raw_linear", fusion="raw_linear",
                   dropout=0.0),
    "S1o": _config("S1o", [_modality("token_ids", 512, False)], token_mode="embed_pool", dropout=0.0),
    "S2": _config("S2", [_CODE], dropout=0.0),
    "S3": _config("S3", [_CODE, _CTX]),
    "S3m": _config("S3m", [_CODE, _CTX]),
    "S4": _config("S4", [_CODE, _CTX, _STATIC]),
    "S4g": _config("S4g", [_CODE, _CTX, _STATIC], fusion="gated"),
    "S4m": _config("S4m", [_CODE, _CTX, _STATIC]),
    "S4-noG": _config("S4-noG", [_CODE, _CTX, _STATIC], layers=0),
    "S6": _config("S6", [_CODE, _CTX, _STATIC, _modality("teacher", 384, True)]),
    "S5": _config("S5", [_CODE, _CTX, _STATIC, _modality("student", 384, True)]),
    "S8": _config("S8", [_CODE, _CTX, _STATIC, _modality("student", 384, True)]),
}
# CTX source per configuration: the masked field rendering for the "m" variants.
CTX_VIEW = {name: ("masked" if name in ("S3m", "S4m") else "original") for name in CONFIGS}
# S5/S6/S8 extend S4: their shared parameters start from S4's initial state.
EXTENDS = {"S5": "S4", "S6": "S4", "S8": "S4"}
# S8 is the permutation control of S5 and shares its modality-dropout random stream.
DROPOUT_PAIR = {"S8": "S5"}


def spec_for(name):
    return FeatureSpec.from_json(CONFIGS[name])


def carry(graph, spec, modalities, token_ids=None):
    """Graph copy whose node ``token`` is the spec's carrier vector.

    ``modalities`` maps a modality name to ``dict(row_keys, values, present)`` with
    rows for every node of ``graph`` (any order; joined by ``row_key``) plus the
    identity columns ``file``, ``node_type`` and ``code_sha256``. ``token_ids``
    (``row_key -> float32[512]``) defaults to the graph's own HCG tokens.
    """
    import copy

    import networkx as nx
    import numpy as np

    from dfg.graph.audit import fingerprint
    from nodesem.rows import row_key, vector_sha
    if not isinstance(graph, nx.MultiDiGraph):
        raise TypeError("Carrier requires a directed multigraph")
    keys = [row_key(n, a) for n, a in graph.nodes(data=True)]
    if len(keys) != len(set(keys)):
        raise ValueError("Graph contains duplicate feature row identities")
    before = fingerprint(graph)
    layout = spec.layout()
    tables = {}
    for modality in spec.modalities:
        name, dim = modality["name"], modality["dim"]
        if name == TOKEN_IDS:
            tokens = token_ids or {row_key(n, a): np.asarray(a["token"], dtype=np.float32)
                                   for n, a in graph.nodes(data=True)}
            tables[name] = {k: (tokens[k], bool(np.any(tokens[k] != 0))) for k in keys}
            continue
        if name not in modalities:
            raise ValueError("Missing modality " + name)
        m = modalities[name]
        values = np.asarray(m["values"])
        if values.dtype != np.float32 or values.shape != (len(m["row_keys"]), dim) or not np.isfinite(values).all():
            raise ValueError("Modality %s shape/dtype/finiteness differs" % name)
        index = {k: i for i, k in enumerate(m["row_keys"])}
        if len(index) != len(m["row_keys"]) or not set(keys) <= set(index):
            raise ValueError("Modality %s rows do not cover the graph" % name)
        for nid, attrs in graph.nodes(data=True):
            i = index[row_key(nid, attrs)]
            if (m["file"][i] != attrs["source_file"] or m["node_type"][i] != attrs["node_type"]
                    or m["code_sha256"][i] != _sha_text(attrs["code"])):
                raise ValueError("Modality %s row identity differs from the graph" % name)
            if not m["present"][i] and np.any(values[i] != 0):
                raise ValueError("Absent modality rows must be zero")
        tables[name] = {k: (values[index[k]], bool(m["present"][index[k]])) for k in keys}
    result, rows = copy.deepcopy(graph), []
    for (nid, attrs), key in zip(graph.nodes(data=True), keys):
        if spec.token_mode == "raw_linear":
            vector, presence = tables[TOKEN_IDS][key][0].astype(np.float32).copy(), []
        else:
            vector, presence = np.zeros(spec.carrier_dim(), dtype=np.float32), []
            for modality in spec.modalities:
                value, present = tables[modality["name"]][key]
                part = layout[modality["name"]]
                vector[part["presence"]] = float(present)
                vector[part["start"]:part["stop"]] = value
                presence.append(present)
        result.nodes[nid]["token"] = vector
        rows.append(dict(row_key=key, vector_sha256=vector_sha(vector), presence=presence))
    if fingerprint(graph) != before:
        raise AssertionError("Carrier changed the input graph")
    return result, dict(version=VERSION, spec=spec.to_json(), spec_sha256=spec.digest(), rows=rows,
                        feature_shape=[len(graph), spec.carrier_dim()])
