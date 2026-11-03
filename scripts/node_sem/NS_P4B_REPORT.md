# NS-P4b 实施与验收报告（Codex，2026-11-03）

本轮按 PROMPTS.md r15 第5.1/5.6b节执行，输入 HEAD 为48d83d1b，前置实现为3b132618。范围为 dropout 种子修正与非正式单轮功能/资源检查；主视图为 original，局部 masked 仅是 CTX 对照。没有推进 NS-P5，也没有进行正式K折或模型选型。

## 实际修改

- adapter.py：modality_dropout 的种子增加 ntype。不同节点类型不再共享相同伯努利序列；同类型/同计数仍逐位可复现，eval 不推进计数，全局 RNG 不受影响。
- p4_acceptance.py：仅增加可选输出目录、设备准备和阶段观察接口；默认 NS-P4 路径及其历史规则保留。冻结 fit、HGT、监督、优化器、scheduler、特征、图和标签未改。
- p4b_acceptance.py：独立14项验收入口，CPU6项、节点GPU6项、合约GPU2项。复用已有封存零步初值，补建缺少的节点S1o零步初值。每项共同参数与对应8H零步状态精确核验，绝不使用旧训练权重。
- tests/test_p4b.py：覆盖种子、矩阵、数值口径、资源提醒、历史身份、门控、阶段日志和历史证据篡改。

新计划位于 artifacts/ns_p4/attempt3；恢复后有效计划与结果位于 attempt3/resume2。旧 attempt2 的274个文件逐一保持SHA与大小不变。运行入口分开是为了避免修改旧100MiB批准记录或旧plan/seal，不是改变模型。

## 决策与保留记录

用户批准 logits 相对差使用 max|GPU−CPU| / max(max|CPU|,max|GPU|)，同时要求最大绝对差≤1e-4、张量尺度相对差≤1e-4；逐元素相对差仅另行报告，两个全零张量相对差记0。模型仍在float32计算，差值统计转换float64。

首次CPU S3在训练前因阶段记录误用只创建一次的write函数而失败；没有创建fit目录、没有optimizer step。修复为追加式JSONL，18项定向回归通过后经用户批准，在resume1封存新计划，引用原计划及失败记录。旧计划、失败和初值均保留，14项任务和训练runtime未因日志修复改变；无自动重试。

## 显存口径

本轮仅将低于100MiB改为memory_tight提醒，启动仍要求≥3000MiB；OOM/CUDA错误以及数值、输入、checkpoint错误仍停止，不降配、不切CPU、不自动重试。每个GPU检查独立进程，持有原GPU锁。

已独立核对8H资源CSV的SHA与历史报告收据一致。重入合约G3R五折reserved均2094MiB，最小空闲44–74MiB，证实旧绝对门槛也会阻止历史成功运行。相同任务/fold/profile的reserved比值>1.25仅标记“显存需求明显增加”。跨运行差值是描述性对照，受epochs、视图、库缓存和其他占用影响，不能证明纯特征增量的显存因果；S4-noG与G0历史模型的层数也不同。启动空闲≥3000MiB不是其他进程不存在的证明。


## TF32 诊断与第二次明确恢复

恢复1的S1o/S2 GPU已成功；S4在零步默认精度前向验收失败，最大绝对差0.00106704235、张量尺度相对差0.000577034082，尚未执行训练，后五项未启动。用户授权独立诊断：1次CPU和3次GPU eval，无优化器。默认GPU重复结果逐位一致；关闭TF32后绝对差8.34465027e-7、相对差4.51261152e-7，参数digest不变，原TF32设置已恢复。这支持本例差异主要来自精度设置，不能据此宣称所有CUDA运算逐位等价。

用户先误选“停止”，随后明确更正“刚才点错了，按照你推荐的方式进行”。依据更正授权，新resume2计划保留旧失败、plan/seal及精确旧driver源码，复用6CPU和2GPU成功收据，只继续6项剩余GPU。1e-4的绝对/张量相对门槛仍保持，但验收前提改为同初值CPU与临时关闭TF32的GPU eval。默认TF32下的差异单列，不能称默认GPU也通过该门槛。训练前用finally恢复matmul/cudnn的原TF32设置（均true），完整fit后再次核验；训练计算、参数、随机种子、模型及数据保持原样，未把训练改成禁用TF32。

独立诊断入口p4b_parity_diagnostic.py未调用训练器。参数、原计划和证据保留；零步诊断与单轮fit分别计数，不作为新的seed实验。若诊断或fit出错仍停止，未自动放宽容差。

## 验收结果

修复前两个dropout回归均失败；修复后55项定向测试通过。最终全套805 NodeSem + 2653 DFG v2 + 223原项目回归 = 3681项通过，0失败/跳过，42条既有DGL distutils与NetworkX gpickle弃用警告。阶段日志修复后的18项定向测试、原始失败和最终回归分别留档。

CPU 6项和节点GPU 6项均通过：训练loss有限、各模态有非零投影梯度、共同初值精确一致；best/last保存、inner_val/outer_test评分及重载预测一致，outer_test未参与优化。门控仅对有可用模态的行要求和为1，全缺失行保留0，符合已有定义。历史8H load和354项生效源码摘要通过，未改变冻结源码。

Contract GPU passed: 2; allowed OOM: 0. Formal fits: 0.

| CPU config | Parameters | Train loss | Inner val loss | Construct s | Fit/check s |
|---|---:|---:|---:|---:|---:|
| S3 | 5128420 | 0.722186 | 0.651478 | 22.97 | 37.87 |
| S3m | 5128420 | 0.658538 | 0.592991 | 28.02 | 32.39 |
| S4 | 5661540 | 0.827695 | 0.752278 | 30.88 | 37.72 |
| S4g | 5681175 | 0.803666 | 0.753580 | 30.64 | 38.96 |
| S4m | 5661540 | 0.775206 | 0.746771 | 30.19 | 38.21 |
| S4-noG | 1569026 | 0.862285 | 0.768413 | 27.93 | 23.71 |

| GPU task / config | Result | Allocated MiB | Reserved MiB | Min free MiB | Delta allocated | Delta reserved | Delta free | Reserved/8H | Wall s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| reentrancy_node / S1o | PASS | 1215.66 | 1348 | 337 | -43.47 | -88 | -2 | 0.939 | 123.56 |
| reentrancy_node / S2 | PASS | 1195.29 | 1344 | 345 | -63.84 | -92 | +6 | 0.936 | 82.18 |
| reentrancy_node / S4 | PASS | 1236.05 | 1434 | 321 | -23.07 | -2 | -18 | 0.999 | 132.73 |
| reentrancy_node / S4g | PASS | 1288.07 | 1434 | 257 | +28.94 | -2 | -82 | 0.999 | 134.37 |
| reentrancy_node / S4m | PASS | 1236.59 | 1414 | 343 | -22.54 | -22 | +4 | 0.985 | 131.22 |
| reentrancy_node / S4-noG | PASS | 161.22 | 208 | 1544 | -647.35 | -724 | +390 | 0.223 | 108.41 |
| reentrancy_contract / S1o | PASS | 1852.97 | 2074 | 81 | -42.23 | -20 | +27 | 0.990 | 150.35 |
| reentrancy_contract / S4 | PASS | 1884.88 | 2194 | 44 | -10.32 | +100 | -10 | 1.048 | 205.08 |

显存表中的耗时是每项独立进程的完整墙钟时间，含装配、完整性检查、训练、评分与验收；不能当作单纯GPU计算时间。fit/check秒数另见summary.json，原始采样、上下文/启动前读数、内存紧张标记在resources目录。超过1.25的条目仅作显存需求明显增加提醒。

| Zero-step eval | Default TF32 max abs | FP32 max abs | FP32 tensor relative | FP32 elementwise relative | FP32 passed |
|---|---:|---:|---:|---:|---|
| S4 | 0.00106704235 | 8.34465027e-07 | 4.51261152e-07 | 0.0059099246 | True |
| S4g | 0.00120931864 | 1.07288361e-06 | 6.0520468e-07 | 0.00549828179 | True |

## 实际命令

```bash
# mando，CPU时 CUDA_VISIBLE_DEVICES=''；其余沿用OMP/MKL=2和原TREE_SITTER_LIB_DIR
python -B -m scripts.node_sem.p4b_acceptance prepare
# 首次日志接入失败后的明确批准恢复；以下目录已经存在，禁止覆盖重跑
python -B -m scripts.node_sem.p4b_acceptance resume-prepare --out scripts/node_sem/artifacts/ns_p4/attempt3/resume1
python -B -m scripts.node_sem.p4b_acceptance run --only cpu_reentrancy_node_S3 --out scripts/node_sem/artifacts/ns_p4/attempt3/resume1
# CPU其余S3m/S4/S4g/S4m/S4-noG；GPU使用gpu_<task_id>_<name>，确切命令见controller.json
python -B -m scripts.node_sem.p4b_parity_diagnostic
python -B -m scripts.node_sem.p4b_acceptance precision-resume-prepare --out scripts/node_sem/artifacts/ns_p4/attempt3/resume2
python -B -m scripts.node_sem.p4b_acceptance verify --out scripts/node_sem/artifacts/ns_p4/attempt3/resume2
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

命令用于说明已执行过程；运行入口拒绝同一身份再次启动。每项完整命令、退出码和墙钟耗时在cpu_controller.json/gpu_controller.json中，失败现场和修复前测试另存。

## 限制与停止位置

上述均为fold0、seed1、最多1 epoch的实现验收，不以这些F1/loss选型，也不据此声称分类提升、泛化或完整训练稳定。当前STATIC245维，S4载体760维保持原样。原名主实验仍需原名S0配对基线，旧匿名8H成绩只能作历史参考。

最终实验将按用户安排在显存充足的服务器运行；RTX3050 4GiB限制仅来自当前本机开发环境。本轮没有部署或测量服务器。正式全尺寸资源仍需在目标服务器实测；若合约探针OOM，必须作为下一阶段资源前提保留，不能据此缩减最终方案。

没有新增关系、重编码、下载依赖、修改原HGT/tokenizer/训练器或重写旧实验。产物保留在WSL工作树，不另行复制至C盘。本轮按共享上下文本地提交，不自动推送，不推进NS-P5。
