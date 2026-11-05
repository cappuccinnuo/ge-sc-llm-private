"""DFG v2 profiles; the frozen first-version analyzers remain unchanged."""

VERSION = "dfg-v2"
DATA_DEF_USE = "DATA_DEF_USE"
WRITES_STATE = "WRITES_STATE"
READS_STATE = "READS_STATE"
ENV_FLOW = "ENV_FLOW"
REV_DATA_DEF_USE = "REV_DATA_DEF_USE"
REV_WRITES_STATE = "REV_WRITES_STATE"
REV_READS_STATE = "REV_READS_STATE"
REV_ENV_FLOW = "REV_ENV_FLOW"
ENV_SOURCE = "env_source"

FORWARD_RELATIONS = frozenset({DATA_DEF_USE, WRITES_STATE, READS_STATE, ENV_FLOW})
REVERSE_OF = {
    DATA_DEF_USE: REV_DATA_DEF_USE,
    WRITES_STATE: REV_WRITES_STATE,
    READS_STATE: REV_READS_STATE,
    ENV_FLOW: REV_ENV_FLOW,
}
AUX_NODE_TYPES = frozenset({ENV_SOURCE})

PROFILES = {
    "G0": frozenset(),
    "G1R": frozenset({DATA_DEF_USE, REV_DATA_DEF_USE}),
    "G2R": frozenset({DATA_DEF_USE, WRITES_STATE, READS_STATE,
                       REV_DATA_DEF_USE, REV_WRITES_STATE, REV_READS_STATE}),
    "G3R": FORWARD_RELATIONS | frozenset(REVERSE_OF.values()),
    "G3": FORWARD_RELATIONS,
}


def _validate_profile_relations(profile, relations):
    for forward, reverse in REVERSE_OF.items():
        if reverse in relations and forward not in relations:
            raise ValueError("Profile {} declares {} without {}".format(
                profile, reverse, forward))


def _profile_relations(profile):
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError("Unknown DFG v2 profile: {!r}".format(profile))
    relations = PROFILES[profile]
    # Also validate profiles registered after import (e.g. directional controls).
    _validate_profile_relations(profile, relations)
    return relations


def forward_relations(profile):
    """Relations allowed in the source NetworkX graph for this profile."""
    return _profile_relations(profile) & FORWARD_RELATIONS


def has_reverse(profile, relation):
    """Whether the profile explicitly requests a forward relation's reverse."""
    relations = _profile_relations(profile)
    if relation not in REVERSE_OF:
        raise ValueError("Not a forward DFG v2 relation: {!r}".format(relation))
    return REVERSE_OF[relation] in relations


# Fail during import if a declared reverse has no matching forward relation.
for _profile_name, _relations in PROFILES.items():
    _validate_profile_relations(_profile_name, _relations)
del _profile_name, _relations
