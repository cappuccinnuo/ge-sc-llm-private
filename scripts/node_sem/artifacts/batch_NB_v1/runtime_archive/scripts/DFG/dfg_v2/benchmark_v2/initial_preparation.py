"""CPU-only reuse of never-trained profile structures, approved for Prompt 8H.

Each G0 anchor is still freshly constructed using the fold's constructor seed.
initialize_family overwrites every receiving parameter using the unchanged
semantic rules. Formal fit workers do not use this cache.
"""
import copy
import gc
from pathlib import Path
import torch
from .runtime_model import make_model
from .prepare import read,write,ref,checked
from ..experiment.init import _check_fresh,initialize_family,seeds
from scripts.DFG.experiments.common import seed_all,tensor_digest

VERSION="prompt8h-untrained-cpu-structure-reuse-v1"
RECEIVERS=("G1R","G2R","G3R","G3")

class UntrainedStructures:
    def __init__(self,granularity,graphs,config):
        self.granularity=granularity
        self.graphs=dict(graphs)
        self.config=copy.deepcopy(config)
        self.models={}

    def get(self,profile):
        if profile not in RECEIVERS:
            raise ValueError("Only enhanced, never-trained CPU receivers may be cached")
        if profile not in self.models:
            c=self.config
            self.models[profile]=make_model(self.granularity,self.graphs[profile],profile,"cpu",
                hidden_size=c["hidden_size"],layers=c["layers"],heads=c["heads"],
                reducer="mean",layer_impl="shared_projection")
        model=self.models[profile]
        _check_fresh(model)
        if any(p.device.type!="cpu" for p in model.parameters()):
            raise ValueError("Preparation reuse is CPU-only")
        return model

def prove():
    """Compare against archived fresh-per-fold preparation, never load it."""
    from .acceptance import DEFAULT
    from .spelling_features import assemble
    auth=read(DEFAULT/"authorization.json")
    plan=read(checked(auth["source_plan"]))
    task_id="reentrancy_contract"; task=plan["tasks"][task_id]
    config=task["effective_config"]
    torch.set_num_threads(2)
    graphs={p:assemble(checked(e["graph"]),task["feature_view"]["anonymous"])
            for p,e in task["profiles"].items()}
    cache=UntrainedStructures(task["granularity"],graphs,config)
    records=[]
    for fold in (0,1,2):
        manifest_path=DEFAULT/"prepared"/task_id/("fold_"+str(fold))/"manifest.json"
        manifest=read(manifest_path)
        sf=seeds(task["granularity"],fold,1)
        assert manifest["seeds"]==sf
        seed_all(sf["constructor"])
        anchor=make_model(task["granularity"],graphs["G0"],"G0","cpu",
            hidden_size=config["hidden_size"],layers=config["layers"],heads=config["heads"],
            reducer="mean",layer_impl="shared_projection")
        for profile in ("G0",)+RECEIVERS:
            seed_all(sf["constructor"])
            model=anchor if profile=="G0" else cache.get(profile)
            initialize_family({"G0":anchor} if profile=="G0" else {"G0":anchor,profile:model},sf["constructor"])
            initial_ref=manifest["profiles"][profile]["initial"]
            initial=torch.load(str(checked(initial_ref)),map_location="cpu")
            assert initial["kind"]=="untrained_initial" and initial["optimizer_steps"]==0
            assert initial["task_id"]==task_id and initial["fold"]==fold and initial["profile"]==profile
            assert initial["constructor_seed"]==sf["constructor"] and initial["fit_seed"]==sf["fit"]
            assert tensor_digest(initial["state_dict"])==initial["state_sha256"]==initial_ref["state_sha256"]
            state=model.state_dict()
            assert set(state)==set(initial["state_dict"])
            assert all(torch.equal(v,initial["state_dict"][k]) for k,v in state.items())
            assert tensor_digest(state)==initial["state_sha256"]
            records.append(dict(task_id=task_id,fold=fold,profile=profile,reference=initial_ref,
                bitwise_equal=True,tensors=len(state),elements=sum(v.numel() for v in state.values()),
                generated_state_sha256=tensor_digest(state),optimizer_steps=0))
            del initial,state
            print("bitwise proven",task_id,fold,profile,flush=True)
        del anchor
        gc.collect()
    report=dict(passed=True,version=VERSION,checks=records,source_preparation=auth["source_plan"],
        implementation=ref(Path(__file__)),initialization=ref(Path(__file__).parents[1]/"experiment/init.py"),
        fresh_reference_source=ref(DEFAULT/"prepare_attempt1_source.py"),
        approval="User approved CPU never-trained structure reuse only after bitwise equality proof",
        constraints=["fresh G0 each fold","all receiver parameters rewritten by existing initialize_family",
            "no optimizer or training in preparation","references used only for comparison, never loaded into generated models",
            "formal workers remain fresh independent processes with sealed initial states and restored fit seeds"])
    write(DEFAULT/"acceptance/structure_reuse.json",report)
    return report

if __name__=="__main__":
    prove()
