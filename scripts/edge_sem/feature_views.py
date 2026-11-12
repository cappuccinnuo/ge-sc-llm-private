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
    if plan.get("experiment_stage") is not None:
        if plan["experiment_stage"] != "E-A" or registration.get("experiment_stage") != "E-A":
            raise ValueError("Unknown experiment stage")
        if plan.get("scope","formal") != "formal":
            raise ValueError("E-A only permits formal-fit scope")
        role=plan.get("analysis_role")
        expected={"primary":("original",("G3R-T","G4R","G4R-P")),
                  "sensitivity":("anonymous",("G3R","G3R-T","G4R","G4R-P"))}
        if role not in expected or view != expected[role][0]:
            raise ValueError("E-A batch role/view differs")
        batch=registration.get("batches",{}).get(role,{})
        if (registration.get("primary_endpoint",{}).get("view") != "original"
                or batch.get("view") != view or batch.get("profiles") != list(expected[role][1])
                or batch.get("holm_member") is not (role=="primary")):
            raise ValueError("E-A endpoint/registration differs")
        keys=[(j["task_id"],j["fold"],j["edge_profile"]) for j in plan["jobs"]]
        required={(t,f,p) for t in ("reentrancy_node","access_control_node")
                  for f in range(10) for p in expected[role][1]}
        if len(keys)!=len(required) or set(keys)!=required:
            raise ValueError("E-A requires the exact complete batch matrix")
        if role=="sensitivity" and not plan.get("prior_main_plan"):
            raise ValueError("Sensitivity requires its primary predecessor")
        if not plan.get("baseline_plan"):
            raise ValueError("E-A historical baseline binding missing")
        return view
    expected_endpoint="original" if view=="original" else "N-anon-s"
    if (registration.get("feature_policy")!=FEATURE_POLICIES[view]
            or registration.get("primary_endpoint",{}).get("view")!=expected_endpoint):
        raise ValueError("P2 registration primary view differs from execution plan")
    return view
