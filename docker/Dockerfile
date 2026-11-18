# GPU image for the pipeline (RTX 5080, Blackwell sm_120).
#
#   docker build -f docker/Dockerfile -t mando-llm:5080 .     # from the repository root
#
# Base: an NVIDIA DGL container (DGL 2.5, Python 3.12, CUDA >= 12.8 for sm_120). Default
# 25.05 (CUDA 12.9); 25.08 (CUDA 13.0) is the last one NVIDIA published:
#   docker build -f docker/Dockerfile --build-arg BASE=nvcr.io/nvidia/dgl:25.08-py3 -t mando-llm:5080 .
# The code is not copied in: docker/run.sh mounts the checkout, so the image only
# changes when requirements.txt does.
ARG BASE=nvcr.io/nvidia/dgl:25.05-py3
FROM ${BASE}

ENV DGLBACKEND=pytorch \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/cache/huggingface \
    MPLCONFIGDIR=/tmp/matplotlib

# The container's pip constraints (/etc/pip/constraint.txt) keep its torch/DGL/NumPy stack
# fixed; requirements.txt only adds what the pipeline needs on top.
COPY requirements.txt /opt/mando/requirements.txt
RUN pip install -r /opt/mando/requirements.txt

# llama.cpp with CUDA for `nodesem describe` (Qwen2.5-Coder-3B GGUF), built for sm_120.
# No driver exists during `docker build`, so libcuda is linked against CUDA's stub library;
# the real driver is mounted at run time (--gpus all).
RUN LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LIBRARY_PATH:-} \
    CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120" FORCE_CMAKE=1 \
    pip install llama-cpp-python==0.3.19

# Record the resolved environment inside the image (docker/check_env.py prints it).
RUN mkdir -p /opt/mando /cache && chmod 1777 /cache \
    && pip freeze > /opt/mando/pip-freeze.txt

# Full FP32 like the CPU runs and the sealed experiments: NVIDIA's containers force TF32
# matmuls (TORCH_ALLOW_TF32_CUBLAS_OVERRIDE=1); NVIDIA_TF32_OVERRIDE=0 disables TF32 in all
# kernels (cuBLAS and cuDNN). Last layer, so changing it never rebuilds llama.cpp.
ENV TORCH_ALLOW_TF32_CUBLAS_OVERRIDE=0 \
    NVIDIA_TF32_OVERRIDE=0

WORKDIR /work/repo
