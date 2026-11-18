"""Check the GPU environment before running the pipeline (python docker/check_env.py).

Prints the resolved versions and checks, in order: the GPU and its compute capability;
that PyTorch was built for it; DGL's GPU kernels used by HGT (edge softmax, message
passing) against the CPU result; the tree-sitter grammar build and a Solidity parse; and
llama.cpp GPU offload. Exits non-zero on the first failed check.
"""
import importlib
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.setdefault("DGLBACKEND", "pytorch")


def check(name, fn):
    try:
        detail = fn()
    except Exception as error:  # report every failure the same way, then stop
        print("FAIL  %-28s %s: %s" % (name, type(error).__name__, error))
        raise SystemExit(1)
    print("ok    %-28s %s" % (name, detail or ""))


def versions():
    rows = [("python", sys.version.split()[0])]
    for name in ("torch", "dgl", "numpy", "networkx", "scipy", "transformers", "tokenizers",
                 "sentence_transformers", "torch_geometric", "tree_sitter", "pydot", "llama_cpp"):
        try:
            module = importlib.import_module(name)
            rows.append((name, getattr(module, "__version__", "?")))
        except ImportError as error:
            rows.append((name, "MISSING (%s)" % error))
    import torch
    rows.append(("torch CUDA / cuDNN", "%s / %s" % (torch.version.cuda, torch.backends.cudnn.version())))
    for name, version in rows:
        print("      %-28s %s" % (name, version))


def gpu():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("torch.cuda.is_available() is False (driver, --gpus all, WSL GPU support?)")
    major, minor = torch.cuda.get_device_capability(0)
    arch = "sm_%d%d" % (major, minor)
    built = torch.cuda.get_arch_list()
    if arch not in built and "compute_%d%d" % (major, minor) not in built:
        raise RuntimeError("PyTorch built for %s, not for this GPU (%s)" % (built, arch))
    x = torch.randn(1024, 1024, device="cuda")
    torch.testing.assert_close((x @ x).cpu(), x.cpu() @ x.cpu(), rtol=1e-3, atol=1e-2)
    free, total = torch.cuda.mem_get_info()
    return "%s, %s, %.1f/%.1f GB free" % (torch.cuda.get_device_name(0), arch, free / 2**30, total / 2**30)


def dgl_kernels():
    import dgl
    import dgl.function as fn
    import torch
    from dgl.nn.functional import edge_softmax

    def run(device):
        torch.manual_seed(0)
        graph = dgl.heterograph({("a", "r", "b"): (torch.randint(0, 50, (400,)), torch.randint(0, 40, (400,))),
                                 ("b", "s", "a"): (torch.randint(0, 40, (300,)), torch.randint(0, 50, (300,)))},
                                num_nodes_dict={"a": 50, "b": 40})
        h = {"a": torch.randn(50, 8, 16), "b": torch.randn(40, 8, 16)}
        score = torch.randn(400, 8, 1)
        graph = graph.to(device)
        sub = graph["r"]
        sub.srcdata["h"] = h["a"].to(device)
        sub.edata["w"] = edge_softmax(sub, score.to(device))
        sub.update_all(fn.u_mul_e("h", "w", "m"), fn.sum("m", "out"))
        return sub.dstdata["out"].cpu()

    torch.testing.assert_close(run("cuda"), run("cpu"), rtol=1e-4, atol=1e-5)
    return "edge_softmax + u_mul_e/sum on GPU equal CPU"


def grammar():
    from hcg.cfg.builder import grammar_dir
    os.environ.setdefault("TREE_SITTER_LIB_DIR", str(grammar_dir()))
    importlib.import_module("mando.graphs.tree_sitter_codeviews.tree_parser.custom_parser")
    from dfg.analysis.frontend import parse
    tree = parse("pragma solidity ^0.4.24;\ncontract A { uint x; function f() public { x = 1; } }\n")
    return "%s, root=%s" % (os.environ["TREE_SITTER_LIB_DIR"], tree.root_node.type)


def llama():
    import llama_cpp
    if not llama_cpp.llama_supports_gpu_offload():
        raise RuntimeError("llama-cpp-python was built without GPU offload")
    return "GPU offload supported"


if __name__ == "__main__":
    versions()
    check("GPU", gpu)
    check("DGL GPU kernels", dgl_kernels)
    check("tree-sitter grammar", grammar)
    check("llama.cpp", llama)
    print("environment ok")
