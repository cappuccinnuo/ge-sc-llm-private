"""Read-only GPU sampling; resource gates never change the numerical config."""
import subprocess
import threading
import time
import torch


class MemoryGateError(RuntimeError):
    pass


class Resources:
    def __init__(self, device, minimum_free_mib=100):
        self.cuda = str(device).startswith("cuda")
        self.minimum = minimum_free_mib
        self.started = time.monotonic()
        self.samples = []
        self.errors = []
        self.done = threading.Event()
        self.thread = None

    def sample(self):
        if not self.cuda:
            return
        try:
            raw = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                timeout=3).decode().strip().splitlines()
            # Single-GPU target. Refuse silently monitoring the wrong device.
            if len(raw) != 1:
                raise ValueError("Expected one target GPU")
            self.samples.append(float(raw[0]))
            return True
        except Exception as error:
            self.errors.append(str(error))
            return False

    def _watch(self):
        while not self.done.wait(.5):
            self.sample()

    def __enter__(self):
        if self.cuda:
            torch.cuda.reset_peak_memory_stats()
            self.sample()
            self.thread = threading.Thread(target=self._watch, daemon=True)
            self.thread.start()
        return self

    def check(self):
        measured = self.sample()
        if self.cuda and not measured:
            raise MemoryGateError("Current whole-card memory measurement failed; refusing stale sample")
        if self.cuda and not self.samples:
            raise MemoryGateError("Whole-card free memory measurement unavailable")
        if self.cuda and min(self.samples) < self.minimum:
            raise MemoryGateError("Whole-card free memory below {} MiB: {} MiB".format(
                self.minimum, min(self.samples)))

    def summary(self):
        return dict(seconds=time.monotonic()-self.started,
            peak_allocated_mib=torch.cuda.max_memory_allocated()/1024**2 if self.cuda else None,
            peak_reserved_mib=torch.cuda.max_memory_reserved()/1024**2 if self.cuda else None,
            minimum_free_mib=min(self.samples) if self.samples else None,
            whole_card_sampling_seconds=.5, memory_samples=len(self.samples),
            sampling_errors=self.errors, device="cuda" if self.cuda else "cpu")

    def __exit__(self, *args):
        self.done.set()
        if self.thread:
            self.thread.join(timeout=4)
        self.sample()
