# 函数内正向 DDG（第一阶段）

新增逻辑位于本目录；只附加 DATA_DEF_USE。详见 [逐阶段实施记录](IMPLEMENTATION_NOTES.md) 和 [原接入分析](DDG_INTEGRATION_ANALYSIS_2026-10-11.md)。

当前支持局部标量、参数、命名返回值的直接定义—使用依赖。复杂类型、副作用、modifier 等采用保守回退，保留原合约、函数和节点。缺少原 HCG 节点的事实会跳过并报告。没有 REV_DATA_DEF_USE。

## 在 WSL 验证

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm
conda activate mando
export TREE_SITTER_LIB_DIR="$PWD/build/linux-x86_64"

PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/tests \
  tests/test_graph_utils.py tests/test_model_imports.py \
  tests/test_classifier_cli.py tests/test_early_stopping.py
~~~

本轮结果：140 passed。不会运行完整数据集训练。

最小示例（输出目录必须未存在；再次运行请换目录名）：

~~~bash
python -B -m scripts.DFG.demo \
  --output scripts/DFG/artifacts/minimal_manual_v1
~~~

使用已缓存的 CodeT5p-770m tokenizer、现有 encode_ids、原构图器和两类 HGT。11 节点、12 原边，新增7条直接依赖；模型做一次优化、保存/重载。测试例不是漏洞数据集，不报告 F1。本轮已运行的结果在 artifacts/minimal_20261012_v1/result.json。

## 对现有图开关 DDG

输入应是已经含原 token 特征的原始 HCG。两个模式用同一输入，不能给 off 模式传已增强图。

以下以重入的本地 narrow 全量图为例：

~~~bash
python -B -m scripts.DFG.cli \
  --graph experiments/ge-sc-data/source_code/reentrancy/tokenizer_ids_narrow.gpickle \
  --source_dir experiments/ge-sc-data/source_code/reentrancy/source_files \
  --output scripts/DFG/artifacts/reentrancy_narrow_forward_v1 \
  --use_ddg
~~~

保持原图的对照：

~~~bash
python -B -m scripts.DFG.cli \
  --graph experiments/ge-sc-data/source_code/reentrancy/tokenizer_ids_narrow.gpickle \
  --output scripts/DFG/artifacts/reentrancy_narrow_baseline_v1 \
  --no_ddg
~~~

默认是 --no_ddg。行级输入可换为原来的 linelevel_narrow.gpickle，单独输出到新的目录；不要把全量图与漏洞文件子图的样本范围混为一谈。作者图、本地图使用同一分析实现；没有 token 的图需先用既有特征流程编码，DDG CLI 不自动补特征或标签。

每次输出：

- hcg.gpickle：原节点、特征、标签、基础边均保留的新图。
- audit.json：源码/输入/grammar 摘要、函数支持/回退、事实投影、缺失锚点、不变量与新增边统计。
- source_manifest.json：本轮使用的精确文件身份、路径、SHA；可作为后续固定输入的清单。

可用 --source_manifest 替代 --source_dir：

~~~json
{
  "buggy_18.sol": {
    "path": "/absolute/path/buggy_18.sol",
    "sha256": "真实文件SHA256"
  }
}
~~~

清单 key 必须与图内 source_file 一致；相对 path 相对清单所在目录。可选 scope_mode 仅允许 legacy/modern，不能强行覆盖与 pragma 矛盾的模式。--max_iterations 默认100000，限制单函数 worklist 块求值次数；超限回退，不输出未收敛事实。

## 训练接入与边界

生成的新 hcg.gpickle 可以传给原训练脚本的图参数。节点仍按原节点标签监督，合约仍按原 JSON 监督；本模块不改变两阶段任务。

~~~bash
bash scripts/train_contractlevel.sh \
  scripts/DFG/artifacts/reentrancy_narrow_forward_v1/hcg.gpickle \
  inside_token ddg_forward_v1 \
  --label experiments/ge-sc-data/source_code/reentrancy/graph_labels.json \
  --verbose_epochs
~~~

这只是输入接入命令，本轮未运行该完整实验。它沿用原训练输出目录和参数。访问控制须显式覆盖 label/dataset/testset，避免原 shell 脚本的重入默认路径。

正式比较 E0/E1 前仍需固定折清单、标签、特征、best/last、种子，并在每折对齐共同参数初始化；同 seed 不会自动保证新增关系前后的共同权重相同。本轮没有把这些策略插入原训练循环。

model_validation.capture_model_input / assert_model_input 可绑定 checkpoint 的有序类型 schema、实际输入特征和边方向；必须在加载权重前调用。原训练脚本没有自动接入这个旁路校验器。不要把增强图 checkpoint 直接加载到原图，也不要用更高 F1 代替依赖正确性审计。

本版认证 inside_token 固定图接口；未宣称完整 storage/mapping 依赖、跨函数依赖、所有特征模式或任意新源码级联推理可用。
