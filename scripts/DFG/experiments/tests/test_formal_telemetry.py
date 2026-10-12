import json
from argparse import Namespace
import pytest
import torch
from scripts.DFG.experiments import formal_worker, resource_probe, paper_run


def test_cpu_telemetry_does_not_create_cuda_state():
    assert formal_worker.memory("cpu") == {"device": "cpu", "cuda": False}
    model = torch.nn.Linear(3, 2)
    assert formal_worker.parameters(model)["total"] == 8


def test_wrapper_restores_original_functions_on_failure(monkeypatch):
    original_make, original_fit = paper_run.make_model, paper_run.fit_variant
    def fail(args):
        assert paper_run.make_model is not original_make
        raise RuntimeError("fixture error")
    monkeypatch.setattr(paper_run, "run", fail)
    with pytest.raises(RuntimeError, match="fixture error"):
        formal_worker.execute(Namespace())
    assert paper_run.make_model is original_make
    assert paper_run.fit_variant is original_fit


def test_missing_cuda_reports_block_without_cpu_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(resource_probe, "hardware", lambda: {"cuda_available": False})
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    report = resource_probe.probe(Namespace(output=str(tmp_path/"resource.json"), device="cuda:0",
        task="contract", prepared=str(tmp_path), splits=str(tmp_path/"split.json"), threads=1))
    assert report["status"] == "blocked"
    assert report["steps"] == {}
    assert (tmp_path/"resource.json").exists()
