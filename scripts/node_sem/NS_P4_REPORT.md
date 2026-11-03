# NS-P4：融合、原名基线与单轮验收

实施者：Codex；日期：2026-11-03。按 PROMPTS r14 / §5.1 / §5.6 实施，起点 node-sem@d9f7eb24。结果位置：scripts/node_sem/artifacts/ns_p4/attempt2；本轮仅非正式单轮验收，不启动 NS-P5 或完整实验。

## 1. 本轮实现

- concat：连续 CODE/CTX 经各自 LayerNorm 与无偏置投影，STATIC 直接投影，各模态按存在位求和，最后加共享融合偏置。TOKEN_IDS 混合配置复用共享 EmbeddingBag；旧单 TOKEN 的 S1 参数名与 p=0 算术路径保留。
- gated：在各模态投影后计算门控；缺失模态权重为0，全缺失输出偏置。避免全负无穷 softmax 产生 NaN；last_gates 为脱离计算图的 CPU 张量。
- 模态 dropout：仅训练生效；使用绑定 fit 身份的局部 CPU Generator 与 forward 计数，不消耗全局随机数。正式多模态配置 p=0.1；p=1 只用于必须覆盖的全缺失测试。评估不递增计数。
- layers=0 显式保留，只允许 G0；节点和合约的前向、反向均经过测试。HGT 核心与训练器未改动。
- 登记原名 S0o/S1o、S2/S3/S4/S4g/S4-noG，以及 CTX 局部 masked 对照 S3m/S4m。S3m/S4m 的 CODE 仍保留原名，不能称为完整匿名实验。
- 新增专用 p4_acceptance / p4_verify，复用冻结 fit、监督、InputGuard、checkpoint 和资源监测。旧 execution.py 的正式白名单保持原样，本轮入口不开放正式训练。
- 初值从对应8H零步初值复制共同 gcs/classify，新增参数按已有语义初始化算法生成；S0o复制全部参数。未使用训练后、best/last 或 smoke 权重作为新 fit 初值。

文件：adapter.py、model.py、init.py、feature_spec.py；configs/ 与 NS_P4_INDEX.json；p4_acceptance.py、p4_verify.py；tests/test_fusion.py、test_p4_acceptance.py 及旧接口测试。原 DFG、作者模型、tokenizer、图、标签、划分和特征文件均不修改。

## 2. 用户批准及模板调整

1. 不同 GEMM 累加顺序不能保证 float32 逐位一致。原宽度探针最大绝对差为3.814697265625e-05，输出尺度113.99011993408203。用户批准改用 float64 参考与 atol=1e-6、rtol=1e-5 的验证；同一实现重复运行仍严格逐位一致。没有更换文档的融合计算。
2. 用户批准 CPU 验收通过后，对重入合约 fold0/G3R 的原名 S1o、S4 各执行1个GPU epoch。独占同一 GPU 锁，启动空闲至少3000MiB，运行最小空闲低于100MiB或OOM立即停止，不自动重试或降配。
3. p=1 是模板明确要求的测试边界，因此 FeatureSpec 从[0,1)扩展到[0,1]；生产配置没有改为p=1。
4. 沿用上一阶段已验收的STATIC245维，不使用旧243维。S3=2+256+256=514，S4=3+256+256+245=760；存在位包含在载体宽度内。
5. 原名主视图遵循用户最新指令与EXPERIMENT_POLICY。旧匿名S0/S1及接口保留，原8H匿名成绩不作为原名实验的配对成绩。

## 3. 输入、初值与CPU结果

四任务分别对G0/G3R核验S0o载体与原图token逐位一致，共8项。原名token来自8G准备清单记录的original视图，并核对来源SHA，未从匿名token反推。重入节点fold0/G3R的S0o全部参数tensor digest与历史8H S0一致。每个冒烟配置共同参数也独立逐张量核验。

下面仅为实现检查；一轮loss或预测不能用于选型或声称提升。配置沿用各任务实际冻结参数，唯一训练配置覆盖是maximum_training_epochs=1，CPU仅为执行设备。

| Config | D | Parameters | Construct s | Fit/check s | Train loss | Inner val loss | Tensor subtotal MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| S2 | 257 | 4562660 | 16.77 | 25.84 | 0.751504 | 0.713549 | 82.33 |
| S3 | 514 | 5128420 | 23.46 | 30.94 | 0.718943 | 0.651452 | 102.94 |
| S4 | 760 | 5661540 | 29.72 | 36.53 | 0.826441 | 0.752259 | 122.55 |
| S4g | 760 | 5681175 | 29.62 | 37.60 | 0.805638 | 0.753528 | 122.85 |
| S4-noG | 760 | 1569026 | 27.09 | 22.70 | 0.864160 | 0.768438 | 59.19 |
| S3m | 514 | 5128420 | 22.98 | 31.10 | 0.658910 | 0.593325 | 102.94 |
| S4m | 760 | 5661540 | 29.54 | 36.79 | 0.773311 | 0.746789 | 122.55 |

8H measured construction: 18.237s. S4 exceeds 3x: False.

构造时间直接测量make_nodesem_model，包含载体验收；fit时间还包含重载、评分与落盘，不能等同纯GPU计算时间。张量估计仅含参数、梯度、两份Adam矩、输入和边端点，不含激活、attention缓存、DGL结构缓存、CUDA上下文及分配器峰值，不能据此断言4GiB足够。

CPU每组都检查有限loss、各模态投影存在非零训练梯度、共同初值相同、输入未变、best/last及inner_val/outer_test重载预测一致。gated全缺失、缺失掩码、归一化和dropout确定性另有单元测试；独立验收重查SHA、输入身份、配置、初值与checkpoint绑定。

## 4. GPU资源探针

| Config | Resource gate passed | Peak allocated MiB | Peak reserved MiB | Minimum free MiB |
|---|---|---:|---:|---:|
| S1o | False | 1852.9716796875 | 2074.0 | 88.0 |
| S4 | False | not run | not run | not run |

S1o stopped: MemoryGateError('Whole-card free memory below 100 MiB: 88.0 MiB')

GPU accepted: 0/2; formal fits: 0.

本轮GPU验收未通过：S1o已完成1轮训练/inner_val计算并保存best，但在随后资源检查处因最低空闲88MiB停止；last、最终评分及重载一致性验收尚未完成。PyTorch峰值allocated=1852.972MiB、reserved=2074MiB，启动前空闲3456MiB；未发生已记录的OOM。S4按规则未启动，未重试。完整现场和111次采样保留，gpu_stop_audit.json只证明停止规则正确，不代表GPU模型验收通过。

因此当前结论是“代码和CPU验收完成，GPU资源验收受阻”，不能称NS-P4全部验收通过；后续在合适资源环境中经明确安排补验，本轮不解除阈值或自动重跑。


## 5. 测试与冻结边界

最终 NodeSem 784、DFG v2 2653、原DDG/graph_utils 223，共3660项通过，0失败、0跳过；42条既有DGL distutils / NetworkX gpickle弃用警告。包含线性参考、同实现逐位确定性、局部RNG、all-missing、混合token、层数0、原名全参数复制、配置/梯度/初值/重载拒绝测试。未以删除测试或放松身份断言换取通过。

开发失败记录保留：fusion_final_tests中1个测试夹具使用list+tuple导致TypeError，改为显式列表转换后全套通过；首次prepare因新任务spec目录未创建而停止，发生在模型构造/训练之前。修复mkdir接入后使用独立attempt2，不覆盖首次现场；不是训练失败重跑。旧NS-P4准备记录与已封存历史结果均未删改。

最终只读8H execution.load及生效runtime清单核验、git授权路径检查、三份文档追加前缀SHA与UTF-8/CJK校验见final_checks.json和doc_check.log。冻结源码未改，计划单独绑定NodeSem runtime及本轮driver。PT/NPZ保留在本地WSL，提交代码、报告及轻量审计收据，不将大模型/训练权重塞入Git。

## 6. 实际执行命令与下一步边界

mando环境，PYTHONDONTWRITEBYTECODE=1，OMP_NUM_THREADS=2，MKL_NUM_THREADS=2，TREE_SITTER_LIB_DIR沿用原路径。CPU使用CUDA_VISIBLE_DEVICES=''；GPU探针恢复CUDA可见性。

```bash
python -B -m scripts.node_sem.p4_acceptance prepare --out scripts/node_sem/artifacts/ns_p4/attempt2
python -B -m scripts.node_sem.p4_acceptance cpu --only <S2|S3|S4|S4g|S4-noG|S3m|S4m> --out scripts/node_sem/artifacts/ns_p4/attempt2
python -B -m scripts.node_sem.p4_verify --out scripts/node_sem/artifacts/ns_p4/attempt2 --device cpu
python -B -m scripts.node_sem.p4_acceptance gpu --only <S1o|S4> --out scripts/node_sem/artifacts/ns_p4/attempt2
python -B -m scripts.node_sem.p4_verify --out scripts/node_sem/artifacts/ns_p4/attempt2 --device gpu
python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

以上是已执行或受门槛控制的命令形式，不是允许覆盖旧目录的重跑指令；每个任务的实际开始/完成/失败标记和退出码均保留。GPU独立验收只在两项资源门槛都通过时执行；若中止，表中注明未执行项。

合理的后续边界：NS-P5需在原名基线上封存正式计划，不能借用匿名8H成绩当作配对基线；一轮冒烟不足以判断融合是否有分类收益。S4-noG消除的是HGT消息传递，CTX/STATIC仍有DFG与语义信息；局部masked CTX也不消除原名CODE捷径。本轮不增加新模型模块、重新提取特征、修改DFG、开展正式K折或推进NS-P5。

最终实验将按用户安排在显存充足服务器运行；本机RTX3050 4GiB只是当前开发限制，不能据此削减最终方案。本轮未部署或实测服务器。本轮本地提交，不自动推送。
