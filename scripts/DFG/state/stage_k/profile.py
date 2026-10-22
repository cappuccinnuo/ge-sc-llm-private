"""Bound analysis to declared supported semantics, not an invented compiler."""
import copy
from ..stage_f.frontend import StageFSourceView
from ..stage_f.versioning import mode_for
from ...models import Unsupported
from . import VERSION

# This is the existing analyzer's semantic domain, not a claim that all programs
# compile in all these versions, or that the author's compiler was in this set.
SUPPORTED = ((0, 4, 0), (0, 9, 0))

class SupportedSourceView(StageFSourceView):
    def __init__(self, source, file, metadata=None):
        super().__init__(source, file, metadata)
        original = self.version_interval
        low, high = max(original[0], SUPPORTED[0]), min(original[1], SUPPORTED[1])
        if low >= high:
            raise Unsupported("K: no intersection with supported semantic domain")
        # Missing/contradictory metadata and legacy/modern scope ambiguity have
        # already failed in Stage F; this must not bypass those checks.
        original_evidence = copy.deepcopy(self.version_evidence)
        self.version_interval = (low, high)
        if mode_for(source, self.tree.root_node, self.version_interval) != self.mode:
            raise Unsupported("K: profile changed lexical scope")
        self.version_evidence = {
            "kind": "explicit_supported_analysis_domain",
            "version": VERSION,
            "source_evidence": original_evidence,
            "pragma_or_recorded_interval": original,
            "supported_domain": SUPPORTED,
            "analyzed_interval": self.version_interval,
            "domain_restricted": original != self.version_interval,
            "excluded_future_interval": (high, original[1]) if high < original[1] else None,
            "exact_compiler": original_evidence.get("metadata", {}).get("version")
                if original_evidence.get("metadata") else None,
            "independently_compiled": False,
            "guarantee": "only supported interval; future versions and full compiler validity not asserted",
        }
