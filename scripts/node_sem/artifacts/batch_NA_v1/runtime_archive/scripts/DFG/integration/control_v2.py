"""Versioned receiver-binding correction; frozen guard modules remain unchanged.

Only address-member receiver validation and modifier audit metadata differ from
control v1. The existing CFG, postdominator, projection and fusion algorithms are
reused via subclassing and private FunctionType globals, without monkeypatching.
"""
from types import FunctionType

from ..control_dependency import analysis as _analysis
from ..control_dependency import pipeline as _pipeline
from ..control_dependency.cfg import ControlCFGBuilder as _ControlCFGBuilder
from ..frontend import text, walk
from ..models import Unsupported
from ..state.stage_k.profile import SupportedSourceView

VERSION = "guard-control-receiver-validated-v2"
BUILD_VERSION = "author-hcg-ddg-guard-build-v2"


def _bind(function, **overrides):
    namespace = dict(function.__globals__)
    namespace.update(overrides)
    bound = FunctionType(function.__code__, namespace, function.__name__,
                         function.__defaults__, function.__closure__)
    bound.__kwdefaults__ = function.__kwdefaults__
    bound.__doc__ = function.__doc__
    return bound


class ControlCFGBuilderV2(_ControlCFGBuilder):
    """Reject receiver effects needing the unsupported expression CFG."""

    def call_effect(self, node, predicate=False):
        function, _, _ = self.call_parts(node)
        if function.type == "member_expression":
            receiver = function.child_by_field_name("object")
            if receiver is not None:
                for expression in walk(receiver):
                    kind = expression.type
                    unsupported = kind in (
                        "call_expression", "assignment_expression",
                        "augmented_assignment_expression", "update_expression",
                        "new_expression", "assembly_statement", "try_statement",
                    )
                    if kind == "unary_expression":
                        operator = expression.child_by_field_name("operator")
                        unsupported = operator is not None and text(self.view.source, operator) == "delete"
                    if unsupported:
                        raise Unsupported(
                            "guard-v2: receiver evaluation requires expression CFG; "
                            "kind={}; span={}:{}; expression={}".format(
                                kind, expression.start_byte, expression.end_byte,
                                text(self.view.source, expression)))
        return super().call_effect(node, predicate)

    def build(self):
        ir = super().build()
        ir.evidence["legacy_cfg_profile_version"] = ir.evidence.get("version")
        ir.evidence["version"] = VERSION
        ir.evidence["receiver_expression_policy"] = "reject nested calls and side effects by function"
        modifier = ir.evidence.get("modifier")
        if modifier is not None:
            # The old false described the prefix-only profile, not this module's
            # published control facts. Keep its provenance under an explicit name.
            modifier["legacy_prefix_profile_control_dependence_edges"] = modifier.pop(
                "control_dependence_edges", False)
            modifier["control_dependence_analysis_version"] = VERSION
        return ir


_control_facts = _bind(_analysis.control_facts, VERSION=VERSION)
analyze_view = _bind(_analysis.analyze_view, ControlCFGBuilder=ControlCFGBuilderV2,
                     control_facts=_control_facts, VERSION=VERSION)
_augment_template = _bind(_pipeline.augment, analyze_view=analyze_view, VERSION=BUILD_VERSION)


def augment(graph, sources, metadata=None, use_control=True, max_iterations=100000):
    """Thread the explicit postdominator bound through the unchanged pipeline."""
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be positive integer")

    def bounded_analysis(view):
        return analyze_view(view, max_iterations=max_iterations)

    execute = _bind(_augment_template, analyze_view=bounded_analysis)
    output, audit = execute(graph, sources, metadata, use_control)
    audit["requested_max_iterations"] = max_iterations
    audit["effective_max_iterations"] = max_iterations if use_control else None
    return output, audit


def analyze_source(source, file="example.sol", metadata=None, max_iterations=100000):
    view = SupportedSourceView(source, file, metadata)
    return view, analyze_view(view, max_iterations=max_iterations)
