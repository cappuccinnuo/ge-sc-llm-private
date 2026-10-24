"""Offline, provenance-bound tokenizer IDs for DFG v2 auxiliary nodes.

Reuse the frozen prepare.cached_tokenizer and encode_tokenizer_features.encode_ids
recipe. Full tokenization includes special tokens; only encode_ids slices to 512.
The input text is consumed exactly as supplied, including serialized HCG quotes.
No model weights or network assets are loaded.
"""
import copy
import os
from pathlib import Path

import numpy as np

from scripts.DFG.experiments.prepare import (
    TOKENIZER, REVISION, cached_tokenizer, tokenizer_assets)
from scripts.DFG.integration.io import checked, sha256
from scripts.encode_tokenizer_features import encode_ids


FEATURE_SIZE = 512
RECIPE = {
    "scheme": "ids",
    "node_feature": "inside_token",
    "feature_size": FEATURE_SIZE,
    "dtype": "float32",
    "add_special_tokens": True,
    "padding_id": 0,
    "local_files_only": True,
    "model_weights_loaded": False,
}


class TokenEncoder:
    """Callable encoder bound to one frozen task manifest's feature record."""

    def __init__(self, feature):
        if not isinstance(feature, dict):
            raise TypeError("TokenEncoder requires a frozen feature dictionary")
        feature = copy.deepcopy(feature)
        if feature.get("model") != TOKENIZER or feature.get("revision") != REVISION:
            raise ValueError("Frozen tokenizer model/revision mismatch")
        for key, expected in RECIPE.items():
            if feature.get(key) != expected:
                raise ValueError("Frozen tokenizer recipe mismatch: " + key)
        assets = feature.get("asset_hashes")
        if not isinstance(assets, dict) or not assets:
            raise ValueError("Frozen tokenizer requires nonempty asset_hashes")
        for path, value in assets.items():
            if (not isinstance(path, str) or not Path(path).is_absolute()
                    or not isinstance(value, str) or len(value) != 64
                    or any(c not in "0123456789abcdef" for c in value)):
                raise ValueError("Invalid frozen tokenizer asset identity")
        self._assets = copy.deepcopy(assets)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        self.verify_assets()
        self._tokenizer = cached_tokenizer()
        self.verify_assets()
        if type(self._tokenizer).__name__ != feature.get("tokenizer_class"):
            raise ValueError("Frozen tokenizer class mismatch")
        # The frozen recipe uses literal pad ID zero. No fallback to EOS or
        # another padding scheme is permitted for a different tokenizer.
        if self._tokenizer.pad_token_id != RECIPE["padding_id"]:
            raise ValueError("Frozen tokenizer padding ID mismatch")
        root = Path(__file__).resolve().parent
        implementations = {
            "TokenEncoder": Path(__file__).resolve(),
            "cached_tokenizer": root.parent / "experiments" / "prepare.py",
            "encode_ids": root.parent.parent / "encode_tokenizer_features.py",
        }
        self._provenance = dict(RECIPE)
        self._provenance.update({
            "model": TOKENIZER,
            "revision": REVISION,
            "tokenizer_class": type(self._tokenizer).__name__,
            "asset_hashes": copy.deepcopy(self._assets),
            "input_text": "code exactly as supplied; no unquoting or normalization",
            "tokenization_truncation": False,
            "vector_truncation": "first 512 IDs after adding special tokens",
            "padding": "right padding with literal zero",
            "container": "numpy.ndarray",
            "network_used": False,
            "implementation": {
                name: {"path": str(path), "sha256": sha256(path)}
                for name, path in implementations.items()
            },
        })

    def verify_assets(self):
        """Recheck the declared snapshot; reject unbound extra local assets."""
        for path, value in self._assets.items():
            checked(path, value)
        if tokenizer_assets() != self._assets:
            raise ValueError("Local tokenizer asset set differs from frozen manifest")
        return True

    @property
    def provenance(self):
        return copy.deepcopy(self._provenance)

    def __call__(self, code):
        if not isinstance(code, str):
            raise TypeError("TokenEncoder requires exact code text")
        ids = self._tokenizer(code, add_special_tokens=True).input_ids
        result = encode_ids(ids, FEATURE_SIZE, RECIPE["padding_id"])
        if (type(result) is not np.ndarray or result.dtype != np.float32
                or result.shape != (FEATURE_SIZE,) or not np.isfinite(result).all()):
            raise ValueError("Encoded token vector differs from frozen feature format")
        return result
