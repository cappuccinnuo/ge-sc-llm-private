**近期训练改动记录与早停方案（2026-10-07）**

> 2026-10-08 Codex update: section 11 documents labeling_v2. The initial statement about leaving HANDOVER.md unchanged applied to the earlier task; this task explicitly authorizes its update.


本文件独立新增，保留原 HANDOVER.md 和 scripts/DFG/MANDO_LLM_DDG_Code_Design_Guide.md 不变。本文区分“已经修改”和“建议、尚未实施”，不是对旧交接文档的覆盖。

记录日期使用 America/New_York（EDT，UTC−04:00）。精确时间来自文件 mtime 与会话核验，不是提交时间；mtime 可被后续写入覆盖。记录时 Git HEAD：6c8d241b1829bbc4b55315568a6d71f70de2b7ab，近期改动尚未提交。

**1. 归属与时间**

“原仓库”指上述 HEAD，不等于本次编辑前的本地状态。工作区已有构图、标签、日志、CLI 等更早的改动，不能把整个 git diff 都归入最近这次工作。尤其 tools.py、snippet 划分以及既有逐轮日志框架，不作为本次新实现。

| 事件 | EDT 时间 | UTC 时间 | 依据 |
| --- | --- | --- | --- |
| graph_classifier.py、node_classifier.py、train_contractlevel.sh、train_linelevel.sh 参数/调度/输出修改 | 2026-10-07 09:38:57 | 2026-10-07 13:38:57 | 当前文件 mtime，不能还原每一处历史编辑 |
| classifier_cli.py 配置修改 | 2026-10-07 09:39:07 | 2026-10-07 13:39:07 | 当前文件 mtime |
| 合约池化梯度修复 | 2026-10-07 22:59:07 | 2026-10-08 02:59:07 | model_hgt.py 与修复前快照 |
| CPU/CUDA 短验证 | 2026-10-07 23:02:04 | 2026-10-08 03:02:04 | 临时 validation.json |
| 用户运行的修复后窄行号图训练结束 | 2026-10-07 23:07:34 | 2026-10-08 03:07:34 | 新日志 mtime |

**2. 参数、学习率、输出：修改在哪里**

行号以本文记录时文件内容为准。

| 位置 | 当前行为 / 本轮改动 | 与原仓库的区别及归属边界 |
| --- | --- | --- |
| sco_models/classifier_cli.py:160 | 合约提供 --patience，默认 7，运行默认配置不再覆盖该参数 | HEAD 合约 runtime patience 为 10，未提供该合约 CLI 参数 |
| sco_models/classifier_cli.py:28 | 节点 lr 配置默认 0.0002 | HEAD 配置写 0.0005，但旧节点 Adam 已硬编码 0.0002；不能说旧训练实际从 0.0005 开始 |
| graph_classifier.py:176,184–187 | Adam 使用 args['lr']；OneCycle 总步数为 epochs * len(train_dataloader)；默认 0.0005 → 0.01 → 0.0005 | HEAD Adam 字面值是 0.00005，但旧交接文档已记载更早改成 0.0005，不能将 HEAD 冒充本轮即时修改前版本 |
| graph_classifier.py:37–41,203 | 记录本次更新 LR，optimizer.step() 后推进 scheduler.step()；训练函数接收 scheduler | HEAD 的 scheduler 更新被注释；OneCycle 默认初始化会把 LR 设为 0.01/25=0.0004，单改 Adam 的 lr 不保证生效 |
| node_classifier.py:271–274 | Adam 使用 args['lr']；OneCycle 默认 0.0002 → 0.005 → 0.0002 | 节点 scheduler 原来就会推进；本轮明确边界，旧默认末端接近 2e-8 |
| node_classifier.py:307–309,321,335–341 | 更新前读取 used_lr，记录并显示刚刚真正使用的 LR | 避免误报为 scheduler 推进后下一步使用的 LR |
| graph_classifier.py:189–191,207–212；node_classifier.py:276–278 | 输出 patience、delta、LR 策略，逐轮日志包含 LR | 不是把全部已有日志功能重新实现 |
| scripts/train_contractlevel.sh:21；scripts/train_linelevel.sh:22 | python -u，减少输出重定向时的 Python 缓冲 | 脚本为本地未跟踪文件，HEAD 没有完整旧脚本可对照；train_node.sh 未在本轮统一修改 |

当前默认值：

| 项目 | 合约级 | 节点/行级 |
| --- | --- | --- |
| 折数 | 5 | 10 |
| 最大 epoch | 50 | 50 |
| patience / delta | 7 / 0.001 | 7 / 0.001 |
| LR 起点 / 峰值 / 终点 | 0.0005 / 0.01 / 0.0005 | 0.0002 / 0.005 / 0.0002 |

节点 patience=7、delta=0.001 在 HEAD 已存在。合约 delta 当前 0.001、HEAD 为 0.005；由于缺少逐次提交历史，这里记录上游差异与当前值，不把它确定归属到某一次即时编辑。

论文 §5.3 给出 LR 范围，§5.4 给出 patience=7、delta=0.001。论文未明确给出这里完整的 OneCycle 曲线、div_factor 和 final_div_factor。当前保留 OneCycle 并设置 final_div_factor=1 是边界实现选择，不能宣称完全还原作者调度轨迹。[MANDO-LLM 原文](https://daoyuan14.github.io/papers/TOSEM25_MANDO-LLM.pdf)。

**3. 梯度修复：仅两行有效逻辑变化**

位置：sco_models/model_hgt.py，HGTVulGraphClassifier.forward()，当前第 604–609 行。原语句作为注释保留，并使用 GRADIENT FIX 标记：

~~~python
# GRADIENT FIX: keep the pooled tensor connected to the HGT layers.
# Original: batched_graph_embedded.append(hiddens[node_list].mean(0).tolist())
batched_graph_embedded.append(hiddens[node_list].mean(0))
# GRADIENT FIX: stack preserves autograd; rebuilding a tensor detaches it.
# Original: batched_graph_embedded = torch.tensor(batched_graph_embedded).to(self.device)
batched_graph_embedded = torch.stack(batched_graph_embedded, dim=0)
~~~

原来的 .tolist() 把 HGT 输出变成 Python 数值，重建张量后分类损失无法传回输入投影和 HGT。保留张量并 stack 后，均值池化数值及批次顺序不变，梯度连接恢复。

该次修改未改变 HGT 层算法、图、tokenizer、标签、LR、早停和保存逻辑。辅助 _forward() 中的类似转换仍保留：此次范围仅为当前合约训练使用的公开 forward()，不是修复仓库所有相似代码。

行级训练使用 HGTVulNodeClassifier，在 model_hgt.py:420–432 将每个节点的 hiddens 直接送入分类器，不经过合约池化。两类模型分别初始化和训练，权重不共享。因此独立 train_linelevel.sh 不受此补丁影响；如果 cascade_detect.py 换用新合约 checkpoint，第一阶段筛选变化可以间接影响最终展示的漏洞行。

回退方法：只恢复上述两条 Original 注释中的可执行语句，删除对应的新 append(mean(...)) 和 torch.stack(...)。不要重置其他已修改文件。

**4. 验证与临时证据**

在 mando 环境、PyTorch 1.8.1+cu111 下，用本地图的 simple_dao.sol 和 0x12345678979f29ebc99e00bdc5693ddea564ca80.sol 构造短验证输入：144 节点、193 边；CPU 和 CUDA 分别通过。

| 检查项 | 结果 |
| --- | --- |
| 相同权重、eval 模式的 logits 与池化向量 | 修复前后逐元素完全相同 |
| 原来的有梯度参数张量数：投影/HGT1/HGT2/分类头 | 0 / 0 / 0 / 2 |
| 修复后有限且非零梯度参数张量数 | 20 / 80 / 84 / 2 |
| 优化器更新 | 各模块均有参数变化；连续两次训练模式更新通过 |
| 修改范围 | AST 对比只改变合约 forward；git diff --check 通过；其他既有 tracked diff 与修复前快照一致 |

证据位于 /tmp/mando_contract_gradient_fix/：validation.json、two_contracts.gpickle、model_hgt.py.before、other_changes.before.diff。/tmp 可能被清理，本文已保存关键结论。

源码 SHA-256（sco_models/model_hgt.py）：

- 修复前：9986fb348d440edf954f7e068015bc793c5aa7e11b5a429459ddeb70aed2ee92
- 修复后：4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947

**5. 用户完成的运行与结果**

合约对照使用本地生成的 experiments/ge-sc-data/source_code/reentrancy/tokenizer_ids_narrow.gpickle，不是作者下载的 upstream_contractlevel_tok.gpickle。narrow 指收窄源码行号映射的版本。

| 运行 | Buggy-F1 (%) | Macro-F1 (%) | 日志 |
| --- | ---: | ---: | --- |
| 梯度修复前，已应用当前 LR/patience 设置 | 94.3810 | 94.3810 | outputs/contractlevel_narrow_paper_lr_v1.log:363–364 |
| 梯度修复后 | 93.2635 | 92.8690 | outputs/contractlevel_narrow_gradfix_v1.log:200–201 |
| 既有独立行级运行，仅作背景 | 99.1508 | 99.0507 | outputs/linelevel_narrow_paper_lr_v1.log:426–427 |

合约两类 F1 分别下降 1.1175、1.5120 个百分点。但两次 5 折名单均不同；例如 fold 0 各有 29 个验证合约，仅 3 个相同，不是固定划分的严格消融。

修复前各折跑满 50 轮；修复后停止索引 [16,15,19,13,14]，从 0 编号，实际训练 [17,16,20,14,15] 轮。训练 loss 很快接近 0、验证 loss 随后上升，出现过拟合迹象。fold 1 的验证 Buggy-F1 曾为 96.30%，停止保存时为 92.86%。当前仍未恢复最佳权重，不能据一次 F1 下降认定梯度补丁错误。

历史运行命令（再次用相同 tag 会覆盖该 tag 的部分产物）：

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm
conda activate mando
mkdir -p outputs
set -o pipefail

bash scripts/train_contractlevel.sh \
  experiments/ge-sc-data/source_code/reentrancy/tokenizer_ids_narrow.gpickle \
  inside_token narrow_gradfix_v1 \
  --verbose_epochs \
  2>&1 | tee outputs/contractlevel_narrow_gradfix_v1.log
~~~

模型目录 models/contractlevel/narrow_gradfix_v1/；TensorBoard 目录 logs/contractlevel_narrow_gradfix_v1/。当前通用 reentrancy_hgt.pth 随各折覆盖，不是“全体折的最佳模型”；另有包含 stop epoch 与 fold 的 checkpoint。

| 文件 | SHA-256 |
| --- | --- |
| tokenizer_ids_narrow.gpickle | 10f2d63278f34c31553129289365b4ffb57b03639198a1f217fc7a5b05055312 |
| graph_labels.json | 14e212893b6ebc060e2ff9deea78dbf546c12a6aea73aaf78224c9c33b4e5ffe |
| contractlevel_narrow_paper_lr_v1.log | 03685e60d6a175a46284ba3ea68dcc4834ceda5a4420cced886ca3f477e80f0e |
| contractlevel_narrow_gradfix_v1.log | 0a8a234406375673296cfbaa4689fdc0ecbf78d3ff6aa60c6c0da424396bfa86 |

**6. 当前仍存在的问题，尚未修改**

| 问题 | 代码或证据 | 含义 |
| --- | --- | --- |
| 未在改善时保存最佳权重 | tools.py:36–52 仅更新计数；graph_classifier.py:235–239 停止时才保存 | best loss 不代表保存了该时刻的模型 |
| 节点验证复用旧 logits | node_classifier.py:303–312 | 更新后用更新前、训练模式 logits 计算验证指标，指标与保存权重不对应 |
| 默认 fold 未固定 | graph_classifier.py:123、node_classifier.py:130 未指定 random_state；节点列表还有 list(set(...)) | --seed 1 只固定部分 PyTorch 随机过程，不保证相同折 |
| 留出折兼作早停和最终评分 | 当前训练流程 | 不等于完全独立的最终测试 |
| 模板/代码重复仍在 | 既有行级日志：(code,label) 跨折重叠 9319/12036，77.4% | 早停及梯度修复不能消除数据重复引起的记忆效应 |

原交接文档中若有“torch seed 已固定 KFold”等较早结论，应以当前代码和真实名单为核验依据；本次保留原文档不动。本文新增不会改变上述实现。

**7. 参考文献能支持什么**

| 工作 | 可确认的训练/评估设计 | 未说明或不能推导的内容 |
| --- | --- | --- |
| MANDO-LLM，TOSEM | §5.4：patience=7、delta=0.001；合约 5 折、细粒度 10 折 | 未明确给出改善即保存、最终恢复最佳 checkpoint 的完整实现 |
| Clear，ICSE 2024 | §4.4：对比阶段 100 轮，检测微调 20 轮，明确输出最后一轮，重复 5 次取平均 | 重复 5 次不是 5 折；顶会不意味着一律采用最佳验证权重 |
| iAudit，ICSE 2025 | §III-D：2268/567/709 条训练/验证/测试数据；§VI 提到采用早停 | 未明确给出 patience、delta、监控指标和最佳权重恢复细节 |

来源：[MANDO-LLM](https://daoyuan14.github.io/papers/TOSEM25_MANDO-LLM.pdf)、[Clear §4.4](https://arxiv.org/html/2404.17839v1#S4.SS4)、[Clear 官方分类训练循环](https://github.com/chenpp1881/Clear/blob/main/train.py#L373-L431)、[iAudit](https://daoyuan14.github.io/papers/ICSE25_iAudit.pdf)。Clear/iAudit 是智能合约方向参考，并非都使用 HGT。Clear 的循环虽每轮计算传入测试数据的指标，但检查到的循环不按这些指标提前停止或选最佳；不能把记录指标直接等同于用于选模型。

**8. 推荐早停方案：待实施，不是当前代码行为**

建议先保持 patience=7、min_delta=0.001、最大 50 轮及当前 LR 策略，修复验证、保存和恢复语义，不同时修改这些数值。

| 项目 | 推荐设计 |
| --- | --- |
| 监控指标 | 内部验证集平均交叉熵 val_loss，越小越好；Buggy-F1、Macro-F1 同时记录 |
| 验证时机 | 本轮更新后 model.eval() + torch.no_grad() 重新前向；下一轮显式 model.train() |
| 节点验证 | 用内部验证节点 mask 计算 loss；不复用训练 logits，不把标签作为输入特征 |
| 最优保存 | 任何严格更低且有限的 val_loss 都保存对应参数 |
| 提前停止 | 独立维护“显著改善参考值”；下降超过 0.001 清零，否则累计；连续 7 次未显著改善停止 |
| 结束处理 | 无论提前停止还是跑满 50 轮，都加载 best checkpoint 再评估 |
| 文件管理 | 每个 run/fold 独立 best.pt、last.pt、配置、指标和划分清单 |
| 异常处理 | 首个有限验证值建立 best；NaN/Inf 不覆盖 best，不作为正常训练结果汇总 |

保存与停止使用两个状态是有意的：小于 0.001 的下降也可能是最低 loss，值得保存，但未必足以延长训练。不要把实际最低 loss 与用于 patience 的显著改善参考值混为一谈。

逻辑示意，尚未接入项目：

~~~python
best_loss = float('inf')
patience_reference = float('inf')
bad_epochs = 0
for epoch in range(max_epochs):
    model.train()
    train_one_epoch(...)
    model.eval()
    with torch.no_grad():
        val_loss, val_metrics = validate_fresh_forward(...)
    require_finite(val_loss)
    if val_loss < best_loss:
        best_loss = val_loss
        save_best_checkpoint(...)
    if patience_reference - val_loss > min_delta:
        patience_reference = val_loss
        bad_epochs = 0
    else:
        bad_epochs += 1
    save_last_checkpoint(...)
    if bad_epochs >= patience:
        break
load_best_checkpoint(...)
model.eval()
with torch.no_grad():
    evaluate_held_out_test(...)
~~~

内存缓存最佳参数时使用 deepcopy(model.state_dict()) 或逐张量复制，不能只保存会随训练变化的浅引用。last checkpoint 若用于继续训练，应保存 optimizer、scheduler、早停状态、epoch、随机状态；仅做推理不需要恢复优化器。

最低验证 loss 不保证最高 F1。选择 loss 是为贴近 MANDO 描述并减少小样本 F1 跳变；若另做按 F1 选优的实验，须事先声明并只用内部验证集，不能按最终测试结果挑选更好看的标准。

**9. 实施与对照顺序建议（尚未实施）**

1. 先固化数据清单、实际 fold manifest、排序和随机源，再比较“仅梯度修复”和“梯度修复 + 正确保存/恢复”。同一外层折的训练样本和测试样本应完全相同。
2. 节点训练应先修复更新后的 eval 前向，否则早停依据仍不对应保存权重。合约已有独立 eval 验证，不能将同一问题误归到所有入口。
3. 诊断实验若继续沿用同一留出折早停和评分，要标为复现/诊断协议。正式独立评估建议外层保留合约 5 折、节点 10 折，每个外层训练折内再分内部验证集，例如按合约分层留出 20%（本项目建议，不是论文规定）。内部验证选权重，外层测试只在选择结束后评估。
4. 同一合约及克隆家族应处于同一组；节点任务先按合约划分再展开 mask。保存 seed 不够，还需固定 NumPy 等随机源和实际名单；检查模板重复需独立进行。
5. 每折记录 best epoch、stop epoch、best loss、停止时 loss、加载路径和最终两类 F1，报告折均值及离散程度。新评估协议应重新建立基线，不宣称与原论文表格完全同条件。
6. 最后才单独研究 LR/早停交互：当前 OneCycle 前段升高 LR，而恢复训练的 HGT 已快速拟合，可能在 LR 尚未下降时早停。后续可以对照，但本轮不同时改 patience、LR、指标和划分来追求更高 F1。


**10. 2026-10-08 更新：最小早停与最佳权重保存补丁已实施**

本节是第 6、8、9 节之后的新状态。前文“尚未修改”“待实施”“当前仍未恢复最佳权重”等表述保留为 2026-10-07 的历史记录；截至本节，两个主训练入口已实现改善即保存、结束恢复最佳权重，节点训练已改为更新后重新验证。内部验证集、固定折名单、模板去重等建议仍未实施，不能把整个第 8、9 节视为全部完成。

本次授权：只实施早停、保存/恢复最佳模型所必需的修改，原代码注释保留，便于回退。之前的合约梯度修复继续保留。没有重新生成图、改标签、改 tokenizer/LLM、改 HGT 结构、调整学习率或换数据划分，也没有运行正式全量 5 折/10 折实验。

**10.1 时间、基线和文件范围**

- 本轮修改前快照：2026-10-08 06:00:49 UTC / 02:00:49 EDT（America/New_York）。
- sco_models/tools.py 修改后 mtime：2026-10-08 06:03:12 UTC / 02:03:12 EDT。
- graph_classifier.py、node_classifier.py 修改后 mtime：2026-10-08 06:04:17 UTC / 02:04:17 EDT。
- 时间来自文件系统和本轮快照，不是 Git 提交时间。本轮未创建提交。Git HEAD 仍为 6c8d241b1829bbc4b55315568a6d71f70de2b7ab；工作区有既有修改，因此本节比较基线是“本轮操作前”，不是直接拿整个 git diff 当作本轮修改。
- 快照目录 /tmp/mando_early_stop_fix_20261008/ 保存三个生产文件和本文的 before 副本、before_manifest.json；/tmp 可能被清理。
- 生产文件仅改 3 个；新增 tests/test_early_stopping.py，并在本文追加记录。检查其余 2975 个 tracked 文件 SHA-256 全部一致；HANDOVER.md、scripts/DFG/MANDO_LLM_DDG_Code_Design_Guide.md 保持原样。
- 修改处统一用 EARLY STOP FIX 注释标记；被替换的原逻辑留作注释。

| 文件 | 本次位置（本节写入时） | 修改及目的 |
| --- | --- | --- |
| sco_models/tools.py | 36–70 | 注释保留旧 __call__；区分绝对最低 loss 和 patience 的显著改善参考；拒绝 NaN/Inf |
| sco_models/tools.py | 72–90 | 更新保存方法说明，原保存语句 torch.save(model.state_dict(), path) 不变 |
| graph_classifier.py | 10–11、197–204、212、245–260 | 引入 JSON 记录；按 fold 分目录；每次新最低 loss 立即保存；早停分支只负责退出 |
| graph_classifier.py | 288–320 | 停止时另存 last，记录 selection.json，加载 best 后再评估，并写入原推理路径 |
| node_classifier.py | 10–11、296–329 | 分 fold 管理；每轮 model.train()；更新后 eval + no_grad 重新前向 |
| node_classifier.py | 348–381、395–438 | 新最低 loss 保存；停止时另存 last；恢复 best 再计算最终 F1 |
| tests/test_early_stopping.py | 新文件 | 8 个测试方法，覆盖早停边界、状态独立和权重快照恢复 |

**10.2 保存与早停分别怎么判断**

监控指标仍是当前验证折的交叉熵 val_loss，越低越好。没有改为按 Buggy-F1 或 Macro-F1 选模型。两个主入口保持 patience=7、delta=0.001。

1. 首个有限 val_loss 建立 best；以后只要严格小于此前绝对最低值，就立即保存 best.pt。即使下降小于 0.001，也会保存。
2. patience 使用独立的显著改善参考值。相对于该参考值下降严格超过 0.001 才清零并更新参考；否则计数加一。连续 7 次未达该条件就停止。
3. 与最低值相等不覆盖 best。与显著改善参考的差恰好等于 delta 不清零。这是有意采用的严格阈值；旧分支 score < best_score + delta 的 else 会把恰好相等计作改善。
4. NaN/Inf 在改变早停状态之前抛出 ValueError，不覆盖 best，也不当作正常完成的训练汇总。若没有有效最佳轮次则不加载可能残留的旧 checkpoint。
5. 无论提前停止还是达到最大轮数，都先保存最后权重，再加载 best，重新计算最终折指标。

例如 loss 从 0.5000 下降到 0.4995：best.pt 更新到 0.4995，但显著改善参考仍为 0.5000，patience 计数增加。随后下降到 0.4988，累计相对参考下降超过 0.001，计数才归零。因此绝对最优值与 patience 参考值不能共用同一个状态。

实现核心（完整旧代码已在源文件中注释）：

~~~python
self.improved = val_loss < self.best_val_loss
if self.improved:
    self.best_val_loss = val_loss
score = -val_loss
if self.best_score is None or score > self.best_score + self.delta:
    self.best_score = score
    self.counter = 0
else:
    self.counter += 1
    if self.counter >= self.patience:
        self.early_stop = True
~~~

两个训练入口在调用 early_stopping(val_loss) 后，检查 improved 并当场保存当前 state_dict，不使用随训练变化的内存浅引用。最低 loss 不保证最高 F1，本补丁不承诺 F1 一定提高。

**10.3 节点验证为何也是本次必要修改**

修改前：本轮训练前向得到 logits，反向传播并 optimizer.step() 更新参数，然后仍用旧 logits 的 val_mask 计算验证指标。旧 logits 来自训练模式，且对应更新前参数；若据它选择更新后的权重，会导致指标和 checkpoint 不对应。

修改后：训练步骤保留；每轮开头明确 model.train()。optimizer.step() 和 scheduler.step() 后切换 model.eval()，在 torch.no_grad() 中重新执行 model()，用新 val_logits[val_mask] 计算验证 loss 和 F1。下一轮再回到训练模式。训练指标依旧使用原来的训练前向，不改其统计口径。

~~~python
# Original lines retained as comments in node_classifier.py:
# val_loss = loss_fcn(logits[val_mask], targets[val_mask])
# val_acc, val_micro_f1, val_macro_f1, val_buggy_f1 = score(
#     targets[val_mask], logits[val_mask])

model.eval()
with torch.no_grad():
    val_logits = model().to(args['device'])
    val_loss = loss_fcn(val_logits[val_mask], targets[val_mask])
    val_acc, val_micro_f1, val_macro_f1, val_buggy_f1 = score(
        targets[val_mask], val_logits[val_mask])
~~~

合约级原有 validate() 已经用 eval + no_grad，未重写它。节点级增加一次验证前向，计算时间可能增加；这是使验证与权重对应所需的成本。

**10.4 best.pt、last.pt 与原保存方式的对应**

| 文件 | 当前含义 | 是否用于最后打印的折 F1 |
| --- | --- | --- |
| 每折 best.pt | 该折训练过程中有限 val_loss 的绝对最低值对应的权重 | 是，加载后重新评估 |
| 每折 last.pt | 该折提前停止或跑满轮数时的权重；在加载 best 前保存 | 否，只保留停止时状态供核对 |
| 每折 selection.json | 选择依据、轮次、指标、参数、实际训练/验证文件名单 | 元数据 |
| 原 reentrancy_hgt.pth | 兼容旧推理命令，随每折写入该折 best；全部完成后是最后一折的 best | 与最后一折 best 内容相同 |

回答“last.pt 就是之前的保存方式吗”：**就保存停止时权重这一语义而言，是。** 之前通常在停止时保存带 epoch/fold 后缀的 .pth，并把结束时权重保存到通用 .pth；跑满轮数则保存最后一轮。原先没有统一叫 last.pt。本次把这种权重明确命名、按折保留，同时新增独立的 best.pt。若最后一轮恰好最好，两者可以完全相同。

best.pt / last.pt 仍是裸 model.state_dict()，不是包含 model_state_dict 字段的包装对象，兼容现有 load_state_dict(torch.load(...)) 推理代码。last.pt **不包含 optimizer、scheduler、随机状态和早停状态，不能实现完整的断点续训**。为了最小改动，本次只在正常结束每折时写 last，不每轮保存完整续训包；进程异常中断时不能保证存在该次运行的 last。

selection.json 包含 fold、best_epoch、last_epoch、best_val_loss、last_val_loss、最佳轮次的两类验证 F1、patience、delta、best/last 路径、checkpoint_format、config、train_files、val_files。轮次与原日志一致，从 0 编号；F1 字段为 0–1 数值，最终 Average 行乘 100 输出。snippet 划分下文件名单不能还原精确的节点分配，本次没有扩展该实验模式的清单格式。

保存目录由 output_models 去掉扩展名后追加 _foldN 得到。例如：

~~~text
models/contractlevel/narrow_best_v1/
  reentrancy_hgt.pth
  reentrancy_hgt_fold0/
    best.pt
    last.pt
    selection.json
  ... reentrancy_hgt_fold4/

models/linelevel/narrow_best_v1/
  reentrancy_hgt.pth
  reentrancy_hgt_fold0/
    best.pt
    last.pt
    selection.json
  ... reentrancy_hgt_fold9/
~~~

同一个 tag 再跑会覆盖相同路径，换 tag 即可保留不同实验。通用 .pth 不是“全体折的最优模型”，也不是各折集成。

**10.5 保持不变的设置与仍待处理的问题**

- 合约 5 折、节点 10 折、最多 50 epochs、patience=7、delta=0.001 保持不变；命令可使用既有参数覆盖。
- 合约 LR 0.0005 → 0.01 → 0.0005，节点 LR 0.0002 → 0.005 → 0.0002；既有 OneCycle 每 optimizer update 步进和参数保持原样。
- 之前 model_hgt.py 的 torch.stack 合约梯度修复保留，本轮未改该文件。
- 默认 contract 划分、KFold/StratifiedKFold、随机源保持原样。因此 --seed 1 仍不能保证两次实际折名单一致；selection.json 记录本次名单，但没有修复跨运行随机性。
- 仍用同一个留出折早停/选择权重和计算最终 F1，没有增加内部验证集或独立外层测试。属于沿用当前复现协议，不能宣称已经完成严格的独立测试评估。
- 数据重复、SolidiFI 模板记忆、图与作者版本的差别均未通过本补丁解决；分数很高仍需单独检查这些原因。
- 合约 validate() 的 loss 聚合方式保持原样，没有顺带改为不同 batch 大小的加权平均。
- sco_models.tools.EarlyStopping 为共享工具，其有限值检查和严格 delta 语义也会影响调用它的 experiments/token_baselines.py；但该实验文件未修改，不代表它也完成改善保存和恢复 best。
- sco_models/train_sampling.py 使用另一处 sco_models.utils.EarlyStopping，本次不覆盖该路径。本节完成范围是 graph_classifier.py 与 node_classifier.py 两个主入口。

**10.6 验证记录**

在现有 mando 环境（Python 3.7、PyTorch 1.8.1+cu111）执行：

1. 三个生产文件语法检查通过，git diff --check 通过。
2. pytest 针对 tests/test_early_stopping.py、tests/test_classifier_cli.py、tests/test_model_imports.py、tests/test_graph_utils.py：**19 passed**（8 项新增，11 项既有；仅有既有依赖的弃用警告）。
3. 小规模真实 HGT 集成检查，图和 token 特征取自本地 tokenizer_ids_narrow.gpickle：合约子集 8 合约、66 节点、64 边；节点子集 4 个有漏洞合约、41 节点、41 边。子图重新编号后进入实际 main() 训练入口，使用 CUDA。
4. 分别检查合约/节点的提前停止和跑满轮数，共 4 个场景，每场景 2 折。测试中真实前向和参数更新保留，仅在测试进程控制用于早停的验证 loss 序列：早停场景 [0.2, 0.3]、patience=1，best_epoch=0、last_epoch=1；跑满场景 [0.3, 0.2, 0.4, 0.5]、patience=7，best_epoch=1、last_epoch=3。正式源码的参数没有因此改变。
5. 检查每折 best/last 分开且权重确有差异、通用别名等于最后一折 best、最终 F1 与最佳轮次的验证 F1 一致。节点额外记录前向调用，确认训练模式/梯度开启，验证模式/梯度关闭；验证看到更新后的参数，最终前向恢复为最佳轮次参数。
6. 所有场景通过。它们验证控制流和权重对应关系，**不是正式复现 F1**，不能将小图得分当作新实验结果。
7. 集成数据、日志、checkpoint、integration_results.json 在 /tmp/mando_early_stop_fix_20261008/integration/。调试测试器时曾因替换类导致 super 冲突、子图未重编号导致越界，均只修正测试器/临时子图，未为此改生产实现。

**10.7 修改内容校验与回退**

| 文件 | 修改前 SHA-256 | 修改后 SHA-256 |
| --- | --- | --- |
| sco_models/tools.py | 78495917b14b973697b53b1e7cbafc477c8c61787a0704fba86e723dc2cef30e | 32e7568876ac3369084f73623288b62a7d09f7161c1ac2f5f7582ab710d6630d |
| graph_classifier.py | 04181a93fd8f904571c1a9a31845cee337b4bd08151e98ae94b3d3ab2e5153eb | c3de3263fac026ec575e52f394eda273ccecda439e1228f2058dcce3ebcfd8e6 |
| node_classifier.py | 2f89ff43dd430b047f720530254b25d5d2b70ed5157907a7480ef9ba0ddca61d | 726afff87024b052494317fe18a7294b76df799670398617638f20b8d5141a7e |

回退时以 EARLY STOP FIX 标记为界，恢复三个文件中注释保留的旧逻辑，并去掉本次新增的保存目录、元数据、train/eval 切换等配套代码，三处一起恢复。不要只关闭 best 保存却保留后面的加载 best。

若这些文件在本节记录后没有其他修改，可从 /tmp/mando_early_stop_fix_20261008/ 的对应文件恢复到本轮修改前；先核对上表 SHA，避免覆盖后续工作。不要直接 git restore 整个文件，那会一并丢掉本轮之前的训练设置、实时日志等改动。回退本补丁也不应撤销 model_hgt.py 中之前的梯度修复。保留本文作为历史记录，不随代码回退删除。

**10.8 WSL Ubuntu 终端运行命令**

沿用用户自己生成的 narrow 图；合约使用 tokenizer_ids_narrow.gpickle，行级使用 linelevel_narrow.gpickle，均已核对存在。合约标签继续使用脚本默认的同目录 graph_labels.json。不是作者下载的 upstream 图，不重新做 tokenizer 编码。

在 VS Code 连接 WSL 的 Bash 终端运行，一次准备：

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm
conda activate mando
mkdir -p outputs
set -o pipefail
~~~

合约级，5 折：

~~~bash
bash scripts/train_contractlevel.sh \
  experiments/ge-sc-data/source_code/reentrancy/tokenizer_ids_narrow.gpickle \
  inside_token narrow_best_v1 \
  --verbose_epochs \
  2>&1 | tee outputs/contractlevel_narrow_best_v1.log
~~~

行级，10 折：

~~~bash
bash scripts/train_linelevel.sh \
  experiments/ge-sc-data/source_code/reentrancy/linelevel_narrow.gpickle \
  inside_token narrow_best_v1 \
  --split_by contract \
  --verbose_epochs \
  2>&1 | tee outputs/linelevel_narrow_best_v1.log
~~~

运行前本轮确认 narrow_best_v1 对应的两处模型目录和日志尚不存在，避免覆盖已有 narrow_gradfix_v1 / narrow_paper_lr_v1 结果。脚本已有 python -u，--verbose_epochs 每轮打印，tee 同时保存日志；不需要预先设置 BASE 或 RUN_TAG 变量。

日志预期包含每轮 train/val loss、两类 F1、patience、LR、新最低值标记，以及每折 restore best epoch ... / last epoch ... saved to ...。最后两个 Average F1 都基于各折加载 best 后的重新评估，不再是直接使用停止时权重。

本轮未自动启动这两条完整实验。后续对比需同时查看 selection.json 的实际折名单、best/last epoch 与 loss；因为划分仍未固定，不能把与旧日志的全部 F1 差异都归因于早停补丁。


**11. 独立标注工具与两种训练标签版本（Codex，2026-10-08）**

**11.1 时间、归属与授权范围**

修改 AI：**Codex**。实施时间约 2026-10-08 04:47–05:06 EDT（08:47–09:06 UTC）；图生成 manifest 时间为 2026-10-08 08:55:08.853467 UTC。该时间是本轮操作记录，不是 Git 提交时间。Git 基线仍为 6c8d241。

用户明确要求在 scripts 下新建文件夹完成新的标注实现、不修改其他代码；同时允许更新本训练变更文档和 HANDOVER.md。全部新代码、测试、输出图、审计和回退快照均位于 scripts/labeling_v2/。本轮没有修改既有训练、模型、构图、旧标注脚本；只读复用 scripts/line_mapping.py 并记录其哈希。

本轮之前新增的 scripts/build_labeled_graph.py、line_mapping.py 及旧 narrow 构图改动不归属为本轮 Codex 新实现。本轮是新增并行入口，原图和旧入口仍保留。

**11.2 问题与依据**

之前逐节点审计证实，本地 narrow 与作者全量 CFG+CG 图在规范化代码后有 18312 个对应节点，19267 条无类型边的端点及重数一致；控制流边类型不同，标签实际有 410 个不同（409 本地阳性/作者阴性，1 反向），阳性节点净差 408。

作者发布图的保存标签可由“保存的起止端点或单行值，与图内恢复的漏洞行集合相交”逐节点重放。普通字段为 [[start,end]]，合流/循环结束节点还有 [[line]]。这只是资产的行为证据，不等于找到了作者原始生成程序，也不是论文明确规定的映射方式。

本地使用原始源码行范围与 JSON/CSV 漏洞行求交，且旧逻辑合并同文件所有类别。71 份漏洞文件中可恢复标注有 68 份与本地映射后的集合一致；差异为 buggy_18、buggy_20、0x627fa62...。作者 buggy_18 中存在 41 个超过预处理源码525行的记录，因此“精确兼容作者”必须与“按当前源码核验”分开。详见 outputs/graph_alignment_review_20261008/。

**11.3 新增文件与具体行为**

| 文件 / 位置 | 实现 | 与原有流程的关系 |
| --- | --- | --- |
| scripts/labeling_v2/label_rules.py:9 | 解析作者字符串化漏洞记录，校验行号并去重 | 不调用模型生成标签 |
| label_rules.py:44 | 接受 [[line]] 和 [[start,end]]，只取保存值 | 作者兼容方式，不把端点展开成连续区间 |
| label_rules.py:68–115 | 使用文件/类型/规范化代码/AST或合流锚点匹配节点；核验边端点；恢复标注并逐节点重放 | 不按全局 node ID 或文件名猜测，不依赖节点迭代顺序；歧义或不自洽时报错 |
| label_rules.py:121–187 | 源码匹配检查；读取 SmartBugs JSON、SolidiFI CSV，仅保留 reentrancy | CSV 仍用整个注入范围；增加目标类别筛选和来源校验 |
| label_rules.py:189 | 原始源码行号映射重放，并与图保存的 original 行号逐节点核对 | 保留现有 narrow 节点跨度；遇过期映射停止 |
| scripts/labeling_v2/safe_graph.py | 只允许已审计的 NetworkX 容器和数值 NumPy 类型；拒绝其他全局引用；protocol 4 输出 | 适配 Python 3.7，避免直接无限制加载 pickle |
| scripts/labeling_v2/build.py:34 | 对除 node_info_vulnerabilities 外的节点属性、边属性、token、图属性生成不变量摘要 | 验证本轮确实只改节点标注 |
| build.py:72 | 写出新全量图、71份漏洞合约子图、原字节/原顺序合约标签、清单和差异 | 所有文件写入新目录；既有 graph_labels 不重新排序 |
| build.py:170 | CLI、来源哈希、双模式构建、输出范围约束、禁止覆盖已有目录 | 默认针对当前重入语料；不修改既有训练入口 |
| scripts/labeling_v2/test_labeling.py | 12 项回归检查 | 只验证标注与保护条件，不训练模型 |
| scripts/labeling_v2/README.md | 方式区别、适用范围、命令、验证和回退 | 不替换原交接文档 |

不存在“将旧实现注释后替换”的主代码改动；按本次要求使用新增入口隔离，因此无需修改旧脚本中的任何行。

**11.4 两种方式及坐标系**

| 模式 | 原标注 | 规则 | 目的与限制 |
| --- | --- | --- | --- |
| author_compat | 作者图内嵌漏洞记录 | 作者保存的预处理端点/单行值求交，逐节点结果必须等于作者原标签 | 精确对齐训练标签，保留异常及其他类别；不是修正后的真实漏洞位置 |
| source_range | 已核验源码对应的 SmartBugs / SolidiFI | 仅 reentrancy；CSV [loc,loc+length-1]；现有 narrow 节点映射回原始行后求交 | 保留源码位置依据；注入片段正例不等于逐行人工验证可利用性 |

author_compat 的 node_info_vulnerabilities.lines 是作者预处理坐标；source_range 是原始源码坐标。两者都不改本地节点已有的 node_source_code_lines / node_source_code_lines_original。不能把作者兼容记录直接当作原始行号使用；本轮仅对齐训练 y，未改变推理定位行范围的实现。

节点特征 code/token 和 7 类边全部仍取自本地 narrow，因此 author_compat 不等于完整作者图。恢复 8 类边、统一 tokenizer 输入文本、修复双方共有调用解析缺陷均不在本轮标注范围。

源码校验中 4 份 SmartBugs 文件（etherstore、reentrancy_bonus、reentrancy_cross_function、reentrancy_insecure）只有同一行 pragma 版本不同。工具逐行确认其余内容一致、行数相同且差异行不在标注中，记录两边哈希及差异行；其他差异直接失败。40 份 SolidiFI 文件要求字节一致。此容许仅证明标注位置未移位，不声称编译语义完全相同。

**11.5 重新生成的图与实际变化**

输出目录：scripts/labeling_v2/artifacts/labels_v1/。

| 版本 | 全量图 节点/边 | 行级图 节点/边 | 漏洞节点 | 相比本地 narrow 的二分类标签变化 |
| --- | --- | --- | --- | --- |
| 原本地 narrow | 18312 / 19267 | 12036 / 11710 | 6978 | — |
| author_compat | 18312 / 19267 | 12036 / 11710 | 6570 | 410 |
| source_range | 18312 / 19267 | 12036 / 11710 | 6976 | 2 |

author_compat 的完整漏洞记录字段发生 6979 处变化（主要包括行号坐标/记录表示），但二分类标签只变410处；不能把元数据变化数当标签翻转数。source_range 两处变化均为去掉只有 unchecked_low_level_calls 的正例，目标类别外正例降为0。author_compat 为兼容作者保留1个此类节点，并在 manifest 明示。

每种方式均写出 contractlevel.gpickle、linelevel.gpickle、graph_labels.json、annotations.json、label_changes.json、manifest.json。总表为 summary.json。合约名单142份、71份漏洞子集、合约标签JSON字节及顺序保持不变。

**为什么全量图也另存，但合约训练不必重跑：** 全量图里的节点标注元数据确实改变，因此按用户要求生成独立文件；当前合约分类的监督由独立 graph_labels.json 提供，图结构和 token 未变，所以合约级有效监督输入不变。若重跑分数不同，不能归因于这次节点标签修改；仍有随机折划分等因素。

**11.6 验证、失败处理与结果**

- 构建 author_compat 时18312个节点均有唯一映射，所有端点重放标签逐节点与参考一致。
- 验证19267条边的映射端点/重数；输出图的边类型保留本地模式。
- 两种图的全量非标签属性摘要与输入一致；写入后使用受限读取器重载验证。
- 实际调用 sco_models.graph_utils.get_node_label，12036个行级节点读取的0/1与设计目标逐项一致。
- 71份带标注源码已校验来源；4份pragma差异单独记录；输入源码、原图、CSV/JSON及依赖文件哈希在构建结束再次核对。
- 12项 unittest 最终全部通过，涵盖内部行/端点区别、作者单行格式、跨类别过滤、字符串记录、乱序节点对齐、歧义拒绝、作者标签自洽、映射过期、pragma例外、非标签属性、protocol4往返、未知pickle类型拒绝。
- 开发中首次严格按双端点解析拒绝作者 [[line]]；据真实数据扩展格式后通过。首次严格字节匹配拒绝4份pragma变更；经逐行核对后加入上述受限规则。两次都在写图前停止，没有覆盖旧数据。
- 首轮安全测试使用标准pickle异常类型，环境pickle5的异常类不同导致测试器报错；改为检查实际读取器异常类型，确认非法引用确被阻止。没有因此放宽读取器。
- 未启动新的完整HGT训练；正式指标由用户之后执行命令获得。

**11.7 本轮之前的运行结果，勿与新版本混用**

使用作者下载的完整混合图及其71份漏洞合约子图，当前训练程序运行结果：

| 既有日志 | Buggy-F1 | Macro-F1 |
| --- | --- | --- |
| outputs/contractlevel_author_hcg_contract_v1.log | 94.8089% | 95.0137% |
| outputs/linelevel_author_hcg_line_v1.log | 96.8931% | 97.0788% |

这是使用作者原混合图的既有结果，不是新 author_compat（本地边/token + 作者标签）的结果。更早96.8031%来自作者单独发布的CFG输入，不可混淆。论文表5重入CodeT5p对应96.78%；接近该数值不能证明完整实验条件已对齐。

**11.8 环境运行命令**

图已生成，先测试作者标签兼容方式：

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
mkdir -p outputs
set -o pipefail
bash scripts/train_linelevel.sh \
  scripts/labeling_v2/artifacts/labels_v1/author_compat/linelevel.gpickle \
  inside_token labels_author_compat_v1 \
  --split_by contract --verbose_epochs \
  2>&1 | tee outputs/linelevel_labels_author_compat_v1.log
~~~

然后测试源码范围方式：

~~~bash
bash scripts/train_linelevel.sh \
  scripts/labeling_v2/artifacts/labels_v1/source_range/linelevel.gpickle \
  inside_token labels_source_range_v1 \
  --split_by contract --verbose_epochs \
  2>&1 | tee outputs/linelevel_labels_source_range_v1.log
~~~

两条命令依次运行，既有训练参数、梯度修复、best/last方式保持当前实现。新增方式没有修复跨运行折划分随机性；要严格量化标签影响，之后需使用相同折名单另做控制实验。

重新生成、验证：

~~~bash
python -B scripts/labeling_v2/build.py --mode both \
  --output scripts/labeling_v2/artifacts/labels_v2
python -B -m unittest discover -s scripts/labeling_v2 -p test_labeling.py -v
~~~

**11.9 修改校验与回退**

history/before.json 记录本轮前112个已有代码/文档的哈希，其中110个既有代码文件应保持一致，只有本训练文档和HANDOVER允许更新；新文件摘要及最终核验记录见 scripts/labeling_v2/history/verification.json。文档原版快照为 history/*.md.before。

新增核心文件首次完成时SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| build.py | 5b87fbd7d9892b0c79879fe7ae319722f0f1453334ec9ac160eee6426386a7bf |
| label_rules.py | cc71bf24f74f1474eed6d8ff39154014d516f9a8ee07ee2b02946b3b0dc54f47 |
| safe_graph.py | e3c9be6e505c52b5dd4f12293b4bdcd58c4af5241479d2be73f07a2c09e4e7c0 |
| test_labeling.py | 1f3bc199bfc559fd6899146b33f8a0a1274697143ec0021536799dfb24967158 |

回退仅需将训练输入换回原 linelevel_narrow.gpickle（合约原输入为 tokenizer_ids_narrow.gpickle），不用修改训练或构图代码，不用 git restore。保留本节、审计记录和已有模型以便对照。


**12. 函数内正向 DDG 第一阶段（Codex，2026-10-12）**

**12.1 时间、归属与授权**

修改 AI：**Codex**。记录日期按 America/New_York；验收摘要核对时间为 2026-10-12 02:03 EDT / 06:03 UTC。该时间不是 Git 提交时间。用户本轮明确授权按 Phase 1–10 实施，并更新本训练文档与 HANDOVER.md。

所有新增 DDG 核心、测试、分析、示例和审计位于 scripts/DFG/。原项目生产代码只在 sco_models/graph_utils.py 的 reflect_graph 增加一个分支。既有 tokenizer、HGT 核心、分类任务、梯度修复、早停、LR、划分和保存机制均未修改。

更早工作区已有改动不能算成本轮新实现。完整当前实施记录：[IMPLEMENTATION_NOTES.md](../scripts/DFG/IMPLEMENTATION_NOTES.md)；运行入口说明：[README.md](../scripts/DFG/README.md)。

**12.2 与上一轮分析的关系**

2026-10-11 Codex 只新增 DDG_INTEGRATION_ANALYSIS_2026-10-11.md 及 audit/review_manifest_2026-10-11.json，没有改算法或训练。那轮在内存证实旧 CFG 可将 return 接到后继语句，核对两类作者/本地节点对齐与 HGT 反射行为；这些是分析，不是已经实现 DDG。

本轮用户新要求优先：只实现函数内 Definition–Use、只新增 DATA_DEF_USE、不新增变量节点、暂不做 REV。上一轮报告的完整消融 runner、共同参数每折对齐、REV、任意源码 cascade 并未在本轮全部实施，不能把计划写成结果。更早 HANDOVER 提出的 Test_code 目录、首版必须含 mapping 等，是历史建议，本轮以此次明确授权为准。

**12.3 各 Phase 的文件、逻辑与测试**

下表测试数字是阶段当时累计数量，后续修正另记；最终全套为 140 passed。

| Phase | 新建文件（均在 scripts/DFG） | 修改及原因 / 核心逻辑 | 测试与限制 |
| --- | --- | --- | --- |
| 1 | __init__.py、models.py、tests/test_models.py | 不可变源码/符号/事件身份，内部 CFG 数据结构；不产生模型变量节点 | 2 passed；基础结构不代表语义完成 |
| 2 | frontend.py、symbol_table.py、tests/test_frontend.py、tests/test_symbols.py | raw/compat 双 AST、UTF-8 span、版本作用域、声明唯一 ID | 26 passed；复杂类型/版本歧义/modern同名初始化先回退 |
| 3 | access_extractor.py、tests/test_access.py | 事件内先 USE 后 DEF；赋值/复合赋值/递增/delete/tuple；未知 RHS 仍 kill 被赋值标量 | 46 passed；不确定副作用回退，storage 不冒充局部变量 |
| 4 | semantic_cfg.py、reaching_definitions.py 及两测试 | 独立控制流；静态 defID、GEN/KILL、worklist 固定点、收敛后 facts；过滤不可达块 | 70 passed；modifier/assembly/try等回退，未顺带修旧HCG |
| 5 | ddg_builder.py、tests/test_ddg_builder.py | 直接 facts 汇总、同端点同关系去重，保留多符号证据 | 79 passed；不做闭包，自环facts保留但不输出边 |
| 6 | projection.py、tests/test_projection.py | 按文件/AST ID/类型/代码/坐标唯一核验；缺节点不猜最近行 | 88 passed；emit等缺节点会损失覆盖 |
| 7 | pipeline.py、graph_audit.py、tests/test_pipeline.py、test_model_integration.py初版 | 深拷贝附边、不变量核验；原 reflect_graph 对 DATA_DEF_USE 保持方向 | 102 passed，含既有图工具；仅inside_token已认证 |
| 8 | model_validation.py；扩展模型测试 | 节点/合约前向反向、DDG梯度、更新、schema+输入摘要、重载 | 115 passed；集成20项；原正式训练未自动调用新validator |
| 9 | configuration.py、cli.py、tests/test_configuration.py | use_ddg默认false；同一原图生成E0/E1；新目录、拒绝覆盖、输入摘要和重读 | 121 passed；不补token、不改标签，缺源码保留并报告 |
| 10 | demo.py、tests/fixtures/minimal.sol、tests/test_end_to_end.py | 原生成器＋真实缓存tokenizer＋既有encode_ids＋DDG＋两模型单步更新/重载 | DDG 121 + 原测试19 = 140 passed；没有正式K折/F1结果 |

测试日志位于 scripts/DFG/audit/phase*.log。另有 README.md、IMPLEMENTATION_NOTES.md、本节与 HANDOVER 的追加条目、运行前后摘要及回退快照。没有修改两份最初的 DFG 方案文档。

**12.4 唯一原项目生产接入**

文件 sco_models/graph_utils.py，reflect_graph 原 L426 起；新增分支位于 for metapath, value 循环内部、原反射 if 之前：

~~~python
# DDG FORWARD FIX (Codex, 2026-10-12): only the new relation is directed.
# Original behavior below reflected every relation, including DDG.
# Removing this branch restores the original behavior; no base edge changes.
if metapath[1] == "DATA_DEF_USE":
    symmetrical_data[metapath] = value
    continue
~~~

其余旧反射分支未删除、未重写；因此保留旧代码本体与说明注释，没有复制整段旧函数造成双份实现。快照：scripts/DFG/audit/graph_utils_before_2026-10-12.py.txt。

原 generate_hetero_graph_data 已按 (src.node_type, edge_type, dst.node_type) 自动建元关系，不需要改。现有两个 HGT 模型直接从增强图建立新增关系参数，无需重写 HGTLayer。新增边类型会增加 canonical relation 和参数量，不能说模型参数量完全不变。

**12.5 复核中发现的问题及限定修正**

1. frontend 的叶节点比较起初遗漏字符串正文；改为完整 literal token，并加预处理改变字符串必须拒绝的测试。多条 pragma 暂回退，不用 experimental 掩盖矛盾版本。
2. pytest 将名为 setup 的测试辅助函数识别成生命周期函数，首轮产生18个 setup error；只重命名测试辅助函数，之后通过，未为此改变算法。
3. 注释不应改变裸 return/throw 和 for condition 的语义；先过滤注释。普通 revert 参数的实际 AST 有 parenthesized_expression，不只 revert_arguments，已据真实形状修正。
4. 终止 builtin 可能被同名用户函数、导入、继承遮蔽时保守回退，避免把后续代码错误判为不可达。
5. for 更新表达式在原 HCG 有独立 i++ 节点，初版归整个 for 头是错误映射。已暂停后续验收并说明，改成更新表达式自己的 span，加入真实图 oracle 测试，补修后累计103通过。for初始化无独立节点时仍归循环头，明确为投影粒度限制。
6. 合约模型接收但不保存 node_feature 属性，新 validator 初次假设该属性存在导致两项测试失败。只改旁路校验为实际 inp/token 一致性检查，不向原模型增加属性；最终20项模型集成通过。
7. 原 HGT 已有孤立类型的零消息分支，本轮只测试其仍能工作，不将它冒充本轮新增修复。

**12.6 保护条件与实测**

- 输入图不被修改。新图节点顺序、ID、类型、code、token字节/shape/dtype、漏洞标注、源码字段、文件归属、旧边类型/端点/key/重数逐项核验。
- DDG构建不读取漏洞标签进行决策；打乱标签后依赖边不变。Projector中的 label 是 AST 标识字符串，与 node_info_vulnerabilities 不同。
- 不支持的函数仍在输出HCG中；只是不附加未经证明的数据边。某些 storage 表达式仍可读取已知局部索引，但不表示实现了 storage 内容依赖。
- DGL中同/跨类型 DATA_DEF_USE 的方向与输入完全相同；不会自动产生同名反向或 REV。
- E0使用冻结旧反射与新反射，在相同seed下权重和eval logits逐位一致。
- 当前源码SHA、实际代码/锚点一致性是本轮审计；原图通常没有生成时源码SHA，因此不能声称完整恢复了作者图的历史源码身份。

真实单文件审计（audit/real_projection_probe.json）：

| 类别 | 作者/本地均一致的节点 | 支持函数 | facts / 投影facts | 新增边 |
| --- | --- | --- | --- | --- |
| 重入 buggy_18.sol | 383普通 + 41合成 | 45/69 | 96/86 | 74 |
| 访问控制 buggy_18.sol | 273普通 + 11合成 | 60/67 | 156/146 | 114 |

两版本新增边按原源码 span 对齐后相同，每组10未投影facts对应5个没有原HCG节点的emit。支持率/投影率仅针对当前分析范围，不等于整个Solidity程序的数据依赖完备率。

最小真实tokenizer示例（artifacts/minimal_20261012_v1/result.json）：

| 项 | 结果 |
| --- | --- |
| tokenizer | Salesforce/codet5p-770m，本地缓存，无完整LLM前向 |
| 特征 | 原 encode_ids，float32[512] |
| 原图→增强图 | 11节点/12边 → 11节点/19边 |
| 新增关系 | 7条 DATA_DEF_USE，无REV |
| 节点/合约输出 | [11,2] / [1,2] |
| DDG relation_msg 梯度L1 | 3.91129184 / 5.12457860 |
| 更新/重载 | 两模型均通过，重载logits逐位相同 |

样例全clean标签只用于接口检查，不是漏洞标注实验，不能据其loss或预测声称检测性能。测试宿主时钟偶有跳变，pytest个别耗时异常，未将日志耗时用于性能比较。

**12.7 终端命令与产物**

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm
conda activate mando
export TREE_SITTER_LIB_DIR="$PWD/build/linux-x86_64"

PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/tests \
  tests/test_graph_utils.py tests/test_model_imports.py \
  tests/test_classifier_cli.py tests/test_early_stopping.py

python -B -m scripts.DFG.demo \
  --output scripts/DFG/artifacts/minimal_manual_v1
~~~

输出目录须未存在，再次运行换名字。最小示例只做单步更新，不跑正式折训练。

给现有窄图附边的入口（本轮未自动跑完整语料）：

~~~bash
python -B -m scripts.DFG.cli \
  --graph experiments/ge-sc-data/source_code/reentrancy/tokenizer_ids_narrow.gpickle \
  --source_dir experiments/ge-sc-data/source_code/reentrancy/source_files \
  --output scripts/DFG/artifacts/reentrancy_narrow_forward_v1 \
  --use_ddg
~~~

对照用同一原图配 --no_ddg、新输出目录；行级需换成原漏洞子图作为输入。新 hcg.gpickle 可传原训练脚本，标签JSON仍由原流程提供。详细参数/正式训练接入示例见DFG README。

**12.8 待解决事项与回退**

- 暂无本轮测试失败；仍不支持完整storage/mapping/reference依赖、跨函数摘要、modifier执行、复杂副作用、隐式返回的完整投影和任意源码cascade。
- 没有运行正式K折或比较F1。下一次完整E0/E1实验需固定标签/图/token/折/种子/权重选择，并在每折构造时对齐共同初始化；只加同seed不够。
- 新 checkpoint validator 是旁路辅助，原训练器未自动调用。正式实验必须额外绑定合约标签和fold摘要，不只绑定图。
- 节点标签保持不变不等于证明ground-truth正确；新增DDG能否提升、是否受模板记忆影响仍待实验。
- 最简回退是输入原图或--no_ddg，旧关系行为已验证一致。不要给原图加载增强图关系权重。
- 如需撤销原接入，核对摘要后只移除 DDG FORWARD FIX 分支；不要 git restore 整文件覆盖历史工作。

| 文件 | 本轮前SHA256 | 本轮后SHA256 |
| --- | --- | --- |
| sco_models/graph_utils.py | 1bdedc8f72ae3e1abd7cfa26cd5c5c071f590ea3456af225064e13ad850bcc48 | 5da9afc69f4528b63e4acf9595588b20b06d15cf3d508a49d56f10e33116015d |

完整前后清单：scripts/DFG/audit/implementation_before_2026-10-12.json、implementation_after_2026-10-12.json。两个文档的修改前快照也在该 audit 目录。本节追加，不删除前文历史。


**13. paper_kfold 主协议实施与短验收（Codex，2026-10-12）**


修改 AI：Codex。记录时间：2026-10-12T12:56:45.050158+00:00。本轮依据实际源码、README、可读 JSON 记录实施；不把工作区已有修改计为本轮修改。

**13.1 本轮范围与旧记录核验**

新增主协议 `paper_kfold / ddg-paper-kfold-v1`。旧 `ddg-nested-paired-v1` 通过 `nested_strict` 旁路保留，旧实现、严格支持策略及结果不覆盖。所有新增运行逻辑、测试与实验产物位于 `scripts/DFG/experiments/`。原 DDG、HGT、tokenizer、原训练脚本未改；仅追加 README 和既有训练/交接文档说明。

`REPORT_2026-10-12.md` 的原始文件是合法 UTF-8，6458 字节，其中 2602 个字面量 ASCII 问号、0 个汉字。不能通过换解码方式找回中文。原文件保留，字节备份和编码证据保存在 `audit/paper_kfold_v1/`。原始 SHA-256：
`ff20d660b7d38e67c4ecfc75befa6c9bdc7ce19f0322a41012b8594efca4fd0c`。
本报告是依据源码和 JSON 新写的记录，不是对损坏正文的猜测恢复。

**13.2 最小修改清单及实现**

| 新增文件 | 关键接口与理由 |
|---|---|
| paper_protocol.py | convert_document/validate_document 精确转换冻结划分；独立协议版本与摘要；initialize_pair 包装旧语义初始化算法但不改变随机抽样 |
| paper_runtime.py | Supervision 完整图前向加 mask/文件监督；validate_registration 检查模型与 HGT 层字典、参数库、DGL ID 和端点；graph_schema_and_support 分离注册与训练实例支持；gradient_audit 分类记录 DDG 梯度 |
| paper_checkpoint.py | 新格式 ddg-paper-cv-checkpoint-v1；复用 model_validation；保存/恢复前校验协议、schema、输入和状态摘要 |
| paper_run.py | 新单层 CV 训练编排；复用现有模型、配置来源、StopMonitor、CE、Adam、OneCycleLR；保存 best/last 及 CV 预测 |
| run_experiment.py | 默认 paper_kfold；nested_strict 直接调用旧 run_pair.run，不改变旧阻断逻辑 |
| audit_paper.py | 在不训练的条件下检查全部折；实际原 HGT 构造 schema 与结构统计交叉核对 |
| summarize_paper.py | CV 专用 JSON/CSV 导出；拒绝混合 nested/outer 评分或静默忽略不完整折 |
| tests/test_paper_protocol.py | 转换、版本、摘要、协议目录与初始化版本测试 |
| tests/test_paper_runtime.py | 稀有类型/关系、字典错误、mask、原生前向/梯度、跨文件连接测试 |
| tests/test_paper_run.py | 真实小 HGT 训练、val-only DDG、best/last、输入绑定、预测身份及旁路回归 |
| tests/test_paper_reporting.py | 主结果角色、输出命名和混合协议拒绝测试 |

已有实验 Python 文件全部保留；已有 README 在顶部新增主协议说明，历史 nested 正文完整保留。训练变更文档与 HANDOVER 只追加记录，并保存追加前字节备份。

**13.3 主协议的实际行为**

1. 合约任务仍为文件级 StratifiedKFold 5 折，节点任务为文件级 KFold 10 折，沿用旧排序和 seed1。
2. 新 train 严格等于旧 inner_train 与 inner_val 的并集；新 val 严格等于旧 outer_test。新 JSON 嵌入旧完整清单及摘要；重新计算摘要也无法绕过“精确转换”检查。不另抽样、不挑 seed、不丢折。
3. 只对 train 监督反传。每轮更新后执行 eval/no_grad，在 val 上计算 loss，复用 patience=7、delta=0.001；每次严格更低 loss 更新 best，patience 的显著改进阈值另行计数；结束时保存 last。
4. best 和 last 都在同一 val 评分，因此结果叫 **CV validation**。这不是 independent outer test，也不是嵌套交叉验证的外层泛化估计。
5. 节点模型每次调用原 model()，在完整固定节点任务图前向，然后按 train/val mask 取行。合约模型调用原 model(files)，内部仍在完整固定合约任务图前向，仅指定文件 batch 接受监督。本次 Dataset A 的 train 文件能放入单个完整文件 batch。
6. E0 从 E0 全任务图注册；E1 从 E1 全任务图注册。模型间按节点类型名称和 canonical relation 对齐共同初始参数。E0 不增加空 DDG 关系；不同类型/关系不合并或借用参数；不用训练过的 E0 初始化 E1。
7. 初始化算法单独记录为 `semantic-paired-native-xavier-v1`，调用旧 paired_initialize 原实现，保留原随机数与 native full-bank Xavier 尺度；初始化版本不再冒充实验协议版本。
8. 模型注册完整 schema 不等于每种关系都有训练实例。已注册且只出现在 val 的类型/关系允许预测并列入支持审计。未注册、字典错位、参数库不匹配、图端点/特征/标签或 checkpoint 绑定不一致仍报错。
9. 跨文件连接直接报错，不删连接或样本来“通过”审计；训练和评分期间不创建参数。语义 CFG/DDG 分析、标签构建、tokenizer 都没有重跑或改变。
10. DDG 支持为 0 时允许监督梯度为 0；支持非零但观测到零梯度会显式记为诊断，不能仅凭一次零值断言断图。HGT 整体梯度断开、支持关系参数库断开和错误字典仍会报错。contract 的 Adam weight_decay 可能改变无监督支持的参数，不能把这种变化当成关系受到训练监督的证据。

主协议保留了此前已修复的梯度、eval 和最优权重逻辑。协议名字说明本轮按用户要求恢复单层 K 折、完整图前向和同 val 选模/评分，**不代表恢复了作者未公开的折清单，也不保证所有训练实现细节与作者历史执行一致**。

**13.4 数据、schema 与划分**

使用两类作者标签 prepared 图；没有混入 local narrow 标签。节点任务图是在同一原图中按图级标签选出的 buggy 文件集合，当前已有 prepared 不重建。

| 数据/任务 | 文件数 | 节点数 | E0 原边 | E1 新增正向 DDG | 漏洞节点 |
|---|---:|---:|---:|---:|---:|
| 重入/合约 | 142 | 18312 | 19267 | 3363 | 6570 |
| 重入/节点 | 71 | 12036 | 11710 | 1711 | 6570 |
| 访问控制/合约 | 114 | 13432 | 15538 | 3765 | 2977 |
| 访问控制/节点 | 57 | 7710 | 8840 | 2632 | 2977 |

以上边数是 prepared HCG 边数；原模型的基础关系反射行为照旧，新 DDG 不添加反向关系。所有任务均有 16 种节点类型。模型实际注册的 canonical relations：

| 任务 | E0 | E1 | fold0 train/val 文件 |
|---|---:|---:|---:|
| 重入/合约 | 165 | 179 | 113/29 |
| 重入/节点 | 146 | 158 | 63/8 |
| 访问控制/合约 | 163 | 179 | 91/23 |
| 访问控制/节点 | 153 | 168 | 51/6 |

固定特征为已核验的 Salesforce/codet5p-770m tokenizer ID、inside_token、float32[512]；原 stored code（包含作者 DOT 序列化形式）不改。本轮不调用完整 LLM，不重新编码。

**13.5 测试与结构审计**

按阶段先测试再进入下一阶段：

| 阶段 | 验证 | 结果 |
|---|---|---|
| 划分与初始化 | 新协议 + 旧 protocol 测试 | 24 passed |
| 完整图运行 | 新 runtime + 旧 runtime | 36 passed，4 个依赖弃用警告 |
| 训练与 checkpoint | 新 run + 旧 run_pair + 旧 checkpoint | 18 passed，4 个依赖弃用警告 |
| 实验全套 | experiments/tests | 95 passed，4 warnings |
| DDG 全套 | scripts/DFG/tests | 170 passed，28 warnings |
| 原项目全套 | tests（当前同四个测试文件） | 25 passed，7 warnings |
| 主折结构审计 | 两类 × (5+10) 折，E0/E1 配对 | 30/30 pass，0 blocked |

阶段测试有重叠，不能把表内各行相加。最终三套回归总计 **290 passed，0 failed，0 skipped**，其中新增实验测试 42 项。警告是现有 DGL/TensorBoard distutils 与 NetworkX read_gpickle 弃用提示，未升级依赖。合成图测试不等于 Solidity 编译验证。

实际命令和完整日志保存于 `audit/paper_kfold_v1/test_results.json` 与 experiments.log/ddg.log/project.log。命令为 mando 环境的：

~~~bash
python -B -m pytest scripts/DFG/experiments/tests -q
python -B -m pytest scripts/DFG/tests -q
python -B -m pytest tests -q
~~~

30 折中 **21 折存在完整图已注册但 train 未出现的类型或关系**，均保留；所有 E1 折都至少存在一些训练 DDG 边。审计不仅统计 NetworkX：每个完整任务图实际构造原 HGT，核对其注册 schema 和 model_validation 输入摘要，再对每折计算支持统计。没有对 30 折做完整训练。

**13.6 四任务 fold0 短检查**

CPU，threads=2，固定 seed1，hidden128、2 层、8 头、norm、dropout0.2。每个 E0/E1 3 个 epoch，使用 50-step OneCycle 计划；没有把调度压缩到 3 步。

- 节点：Adam initial_lr=0.0002，max_lr=0.005，div_factor=25，weight_decay=0。
- 合约：Adam initial_lr=0.0005，max_lr=0.01，div_factor=20，weight_decay=5e-6。
- 共用 final_div_factor=1、cycle_momentum=True、无权重交叉熵。

| 任务（fold0，CV validation） | E0 Buggy-F1 / Macro-F1 | E1 Buggy-F1 / Macro-F1 |
|---|---:|---:|
| 重入/合约 | 84.6154 / 86.0577 | 84.6154 / 86.0577 |
| 重入/节点 | 78.3767 / 72.0414 | 78.3767 / 72.0414 |
| 访问控制/合约 | 85.7143 / 86.8571 | 85.7143 / 86.8571 |
| 访问控制/节点 | 77.5385 / 75.4965 | 77.1822 / 74.9714 |


指标单位为百分数。节点结果是 **HCG 节点 F1**，不是按文件+原始源码行去重后的独立行 F1。本次 8 次短训练的 best 和 last 均在第 3 轮（JSON epoch=2），两者指标相同；不是程序把 best 固定成 last，而是三轮 val loss 每次都降低。重入合约第二轮 Buggy-F1 更高，第三轮 loss 更低；按已规定的 loss 选模，所以 best 是第三轮。

每个模型的 best/last 都重载两次，eval logits 逐位一致；导出的预测重新计算指标与结果 JSON 完全相同；参数身份始终未改变。四个 E1 的首轮 DDG message 梯度 L1 与三轮 message 参数变化如下：

| task | first DDG gradient L1 | DDG weight update L1 |
|---|---:|---:|
| 重入/合约 | 0.537885 | 93.426578 |
| 重入/节点 | 0.591061 | 36.625085 |
| 访问控制/合约 | 0.532469 | 99.760648 |
| 访问控制/节点 | 1.684659 | 44.343665 |


访问控制合约 fold0 存在两个验证独有关系：
- (expression_statement, DATA_DEF_USE, while)：train 0 条、val 2 条。
- (new_variable, DATA_DEF_USE, while)：train 0 条、val 2 条。

它们的监督 message 梯度都是 0，状态为 `no_training_ddg_support`，折正常完成。这是“注册支持与训练支持分离”的真实数据证据。

前三个任务 E0/E1 的最终离散预测相同，但 loss/概率不同；访问控制节点 E1 在短检查中多 3 个 FP，Buggy-F1 低约 0.356 个百分点。**三轮短检查不能证明 DDG 有效或无效，不能把这些数当成论文对比的最终 K 折成绩。**

**13.7 输入不变性、产物与命令**

末次摘要核验：46 个冻结核心代码文件全部未改变；112 个旧实验文件中只有 README 增加主协议说明，其余均未改变。旧 prepared 图、token、标签、旧 nested 结果/日志/权重保持不变。两类原输入图与标签 JSON 的摘要相符，142+114 份源码摘要也相符。证据：`audit/paper_kfold_v1/verification.json`。

新产物位置：
- `artifacts/paper_kfold/20261012_v1/<cohort>/splits/`：转换后的两种任务清单。
- `artifacts/paper_kfold/20261012_v1/structure_audit/`：30 折结构与注册输入审计。
- `artifacts/paper_kfold/20261012_v1/<cohort>/smoke_<task>/`：配置、折清单、schema 支持、共同初始化、best/last、历史和预测。
- `artifacts/paper_kfold/20261012_v1/smoke_summary/cv_validation_summary.csv`：16 行（4 任务×E0/E1×best/last）短检查结果。
- `audit/paper_kfold_v1/smoke_execution.json`：实际执行命令、退出码和耗时。

可运行命令见 README 主协议部分，包含完整的重入节点命令，无须预先设置 BASE/RUN_TAG。切换 task=contract 并改 contract_folds.json 即合约任务；切换 cohort 为 access_control_author 即访问控制。目录存在时拒绝覆盖，复跑需新输出名。旧 nested 仅通过显式 protocol=nested_strict 或旧 run_pair 命令进入，仍可能按旧规则阻断，不把旧结果重新命名成主结果。

**13.8 剩余限制与未执行事项**

- 没有运行 60 次完整训练、其他折性能实验、多 seed 或 local narrow 的新训练。完成本轮规定的结构审计和短检查后停止。
- 主协议的 val 同时用于早停、选模与评分，具有选模偏差；不能称独立测试估计。若需要该估计，保留的 nested_strict 是另一协议，其阻断问题不在本轮悄悄放宽。
- 完整任务图的 schema 在训练前已知。训练未见的参数没有该关系的训练监督，预测可能依赖初值/正则项；这不是已学会该关系。
- 原 HGT 的跨关系 mean 聚合保留。完整 schema 及新增关系可能改变聚合归一化，故 E0/E1 的任何差异不能一概归因于 DDG 所携带的数据语义；本轮不增加随机边/关系数控制实验，也不改 HGT。
- 作者标签来源与历史源码身份仍不能由本轮恢复。两类的已发布标签按原样冻结，不混入 narrow。文件级切分也没有消除 SolidiFI 模板复用。
- 保留当前标量、函数内、正向 DDG 范围，不扩展状态变量、mapping、跨函数摘要、缺失 emit 节点或反向关系；不声明完整 Solidity DDG 已实现。
- 本轮没有下载/安装依赖或编译器，没有运行新的 solc 编译验证；没有 resume-training CLI 和任意新源码推理扩展。


## 14. 2026-10-12：正式paper_kfold执行层及完整fold0验证（Codex）

**14.1 授权与版本**

修改AI：Codex。用户要求冻结DDG/HGT/tokenizer/标签/折，先A资源及B重入合约fold0，
确认后再全量。本轮执行A/B，未执行C。基础HEAD及origin HEAD均为70c9d44b183dd81910fb5a9bdc30f3f9424e16b2；
只读核验，无pull/merge/checkout/自动提交。主paper_kfold，nested_strict不改。
E0=作者HCG/标签+本地核验512维CodeT5p-770m tokenizer IDs+现有HGT；
E1仅加正向DATA_DEF_USE，不混narrow，不使用完整LLM权重。

**14.2 文件、修改位置及理由**

全部新代码/测试在scripts/DFG/experiments/：

| 文件 | 操作 | 实现及理由 |
|---|---|---|
| resource_probe.py | 新增 | CUDA/nvidia-smi检查，成对加载与各一次完整图训练；失败记录blocked，不擅自改设备/模型 |
| formal_worker.py | 新增 | 包裹原构造和fit，记录参数量、显存、monotonic耗时；finally恢复引用，不改计算 |
| formal_checks.py | 新增 | 重放学习率/早停，检查图/标签/监督/schema/初始化/配置/checkpoint绑定，重算指标和差值，汇总完整任务 |
| formal.py | 新增 | 固定30配对折、阶段门槛、逐任务验收，互斥锁/PID启动时刻检查，失败保留与整折重试、成功复用 |
| tests/test_formal_checks.py | 新增 | 历史/指标/不完整结果拒绝和汇总数值测试 |
| tests/test_formal_controller.py | 新增 | B/C门槛、任务屏障、恢复、摘要损坏、并发、代码/数据漂移及真实计划测试 |
| tests/test_formal_end_to_end.py | 新增 | 原HGT真实小图full训练两任务，验收并拒绝破坏checkpoint |
| tests/test_formal_telemetry.py | 新增 | 包裹异常恢复、CPU统计、无CUDA不隐式降级 |
| README.md | 追加 | 实际可执行命令、恢复条件、输出角色和限制 |
| FORMAL_EXPERIMENT_REPORT_2026-10-12.md | 新增 | 完整分析、资源、结果与下一阶段设计 |
| 本文/HANDOVER.md | 追加 | 详细/简略交接，保留旧正文及字节备份 |

未修改原paper_run、DDG算法、HGT、tokenizer、原训练脚本、prepared图/特征/标签、
固定划分或旧nested结果。67个本轮前记录文件摘要未变；记录见
audit/formal_20261012_v1/final_verification.json。

**14.3 对模板的调整**

B计入正式5折，C复用；不重跑挑成绩。只支持折级续跑，不伪造epoch-resume：
成功折摘要验证复用，失败保留旧attempt，显式--retry-failed按相同seed/config重跑整对。
存活worker不重复启动，损坏成功结果不自动重训掩盖。代码/输入变更需新批次。
C须--confirm-stage-c；主结果叫CV validation，同val选best并评分。
原早停指当前已冻结patience7/delta0.001和严格最低val loss best，不回退到历史上游问题实现。
显存测完整训练步，不能只估权重；增加逐样本错误转移辅助分析。
nested/narrow/其他标签版本不混入主统计。

**14.4 测试与不变量**

先27项定向通过，随后两种任务真实小图full端到端通过；补进程/冻结计划测试。
最终：实验133 + DDG170 + 原项目25 = **328 passed，0失败、0跳过**。
各套警告4/28/7，为既有弃用。DDG pytest打印负时间，外部monotonic约3.4秒，
原日志保留；正式训练使用perf_counter。没有安装/升级依赖或执行新solc。
测试命令及日志在audit/formal_20261012_v1/，旧文档字节备份也在该目录。

**14.5 实际A/B结果**

RTX3050 Laptop 4GiB四任务探针通过。正式E1峰值2.58GiB allocated/2.78GiB reserved，
整卡采样一度余59MiB；后续显存竞争仍可能失败，不自行缩图。
重入合约fold0：113train/29val（15正），seed1，50epoch上限，lr0.0005→max0.01。
E0/E1都第14轮早停、best第7轮（JSON 6/13）；完整checkpoint及预测验收通过。

| fold0 CV validation | E0 BF1/MF1 | E1 BF1/MF1 | E1−E0百分点 |
|---|---:|---:|---:|
| best | 84.6154/86.0577 | 84.6154/86.0577 | 0/0 |
| last | 92.8571/93.0952 | 88.8889/89.6057 | -3.9683/-3.4895 |

Precision均100；best Recall73.3333；last E0 Recall86.6667、E1 Recall80。
last E1新增simple_dao.sol漏报，原样保留，不事后改主checkpoint。
参数E0 4526962、E1 4641874；训练DDG边2665，监督梯度L1累计4.781603，
权重变化L1=1494.641465可能含weight decay；耗时105.59/132.22秒（含验证和保存/重载）。
实际重调stage-b只复用，无新attempt。单折产物约318MiB，30配对同规模粗估9.3GiB。

**14.6 产物、执行、回退与限制**

新批次artifacts/paper_kfold/formal_20261012_v1/；计划、状态、逐折产物均在其中。
audit/formal_20261012_v1/stage_b_summary.csv/json仅是一折，非全CV均值。
详细可执行WSL命令在README新段与本轮报告，不依赖BASE/RUN_TAG。
C须用户确认后显式执行；重入合约→访问控制合约→重入节点→访问控制节点，
5/5/10/10折，每任务验收后才继续。B已做2次，剩58次；本轮未启动。
原baseline/nested入口没有改变，不使用formal入口即可走旧流程。
没有全CV结果，也未做narrow/nested、多seed、随机边、DDG范围扩展或7类全量。
论文只是外部参考；标注历史、模板复用、同val选模偏差、参数量/聚合变化需分别解释。


## 15. 2026-10-12：冻结阶段 C 续跑及独立结果统计（修改 AI：Codex）

**15.1 授权、历史与当前状态**

用户已明确授权完成剩余29个配对折、58次模型拟合。主协议paper_kfold；
DDG/HGT/tokenizer/图标签/划分/初始化/学习率/早停/best选择规则保持冻结。
原有第13节（主协议）与第14节（正式控制器、A/B）完整保留，本节承接这些记录，
不改写此前结果。本段写入时阶段C仍在运行，只有导入的重入合约fold0整体通过；
不能把本段当作全部训练已经完成的报告。UTC实际执行日期2026-10-13，纽约当地为2026-10-12。

**15.2 必要适配：提交绑定迁移，训练字节未变化**

当前Git HEAD为646e9b3495c0fe7f2c4a6e4b72d0bab64d6ee2fc，
旧批次绑定70c9d44b183dd81910fb5a9bdc30f3f9424e16b2。
新提交只是收录上轮正式实验代码与记录，39个运行代码摘要、68个冻结文件摘要完全相同。
现有formal.validate_plan会因HEAD不同正确拒绝旧批次；没有放宽此检查、修改旧seal或回退Git。

按原控制器要求新建artifacts/paper_kfold/formal_20261012_v1_stage_c/：
新旧plan只有base_git_head、created_utc两项不同，其他字段逐项相同；
复制旧fold0整个job（初始权重、best/last、日志、receipt）并通过verify_receipt和verify_fold。
新state记录import_provenance，保留原command作为历史；未重训fold0，不复制旧执行锁。
原plan/state/receipt与旧权重保留。证据在audit/stage_c_20261012_v1/migration.json、
before.json、preflight.json；新批次也保留migration.json。这是产物与版本绑定适配，不是计算协议变更。

**15.3 新增只读统计文件与原因**

现有formal的逐任务汇总已有指标均值和std，但不完整包含本轮要求的错误转移、
逐指标升/平/降、显存和全部attempt历史。训练模块不得修改，故新增文件仅在：
scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/。

| 文件 | 修改方式 | 实现/理由 |
|---|---|---|
| report_stage_c.py | 新增 | 仅标准库读JSON/CSV；校验plan seal、receipt、产物摘要；独立重算预测指标及错误转移；完整任务才汇总 |
| test_report_stage_c.py | 新增 | 26项数值/JSON夹具测试，验证统计、协议拒绝、完整性门槛、耗时不重复等 |
| README.md | 新增 | 实际CLI、结果字段、统计口径和限制 |
| creation_code_hashes.json、final_verification.json | 新增记录 | 写前写后39项运行代码摘要一致 |
| tests_v2.log/json、reports/status_v1/ | 新增验证产物 | 26通过及真实未完成任务快照，不输出部分折平均值 |

顶层experiments/*.py和DFG/*.py会参与冻结摘要，因此没有把统计脚本放在这些层级。
没有导入模型/启用GPU、改formal或修改HGT，报告代码不参与训练计算。
均值等权按折，标准差ddof=1；差值std直接对成对差值计算。
升/平/降按每个指标单独统计，1e-10百分点仅作浮点平局容差。
best/last分开；耗时每fold/variant只计一次；GPU峰值注明双模型驻留进程口径。
节点指标保持(file, original_graph_node_id)口径，未改成去重源码行F1。
不能恢复的历史失败原因写unknown，不能编造；未完成任务写pending而非部分均值。

**15.4 验证及运行规则**

新增统计测试26 passed，0失败/跳过/警告；另一次独立只读审查确认口径一致。
上轮328项通过记录保留；本轮没有把旧测试冒充重新执行。
本轮对旧fold0做完整文件摘要与验收复核，39代码/68冻结文件不变；
每个新折继续由原formal执行训练、checkpoint、预测、梯度及输入绑定验收。
任务顺序：重入合约fold1–4；访问控制合约fold0–4；
重入节点fold0–9；访问控制节点fold0–9。
每任务全部折验收后才进入下一任务，不要求E1高于E0。
失败保留，不无限重试、不改设备/缩图/改参数，不把last改成主结果。

**15.5 执行观察及未完成验证**

本段记录时首次新训练仍是reentrancy_author_contract_fold1/attempt_001，
无训练失败或重试。E0已经18轮早停并完成收尾，fit/eval/checkpoint耗时约1118.08秒；
E1仍在训练。资源采样整卡仅余约80–107MiB，GPU满载且有视频编码负载。
耗时偏长的原因尚未确定，不能仅凭采样归因于DDG或模型错误。
观察到WSL系统时钟回拨、日志mtime晚于读取时间；不用文件时间差估算精确训练耗时，
以训练器perf_counter记录为准，不把停顿观察当成失败或自动重试依据。
尝试使用已有strace做限时只读诊断，因ptrace权限拒绝而未取到内部栈；
未安装工具、未改变系统安全设置。slow_step_diagnostic.json保留原始结果。
最终完成或发生执行错误后，将追加真实验收、完整性和四任务统计，不能预写成功。

**15.6 当前命令与产物**

从WSL项目根目录、mando环境使用现有入口：
python -u -B -m scripts.DFG.experiments.formal stage-c --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c --confirm-stage-c
本次已运行，不要再次并行启动。主日志audit/stage_c_20261012_v1/stage_c_controller.log，
执行状态execution.json；每折实时日志在新批次jobs/<任务>_foldN/attempt_001.log。
完整任务后生成独立报告时使用analysis/report_stage_c.py --run <新批次> --output <新报告目录>。
旧成功fold复用，显式失败重试才建新attempt，绝非epoch断点续训。
本轮不运行nested_strict、narrow、多seed、新模型模块，也不修改标签或DDG支持范围。


**15.7 2026-10-13：四任务全部完成及最终绑定核验（修改 AI：Codex）**

本条为第15.1–15.6运行中记录之后的最终完成补充，旧记录原样保留。
阶段C控制器退出码0；完成时间2026-10-13T04:10:27.137687+00:00，
纽约当地2026-10-13 00:10:27。控制器monotonic耗时8490.0263秒（约141.50分钟），
随后formal verify退出码0，确认30/30配对折通过；独立最终报告4任务complete、0 pending。
共计30个配对折、60次模型拟合：本轮新执行58次，另2次是原重入合约fold0的E0/E1完整复用，
不是本轮重训60次。实查60个best.pt和60个last.pt，共120个checkpoint文件；所有job均为attempt_001，
无拟合失败、无重试、无换seed/删折/挑选成绩。

E0固定为作者发布HCG及标签，加本地已核验512维CodeT5p-770m tokenizer IDs、inside_token；
E1是同图只增加正向DATA_DEF_USE，保留全部原节点、标签、特征和CFG/CG边。
本轮没有加载完整LLM权重、重新编码或重建数据。主paper_kfold保持单层文件K折，
合约5折、节点10折，同val选best并评分；结果名称为CV validation。

最终冻结审计确认39项运行代码与68项冻结文件摘要不变；新旧plan仅base_git_head、created_utc不同。
旧HEAD=70c9d44b183dd81910fb5a9bdc30f3f9424e16b2，新HEAD=646e9b3495c0fe7f2c4a6e4b72d0bab64d6ee2fc。
旧fold0复制前后字节一致，receipt及完整fold双重验收通过；复用来源记录在该job的
state entry.import_provenance和migration.json中。最终派生report顶层import_provenance为null，
因为来源存在job entry层级；此字段不是新的训练或数据缺失，正式来源以migration和job entry为准。
旧plan、state、receipt、checkpoint未改；没有放宽绑定检查、回退提交或在训练期间提交修改。

最终证据位于scripts/DFG/experiments/audit/stage_c_20261012_v1/：
execution.json、final_verify.json/log、final_report_command.json、migration.json、
analysis/final_frozen_audit.json及analysis/reports/final_v1/。

**15.8 best主结果：最低验证loss选模**

以下均为等权折均值±样本标准差（ddof=1），不是置信区间；E0/E1数值单位为百分数，
E1−E0单位为百分点，差值std由每折配对差值直接计算。Buggy-F1是正类F1，Macro-F1对两类平均，
Precision/Recall为正类指标。不同漏洞、任务粒度不混算。

| 任务 | 配置 | Buggy-F1 | Macro-F1 | Precision | Recall |
|---|---|---|---|---|---|
| 重入/合约 | E0 | 94.1593 ± 5.8347 | 94.3452 ± 5.2827 | 96.1667 ± 5.6396 | 93.2381 ± 11.5490 |
| 重入/合约 | E1 | 93.5157 ± 5.6802 | 93.6245 ± 5.1729 | 95.0000 ± 6.8465 | 93.2381 ± 11.5490 |
| 重入/合约 | E1-E0 | -0.6437 ± 1.4393 | -0.7207 ± 1.6115 | -1.1667 ± 2.6087 | 0.0000 ± 0.0000 |
| 访问控制/合约 | E0 | 93.5590 ± 2.5626 | 93.8316 ± 2.3850 | 98.3333 ± 3.7268 | 89.3939 ± 4.2519 |
| 访问控制/合约 | E1 | 93.5590 ± 2.5626 | 93.8316 ± 2.3850 | 98.3333 ± 3.7268 | 89.3939 ± 4.2519 |
| 访问控制/合约 | E1-E0 | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 |
| 重入/节点 | E0 | 96.0580 ± 10.1730 | 96.0088 ± 10.4832 | 94.6366 ± 14.7388 | 98.5817 ± 2.4230 |
| 重入/节点 | E1 | 96.0740 ± 10.0411 | 96.0107 ± 10.2829 | 94.5650 ± 14.5568 | 98.6565 ± 2.3225 |
| 重入/节点 | E1-E0 | 0.0161 ± 0.2242 | 0.0019 ± 0.2708 | -0.0716 ± 0.2070 | 0.0748 ± 0.3417 |
| 访问控制/节点 | E0 | 95.9723 ± 7.4499 | 96.8764 ± 5.5287 | 94.9924 ± 11.2942 | 97.4669 ± 3.0370 |
| 访问控制/节点 | E1 | 95.8130 ± 7.3344 | 96.7384 ± 5.4314 | 94.7985 ± 11.0848 | 97.3294 ± 3.1424 |
| 访问控制/节点 | E1-E0 | -0.1593 ± 0.3648 | -0.1380 ± 0.2997 | -0.1939 ± 0.5403 | -0.1375 ± 0.2921 |

各任务完整逐折四指标、best/last、配对差值保存在final_v1/REPORT.md和fold_metrics.csv，
所有低分折均纳入均值。节点统计单位仍为(file, original_graph_node_id)，
不是按文件+源码行去重后的独立源码行F1。

**15.9 last辅助结果：不替代主评分**

| 任务 | 配置 | Buggy-F1 | Macro-F1 | Precision | Recall |
|---|---|---|---|---|---|
| 重入/合约 | E0 | 90.8867 ± 4.0547 | 90.8508 ± 3.9624 | 90.4762 ± 6.1353 | 91.6190 ± 5.7597 |
| 重入/合约 | E1 | 88.9362 ± 4.8619 | 88.6855 ± 5.3119 | 88.4370 ± 8.8235 | 90.2857 ± 7.6532 |
| 重入/合约 | E1-E0 | -1.9505 ± 2.7469 | -2.1652 ± 3.2619 | -2.0392 ± 4.5598 | -1.3333 ± 2.9814 |
| 访问控制/合约 | E0 | 85.9247 ± 6.4256 | 85.8996 ± 7.1171 | 88.1049 ± 9.1769 | 84.2424 ± 7.0132 |
| 访问控制/合约 | E1 | 83.8095 ± 7.0569 | 83.2511 ± 8.3536 | 84.1538 ± 11.8372 | 84.2424 ± 7.0132 |
| 访问控制/合约 | E1-E0 | -2.1152 ± 3.3175 | -2.6485 ± 3.9164 | -3.9510 ± 6.1408 | 0.0000 ± 0.0000 |
| 重入/节点 | E0 | 97.1504 ± 6.8062 | 97.3135 ± 6.4413 | 95.6913 ± 11.0584 | 99.3395 ± 0.8549 |
| 重入/节点 | E1 | 96.9007 ± 6.7299 | 97.0240 ± 6.3498 | 95.2852 ± 10.9595 | 99.2524 ± 0.7463 |
| 重入/节点 | E1-E0 | -0.2497 ± 0.3073 | -0.2894 ± 0.3994 | -0.4061 ± 0.5984 | -0.0871 ± 0.4483 |
| 访问控制/节点 | E0 | 95.8010 ± 5.8196 | 96.6133 ± 4.3615 | 94.3202 ± 10.2951 | 97.9893 ± 1.7607 |
| 访问控制/节点 | E1 | 95.2313 ± 6.7664 | 96.1464 ± 5.1923 | 93.8639 ± 11.7561 | 97.5396 ± 1.9913 |
| 访问控制/节点 | E1-E0 | -0.5698 ± 1.4188 | -0.4669 ± 1.2381 | -0.4563 ± 1.5924 | -0.4497 ± 1.7886 |

last仅用于观察最终停止轮的行为；没有因个别fold的last F1较高而改变最低val loss的best规则。
JSON epoch为0基编号，面向用户的第几轮应加1；全部60个模型的best_epoch、last_epoch、实际epochs和
stop_reason见fit_telemetry.csv。训练轮次及学习率、patience7/delta0.001均由原验收器重放核验。

**15.10 逐折升平降、错误变化与难例**

下表每格为“提升/持平/下降”折数，分别针对相应指标；浮点持平容差仅1e-10百分点。

| 任务 | 权重 | Buggy-F1 升/平/降 | Macro-F1 升/平/降 | Precision 升/平/降 | Recall 升/平/降 |
|---|---|---|---|---|---|
| 重入/合约 | best | 0/4/1 | 0/4/1 | 0/4/1 | 0/5/0 |
| 重入/合约 | last | 0/3/2 | 0/3/2 | 0/4/1 | 0/4/1 |
| 访问控制/合约 | best | 0/5/0 | 0/5/0 | 0/5/0 | 0/5/0 |
| 访问控制/合约 | last | 0/3/2 | 0/3/2 | 0/3/2 | 0/5/0 |
| 重入/节点 | best | 4/1/5 | 3/1/6 | 2/1/7 | 4/4/2 |
| 重入/节点 | last | 2/2/6 | 2/2/6 | 2/2/6 | 2/4/4 |
| 访问控制/节点 | best | 3/3/4 | 3/3/4 | 3/3/4 | 0/8/2 |
| 访问控制/节点 | last | 2/1/7 | 2/1/7 | 3/2/5 | 1/5/4 |

错误转移按各折实际验证样本累计。合约任务是文件数，节点任务是HCG节点数，不能互相比较绝对数量。

| 任务 | 权重 | 纠正FP | 纠正FN | 新增FP | 新增FN | 双方正确 | 双方错误 |
|---|---|---|---|---|---|---|---|
| 重入/合约 | best | 0 | 0 | 1 | 0 | 133 | 8 |
| 重入/合约 | last | 0 | 0 | 2 | 1 | 126 | 13 |
| 访问控制/合约 | best | 0 | 0 | 0 | 0 | 107 | 7 |
| 访问控制/合约 | last | 0 | 0 | 3 | 0 | 95 | 16 |
| 重入/节点 | best | 9 | 8 | 13 | 7 | 11588 | 411 |
| 重入/节点 | last | 9 | 4 | 27 | 16 | 11709 | 271 |
| 访问控制/节点 | best | 4 | 0 | 9 | 4 | 7486 | 207 |
| 访问控制/节点 | last | 11 | 9 | 33 | 24 | 7422 | 211 |

完整both_correct/both_wrong/单方纠正计数在report.json，
逐个文件/节点的变化见error_transitions.csv和changed_predictions.csv。
访问控制合约best两组离散预测全同，不能据此说概率、loss或模型参数也相同。
重入合约best中E1多1个FP；last的simple_dao.sol新增漏报也如实保留。

重入节点fold8尤其影响标准差：best E0/E1 Buggy-F1为67.1986/67.5579，
其余多数折接近99。两组均best第5轮、停止第12轮（JSON 4/11）。
E0 best loss=0.644100、last loss=0.976942，虽然last F1=77.9171更高，
按最低loss保存第5轮是正确执行冻结规则，不是拿错checkpoint。
buggy_18.sol在该fold中有424节点、35个作者正例；两组best均出现250 FP、2 FN。
这指出错误集中位置，不能单凭低分或误报数证明作者标签错误；本轮没有重标注、删文件或重跑此折。
证据见analysis/independent_reentrancy_node_review.json中的fold8与per_file明细。

总体结果未呈现稳定的正向DDG收益：重入节点best平均仅+0.0161百分点，
该指标4折升、1折平、5折降，不能把微小正均值写成稳定提升或统计显著改进。
重入合约和访问控制节点best略降，访问控制合约best持平；last四任务平均均下降。
本轮只得到冻结配置下的观察结果，没有为改善分数改超参数或扩大DDG范围。

**15.11 DDG支持、梯度、参数与运行成本**

每次fit只计一次耗时，不能因为best/last两种评分重复相加。
下表时间含拟合、验证、checkpoint保存/重载评分，GPU数据为双模型驻留进程的PyTorch峰值，
不是独立E0/E1模型显存，也不是整张显卡占用。

| 任务 | 配置 | 参数量 | fit总秒数 | allocated峰值MiB | reserved峰值MiB |
|---|---|---|---|---|---|
| 重入/合约 | E0 | 4526962 | 1446.37 | 2159.49 | 2348.00 |
| 重入/合约 | E1 | 4641874 | 2392.58 | 2749.57 | 2954.00 |
| 访问控制/合约 | E0 | 4510546 | 308.80 | 1593.42 | 1686.00 |
| 访问控制/合约 | E1 | 4641874 | 323.62 | 2130.55 | 2278.00 |
| 重入/节点 | E0 | 4371010 | 879.60 | 1391.53 | 1512.00 |
| 重入/节点 | E1 | 4469506 | 890.97 | 1825.83 | 1962.00 |
| 访问控制/节点 | E0 | 4428466 | 797.04 | 954.49 | 1038.00 |
| 访问控制/节点 | E1 | 4551586 | 805.59 | 1365.21 | 1486.00 |

各任务E1训练DDG边数及累计message梯度如下；E0不含DDG，该项为0。
“train未见关系折数”统计完整图已注册但train无实例的全部canonical关系，
不能误读为整个fold无DDG训练支持。所有E1折均有训练DDG实例及已观测到的监督梯度。

| 任务 | 训练DDG边范围 | DDG梯度L1累计 | E0/E1 train未见关系折数 |
|---|---|---|---|
| 重入/合约 | 2592-2844 | 24.375570 | 2/3 |
| 访问控制/合约 | 2848-3151 | 29.497752 | 5/5 |
| 重入/节点 | 1366-1666 | 121.145579 | 6/6 |
| 访问控制/节点 | 2288-2438 | 239.132191 | 6/7 |

注册但只在val出现的关系保留，监督梯度为0是无训练支持的预期行为，不能因此删折。
梯度总和依赖实际epoch数；参数变化可能含weight decay，不能把非零参数变化当成独立监督证据。
逐折支持量、训练未见relation列表、梯度累计及参数变化见fit_telemetry.csv和各折gradient_audit.json。

全任务fit耗时汇总包含旧fold0原运行时间；它与本轮58次新fit的控制器总耗时不是同一量。
重入合约fold1曾明显变慢，期间整卡显存余量很窄且有视频编码负载。
这些只是资源观测，因果原因未确定，不能将该任务E1/E0总时间比当作纯DDG计算开销。
曾观察到WSL实时时钟回拨；使用perf_counter而非日志mtime估算fit耗时。
本轮没有GPU OOM、缩图、改模型参数或切CPU。

**15.12 最终验收、测试与失败记录**

- 四任务按既定顺序逐任务验收后继续；30个receipt与全部封存产物摘要通过最终复核，
  120个best/last文件完整，模型重载与预测一致性、输入/schema/划分/初始化绑定、
  mask或文件监督、梯度、学习率及早停历史通过原formal验收。
- 新增只读统计代码仍仅report_stage_c.py和test_report_stage_c.py，位置为
  scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/；配套README和JSON/CSV/MD产物不参与训练。
  本轮26项统计回归测试通过，0失败/0跳过/0警告。上轮328项原实验/DDG/项目测试记录保留，
  没有把历史通过结果冒充本轮重新运行。
- 独立复核文件：analysis/independent_contract_review.json、
  independent_reentrancy_node_review.json、independent_access_control_node_review.json。
  它们独立重算预测、四指标、配对均值/std、升平降和文件/节点覆盖；
  使用已验收checkpoint证据，不额外加载GPU或重训模型。
- 全部attempt与状态见final_v1/attempts.csv。30个job均attempt_001，
  无失败fit、无自动/手动重试，没有不完整折混入成绩。
- 旧plan因Git HEAD变化在训练前被拒绝，是正确的绑定保护；通过显式新批次迁移解决，
  不计为模型训练失败。已有strace的只读诊断因OS ptrace权限拒绝未取到栈，
  属于诊断失败，不是训练失败；未安装工具、未改系统安全设置。
- 本次文档仅追加第15.7–15.13及HANDOVER最终完成记录，保留旧字节前缀；
  修改AI为Codex。追加前后哈希、原字节长度、前缀验证、中文完整性、
  来源文件摘要及章节行号见analysis/documentation_final_update.json。

完整派生表实查：fold_metrics 120行、metric_summary 96行、fit_telemetry 60行、error_transitions 60行、changed_predictions 194行、attempts 30行；行数均不含CSV表头。

**15.13 结果入口、可运行命令与范围限制**

完整报告目录：
scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/reports/final_v1/。

| 文件 | 内容 |
|---|---|
| REPORT.md | 四任务逐折、best/last、均值/std、升平降、错误及资源总表 |
| report.json | 完整数值、协议/状态摘要、错误明细、attempt信息 |
| fold_metrics.csv、metric_summary.csv | 逐折四指标/差值及等权配对统计 |
| fit_telemetry.csv | 每次fit的epoch、参数、支持/梯度、显存和耗时 |
| error_transitions.csv、changed_predictions.csv | 各折错误转移及每个变化节点/文件 |
| attempts.csv | 原fold0复用后的全部job attempt与执行状态 |

从项目根目录、mando环境可复核，不会重新训练：
~~~bash
python -B -m scripts.DFG.experiments.formal verify \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c
~~~

生成新的只读报告需指定不存在的新目录，不能覆盖final_v1：
~~~bash
python -B scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/report_stage_c.py \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c \
  --output scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/reports/final_v2
~~~

本轮完成后停止，没有启动nested_strict、narrow、多seed、其他5类漏洞、新模型模块、
随机边对照、状态变量/mapping/跨函数或反向DDG扩展，也未新增编译器验证。
当前仍为函数内标量Definition–Use MVP，不是完整Solidity DDG。
主协议在同一val上选best和评分，不能称独立测试；冻结作者标签不代表已经还原其历史生成方式；
文件划分也不消除SolidiFI模板复用。E1同时改变关系数量、参数量及HGT关系聚合，
这次配对衡量整体增强效果，不能将差异全部归因为数据依赖语义。
论文原数字仅外部参考，不与本地E0混合计算，不以“接近论文”或“必须提升”为成功判据。

## 16. 2026-10-13：冻结权重 DDG 原因诊断补记（修改 AI：Codex）

**16.1 时间、目的与历史边界**

本节补记上一轮已完成且已归档的诊断，不改写历史第15节。诊断执行时 HEAD 为3fb3fbcaed34c5c97976b570aac484935aa81484，随后用户归档到359a7f13d94fb2c7d8d5d4656d76a94a967e10e4。训练基646e9b3不变。历史input_audit/final_drift是当时的验收记录，不为当前HEAD重写。

新增内容全部位于scripts/DFG/experiments/audit/ddg_diagnostics_v1/。没有修改原DDG、HGT、tokenizer、训练器、标签、图、折、参数、早停和checkpoint。未重新训练，也未把固定权重置零诊断称为E0重新拟合。

**16.2 已新增代码及作用**

| 文件/组 | 作用与原因 |
|---|---|
| archive_audit.py、validate_runner_inputs.py | 按plan/state/receipt定位验收资产，原归档只读复核、保护摘要；不运行要求HEAD相等的formal verify |
| static_analysis.py | 冻结标量分析器内存重放，事实/投影/模型真实反射拓扑距离、错误覆盖和train-only重复统计 |
| posthoc_duplicate_strata.py | 按节点类型复核重复率，区分结构节点和表达式，标签只作事后分组 |
| interventions.py | 局部包装原forward；N等价、Z在两层跨关系聚合前置零实际DDG消息；恢复参数及图状态 |
| rewiring.py | 同文件/函数/canonical有向双边交换，保持度数与基础平行边；种子101/102/103 |
| diagnostic_common.py、run_diagnostics.py | 严格输入绑定、串行单模型GPU前向、一致性门槛、试点initial/best/last |
| aggregate_results.py | 从原ID对齐导出预测独立重算指标、混淆矩阵、翻转及消息概要 |
| write_report.py | 证据分级报告；不加载模型、不改变原成绩 |
| test_archive/test_runner/test_static/test_interventions/test_rewiring/test_runtime_compatibility/test_aggregate_results | 正常等价、Z语义、恢复、R约束、标签独立、指标重算和拒绝路径 |

记录与结果包括README、input_audit、coverage/edge_increment/sensitivity、rewiring_audit、message_norms、parameter_scales、representation_changes、case_studies、diagnostic_report及阶段日志。完整路径与大文件SHA已由后续归档写入docs/ddg_diagnostics_v1_local_assets.json。Git归档不等于完整本地大资产备份。

**16.3 实际诊断与结果**

全部30个配对折best完成；7个预定试点另测initial/last，共88次checkpoint状态评估。主观察使用原CV validation，节点单位为原HCG节点。N包装器与同设备原生forward逐位一致；归档概率使用预先声明的atol1e-6/rtol1e-5，未因失败放宽。

| 任务 | 正常E1 Buggy-F1 | 同权重DDG消息置零 | 分类翻转 |
|---|---:|---:|---:|
| 重入/合约 | 93.5157 | 92.8260 | 1/142 |
| 访问控制/合约 | 93.5590 | 93.5590 | 0/114 |
| 重入/节点 | 96.0740 | 96.0140 | 13/12036 |
| 访问控制/节点 | 95.8130 | 95.7955 | 1/7710 |

DDG参与计算，对部分预测有益，但未取得稳定E1−E0净收益。R全部种子无分类翻转，但节点任务通常8–9折没有val语义边扰动，不能据此判定依赖语义无用。节点DDG超出原两跳端点比例25.31%/10.22%；参数和入口来源占主导。状态、mapping内容、modifier和跨过程未覆盖。

节点正例stored-code在本折train精确重复率99.79%/99.03%，并有同文本异标签；这不是标签错误或泄漏的自动证明。总消息/残差范数不是普遍近零：节点两层约0.59–0.71、0.66–0.67；不能将首个弱消息试点外推全体。全4D bank Xavier与关系mean为候选机制，未完成因果分离。

**16.4 测试、失败和保护**

最终97 passed、0 failed、0 skipped、4条依赖弃用警告；独立重复分层210项一致性断言。5387份当时保护文件及HEAD未变。首次pilot因torch1.8 CUDA未初始化时查询显存失败，修复仅诊断脚本初始化顺序，旧失败目录保留，成功输出pilot_v2。静态统计初稿修正保留于draft_v1，不改原图或标签。没有solc安装/执行、模型训练、标签修订或状态分析实现。

**16.5 诊断后的决策**

先修复精确DOT投影与if/else注释两处确定缺陷并审计恢复量，同时核查难例上下文；不承诺增加边即可提高F1。这个建议在本节之后的新隔离版本实施，旧诊断目录保持不变。

## 17. 2026-10-13：DDG v1.1 正确性修复、D2上下文审查及D3设计（修改 AI：Codex）

**17.1 工作位置、版本和最小变更策略**

实际原HEAD=359a7f13d94fb2c7d8d5d4656d76a94a967e10e4，原已跟踪文件无未提交更改；已有未跟踪资产全部保留。新建detached worktree：
/home/zhao/SmartContract/ge-sc-llm-ddg-v11。
原业务代码仍为封存版本，不把新代码直接替换到原运行目录。原目录只按用户本轮授权追加本文件和HANDOVER，两份旧字节前缀保存并验证。没有commit/push/reset/pull。

新版本ddg-v1.1-correctness-fix；包版本0.1.1。主产物目录：
scripts/DFG/experiments/audit/ddg_v11_correctness/（在新worktree内）。
原图、源码、标签、token、checkpoint、receipt、plan/seal、折及原诊断都是只读输入。详细说明及实际命令见该目录README。

**17.2 核心修改：位置、旧行为、修复原因**

| 新worktree文件 | 旧行为/风险 | 新行为 |
|---|---|---|
| scripts/DFG/projection.py | 源码用Python literal_eval解码DOT；合法反斜杠源码投影失败，部分其他转义可能被错误接受 | 原文相等或与实际pydot.quote_if_necessary精确相等；保留AST ID/类型/端点/唯一性；对序列化物理多行字符串歧义保守拒绝 |
| scripts/DFG/semantic_cfg.py | 分支间comment被语法树标成body，旧第二body选中comment导致函数回退 | _if_bodies过滤直接子节点comment，严格验证condition/then/else数量与顺序；额外body、未知结构继续回退 |
| scripts/DFG/__init__.py | 0.1.0 | 0.1.1，明确新图来源 |

没有修改pipeline、access_extractor、symbol_table、reaching_definitions、HGT、tokenizer或原训练脚本。pydot的编码非完全单射：额外守卫针对解析器反例，不声称恢复了作者历史源码哈希。没有最近行、空白归一化或相似文本匹配。原始代码可在主工作树及Git起点读取，无需反向覆盖恢复。

**17.3 新增代码与测试位置**

| 位置 | 内容 |
|---|---|
| scripts/DFG/tests/test_projection_v11.py | 21项DOT正反向、锚点、歧义回归 |
| scripts/DFG/tests/test_semantic_cfg_v11.py | 25项分支/合流/KILL/终止/图不变量回归 |
| scripts/DFG/tests/test_semantic_cfg_conditions_v11.py | 6项条件注释与参数读取回归 |
| 新审计/protect_assets.py | 原资产前后摘要；新增文件检测；只允许两文档追加 |
| 新审计/coverage_rebuild.py | 从同一冻结E0用原/新代码重放，输出新图与事实差异 |
| 新审计/finalize_d1.py | 只允许3个核心差异、保留旧事实、逐事实恢复归因、D2门槛 |
| 新审计/test_audit_guards.py | 6项新增文件/非授权核心改动/伪造边事实的拒绝测试 |
| 新审计/context_design/context_audit.py及测试 | 精确文件/原nodeID/sourceSHA/作者标签/训练重复来源绑定，完整性错误不得降级成普通回退 |
| 新审计/context_design/文档和Oracle | D2语义审查、D3接口/状态位置/回退/实验设计；不执行状态分析算法 |

回归前后测试文件SHA一致。投影新测试原实现7失败/14通过，修复后加原投影测试30通过。语义新25测试原实现18失败/7通过；修复后通过，另6条件测试通过。不将Tree-sitter解析成功视为Solidity编译认证。

**17.4 四任务修复恢复量**

| 任务 | 支持函数 前→后 | 提取facts 前→后 | 投影facts 前→后 | DDG边 前→后 | 新边 | 新canonical |
|---|---:|---:|---:|---:|---:|---:|
| 重入/合约 | 2034→2035 | 5400→5415 | 4510→4822 | 3363→3561 | 198 | 0 |
| 重入/节点 | 1210→1210 | 2636→2636 | 2083→2380 | 1711→1894 | 183 | 2 |
| 访问控制/合约 | 2127→2128 | 6139→6145 | 5197→5624 | 3765→4032 | 267 | 0 |
| 访问控制/节点 | 1550→1550 | 4101→4101 | 3529→3858 | 2632→2836 | 204 | 1 |

投影失败文件3/3/5/2→0；前端文件回退6/2/12/2保持。注释修复恢复calculateTokens和getCurrentTokenPrice两个clean文件函数，所以节点任务函数和提取facts不变，仅投影恢复。

旧DDG端点/canonical/事实全部保留，0删除；原节点、ID、类型、标签、token、源码映射和基础多重边/key完全相同。DDG语义未变文件138/142、68/71、108/114、55/57；不包括新版本号和全局事实索引元数据必须逐字节相同的承诺。

新增边有原AST锚点与definition/use证据。文件级回退标签与逐事实恢复原因分开，详见D1_RECOVERY_ATTRIBUTION。独立审查后补强新增资产检查；没有用“只查旧文件哈希”代替完整保护范围的新文件检测。

新图：
after/reentrancy_author/E2_contract.gpickle、E2_node.gpickle；
after/access_control_author/E2_contract.gpickle、E2_node.gpickle。
E0引用原prepared，不重复生成。新schema和SHA见D1_PROVENANCE；未创建新训练plan，不改旧seal。E2节点canonical增加，不能认为参数量必然与E1相同。

**17.5 D2真实案例与标签边界**

核查12个原验证节点，绑定原作者图标签、sourceSHA、AST原行号、完整函数与旧E0/E1 best预测；追溯480个训练重复节点，447个得到完整精确函数上下文，33个因已知多pragma等前端限制记录为D级未回映。源码SHA或图身份错误会中止，而非吞掉。

D2只使用修复Projector建立源码对应；DDG覆盖、标签、预测仍来自封存E1，不把新E2边与旧预测混合解释。全部标签原样保留。

确认的代表性情况：
- R buggy_18外部调用节点2706作者标签0、公共CSV范围覆盖，同文本37个train节点全为1；这说明标签上下文/构造口径有疑问，不能由FP直接宣布标签错误。
- R buggy_18的send节点2675已有参数DDG但仍FN；R buggy_36乘法节点5961有DDG且E1纠正；另有无直接DDG路径却新增错误或被纠正的节点。
- mapping_write.sol的map是uint256[]数组，不是mapping；arbitrary_location_write_simple的公开标注行27对应长度检查而非直接行28自减。
- AC buggy_18/26部分owner_txoriginXX是参数，现有DDG已覆盖；不能把这批错误全归因于缺状态owner。
- AC26的to.call.value(amount);没有最终调用括号，不擅自叙述成已发生ETH转账。
- 有些纯算术节点已有完整局部依赖仍误判；modifier权限控制也不等价于state DEF→USE。

D2_CONTEXT_REVIEW、D2_CASE_AUDIT、D2_LABEL_AMBIGUITY、D2_MISSING_DEPENDENCIES及全函数证据保存在context_design。证据区分A身份/图事实、B语义解释、C标注歧义、D材料/映射不足。没有正式人工漏洞认证，也不根据预测重标注。

**17.6 D3方案：只设计，不实现**

采用源码声明与作用域身份的Storage-location abstraction，不伪称精确EVM slot。不用同名变量或相同键文本判断位置：mapping键关联局部定义版本、类型常量或调用帧内已确认builtin；MUST位置身份与may-reaching路径事实分开。

最小原型先支持直接声明的标量状态与可证明位置的简单mapping键。ENTRY_UNKNOWN和外部调用HAVOC从第一版就必须有；未知调用/别名不能保留不合理的强定义。强KILL仅用于确定单一位置；弱更新、分支union、循环fixpoint与未投影写入仍覆盖必须测试。state回退保留原HCG与标量DDG，不提交部分不可信状态边。

原HCG不加变量/状态节点。拟用独立StateFunctionIR旁表引用原分析CFG，不替换模型CFG/CG。提议STATE_DEF_USE与标量DATA_DEF_USE语义分开；require对敏感写入是控制约束，modifier执行另立项；同位置先读后写、回调/调用事件不是传统def-use。

特别是入口余额读取→外部调用→余额清零，后面的写不能倒连成前面读的definition；仅增加函数内state DEF→USE可能合法地新增0条边。应先用Oracle检查真实信息增量再决定是否实现更广关系，不能为了增加边数改语义。

未来E0原HCG、E1封存标量、E2正确性修复、E3经Oracle验收的状态增强、E4单独融合/初始化；同标签/折/特征/训练规则，共同参数按语义对齐，记录新canonical和参数量。paper_kfold结果仍称CV validation；跨模板/独立测试仅旁路。本轮不运行这些实验。

**17.7 验证、环境修正、保护和停止点**

第一次全量372通过/18失败：17个为worktree缺失硬编码本地语法库，1个为原绝对路径资源绑定。复制已有库且SHA相同，路径测试在原目录执行，其实现/断言不变。保留第一次失败日志，不改旧资源或测试期望。

正式分区回归389通过（1项另跑）+原目录1通过；后续审计/context19通过，其中10项与主回归重复，因此399个不同测试通过。无最终失败或跳过；警告为依赖弃用。完整实际命令、返回码与日志在新审计JSON内；单元测试中的合成模型检查不是新Dataset A拟合。

原归档reporter先验收4任务完成/0待办。6217个既有保护文件前后摘要以及原目录新增文件检测由protected_before/after记录；仅两份文档追加是明确授权例外，保留旧前缀。修改版core diff check通过。未进行solc编译、安装升级、真实模型训练或新状态算法。

后续只有在正确性、Oracle、边来源/未知覆盖和新schema验收后，才应另建E2/E3训练计划。本轮结束于新图审计和设计报告，不能声称F1提高。

D2最终完整性：918项源码字节跨度与121项原输入SHA核验通过。D3交付9个真实函数候选Oracle和5个合成规格；独立人工批准和编译验证数均为0。


## 18. 2026-10-14：Stage E 通用状态 DDG 旁路原型与真实样本语义验收（修改 AI：Codex）

**18.1 本轮授权、目标及冻结边界**

本条接续第16节诊断、第17节v1.1修复/D3设计和后续Git归档说明。此前变化已记录，不改写其历史结果。本轮用户新附件明确授权E-A、E-B、E-C实施，E-D只规划；用户最新要求优先重入/访问控制，不要求本轮七类全量。设计规则仍面向通用源码语义，禁止按漏洞类别、标签、文件名或预测定制连边。

实现位于已有隔离工作树 /home/zhao/SmartContract/ge-sc-llm-ddg-v11，分支 ddg-v1.1-correctness，起始HEAD 93c9684302aa964e37ec8ff3342c9f2dafcd16ae。原工作树 /home/zhao/SmartContract/ge-sc-llm 起始HEAD 8c7a2fc8307fc920330d8401ad1405afb5dc81f5。本轮无提交/推送，不修改原标量DDG、HGT、tokenizer、训练器、作者标签、冻结K折/初始化/早停或E0/E1/E2图。

新增核心集中在 scripts/DFG/state/，新审计目录为隔离工作树的 scripts/DFG/experiments/audit/state_aware_ddg_prototype_v1/。两工作树只对已有training_changes及HANDOVER追加同一记录，旧正文按字节前缀保护。第一次模块写入曾因自动审查沿用旧D3“只设计”限制而被拒；核对本轮附件的实施授权后重新提交获准，拒绝时无写入，没有绕过审批。

**18.2 新增文件、接口和修改原因**

| 文件（相对scripts/DFG/） | 新增内容与原因 |
|---|---|
| state/__init__.py | state-aware-prototype-v1及STATE_DEF_USE，与原标量版本隔离 |
| state/models.py | DeclarationRef、StateLocation、StateEvent、StateFunctionIR、StateFact、StateAccessSummary、StateAnalysisResult；不改原FunctionIR |
| state/locations.py | sourceSHA/声明/作用域绑定，状态根、简单mapping键、EXACT/MAY/NO_ALIAS；不按同名匹配 |
| state/access.py | READ/WRITE、复合更新、环境读、调用配置、外部/未知调用HAVOC；模糊求值顺序整函数回退 |
| state/reaching_definitions.py | ENTRY_UNKNOWN、强弱更新、分支union、循环fixpoint、KILL、可达性及逐事实CFG witness |
| state/analyzer.py | 复用原CFGBuilder和SymbolTable，独立状态Side Table，函数回退不发布部分结果 |
| state/projection.py | 复用v1.1精确Projector，只物化EXACT位置事实，保护E2全部节点和旧关系 |
| state/model_adapter.py | 显式旁路保持STATE_DEF_USE正向；不改旧reflection或formal训练入口 |
| state/audit.py | 访问/调用顺序侧表，以及原两层CFG/CG/E2上下文之外增量统计 |
| state/tests/ | 5个测试文件，共56项；语义、投影、不变量、DGL/HGT和审计 |
| 新审计目录run_stage_e.py | 核验来源SHA、Oracle、7个真实文件及独立候选图，禁止覆盖旧attempt |
| 新审计目录oracle_review.py | 手写预期与observed输出分离，保留未独立批准状态 |

StateReadEvent/StateWriteEvent复用不可变StateEvent并以校验后的kind区分。所有新增位置、事件和未知来源仅为中间分析对象，不添加模型变量节点。

**18.3 实际语义范围及保守策略**

支持同合约可明确绑定的直接状态标量及简单mapping标量键/值。键证据限于有类型的范围内常量、同调用帧未遮蔽msg.sender、类型匹配且整函数未写入的值参数。不同根或不同常量键可证明不别名；不同参数名不证明键不同。重赋值参数/局部键/复杂键UNKNOWN，不用静态定义ID误判循环中运行时值不变。

状态位置是源码声明抽象，不是精确EVM slot。msg.sender、tx.origin、block.timestamp等单列环境读取。数组不作为mapping，参数owner不作为状态owner。当前所有继承/导入上下文均回退，modifier执行、数组、嵌套mapping、storage引用、assembly及跨函数/跨交易摘要未实现。

确定单一位置写入强覆盖；MAY位置弱更新。分支union和循环固定点沿原语义CFG计算，无传递闭包。无法投影的写入仍参与KILL。不支持函数保留原图和标量DDG，不提交不可信状态事实。

外部或未知调用使用HAVOC TOP；TOP包含旧值可能保留及其他来源，不宣称每个调用一定改状态。staticcall当前也保守TOP，属于精度限制。宽pragma不能确定require/assert内建可用性时按未知调用记录，不选取伪造编译版本。原B1终止调用绑定保护不变。.call.value(amount);独立配置不等于调用已发生。

STATE_DEF_USE只物化EXACT位置的may-reaching事实；MAY别名事实留侧表。EXACT不是所有路径必执行。CFG witness证明结构可达且无强覆盖阻断，不证明分支谓词真实可满足。STATE_ACCESS_ORDER与EXTERNAL_CALL_BEFORE_STATE_WRITE/UNKNOWN_CALL_BEFORE_STATE_WRITE仅侧表，CONTROL_DEPENDENCE未实现。

**18.4 Oracle核验、复审发现与修复**

原9个真实函数核验源码SHA、完整函数UTF-8跨度、合约/状态声明、AST和原HCG node_id；原5个合成规格加6个通用规格，共20个自动化预定子集行为检查：13完成分析，7按预先声明的限制回退。独立人工批准0、solc编译验证0；不将Tree-sitter解析等同合法Solidity认证。

合成Oracle共17条状态事实（16EXACT、1MAY），15条状态模型边（1条EXACT自身端点过滤）。原9个真实Oracle均无新增状态边。根目录ORACLE_EXPECTATIONS.json手写语义预期与observed字段分开，不从标签或预测生成Oracle。

复审发现新增状态emit处理递归遍历参数，可能重复读取并错误触发求值顺序回退；另外未知事件kind可能被静默视为空操作。新增同一组两项回归测试：修复前2 failed，改为只处理emit直接参数、拒绝未知kind后通过。测试SHA保持，未删除或放宽断言。记录见review_correction.json和review_regression_before.log。

最终源码审计重跑为results_attempt_002，旧results_attempt_001原样保留；两次均为源码/图审计，不是模型训练重试。

**18.5 真实样本覆盖与零增量的解释**

| 集合 | 文件 | 函数 | 完成子集 | 回退 | 状态READ/WRITE | 未知来源记录 | 具体状态事实/新状态边 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 重入 | 3 | 196 | 35 | 161 | 28/20 | 28 | 0/0 |
| 访问控制 | 4 | 119 | 28 | 91 | 6/3 | 6 | 0/0 |

文件为重入buggy_18/27/36.sol，以及访问控制mapping_write.sol、buggy_18/26.sol、arbitrary_location_write_simple.sol。只分析这些预选困难文件，不能解释为全语料覆盖。315函数共63完成子集、252回退；其中204与继承绑定有关（原B1与状态层均有保护），其他为版本、modifier、数组及非标量边界。

四个E3a_selected_contract/node.gpickle与对应E2的SHA逐字节相同。真实语义事实在投影前已为0，投影缺失端点0；因此本次零增量不是投影丢失引起的。真实新增canonical、两层上下文和条件参数增量全部0。

正确语义允许入口读余额→调用→清零没有函数内Def–Use；不能把清零反向连到之前读取来增加边。同时回退函数尚不能判断全部依赖，不能据此断言状态DDG对两个漏洞无效。侧表得到32条状态访问顺序、15条已确认外部调用到写入、15条未确认调用到写入；这些没有加入模型。

**18.6 HGT兼容性、原训练入口边界**

确认原sco_models/graph_utils.reflect_graph只保留DATA_DEF_USE方向，若直接送入STATE_DEF_USE会补反向。新model_adapter显式保留状态正向，基础关系反射与标量方向不变；原加载器/训练器没有改动。

合成图测试已验证新canonical注册、HGT前向和非零关系梯度；不只是存文件。未运行optimizer/正式训练/GPU。原formal入口尚未迁移，不能拿旧训练命令直接跑E3候选。每个新canonical在hidden128/heads8/layers2条件下8208参数的公式仅用于审计；本次真实增量0，不是新的完整模型实测。

**18.7 测试命令、结果与失败记录**

复用mando环境及已有TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64，PYTHONDONTWRITEBYTECODE=1，OMP_NUM_THREADS=2，MKL_NUM_THREADS=2。

隔离工作树：
```bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/state/tests
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/state/tests scripts/DFG/tests scripts/DFG/experiments/tests tests \
  -k 'not test_actual_prepared_inputs_form_exactly_thirty_paired_jobs'
```

第一条56 passed/4 warnings；第二条435 passed/1 deselected/31 warnings。原绝对资源测试在原工作树单独执行：
```bash
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/tests/test_formal_controller.py::test_actual_prepared_inputs_form_exactly_thirty_paired_jobs
```
1 passed/4 warnings。合计436个不同测试通过、0失败、0跳过；定向重跑不重复计数。警告来自现有distutils/NetworkX弃用，不进行依赖升级。

run_stage_e.py --output <全新目录>完成最终源码审计约267.16秒；完整命令及源码SHA在新审计目录。原只读report_stage_c.py重算4任务complete/0pending：第一次因预建输出目录触发拒绝覆盖，日志保留；改用全新archive_check_002后通过，未改报告器。

没有执行solc验证（无本轮已核准适配编译器）、独立人工Oracle批准、E2/E3训练、七类全量、旧训练入口迁移或新增反向关系。没有新F1。

**18.8 交付、资产保护及下一步**

完整报告入口：新审计目录README.md / IMPLEMENTATION_REPORT.md。位置语义、Oracle、alias/HAVOC、访问/投影CSV、增量CSV、INPUT/GRAPH_MANIFEST、REGRESSION_RESULTS与两类后续计划均已交付。accepted attempt为002。

protected_before/after保护原有12021项输入/源码/归档文件，授权例外仅两仓库四个文档追加，并核验原字节前缀；实际结束核验以protected_after为准。原HEAD、冻结图/标签/token/模型/plan/seal及v1.1旧审计不覆盖。

下一步先完成Oracle独立语义核验，再按证据处理版本/绑定与受限继承覆盖瓶颈，或独立验证已经出现的访问/调用顺序；权限guard的modifier/控制依赖另立项。只有真实信息增量、全语料不变量及正式加载器/初始化绑定验收通过，才考虑E2/E3新计划。本轮停止，不为了提高F1改标签、扩模型或启动60次训练。


**18.9 收尾资产审计范围补记**

首次结束扫描误将整个artifacts树都视为已建立起始SHA基线，因203个旧smoke路径未在protected_before中出现而触发requires_review；不是发现内容SHA变化。保留首次protected_after.json及其拒绝结果，不补造起始快照。

复核上一轮protect_assets.py及本轮清单后，最终按完整建立基线的两个formal目录、旧诊断目录及v1.1旧审计目录检查新增文件；扩大扫描的203个路径单列为起始清单外文件，不能给出其本轮前后字节一致性结论，也不将其冒称本轮新增。最终核验见protected_after_verified.json：12021项既有文件核验、四份授权文档前缀、冻结HEAD及规定保护目录均单独报告。本补记没有改变业务代码、图或任何测试断言。


## 19. 2026-10-14：Stage F 覆盖恢复与状态访问顺序验证（修改 AI：Codex）

**19.1 授权范围、实际版本与保护**

根据用户 Stage F 模板及允许调整的说明，本轮实施 F0/F1/F2/F3，
F4仅兼容性和入口设计，不启动正式训练，不以提高F1为目标放宽语义。

实际开发工作树 /home/zhao/SmartContract/ge-sc-llm-ddg-v11，
分支 ddg-v1.1-correctness，起始HEAD=08a4488c750362603d3359a5174ffdc0780c6adb；
原工作树 /home/zhao/SmartContract/ge-sc-llm，起始HEAD=916145e4f1f12bd18c565e809de5d8e1f7772d37。
本轮未提交/推送/reset/checkout，没有重写历史plan/seal。
此前Stage E归档后的HEAD与报告初始HEAD不同，以本轮protected_before实际记录为准。

新增核心 scripts/DFG/state/stage_f/；
新增审计 scripts/DFG/experiments/audit/state_aware_ddg_stage_f/。
下文路径相对此开发工作树。原工作树只追加本文件和HANDOVER，旧正文保留。
原scalar/v1.1/Stage E业务代码、E0/E1/E2、HGT、tokenizer、标签、折、
训练器、旧权重和归档记录不变。起始完整保护13,579项，包含此前未完整纳入的smoke目录；
最终逐项核验见新审计protected_after.json，而非只比较Git状态。

**19.2 新增文件与最小设计调整**

| 文件（state/stage_f/下） | 新增逻辑与理由 |
|---|---|
| __init__.py | 独立版本state-aware-ddg-stage-f-v1，显式正向关系集合 |
| versioning.py | 多pragma交集、语义版本区间、精确来源绑定的versions.csv；不任意挑选solc |
| frontend.py | 保留原始/兼容AST精确映射，用新版本证据初始化；不改源码规避解析 |
| binding.py | 同单元唯一单继承链、声明可见性/遮蔽/私有成员、内建与同名用户调用证据 |
| analyzer.py | 复用SymbolTable、CFGBuilder、状态事件和RD，独立作用域/调用适配；函数级回退 |
| relations.py | 独立状态访问次序、调用→写入、三事件模式及CFG witness复核 |
| projection.py | 精确AST→原HCG映射，缺失/同节点单列，证据索引，off与基础图不变量 |
| model_adapter.py | 保留四种增强关系正向，原CFG/CG反射规则不变；DGL/two-hop审计 |
| initialization.py | 沿用冻结语义初始化数值算法，仅扩展支持schema并独立版本记录 |
| compatibility.py | 复用原HGTLayer的合成CPU前向/反传/绑定/重载检查，无优化器 |
| tests/test_binding.py | 23项绑定/版本/副作用正反例 |
| tests/test_relations.py | 16项事件次序、投影、标签独立性及不变量检查 |
| tests/test_compatibility.py | 6项canonical、共同初始化、梯度、重载和漂移拒绝检查 |

新审计脚本common.py/corpus.py/compare_f1.py/project_f3.py负责冻结清单、
全语料前后比较、语义投影与8图生成；protect.py建立起始资产清单；
verify_delivery.py只读复核完整身份/摘要；projection_breakdown.py分解每关系的投影损失。
README、IMPLEMENTATION_REPORT、F0_SUMMARY、F1_BINDING_CHANGELOG、
ORACLE_SOURCE_REVIEW、F2_RELATION_SPEC/F2_LIMITATIONS、F3_E3_READINESS、
F4_MODEL_INTEGRATION及JSON/CSV/日志记录交付证据。

没有实现多继承C3、import解析、复杂覆盖、modifier或跨函数摘要。
接口/库基类、带构造参数、循环/不唯一基类、冲突状态声明仍回退；
不是删除原B1/state保护来恢复函数。
STATE_ACCESS_ORDER与CALL→WRITE不是STATE_DEF_USE，三事件模式仅留侧表。
UNKNOWN调用不冒充EXTERNAL_CALL，也不进入确认调用模型边。

**19.3 F0/F1全语料、版本证据与恢复量**

名单来自原prepared manifest及封存paper_kfold任务折，逐文件SHA核验。
合约级142重入/114访问控制；节点级71/57为各自子集。
共256来源路径、254种唯一源码SHA；不能跨任务把重复源码当独立样本。
完整函数比较6,552行=3,404+3,148，包含前后均失败的函数。

| 任务 | 总函数 | Stage E支持 | Stage F支持 | 恢复 | EXACT事实前/后 |
|---|---:|---:|---:|---:|---:|
| 重入/合约 | 3404 | 1042 | 1316 | 274 | 10/17 |
| 重入/节点 | 2045 | 670 | 899 | 229 | 5/8 |
| 访问控制/合约 | 3148 | 939 | 1299 | 360 | 12/29 |
| 访问控制/节点 | 1958 | 691 | 965 | 274 | 7/10 |

重入恢复来源：状态继承126、原B1继承79、多pragma69。
访问控制：状态继承268、B1继承2、多pragma90。
合约级READ/WRITE：重入878/658→1248/903，访问控制155/158→241/189。
按函数累计位置756→1041、226→316；不是全局唯一状态变量数。
MAY事实合约级最终7/8；UNKNOWN读取1231/213。旧事实丢失0，原支持函数新增回退0。

27个重入、16个访问控制源码能匹配已有SmartBugs版本记录。
CSV文件、记录行、来源路径和源码SHA均核验；这不是本轮solc编译结果。
其他源码保留pragma区间，多个pragma求交；宽区间不能证明builtin时仍UNKNOWN。
require(foo())保留foo副作用；send/transfer/call及未知调用不删HAVOC；
staticcall当前也采取保守全状态处理，不宣称完整只读摘要。

F0语法文本先写后读候选重入441/访问控制407函数。
候选不等于正确依赖。冻结Stage E在全语料已有22条EXACT事实，
因此原7困难文件零状态边不代表整个语料。
恢复后的原7文件仍63/315支持、状态EXACT事实0；不能声称难例已经解决。

**19.4 复审修复与保留失败证据**

发现已确认非内建用户函数revert()的revert_statement解析形式，
旧状态层只处理参数而漏HAVOC，可能错误保留跨调用的写入来源。
新test_nonbuiltin_revert_statement_is_opaque_effect_not_silent_pure先复现1 failed；
Stage F.extract增加绑定保护：NON_BUILTIN追加UNKNOWN_CALL HAVOC，
真内建终止及参数读取不变；缺绑定证据回退。旧Stage E源文件未覆盖。

修复后45项Stage F测试通过，全语料重新运行。
本批真实语料事实计数未变；不能因此忽略已复现的语义反例。
review_regression_before.log / review_before.json / review_tests_after.log /
review_correction.json完整保留。

首次F1比较少列121个前后均文件前端失败的函数，图/样本一直保留。
最终以F0全部函数身份补齐，F1_attempt_002/F3_attempt_002为接受版本，
F1/F3_attempt_001保留，不覆盖或删除首次输出。

**19.5 E3候选模型边与上下文增量**

E3a=原固定E2+STATE_DEF_USE；
E3b=E3a+STATE_ACCESS_ORDER+EXTERNAL_CALL_BEFORE_STATE_WRITE。
8图独立存放F3_attempt_002/*_candidate.gpickle，未覆盖E2。

| 任务 | E3a状态数据边 | E3b另加访问顺序 | E3b另加调用→写入 | E3a/E3b新增两层节点对 | E3a/E3b新增上下文目标 |
|---|---:|---:|---:|---:|---:|
| 重入/合约 | 6 | 847 | 547 | 1/1546 | 1/576 |
| 重入/节点 | 3 | 829 | 547 | 1/1545 | 1/575 |
| 访问控制/合约 | 11 | 33 | 0 | 17/17 | 12/12 |
| 访问控制/节点 | 4 | 16 | 0 | 1/1 | 1/1 |

两层节点对按实际适配图方向计算，不等于检测性能。
已有两跳可达仍可能增加关系语义；新可达也不保证F1提升。

所有原节点/ID/顺序/类型/标签/token/源码映射/CFG/CG/DATA_DEF_USE保留；
剥除新关系后8图均等于E2指纹，off也等于E2。
每条新边有源码SHA、函数、声明/事件和投影节点证据；同端点不同关系共存。

事实与边数差异：重入合约17条EXACT事实，11缺端点，6证据→6边；
重入节点8条，5缺端点，3边。访问控制合约29条，14缺端点，
15投影证据按相同端点去重→11边；访问控制节点10条，5缺端点，5证据→4边。
访问顺序另有同HCG节点事件合并损失；不靠最近行号猜测或新增节点补齐。

重入合约714条同位置READ→CALL→WRITE结构候选、84不同位置、
124未确认调用；不把这些重复可能很高的模式数当独立漏洞数。
访问控制有254已确认外部调用事件，但本子集没有确认调用后的状态写入边。
权限guard/modifier→敏感操作需要单独控制依赖规格，未偷偷加入本轮DDG。

**19.6 Oracle、覆盖限制与HGT兼容性**

原20项Oracle保留源SHA/AST身份重查，13子集完成、7回退；
Codex逐项源码复核另记ORACLE_SOURCE_REVIEW。
独立人工批准0、编译验证0。新增10类顺序正反例含同位置/不同位置/MAY、
互斥分支、不可达后继、call配置、参数状态读、未知调用、无调用及HAVOC。
部分同名builtin样例仅解析器健壮性，不等同目标Solidity合法程序。

R buggy_18仍13/69支持：宽pragma/继承等阻断保留，新访问顺序候选8条，
不是关键余额路径已经可分析。AC mapping_write实际是数组；onlyOwner仍回退。
EXACT表示位置/别名精度，不表示所有路径必然来源于该写入。
CFG结构可达不是SMT路径可满足，也不证明交易成功或漏洞可利用。

原HGT核心未改。新adapter保留四种增强关系正向；8真实图DGL边数和schema检查通过。
新initialization旁路扩展schema允许集合，数值算法沿用旧语义初始化；
DATA_DEF_USE原案例逐张量相同。独立版本state-forward-semantic-paired-v1。
没有使用已训练权重初始化E3。

CPU合成HGT（三种新关系）relation_msg梯度L1分别15.386905、19.373989、3.987084，
checkpoint重载输出逐元素相同；optimizer_steps=0。
F4_initial_synthetic.pt是未训练初始化状态，不是best/last。
8维为合成夹具，真实512维tokenizer输入未改变。
hidden128/heads8/layers2每新canonical增加8208参数仅公式，不是全模型实测。

**19.7 测试命令、结果与未执行事项**

沿用mando环境和原TREE_SITTER_LIB_DIR；PYTHONDONTWRITEBYTECODE=1，
OMP_NUM_THREADS=2、MKL_NUM_THREADS=2，没有依赖升级。
在开发工作树：
```bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/state/stage_f/tests
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/state scripts/DFG/tests scripts/DFG/experiments/tests tests \
  -k 'not test_actual_prepared_inputs_form_exactly_thirty_paired_jobs'
python -B scripts/DFG/experiments/audit/state_aware_ddg_stage_f/verify_delivery.py --validate-only
```
在原工作树：
```bash
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/tests/test_formal_controller.py::test_actual_prepared_inputs_form_exactly_thirty_paired_jobs
```
45项定向通过；全量480 passed/1 deselected/31 warnings；原资源测试1 passed/4 warnings。
合计481个不同测试通过、0失败、0跳过；定向不重复计数。
警告来自已有distutils及NetworkX弃用。单独测试是原绝对资源路径要求，不是删除测试。
verify_delivery验证输入/代码SHA、6552函数身份、8图SHA和已记录不变量。

RTX3050Laptop4096MiB资源快照空闲2913MiB；未测完整配对模型显存峰值。
未执行新solc、GPU模型短跑、优化器、正式训练、其他五类或多seed。
没有新F1，不能认定DDG有效/无效。未对真实绑定误差率作独立ground-truth认证。

**19.8 下一步门槛与本轮停止点**

F0/F1/F2/F3已生成可复核结果，F4只完成合成兼容性与接口清单。
正式入口未迁移，不能直接用旧formal命令读取STATE_DEF_USE以免错误反射。
后续需新版本输入/关系/初始化/checkpoint绑定，真实全图前向反向显存预检，
独立Oracle审核，以及针对重入顺序模板重复、访问控制guard语义的分开审计。
通过后再预先固定小折E2/E3a/E3b对照，完整K折另行决定。
本轮不调整标签、不换折、不删样本、不扩展反向边或自动训练。

## 20. 2026-10-14：Stage G 真实 E2/E3a/E3b 接入及固定单折试验（修改 AI：Codex）

**20.1 本轮授权、版本与执行边界**

接续第17节正确性修复、第18节状态原型、第19节Stage F及其Git归档说明；历史正文和封存结果不改写。本轮用户Stage G附件授权有限语义审核、实际模型接入、四任务三变体各3轮短检查，以及通过门槛后的12次正式fold0拟合。完整K折另有78次，不在本轮授权范围内。

实际开发工作树 /home/zhao/SmartContract/ge-sc-llm-ddg-v11，分支 ddg-v1.1-correctness，HEAD c311c93927138f3fab3aab94b9afa6e63c90269e；原工作树 /home/zhao/SmartContract/ge-sc-llm，HEAD 16bcf2d0a786b5448c1ed9e133922e1e82611167。本轮不pull、reset、commit或push。原工作树只追加两份文档；已有其他未跟踪内容保留。

新增入口 scripts/DFG/experiments/e23_pilot/；独立输出 scripts/DFG/experiments/artifacts/paper_kfold/e23_pilot_v1/。不改scalar/Stage F构图、HGT、tokenizer、标签、冻结K折、原训练脚本、旧图或旧权重。初始资产保护清单13710项，含原历史实验与审计树；最终结果后另做逐项核验。

E2=作者固定HCG/标签、512维CodeT5p-770m tokenizer IDs及v1.1修复标量DDG；E3a只在E2加Stage F已生成的STATE_DEF_USE；E3b再加STATE_ACCESS_ORDER、EXTERNAL_CALL_BEFORE_STATE_WRITE。顺序边不是Def–Use或漏洞证明。本轮不重新运行语义构图，不新增反向关系。

**20.2 新增文件、关键实现及调整理由**

| 新文件（相对e23_pilot/） | 实现及原因 |
|---|---|
| __init__.py | 实验e23-paper-pilot-v1，接入版本、三变体名单，与paper协议版本分开 |
| model.py | 两个原分类器的inside_token构造旁路，显式使用Stage F正向适配；继承原forward/HGTLayer，不重写模型计算；深查schema/端点/行顺序/特征/标签；CPU共同初始化与设备移动 |
| runtime.py | 复用原文件监督/节点mask；只替换图schema反射策略及扩展四关系梯度审计，区分无train支持与接入异常 |
| checkpoint.py | 原保存/重载函数的相同code object，局部绑定处理器扩展新协议/关系/初始化身份；不修改原模块全局变量 |
| training.py | 复用原fit_variant同一code object，替换本入口checkpoint/梯度处理器；增加单模型资源采样、参数更新、时间和停止原因记录，不改变优化器/损失/调度/选模 |
| inputs.py | 从D1/F3及原任务manifest取得冻结图、标签、source/tokenizer SHA、fold0与实际配置；逐节点不变量、基础多重边/特征/文件划分验证 |
| prepare.py | CPU先完成四组三变体全部未训练初值封存，验证真实E2与原分类器前向逐位一致；记录监督行、schema及支持量 |
| worker.py | 每进程一个GPU模型，加载本任务未训练state，实测并核对环境；运行后记录输入绑定、产物SHA和完成收据 |
| control.py | 新plan/seal、代码/输入漂移检查、严格12任务顺序、所有smoke门槛、fcntl互斥、成功复用及显式失败重试 |
| report.py | 独立从冻结E2/标签恢复验证人口、重算混淆矩阵/F1、核验最低loss best及产物；best/last及三种对比分开输出 |
| tests/test_model.py | 22项模型前向/方向/canonical/共同初值/漂移检查 |
| tests/test_training_integration.py | 18项原循环数值对齐、mask监督、梯度、early-stop/checkpoint绑定检查 |
| tests/test_control.py | 18项互斥、目录缺失的失败sidecar、明确重试、成功复用/冲突拒绝检查 |
| tests/test_report.py | 26项统计、伪造/错位预测、best选择、smoke混入、重复成功等拒绝检查 |
| tests/test_inputs.py | 20项含四任务真实输入与标签/类型/特征/划分/跨文件边/哈希负向检查 |
| review/ | 20 Oracle与33条边证据的有限复核脚本、6项审核器测试、源码片段、SHA及review_manifest |
| README.md | 实际可用入口、冻结规则、恢复和限制 |

旧loader会把新关系反射、旧checkpoint只接受原初始化版本，故采用局部旁路；未放宽旧入口或把E3数据直接交给旧loader。训练循环使用FunctionType复制原函数code object并替换局部globals字典；测试确认原globals未被猴子补丁修改。真实E2四任务初始权重、特征、端点、节点行与eval前向均逐位等价。

三变体初始化采用未训练E2→E3a→E3b链条。分别独立E2→E3a与E2→E3b会因新关系参数bank形状不同，不能保证共享STATE_DEF_USE切片相同；链条确保E2共有参数及E3a/E3b共有状态参数按语义一致。数值pair算法沿用Stage F，三变体组织单独记录state-forward-semantic-paired-v1/triple-chain-v1；不是使用训练权重暖启动。

controller预审修复“worker建目录前失败只留下sidecar、下次未识别”的执行记录问题：按attempt_NNN的目录和sidecar归并，编号取最大已有值+1；默认拒绝重试，显式指定任务/变体才允许新attempt。使用不删除的fcntl锁文件避免双进程运行。停止原因额外记录patience与epoch上限是否同时触发，只改记录不改停止规则。

**20.3 冻结任务、图与训练设置**

| 任务 | 文件数 | 节点 | E2边 | E3a增加STATE | E3b再加ORDER/CALL |
|---|---:|---:|---:|---:|---:|
| 重入合约 | 142 | 18312 | 22828 | 6 | 847/547 |
| 访问控制合约 | 114 | 13432 | 19570 | 11 | 33/0 |
| 重入节点 | 71 | 12036 | 13604 | 3 | 829/547 |
| 访问控制节点 | 57 | 7710 | 11676 | 4 | 16/0 |

四任务验证人口分别29文件(15正)、23文件(11正)、1346节点(855正)、600节点(282正)。节点预测按原HCG节点计分，不是去重源码行F1。作者节点标签与对应图级JSON全部冻结，不混narrow或公共CSV重建标签。

主协议保持paper_kfold/ddg-paper-kfold-v1，完整固定任务图前向；train监督更新，val loss选best/早停，同val评分，结果明确为CV validation。原5/10折清单仅选预先指定fold0，不重新划分或挑折。seed1，构造seed合约11000/节点10000，pair+77，每变体fit前重置+1000000。

hidden128、layers2、heads8、dropout0.2、use_norm、inside_token不变。合约initial/max LR=0.0005/0.01、weight_decay=5e-6；节点0.0002/0.005、weight_decay=0。Adam、unweighted CE、50步OneCycle、cycle_momentum=true、final_div_factor=1不变。patience7/delta0.001；best仍严格最小val loss，delta只影响patience参考，不改按F1选模。last独立辅助。

smoke最大3epoch但调度仍50步；full最大50。每个smoke/full从同一未训练权重独立开始，不用smoke最后权重继续训练。已注册但train未出现关系允许预测并审计，错误字典/未注册/输入不一致仍拒绝；评分不创建参数，E2没有空状态关系占位。

**20.4 有限语义复核与覆盖解释**

新review复核全部17条合约图STATE_DEF_USE，以及seed1分层选择8条STATE_ACCESS_ORDER、8条CALL→WRITE（分别8函数/模板，含3/5个分支案例），并检查20个已冻结Oracle来源SHA和具体正反例断言。没有确认新的语义阻断。17条状态边中12条在构造函数，另外5条在访问控制getCurrentTokenPrice；不能把这些边数解释成余额/权限主路径已充分覆盖。

独立人工批准0，solc编译验证0；已有Oracle和新增审查仍为Codex静态/测试证据，非完整语言正确性认证。未安装/执行新solc。通用pickle读取审查被自动审批拒绝后，改用既有JSON事件/CFG证据完成审核；实际图读取沿用白名单RestrictedReader，没有绕过拒绝执行通用pickle.load。

| 任务 | STATE train/val | ORDER train/val | CALL→WRITE train/val |
|---|---:|---:|---:|
| 重入合约 | 5/1 | 675/172 | 427/120 |
| 访问控制合约 | 11/0 | 29/4 | 0/0 |
| 重入节点 | 1/2 | 711/118 | 457/90 |
| 访问控制节点 | 4/0 | 12/4 | 0/0 |

访问控制的val均没有STATE_DEF_USE；定价函数5条状态边全在合约train，其文件不属于节点任务。覆盖旁表coverage_note.json/md包含直接目标、涉及文件、val名单和函数归属。

原HGT是关系内sum、跨canonical relation mean；本地DGL汇总未按每节点非零入度过滤关系输出。新增关系可能同时改变共享参数训练和同目标类型的聚合分量。因此“val没有直接新增边”不能推出logits一定不变，成绩变化也不能全部归因于状态语义。没有改变HGT来消除这个结构混杂因素。

**20.5 原归档、单元/集成回归及真实短检查**

旧Stage C只读reporter验收4任务complete、0pending，30配对折完整；0失败/重试，39运行源码摘要和旧state保持不变。结果在新输出archive_check_001/，旧归档不修改。

本轮累计591个不同测试通过、0失败、0跳过：原开发目录480、原绝对路径资源测试1、新入口核心90、新输入20。原16项关系测试包含在480中，重复定向执行不重复计数。警告仅既有DGL/TensorBoard distutils与NetworkX弃用；实际命令、日志、返回码在integration_tests.json及引用记录。

开发目录测试：
```bash
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/state scripts/DFG/tests scripts/DFG/experiments/tests tests \
  -k 'not test_actual_prepared_inputs_form_exactly_thirty_paired_jobs'
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/e23_pilot \
  --ignore=scripts/DFG/experiments/e23_pilot/tests/test_inputs.py
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/e23_pilot/tests/test_inputs.py -k real_frozen
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/e23_pilot/tests/test_inputs.py -k 'not real_frozen'
```
原工作树另运行test_formal_controller.py::test_actual_prepared_inputs_form_exactly_thirty_paired_jobs。使用已有mando/语法库与PYTHONDONTWRITEBYTECODE=1、OMP/MKL线程2，无依赖升级。

12次三轮smoke全部attempt_001通过，0失败/重试，控制器monotonic1332.464秒。best/last重载logits逐位相同，schema、输入、预测、初始化和50步调度逐项核验。有训练支持的三种新增关系均实际产生非零消息梯度；训练未见canonical的零梯度正常记录，不删关系。

smoke最高峰值为重入合约E3b：allocated约2.646GiB、reserved约2.811GiB。4GiB整卡资源余量窄，某次最低只剩17MiB；用户已确认关闭或没有其他GPU程序。继续单模型串行，实际OOM或错误即停止，不自动切CPU/缩图/调参。纯资源耗时含校验/保存/重载，不作模型纯复杂度结论。

**20.6 恢复规则与当前运行状态**

本条写入时12次正式fold0训练刚启动，不能把smoke F1或运行中任务写成正式完成。正式顺序：重入合约E2/E3a/E3b→访问控制合约→重入节点→访问控制节点。主日志formal_controller.log，逐模型日志在runs/<task>/fold_0/<variant>/attempt_001.log。

plan/seal绑定本轮HEAD、全部运行源码、图/特征/标签/划分、初始化、配置、schema与评估角色。成功结果校验后复用；失败保留所有产物、reason和attempt，诊断后才显式重试，非epoch续训。没有结果下降删折、换seed、挑best F1或以last替主结果。实际正式结果、完整性及最终旧资产保护在后续20.7补记。

可运行命令见e23_pilot/README.md；当前已prepare/seal/smoke成功并正在control run，不应重复启动或重写初始化/计划。四任务只报告各自fold0，不平均不同任务、不估计单折std，不声称独立测试或七类有效。


**20.7 正式12次完成及主/辅助结果（2026-10-14，Codex）**

本条为20.6“运行中”的最终补记。四任务固定fold0×E2/E3a/E3b全部完成，正式控制器returncode=0，全部attempt_001，0失败/重试；verify返回smoke=12/full=12，summarize独立重算通过。无源码/算法/数据数值规则变化。

| 任务 | 变体 | Buggy-F1 | Macro-F1 | Precision | Recall |
|---|---|---:|---:|---:|---:|
| 重入合约 | E2 | 88.8889 | 89.6057 | 100.0000 | 80.0000 |
| 重入合约 | E3a | 88.8889 | 89.6057 | 100.0000 | 80.0000 |
| 重入合约 | E3b | 88.8889 | 89.6057 | 100.0000 | 80.0000 |
| 访问控制合约 | E2 | 90.0000 | 91.1538 | 100.0000 | 81.8182 |
| 访问控制合约 | E3a | 90.0000 | 91.1538 | 100.0000 | 81.8182 |
| 访问控制合约 | E3b | 90.0000 | 91.1538 | 100.0000 | 81.8182 |
| 重入节点 | E2 | 99.7071 | 99.5997 | 99.8826 | 99.5322 |
| 重入节点 | E3a | 99.6487 | 99.5195 | 99.7655 | 99.5322 |
| 重入节点 | E3b | 99.6491 | 99.5191 | 99.6491 | 99.6491 |
| 访问控制节点 | E2 | 99.2883 | 99.3306 | 99.6429 | 98.9362 |
| 访问控制节点 | E3a | 99.4652 | 99.4979 | 100.0000 | 98.9362 |
| 访问控制节点 | E3b | 99.4652 | 99.4979 | 100.0000 | 98.9362 |

| 任务 | 比较 | Buggy-F1差值（百分点） | Macro-F1差值（百分点） |
|---|---|---:|---:|
| 重入合约 | E3a-E2 | +0.000000 | +0.000000 |
| 重入合约 | E3b-E2 | +0.000000 | +0.000000 |
| 重入合约 | E3b-E3a | +0.000000 | +0.000000 |
| 访问控制合约 | E3a-E2 | +0.000000 | +0.000000 |
| 访问控制合约 | E3b-E2 | +0.000000 | +0.000000 |
| 访问控制合约 | E3b-E3a | +0.000000 | +0.000000 |
| 重入节点 | E3a-E2 | -0.058377 | -0.080259 |
| 重入节点 | E3b-E2 | -0.057966 | -0.080675 |
| 重入节点 | E3b-E3a | +0.000411 | -0.000416 |
| 访问控制节点 | E3a-E2 | +0.176984 | +0.167230 |
| 访问控制节点 | E3b-E2 | +0.176984 | +0.167230 |
| 访问控制节点 | E3b-E3a | +0.000000 | +0.000000 |

Last独立辅助（BF/MF）：

| 任务 | E2 last BF/MF | E3a last BF/MF | E3b last BF/MF |
|---|---:|---:|---:|
| 重入合约 | 88.8889 / 89.6057 | 88.8889 / 89.6057 | 88.8889 / 89.6057 |
| 访问控制合约 | 86.9565 / 86.9565 | 86.9565 / 86.9565 | 86.9565 / 86.9565 |
| 重入节点 | 99.7071 / 99.5997 | 99.6487 / 99.5195 | 99.6487 / 99.5195 |
| 访问控制节点 | 99.4652 / 99.4979 | 98.5866 / 98.6624 | 96.7185 / 96.8294 |

**20.8 分类变化、原因解释及限制**

两个合约任务三个变体的类别预测完全相同，概率有变化。重入仍漏报modifier_reentrancy.sol、reentrancy_simple.sol、simple_dao.sol；访问控制仍漏报parity_wallet_bug_2.sol、phishable.sol。

重入节点：E3a相对E2新增buggy_40.sol节点10732的误报；E3b相对E2修复buggy_47.sol节点9326的漏报，但新增buggy_40.sol:10732和buggy_28.sol:17439两个误报。故不是“完全没有改变分类”，也不是总体改善。

访问控制节点：E3a/E3b相对E2都只纠正mapping_write.sol节点12964的一个误报，未纠正其余三个漏报。两个增强的best分类完全相同。该任务验证图没有STATE_DEF_USE，不能把这个修复归因为该验证节点获得了状态Def–Use边。

目前没有稳定明显收益的证据，但不能因此证明状态依赖对这两类漏洞无效：
1. E2节点级已只有重入5个、访问控制4个错误，指标有明显天花板；不足一个百分点的差异必须结合错误数解释。
2. 状态Def–Use只增加少数构造器/定价关系，未充分覆盖漏洞关键余额或权限检查路径；访问控制没有CALL→WRITE。
3. 模型确实读到新增canonical关系并更新关系参数，不是“仅把边存入文件”。有训练支持的增强关系有非零有限梯度；训练未见的注册canonical关系单独记录，零梯度不作为删折依据。
4. 原HGT跨canonical relation做mean。新增关系可能改变聚合分量及共享参数训练，即使某验证文件没有直接新增边，其logits也可变化。当前对照不能把全部分数变化归为依赖语义贡献。
5. 同一验证集用于早停、选模、评分，且只有一个fold/seed；无折间方差、显著性或独立测试结论。文件级划分本身也没有消除既有模板相似性，本轮不改既定协议。
6. last的访问控制节点结果下降，显示训练轨迹/选模影响明显；不能挑选不同checkpoint替换主结果。

支持量、梯度、参数更新和全部概率变化详见summary.csv、error_changes.csv、coverage_note与各result.json。关系支持是结构计数，不是语义有效性或因果贡献证明。


**20.9 最终验证、资源及旧资产保护**


591个不同测试通过，0失败、0跳过：原开发目录480，原工作树绝对资源测试1，新入口核心90，新输入20。选择性deselect的资源测试已在正确原目录补跑；16个关系回归包含在480中不重复计数。警告为既有DGL/TensorBoard distutils及NetworkX弃用，未升级依赖。

12次smoke和12次full均attempt_001成功，无训练失败、OOM、数值错误或重试。所有best/last checkpoint重载输出逐位一致。独立复算24组指标/混淆矩阵、严格min选模及早停；180个正式收据产物SHA一致。12对smoke/full初值SHA、fit seed及50步调度一致，前三条完整历史逐值一致，证明本次正式训练没有沿用smoke已训练状态；不据此宣称所有GPU运行必然位确定。

旧Stage C的30配对折只读验收通过。protected_before/after核对13710项：13706文件完全未变，4授权文档仅追加；6个完整旧目录无增删、两个HEAD不变。最后文档追加另有documentation_update_phase2.json记录原字节前缀和SHA。

测试实际命令及日志在integration_tests.json；执行命令/返回码在smoke_execution.json、formal_execution.json、final_validation_execution.json。输入、划分、初值、schema、前向范围、评分角色、配置与checkpoint均绑定；未在评分时临时造参数。

正式控制器耗时 2211.445 秒（36.86分钟），包含输入校验、模型拟合、保存及重载；smoke控制器耗时 1332.464 秒。不能将不同停止轮数的耗时当作纯算法速度比较。所有正式模型按patience触发停止，未修改50轮上限。

| 任务 | 变体 | best/last轮（1起始） | 参数量 | 拟合/验收秒 | 峰值allocated/reserved GiB | 整卡最小空闲MiB |
|---|---|---:|---:|---:|---:|---:|
| 重入合约 | E2 | 7/14 | 4641874 | 157.71 | 2.366 / 2.584 | 40 |
| 重入合约 | E3a | 7/14 | 4650082 | 155.97 | 2.409 / 2.566 | 42 |
| 重入合约 | E3b | 7/14 | 4715746 | 159.67 | 2.646 / 2.811 | 36 |
| 访问控制合约 | E2 | 8/15 | 4641874 | 122.61 | 1.775 / 1.918 | 132 |
| 访问控制合约 | E3a | 8/15 | 4658290 | 125.21 | 1.837 / 1.984 | 67 |
| 访问控制合约 | E3b | 8/15 | 4715746 | 126.69 | 1.968 / 2.062 | 40 |
| 重入节点 | E2 | 40/40 | 4485922 | 294.01 | 1.531 / 1.660 | 417 |
| 重入节点 | E3a | 31/31 | 4494130 | 220.29 | 1.560 / 1.695 | 396 |
| 重入节点 | E3b | 25/32 | 4559794 | 214.80 | 1.720 / 1.861 | 203 |
| 访问控制节点 | E2 | 21/28 | 4559794 | 116.68 | 1.062 / 1.148 | 932 |
| 访问控制节点 | E3a | 13/20 | 4568002 | 95.42 | 1.087 / 1.168 | 912 |
| 访问控制节点 | E3b | 13/20 | 4592626 | 95.44 | 1.125 / 1.225 | 848 |

**20.10 最终文档、产物与未执行事项**

 后续78次与停止位置

本批已完成12次，不自动运行剩余78次。计算入口及本批资源/重载验证已通过，技术上可以据此准备其余26个配对折×3模型；但**当前control的封存计划只允许四任务fold0的12次**，不能声称再次执行现有run就会运行78次。下一批需要独立输出/计划，引用相同冻结折，逐折封存三变体初值、schema和支持审计；原计划/收据保持不变。

4GiB资源余量曾很窄，后续仍需单模型串行和逐折预检，真实OOM停止，不自动改图或超参数。是否投入完整K折，应结合这轮覆盖稀疏和有限错误变化决定；本轮没有提高支持率、添加modifier/控制依赖或改变模型来追分。旧E0/E1仅是历史参考，不与这次E2/E3a/E3b冒称严格配对。

**产物与实际命令**

主要输出位于 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/e23_pilot_v1/`：
plan.json/seal、input_manifest.json、initialization、smoke、runs、summary.csv、last_summary.csv、paired_deltas.csv、error_changes.csv、report.json/md、fresh_initial_replay_audit、coverage_note及protected_after。
完整文件改动及过程原因另追加至两工作树的training_changes第20节和HANDOVER（Codex）。

只核验和查看当前已完成结果：
```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONPATH="$PWD"
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m scripts.DFG.experiments.e23_pilot.control verify
python -B -m scripts.DFG.experiments.e23_pilot.control summarize
```

这两个入口已实际执行成功。seal绑定当前HEAD和源码；后续若归档提交，旧计划拒绝HEAD漂移是预期行为，不能改旧seal适配。运行前后均未安装依赖、未改源码图/标签/折、未执行新编译器、未开启全K折。

## 21. Stage H1：E2/E3b 完整交叉验证独立批次（2026-10-14，Codex）

**21.1 授权范围、版本核验及最小接入**

本条接续第20节与 Stage G Git archive follow-up，不改写旧实验记录。用户授权完成两个漏洞、两种粒度的 E2/E3b 全部固定折，保留 E3a 初值与 H2 计划，H1结束后停止。本条写入时尚未启动 H1 GPU 正式拟合；完成结果另补21.7。

开发工作树 ge-sc-llm-ddg-v11，HEAD 44e7337bb7b47738bc49a947ed5625809f7f006a；原工作树 ge-sc-llm HEAD 7fce3dde322f4a165c4b5ccff89d3839befdf7a6。GitHub ddg-v1.1-correctness 同为44e7337，IMPLEMENTATION_REPORT.md内容与本地一致。Stage G训练HEAD为c311c93927138f3fab3aab94b9afa6e63c90269e；其75份已封存运行源码摘要与当前完全一致。后继提交为归档/只读验收，不能仅因HEAD不同重训，也不能绕过源码和输入检查。未pull/reset/迁移/修改旧seal。

新增逻辑仅 scripts/DFG/experiments/e23_cv/，产物仅 artifacts/paper_kfold/stage_h1_v1/。采用与 e23_pilot 同级的旁路目录，避免原runtime_hashes递归扫描改变旧Stage G源码清单。原DDG/state算法、HGT、tokenizer、图/标签/特征、折、原训练代码均不改。两工作树已有训练变化文档与HANDOVER只追加。起始protected_before.json保护14253文件和7个完整旧目录。

**21.2 新增文件与修改原因**

- __init__.py：H1批次版本及允许变体。
- prepare.py：读取旧冻结折，按原seed公式创建30组三变体未训练链；fold0逐一核验与Stage G初始张量、监督mask及关系支持一致，记录复用收据。其余26折保留E2/E3a/E3b全部初始状态。
- control.py：新plan/seal、52个新拟合和8个复用结果、单worker串行执行、任务完整性门禁；H2另存30项固定计划且execution_authorized=false。旧控制器不修改。
- worker.py：沿用Stage G worker，仅增加fold/batch身份、选择对应封存初值、拒绝E3a/smoke/fold0新训练，以及CUDA前已有compute进程检查；make_model、Supervision、fit、checkpoint仍调用Stage G原对象。WORKER_PROVENANCE.json记录原worker SHA和接入差异。
- report.py：复用原逐模型验收，新增逐折/等权均值/样本标准差、配对差值、混淆矩阵、pooled OOF、错误/概率变化，以及单列旧E0/E1历史基线。
- tests/test_h1.py：矩阵完整性、种子、真实全部冻结折、禁止H2/重训fold0、无数值训练替换、失败停止/显式重试、统计口径与身份错误测试。
- README.md：可运行命令、恢复语义和输出说明。H2_EXECUTION_PLAN.md说明后续审批范围与完整消融要求。

这是调度和统计接入；没有为了改善指标新增边、类型或模型参数结构。允许变体本身原本已有的关系参数保持 Stage G 原实现。

**21.3 固定矩阵、初始化与评分**

完整三变体矩阵为2×(5+10)×3=90次拟合，非论文指定总训练次数。Stage G已12次；H1新增E2/E3b各26=52次，8个fold0复用，得到60结果；H2剩余E3a26次本轮不运行。四任务顺序为重入合约、访问控制合约、重入节点、访问控制节点。每折E2后E3b，一个worker释放后再启动另一个。

seed1固定；沿用 base=10000+fold+(合约1000，否则0)、pair=base+77、fit=base+1000000。这属于既定每折随机状态，不是新增seed重复实验。fresh E2→fresh E3a→fresh E3b全部未优化；共同节点类型/canonical关系语义对齐，STATE_DEF_USE在E3a/E3b相同；新关系独立可复现。正式拟合前恢复固定fit随机状态，不加载smoke已训练权重。

paper_kfold、完整固定图前向、节点mask/合约文件监督，原学习率调度、patience7、delta0.001、50轮上限不变；strict min val loss选best，last单独保存报告。所有主结果CV validation，同val选模/评分，不称独立测试；节点仍HCG节点口径。pooled OOF与等权折均值分开，也不能变成独立测试。

**21.4 验收、恢复与资源规则**

独立plan/seal绑定当前HEAD/运行源码、图/标签/特征/折、初始化、schema/关系方向/逐折支持、配置/前向范围/评分角色和旧收据。成功核验后复用；失败保存旧attempt/日志，停止并排查后才显式重试单个模型，不是epoch断点续训。不改变结果较差的fold。全局及批次互斥锁，并检查GPU现存compute进程；不自动OOM重试、缩图、调参、切CPU。资源沿用Stage G逐fit峰值allocated/reserved、整卡最小空闲、耗时与梯度记录。

训练前607个不同测试通过：开发原回归480、旧入口110、新H1 16、原工作树绝对资源1；0失败/0跳过。开发套件deselect的一项已在原目录补跑，不漏测。警告仍为DGL/TensorBoard distutils、NetworkX弃用；无依赖升级。全部命令和日志在新批次integration_tests.json及original_resource_test.json。

**21.5 与原基线的比较口径**

原Stage C E0=作者HCG，E1=最初标量DDG；新E2=修复v1.1标量DDG，E3b=再加状态Def–Use及两类顺序关系。对旧E0/E1验收30配对折的收据、预测与配置，单独报告同折历史基线比较。旧初始化算法和本批三变体链不同，未证明跨批共同参数完全相同，所以不能把历史E0/E1与新E2/E3b混称同一次严格配对消融。新E2/E3b内部才是本批受控配对。

**21.6 未执行事项**

本条时正在CPU初始化/复用审计，正式52次尚未开始。没有H2新训练、更多seed、七类全量、nested/narrow、新关系或新语义修复，也未提交推送。本轮结束应补充实际完成数/失败记录、H1_RESULT_REPORT.md、旧资产保护与H2是否值得开展的判断，不能用fold0代替全折结论。

**21.7 H1 实际完成与冻结核验（2026-10-14，Codex）**

接续21.6的启动前记录：现已完成授权的52次新增拟合，并复用Stage G的8个E2/E3b fold0结果，总计60个正式结果。四任务按重入合约、访问控制合约、重入节点、访问控制节点顺序串行完成；每任务验收通过才进入下一任务。全部新增均attempt_001，0失败、0重试、0 OOM、0非有限loss中止。没有为挑分重训、改变seed/折、删文件/边、缩图或切CPU。H2新增E3a拟合为0，仅保留26次后续拟合计划及全部30折E3a未训练初值。

control verify最终返回new_complete=52、stage_g_reused=8、total_complete=expected_total=60。独立summarize复算全部120组best/last指标及混淆矩阵、原E0/E1历史结果、OOF覆盖和身份；返回码均0。60个模型的best/last重载输出一致，未在训练/评分时创建参数。源代码仍82项封存摘要，固定资产684项；DDG/state、HGT、tokenizer、标签、图、划分、初始化算法及数值训练规则未修改。

Stage G的75份原运行源码与当前完全一致，12个fold0初始张量重建核验通过；本轮只使用其中E2/E3b的8个正式结果，E3a的4个留给H2。所有旧seal与结果保持原样；GitHub核验结果、两工作树HEAD和运行绑定证据均已保存。没有提交或推送。

**21.8 主结果与辅助结果**

主结果仍为strict minimum val loss的best，CV validation；节点仍为HCG节点口径。数值为等权折均值，差值单位为百分点，SD为样本标准差：

| 任务 | E2 BF1 / MF1 | E3b BF1 / MF1 | 配对ΔBF1 ± SD | BF1提升/持平/下降 |
|---|---:|---:|---:|---:|
| 重入合约5折 | 95.0140 / 95.0549 | 95.0140 / 95.0549 | 0.0000 ± 0.0000 | 0/5/0 |
| 访问控制合约5折 | 91.5628 / 92.0657 | 91.5628 / 92.0657 | 0.0000 ± 0.0000 | 0/5/0 |
| 重入节点10折 | 96.0772 / 95.9052 | 96.2460 / 96.0506 | +0.1688 ± 0.2766 | 6/1/3 |
| 访问控制节点10折 | 96.1983 / 96.9983 | 96.3495 / 97.1228 | +0.1512 ± 0.3606 | 4/4/2 |

E2/E3b的BF1折间SD依次为重入合约4.1596/4.1596、访问控制合约2.1697/2.1697、重入节点10.0686/10.0700、访问控制节点6.3884/6.1694。不是多数折都99就可以宣称整体99；困难折使完整结果回落且方差较大。

Last单列，不覆盖主结果：重入合约BF/MF 90.2265/90.1307→90.2265/90.1307；访问控制合约86.9065/86.8342→86.1731/85.9480；重入节点96.8949/97.0180→96.8440/97.0590；访问控制节点96.0416/96.8437→94.7358/95.8352。访问控制节点last BF1下降1.3058pp，不能宣称整个训练轨迹更稳定。pooled OOF单独统计，不替换等权均值，也不是独立测试。

**21.9 预测变化、困难文件和关系支持**

两个合约任务best全部类别预测相同，只改变概率。重入节点best纠正31错误、新增17错误，净少14；访问控制纠正13、新增3，净少10。类别变化仅48/12036和16/7710个节点，其余主要是概率变化。

重入fold8：BF1 67.5236→67.6370；buggy_18.sol的275错误、buggy_36.sol的58错误完全未变，减少的是buggy_42.sol的一项漏报。访问控制fold7：79.1252→80.0805；buggy_18.sol的94误报仍未变，减少6个其他文件误报。这里是相对冻结作者标签的错误计数，不据此证明作者标签错误；前期标注上下文问题未被本次训练消除。

E3b新增关系total，按STATE_DEF_USE / STATE_ACCESS_ORDER / EXTERNAL_CALL_BEFORE_STATE_WRITE排列：重入合约6/847/547、重入节点3/829/547、访问控制合约11/33/0、访问控制节点4/16/0。所有折的train/val支持量均已导出；无支持折未删除。1120个模型×增强canonical记录含原DATA_DEF_USE，其中1091个有train支持者均观察到非零有限梯度，29个无train支持者无梯度并独立保留。参数更新含weight decay，不能单凭更新证明数据梯度；本次检查了各轮msg/attention/priority实际梯度。

这说明新关系进入训练，而非只存图文件；不证明完整语义或因果贡献。有限17条状态Def–Use主要是构造器/定价关系，未完整覆盖余额或权限guard/modifier；访问控制没有CALL→WRITE。H1仅比较整体新增关系，不能分离各组贡献。

**21.10 原始E0/E1历史基线对照**

已核对原Stage C全部30配对折60模型的收据、相同文件/节点/target、split及数值配置。下列为best均值BF1/MF1：

| 任务 | E0历史 | E1历史 | E2本批 | E3b本批 |
|---|---:|---:|---:|---:|
| 重入合约 | 94.1593/94.3452 | 93.5157/93.6245 | 95.0140/95.0549 | 95.0140/95.0549 |
| 访问控制合约 | 93.5590/93.8316 | 93.5590/93.8316 | 91.5628/92.0657 | 91.5628/92.0657 |
| 重入节点 | 96.0580/96.0088 | 96.0740/96.0107 | 96.0772/95.9052 | 96.2460/96.0506 |
| 访问控制节点 | 95.9723/96.8764 | 95.8130/96.7384 | 96.1983/96.9983 | 96.3495/97.1228 |

旧semantic-paired-native-xavier-v1与当前state-forward/triple-chain初始化不同，未证明跨批共同参数完全相同；只可称历史同折参考。本批E2/E3b才是严格成对。访问控制合约比历史E0/E1低约1.9962pp BF1，必须保留，不能宣称全面超过基线。

**21.11 资源、补充文件、测试与保存位置**

正式控制器monotonic耗时10564.2432秒（约2.93小时），包含校验/启动/保存/重载；52个新fit记录耗时合计8791.6400秒。重入合约fold1/E2遇Windows显存竞争，耗时656.4475秒，整卡free最低14MiB；GameViewerServer曾分配约916MiB专用显存，用户表示自行关闭，后续速度恢复，但没有独立确认该进程退出。没有代关程序或重启模型。不能用变化的系统负载和不同早停轮数比较算法速度。

本批产物目录scripts/DFG/experiments/artifacts/paper_kfold/stage_h1_v1/新增只读后处理：
- analyze_h1_results.py：独立复算节点/文件身份与指标，统计逐文件纠错、概率幅度、全历史canonical梯度及逐折资源；不加载训练模型。
- render_h1_report.py：将已验收CSV/JSON渲染为中文H1_RESULT_REPORT.md。语法检查发现并修正一处报告字符串引号/代码块转义后通过；未触及训练源文件，无模型重跑。
- verify_protected_after.py：核对14253项旧资产、7个完整旧目录、两HEAD和4个文档原始前缀，仅写新批次审计JSON。

607项不同测试通过，0失败/0跳过；重复的16项H1复查不重复计数。训练数值代码在测试后封存，训练期间未改；未升级依赖。警告仍为既有DGL/TensorBoard distutils及NetworkX弃用。后处理语法检查、独立指标断言、全部重载验收通过。最终旧资产/目录核验见protected_after.json；4份文档追加SHA见documentation_phase2.json。

主要交付：H1_RESULT_REPORT.md、H2_EXECUTION_PLAN.md、summary.csv、last_summary.csv、fold_statistics.csv、last_fold_statistics.csv、paired_deltas.csv、paired_statistics.csv、pooled_oof.csv、oof_predictions.json、error_changes.csv、file_error_analysis.csv、prediction_change_summary.csv、enhancement_support.csv、canonical_support.csv、gradient_support_detail.csv、resource_folds.csv、baseline_*、historical_baseline_deltas.csv、analysis.json、postprocessing_checks.json及plan/seal/各fold收据。保留所有Stage G原始产物和日志。

**21.12 结论、限制与停止**

合约best无收益，节点best有小幅平均收益，但存在下降折、last退化和困难文件未改善，不能称稳定普遍提升、显著性或独立测试泛化证据。单seed、同val选模评分、既有模板相似性、历史标签上下文、有限语义及无独立人工/新solc编译验证仍是限制；不能声称完整Solidity DDG。

若要形成完整消融，建议审查后按已封存计划补齐H2的26次E3a，用于解释状态Def–Use与两类顺序关系联合贡献，不预设提高成绩。本轮不执行H2、不扩七类、不增加seed、不扩状态/反向关系。已经按用户要求在H1报告处停止。

只读验收（在mando环境、开发工作树下）：
```bash
export PYTHONPATH=/home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m scripts.DFG.experiments.e23_cv.control verify
python -B -m scripts.DFG.experiments.e23_cv.control summarize
python -B scripts/DFG/experiments/artifacts/paper_kfold/stage_h1_v1/analyze_h1_results.py
```
后续若归档提交造成HEAD漂移，不改旧seal，应单独做只读归档身份验收。


## 22. Stage H2：E3a 完整消融接入与正式执行（2026-10-15，Codex）

**22.1 任务范围与历史冻结**

用户本轮明确授权新增26次E3a正式拟合，复用Stage G四个fold0，与H1已有E2/E3b各30项合并为90个结果。仅重入/访问控制、合约5折/节点10折，seed、图、标签、512维inside_token、HGT、初始化及训练计算全部冻结。不重训E2/E3b、不重做Oracle/覆盖普查、不扩其他五类、不启动额外seed或独立测试。

开发树当前HEAD为cef8fb9bac5f855d657b7d72a04d650f03465469，H1训练HEAD为44e7337bb7b47738bc49a947ed5625809f7f006a。已读取H1报告、H2预留计划、各task/fold manifest、初值和G收据。复用现有scripts/verify_h1_archive.py的H1专用只读归档核验；不修改旧seal，也不把提交祖先关系当作内容一致证据。82份H1运行源码及684项H1冻结资产摘要全部一致，60个H1结果验收通过。旧h2_plan.json中的execution_authorized=false保持原样；新H2计划独立记录本轮授权。

**22.2 新增文件与最小接入**

新增目录scripts/DFG/experiments/e23_h2/：
- __init__.py：H2版本与新产物目录常量。
- archive.py：调用H1只读归档校验；检查30份保存初值的文件SHA、tensor digest、kind、optimizer_steps=0、任务/折/图身份、共同参数对齐记录、fit_seed，以及四个Stage G E3a fold0收据。没有重新初始化模型。
- control.py：独立plan/seal、固定26次新fit顺序、四个fold0只读引用、任务验收、串行双锁、成功复用与失败保留/显式重试。
- worker.py：从H1薄层worker派生，仅变更E3a白名单、批次绑定、初值检查调用。直接复用e23_pilot.make_model、Supervision、fit及checkpoint；不重写epoch循环。差异保存在WORKER_PROVENANCE.json。
- report.py：从冻结图标签及预测独立复算三变体指标；按file/node identity字典对齐，导出cohort与source SHA，拒绝缺失/重复/混合评分身份；best/last分别统计、OOF与等权折均值分别统计。
- tests/test_h2.py：必要调度、错误初值、历史不可覆盖、身份对齐、失败恢复和成功复用测试。
- README.md：实际运行命令、日志位置和限制。

没有修改H1 worker白名单、旧计划、旧报告、DDG/state语义、HGT、tokenizer或原训练脚本。所有新增主要逻辑位于新H2目录。旧G初值没有显式fold字段与嵌入initialization审计对象，采用原已封存fold0 manifest和外部audit绑定验证；H1后续折必须具有显式fold及嵌入audit，不降低后续折身份检查。

**22.3 配置核对与旧文字澄清**

旧H1报告第2节用合约任务配置简略描述了全部训练，不能据此认为节点也使用相同学习率。真实manifest/有效配置为：
- 合约：initial_lr=0.0005、OneCycle max_lr=0.01、div_factor=20、weight_decay=5e-6。
- 节点：initial_lr=0.0002、max_lr=0.005、div_factor=25、weight_decay=0。
共同规则为50轮上限、patience=7、delta=0.001、严格最低val loss保存best、last另报、原Adam/OneCycle与每轮step数。H2逐任务继承完整manifest，不统一改写数值；该项是旧报告文字澄清，不是训练配置修改。原H1报告保留不覆盖。

全部评分为paper_kfold的CV validation，同一val用于选择/早停/评分；节点仍为HCG节点口径。pooled OOF不称独立测试。

**22.4 测试与启动门槛**

在现有mando环境运行：
python -B -m pytest -q -p no:cacheprovider scripts/DFG/experiments/e23_h2/tests scripts/DFG/experiments/e23_pilot/tests/test_training_integration.py scripts/DFG/experiments/e23_pilot/tests/test_model.py

71 passed，0 failed，0 skipped，4条既有DGL distutils弃用警告。包括实际保存初值、错误图/标签/特征/schema保护、训练数值一致性、验证标签不影响训练梯度、checkpoint绑定，以及调度失败不自动重试。未重新运行四任务真实smoke，也未使用合成测试作为正式成绩。

新目录scripts/DFG/experiments/artifacts/paper_kfold/stage_h2_v1/已生成独立plan/seal、archive_audit.json、fold0_reuse_audit.json、integration_tests日志。89份运行源码及1525项固定资产封存，历史计划授权值保持不变。启动前GPU无其他CUDA计算进程，RTX3050 Laptop 4GiB；显存仍受Windows进程共享，实际峰值与最低free逐fit记录。磁盘约859GiB可用。

已启动26次E3a正式拟合，按重入合约1–4、访问控制合约1–4、重入节点1–9、访问控制节点1–9串行执行；此条仅记录启动，不预报结果。运行期间不修改封存源码，不提交Git；成功任务验收后进入下一任务。最终结果与是否失败/重试另追加。


**22.5 正式完成与历史保护（2026-10-15，Codex）**

26次新增E3a全部完成：重入合约fold1–4、访问控制合约fold1–4、重入节点fold1–9、访问控制节点fold1–9。每项均attempt_001，0失败、0重试、0 OOM；四个任务完整性门槛依次通过。四个Stage G E3a fold0通过初值/配置/图/收据验收并引用，不重训。最终E3a=30，联合H1已有E2/E3b=90个正式结果。execution.json标记complete，verify返回new_complete=26/stage_g_reused=4/total_complete=30，summarize返回0。

主结果以冻结标签及导出预测独立复算；按task/cohort/file/original_graph_node_id对齐，另带source SHA。90项best/last均有完整产物和重载验收。没有使用CSV行序、同名文件混合或更优F1选择checkpoint。全部为CV validation；pooled OOF与等权折均值分开，节点仍按HCG节点计分。

**22.6 完整三变体best主结果**

| 任务 | E2 BF1/MF1 | E3a BF1/MF1 | E3b BF1/MF1 | E3a−E2 BF1 | E3b−E3a BF1 |
|---|---:|---:|---:|---:|---:|
| 重入合约5折 | 95.0140/95.0549 | 95.0140/95.0549 | 95.0140/95.0549 | 0 | 0 |
| 访问控制合约5折 | 91.5628/92.0657 | 91.5628/92.0657 | 91.5628/92.0657 | 0 | 0 |
| 重入节点10折 | 96.0772/95.9052 | 96.0388/95.8613 | 96.2460/96.0506 | −0.0384pp | +0.2072pp |
| 访问控制节点10折 | 96.1983/96.9983 | 96.2631/97.0592 | 96.3495/97.1228 | +0.0648pp | +0.0865pp |

节点E3a−E2的BF1差值SD/升平降：重入0.2093、3/3/4；访问控制0.3399、3/5/2。E3b−E3a：重入SD0.3282、6/2/2；访问控制SD0.2248、3/6/1。两个合约任务每种对照均5折持平。逐折BF/MF/P/R、混淆矩阵、均值和样本SD、全部三组差值及pooled OOF已独立导出，不能将折SD当独立seed方差。

E3a仅增加STATE_DEF_USE，不能证明其对两类都有稳定收益；H1重入的主要小幅收益出现在随后加入两种顺序关系的联合对照。访问控制两段均小幅正向，但无调用→写入边，不能称调用依赖收益。关系参数量、聚合和优化轨迹一并变化，不是纯语义因果消融。

**22.7 last与错误变化**

E3a last均值BF1/MF1：重入合约90.2265/90.1307；访问控制合约86.1731/85.9480；重入节点96.9309/97.0638；访问控制节点96.0594/96.8393。重入节点E3a−E2的last BF1 +0.0360pp，与best −0.0384pp反向；访问控制+0.0178pp，但MF1 −0.0044pp。E3b−E3a的last BF1分别−0.0869pp、−1.3236pp。访问控制合约E3a/E3b last较E2低0.7333pp。不能用last替换已冻结的最低val loss best主规则。

合约best的全部142/114个概率发生变化，但类别均不变。节点E3a−E2 best：重入纠正12/新增14错误，26/12036节点改变类别；访问控制纠正9/新增5，14/7710改变。E3b−E3a best：重入纠正30/新增14，44个类别改变；访问控制纠正9/新增3，12个改变。主要仍是概率变化，不能把远离新增边的变化直接解释为局部依赖语义收益。

困难文件best三变体离散预测不变：重入buggy_18.sol 275错误、buggy_36.sol 58错误，访问控制buggy_18.sol 94错误、buggy_26.sol 42错误。访问控制fold7的6项E3a纠错来自另外4个文件，不来自buggy_18.sol。文件分布与原node_id明细均保存在新CSV，cohort/source SHA区分同名文件。本轮不重标、不删除、不全面重审这些文件。

**22.8 支持、资源与验收**

STATE_DEF_USE在四任务固定图中的边数依次6/11/3/4；节点任务分别8/10、7/10折val无这种边。所有折在关系名称汇总层面有train支持，不代表每个canonical都有train实例。三变体1605项增强canonical梯度记录（包含原DATA_DEF_USE）：1564项有train支持者均观察到非零有限梯度，41项无train支持者独立保留，非有限记录0。证明计算接入，不证明语义完整或普遍收益。

26个新fit记录耗时合计4296.9452秒；控制器monotonic5521.9853秒（约1.53小时，含启动/校验/保存/重载）。仅本轮新fit的最高allocated2466.5654MiB、reserved2628MiB，最低整卡free54MiB；全90结果资源表还含历史批次更低的free。首个fit曾因Windows GPU竞争变慢，用户表示自行关闭不需要的程序；未代关进程、重启fit或改参数，未独立确认程序退出。不同系统负载和早停轮数不能用于公平速度结论。

71项必要测试通过，0失败/跳过，4条既有DGL弃用警告。未重新运行四任务真实smoke、完整DDG语义测试、solc编译或Oracle；未升级依赖。训练完成后只执行只读核验、指标复算和输出报告，不改变封存计算源码。最终资产保护与文档追加检查见stage_h2_v1/protected_after.json，交付索引见delivery_manifest.json。

**22.9 后处理文件和交付**

在新stage_h2_v1产物目录新增render_reports.py与interpretation.md，用于将已验收CSV/JSON渲染成中文H2_RESULT_REPORT.md、E2_E3_COMPLETE_ABLATION_REPORT.md；不是训练器。H1 baseline_statistics.csv校验旧交付SHA后只读复制为historical_baseline_statistics.csv，来源见historical_reference_provenance.json。旧E0/E1仅历史参考，跨批初始化不同，不与E2/E3a/E3b混称共同初始化对照。

主要产物：独立plan/seal、归档/四fold0复用审计、26次完整fit、summary/last_summary、three_variant_best/last、fold_statistics/last_fold_statistics、paired_deltas/paired_statistics、pooled_oof、oof_predictions、error_changes、file_error_analysis、prediction_change_summary、enhancement_support、gradient_support_detail、resource_folds、report.json、两份报告、README和运行/测试日志。90个正式结果通过身份、输入、checkpoint和预测校验。旧计划seal、H1/G产物保持原样，旧预留H2 execution_authorized=false未改。没有pull/checkout/reset/commit/push。

实际只读核验命令（现有mando环境，当前开发HEAD）：
~~~bash
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONPATH=$PWD
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -B -m scripts.DFG.experiments.e23_h2.control verify
python -B -m scripts.DFG.experiments.e23_h2.control summarize
~~~
26次正式拟合已用同模块run完成，不需要重训；不再次seal。后续若归档导致HEAD不同，应另做只读归档核验，不改旧seal。

**22.10 结论及停止边界**

当前最支持有限的顺序关系机制研究：已有小幅节点best收益，但非所有折改善、last退化、核心困难文件未解决。单独STATE_DEF_USE覆盖过稀，尚无稳定增益证据。后续若继续，应另定任务检查已变化节点和困难上下文，预先固定区分两类顺序关系及参数/连接数量控制；权限guard/modifier、独立seed和独立评估仍缺证据。本轮没有自动执行这些后续研究。

已完成用户要求的26次新训练、30个E3a验收、90结果完整三变体消融后停止。不重跑E2/E3b、不增seed、不扩七类、不新增图关系/模型。修改、执行与分析AI：Codex。
