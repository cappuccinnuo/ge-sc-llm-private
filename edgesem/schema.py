"""EdgeSem relation registry: new E1 relations, relation families, profiles and the frozen
attribute selection. DFG profiles are never modified; EdgeSem profiles derive from G3R.
"""
VERSION = "edgesem-v1"

NEW_RELATIONS = ("MOD_APPLY", "CALL_SITE", "GUARDS")

REVERSE_PREFIX = "REV_"

FAMILIES = frozenset(("control", "call", "data", "guard", "structure"))

RELATION_FAMILY = {
    "next_line": "control", "next": "control", "first_next_line": "control",
    "pos_next": "control", "neg_next": "control", "end_if": "control",
    "if_true": "control", "if_false": "control",
    "cf_back": "control", "internal_call": "call", "external_call": "call",
    "recursive_method_call": "structure", "DATA_DEF_USE": "data",
    "WRITES_STATE": "data", "READS_STATE": "data", "ENV_FLOW": "data",
    "MOD_APPLY": "call", "CALL_SITE": "call", "GUARDS": "guard",
}

RELATION_FAMILY.update({REVERSE_PREFIX+r: family for r, family in list(RELATION_FAMILY.items())})

def _profile(mode="typed", new=True, features="none", placebo="none"):
    # EP0 measured <50 projected back edges in every task: disabled.
    return dict(direction_mode=mode, cf_back=False,
                new_relations=frozenset(NEW_RELATIONS if new else ()),
                edge_features=features, placebo=placebo)

PROFILES = {
    "G3R": _profile("merge", False),
    "G3R-T": _profile(new=False),
    "G4R": _profile(),
    "G4R-P": _profile(placebo="relations"),
    "G4R-A": _profile(features="core"),
    "G4R-Api": _profile(features="core", placebo="attributes"),
    "G4R-AC": _profile(features="core_context"),
    "G3R-TA": _profile(new=False, features="core"),
}

def validate_profile(profile, layer_type=None):
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError("Unknown EdgeSem profile: {!r}".format(profile))
    spec = PROFILES[profile]
    if set(spec) != {"direction_mode", "cf_back", "new_relations", "edge_features", "placebo"}:
        raise ValueError("Incomplete EdgeSem profile")
    if spec["direction_mode"] not in ("merge", "typed") or type(spec["cf_back"]) is not bool:
        raise ValueError("Invalid direction/cf_back policy")
    if profile.startswith("G4R") and spec["direction_mode"] != "typed":
        raise ValueError("G4R profiles require typed directions")
    if not isinstance(spec["new_relations"], (set, frozenset)) or not spec["new_relations"] <= set(NEW_RELATIONS):
        raise ValueError("Unknown new relations")
    if spec["edge_features"] not in ("none", "core", "core_context"):
        raise ValueError("Unknown edge feature mode")
    if spec["placebo"] not in ("none", "relations", "attributes"):
        raise ValueError("Unknown placebo mode")
    if spec["placebo"] == "attributes" and spec["edge_features"] == "none":
        raise ValueError("Attribute placebo needs edge features")
    if layer_type is not None and spec["edge_features"] != "none":
        # EP6 supplies this class; accepting a same-named foreign class is unsafe.
        try:
            from edgesem.model.layers import EdgeAwareHGTLayer
        except ImportError:
            raise ValueError("EdgeAwareHGTLayer is not implemented until EP6")
        if not issubclass(layer_type, EdgeAwareHGTLayer):
            raise ValueError("Edge features require EdgeAwareHGTLayer")
    return dict(spec)

for _name in PROFILES:
    validate_profile(_name)

del _name

# Attribute columns frozen by EdgeSem v1 (selected on the reentrancy/access-control node
# tasks before any label access, then fixed for every task): G*-A profiles read the core
# columns, G4R-AC the union of core and context columns.
CORE_INDICES = (0, 1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
                31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 68, 69,
                71, 72)
CONTEXT_INDICES = (3, 4, 16, 18, 30, 41, 42, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 69, 70,
                   71, 72, 73)

# Training protocol P2: the DFG task config with early stopping disabled (patience beyond
# the 50-epoch schedule), so every fit runs 50 epochs and keeps the strict-minimum
# inner-validation checkpoint.
P2_OVERRIDES = dict(patience=51)

# Profiles in run order: the G3R baseline, structural contrasts, then attribute profiles.
TRAIN_PROFILES = ("G3R", "G3R-T", "G4R", "G4R-P", "G3R-TA", "G4R-A", "G4R-Api", "G4R-AC")
