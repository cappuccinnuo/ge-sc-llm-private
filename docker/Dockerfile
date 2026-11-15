# Training image for the RTX 5080 (Blackwell, sm_120) machine.
#
# Why this base: Blackwell needs CUDA >= 12.8 and PyTorch >= 2.7, while DGL's own
# pip wheels stop at torch 2.4 / CUDA 12.4. NVIDIA's DGL container is the only
# prebuilt DGL for Blackwell (25.01-25.08 ship DGL 2.5 on CUDA 12.8-13.0). NVIDIA
# ended that container line after 25.08, so the tag is pinned here and will not move.
#
# The repository is bind-mounted at run time rather than copied, so code changes do
# not need a rebuild and outputs land on the host:
#
#   docker build -t mando-llm:5080 -f docker/Dockerfile docker
#   docker run --gpus all --rm -it --shm-size 8g \
#     -v "$PWD":/workspace/ge-sc-llm -v "$HOME/.cache/huggingface":/root/.cache/huggingface \
#     mando-llm:5080
#
# Host requirements: NVIDIA driver >= 570 (open kernel module on Linux) and the
# NVIDIA Container Toolkit. On Windows, run this from WSL2 with Docker Desktop.
FROM nvcr.io/nvidia/dgl:25.08-py3

# TREE_SITTER_LIB_DIR: the grammar in git is a macOS binary; compile per platform
# into the git-ignored <repo>/build/linux-x86_64, the old machine's convention.
ENV DGLBACKEND=pytorch \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TREE_SITTER_LIB_DIR=/workspace/ge-sc-llm/build/linux-x86_64

# The NGC image pins its torch/dgl through a pip constraint file; installing on top
# keeps them. gcc is already present for compiling the tree-sitter grammar.
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt \
 && python -c "import torch, dgl; print('torch', torch.__version__, 'cuda', torch.version.cuda, 'dgl', dgl.__version__)"

WORKDIR /workspace/ge-sc-llm
CMD ["bash"]
