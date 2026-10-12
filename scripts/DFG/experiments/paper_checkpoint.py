"""Paper-CV checkpoints, distinct format and role from nested checkpoints."""
from pathlib import Path
import torch
from scripts.DFG.model_validation import assert_model_input
from .checkpoint import StopMonitor, snapshot_input
from .common import digest, tensor_digest, sha256, write_json
from .paper_protocol import NAME, VERSION, INITIALIZATION_VERSION, FORWARD_SCOPE, SCORE_ROLE
from .paper_runtime import validate_registration

FORMAT = "ddg-paper-cv-checkpoint-v1"


def validate_binding(model, binding):
    for key, value in {"protocol": NAME, "protocol_version": VERSION,
                       "initialization_version": INITIALIZATION_VERSION,
                       "forward_scope": FORWARD_SCOPE, "score_role": SCORE_ROLE}.items():
        if binding.get(key) != value:
            raise ValueError("Checkpoint protocol binding mismatch: " + key)
    validate_registration(model, binding["registered_schema"])


def save_checkpoint(path, model, expected_input, binding, epoch, monitor, optimizer, scheduler):
    validate_binding(model, binding)
    assert_model_input(model, expected_input, external_inputs=binding)
    state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    obj = {"format": FORMAT, "state_dict": state, "state_sha256": tensor_digest(state),
           "model_input": expected_input, "binding": binding, "binding_sha256": digest(binding),
           "epoch": epoch, "monitor": {"best_cv_validation_loss": monitor.best,
                                      "counter": monitor.counter, "reference": monitor.reference},
           "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict()}
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    torch.save(obj, str(temp))
    temp.replace(path)
    write_json(path.with_suffix(".json"), {k: obj[k] for k in (
        "format", "state_sha256", "model_input", "binding", "binding_sha256", "epoch", "monitor")})
    return sha256(path)


def restore_checkpoint(path, model, binding, expected_file_sha256):
    if sha256(path) != expected_file_sha256:
        raise ValueError("Checkpoint file changed")
    obj = torch.load(str(path), map_location=model.device)
    if obj.get("format") != FORMAT:
        raise ValueError("Unsupported paper checkpoint format")
    if obj["binding"] != binding or obj["binding_sha256"] != digest(binding):
        raise ValueError("Checkpoint experiment binding mismatch")
    validate_binding(model, binding)
    assert_model_input(model, obj["model_input"], external_inputs=binding)
    if tensor_digest(obj["state_dict"]) != obj["state_sha256"]:
        raise ValueError("Checkpoint weights changed")
    model.load_state_dict(obj["state_dict"])
    return obj
