# EP6产物与执行记录

新文件采用排他写入；以下是执行记录，不应在已有目录重复生成。
环境：mando；CUDA_VISIBLE_DEVICES为空；PYTHONDONTWRITEBYTECODE=1；OMP_NUM_THREADS=2；MKL_NUM_THREADS=2；TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64。
真实CPU收据由EDGESEM_EP6_PROBE指向本目录real_cpu.json，其他测试复用收据。

    python -B -m scripts.edge_sem.recon.ep6_common
    /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep6_anon_run
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_build_f4_guards.py::test_archived_ep2_is_explicit_and_current_loader_still_rejects scripts/edge_sem/tests/test_build_f4_model.py::test_real_g4r_empty_and_added_edges scripts/edge_sem/tests/test_ep6_archive.py
    /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep6_prereq attributes
    /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.attr_batch --out scripts/edge_sem/artifacts/ep6_v1/attributes
    /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep6_compilers
    /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep6_coverage
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests
    /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep6_prereq f4
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests scripts/DFG/dfg_v2/tests
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_hgt_edge.py scripts/edge_sem/tests/test_ep6_delta.py
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py scripts/edge_sem/tests/test_build_f4_calls.py
    python -B -m scripts.edge_sem.recon.ep6_report
    python -B -m scripts.edge_sem.recon.ep6_verify

包含保留的失败记录。最终实验转服务器，本机限制不代表最终显存预算。

最终报告与验收以 documentation_revision1/summary.json、documentation_revision1/verification.json 为准。该修订更正交接草稿中的fallback预期计数，并补充not_in_graph证据；旧摘要/收据及修改前草稿均保留，训练和属性计算未变。
