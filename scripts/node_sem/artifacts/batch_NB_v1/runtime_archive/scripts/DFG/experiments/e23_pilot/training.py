"""Frozen paper epoch loop with explicit local handlers; no global monkeypatch."""
import time,threading,subprocess,json
from types import FunctionType
import torch
from scripts.DFG.experiments import paper_run as old
from scripts.DFG.experiments.common import write_json,tensor_digest,seed_all
from scripts.DFG.state.stage_f import FORWARD_RELATIONS
from .runtime import gradient_audit
from .checkpoint import save_checkpoint,restore_checkpoint,snapshot_input

_handlers=dict(old.fit_variant.__globals__,gradient_audit=gradient_audit,
               save_checkpoint=save_checkpoint,restore_checkpoint=restore_checkpoint,
               snapshot_input=snapshot_input)
FIT=FunctionType(old.fit_variant.__code__,_handlers,old.fit_variant.__name__,
                 old.fit_variant.__defaults__,old.fit_variant.__closure__)
assert FIT.__code__ is old.fit_variant.__code__
assert old.fit_variant.__globals__["gradient_audit"] is not gradient_audit

class CardMonitor:
    def __init__(self):
        self.stop=threading.Event();self.samples=[];self.errors=[]
    def sample(self):
        try:
            result=subprocess.run(["/usr/lib/wsl/lib/nvidia-smi","--query-gpu=memory.total,memory.used,memory.free,utilization.gpu","--format=csv,noheader,nounits"],
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=10)
            if result.returncode:self.errors.append(result.stderr.strip())
            else:
                values=[int(v.strip()) for v in result.stdout.strip().split(",")]
                self.samples.append(dict(zip(("total_mib","used_mib","free_mib","utilization_percent"),values)))
        except Exception as exc:self.errors.append(repr(exc))
    def run(self):
        while not self.stop.wait(2):self.sample()
    def __enter__(self):
        self.sample();self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start();return self
    def __exit__(self,*args):
        self.stop.set();self.thread.join(timeout=12);self.sample()
    def report(self):
        return {"samples":self.samples,"errors":self.errors,
                "minimum_whole_card_free_mib":min((x["free_mib"] for x in self.samples),default=None)}

def fit(model,parts,task,labels,config,dest,binding,original_ids,support,initial,fit_seed):
    if tensor_digest(model.state_dict())!=tensor_digest(initial):
        raise ValueError("Fit is not starting from sealed untrained initial state")
    seed_all(fit_seed)
    start=time.perf_counter()
    with CardMonitor() as monitor:
        result=FIT(model,parts,task,labels,config,dest,binding,original_ids,support)
    updates={}
    for relation in sorted(FORWARD_RELATIONS):
        updates[relation]=sum(float((layer.relation_msg.detach().cpu()[idx]-
                 initial["gcs.{}.relation_msg".format(i)][idx]).abs().sum())
                 for i,layer in enumerate(model.gcs) for c,idx in model.etypes_dict.items() if c[1]==relation)
    history=[json.loads(row) for row in (dest/"history.jsonl").read_text().splitlines()]
    stopped_by_patience=history[-1]["patience_counter"]>=config["patience"]
    result.update(early_stopping_triggered=stopped_by_patience,
        reached_epoch_limit=result["history_rows"]==config["maximum_training_epochs"],
        wall_seconds_monotonic=time.perf_counter()-start,
        parameters=sum(p.numel() for p in model.parameters()),fit_seed=fit_seed,
        stop_reason="early_stopping" if stopped_by_patience else
                    "smoke_limit" if config["mode"]=="smoke" else "epoch_limit",
        enhancement_last_message_update_l1=updates,
        resource={"peak_allocated_bytes":torch.cuda.max_memory_allocated(model.device),
                  "peak_reserved_bytes":torch.cuda.max_memory_reserved(model.device),"card":monitor.report()},
        experiment_version=binding["experiment_version"],variant=binding["variant"],
        initialized_from="sealed_untrained_initial_not_smoke_or_prior_fit")
    write_json(dest/"result.json",result)
    write_json(dest/"effective_config.json",config)
    return result
