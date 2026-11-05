"""Versioned fixed-HCG entry for implemented DDG capability profiles."""
VERSION = "ddg-integration-v1"
RELATIONS = frozenset(("DATA_DEF_USE", "STATE_DEF_USE", "STATE_ACCESS_ORDER",
                       "EXTERNAL_CALL_BEFORE_STATE_WRITE", "CONTROL_DEPENDENCE"))
PROFILES = {"baseline": frozenset(), "scalar": frozenset(("DATA_DEF_USE",)),
            "full": RELATIONS - {"CONTROL_DEPENDENCE"}, "full_guard": RELATIONS}
