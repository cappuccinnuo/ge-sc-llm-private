# EP1：关系注册、typed 反向与模型等价验收

修改 AI：Codex。日期：2026-11-10。依据 edge-sem 的 PROMPTS r8 §4.1、§4.3；起点 a71b2bc16f1edd7c8f298209c8a2a9b0b862eab3。同步执行 fast-forward-only，远端已最新。PROMPTS 原始 SHA256：ece6f1798c549d9275a95a812b0627af43d7677008c6328ecfae554ffc5ddc2f。

EP1 的 CPU 结构闸门通过。关闭 EdgeSem 开关时，重入节点 fold 0、fold 9 的 G3R 规范关系、端点、全部参数和 eval 输出均与冻结实现逐位相同。G3R-T 在重入与访问控制节点任务均成功完成 CPU 前向和反向，规范关系数与 EP0 完全一致。本轮没有训练或 GPU 运行，不报告检测效果。

## 实现

- __init__.py：注册 8 个剖面、基础/DFG/新增关系族与 REV_。recursive_method_call 属于 structure；MOD_APPLY 归 call，表达修饰器应用，不把它本身认定为授权守卫。EP0 的可投影回边均不足 50，所有剖面的 cf_back=false。
- materialize.py：merge 的普通边调用原 reflect_graph；typed 的普通边分别保留正向键与显式 REV_ 键，不再把两向混在同一关系中。DFG 关系仍交给冻结 G3R materialize。已有方向、端点顺序与重复边保留；新关系键冲突及输入 REV_ 会报错。
- rel_meta 保留 base/reverse/family，附加 anchor_key 以传递文档要求的参数来源；parameter_key_map 只返回有 G3R 来源的键。merge 下 reverse=false 仅说明不是显式 REV_ 键，不声称其内部没有反向边。
- init.py：共享参数逐个复制；typed 关系按承载原边的 G3R canonical 键复制。没有来源的行只允许属于 E1 关系及其 REV_，用规范键紧凑 ASCII JSON 的 SHA256 前 16 位生成局部 CPU Generator 种子。att/msg 按锚模型关系数的 Xavier 范围初始化，pri=1；不消耗全局 RNG。文件头记录参考源码与 SHA。
- model.py：用每折指定种子的未训练 G3R/shared_projection/mean 构造器装配锚模型，再深拷贝、重建 DGL schema/关系 ID/层和 metapath，输入特征从锚模型复制。沿用原前向、池化与 HGT 层。新 E1 边只接受未来构建器提供的输入，本轮没有实现边构建器。
- edge_profile 表达真实拓扑，dfg_profile=G3R 只记录锚来源。G3R 校验委托冻结实现；typed 用本地深校验逐项检查节点身份、标签/掩码、特征、schema、端点、缓存与参数映射。不会通过改 dfg_profile 绕过冻结 checkpoint 校验；独立 checkpoint 接入留 EP7。
- 属性与安慰剂剖面仅注册，当前模型入口明确拒绝构造，避免用普通结构模型冒充这些剖面。EdgeAwareHGTLayer 的实现留 EP6。

## 真实 CPU 验收

| 任务/剖面 | fold | canonical关系数 | 参数量 | 构造秒数 | 验收 |
|---|---:|---:|---:|---:|---|
| reentrancy_node/G3R | 0 | 212 | 5,111,012 | 20.860 | 逐位等价 |
| reentrancy_node/G3R | 9 | 212 | 5,111,012 | 20.976 | 逐位等价 |
| reentrancy_node/G3R-T | 0 | 220 | 5,176,676 | 20.178 | 有限前后向 |
| access_control_node/G3R-T | 0 | 234 | 5,291,588 | 8.446 | 有限前后向 |

构造耗时包括本入口的锚模型、深拷贝、关系重建及完整校验；这是单次 CPU 测量，不是训练耗时或性能基准。typed 反向检查的目标是 mean(logits²)，只验证可微计算与有限值，optimizer step=0。装配沿用冻结的标签完整性检查，标签没有参与该反向目标。

fold 0 的完整参数摘要也与 EP0 的 cpu_A 记录一致。两任务 typed 的每个关系行均按映射复制（每层 220/234 行）；原 F3 图指纹和文件 SHA 未变。增加的关系行与平均聚合分母会改变 typed 模型的计算，后续实验需据实际对照解释，不能在本轮声称效果改善。

验收输入沿用 EP0 绑定的历史 8H N-anon-s 特征，仅用于可复现的等价检查。本轮没有重新选择主实验视图，不把这项 CPU 验收当作改回匿名主实验的授权。图、特征 manifest 和实际历史配置分别绑定在每份 probes 收据中；config.device 是历史配置的 cuda:0，实际执行证据为 CUDA_VISIBLE_DEVICES 为空、cuda_initialized=false。

两任务边数小于 20 的规范关系分别为 94、114 个。完整清单在 PROGRESS.md 本节与 probes JSON 的 sparse_relations，未做稀疏共享、删关系或按支持量重初始化。

## 测试与开发记录

EdgeSem 149、NodeSem 1353、DFG v2 2653，共 4155 项通过。EdgeSem 较上轮增加 34 项，覆盖材料化顺序/反向/冲突、参数复制与独立 RNG、真实两折等价、两任务 typed 前后向，以及 ID/端点/特征/掩码/来源映射/层类型篡改拒绝。

首次定向测试暴露新 registry 漏了现有合成 CFG 的 if_true/if_false：19 passed、2 failed、9 errors、4 deselected。原源码与日志保存在 development/ 和 execution/unit_tests.*。只为 EdgeSem 注册表补 control 别名，冻结代码和真实图不改；修正后 30 passed、4 deselected，再完成上述三套回归。没有覆盖失败记录或重试正式实验。r8 的实质方案保持；没有自行实施 EP2 的解析替代方案。

## 归档与复现

独立目录：[artifacts/ep1_v1](artifacts/ep1_v1/)；summary.json 保存机器结果，before.json 保存起点，audit_plan.json 绑定代码与实施选择，probes/ 保存四个真实 CPU 收据，execution/ 保存命令、退出码、耗时和日志 SHA。没有保存新权重、生产图或特征文件。

核验入口 ep1_verify.py：核对 750 份冻结源码、354 项 _code_refs、43 份其他 EdgeSem 源码、287 份旧产物、697 项输入引用、8H load、源图指纹和三文档追加前字节。最终结果见 verification.json；它不把历史 EP0e gate 改成通过。

实际命令（mando；CUDA_VISIBLE_DEVICES 为空；PYTHONDONTWRITEBYTECODE=1；OMP/MKL 各 2；原 TREE_SITTER_LIB_DIR）：

    python -B -m scripts.edge_sem.recon.ep1_common
    python -B -m scripts.edge_sem.recon.ep1_run --name edge_tests -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests
    python -B -m scripts.edge_sem.recon.ep1_run --name nodesem_tests -- -m pytest -q -p no:cacheprovider scripts/node_sem/tests
    python -B -m scripts.edge_sem.recon.ep1_run --name dfg_tests -- -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    python -B -m scripts.edge_sem.recon.ep1_run --name collect_report -- -m scripts.edge_sem.recon.ep1_report
    python -B -m scripts.edge_sem.recon.ep1_run --name doc_check -- -m scripts.node_sem.doc_check --expect-cjk HANDOVER.md:290093 docs/training_changes_2026-10-07.md:1068848 scripts/edge_sem/PROGRESS.md:11776 scripts/edge_sem/EP1_REPORT.md
    python -B -m scripts.edge_sem.recon.ep1_run --name verify -- -m scripts.edge_sem.recon.ep1_verify

首次正式 EdgeSem 验收额外设置 EDGESEM_EP1_RECEIPTS 为上述独立批次的 probes 绝对路径，成功测试才排他写入收据；日常重跑测试不设置此变量，以免覆盖证据。未自动重跑任何已成功套件。

## 停止位置与后续边界

EP0e 的库召回仍为 312/347=89.9135%，历史 90% 门槛仍失败。r8 明确允许与调用解析无关的 EP1 独立推进；本轮没有批准接受该覆盖限制，也没有实现库重载或外层 call_option 新解析，EP2 尚未启动。

新语义边、边属性、EdgeAware 层、checkpoint/训练调度及效果评估均留各自后续 Prompt。最终实验将在显存充足的服务器进行，当前 RTX3050 4GiB 只限制本机开发；本轮全 CPU，不能据此估算最终 GPU 显存。产物保存在 WSL，未向 C 盘另存大型文件。

按共享流程完成本地 EP1 提交；本轮不自动推送 GitHub。
