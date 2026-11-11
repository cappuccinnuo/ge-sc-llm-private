"""Explicit original/anonymous S0 policies; sources come only from sealed indexes."""
from .io import checked,read

FEATURE_POLICIES={"anonymous":"N-anon-s S0","original":"N-original S0"}


def selected_view(record):
    value=record.get("token_view","anonymous")
    if value not in FEATURE_POLICIES:
        raise ValueError("Unknown EdgeSem token view")
    return value


def source_feature(source,task_id,view):
    """Keep the old 8H path unchanged; obtain original S0 from its source plan."""
    if view not in FEATURE_POLICIES:
        raise ValueError("Unknown source token view")
    if view=="anonymous":
        task=source["tasks"][task_id]
        return task["feature_view"],task["feature_npz"]
    prepared=read(checked(source["source_preparation"]))
    reference=prepared["tasks"][task_id]["feature_view"]["original"]
    manifest=read(checked(reference))
    if manifest.get("view")!="original" or manifest.get("task_id")!=task_id:
        raise ValueError("Original feature index identity differs")
    checked(manifest["data"])
    return reference,manifest["data"]


def validate_view(job,plan=None):
    view=selected_view(job)
    manifest=read(checked(job["feature_view"]))
    if (manifest.get("view")!=view or manifest.get("task_id")!=job["task_id"]
            or manifest.get("data")!=job["feature_npz"]):
        raise ValueError("Sealed S0 view identity differs")
    if plan is not None and (selected_view(plan)!=view
            or plan["node_features"]!=FEATURE_POLICIES[view]):
        raise ValueError("Mixed primary feature views")
    return view


def validate_plan_view(plan):
    view=selected_view(plan)
    registration=read(checked(plan["registration"]))
    expected_endpoint="original" if view=="original" else "N-anon-s"
    if (registration.get("feature_policy")!=FEATURE_POLICIES[view]
            or registration.get("primary_endpoint",{}).get("view")!=expected_endpoint):
        raise ValueError("P2 registration primary view differs from execution plan")
    return view
