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


## 23. Stage I：能力清单与固定权重状态消息诊断（2026-10-19，Codex）

**23.1 授权、边界与工作树**

本轮执行此前建议的第1步（能力清单、编号与入口约束）和第2步（复用证据与固定checkpoint诊断）。开发工作树为ge-sc-llm-ddg-v11，起始HEAD 021a6f55；原工作树ge-sc-llm起始HEAD f3dfc179，其auto_version_solc.py已有用户修改，保留不动。没有pull/checkout/reset/commit/push。新增逻辑位于scripts/DFG/experiments/stage_i_diagnostics/，结果独立保存，不修改DDG/state语义、HGT、tokenizer、图、标签、划分、训练规则或历史checkpoint；不新增modifier、控制依赖、反向关系或正式训练。

现有E2=修复标量DDG；E3a=E2+STATE_DEF_USE；E3b=E3a+两类顺序关系。原始宏观文档中E2/E3的长期路线编号另有所指，不能与当前Stage G/H矩阵混淆。

**23.2 新增文件与实现原因**

- CAPABILITIES.md：逐项列明当前能力、保守回退及尚未实现部分；ENTRY_POINTS.md、modifier_scope.md明确入口与modifier边界。
- entry_validation.py：显式旁路校验。旧graph_utils只保护DATA_DEF_USE方向；Stage F/e23_pilot保护四类正向增强关系。新检查拒绝状态图误入legacy、未知增强关系前缀及缺失元数据；保留正常CFG/CG关系。它不会全局拦截直接运行的旧训练脚本，也不替代既有SHA、标签、特征、schema和receipt校验。
- evidence.py：复用Stage F语义/投影sidecar与H2预测，按cohort、source SHA、原node ID建立静态证据链，不重新构图、不猜最近源码行、不重审标签。
- interventions.py：复用旧诊断实例包装，在原attention和multi_update_all路径中，将选定canonical消息置零后执行原cross-mean，保留分母、节点、边、参数与schema。只处理三个状态/顺序关系，保留原DATA_DEF_USE。
- common.py/run.py：独立plan/seal，读取历史manifest和收据，CPU校验后单CUDA worker串行加载。eval+no_grad，无optimizer/backward；正常包装及退出恢复须与native逐位一致；权重、参数对象、图/标签/特征/schema与梯度状态均核验。成功结果绑定plan/job/source receipt后复用，失败保留，不自动无限重试。
- aggregate.py与测试：从导出预测独立重算逐折/pooled/错误变化。其封存版评分角色绑定错误由产物目录独立aggregate_stage_i.py适配，原文件不改，附diff和来源SHA；不改指标公式或预测数据。
- 产物目录中的analyze_messages.py和join_prediction_context.py：只读关联canonical消息、冻结支持量、静态上下文和预测，不将聚合范数伪称逐节点因果贡献。

**23.3 静态证据与来源限制**

四任务E3b新增关系（STATE_DEF_USE/STATE_ACCESS_ORDER/EXTERNAL_CALL_BEFORE_STATE_WRITE）：
重入合约6/847/547，访问控制合约11/33/0，重入节点3/829/547，访问控制节点4/16/0。
两个节点任务的7条状态Def–Use全部来自构造器；合约图17条中12条构造器、5条定价函数。不同粒度包含重复节点，不能将它们相加当独立证据。

重入节点E2的439个best错误中，422个（96.13%）位于新增关系两层潜在影响域之外；域内1338节点仅17个错误。575个获得新上游节点身份的节点中仅4错。访问控制37个潜在影响节点和1个新增上下文节点在E2中均预测正确，206个错误全部在域外。因此新增关系与主要错误重合很少，但可达性不等于利用或因果收益，已有可达也不代表新的关系类型必然冗余。

两个节点任务的困难文件仍为：重入buggy_18/buggy_36的275/58错，访问控制buggy_18/buggy_26的94/42错。继承相关原因约占已记录函数回退54%–62%，modifier约9%–14%；这是首先触发的回退原因，不是修复后保证能恢复的数量。

静态产物在stage_i_v1/static。Stage F sidecar与其delivery一致，但该delivery不在H2 frozen_files清单，明确作为本轮观察封存的历史旁证，不伪称被H2 seal认证。图和checkpoint仍由历史manifest/receipt SHA绑定。PROVENANCE_ASSURANCE.json记录该边界及生成后仅增加来源说明字段的代码差异；原静态文件不覆盖。

**23.4 预检、修订和执行状态**

H1/H2只读归档核验分别通过52新+8复用=60、26新+4复用=30。新诊断固定60个已验收E3a/E3b模型，best/last共120份checkpoint；6条件为N/Z_D/Z_S/Z_C/Z_SC/Z_ALL，差值统一为屏蔽−N。全部属于固定权重的CV validation敏感性，非新增训练或独立测试。

126项联合测试通过（94项新增+32项旧干预/模型适配器回归），0失败/跳过，4条既有DGL distutils弃用警告。v1计划在执行前保留，修复概率exact描述字段被误判失败的问题；v2真实预检在创建模型前因read_graph接收str而失败，改为Path并新增回归，旧日志与seal保留。v3是实际执行批次。其封存后发现后处理角色应为exploratory_cv_validation_fixed_checkpoint_sensitivity、来源角色为cv_validation，使用独立产物后处理修正，不改封存推理源码或数据。

四任务fold0的8模型/16checkpoint真实预检通过后，继续全折；本条写入时全折执行中，最终数量、消息/预测结论、资源与保护检查在后续小节追加。GPU单模型串行，无CPU回退/缩图/调参/代关程序。平均诊断时间包含重复完整前向、输入SHA检查、checkpoint加载和范数同步，不能作为训练速度比较。

受限modifier只作范围说明：最早两份宏观设计未展开，后续接入分析明确适配/回退，当前代码遇到modifier仍函数级回退并保留原HCG。未来需要先证明唯一绑定、参数代入、占位符执行顺序和原HCG锚点；权限guard到操作通常属于控制依赖，不能假装为STATE_DEF_USE。本轮没有实施该扩展。修改与分析AI：Codex。


**23.5 全折诊断完成与独立复算**

实际完成60模型、120份best/last checkpoint、720个条件评分，训练步数0。全部正常概率与历史逐位一致（最大误差0），native包装/恢复、权重及参数对象、原图/标签/特征/schema均通过。新增推理不写旧图或checkpoint。消息审计41,660项canonical-layer观察，其中1,020项状态消息正常均非零，Z_ALL均被正确置零，cross-mean分母保持。完整汇总在stage_i_v3/STAGE_I_RESULT_REPORT.md。

下表为best的Z_ALL−N固定权重诊断，负值代表屏蔽损害当前模型，不能当作新增训练成绩：

| 任务 | 变体 | N BF1 | 屏蔽后BF1 | 等权ΔBF1/ΔMF1(pp) | 类别翻转 | 纠正/新增错误 | 概率变化数 |
|---|---|---:|---:|---:|---:|---:|---:|
| 重入合约 | E3a | 95.0140 | 95.0140 | +0.000000 / +0.000000 | 0 | 0 / 0 | 5 |
| 重入合约 | E3b | 95.0140 | 95.0140 | +0.000000 / +0.000000 | 0 | 0 / 0 | 61 |
| 访问控制合约 | E3a | 91.5628 | 91.5628 | +0.000000 / +0.000000 | 0 | 0 / 0 | 6 |
| 访问控制合约 | E3b | 91.5628 | 91.5628 | +0.000000 / +0.000000 | 0 | 0 / 0 | 24 |
| 重入节点 | E3a | 96.0388 | 96.0335 | -0.005299 / -0.006401 | 1 | 0 / 1 | 4 |
| 重入节点 | E3b | 96.2460 | 96.2346 | -0.011342 / -0.008748 | 1 | 0 / 1 | 1331 |
| 访问控制节点 | E3a | 96.2631 | 96.2631 | +0.000000 / +0.000000 | 0 | 0 / 0 | 6 |
| 访问控制节点 | E3b | 96.3495 | 96.3495 | +0.000000 / +0.000000 | 0 | 0 / 0 | 37 |

**23.6 机制证据与后续边界**

两个合约任务及访问控制节点在全部条件、best/last中均无类别变化。重入E3b best屏蔽全部状态消息仅新增1漏报（buggy_42.sol/node12245），但有1331个节点概率变化；该点E2/E3a best原漏报，E3b约0.512159正确，Z_C约0.490741变漏报，有实际新上下文和训练支持。另有buggy_32构造器节点屏蔽STATE_DEF_USE变错，但E2原本正确，仅证明已训练模型依赖消息维持正确。buggy_24的两个end_if节点在last联合屏蔽两种顺序关系才漏报，单项不翻转；各种干预不能线性相加。完整身份/路径/概率在case_review.md。

重入E3b last Z_ALL纠正2/新增2，等权BF1+0.060467pp但pooled−0.000666pp，保留两个口径；不以last替代best。所有固定权重节点变化均在对应两层潜在影响范围内。四个困难文件所有干预类别不变；继承与modifier只是源码分析首个回退原因，不是保证恢复量或逐节点错误归因。

现有数据不支持“消息未接入”或“状态依赖毫无价值”的结论。更具体的限制是状态DU集中构造器、覆盖与错误重合少。后续优先核对实际困难函数的继承/绑定、原HCG锚点及modifier上下文，再决定小范围扩展；本轮不编码modifier或新关系，不增加训练。guard到操作属于独立控制依赖问题，不能冒充STATE_DEF_USE。

**23.7 后处理、测试、资源与保护**

新增产物级aggregate_stage_i.py（评分角色适配，附diff/来源SHA）、analyze_messages.py、join_prediction_context.py及各自测试；另有verify_delivery.py、render_report.py、report_sections.json、case_review.md、报告与资源/保护清单。原封存aggregate.py不改，默认run summarize角色检查错误和日志保留；README明确改用独立后处理命令。后处理不改metric公式、样本身份、输入和预测。

126项接入/相关回归+36项后处理测试，共162项通过、0失败/跳过；两次命令各4条既有DGL distutils警告。60回放无失败/OOM，无训练或训练重试；v1/v2预检历史保留。没有重新执行全部历史DDG语义测试、外部solc编译、正式训练或七类扩展。

本轮60项推理/校验记录耗时合计3319.838秒（约55.33分钟）；最高allocated 706.573 MiB、reserved 742.0 MiB，整卡最低采样空闲1335 MiB，采样错误0。这含加载、哈希、重复前向和范数同步，不是训练耗时，也不是连续监控显存的绝对最小值。

完成后H1只读归档复核52新+8复用=60、H2复核26新+4复用=30，均通过。当前计划/源码/输入/静态证据摘要及60份回放收据均通过。最终文档前缀及用户改动保护清单见protected_after.json。

两工作树training_changes与HANDOVER仅追加；原auto_version_solc.py用户修改的SHA保持bf3365c32f65f4c51932478eb54687a53c6aaad932f8f56a4d58687aaa493f31。旧H1/H2/G计划、源码计算及产物不覆盖，无Git写操作。最终交付索引见stage_i_v3/delivery_manifest.json。实施、审查与分析AI：Codex。


## 24. 2026-10-19 Stage J：DDG整体构图入口与覆盖恢复（Codex）

**24.1 授权、设计选择与版本**

用户要求根据此前推荐完成DDG整体板块。基于Stage I的继承回退与错误覆盖证据，采用旁路实现“受限继承→受限modifier→精确投影→融合与审计”，没有跳过语义验证直接重训。整体闭环不等于完整Solidity分析；反向/控制依赖/跨函数摘要仍另行设计。

开发树ge-sc-llm-ddg-v11，HEAD保持021a6f55ac9e3f94fc70feb441ff48b51b6a92ea；原树HEAD保持f3dfc17908029355c5fc45d6d3932f203068fcf5。实现版本ddg-stage-j-coverage-v1，批次stage_j_v1。原DDG/Stage F、HGT、tokenizer、训练器、作者标签和旧实验不修改；无pull/checkout/reset/commit/push。修改、执行与分析AI：Codex；完成时间2026-10-19 UTC。

**24.2 新增文件、原因与关键逻辑**

主要新增目录：scripts/DFG/state/stage_j/，不搬移旧实现。

- binding.py：同一源码唯一基类、右侧优先C3和菱形去重；无参数基类、有限interface声明。保存声明span/owner身份；同名冲突、import、循环、无唯一基类、library/base参数等回退，不猜重载分派。
- modifiers.py：唯一且无参数modifier，恰有一个末尾顶层占位符；直线前缀支持已有表达式，require/assert须确认内建绑定及版本。拒绝多modifier、参数、后缀、多/条件占位符、前缀局部声明和副作用未知调用。
- analyzer.py：先执行旧Stage F；原成功结果复用，只重试回退函数。独立语义CFG为“参数入口→modifier前缀→函数体”，不替换模型CFG/CG。仍调用旧状态位置、提取及reaching definitions；失败函数无部分事实。另记录legacy构造器/运行时函数，避免把构造器恢复当作运行时提升。
- configuration.py：use_ddg、add_scalar、state_mode(off/def_use/orders)、recovery(frozen/inheritance/modifiers)、迭代上限。关闭时精确复制传入图，不反向删除已有DDG；恢复baseline必须传原baseline输入。
- pipeline.py：统一调用标量模块、版本/源文件分析、旧精确Projector及materializer。新事实加coverage来源与materializer/producer版本，最终再次验证指纹。禁止已有状态图二次叠加，不改node ID/token/标签/基础边；缺失投影保留原图、不按最近行猜。
- cli.py：显式本地图/源码SHA、拒绝覆盖、导出enhanced.gpickle/audit/manifest；复用Stage F四类正向关系DGL适配，检查真实canonical边数量。不会重写训练脚本。
- tests/__init__.py、test_semantics.py、test_pipeline.py：新增54项，覆盖继承/绑定/modifier/回退、投影/KILL、标签特征独立性、同端点多关系、配置及原HGT接口。
- README.md、DESIGN_AND_ACCEPTANCE.md：整体架构、实现边界、官方语言规则引用、真实入口和命令。
- scripts/DFG/experiments/stage_j_coverage/run.py及README：冻结manifest派生四任务三模式图，来源SHA/独立plan/seal/收据、增量覆盖统计；没有训练代码。

本次恢复主要发生于状态分析；原标量DATA_DEF_USE规则未扩展。本批以冻结E2为输入，标量边直接保留。通用入口可从原HCG调用add_scalar复用原模块。数据依赖事实投影到同一语句节点后与CFG/CG合并，不新建变量节点或独立图编码器。

**24.3 回退、方向与不变量**

原成功Stage F函数不重新解释。未知/不支持函数级回退，无临时DDG残留；原图所有样本保留。未投影写入仍执行KILL，未投影控制结构仍在分析IR中；原HCG锚点缺失只丢弃不可投影事实，不补点或猜最近行。

DATA_DEF_USE、STATE_DEF_USE、STATE_ACCESS_ORDER、EXTERNAL_CALL_BEFORE_STATE_WRITE均正向；增强在schema提取前物化。同端点不同relation保留；同relation重复证据合并边并保存侧表。状态顺序不是Def–Use；modifier权限检查也不自动等于控制依赖。内建终止和状态HAVOC沿用既有语义。

新增语义不使用标签或token值；对应扰动测试通过。新图仍有原图的标签语义不确定性，本轮未重新标注，也不声称解决作者标注来源问题。

**24.4 真实图生成与结果**

独立批次scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build。输入来自e23_pilot_v1/input_manifest，accepted Stage F sidecar由delivery摘要验证；sidecar是本批观察绑定，不能追认为旧H2 seal认证。

四任务各frozen/inheritance/modifiers，共12图。frozen复现原E3b状态关系集合；后两模式关系单调保留；全部原图指纹和实际DGL方向计数通过。

| 任务 | 文件/节点 | 原可分析→恢复后 | 恢复函数/其中运行时 | 新增状态关系 | 新上游上下文目标 |
|---|---:|---:|---:|---:|---:|
| 重入合约 | 142/18312 | 1316→2033 | 717/700 | 863 | 464 |
| 访问控制合约 | 114/13432 | 1299→2045 | 746/738 | 70 | 123 |
| 重入节点 | 71/12036 | 899→1372 | 473/470 | 806 | 415 |
| 访问控制节点 | 57/7710 | 965→1482 | 517/514 | 40 | 89 |

最终STATE_DEF_USE/STATE_ACCESS_ORDER/EXTERNAL_CALL_BEFORE_STATE_WRITE分别为重入合约9/1388/866，访问控制合约14/100/0，重入节点4/1322/859，访问控制节点5/55/0。两个节点任务新增STATE_DEF_USE各1条仍来自buggy_16构造器；不能宣称运行时DU稀疏已解决。

函数总量3388/3043/2045/1958与accepted F1逐文件一致。旧Stage I静态表额外16/105个合约函数记录均为file_fallback，来自2/6个版本证据不足/跨作用域版本边界文件；本批仍保留这些文件的原图，未进入函数分析，见function_population_note.json。

**24.5 后处理、困难文件与真实语义证据**

新增产物级audit_coverage.py/v2.py按task/file/sourceSHA/nodeID及原target对齐旧E2/E3b best预测；仅构图后诊断，不将错误标签送入分析。

重入旧E3b 425错误中39进入新增边两层局部范围、6有新上游节点；访问控制旧196错误均在范围外。旧E2对应439/39/8和206/0/0。局部范围不是新训练的因果边界，共享参数和canonical聚合还可能影响范围外；新增边不等于收益。

重入buggy_18新增17关系、恢复18函数，275旧错误中37进入局部范围、6有新上下文；buggy_36新增12关系但58旧错误未覆盖。访问控制buggy_18/26恢复33/30函数但新增模型边0，94/42旧错误未覆盖。

Codex源码证据核对：重入buggy_18 claimReward_re_ent18第249行读取→251清零产生STATE_ACCESS_ORDER，非反向伪Def–Use；访问控制buggy_17 onlyOwner第63行读取owner→68行写owner产生状态访问顺序，未制造权限控制边。完整SHA/原nodeID/字节锚点及源码在opportunity_v2/new_edge_cases.json；不是独立人工Oracle或编译验证。

后处理v1因合约/节点CSV字段不同在写表时失败，失败脚本和日志保留。v2改为列并集写入opportunity_v2，构图源码、图、统计定义不变。首次全DDG pytest收集时test_pipeline模块同名冲突，通过给新增tests补__init__.py解决；未删除或放宽测试。

**24.6 测试、验收命令与实际结果**

在mando环境、开发树、TREE_SITTER_LIB_DIR指向原项目现有build/linux-x86_64：

~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests scripts/DFG/state/tests scripts/DFG/state/stage_f/tests scripts/DFG/state/stage_j/tests
python -B -m pytest -q -p no:cacheprovider tests
python -B -m scripts.verify_h1_archive
python -B -m scripts.verify_h2_archive
~~~

DDG377通过（含新增54），0失败/跳过，28条既有DGL/NetworkX弃用警告；原项目25通过，0失败/跳过，7条既有TensorBoard/DGL/NetworkX警告。合成HGTLayer前向、关系非零有限梯度及checkpoint重载通过，optimizer_steps=0。真实12图不变量/SHA/schema通过；H1 52+8=60、H2 26+4=30只读归档复核通过。

真实构图命令：
~~~bash
python -B -m scripts.DFG.experiments.stage_j_coverage.run \
  --input-manifest scripts/DFG/experiments/artifacts/paper_kfold/e23_pilot_v1/input_manifest.json \
  --output scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build
~~~
目录已存在，重复命令会拒绝覆盖。通用入口及源码manifest格式见state/stage_j/README。输出包含各模式enhanced.gpickle/audit.json/manifest.json及批次plan/seal/receipt。新图不能直接替换冻结训练计划的输入，必须另行绑定新图/schema/初始化。

**24.7 未执行、剩余边界与保护**

没有运行新正式训练、GPU短检查、其他五类、反向DDG、控制依赖或跨函数摘要；没有下载/执行新solc。新增样例是解析/静态语义夹具，未完成编译验证；不把解析成功当作合法性证明。

后续优先核验新恢复事实和剩余错误缺口，按新候选图单独建立实验计划后再短检查；访问控制未覆盖的权限语义需要独立小型控制依赖Oracle，不能冒充状态DU。

旧183项代码/用户文件SHA不变，两工作树4文档仅追加；旧图/标签/token/计划/seal/权重不改。原用户auto_version_solc.py SHA保持bf3365c32f65f4c51932478eb54687a53c6aaad932f8f56a4d58687aaa493f31。保护与完整交付清单在stage_j_v1/protected_after.json、delivery_manifest.json。主报告STAGE_J_RESULT_REPORT.md。完成后停止，不自动训练；修改与分析AI：Codex。


## 25. 2026-10-19 Stage K：版本域修复与整体DDG成对单折验证（Codex）

**25.1 本轮目标、授权与实现边界**

用户要求按此前分析修复问题并继续运行，减少对每个小点单独训练的消融。采用“一个整体修复版本＋两个节点任务固定fold0配对训练”：既修复已确认的开放pragma覆盖瓶颈，也将Stage J的继承/modifier恢复一起接入，不为每个恢复点分别训练。新增正式拟合计划为4次，不自动重跑90次或扩展七类。合约级仅生成新候选图，本轮不训练。

开发工作树/home/zhao/SmartContract/ge-sc-llm-ddg-v11，起始及运行HEAD为021a6f55ac9e3f94fc70feb441ff48b51b6a92ea；原工作树HEAD f3dfc17908029355c5fc45d6d3932f203068fcf5。新语义版本ddg-stage-k-supported-profile-v1，新实验版本ddg-stage-k-overall-paired-pilot-v1，独立批次scripts/DFG/experiments/artifacts/paper_kfold/stage_k_v1。没有pull/checkout/reset/commit/push；保留原工作树auto_version_solc.py的用户修改。实施、审查、执行与分析AI：Codex。

**25.2 已确认问题及修复方式**

旧state/stage_f/versioning.py将pragma >=0.5.9表示为[0.5.9,999.0.0)，而内建调用可用性表只声明到0.9.0之前。由此出现“未来无限区间无法保证”的保守回退：revert/selfdestruct终止调用可能使函数回退；普通require/assert有时被保留为UNKNOWN_CALL并触发HAVOC；address调用也可能失去已知外部调用分类；modifier前置guard无法确认。这不是tree-sitter要求编译成功，也不是源文件必须修改版本，而是新增静态分析器的语义域与源码允许版本范围没有分开。

新增SupportedSourceView，先执行原Stage F源码/版本/作用域检查，再将分析域显式限定为原分析器已声明支持的[0.4.0,0.9.0)与源码版本区间的交集。证据同时保留原pragma区间、分析交集、被排除未来区间、源SHA和是否存在真实版本元数据；不伪造确定solc版本，不修改源码/pragma，不保证未来版本语义。没有真实编译器元数据时exact_compiler为空。

这不是“每个程序在整个区间都已验证可编译”。跨legacy/modern作用域仍无法确定、无版本证据、元数据矛盾、无支持域交集、同名遮蔽或不支持绑定仍按旧规则回退；suicide的较窄可用版本范围没有被放宽。当前修复针对状态前端，标量DATA_DEF_USE提取规则保持原样。

**25.3 新增文件与接入原因**

新增scripts/DFG/state/stage_k/：
- __init__.py、profile.py：显式版本域与来源证据，保持原Stage F声明/作用域检查。
- pipeline.py：复用Stage J prepare_graph函数体，以局部函数globals注入SupportedSourceView及新producer版本；不修改旧模块globals、不改旧Stage F/J源码或旧入口行为。
- tests/__init__.py、test_profile.py：11项版本、终止调用、同名用户函数、未知回退、图不变量和旧入口隔离测试。
- README.md：分析域定义、非编译保证、回退边界及入口。

新增scripts/DFG/experiments/stage_k_pilot/：
- common.py、prepare.py：原manifest取路径；校验源/图/配置/划分摘要；四任务生成同一整体B1图，保留Stage J已有typed边集合和原节点/标签/token/CFG/CG；只为两个节点任务保存新B0/B1未训练初值、schema、监督清单和seal。
- checkpoint.py、training.py：复用原paper_kfold/e23_pilot函数体，只绑定新实验checkpoint格式与B0/B1身份；未重写优化器、loss、scheduler、早停、评分或HGT前向。
- worker.py、control.py：单GPU单模型串行，正式fit前恢复原fit_seed；验证初值未训练、输入/schema一致，记录best/last及预测；成功有收据可复用，失败保留并要求诊断后显式重试，不自动无限重试、降维或切CPU。
- report.py：按task/file/original_node_id和冻结标签独立复算指标，拒绝重复/缺失/错误标签或评分角色，导出best/last及预测变化。
- tests/__init__.py、test_integration.py：8项任务矩阵、旧训练函数体数值路径、checkpoint/schema/初值绑定与错误输入拒绝测试。
- README.md：实际命令、实时日志、B0定义、单折解释及恢复规则。

既有DDG、Stage F/J、HGT、tokenizer和原训练脚本没有被覆盖。新pipeline仍以独立语义CFG分析，再将四类正向关系精确投影到原HCG语句节点；不新增变量节点、反向边或控制依赖。用局部函数绑定复用旧实现是为隔离封存历史，并不改变旧入口的默认语义。

**25.4 对照定义与训练规则**

B0=原Stage G/H冻结E3b图，即已有标量DDG和旧状态/顺序关系；B1=冻结E2标量图＋Stage J继承/modifier覆盖恢复＋Stage K版本域修复后的全部状态关系。B0不是无DDG的原MANDO，历史E0/E1继续仅作历史参考。

本轮B0/B1均重新创建未训练模型，共同参数按节点类型及canonical relation语义对齐，新关系独立可复现。构造seed10000、语义配对seed10077、fit_seed1010000，来源于现有任务策略。没有从已训练E2/E3b、smoke、best或last启动。由于本批B0直接新建于E3b schema，不是历史E2→E3a→E3b三级初始化链，不能把历史H1的F1直接冒充本批共同初始化的B0；本批已重新成对训练。

两个任务均使用原冻结node fold0。重入63/8 train/val文件，访问控制51/6。完整固定图前向、train节点mask监督，同一val用于早停、best选择和最终评分，结果称CV validation，计分单位HCG节点；不是独立测试或去重源码行F1。

配置沿用原节点manifest：512维inside_token（CodeT5p-770m tokenizer IDs，未加载LLM encoder权重），hidden128、2层、8头、dropout0.2、use_norm；Adam initial_lr0.0002/max_lr0.005、weight_decay0，OneCycle50步、div_factor25/final_div_factor1；最多50epoch、patience7、delta0.001。best严格取最低val loss，last独立，不因哪个F1更高而换checkpoint。原图标签/特征/文件折清单不改，状态关系由Stage F adapter保持正向。

**25.5 构图与覆盖结果**

四份B1候选图已生成，实际DGL canonical边数量及原图不变量通过。以下新增边为相对旧E3b；“本次版本修复新增”是相对Stage J modifiers图。

| 任务 | 节点/最终边 | 可分析函数Stage J→K | 相对旧E3b新增边 | 本次版本修复新增 | STATE_DEF_USE/STATE_ACCESS_ORDER/EXTERNAL_CALL_BEFORE_STATE_WRITE |
|---|---:|---:|---:|---:|---:|
| 重入合约 | 18312/25519 | 2033→2189 | 1291 | 428 | 9/1573/1109 |
| 访问控制合约 | 13432/19691 | 2045→2058 | 77 | 7 | 14/107/0 |
| 重入节点 | 12036/16217 | 1372→1528 | 1234 | 428 | 4/1507/1102 |
| 访问控制节点 | 7710/11743 | 1482→1495 | 47 | 7 | 5/62/0 |

触发显式分析域裁剪的文件分别9/8/8/8。标量边数仍3561/4032/1894/2836。作者节点ID、类型、源码映射、标签、token和基础CFG/CG未修改，Stage J原有typed边也未丢失；所有回退文件保留。

仅作为构图后证据，复用旧H2 E3b预测统计：重入425个旧错误中74进入新增边两层局部范围、36有新上游节点（Stage J为39/6）；访问控制196个旧错误仍0/0。重入buggy_18的275旧错误中64进入范围、30获新上下文；buggy_36的58旧错误中8/6。访问控制buggy_18/26仍未覆盖主要旧错误。该审计不向构图提供标签，也不等同于纠错收益。

这些困难文件不在本批固定fold0的验证集；不换折挑成绩，不以训练集预测宣称困难文件已解决。版本修复主要恢复顺序关系，STATE_DEF_USE数量未增加，不能把其说成完整状态Def–Use覆盖已经实现。

**25.6 测试、原实验保护与早期失败记录**

最终联合命令：
~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests scripts/DFG/state/tests scripts/DFG/state/stage_f/tests scripts/DFG/state/stage_j/tests scripts/DFG/state/stage_k/tests scripts/DFG/experiments/stage_k_pilot/tests tests
~~~
421通过、0失败/跳过；包含19项新增测试、之前DDG测试和25项原项目回归。31条既有DGL/TensorBoard distutils和NetworkX read_gpickle弃用警告。测试用现有mando环境，不升级依赖。

保留早期测试日志：profile_tests_001为1失败/10通过，原因是最初夹具误以为普通require必触发全函数回退；根据实际实现改成确有终止语义的revert分支，保留参数/后继/图不变量断言。targeted_tests_002为1失败/13通过/5错误：诊断字段name应为call_name，另schema单元夹具不应调用要求非空验证划分的监督入口，改为直接验证registration；没有放宽生产划分规则、删除测试或伪造通过。

历史H1只读归档验证52新增＋8复用=60；H2为26新增＋4复用=30，均通过。旧plan/seal、输入、初始化、权重和运行源码不变。没有执行solc编译；合成样例仅验证解析和静态语义，不将tree-sitter解析成功称为编译验证。

**25.7 正式训练、实际结果与资源**

四次正式拟合均attempt_001成功，0训练失败/重试/OOM；prepare、run、verify、summarize全部返回0。8份best/last checkpoint重载后预测逐值一致，独立冻结标签复算与训练输出指标相同，没有训练/评分时创建参数、非有限loss或标签身份错位。

主结果（CV validation，fold0；单位%）：
| 任务 | B0 Buggy-F1 | B1 Buggy-F1 | 差值pp | B0 Macro-F1 | B1 Macro-F1 | 差值pp |
|---|---:|---:|---:|---:|---:|---:|
| 重入节点best | 99.648712 | 99.590404 | −0.058308 | 99.519478 | 99.439149 | −0.080329 |
| 访问控制节点best | 99.111901 | 99.111901 | 0 | 99.163486 | 99.163486 | 0 |
| 重入节点last | 99.648712 | 99.590404 | −0.058308 | 99.519478 | 99.439149 | −0.080329 |
| 访问控制节点last | 99.111901 | 99.288256 | +0.176356 | 99.163486 | 99.330648 | +0.167163 |

重入best的混淆矩阵[tn,fp,fn,tp]：B0[489,2,4,851]，B1[488,3,4,851]；访问控制best两者均[316,2,3,279]。Precision/Recall详见results.csv。重入best只有buggy_28.sol原node17439由正确转误报；last新增误报在buggy_47.sol node9332。两种checkpoint的F1相同不代表错误节点完全相同。访问控制best没有离散类别变化，last纠正mapping_write.sol node12963的一个误报；不以last替代主best。

两任务全部1346/600验证节点概率均发生变化（阈值1e-8）；best平均绝对概率差分别0.019149/0.000942，最大0.404510/0.072442。概率改变不等于检测提升，不把新增边范围外的差异强行归为局部语义因果贡献。文件身份带cohort、原nodeID和source SHA，明细在prediction_changes.csv、training_audit.json。

| 任务/变体 | 实际epoch数 | best/last（0基） | 参数量 | fit耗时s | peak allocated/reserved MiB | 整卡最低free MiB |
|---|---:|---:|---:|---:|---:|---:|
| 重入B0 | 31 | 24/30 | 4559794 | 225.171 | 1761.157/1906 | 65 |
| 重入B1 | 29 | 21/28 | 4559794 | 202.536 | 1761.376/1904 | 85 |
| 访问控制B0 | 22 | 17/21 | 4592626 | 110.486 | 1151.892/1254 | 742 |
| 访问控制B1 | 22 | 17/21 | 4600834 | 110.076 | 1162.323/1262 | 732 |

四fit耗时合计648.2695秒（约10.80分钟），不含准备/进程启动/外层验收；受显存竞争及不同早停轮数影响，不能据此比较算法速度。启动前GPU可用，实际运行RTX3050 Laptop 4GiB单模型串行，未代关Windows程序或改变配置。重入schema没有新增canonical，参数量不变；访问控制多一个canonical，新增8208参数，需计入解释。

**25.8 关系训练支持与接入核验**

以下均为该关系所有canonical的train/val实例数：
| 任务/变体 | DATA_DEF_USE | STATE_DEF_USE | STATE_ACCESS_ORDER | EXTERNAL_CALL_BEFORE_STATE_WRITE |
|---|---:|---:|---:|---:|
| 重入B0 | 1630/264 | 1/2 | 711/118 | 457/90 |
| 重入B1 | 1630/264 | 2/2 | 1292/215 | 959/143 |
| 访问控制B0 | 2611/225 | 4/0 | 12/4 | 0/0 |
| 访问控制B1 | 2611/225 | 5/0 | 58/4 | 0/0 |

四fit共87个增强canonical记录（包括DATA_DEF_USE），都有训练实例，并在至少一个epoch观察到有限非零message梯度；无训练支持canonical=0。本批能排除“新边只存文件没进入模型”的情况，但不能由此证明语义完整或性能有效。各epoch完整记录在gradient_audit.json，汇总training_support.csv。

访问控制新增47条状态边全部在train，本折val的状态边实例数未增；新增信息与历史主要错误不重合。重入val虽新增150条状态边，主结果仍多1误报。支持当前整体恢复主要改变概率/优化轨迹，而不是该折已证实纠错收益。

**25.9 结论、后续建议与未执行事项**

已完成DDG整体构图、版本域修复、模型接入及一次整体成对验证；没有为了改善分数继续改标签/模型/折或逐小点训练消融。当前不能宣称已得到稳定有效的创新：主结果重入小幅下降、访问控制持平，覆盖改善与分类改善必须分开。单折B0本身已99%以上，不能与旧10折均值约96%直接比较；既有困难文件未进入本折val，不能宣称其问题解决。

下一步若评估整体方案，固定当前B0/B1后完成同一批配对的原10折即可，不需要继承、modifier、每个版本条件各跑一套；本批fold0可经输入/代码/初始化身份核验后复用，其他折使用预先固定规则。本轮尚未执行剩余18个配对折或合约级新训练，也没有新seed、七类全量、独立测试或控制依赖实现。

访问控制真正缺失的“权限检查约束敏感操作”仍属于控制依赖，不可通过增加STATE_DEF_USE/顺序边冒充；复杂storage别名、mapping表达式、外部import、参数modifier及跨函数摘要也未变成完整支持。这些是明确范围，不为追求支持率取消回退。仍未进行新solc编译或独立人工Oracle。

新增产物级audit_training_results.py仅从封存fit/预测导出training_support.csv、resource_summary.csv、training_audit.json；不修改训练源码、输入或指标规则。主要交付为STAGE_K_RESULT_REPORT.md、change_record.md、plan/seal、四任务prepared图、两个任务成对初值、4次完整fit、results/paired_results/prediction_changes、coverage/graph_summary、测试及H1/H2日志。保护与交付清单见protected_after.json、delivery_manifest.json。

**25.10 已执行命令与维护方式**

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONPATH="$PWD"
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m scripts.DFG.experiments.stage_k_pilot.control prepare
python -B -m scripts.DFG.experiments.stage_k_pilot.control run
python -B -m scripts.DFG.experiments.stage_k_pilot.control verify
python -B -m scripts.DFG.experiments.stage_k_pilot.control summarize
python -B scripts/DFG/experiments/artifacts/paper_kfold/stage_k_v1/audit_training_results.py
~~~

上述prepare和run已完成，现有prepare拒绝覆盖；查看结果只需verify/summarize，不必重训。成功fit有收据后run校验复用；失败必须查明原因再显式整fit重试，不是epoch断点续训。命令的精确HEAD/源码检查仍保留；未来归档提交不能通过修改旧seal绕过。两工作树训练变更文档和HANDOVER均仅追加，旧197项代码/用户文件SHA保持，旧90个正式结果通过归档核验。实施与分析AI：Codex。


## 26. 2026-10-19 原始HCG与整体DDG完整交叉验证接入（Codex）

**26.1 目标、基线和本轮范围**

用户授权按推荐实验设置执行下一步。本轮比较无本地DDG的作者原始CFG+CG（HCG）与同图增加冻结Stage K整体DDG（HCG_DDG），覆盖重入、访问控制的合约级5折和节点级10折，共30个配对折、60次正式拟合。两个分支都复用现有梯度、eval及best保存修复；无DDG基线不表示恢复原仓库的训练缺陷。原E0/E1/E2/E3及Stage K B0/B1不覆盖，作为历史结果单独保留。

旧Stage K B0是E3b，并非无DDG的HCG；其B1共同参数以E3b为锚。本轮重新以HCG为锚做语义配对，不能因为使用相同增强图或相同fold0就复用旧B1成绩。因此按60次新拟合准备，并逐项记录旧B1和新HCG_DDG初值摘要差异。没有为各个小恢复点新增训练消融，不增加类别、seed或模型关系。

开发树/home/zhao/SmartContract/ge-sc-llm-ddg-v11，HEAD 021a6f55ac9e3f94fc70feb441ff48b51b6a92ea；原树HEAD f3dfc17908029355c5fc45d6d3932f203068fcf5。无pull/checkout/reset/commit/push。修改、执行和分析AI：Codex。

**26.2 最小接入文件与原因**

新增scripts/DFG/experiments/overall_cv/，没有修改旧DDG、Stage F/J/K、HGT、tokenizer、原训练脚本或标签：

- common.py、prepare.py：独立60任务矩阵、只读旧批次摘要核验；从H1/G已有manifest查原E0图、作者标签、逐任务有效配置和原折清单，从Stage K交付清单验证整体增强图；保存30对CPU未训练初值、图/特征/标签/schema/监督绑定、plan/seal。
- checks.py：逐节点属性及原MultiDiGraph边键/属性完全相同；HCG禁止已有本地DDG；共同参数按node type/canonical relation语义相等且存储独立；拒绝初值、收据、结果、有限loss及checkpoint身份错配。
- checkpoint.py、training.py：复制已有函数对象的代码体，仅绑定本批checkpoint版本与HCG/HCG_DDG身份；没有改优化器、scheduler、loss、早停、HGT前向或评分的数值路径，也没有修改旧模块globals。
- worker.py、control.py：单GPU单模型，恢复每折fit_seed，从冻结未训练初值开始；先验收首个配对折，再依次完成四任务。成功核验复用，失败保留attempt并要求显式重试；不自动改超参、缩图、换CPU或无限重试。
- report.py：从原冻结标签和预测按task/fold/file/node identity独立复算，输出best/last、逐折均值/样本标准差、差值、OOF、纠错/新增错误、源SHA、关系支持/梯度/资源；源码重复片段只做训练后的描述统计，不改变划分。
- tests/test_overall.py、tests/__init__.py、README.md及包初始化：接入测试和实际运行/恢复说明。

新批次scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/。历史计划、seal和结果只读；归档校验检查旧记录的实际源码/输入哈希，允许新增旁路文件，但不修改旧seal使其通过。

**26.3 实验计算与评分规则**

沿用paper_kfold原文件折：完整固定任务图前向、train监督；同一val选best/早停并评分，全部称CV validation。节点任务仍按HCG节点计分，不混为去重源码行F1或独立测试。合约按文件监督；增强图新关系通过既有正向adapter注册，HCG不注册空DDG关系。

512维inside_token保持现有CodeT5p-770m tokenizer ID特征，不调用LLM encoder。HGT hidden128、2层、8头、dropout0.2/use_norm，最多50轮、patience7、delta0.001。best严格最低验证loss，last另报；结果下降不是剔除或改规则理由。

合约沿用initial_lr0.0005/max_lr0.01、div_factor20、weight_decay5e-6；节点沿用0.0002/0.005、div_factor25、weight_decay0。OneCycle50步、final_div_factor1、原Adam和每轮step保持。每折构造/配对/fit seed公式沿用现有策略，配对算法版本与实验版本分别绑定。不同任务配置从manifest逐项核验，不按报告简述统一学习率。

**26.4 测试和早期失败**

新增定向测试首轮7失败/16通过：合成node标签夹具遗漏原get_node_label要求的category字段；补全reentrancy类别后23通过，4条既有DGL弃用警告。没有改生产标签逻辑、删除测试或放宽关键断言。CPU节点/合约真实两轮训练验证共同初值、梯度、best/last重载预测和评分期间无新参数。

联合回归命令覆盖scripts/DFG/tests、state各阶段tests、experiments/tests、e23_pilot/e23_cv/e23_h2/stage_k_pilot/overall_cv tests及原项目tests：727通过、1失败、31条既有DGL/TensorBoard/NetworkX警告，0跳过。唯一失败是旧formal测试将资源报告绑定的原工作树路径与当前开发树路径比较。formal.py及该测试与原树字节相同；在报告所属原工作树重新运行同一测试，1通过、4条DGL警告。不修改旧资源报告、旧路径规则或测试来伪造全绿。日志integration_tests_001/002、regression_tests_001、historical_test_original_tree_001均保留。

**26.5 执行状态与风险**

本条写入时接入测试完成，真实图不变量及CPU初值准备进行中；正式训练和最终指标将在后续条目补充，不提前声称完成。计划先执行run --first-pair，验收后run复用该对并继续剩余58次。RTX3050 4GiB要求串行；按实际显存/时间记录，遇OOM或输入/数值错误停止，不自动降配。训练期间冻结运行源码，不用修模型来改善本批F1。


**26.6 封存完成、真实输入和首对验收**

30对未训练初值已完成并通过独立存储/共同参数语义一致性检查。新plan封存186份运行源码及503项输入/初值/配置等资产，60项任务；四个原始HCG在CPU上与既有原分类器的state、特征、端点、节点行次序及eval前向逐值一致。旧K两个节点B1初值与本批HCG_DDG摘要均不同，reused=false，未复用历史成绩。

| 任务 | 原节点 | 原CFG+CG边 | 增强后边 | DATA_DEF_USE | STATE_DEF_USE | STATE_ACCESS_ORDER | EXTERNAL_CALL_BEFORE_STATE_WRITE |
|---|---:|---:|---:|---:|---:|---:|---:|
| 重入合约 | 18312 | 19267 | 25519 | 3561 | 9 | 1573 | 1109 |
| 访问控制合约 | 13432 | 15538 | 19691 | 4032 | 14 | 107 | 0 |
| 重入节点 | 12036 | 11710 | 16217 | 1894 | 4 | 1507 | 1102 |
| 访问控制节点 | 7710 | 8840 | 11743 | 2836 | 5 | 62 | 0 |

两分支节点属性（含源码映射、作者标签、token）以及全部原基础边键和属性相同。状态DU仍稀少：重入节点10折中8折val无该关系，访问控制节点6折val无该关系；访问控制两个粒度都没有调用→写入边。逐折支持见frozen_relation_support.csv；该统计不改变输入或剔除折。

首个正式重入合约fold0在2026-10-19 11:44:42–11:51:42 UTC执行完成，控制器419.42秒，两fit实际训练161.51/169.73秒。HCG与HCG_DDG的best BF1均84.6153846、MF1均86.0576923；best_epoch均6、last_epoch均13（零基索引）。last BF1分别92.8571429/88.8888889，仅辅助报告，不能替换best。4份checkpoint重载预测一致，主干参数更新非零，增强322项epoch-canonical记录具有训练支持且message梯度非零有限，无新参数创建、数值错误或OOM。

首对allocated峰值2103.30/2709.92 MiB，整卡minimum free44/58 MiB。Windows只读显存查询主要显示WSL训练分配，未发现明显其他GPU程序竞争；未关闭程序或修改配置。一次只读状态工具审批超时重试成功，不涉及训练失败或重训。

首对通过first_pair_acceptance.json与first_pair_review.json验收后，controller_full.log已开始继续剩余58次，复用本批刚验收的两fit；每项任务完整性和独立指标复算通过才进入下一项。此处不提前声明60次完成。原176项受保护代码和用户文件摘要不变，四份文档仅追加。新增报告生成器render_report.py位于本批产物目录，不属于训练计算；只在完整结果验收后输出正式报告。


**26.7 全部正式训练完成与最终验收（2026-10-20 UTC，Codex）**

已完成本批60次新正式拟合：重入/访问控制合约各10次、节点各20次；均为attempt_001，无训练失败、重试或OOM。首对验收后继续剩余58次，每项任务通过完整性和从冻结标签独立复算后才进入下一项。原K/H1/H2成绩未混入，也没有重跑来挑选分数。

final_verify.log及final_summary.log记录60项验收；final_selection_audit.json再次核验60项完整history、实际配置、严格最低val loss对应best和120份checkpoint重载一致。训练前向/评分没有临时创建参数，主干参数均更新。完整报告OVERALL_CV_RESULT_REPORT.md位于overall_cv_v1独立批次。

**26.8 主结果与辅助结果**

以下是CV validation的等权折均值（百分数）；节点按HCG节点口径。逐折Precision/Recall、混淆矩阵、样本标准差、OOF及来源身份在对应CSV完整保存。

| 任务 | 折 | HCG BF1 | HCG_DDG BF1 | ΔBF1(pp) | HCG MF1 | HCG_DDG MF1 | BF1升/平/降 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 重入合约 | 5 | 94.1593 | 94.1593 | +0.0000 | 94.3452 | 94.3452 | 0/5/0 |
| 访问控制合约 | 5 | 93.5590 | 93.5590 | +0.0000 | 93.8316 | 93.8316 | 0/5/0 |
| 重入节点 | 10 | 96.0580 | 96.1027 | +0.0447 | 96.0088 | 96.0441 | 7/1/2 |
| 访问控制节点 | 10 | 95.9723 | 95.8887 | -0.0837 | 96.8764 | 96.8063 | 2/4/4 |

best的实际错误变化：

- 重入合约：纠正0个错误、新增0个错误、类别变化0个、概率发生浮点变化142个。
- 访问控制合约：纠正0个错误、新增0个错误、类别变化0个、概率发生浮点变化114个。
- 重入节点：纠正33个错误、新增34个错误、类别变化67个、概率发生浮点变化12036个。
- 访问控制节点：纠正2个错误、新增7个错误、类别变化9个、概率发生浮点变化7710个。

last独立辅助结果，不代替预定best：

- 重入合约 last：BF1 90.8867→91.0147；MF1 90.8508→90.8236。
- 访问控制合约 last：BF1 85.9247→84.6752；MF1 85.8996→84.0706。
- 重入节点 last：BF1 97.1504→96.9109；MF1 97.3135→96.9888。
- 访问控制节点 last：BF1 95.8010→94.1517；MF1 96.6133→95.2075。

两个合约任务best均没有离散分类收益。重入节点平均BF1仅提高约0.0447个百分点，纠正33个同时新增34个错误；困难fold8约67%，并非所有折都99。概率变化、等权折均值和pooled OOF必须分别解释，不能选择对增强更有利的一种口径。访问控制节点best BF1下降0.0837个百分点，MF1下降约0.0701个百分点，2折上升/4折持平/4折下降，纠正2个而新增7个错误；其buggy_18和buggy_26分别仍87和42错误。两个节点任务的pooled OOF BF1都略降，本批不支持整体DDG有稳定收益。

**26.9 覆盖、限制、资源与时间异常**

增强仅为冻结四类正向关系；节点STATE_DEF_USE仍仅重入4条、访问控制5条，访问控制没有EXTERNAL_CALL_BEFORE_STATE_WRITE。逐canonical/fold训练/验证支持、梯度及未见关系审计在relation_support_gradients.csv。少量状态DU和大量模板重复是结果解释的线索，不足以单独证明无收益的因果原因。原标签冻结保证受控对比，不能据此证明作者ground truth完全正确。

困难文件按cohort/source SHA区分：重入buggy_18的best错误252→252；buggy_36为60→57。访问控制buggy_18/26及所有变化文件见file_error_analysis.csv及最终报告，不改标签、不删除困难文件。

全部fit计时器秒数合计9466.39，最大allocated 2709.92 MiB、reserved 2878.00 MiB；最小整卡free 19 MiB。资源表保留每折参数量、轮次和真实记录；各分支新增参数/聚合/优化轨迹也变化，不能把分差完全归为纯依赖语义效应。

监控UTC时间从2026-10-19 14:21:20跳至2026-10-20 01:03:45，间隔约38545.86秒，同一个访问控制节点fold2/HCG进程仍继续且最终正常完成；其单调计时训练秒数230.98。原因未证实，可能涉及宿主机挂起/调度或时钟行为。未从记录中擅自扣除时间、重训或更改配置；不把批次墙钟或资源秒数当作排除系统影响的速度基准。详见timing_gap_observation.json。

**26.10 交付、复核与停止边界**

新增报告/验收辅助脚本仅置于overall_cv_v1产物目录，不进入冻结训练源码。report.json、fold_results.csv、fold_statistics.csv、paired_deltas.csv、paired_statistics.csv、pooled_oof.csv、oof_predictions.csv、prediction_changes.csv、file_error_analysis.csv、relation_support_gradients.csv、resources.csv、code_overlap.csv以及各fit best.pt/last.pt/日志/收据均保留。

测试结论沿用26.4：新23项通过；联合727通过/1个历史路径测试失败，同一旧测试在原资源所属工作树通过。没有为取得全绿修改历史资源或运行代码。历史失败日志和解释保留；最终保护检查另见protected_after.json，交付摘要见delivery_manifest.json。

复核命令（已执行）：

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
python -B -m scripts.DFG.experiments.overall_cv.control verify
python -B -m scripts.DFG.experiments.overall_cv.control summarize
~~~

训练入口仍为python -u -B -m scripts.DFG.experiments.overall_cv.control run；成功收据验收后复用，失败需明确重试，不能称epoch断点续训。精确HEAD/资产绑定保持；未来归档提交后需要适用的只读历史验证，不能改旧seal。

本轮结束在完整原HCG与整体DDG对照、分析及文档交付。没有启动新seed、七类全量、独立测试、新关系、完整storage/跨函数分析或逐小点消融。下一步应由完整误差证据决定，不能仅为追求提升继续堆关系。实施、执行、核验与分析AI：Codex。


## 27. 2026-10-20 合约best持平的错图/权重/DDG生效复核（Codex）

**27.1 背景与范围**

用户质疑加DDG后两个合约任务best全部持平是否执行错误。本轮未修改模型或训练代码，也未重新训练；新增推理复核脚本和记录位于开发树scripts/DFG/experiments/artifacts/paper_kfold/overall_ddg_recheck_20261020_v1/。原overall_cv_v1与历史seal只读。

**27.2 实际检查与结果**

沿worker真实variant图路径、StageG模型构造、HGT canonical relation消息和mean/stack合约池化检查。按原manifest重新构造20个合约best模型，核验两组图/权重SHA不同、绑定正确；原CUDA设备重算20份预测与原导出概率逐值一致。共同参数训练后每折至少707/734个张量不同，排除同一权重重复使用。参数量分别4,526,962→4,715,746、4,510,546→4,723,954。

142个重入、114个访问控制合约best概率全部变化，但类别全部不变。平均绝对概率变化1.20915/0.73557个百分点。真实例：spank_chain_payment.sol 76.4798%→87.4936%仍为漏洞；reentrancy_bonus.sol 44.4136%→40.8495%仍漏报。F1不对概率变化连续响应，不能据同F1断言未接入。

**27.3 消息敏感性诊断**

10个增强best仅在内存中将DDG relation_msg切片置零，保留图/schema和其他参数，再eval并恢复原state_dict。10/10 logits改变，最大logit变化重入每折0.21835–1.36658、访问控制0.21268–0.59024；10/10恢复后前向逐值恢复。类别仍不变。该检查证明消息参与数值前向；不能当作重新训练的无DDG模型或新正式消融，因为关系结构/聚合分母保留，训练历史不同。没有新fit。

**27.4 首次失败、边界及交付**

第一次CPU重算概率偏差3.477931e-5超过预设1e-5容差而停止，保留recheck.py/run.log；不是正式训练失败。转为原CUDA设备检查，未放宽容差，20次误差均0。新脚本recheck_gpu.py、recheck.json、probability_examples.csv、raw_probability_audit.json、cpu_attempt_note.json和README给出完整证据。前后冻结plan/seal/report/delivery及20份best SHA保持不变。

本轮排除了已检查范围内的错图/同权重复用/导出不一致/DDG消息完全无前向作用。没有证明完整DDG语义无缺陷，也没有证明方案稳定有效。原主结论不变，未调整阈值、选last取代best、改标签或重训。详细解释见新目录README。实施、核验与分析AI：Codex。

## 28. 2026-10-20 下一步设计前的完整性复核与标签争议交叉检查（Codex）

**28.1 目的与范围**

用户要求先检查方案与数据，再设计下一步。本轮只读复核overall_cv_v1，没有修改冻结DDG/HGT/tokenizer/标签/划分/训练器或重训。新增记录位于开发树scripts/DFG/experiments/artifacts/next_step_review_v1/。UTC为2026-10-20，用户America/New_York当地仍2026-10-19。

**28.2 新建文件、实际执行与复核**

新增audit.py独立使用标准库读取JSON/CSV，调用已审查的control verify（哈希/JSON验收，不反序列化图或模型）。60 fit/30对验收通过，186源码/503冻结资产与收据产物未漂移；120组best/last混淆矩阵和四指标、16组均值/样本标准差、16组pooled OOF独立复算全部一致。逐文件/节点身份、OOF唯一性、train/val无交集、每文件恰好一个验证折、实际配置与初值/图绑定、最低loss best和末轮last均核验。

685条canonical×fold记录中668条有训练支持，均有正的message梯度；17条无训练支持保留，不强制非零梯度。两个分支节点属性摘要相同，初始化共同语义参数一致审计通过。原120份checkpoint回放证据由收据哈希认证，本轮没有重做GPU前向。

首次audit把attempt_001.log当作attempt目录，已保留原脚本与失败JSON，修复为只计目录，仍要求每fit恰好一个attempt；不是训练失败或降低断言。没有修改历史结果。

**28.3 新发现：错误与既有标签分歧重合**

按cohort/file/author_node_id/node_type/source SHA匹配现成public_endpoints_verified_v1差异记录；不更改任何target或重算替代标签成绩。

- 重入作者/public分歧216节点；HCG 428错误中199在分歧处（46.50%），整体DDG429错误中仍199在分歧处。
- 访问控制分歧137节点；HCG211错误中125在分歧处（59.24%），整体DDG216错误中仍125在分歧处。
- 重入buggy_18为214分歧/197计错，0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol为2/2；访问控制buggy_18为93/83、buggy_26为42/42、parity_wallet_bug_2为2/0。
- 两个buggy_18按类别和SHA区分。public注入区间不是人工证明的最小漏洞语句；分歧不等于直接判作者或本地全错。

已有code_overlap.csv汇总：重入验证正例6556/6570（99.79%）、访问控制2948/2977（99.03%）在训练折存在相同node_type+code。是节点文本重叠，不是完整合约重复比例，也不是单独证明记忆效应。文件级分割正确与跨模板泛化不足可以同时成立。

**28.4 下一步设计与不执行事项**

详细方案NEXT_STEP_DESIGN.md：先对上述5个类别/文件对象做有限、可追溯的标签与任务语义核验，争议侧表与正式标签分开；冻结整体DDG为v1。无争议案例若证实guard执行约束缺失，再评估单一受限CONTROL_DEPENDENCE候选，复用语义CFG/投影但明确属于DDG+控制依赖，不冒充状态Def-Use。先做语义和不变量验收，不为每个小点跑F1。

如节点/标签/特征/划分/配置/共同初始化完全一致，后续可引用现有HCG与整体DDG结果，只新增候选30次（其中四任务fold0可计入）；如标签等改变则不能复用旧训练基线。合约与节点任务均保留。额外跨模板协议单独报告，旧CV不能称独立测试。

本轮未执行新训练、全量标签重建、控制依赖实现、额外seed/七类扩展或重复全部DDG单元测试。已有不利结果和历史测试失败记录保留。实施/审查/分析AI：Codex。


## 29. 2026-10-20 buggy_18跨MANDO-HGT与MANDO-LLM标注核验（Codex）

**29.1 背景与范围**

用户要求先确认buggy_18在两个版本的作者标注是否一致。本轮分别检查重入、访问控制同名但不同SHA的文件。新增审计脚本、JSON和报告仅在开发树scripts/DFG/experiments/artifacts/buggy18_hgt_llm_comparison_v1/；没有修改构图、模型、标签或训练。

**29.2 来源与执行**

HGT HEAD f791a855cd58b52420c7690200a90a415a449e1c；两类源码/CSV/标注JSON共六文件均与git show HEAD字节一致。每类HGT、LLM source_files、SolidiFI源码字节相同。原JSON去重行集合与CSV注入区间并集一致。先核验作者CFG+CG图冻结SHA，再用已有安全白名单读取器读取；字符来源映射换算原始标注，未用常数偏移。两类全部断言通过，全部输入前后SHA不变。

**29.3 结果及口径**

重入HGT原始324个不重复标注行，换算后300；LLM内嵌82，交集41，另41条越界，最大840（当前原始源码738行槽、预处理525行）。访问控制原始148/换算148，LLM46，交集23，另23条越界，最大687（原始560行槽、预处理371行）。

同一LLM HCG节点及端点规则下，重入424节点作者正例35，HGT标注复放249，214节点标签不同；访问控制284节点17对110，93节点不同。作者自身内嵌标注复放零差异。249/110不是HGT原生Slither图节点统计。HGT源码control_flow_graph_generator.py:46–47、60–81使用Slither source_mapping行集合交集，不应把其原生范围表示等同LLM端点表示。

**29.4 结论、未解项与保护**

已确定两个版本资产标注不同，排除本轮DDG改动导致该差异；无法确定作者历史生成时具体是源码/标注版本、坐标转换还是发布流程差异。没有把CSV整个注入区间认定为最小漏洞语句真值，也没有替换正式标签或重算更有利成绩。

完整证据README.md、comparison.json、audit.py。文档仅追加，本轮无新训练/编译/下载，未重复运行DDG测试。辅助检索因WSL没有rg失败后使用Python只读检索完成。实施、核验与分析AI：Codex。


## 30. 2026-10-20 五文件源码、标注与坐标定点核验（Codex）

**30.1 范围、新增文件与保护**

按用户指定“先核验数据”阶段，检查重入buggy_18、0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839；访问控制buggy_18、buggy_26、parity_wallet_bug_2。新增开发树scripts/DFG/experiments/artifacts/targeted_label_review_v1/内的audit.py、review_details.py、五组逐文件JSON/Markdown、audit.json、范围/类别复放、测试日志和TARGETED_LABEL_REVIEW.md。没有修改DDG/HGT/tokenizer、图、正式标签、训练计划或checkpoint。

**30.2 来源、节点与坐标验证**

作者融合图SHA与既有manifest一致，使用已有受限图读取器。SmartBugs提交230e649、SolidiFI提交4b0573e、HGT提交f791a855的相关源码/CSV/JSON均通过git show HEAD字节核验。五个本地source_files与公开源码相同。1127节点中1032普通节点AST锚点、正文、端点精确对应；95合成节点按历史marker核对，marker不等于真实执行行。原始/预处理存活token一致，两套来源映射对本轮标注结果一致。输入前后SHA不变。

**30.3 分类结果与证据**

同图同端点“作者正例/公共复放正例/不同节点”：重入buggy_18为35/249/214，0x627为1/1/2；访问控制buggy_18为17/110/93，buggy_26为21/63/42，parity为0/2/2。共353差异，352个0→1、1个1→0。内嵌作者记录复放零差异，不等于标注与源码正确。

三个SolidiFI文件作者标注有41/23/19条越界，最大840/687/687，超过原源码738/560/233行。0x627作者记录为unchecked_low_level_calls、processed11，挂在changeOwner；公共重入raw94→processed75落在调用if。另一类别按其源码raw44→processed32，不能跨路径套用原始行号。HGT原basename-only最后匹配函数已复放确认会选外来类别，但不能证明LLM历史执行链或解释11。parity两个函数节点9496/9499真实存在，命中公共raw226/233，作者标签却全空，不是构图遗漏节点。

**30.4 CSV边界、范围策略与语义限制**

105条区间中7条有可见函数边界疑点。旁路候选只核验影响：重入补117..120，只新增余额清零节点2709；访问控制buggy_18移除224行普通allowed声明、补227行模板语句等，一减一增2节点，正例仍110；buggy_26补106行闭括号，无节点变化。合计3个节点变化，不能解释353分歧，未写回CSV或正式标签。

普通节点端点换成整段跨度仅额外增加13个正例，合成marker保留；这不是新训练输入。注入区间不等于最小漏洞根因。部分tx.origin模板只有require；to.call.value(amount);缺少后续call执行参数列表，不能称已发生外部转账。参考历史Solidity文档与SWC-106做源码静态审阅，未执行solc或EVM利用验证。

**30.5 测试、失败记录与交付**

已有标注管线32测试全部通过，0失败/跳过，无警告。五文件核验断言通过，与历史label_differences逐节点一致。范围审计首次因新增脚本字典少闭括号而语法失败，保留原脚本/log，仅补括号后通过，未放宽断言。文档写入先遇Windows命令长度限制、默认沙箱UNC拒绝访问；改为获准的原生UTF-8写入，正式数据没有改变。文档追加保留原字节前缀。

该阶段完成证据定位，但发布坐标产生原因、parity挂载缺失原因、注入区间语义仍有未决项。不能宣布标签全正确，也不能将相关错误全归因DDG。若采用修订标签，需要独立cohort并重新核验基线；本轮没有新训练、推理、关系扩展或全量DDG测试。详见TARGETED_LABEL_REVIEW.md。实施、核验与源码级审阅AI：Codex。

## 31. 2026-10-20 固定作者图上的DDG收束与下一增量设计（Codex）

**31.1 用户决策、范围与新增文件**

用户决定暂不追查标注差异，继续基于作者下载图尽快完成DDG方案。本轮只读核对开发HEAD 021a6f55、Stage J/K能力、整体CV全折结果和原设计，新增开发树scripts/DFG/AUTHOR_GRAPH_NEXT_STAGE_DESIGN_2026-10-20.md。算法、作者图/标签/token、模型、计划/seal和训练不变；没有构图、新fit或GPU前向。

**31.2 已完成能力与研究结论**

当前v1已包含四种正向关系和受限继承/modifier/版本覆盖恢复；工程闭环已完成，完整Solidity分析尚未完成。原HCG→整体DDG的best BF1：两合约94.1593/93.5590均持平；重入节点96.0580→96.1027，访问控制95.9723→95.8887；没有稳定改善证据。使用完整5/10折而非99附近单折，继续保留作者标签和全部样本，标注争议仅列限制。

**31.3 推荐增量及代码结构差异**

推荐只评估一个受限CONTROL_DEPENDENCE整体候选，方向为条件→受控语句，保留v1四关系。它明确属于DDG＋控制依赖，不能称为新的纯Def–Use。规则不依赖漏洞类别/标签/预测；支持已确认guard、普通if、提前退出及现有前置modifier子集，其他函数本层无残留回退。

本轮核实：semantic_cfg.py/models.py没有所需require失败出口、统一EXIT和完整分支元数据，必须旁路补分析IR，不能改旧DU/模型CFG。stage_f/model_adapter.py仅白名单四关系保持正向，新控制边需独立最小adapter注册，避免意外reflect。overall_cv/common.py扫描当前整个DFG的.py集合，新增文件会触发旧Runtime drift；后续须按旧plan清单做只读归档验证，旧seal不改。上述均为本轮设计发现，尚未实施修复。

**31.4 验收、训练数量和复用条件**

先一次整体语义测试与四任务图覆盖/不变量验收，不为每个小点训练。无可投影新信息或正确性失败时不启动训练。若通过，核验复用旧HCG和HCG_DDG结果，只新增HCG_DDG_GUARD 30fit（四任务fold0共4次计入，余26）。从保存的未训练HCG_DDG初值按类型/关系对齐共同参数，新关系独立确定性初始化，保留原fit_seed及各任务数值规则；禁止用best/last继续训练。无法满足绑定则先报告，不静默混用旧结果。F1下降不作为删折或终止条件。

**31.5 文档、参考与未执行事项**

详细设计含模块目录建议、后支配/guard反例、modifier上下文、冻结图保护、关系支持/资源和停止条件；参考Solidity 0.5.17控制结构、0.4.26 modifier和LLVM/Clang官方ControlDependencyCalculator。本轮仅文档新增/追加，未运行新测试；历史测试/梯度证据明确为引用，不声称本轮复跑。原HCG/HGT/tokenizer/标签/代码和用户修改保留，不进行Git写操作。不自动训练、跨函数摘要、反向DDG或其余五类。实施与分析AI：Codex。
## 32. 2026-10-20 作者HCG上受限控制依赖整体候选实现（Codex）

**32.1 授权、修改范围及旧代码保护**

用户要求按上一轮推荐方案完成下一阶段。本轮在开发树ge-sc-llm-ddg-v11新增scripts/DFG/control_dependency/和experiments/guard_extension/，产物独立存放artifacts/paper_kfold/guard_extension_v1。保留原作者图、标签、512维inside_token、文件折、四类旧DDG、HGT核心及训练数值规则；261份旧DDG/模型/用户代码SHA保护清单已建立并复查无变化。不执行Git写操作，不下载编译器，不重新标注。

**32.2 语义和投影实现**

新models/cfg/analysis构建旁路控制IR，显式正常/异常/统一出口、可靠内建绑定、if/else、require/assert、提前return/revert及既有受限前置modifier；已知true/false裁剪，不处理完整循环/发散/隐式VM异常。采用后支配直接控制依赖，不增加传递闭包。虚拟出口不进入模型。未知语义函数回退不提交部分控制fact，并保留原图和v1 DDG。

projection/pipeline复用既有精确AST源码对应，追加一种正向CONTROL_DEPENDENCE；不猜最近行、不增加变量节点、不读取标签或预测决定连边。同端点不同relation共存，重复控制边保留多份函数上下文证据。不支持的共享modifier上下文不跨函数串联。缺失原HCG端点的revert/emit仍参与语义控制流，仅不投影该事实。

**32.3 实验接入和历史复用**

新model adapter复用原HGT构造/forward数值函数，显式将CONTROL_DEPENDENCE加入正向关系集合；不改旧adapter。archive按旧plan源码/输入/收据清单核验，旧overall_cv 60fit验证通过，不以新增旁路文件误判旧计算变化，也不改旧seal。新训练FIT复用原函数code对象，只替换新审计和checkpoint绑定。

CPU prepare逐折读取旧HCG_DDG optimizer_steps=0初值，复制全部语义共同参数并检验tensor digest；新关系独立确定性初始化，保留原fit_seed、每任务原学习率/OneCycle、50轮上限、patience7/delta0.001和严格最低val loss的best。新计划仅30个HCG_DDG_GUARD候选；先固定四任务fold0，正确性/资源验收通过后剩余26，旧HCG/HCG_DDG不重训。成功复用、失败留痕并停，不自动降配/切CPU或无限重试。

**32.4 新测试与已修问题**

原语义/模型/项目回归413通过、31条既有warning；新增统一测试最终73通过、4条既有DGL warning，0失败/跳过，总计486用例。首次新增统一测试72通过1失败，发现report把str交给需要Path的安全图reader，修正生产调用后保持原断言通过；001日志保留。

核心早期测试揭示既有grammar把 !msg.sender.send(amount) 错误分组；该形式明确回退，带括号形式的正向控制边断言通过，不宣称修好了grammar。其首次原stdout没有保存，semantic_implementation_notes.json明确为执行观察而非伪造日志。投影初次因TREE_SITTER_LIB_DIR遗漏命中Windows库失败，设置已有Linux库后通过，无安装或依赖升级。未执行solc/EVM，解析验证不等于编译/漏洞利用验证。

**32.5 四任务真实构图和资源预检**

按重入合约/访问控制合约/重入节点/访问控制节点顺序，保持节点18312/13432/12036/7710，新控制边3086/1929/2421/1384，全部增强边28605/21620/18638/13127。实际adapter方向两层新增可达对1690/1096/999/464，新增上下文目标1132/600/745/248；每图8新canonical，全部30折新canonical都有train支持。普通旧关系沿原规则反射，全部增强边正向。

支持/回退函数2325/1063、2264/779、1560/485、1636/322；合约任务文件级回退2/6个原样保留。缺投影事实798/134/730/60均因旧图无独立revert/emit锚点。R buggy18新增74条、AC buggy18/26新增37/29，parity_wallet_bug_2仍0；覆盖不等于F1改善。

初始资源：现有mando PyTorch1.8.1+cu111、CUDA可用，RTX3050 4GiB约3.5GiB空闲；WSL磁盘844GiB空闲。首个任务新增65664参数。实现报告IMPLEMENTATION_REPORT.md、新图build/manifest.json及seal、coverage/invariants/support和build_review.json保存证据。正式训练结果将在本节后追加，当前记录不预报分数。实施、审查与执行AI：Codex。
**32.6 四个正式fold0验收与继续执行（2026-10-20，Codex）**

首批四个fold0是正式拟合，计入30个候选结果，不另算smoke。重入合约、访问控制合约、重入节点、访问控制节点的best Buggy-F1分别84.6154、90.0000、99.6487、99.4652；与同折旧HCG_DDG相比前三个持平任务为两个合约及访问控制节点，重入节点99.8245→99.6487。没有因为持平/下降改变方案或重训。全部best/last重载预测精确一致，无评分临时建参。

除控制器verify外，独立检查history最小验证loss对应best_epoch、末条对应last_epoch；导出类别与二分类概率方向一致。CONTROL_DEPENDENCE的实际监督梯度位于gradient_audit.epochs[].enhancement_relations，而不是兼容旧scalar审计的ddg_relations；四fold0逐轮新canonical message梯度均非零，采集在backward之后、optimizer.step之前，不是weight decay造成的参数变化。见fold0_acceptance.json及fold0_independent_review.json。

四fold0的数值/输入/梯度/checkpoint验收通过后，按冻结顺序执行剩余26次候选；复用这四折和旧60个基线fit。控制器full_controller_001.log记录每次START/VERIFIED/TASK_ACCEPTED。F1并非放行阈值。此处为放行时快照，完整结果另追加。

**32.7 训练期间只读交叉审阅发现的范围边界（Codex）**

control_dependency/cfg.py对address转换的接收者内部表达式未递归核验，健壮性探针address(unresolved()).call("")可能绕过未知绑定回退；已绑定普通调用本来只建模may-return/may-revert，不进行callee终止摘要分析。本轮未编译这些探针，不能宣称语言合法性已验证。

对当前四任务256份唯一源码路径/SHA、10434条函数结果作精确AST核对，仅访问控制合约0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol的handleAllocation/handleWithdrawal命中嵌套接收者调用；两者本批已经整体回退，semantic/projected/published事实均为0。全部已支持函数无命中，因此本批增强图没有受到该缺陷污染。保留为下一版正确性修复项，本批不改封存代码/图/plan，也不因此删除函数或重选实验。证据readonly_receiver_review.json。

旧modifier_context内control_dependence_edges=False来自前置modifier旧阶段元数据，不能用作当前新控制边是否存在的判定；当前事实/边/训练按新relation及证据读取。该字段语义歧义留档，未篡改旧证据。当前仅显式控制/异常子集，不是完整Solidity/EVM控制依赖。

只读结果格式检查曾把预测JSON列表当字典调用items而报错，随后按实际列表读取完成验收；该辅助读取不写模型/预测，不是训练失败。原261个代码文件SHA再次全部一致。
**32.8 完整30次候选训练与90结果联合验收（2026-10-20，Codex）**

四fold0数值/资源验收通过后，按冻结顺序完成余26次，合约各5折、节点各10折。新增HCG_DDG_GUARD共30次正式fit，全部attempt_001，0训练失败、0重试、0 OOM；只读复用overall_cv_v1的HCG/HCG_DDG各30结果，合计90模型、180组best/last评分。没有重新训练旧基线，也没有将smoke或失败重试算作额外独立实验。成功收据/旧计算源码/固定输入/初值/配置/图关系与标签身份全部验收通过；plan文件SHA为b621cbc44e5651a421c6417924792cf64f048d464d1b138ebeac1002d6648dd6。

新候选沿用各任务原配置：合约initial/max LR 0.0005/0.01，节点0.0002/0.005，原Adam/OneCycle、50轮上限、patience7/delta0.001、严格最低val loss选择best；last独立保存。完整固定图前向、train监督、同val选模及评分均未改。新关系在所有30折有支持；没有根据分数选择fold、删样本、调整阈值或改seed。

**32.9 best、last和错误变化（CV validation）**

以下为best等权折均值；HCG是本地在下载作者图上的基线训练结果，不是直接引用论文分数。节点仍按HCG节点计分，不是去重源码行F1。

| 任务 | HCG BF1 | 原整体DDG BF1 | DDG＋控制依赖 BF1 | 候选−DDG(pp) | 候选−HCG(pp) | 候选MF1 | 相对DDG升/平/降 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 重入合约 | 94.1593 | 94.1593 | 94.1593 | +0.0000 | +0.0000 | 94.3452 | 0/5/0 |
| 访问控制合约 | 93.5590 | 93.5590 | 93.5590 | +0.0000 | +0.0000 | 93.8316 | 0/5/0 |
| 重入节点 | 96.0580 | 96.1027 | 96.1210 | +0.0183 | +0.0630 | 96.0643 | 3/2/5 |
| 访问控制节点 | 95.9723 | 95.8887 | 95.9171 | +0.0284 | −0.0553 | 96.8155 | 3/4/3 |

两个节点任务的配对BF1差值样本SD分别0.4513、0.2871pp。均值略升不等于稳定提升；访问控制仍低于HCG。折间SD不是独立seed重复方差，不以大量节点冒充独立实验。

last按HCG/原DDG/候选顺序：重入合约90.8867/91.0147/91.6169；访问控制合约85.9247/84.6752/84.5429；重入节点97.1504/96.9109/97.1342；访问控制节点95.8010/94.1517/94.1214。未选择更高last替换best，best/last方向不完全一致。完整均值/SD、Precision/Recall、逐折及pooled OOF分表保存；pooled OOF仍为CV validation。

best候选相对原DDG：两个合约任务类别完全相同（8/7错误未变），全部概率变化，平均绝对概率差0.004435/0.004328。重入节点44翻转，25纠错19新增错误，总错429→423；访问控制12翻转，7纠错5新增错误，总错216→214。重入仅8个翻转直接属于控制边端点，访问控制12个均非端点；无新边文件也可变化，不能把整体优化造成的变化全解释成控制边直接纠错。

困难文件按类别及source SHA区分：重入buggy_18新增74控制边但252错误不变，buggy_36新增73边、57→59错误，simple_dao新增2边、4错误不变；访问控制buggy_18/26新增37/29边、87/42错误不变；parity_wallet_bug_2零新控制边却3→1错误。主要困难案例未解决，不因这些现象改标签或排除文件。

**32.10 完整性、监督梯度、资源与独立复算**

final verify/summarize通过；全部30 fit的best对应history严格最小loss，last对应末轮，loss/概率有限；60个新best/last重载预测逐值一致，无评分阶段建参。独立从完整OOF 60006条三变体身份记录重算180组指标/混淆矩阵与CSV一致。全部240项新canonical×fold有train支持和非零实际监督message梯度，逐轮5464条enhancement_relations记录均非零，采集在backward后/optimizer前；不是用weight decay造成的变化代替梯度证据。

原回归413通过/31 warning，新统一测试73通过/4 warning，最终0失败/跳过；共486个所选用例，不声称测试了所有仓库模块。失败初次测试、grammar歧义、库路径和只读辅助读取错误保留原记录。未下载编译器、未执行solc或EVM验证。

各任务fit秒合计976.74/692.15/2041.18/1249.37，总4959.45秒约82.66分钟；这是fit单调时钟之和，不含准备/验收。最大allocated MiB为2894.40/2159.13/1883.61/1250.32，reserved3068/2252/2048/1364，最低整卡空闲29/31/63/550MiB。每任务新增65664参数。全部串行、无OOM/降配/切CPU，不据背景负载不同的历史时间声称速度提升。

补充口径澄清：第32.5节25519/19691/16217/11743是加控制边前HCG_DDG的总边数，包含原CFG/CG，不是仅DDG新边数。新增8个canonical组合仍只有1种新关系CONTROL_DEPENDENCE。原261代码/用户文件SHA及HEAD021a6f55复核不变。

**32.11 最终产物、分析分母修正与停止边界**

新增最终结果文件均在guard_extension_v1：RESULT_REPORT.md、RESULT_TABLES.md、analysis_summary.json、final_independent_review.json、protected_after.json，以及已有report.json、各类CSV、90结果引用/30新收据、覆盖与错误专项审查JSON。修改两树training_changes/HANDOVER只追加本记录，README/实施报告仅补最终入口，不改历史快照。

prediction_changes.csv是稀疏变化表。初建辅助analysis_summary曾将稀疏行数作为population及概率绝对差均值分母，最终改用完整身份对齐OOF的142/114/12036/7710样本数，显式保留changed_rows/unchanged_rows；例如重入节点best有12035条变化、完整12036。修正只涉及该新分析摘要，正式预测、F1、report.json、CSV及封存训练代码均未变。

receiver内嵌调用未递归核验仍是下一版本待修项；本批唯一两处已经回退/零事实，未污染四图，不悄悄修改seal后重跑。显式控制/异常、普通调用opaque处理、旧modifier元数据歧义、未编译验证及作者标签争议仍如实保留。

结论：实现及实验闭环已完成，但没有稳定改善证据；不宣称完整Solidity DDG、七类通用收益或独立测试泛化。若继续研究，先处理已知绑定边界，再依据现成预测/语义证据评估价值，而不是靠堆关系/挑分数保证提升。本轮停止，不启动新seed、其余五类、独立测试或额外训练。实施、训练、核验、分析与记录AI：Codex。

## 33. 2026-10-20 标签错误分层与已有合约读出诊断（Codex）

**33.1 授权、范围与新增文件**

用户要求按上一轮推荐开展下一阶段。本轮落实无需重训的标签上下文分层、合约均值读出诊断和下一步方案；未更改任何作者图/标签、节点特征、DDG/HGT、原训练代码或已封存计划。开发HEAD仍021a6f55ac9e3f94fc70feb441ff48b51b6a92ea。时间按美国东部2026-10-20记录，部分产物UTC为次日。

新增开发树scripts/DFG/experiments/readout_diagnostics/{__init__.py,core.py,contract_readout.py,label_context.py,summarize.py,README.md,tests/test_core.py,tests/test_label_context.py}。产物独立在artifacts/readout_diagnostics_v1/。原有两树文档仅追加本节及简略交接；保留此前用户修改。

**33.2 标签分层设计、身份保护与结果**

复用既有五文件源码/标注审计，不重新构建标签。按cohort/file/source SHA/原节点ID/type核对60个node-fit的冻结预测、353个已知分歧身份、图/标签/特征绑定及导出摘要。只把已审计1127节点分为REFERENCE_AGREED和DISPUTED；其余18619保持UNREVIEWED，不能将未审计当干净。三配置59238行对应19746独立节点。公共端点投影不是已认证语义真值，官方target未替换。

best错误分层“参考一致/分歧/未审计”：重入HCG 55/199/174，DDG 55/199/175，GUARD 55/199/169；访问控制HCG 6/125/80，DDG 7/125/84，GUARD 5/125/84。GUARD重入相对DDG净少6均来自未审计层；访问控制净少2来自parity两个参考一致节点，仍比HCG多3总错误。争议层没有改善。

三个困难文件三配置best一致：重入buggy_18总错252，其中分歧197、一致55；访问控制buggy_18错87，其中83/4；访问控制buggy_26错42，其中42/0。它们合约分类均为TP，不能混淆节点定位错误与合约漏报。last独立保留：重入HCG/DDG/GUARD分别9/214/61、9/215/122、11/215/77；访问控制2/134/95、5/134/197、7/134/193。不能选更有利last替代best。

**33.3 合约诊断实现与原计算保护**

只读核验overall_cv归档与guard_extension计划，从manifest取得图、标签、源码、checkpoint，不猜路径。两个合约任务各五折三配置共30个已有best，在原CUDA设备完整图前向；hook捕获最后HGT输出和真实分类头输入，按node_ids_dict及原node_id核对。正式输出仍是原mean+linear；原模型state digest、梯度与输入SHA前后核对。

导出768个验证文件记录与95232个节点贡献记录。每文件仅用所属验证折模型，统一score_role=cv_validation。三配置512个文件配对比较全部概率变化但类别变化0；最大历史概率误差1.1921e-7，小于原1e-5。重入TP66/TN68/FP3/FN5，访问控制TP51/TN56/FP1/FN6，三配置相同。

参考贡献是(d·h_i)/N，bias独立，内部节点分数不是节点漏洞预测；作者node target只在forward之后做描述性分组。原作者标签判定沿用is not None，不能改成bool；实际两图没有空值语义差异，通用代码仍修正且回归覆盖。

**33.4 诊断数值失败、修正理由与证据**

attempt_001首模型预测重现，但将float64参考margin与CUDA实际结果直接按1e-4核验而失败。保留failure、log、runtime_snapshot及只读float32_probe；快照SHA与初次plan一致。不是训练失败。探针实际logits约±1，排除本次“大公共logit抵消”的解释。

仅修正新诊断：真实pool在同device/dtype/batch/权重/精度标志下F.linear重放要求torch.equal；历史概率要求不变；float64贡献恒等式以1e-10验收；pooling/head数值残差另列，不归给节点或bias。reference/actual类别不同则不能用参考贡献解释实际分类。保留旧阈值失败计数，未仅调大容差。

attempt_002成功：head重放30/30精确，参考/实际类别0/768不一致；float64最大恒等误差3.553e-15；pooling margin残差最大5.162e-7、head残差8.0242e-4。旧logit阈值失败211/768、旧margin失败330/768均公开。matmul/cudnn allow_tf32=true只是环境记录，没有切换精度对照，不断言全部差异由TF32造成。

成功目标30次前向，另有失败诊断1次、数值探针1次，共32次模型前向、0fit/backward。首次27tests通过，补充后33tests全通过（0失败/跳过，无warning），包括logits篡改、pool错误、残差分离、非有限历史概率、原label语义及标签/身份损坏。未删除或放宽原关键错误断言。汇总独立复核30矩阵、全部表SHA、分表/合并表及身份数量。

**33.5 实际发现与结论边界**

HCG全部漏报均有正向局部证据（重入5/5、访问控制6/6），但正确良性也有65/68和56/56。不能由此证明mean是唯一瓶颈，更不能直接改成最高节点分数。重入漏报平均14.6节点，正确检出漏洞图平均181.26；访问控制51.17对145.16，漏报中位数14.5。当前不支持“单纯图太大稀释”的解释。

完整TP/TN/FP/FN贡献、全部15个不同误判文件和top3示例已导出。top3只是例证，可能包含负分，文件命名error_top_nodes而非positive。不同配置已训练参数不同，贡献变化不等于纯新增边因果效应。仍无稳定DDG改善或独立泛化证据。

**33.6 下一轮设计、调整与未执行事项**

NEXT_STAGE_DESIGN.md冻结既有DDG与控制关系，只保留一个合约读出候选：每文件softmax(a·h)加权，a全零初始化，初始数学等价mean，128维隐藏新增128参数；保留原分类头，不添加MLP、规则、top-k或节点标签监督。理由是需要学习区分证据而非保留所有局部高分；尚未编码，不存在--readout attention训练参数。

计划2×2：作者HCG/整体增强图 × mean/attention，两任务各5折；如果历史mean全部绑定可引用，则只新增20次合约fit。先接口/显存核验，fold0可计入；正式实验不删下降折。检验增强图相对HCG的attention交互增量；两图同时涨只能支持读出改进。新参数和优化轨迹变化仍是限制。本轮不自动执行20次，不新增节点训练、新seed、其余五类、独立测试或新语义关系。

**33.7 资源、交付与保护验收**

30个成功诊断含归档/哈希和导出670.16秒，最大allocated631.81MiB、reserved654MiB，单模型串行，无OOM/CPU替换。旧计算文件与输入/checkpoint摘要前后未变；本轮没有Git写操作、solc运行或依赖升级，未声称重跑全部历史DDG回归。

产物：DIAGNOSTIC_REPORT.md、NEXT_STAGE_DESIGN.md、label_context四表/JSON、contract_best两attempt和30回执、analysis的分组/配对/全部错误/节点例证、测试与运行日志。新增代码README记录实际命令和不能覆盖旧输出的限制。详细失败和设计调整已记录；两树文档旧字节前缀保留。实施、执行、审查和记录AI：Codex。
## 34. 2026-10-20 固定作者图上的合约 attention 读出对照（Codex）

**34.1 授权、范围与新增文件**

用户要求按照上一阶段方案完成下一阶段。本轮落实第33.6节单一attention候选，新增开发树scripts/DFG/experiments/readout_attention/旁路，产物独立为artifacts/paper_kfold/readout_attention_v1/；复用原mean历史结果，避免重训旧基线。开发HEAD仍021a6f55ac9e3f94fc70feb441ff48b51b6a92ea。保留作者图、标签、512维inside_token、原DDG/control算法、HGT层、原文件折、数值训练函数和旧批次seal。所有旧文档只追加，前缀SHA另存于readout_attention_implementation_v1/documentation_prefix_before.json。

新增文件为__init__.py、common.py、model.py、runtime.py、training.py、checkpoint.py、checks.py、worker.py、prepare.py、preflight.py、control.py、report.py、README.md及tests/{test_model,test_report,test_integration}.py。代码只在ge-sc-llm-ddg-v11，两个工作树均追加详细变更和简略交接。未执行pull/checkout/reset/commit/push、依赖升级或编译器下载。

**34.2 唯一模型修改、数值复用与梯度审计**

AttentionGraphClassifier继承原guard模型，保留完整固定图HGT前向与原分类头，只将每文件mean替换为alpha=softmax(h @ a)、sum(alpha*h)。a为128维全零可训练向量，无额外bias、MLP、top-k或标签规则，不新增随机初始化抽样。每文件使用原所有节点，归一化不跨文件；原节点类型、canonical及方向adapter不变。零初值数学等价mean，浮点reduce误差单列，不设置绕开attention梯度的zero-vector分支。

新FIT与原paper训练循环共享代码对象；handler只负责模型/metadata/checkpoint/观察性审计。HGT梯度只统计gcs/adapt_ws，readout梯度单列，不能把新a的更新伪装成HGT连接；允许合法零梯度和训练未见但已注册关系。没有测试时建参、标签参与构图或pooling、从训练后权重继续fit。

新增checkpoint格式author-hcg-attention-paper-checkpoint-v1，绑定graph_kind、readout版本、原mean来源、图/标签/特征/schema、原初值SHA/tensor digest及配置。主评价仍CV validation；同val选best并评分，非独立测试。best严格最低val loss，last独立保存，不因last更好更换主结果。

**34.3 冻结矩阵、历史归档和初始化**

两个合约任务各5折，图为HCG及HCG_DDG_GUARD，每图仅新增attention拟合，共20次；mean分别只读引用overall_cv_v1和guard_extension_v1各10个已完成合约结果。新runs/HCG代表HCG+attention，不能误认为旧mean重新训练。节点分类不使用合约pooling，本轮不新增节点fit，不扩更多seed/其他五类/新关系。

prepare使用适用归档核验，不通过改旧seal应付新增目录。20历史mean结果与20未训练初值、10折划分、共同参数语义对齐全部核验；新模型旧参数逐张量精确复制，只有新增a全零，optimizer_steps=0，保留每折原fit_seed。初值不能从smoke/best/last生成。

新plan冻结20jobs、10task-fold manifests、692资产、207份旧运行源码及15份新Python源码。独立CPU审查917个文件SHA通过；10对跨图共同参数一致，20历史配置/监督/图/源码身份严格一致。正式训练开始后不修改这些源码和资产。

两个合约任务实际配置均为512维输入、hidden128、2层8头、dropout0.2/use_norm=True；Adam initial LR0.0005、OneCycle max LR0.01、div20/final_div1、cycle_momentum=True、weight_decay5e-6、每轮原step数、最多50轮、patience7/delta0.001。不是将节点任务的0.0002/0.005套到合约任务。fit_seed按原manifest逐折恢复，前一fit轮数不影响下一fit随机起点。

**34.4 测试与四任务真实预检**

新增36项测试通过（模型15、报告14、接入7），原guard_extension/readout_diagnostics回归57通过；总计93通过，0失败/跳过，4条既有DGL distutils弃用warning。CPU小图两种图各2轮验证best/last、相同初值seed精确复跑、HGT/readout各自断梯度拒绝、图/标签/特征/schema/初值/历史binding污染拒绝；这些是接口测试，不计为正式成绩。日志在readout_attention_implementation_v1，未声称重跑全部历史DDG测试。

prepare后4个真实fold0零optimizer-step GPU预检通过：HGT输出精确一致，pool最大绝对误差2.384e-7，logit最大2.1249e-5（预定1e-4界内），初始类别相同、alpha均匀、仅新增128参数、原初值不变。readout梯度L1按重入HCG/GUARD、访问控制HCG/GUARD为1.498769/1.496806/2.880494/2.879886，HGT梯度均非零。预检不包含optimizer更新，不能冒充正式训练峰值测试。

预检最大allocated为2041.36/2829.56/1491.36/2097.93MiB，最低整卡free34MiB。沿用mando/PyTorch1.8.1/DGL0.6.1、RTX3050 4GiB，同一共享GPU锁用于预检和正式训练；单模型串行，不改超参/图、不自动切CPU、不关闭用户程序。

**34.5 正式四fold0门槛与执行规则（进行中快照）**

先执行两任务两种图共4个正式fold0，核验有限loss、输入、独立梯度、best/last重载和预测一致性；通过后按冻结顺序执行余16次。四fold0计入20次，不另做训练smoke或挑成绩。成功折核验后复用；失败保留attempt并停止，显式排查后才允许整次重试，非epoch续训或新seed。

本段写入时重入两fold0完成，best BF1均84.6154、last均88.8889；访问控制正在运行。未因持平更换参数、seed或fold。后续完整结果另追加。验收标准是实验正确性，不是必须涨分。全部结果均CV validation，节点困难文件仍属旧节点实验，本批不声称修复其定位错误。实施、执行、审阅与记录AI：Codex。
**34.6 四正式fold0验收与完整五折放行（Codex）**

四fold0均完成，重入HCG/GUARD的best BF1为84.6154/84.6154，访问控制为90.0000/90.0000；主结果与对应mean持平。8份best/last重载精确，4项readout及HGT梯度/实际更新分别有效，新增参数均128，无非有限loss或OOM。两重入各14轮（0-based best6/last13），两访问控制各15轮（best7/last14）。last独立为88.8889/88.8889/90.9091/90.9091，没有替换best。

独立CPU核验全部checkpoint state/file SHA、binding、optimizer步数、scheduler状态，逐轮复算strict-min best、delta/patience和OneCycle LR/beta1；预测混淆矩阵和BF1/MF1复算通过。初次审阅L1更新量出现0.000732/111850约6.5e-9相对差异，核对是独立审阅1线程与原worker2线程的float32 reduction顺序；用原2线程复核逐位一致，没有修改训练/权重/阈值。

证据fold0_acceptance.json、fold0_independent_review.json；通过正确性门槛后已启动余16fit，控制器复用这四折，不因F1持平停跑。新增四模型合计fit耗时596.20秒，正式峰值与最终资源在全折完成后统一汇总。此前20初值公平性再次CPU检查，7240共享张量逐位一致。HCG审计中的CONTROL_DEPENDENCE零支持字段只是一项统计，不对应新增空canonical。

训练期间一次临时进度读取脚本括号笔误导致SyntaxError，修正只读查询后继续；没有影响worker或任何正式artifact，不计为训练失败。运行源码、旧输入及计划均未变。最终结果后补，实施、审阅与记录AI：Codex。
**34.7 完整20次正式拟合与40结果联合验收（Codex）**

余16fit已全部完成，四fold0计入20次，均attempt_001，0训练失败、0重试、0 OOM、0非有限loss。两个合约任务各5折、两图各attention，共20新模型；只读复用20历史mean，形成40模型、80组best/last指标。控制器按任务验收后再继续，full_controller_001.log最终exit0；最终control verify/summarize通过，独立final_independent_review.json核验全部40个新checkpoint文件/tensor摘要、绑定、optimizer/scheduler状态和逐轮规则。训练期间未修改封存源码、数据或配置。

完整输出包含40条best/40条last、16条均值SD、16条pooled OOF、1024条完整四格文件OOF、2048条best/last文件错误记录。两个任务按cohort/fold/file/source SHA分别对齐，独立从预测重算指标和混淆矩阵；不按CSV行号或同名文件匹配，不将稀疏概率变化表行数作为完整分母。新增RESULT_REPORT.md、RESULT_TABLES.md、resource_summary.json和两任务independent_analysis.json，均在新批次。

**34.8 主best结果及实际错误变化（CV validation）**

| 任务 | HCG mean BF1 | HCG attention BF1 | 增强mean BF1 | 增强attention BF1 | attention−mean：HCG/增强(pp) |
| --- | --- | --- | --- | --- | --- |
| 重入合约 | 94.1593 | 93.5157 | 94.1593 | 94.1593 | −0.6437 / +0.0000 |
| 访问控制合约 | 93.5590 | 92.7619 | 93.5590 | 90.5564 | −0.7971 / −3.0026 |

MF1同顺序：重入94.3452/93.6245/94.3452/94.3452；访问控制93.8316/92.9588/93.8316/91.1449。BF1升/平/降折数：重入HCG attention−mean为0/4/1、增强为0/5/0；访问控制分别0/4/1、0/3/2。不是用论文数字充当本地配对基线。

重入HCG attention在fold2新增0x67793426747f8c79332520c1291c4fc6443c8407.sol误报。增强attention纠正0x12345678979f29ebc99e00bdc5693ddea564ca80.sol旧误报，同时新增0x677934...误报，总错误仍8。F1相同不等于预测相同。原modifier_reentrancy/reentrancy_bonus/reentrancy_simple/simple_dao/etherstore五漏报未纠正。

访问控制两attention都在fold3新增0x0c7b8eedd028f3730e7b0f3dc032e916302f09b4.sol误报，增强attention又在fold1新增proxy.sol/rubixi.sol漏报；相对增强mean为0纠错/3新增错误。原六个漏洞合约漏报在四格均未纠正。两类buggy_18及AC buggy_26在本批合约best本来均为TP；没有新增节点fit，不能宣称修复其节点定位错误。

主交互(增强attention−HCG attention)−(增强mean−HCG mean)：重入+0.6437pp仅由HCG attention退化产生，增强attention未超过原mean；访问控制−2.2055pp集中在fold1两个额外FN，该折−11.0276pp。所有主要best对照概率均142/142或114/114文件改变，是真实接入但没有稳定净收益；新增参数和优化轨迹改变，不能当成纯DDG语义因果效应。

**34.9 last、资源和实际梯度证据**

last BF1按HCG mean/attention、增强mean/attention：重入90.8867/93.0421/91.6169/92.3525，访问控制85.9247/80.7818/84.5429/82.5007。重入last相对各自mean有改善但折间不稳定；访问控制两attention仍退化。best/last方向不完全一致，未改选last或最高F1轮次。pooled OOF及等权均值分表，仍为CV validation而非独立测试。

20fit合计3285.44秒约54.76分钟，共315epoch。四组attention参数按重入HCG/GUARD、访问控制HCG/GUARD为4527090/4781538/4510674/4789746，分别比对应mean新增128。最大allocated2894.40MiB、reserved3070MiB，最低整卡free21MiB；保持单GPU串行，不改图/超参/CPU，不拿历史背景负载不同的耗时做速度收益结论。

315条readout epoch审计全部连接且实际梯度非零，最小L1约0.0001675；HGT和readout权重更新分别核验。新attention增强分支325条canonical×fold审计，316有train支持且观察到非零message梯度，9条已注册而train未见者正常保留。没有以必须非零为由删未见关系，没有评分时建参。93相关测试通过证据不变，未宣称重复运行全部DDG测试。

**34.10 交付、保护与研究结论**

新批次RESULT_REPORT.md给中文分析，RESULT_TABLES.md给逐折best/last、均值SD、配对纠错和pooled；全部CSV/JSON、初值、checkpoint、预测、收据和失败策略保留。新源码README补最终结果入口。两个工作树training_changes/HANDOVER继续仅追加，注明Codex；旧字节前缀保护、261旧代码/用户文件、207旧运行源码、15新封存源码及692资产核验，HEAD021a6f55不变。没有Git写操作、依赖升级或solc执行。

本轮单一attention候选未解锁DDG稳定合约收益，访问控制明显下降；维持mean主方案，attention旁路完整归档为负结果。不能据此推断所有DDG/读出/七类均无效，也不能在同一validation上继续搜索多个头直到涨分。已知作者标签争议、既有受限语义/嵌套接收者绑定边界及单seed限制继续保留，当前冻结图未因本轮改变。

本轮完成20新fit/40模型完整对照后停止，没有自动新增节点训练、更多seed、其他五类或新关系。实施、训练、独立审阅、分析与记录AI：Codex。
**完成时间补记（2026-10-21，Codex）**：本阶段跨日执行，上述2026-10-20标题表示阶段开始日期；完整五折训练验收和最终报告交付完成于美国东部2026-10-21。UTC及文件时间另记delivery_manifest.json，不将54.76分钟的累计fit计时冒充完整阶段墙钟耗时。
## 35. 2026-10-21 DDG方案、代码与已完成实验独立审查（Codex）

**35.1 用户要求、范围和版本**

用户要求仔细review方案是否存在问题、完成与未完成内容及代码正确性。本轮只读审查开发树ge-sc-llm-ddg-v11及相关原树材料，不修改DDG、HGT、tokenizer、标签、图、训练规则、plan/seal，不启动正式训练。开发HEAD仍021a6f55ac9e3f94fc70feb441ff48b51b6a92ea，原树HEAD f3dfc17908029355c5fc45d6d3932f203068fcf5，保留原树用户auto_version_solc.py修改。新证据集中于开发树scripts/DFG/experiments/artifacts/design_code_review_20261021_v1/；此前实施记录继续保留，以本节归纳现状，不重写历史。

**35.2 新增文件、原因和方法**

新增REVIEW_REPORT.md；scalar/的独立语义及回归记录；state_control/接收者复现、真实源文件覆盖与pytest日志；experiments/独立指标、runtime seal、HGT canonical mean探针及CPU接口测试；legacy_adapter_probe.json；文档前缀与代码保护快照。原因是区分实际代码错误、保守支持范围、实验负结果和文档漂移，不能把无提升一律归于训练失败。两个工作树training_changes/HANDOVER仅追加，修改及审查AI为Codex。

**35.3 确认的正确性缺陷与本批影响**

control_dependency/cfg.py:169–172只确认address转换类型；193–196只核验实际参数；241–244遇外层call后返回，遗漏receiver内部调用。独立健壮性样例require(ok); address(unresolved()).call(""); x=1被错误analyzed并产2facts；已声明但会revert的target作为receiver也漏过控制求值语义。未知普通调用和参数内嵌调用对照均正确函数回退、ir=None/facts=[]。未执行solc，不能将parser样例称编译合法。

独立按冻结manifest核验256源路径/SHA；40处广义receiver内嵌调用（包括非address-cast模式）全部已function_fallback，semantic/projected/published均0。精确缺陷模式仍仅AC合约0x000c...的handleAllocation/handleWithdrawal，两者因别的不支持条件已回退。未发现现有图污染；本轮不修冻结源码，下一版应最小补receiver核验和无残留回退，不能声称此缺陷解释本批低增益。

**35.4 接入入口、方向与审计可用性问题**

根README/cli仍scalar-only，configuration.prepare_graph仅调用标量pipeline；原树没有最新state/control/后续实验旁路。旧sco_models.graph_utils.reflect_graph只对DATA_DEF_USE保正向。独立五关系小图验证：其他四新关系在旧入口0→1变双向，当前guard正式adapter则五类均正向。旧入口不能当完整方案入口；已完成正式实验走正确旁路，未发现历史关系反射错误。

overall_cv旧verify以整个当前DFG源码集合比较，原186份文件未改/未删但新增43旁路文件会触发Runtime drift。已有guard_extension.archive按旧清单只读核验可用，应文档引导而非改旧seal。旧modifier_context.control_dependence_edges=False在新control facts里仍出现（四任务302/311/143/150条），是历史字段含义歧义，实际已生成控制边。H1配置描述统一写合约LR，H2已澄清真实节点0.0002/0.005、wd0；没有发现实际训练配置被错误统一。

原宏观指南E2/E3含义为反向/跨函数，与后续授权E2修复标量/E3a状态DU/E3b顺序不同；属于方案迭代而非已完成函数摘要，交付应按批次名称解释。

**35.5 新确认的聚合机制与设计归因边界**

model_hgt.py:116–117跨canonical使用mean。CPU无标签无训练探针：train0→1和val2→3各next，只为val2→3新增DATA_DEF_USE，train节点1无新增入边，其聚合值仍1→0.5。新relation零消息参与均值。不是跨文件消息或标签泄漏，但说明新增关系同时改变原消息尺度/参数量/优化轨迹。不能仅用分差宣称纯语义因果贡献，也不能断言此机制就是实际低收益主因；后续线性/残差/归一化还会影响最终输出。本轮没有修改HGT。

**35.6 能力完成度与实验结论**

受限标量声明/作用域、DEF/USE、CFG正向RD、KILL/union/fixpoint、精确投影、函数回退、原图不变量、专用canonical接入及checkpoint绑定已实现。状态DU/简单mapping、状态访问与调用→写顺序、受限继承/modifier、后支配控制依赖已实现子集。当前STATE_DEF_USE在R合约/节点为9/4，AC合约/节点14/5；AC调用→写边0。函数入口未知及调用HAVOC是保守选择，典型先读→调用→写不能反向伪造为Def–Use。

完整跨函数/跨交易摘要、任意storage别名/复杂引用、完整modifier/异常/动态分派、路径可行性、一站式任意新源码增强推理尚未完成；反向DDG有意未加入。七类仅验证重入/访问控制，不等于已证明七类有效。

同一完整主对照best BF1按HCG/DDG/GUARD：重入合约94.1593/94.1593/94.1593，访问控制合约93.5590全同；重入节点96.0580/96.1027/96.1210；访问控制节点95.9723/95.8887/95.9171。完整候选对HCG为0/0/+0.0630/−0.0553pp，不能称稳定改善。Attention增强合约重入持平，AC93.5590→90.5564，不支持替换mean。best/last方向不统一，维持原选模规则。

旧E0/E1、H1/H2和overall初始化锚不同，跨阶段分差不是配对增量。三个困难文件节点错误252/87/42不变，其中197/83/42在既有标注分歧；不能把公共标注当已认证真值，也不能把全部误差归给标签。完整节点均值约96，不是所有折99；重复模板、单seed、同val选模评分仍限制泛化解释。

**35.7 本轮验证与未执行事项**

标量222、状态/控制215、三个最新实验接口83、原项目四组19，共539个不重复所选pytest用例通过，0失败/跳过，43既有DGL/Torch TensorBoard/NetworkX弃用warning。首次标量未设Linux grammar时188通过/34 invalid ELF header失败，使用已有README要求grammar后全过；没有安装二进制。state unittest最初38项已由pytest完整215替代，不重复计数。

另9组标量独立探针通过；receiver缺陷独立复现说明测试全绿不等于语义完整。按身份重算120+180+80=380组best/last指标零不一致；101034条预测含历史重复引用，不当新训练/独立样本。最新seal及207历史+15新共222运行源码hash一致。具体命令/日志见新报告。

未重新加载全部大型checkpoint、未跑solc/EVM、未重跑全部仓库历史测试或正式GPU训练，不冒称已认证所有Solidity语义。旧代码保护和文档字节前缀追加验收另存本轮protected_after.json及documentation_prefix_after.json。

**35.8 下一步建议与停止位置**

先最小修receiver绑定与元数据，再统一完整profile/方向adapter/归档核验文档；将当前工程版收束并保留mean。进一步研究先用少量有语义证据的正反例检查真正新增信息及聚合影响，不再无目标堆关系或反复在同CV选候选。独立评估、多seed、七类扩展需另定范围。本轮仅审查记录，尚未实施修复，没有新fit。实施、审阅与记录AI：Codex。
## 36. 2026-10-21 基于完整结果的下一阶段收束设计（Codex）

**36.1 目标与依据**

用户询问针对当前结果下一步如何设计。本节仅形成方案，不修改代码或启动训练。基于第35节独立审查：整体候选相对HCG仅重入节点+0.0630pp、访问控制节点−0.0553pp，合约无分类收益；attention未改善。下一阶段定位为正确性收尾、统一入口及一次有限的依赖覆盖/模型利用诊断，保留mean、作者图标签与原冻结实验，不继续无目标增加关系。

**36.2 阶段一：修复与工程收束，新增正式训练0次**

在开发树scripts/DFG/下最小修复address receiver嵌套调用核验，无法解释时函数级无残留回退；补未知调用、已声明但有控制效果、正常接收者回归。明确modifier证据字段的阶段含义。统一完整图profile及对应方向adapter，明确旧cli只支持scalar，原图/标量/完整DDG/带控制依赖是能力配置而非新的四组训练。提供正确的历史只读归档核验入口，不改旧seal。

修复后核对四任务原节点、标签、token、原CFG/CG及新增边的规范化摘要。若当前图内容和实际计算等价，已有实验按旧版本保留，无需仅因代码版本变化重训；保留新旧代码身份及等价证据，不把旧结果伪装成新代码运行。若图/数值确变则列明影响任务，另立批次，不覆盖或混合旧结果。

**36.3 阶段二：一次有限诊断，新增正式训练0次**

使用既有模型与源码，按任务/节点类型/关系/文件记录：新增边覆盖与缺失原因、两层新增上下文、收到新消息的节点、没有新增入边却因canonical mean改变原消息缩放的节点、消息及隐表示/分类margin变化。不同训练模型的参数本身不同，不把直接相减解释为纯语义作用；需要隔离聚合时使用已保存的共同初值或显式对齐共同权重，并记录全部内存干预。推理删边/置零只作为敏感性检查，不当作重新训练消融或泛化收益。

预先固定最多12个函数，两个漏洞各6个：应有依赖、应无依赖、应回退各2个。按源码语义/已知失效类别和身份选择，不按哪个例子涨分筛选。标注分歧只作为既有背景，不修改正式标签或删除困难文件。分别归类：语义上不应产生函数内DU、存在但范围外、分析正确但缺HCG投影、已进入模型却无决策收益。STATE_DEF_USE只有4/5条不自动是bug。

交付统一诊断表、源码证据和一个明确的继续/收束结论，不再为每个小关系启动一次K折。

**36.4 是否进入新训练的决策**

若无新的正确性或信息利用证据，收束现有DDG工程版并如实保留负结果。若确认信息存在却主要受聚合机制影响，再单独提出一个候选：例如受控增量接入；它改变模型聚合，是新的方法假设，不能冒充仅修DDG。若需要区分语义与新增参数/密度，可设计同文件、同canonical、同边数/尽量同度分布的非语义边对照；端点不得由标签选择，且随机边可能有额外不合理结构，只能辅助解释。

任何新训练先固定一个问题、一个候选、比较矩阵和验收规则；小规模检查只验正确性/资源，不按某折F1挑选放行或删除下降折。当前不承诺新增60/90次，不将多seed或七类全量作为默认下一步。同CV持续选候选存在研究选择偏差；后续独立评估需另定冻结范围。合约/节点能力均保留，但现有证据不支持继续扩大attention搜索。

**36.5 本轮执行边界**

只读复核审查报告及配对统计，完成设计并向两树文档追加；没有实施修复、没有测试或训练，也没有新增可用CLI参数。具体能力配置是建议接口，不能作为现有命令使用。设计与记录AI：Codex。
## 37. 2026-10-21 DDG整体工程入口与正确性收尾（Codex）

**37.1 授权、定位及保留范围**

用户要求按推荐完成设计、尽快完成完整DDG方案。本轮落实第36节的receiver修复、统一profiles/正向adapter/归档、四任务等价复核、12函数Oracle及一次真实模型聚合诊断。不是新增模型训练阶段；不改作者标签、tokenizer、HGT、原训练数值规则、fold、历史图/计划/seal。完成当前受限范围的工程闭环，不称完整Solidity静态分析。

代码仍在ge-sc-llm-ddg-v11，HEAD021a6f55ac9e3f94fc70feb441ff48b51b6a92ea；原树HEADf3dfc17908029355c5fc45d6d3932f203068fcf5。未pull/checkout/reset/commit/push。230个事前记录旧生产Python SHA不变，原树auto_version_solc用户改动保留。前1—36节和HANDOVER旧正文保留，本轮仅追加。

**37.2 新增文件、接口与原因**

开发树scripts/DFG/integration/新增__init__.py、control_v2.py、pipeline.py、io.py、cli.py、model.py、rebuild.py、archive.py、oracle.py、README.md，以及tests/test_control_v2.py、test_pipeline_model_io.py、test_oracle.py、test_archive.py、test_rebuild.py。experiments/integration_diagnostics/新增__init__.py、message_probe.py、tests/test_message_probe.py。主要产物独立在experiments/artifacts/integration_release_v1/。

profile：baseline精确原图；scalar增加DATA_DEF_USE；full再加STATE_DEF_USE、STATE_ACCESS_ORDER、EXTERNAL_CALL_BEFORE_STATE_WRITE；full_guard再加CONTROL_DEPENDENCE。顺序与控制关系不是def-use；四profile是能力开关，不是新增四套训练。流程复用原scalar、Stage K状态/恢复、控制后支配与精确投影；模型装配复用原五关系方向adapter、HGT和合约mean读出。没有新增变量节点、反向DDG或替换原CFG/CG。

所有新图必须从未增强HCG开始；校验node_id/类型/特征/标签/原边/graph属性，拒绝跨文件连接、重复或自增强边、逆向增强边及profile不匹配；缺源码保留原样本，有记录但SHA错直接报错。IO绑定源码与manifest SHA，非覆盖输出并验证gpickle roundtrip。原脚本仍不变；旧scalar CLI和通用反射器不是完整五关系方案入口。两树DFG README已标明当前工作树与正确入口，overall_cv README标明只读归档命令。

**37.3 receiver缺陷最小修复及实际配置**

旧control_dependency/cfg.py对address转换receiver内部嵌套调用核验不完整，可能绕过不支持调用的效果检查。新ControlCFGBuilderV2检查成员receiver子树中的call/赋值/update/new等；当前无法可靠解释则相关控制分析整函数回退，0部分事实，不删除合约/原图。普通to、msg.sender、支持的纯地址转换保留原行为，裸内建终止规则未改。采用子类及私有FunctionType globals复用原算法，不全局monkeypatch，不改已封存旧代码。

同一断言前后证据control_v2_before_after.json：旧未知receiver产生2事实、应回退断言失败；新IR=None、fallback、0facts通过。初始19项定向测试覆盖未知/同名已声明嵌套调用、正常接收者与原图无残留。未运行solc，未知函数样例仅作为解析器健壮性测试。

modifier旧prefix-only的control_dependence_edges=false改记legacy_prefix_profile_control_dependence_edges，另记control_dependence_analysis_version，消除阶段元数据歧义。新统一入口最初max_iterations只传scalar/state，收尾审查已补control_v2局部bounded analyzer；默认100000不变，三阶段effective配置入audit，禁用阶段None。低上限1回退/0facts/原图不变，默认与旧模板精确一致，新增11项测试。

**37.4 重建四图与历史结果身份**

从原作者HCG和封存源码清单重新计算标量、状态/顺序、控制，输出integration_release_v1/rebuilt/四任务。reference manifest新增启动seal核验；当前输入SHA与seal吻合。四图不读预测或漏洞标签构边。

| 任务 | 文件/节点 | 原边→最终边 | 标量/状态DU/状态顺序/调用后写/控制边 |
| --- | --- | --- | --- |
| 重入合约 |142 / 18312|19267→28605|3561 / 9 / 1573 / 1109 / 3086|
| 访问控制合约 |114 / 13432|15538→21620|4032 / 14 / 107 / 0 / 1929|
| 重入节点 |71 / 12036|11710→18638|1894 / 4 / 1507 / 1102 / 2421|
| 访问控制节点 |57 / 7710|8840→13127|2836 / 5 / 62 / 0 / 1384|

四任务节点/属性、原边、typed-edge重数、类型局部ID/canonical与实际DGL有序端点均相同，模型输入等价。两个合约完整图fingerprint相同；两个节点仅ddg_fact_indices因任务文件集合重新编号，1885/2455条DATA_DEF_USE边属性不同，模型不读取此证据字段。见rebuilt/manifest.json及rebuild_metadata_comparison.json；不把文件差异隐藏为完全相同。

构图计时合计342.09秒。最终默认control包装另行在四个实际图复算，fingerprint全部相同，final_default_control_check.json保留最终源码SHA。首次图产物在接口收尾前生成，audit不覆盖；默认最终语义等价单独验收。旧checkpoint完整输入绑定不重写，旧成绩仍归原runtime；模型输入等价不是本轮重新训练。

**37.5 有限Oracle与聚合诊断**

预先封存12个函数，两个类别各6，4应有关系/4应无特定关系/4应回退；源码身份绑定cohort/file/SHA/function span，不按F1选样。最终12/12符合预设：buggy_18.add、simple_dao.withdraw、AC buggy_18.sendto_txorigin21、buggy_26.add各有1条预期事实并投影；入口状态读/单次写/RMW不虚构状态def-use；复杂bytes/string、delegatecall、多modifier回退无部分不确定事实。Codex源码审阅，非独立人工签署，不是ground-truth审核或全语料正确性证明。

Oracle初版substring将函数入口全文错计，保留validation旧结果，仅改新增工具为精确语句匹配并加测试；selection/预设不改。最终oracle/validation_v2/results.json由verification_receipt.json绑定。

CPU使用四任务fold0保存的未训练共同初值，optimizer_steps=0；A原HCG，B增强schema但五关系message参数仅内存置零，C原增强初值。共同参数精确一致，29个输入/初值/manifest文件前后SHA相同；hook观察原HGT真实聚合与两层隐藏/logit。没有新optimizer步骤。

无新增入边但分母改变节点R合约6879、AC合约4350、R节点4655、AC节点2006；其中首层聚合实际改变6056/3866/3945/1647。第一层B≈A×原canonical数/增强canonical数，最大误差9.5367e-7；R expression_statement由18到31，旧消息受18/31缩放。新增入边节点5571/4450/3776/3078。170.31秒诊断输出diagnostics/CSV/NPZ/JSON。0/0孤立类型防御补丁不影响真实四任务，执行与最终代码身份另记。

这是机制而非性能证据：未训练初值不能代表训练后DDG利用率或低收益根因；第二层包含传播，C−B也不是纯语义因果。没有新增F1，没有用这些差值自动修改HGT。

**37.6 测试、只读归档与实际命令**

新增74项、旧相关539项，最终613 passed/0 failed/0 skipped，31条既有DGL/Torch distutils、NetworkX read_gpickle弃用warning，9.71秒。完整命令及输出见regression_003.log。覆盖真实node/contract HGT前向反向、五关系梯度、图特征标签/schema错误拒绝、profile恢复、源码/产物SHA、无覆盖、低上限回退及seal错误。不是声称运行全部仓库测试。

保留初版接口Path夹具失败、pytest同名test_projection模块收集失败、Oracle计数工具失败证据；分别修测试调用类型、使用--import-mode=importlib、修精确语句matcher，没有删除测试/降低关键断言。最终默认四图已验收。

archive.py只支持已知overall_cv/guard_extension/readout_attention协议，通过历史记录名单允许新增旁路，不放宽记录文件摘要。实际overall_archive.json核验60fit、60收据、689记录文件；checkpoint以SHA核验，未声称本轮重载全部旧权重。旧plan/h2_plan/seal不改。

实际入口（在ge-sc-llm-ddg-v11、mando、原TREE_SITTER_LIB_DIR下）：

```bash
# 新目录复核四图，无训练；本轮已生成integration_release_v1/rebuilt
CUDA_VISIBLE_DEVICES= python -u -B -m scripts.DFG.integration.rebuild \
  --output scripts/DFG/experiments/artifacts/integration_release_repeat_v1/rebuilt
# 新增入口与诊断单元测试
CUDA_VISIBLE_DEVICES= python -B -m pytest -q --import-mode=importlib -p no:cacheprovider \
  scripts/DFG/integration/tests scripts/DFG/experiments/integration_diagnostics/tests
```

完整源码清单格式、单图profile命令、五关系make_model、历史归档和Oracle/聚合诊断命令见integration/README.md；所有输出拒绝覆盖。没有假装原train脚本新增--profile/use_ddg等参数。

**37.7 本轮结论与剩余边界**

工程闭环已完成；未完成完整跨函数/跨交易摘要、任意storage别名、任意继承/modifier/异常语义、一站式任意源码推理、七类完整实证、多seed和独立测试；反向关系仍有意不加入。没有solc下载/安装/编译。本轮正式fit=0。

历史mean/best主链HCG/full/full_guard的重入节点96.0580/96.1027/96.1210、AC节点95.9723/95.8887/95.9171；合约分别94.1593和93.5590三者一致，仍是CV validation和HCG节点口径。不能把工程收尾写成稳定增益。保留mean/attention负结果，停止自动扩关系或重复K折。若继续，聚合证据支持提出一个“保留原HCG消息尺度的增量接入”候选，但属于新模型假设，需独立受控验证，不承诺一定改善。

完整报告与产物索引：scripts/DFG/experiments/artifacts/integration_release_v1/IMPLEMENTATION_REPORT.md。设计、实施、审阅与记录AI：Codex。

## 38. 2026-10-23 DFG v2 Prompt 0：侦察验收、方案选择与三文档同步（Codex）

**38.1 本轮授权、版本及工作范围**

用户要求保留已有DDG实现，在新分支按 `scripts/DFG/dfg_v2/PROMPTS.md` 从Prompt 0开始，并要求对文档方案的实质调整先征求同意。工作树 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11` 实际已处于 `dfg-v2`，基础提交 `29a9b4efdedb2f897dc78c6b332a526ab9994fee`；因此没有重复创建分支、checkout、reset或迁移原实现。该基础包含 `ddg-v1.1-correctness@e7bcb84` 的既有工作。P0新增审计已本地提交为 `085eb86e14f9d13f19a4f6ba937fb3fce279e13b`。

本阶段只核实v2依赖的输入、精确投影锚点、token生成规则、训练数值协议、旧标量覆盖及历史资源；不编写新DFG分析算法，不修改HGT/tokenizer/训练逻辑/标签/折文件，不执行新fit，不进入Prompt 1。以下所称“通过”是P0前置验收，不是完整DFG v2已实现或已验证提升。

P0原指令“不修改任何已有文件”与共享上下文“每轮追加HANDOVER/training_changes”冲突，初次执行选择前者，先将记录写入新PROGRESS。用户本轮明确要求补齐三个文档，因此现将P0全过程追加到本节与HANDOVER，并在PROGRESS追加授权变更说明；不回写或删除旧记录以伪装从未发生该选择。

**38.2 文件清单、具体职责与保留对象**

P0提交新增8个文件，均在 `scripts/DFG/dfg_v2/`：

| 文件 | 实际内容与原因 |
| --- | --- |
| `recon_graphs.py` | 从冻结manifest取得四任务HCG/源码；统计节点、边、canonical和属性；用AST身份比较原SourceView与SupportedSourceView的锚点与语句覆盖。只审计，不改图。 |
| `recon_tokens.py` | 离线加载既有tokenizer；每任务seed=0固定抽200节点，重编码并逐元素比较；保存抽样身份、原/新向量、来源与SHA。 |
| `recon_protocol.py` | 读取实际有效配置、冻结外/内层名单与历史收据；核对种子推导、内层重建、旧90次fit资源。未加载训练权重或启动GPU训练。 |
| `recon_scalar.py` | 调用未修改的原scalar profile四次，重新生成对照图；同时统计原源码函数总量、文件级门槛排除量和函数回退Top 10。 |
| `recon_report.py` | 将审计证据及用户批准的视图选择汇总成人可读/机器可读报告；拒绝覆盖已有输出；不是新的分析器。 |
| `RECON.md` | 回答P0七项要求，记录两种视图口径、结果、限制、未来建议及实际复跑入口。 |
| `recon.json` | 完整机器汇总，包含原始审计、批准后的验收决策、路径/SHA、token、配置、资源与证据索引。仓库全局忽略*.json，提交时仅显式加入本文件。 |
| `PROGRESS.md` | P0实施进度与下一步边界；本轮再追加三文档同步和推送暂缓状态。 |

P0产物只新增到 `scripts/DFG/experiments/artifacts/dfg_v2/recon/`，包括graphs、token、protocol、scalar和保护/测试记录；不覆盖旧产物。本轮唯一跟踪文件修改是HANDOVER、本训练变更文档和PROGRESS。PROMPTS.md及RECON/recon.json均保留P0快照；旧schema、标签、源码、token、模型、历史plan/seal及用户原有未跟踪文件不改。文档同步核验收据独立放在该产物目录的 `documentation_update_20261023_v1/`。

**38.3 方案选择记录：采用哪个、为什么、哪些尚未采用**

| 决策点 | 实际选择 | 理由、替代项及状态 |
| --- | --- | --- |
| DFG v2源码视图 | 复用已有SupportedSourceView及绑定的版本元数据 | 原SourceView对多pragma保守拒绝，使AC合约锚点低于90%；已有Stage K视图可验证区间/词法作用域并恢复精确匹配。先报告并询问，用户答复“同意复用已有 SupportedSourceView（推荐）”。这是唯一已批准的v2方案调整。 |
| 未确认版本或视图 | 保留回退 | 不把没证据当确定版本，不下载/运行新solc，不为达到覆盖门槛补造STATE_VAR节点。 |
| 原scalar对照 | 保持旧SourceView和旧pipeline原样 | 批准v2未来采用新视图，不代表允许改写对照基线；必须保留后续L1逐边比较所需的原行为。 |
| 模型输入来源 | manifest中冻结的作者HCG/标签＋本地已有token | 不换成本地narrow或其他重建标签；本轮不混用不同图版本，不修改输入。 |
| 节点任务用图 | 漏洞文件的HCG子集 | 保留本批真实输入；作者另发的CFG-only文件不是本次节点任务输入。 |
| token重编码 | 先完整编码含特殊token，再由encode_ids截到512并补0 | 必须保留旧长文本EOS截断行为，不能擅自换成tokenizer truncation=True或LLM encoder。 |
| 折清单 | 复用已有冻结outer及inner名单 | 在内存重建4/4完全一致；不换seed、不重新挑折。历史paper协议与v2拟采用nested协议分别记录。 |
| G*选型 | 暂不改文档方案，只列建议 | 使用outer-test分数选G*会让测试参与选择；建议内层选择或预固定报告所有剖面、排名仅探索性。需用户同意，尚未实施。 |
| nested checkpoint绑定 | 暂不实现，只记录接口差异 | 旧paper_checkpoint写死paper_kfold/CV validation等绑定；建议后续在v2旁路适配，而不是直接把历史保存器当nested使用。需用户确认，未修改。 |
| 不见于train的已注册关系 | 保留既有审计语义，后续按支持量判断梯度 | 不要求仅val出现的关系必须有非零训练监督梯度；本轮没有新增梯度逻辑或模型参数。 |
| Git与旧文档 | P0先只新建记录；本轮按明确授权追加三个文档 | 保留执行历史，三份当前记录统一说明验收已过、下一步尚未启动、GitHub暂未同步。 |

**38.4 输入图、标签、特征与身份核验**

入口为 `integration/rebuild.py::DEFAULT_MANIFEST`，即 `scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1/build/manifest.json`，文件SHA为 `47150dc1d15c078291e6f52fccc6e070b968501b723653a2bca18f8ec8a1ac67`。依据各任务记录取得真实路径，未按相似文件名猜选图。

| 任务 | 文件数 | 节点 | 原边 | 节点类型/边类型 | 原始canonical数 |
| --- | --- | --- | --- | --- | --- |
| 重入合约 | 142 | 18312 | 19267 | 16/8 | 89 |
| 访问控制合约 | 114 | 13432 | 15538 | 16/8 | 86 |
| 重入节点 | 71 | 12036 | 11710 | 16/8 | 77 |
| 访问控制节点 | 57 | 7710 | 8840 | 16/8 | 81 |

完整图路径、SHA、source_file到唯一源码路径/SHA、逐节点类型与边/canonical计数在 `RECON.md`第1项及 `recon.json → graphs.tasks`。四任务无缺源码，节点ID均为int。原属性键为code、label、method、node_info_vulnerabilities、node_source_code_lines、node_type、source_file、token、type_label。

两个合约任务文件/节点/边数量与仓库PAPER常量记录的论文表1一致；节点任务是漏洞文件HCG子集，不直接与完整语料表1比较。数量一致不证明作者标注语义完全正确。本批保留作者标签，不重新处理此前buggy_18等标签争议，也不把节点分数改称去重源码行分数。

其余5类仅确认作者HCG、CFG与源码路径存在，未加载、分析或训练；这些路径在RECON“以后扩展”小节。

**38.5 状态变量锚点的失败、授权及最终验收**

投影链为原源码AST字节身份→view.mapping→compat_ids→Projector.by_ast，不按行号邻近猜测。所有验证成功的状态声明目标均为原HCG的new_variable。

| 任务 | 原SourceView锚点/总声明 | 原比例 | 用户批准的SupportedSourceView | 批准比例 | 批准口径验证文件 | ordinary_nodes_checked |
| --- | --- | --- | --- | --- | --- | --- |
| 重入合约 | 2236/2369 | 94.39% | 2360/2369 | 99.62% | 140/142 | 16992 |
| 访问控制合约 | 804/922 | 87.20% | 872/922 | 94.58% | 108/114 | 12476 |
| 重入节点 | 1682/1788 | 94.07% | 1788/1788 | 100% | 71/71 | 10977 |
| 访问控制节点 | 376/403 | 93.30% | 403/403 | 100% | 57/57 | 7495 |

原AC合约87.20%低于P0的90%门槛，已真实暂停并征求用户，而不是直接放宽阈值。其6个多pragma文件在已有SupportedSourceView下恢复68个状态声明；这68个均存在原图精确锚点。用户批准后用支持视图验收，阈值仍90%。原 `graphs/summary.json` 的 `anchor_gate_passed/all_anchor_gates_passed` 保持原SourceView口径，AC仍false；`recon.json → source_view_decision.accepted_gates`另记批准后四任务true。

批准口径仍有R合约9个、AC合约50个声明未验证，原因是缺版本证据或区间跨词法作用域边界；保留在分母和回退记录中。这不是已证实“原图缺少状态节点”。四任务无解析失败；已验证文件中未发现状态声明缺少new_variable锚点。逐文件原因、声明原文、原始行与字节范围见逐文件graphs JSON。

上述选择仅确定v2后续应复用哪个前端，本轮没有修改旧frontend或原scalar分析器。

**38.6 语句覆盖与token实施细节**

语句覆盖逐AST身份核验：expression、variable declaration、if、for/while、return、emit/revert、modifier/constructor上下文及for-update。emit/revert在已验证文件中没有独立HCG锚点；不新增节点来隐藏损失。modifier/constructor统计是普通语句的重叠子集，不能与普通分类相加当总量。do_while_statement/throw_statement未在本次AST类型枚举中观察到，不据此推断所有源码文本都没有其他语法表示；老式同名函数构造器也未自动猜测为constructor_definition。

legacy `var acc = Acc[msg.sender];` 的当前grammar结构已打印：variable_declaration_statement下含无字段variable_declaration，内部type:type_name→primitive_type→var、name:identifier acc；右侧value:array_access含base:Acc与index:member_expression(msg.sender)。证据 `graphs/legacy_var_ast.json`。仅验证解析，没有solc编译验证。

特征核验实际读取既有encode/review/verify代码及来源记录，使用 `Salesforce/codet5p-770m` 的 `RobertaTokenizerFast`，revision `3f7cc6e80aee6612f41253b5ee28f09f86faa35f`，本地缓存离线加载。输入为node.code原样文本，保留DOT引号/转义，未去引号或归一化。先add_special_tokens=True得到ID，再encode_ids取前512、右补pad=0，输出float32[512]；bos/eos/unk=1/2/3，不加载encoder权重。截断可去掉末尾EOS，因此不能直接换其他截断API并假定等价。

每任务独立seed=0随机抽200节点，总800/800逐元素完全一致；四任务抽样中截断长节点分别3/2/1/2。全图dtype/shape已枚举，但本次并未把全图所有向量全部重新编码。一次839-token警告发生在手动截断之前，最终向量一致；不是encoder运行失败。原始下载融合图没有token，这些特征来自此前本地补充，不应称为作者随图发布的LLM语义向量。

证据位于token/selection.json及seal、每任务nodes.json/vectors.npz/mismatches.json、summary与execution_receipt；输入196路径前后核验一致。

**38.7 冻结协议与实际训练数值的记录**

| 任务粒度 | Adam初始LR | OneCycle max_lr | div_factor | weight_decay | 原外层K |
| --- | --- | --- | --- | --- | --- |
| 合约 | 0.0005 | 0.01 | 20 | 0.000005 | 5 |
| 节点 | 0.0002 | 0.005 | 25 | 0 | 10 |

共同数值：hidden128、2层、8头、dropout0.2；Adam默认betas=(0.9,0.999)、eps=1e-8、amsgrad=False。OneCycle余弦50 step、final_div_factor=1、cycle_momentum=True、base/max momentum0.85/0.95，scheduler创建后beta1=0.95。每轮一次train监督optimizer step，再scheduler step，再post-update eval。最大50轮、patience7、delta0.001、无类别加权cross entropy。best严格选最低验证loss，delta用于停止计数，不把best保存也改成必须改善0.001；last分开。

历史实际为paper_kfold，同一CV val选best和评分，保留CV validation名称。v2文档拟用nested：inner val早停/选best、outer test评分；P0只核对资源和接口，不执行这套新训练。

已有冻结outer和inner文件都存在，4/4在内存用原make_fold_document重建完全一致，没有重新生成落盘或修改旧折。fold0的inner_train/inner_val/outer_test数量：R合约90/23/29、AC合约72/19/23、R节点50/13/8、AC节点40/11/6。paper主train是inner_train与inner_val并集，其val即上述outer列表；这不允许混称两套协议结果。

seed规则：split=1；inner=seed×1009+fold+1；constructor=10000+fold+合约任务1000；pair=constructor+77；fit=constructor+1000000。每任务标签、paper/nested清单、源码manifest和SHA在 `protocol/protocol_resources.json`；合约标签文件为contract_name/targets列表，节点标签在冻结图属性中。90份历史实际fit配置与任务manifest逐项一致。本轮未修改任一配置。

**38.8 原标量覆盖基线与输出图**

保持原 `integration.pipeline.build_graph(profile="scalar")`，从同一原HCG和源码重跑四任务。源码函数总量包含带body的FUNCTION_TYPES；因文件级门槛不能进入旧分析的函数仍计入总分母，避免高估覆盖。

| 任务 | 原源码总函数 | 可进入旧文件分析 | 支持函数 | 被文件门槛排除 | DATA_DEF_USE新增边 |
| --- | --- | --- | --- | --- | --- |
| 重入合约 | 3404 | 3166 | 2035 | 238 | 3561 |
| 访问控制合约 | 3148 | 2745 | 2128 | 403 | 4032 |
| 重入节点 | 2045 | 1917 | 1210 | 128 | 1894 |
| 访问控制节点 | 1958 | 1832 | 1550 | 126 | 2836 |

原合约覆盖与方案文档2035/3404、2128/3148一致。主要回退包括modifier、继承、非标量string/bytes/var等及不确定调用版本；每任务Top 10按原reason字符串聚合，完整计数见scalar/summary.json和RECON第6项，未为了降低回退数量改规则。

每任务输出 `scalar/<task>/hcg.gpickle`、audit.json、inputs.json、manifest.json；图节点与属性、原CFG/CG边由原assert_preserved检查，输入图/源码在处理前后核SHA。四任务projection_fallback均0；新增边是新对照产物，不覆盖当前训练输入。总函数=可分析文件函数+文件门槛排除，支持函数+函数回退数=可分析文件函数，两项守恒均通过。

**38.9 历史资源估计与限制**

只读统计overall_cv_v1实际60次fit与guard_extension_v1实际30次新fit，不把历史引用重复计数。按任务R合约/AC合约/R节点/AC节点列出单fit耗时中位数：

| 历史变体 | R合约(s) | AC合约(s) | R节点(s) | AC节点(s) |
| --- | --- | --- | --- | --- |
| HCG | 184.68 | 128.83 | 186.22 | 105.76 |
| HCG_DDG | 204.89 | 140.51 | 189.72 | 98.10 |
| HCG_DDG_GUARD | 179.75 | 133.74 | 209.44 | 117.42 |

overall 60fit累计9466.39s（157.77min），最大allocated2709.92MiB/reserved2878MiB；guard 30fit累计4959.45s（82.66min），最大allocated2894.40MiB/reserved3068MiB。最低整卡空闲分别19/29MiB。历史耗时有不同停止轮数和设备状态，不是严格公平速度基准，更不能保证v2新增env_source后仍满足4GB显存。原“150fit约7小时”仅粗估，需后续Prompt 7实际预检；P0没有启动这些训练。

**38.10 验收命令、测试和保护边界**

P0原实际环境为WSL/mando Python3.7.12，TREE_SITTER_LIB_DIR指向原项目 `build/linux-x86_64`，PYTHONDONTWRITEBYTECODE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2。实际复跑入口如下；每次必须使用全新输出目录，不能覆盖本次证据：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
# 下列路径只是独立复跑示例；本次原产物位于 artifacts/dfg_v2/recon/
python -B -m scripts.DFG.dfg_v2.recon_graphs --output /tmp/dfg-v2-p0-repeat/graphs
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -B -m scripts.DFG.dfg_v2.recon_tokens \
  --output /tmp/dfg-v2-p0-repeat/token --sample-size 200 --seed 0
python -B -m scripts.DFG.dfg_v2.recon_protocol --output /tmp/dfg-v2-p0-repeat/protocol
python -B -m scripts.DFG.dfg_v2.recon_scalar --output /tmp/dfg-v2-p0-repeat/scalar
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

P0原回归结果223 passed、0 failed、29 warnings、4.03s；警告来自旧DGL distutils和NetworkX read_gpickle弃用。并非全仓库全部测试。5个新审计/报告脚本Python3.7语法检查与已有目录拒绝覆盖通过；28个汇总证据摘要、图计数和函数分母守恒、4份scalar图SHA及报告UTF-8检查通过。单独记录在regression.log与validation.json。没有新增分析算法，因此P0没有声称增加新的DFG语义单元测试。

P0修改前后11063个受保护已跟踪文件SHA一致，PROMPTS不变，原15个未跟踪路径保留。该数字是P0快照的结论；本轮授权后HANDOVER与训练文档当然会变化，不篡改原protection.json。此次单独验证三文档旧字节前缀保留、修改范围仅这三份文档、内容与recon.json对应，无需为纯文档追加重新执行模型/训练回归。

**38.11 GitHub同步过程、暂停决定及后续操作**

P0只产生本地提交085eb86，尚未push。本轮用户起初授权更新GitHub并要求一致，故先尝试WSL `git fetch origin dfg-v2`，失败为“Could not resolve host: github.com”。Windows DNS可解析，使用现有Windows Git和当前真实worktree Git元数据进行只读ls-remote；未取得有效凭据助手，失败为gh不可用/终端交互被禁用，没有成功得到远端引用。没有下载工具、改变DNS/代理、读取或打印token、重置/合并分支，也没有执行push。

随后用户明确指示“如果wsl无法解析就先不推送，等我解决了再推送，你先完成其他的”。从此停止网络排查和所有推送尝试；本轮只完成三个文档及本地提交。**当前不能声称本地与GitHub已经一致，也不能将缓存origin/dfg-v2当作实时远端证明。**

后续用户解决网络并要求继续时：先fetch origin dfg-v2，核对远端更新及祖先关系；若远端新增提交则先审查并正常整合，不force push。确认后推送当前dfg-v2，再通过ls-remote/fetch核验远端refs/heads/dfg-v2与本地HEAD完全相同，并检查三个文档位于同一提交中。不要推到upstream/MANDO-Project，不自动合并main或ddg-v1.1-correctness。原锁文件、旧CSV、图/权重等本地资产不混入这次文档提交；代码/汇总同步不等于完整实验二进制上云。

**38.12 当前结论与下一步**

P0已按用户批准的SupportedSourceView策略完成前置验收，下一步是Prompt 1骨架/模型输入，当前未启动。v2关系与多层增强、G0–G3R模型接入及新嵌套训练尚未实现，不能用本次旧scalar复跑宣称新方案有收益。原emit/revert投影缺口、复杂语义/编译未验证、作者标签争议及单seed历史实验边界均保留。

后续G*选型与nested checkpoint适配建议尚待用户确认；不把记录建议写成批准实施。本轮对三文档采用追加式更新，旧文与历史实验身份完整保留。设计核验、实施、审阅与记录AI：Codex。

**38.13 2026-10-23 用户重新授权后的GitHub推送完成补记（Codex）**

用户要求再次尝试推送，并询问是否由策略保护造成。本次先重试WSL fetch，仍返回“Could not resolve host: github.com”；因此没有把网络失败解释为GitHub拒绝或本地提交失败。只读确认现有WSL凭据助手位于/usr/bin/gh，改用已有Windows Git联网，并临时配置 `credential.https://github.com.helper=!wsl.exe -d Ubuntu-22.04 -- gh auth git-credential`。第一次使用Linux绝对路径时被Git Bash自动转换成Windows路径而失败；改为在WSL内按已有PATH调用gh后fetch成功。不下载工具、不读取或输出凭据、不更改全局Git或网络设置。

fetch得到真实origin/dfg-v2=29a9b4efdedb2f897dc78c6b332a526ab9994fee。本地HEAD=e76eec189dd89542f7b24520ce84bd7f0c813c54，merge-base祖先检查通过，包含两个待推送提交085eb86与e76eec1。使用正常 `git push origin HEAD:refs/heads/dfg-v2` 成功，远端返回29a9b4e..e76eec1；没有强制推送，没有修改main、ddg-v1.1-correctness或upstream仓库。

这一结果说明此次失败并非分支保护或审批策略拒绝；本地commit只写本地对象，GitHub push还需网络解析及认证，两者不能混同。WSL DNS故障仍存在，本次通过Windows已有网络路径和WSL已有认证完成同步，未声称修好了DNS。

本补记同步追加到HANDOVER与PROGRESS，原38.11的暂停决定作为当时状态保留。Prompt 0及三文档主体已成功上传；本补记提交后继续正常推送，再用实时ls-remote核对最终本地HEAD与远端refs/heads/dfg-v2。只有SHA相同才在交付中声称同步完成；新状态不回写旧P0审计/历史seal，也不上传图、checkpoint和锁文件。整个补记过程没有运行新测试或训练，没有改变任何计算代码。实施与核验AI：Codex。


## 39. 2026-10-23：DFG v2 Prompt 1骨架、模型输入与构造验收（Codex）

**39.1 授权、版本与冻结边界**

用户要求先读PROMPTS第4.1节共享上下文，再实施Prompt 1；合理替代设计先征求同意并记录。本轮基于修订1f2a3088d3f5299a89e18b4f8e203412cf2faaaa。使用已有Windows Git访问同一WSL工作树，临时复用WSL gh凭据助手，pull --ff-only origin dfg-v2返回Already up to date。没有改DNS/代理/全局Git设置，没有checkout/reset；不把P0旧文档当作当前方案。

新代码仅在scripts/DFG/dfg_v2/，三份记录按允许规则追加。本轮不扩展程序分析，不改原HCG/DDG/HGT/tokenizer、训练参数/损失/早停/划分，无fit。独立验收目录scripts/DFG/experiments/artifacts/dfg_v2/prompt1_v1/，不覆盖P0及旧批次。before.json保存原HEAD、PROMPTS SHA、11060个冻结已跟踪文件摘要、三文档原长度/SHA。

**39.2 方案选择及批准记录**

| 项目 | 文档要求或代码事实 | 实施决定与原因 |
| --- | --- | --- |
| 历史reflect测试 | 文档要求原DATA_DEF_USE同类型双向；实际graph_utils已修复为单向，既有测试也覆盖 | 先询问，用户选择“同意按当前代码事实修正测试（推荐）”。新测试验证DDG单向、next_line反射、G3R显式REV。未伪造错误期望或撤销旧修复，PROMPTS正文不改。 |
| 主聚合 | 原HGT跨canonical mean | 默认原HGTLayer；nonempty_mean仅显式可选诊断，不擅自替换主实验。 |
| 无入关系辅助节点 | 原HGT已有零消息分支 | 直接复用，不修改冻结核心或添加隐式反向边。 |
| 辅助标签 | env_source不是源HCG监督样本 | 仅对原节点调用旧标签规则；内部aux行-1哨兵并排除监督，不写回图、不编造clean标签。 |
| 构造/核验 | Stage G构造顺序适用，旧deep reflector/pool核验不识别v2 | 在v2复制必要构造并标来源SHA，复用native schema检查，另核对v2端点和aux掩码。原forward与池化计算直接继承。 |
| 后续决策 | 新PROMPTS已确定SupportedSourceView、ProjectionView、G* inner选择、nested checkpoint包装 | 遵循新文档；P0的“待确认”是历史记录。本轮不提前实施P2–P9。 |

唯一需修改文档预期的选择已获得批准。其余为落实既定模型输入/监督要求的接口细节，不改变训练任务或DFG语义范围。

**39.3 新文件与职责**

| 文件（相对scripts/DFG/dfg_v2） | 内容 |
| --- | --- |
| __init__.py | VERSION=dfg-v2；DATA_DEF_USE/WRITES_STATE/READS_STATE/ENV_FLOW及四REV；ENV_SOURCE、AUX_NODE_TYPES、PROFILES、REVERSE_OF。 |
| model_input.py | 直接原generate_hetero_graph_data；原边原reflect，新正向不反射，G3R显式REV；DGL节点数/类型内行号检查。 |
| model.py | 原节点/合约分类器子类、make_model、v2注册检查；inside_token/nodetype、原构造顺序、aux监督mask和池化排除。 |
| supervision.py | DfgV2Supervision，保持targets/forward/manifest/mask/full_ids，节点监督排aux，合约文件监督不变。 |
| hgt_layer.py | 可选诊断HGTLayerNonEmptyMean；继承原构造，复制forward仅改跨关系聚合。 |
| tests/test_model_input.py | 32项输入/剖面/反向/拒绝条件/原图保留及批准后的历史行为测试。 |
| tests/test_model.py | 28项构造/前向/RNG/监督/池化/特征/注册/梯度/来源测试。 |
| tests/test_hgt_layer.py | 5项稠密等价、稀疏/空关系/无入边、反向及local_scope测试。 |

复制和参考来源在代码头记录：
- experiments/e23_pilot/model.py SHA256：00472900d131fe9cfc20db09ff20d910edde7ebdc82b59b100bdb2282610f141。
- experiments/paper_runtime.py SHA256：319159bec961320307083f63dea2f4fb5eed3559db401c542bcd0af6eca6218e。
- sco_models/model_hgt.py SHA256：4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947。
- Stage F model_adapter.py SHA256：90c49bf72d33a87e53e6edcc85f7438bf0792cac43f7517a6bac8b8ab4737086。

无FunctionType重绑定。来源有摘要测试，复制改动有旧输入数值等价测试，没有新增训练器。

**39.4 图输入、方向与不变量**

G0不允许v2关系；G1允许DATA_DEF_USE；G2增加WRITES_STATE/READS_STATE；G3增加ENV_FLOW和env_source；G3R的NetworkX输入同G3，仅materialize产生REV。普通关系沿用原reflect的键顺序、同类型反射、平行边/自环数值行为；新正向关系不隐式反射，canonical冲突报错而非覆盖。

拒绝未知profile、不允许的v2关系、REV输入、非整型/负数/形状错误端点、非MultiDiGraph、缺失/错误node_hetero_id、G0–G2含aux；模型仍拒绝跨文件边。build_dgl不重编号或修改输入；构造器如Stage G在深拷贝中建立连续模型行号，original_graph_node_ids保存原ID对应，内部行号转换不写回作者图。

fingerprint包括原节点顺序/属性/标签/token以及基础边key/属性。测试保留孤立节点、平行原边及同端点不同关系；num_nodes_dict来自原工具，非按边端点推断。

**39.5 模型构造、特征与监督**

保持Stage G分配顺序：空gcs容器→各类型adapt_ws→HGT层→classify，没有额外随机模块。inside_token调用原get_node_token，要求有限浮点矩阵和一致宽度；nodetype调用原onehot。当前冻结任务使用float32[512]；本轮未重编码tokenizer。

G0两个任务同seed下state_dict逐tensor、构造后RNG、eval及固定RNG的train forward精确一致，监督manifest/mask/targets也一致。nodetype另对原生产分类器比较初值/前向。这不表示不同schema的G0/G3初值相同；跨剖面语义配对初始化仍属Prompt 7。

节点任务不读aux标签。内部全模型行标签中aux为-1，且不进入full_ids、valid/buggy分组或mask。测试特意将无标签env放在第一行，确认原标签行未偏移。合约仍forward(files)，node_ids_by_filename提前排除aux，原mean计算保留。aux经ENV_FLOW可影响监督目标，有独立adapt_ws，但自己不监督、不池化，不向图写伪标签。

注册检查先native_registration(deep=False)核对node/canonical编号、参数bank和edge id；随后核对v2方向端点、类型行表、features/labels、监督mask和池化行。没有错误复用旧Stage G deep reflector来检查v2。

**39.6 nonempty_mean诊断细节**

默认mean使用冻结HGTLayer。显式nonempty_mean继承同一构造，forward保留k/q/v、关系注意力/消息、edge_softmax、skip、dropout、a_linear和norm，只改multi_update_all的stack及逐节点有效入关系平均。

DGL 0.6.1按图canonical edge ID排列stack，掩码同序，不根据参数bank编号猜测。无入边关系不计分母；全零入度时消息零，原a_linear偏置/残差/norm仍保留，所以不是节点最终输出恒零。空关系参数保留，分母不计；无入关系env_source也可前向。

稠密支持下与原mean输出误差≤1e-6，反向一致，两种norm配置覆盖；初值/RNG一致。独立只读探针还验证了异源类型、反序参数ID、空关系与孤立节点类型，未发现stack错位。

**39.7 测试、实际命令与审查**

已有mando Python3.7.12/PyTorch1.8.1/DGL0.6.1，未安装升级依赖。CPU运行，OMP/MKL各2线程，grammar使用既有目录。minimal.sol经原generate_cfg_from_source构图，512维零token、显式测试标签、手工关系仅验接口；不当作新语义分析结果，也不等同Solidity编译验证。

定向输入32、模型28、诊断层5项通过。随后v2完整合跑65 passed、0 failed/skipped、8 warnings、5.44s；旧DDG+graph_utils 223 passed、0 failed/skipped、29 warnings、3.55s。共288项，非全仓库测试全集。警告来自DGL distutils和NetworkX gpickle弃用，未隐藏、未放宽关键断言。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

实际归档命令另带--junitxml，保存prompt1_v1/v2_tests.xml、regression_tests.xml及完整合并stdout/stderr日志。G1/G2/G3/G3R的node/contract新增relation_msg均有非零梯度，证明连接可反向，不等于所有真实数据关系都会非零或提升F1。未调用optimizer.step或fit。

独立只读审查另用seed19和小hidden/heads核对G0初值/manifest/前向，并验证node/contract×inside_token/nodetype的无标签env前后向、原图fingerprint保持。未发现本步阻断，未修改冻结文件让测试通过。

**39.8 保护、三文档记录与本地提交**

11060个受保护已跟踪文件逐SHA一致，PROMPTS正文一致；旧分析/HGT/训练及已跟踪产物不变。HANDOVER、training_changes、PROGRESS仅追加，按before.json原字节长度截取前缀核SHA。新增模块SHA、JUnit计数及保护结果保存prompt1_v1/validation.json。旧锁/CSV/P0资产未stage、删除或上传。

测试及保护通过后按共享上下文将8个新代码/测试文件与3份记录作Prompt 1本地提交。本轮不push；不能声称Prompt 1已在GitHub。P0已同步是历史状态，新增提交的远端状态分开说明。

**39.9 限制和停止点**

本步仅关系输入/模型/监督骨架。L1 aggregate扩展、L2状态锚点、L3环境读取及真实token、新图覆盖、Oracle、nested训练/checkpoint、跨schema初始化、GPU显存验收均未在此步完成。只验固定图forward，继承的旧extend_forward未验收为v2推理入口；后续按Prompt 9单独实现。

未训练、未改作者标签或解决历史困难文件争议，未下载/执行solc。不能据小图测试声称完整Solidity DFG、七类验收或检测增益。默认mean不变。完成Prompt 1本地提交后停止，下一步按用户指令进入Prompt 2。实施、复核与记录AI：Codex。


## 40. 2026-10-23：DFG v2 Prompt 1b显式双向主剖面（Codex）

**40.1 授权、版本与执行边界**

用户明确选择“two-way approach”，要求读取PROMPTS.md并执行Prompt 1b。本轮先核对第4.1节共享上下文、第3.1节理由和4.3b实施要求；在分支dfg-v2、开发树ge-sc-llm-ddg-v11上执行pull --ff-only origin dfg-v2，返回Already up to date。实施起点HEAD为0449355cb1b644869a45b747ad76198250783ef1，包含已修订的双向主剖面说明；此前Prompt 1实现提交4ec8806已包含在该分支中。没有checkout/reset、迁移旧批次或修改全局网络/Git设置。

本步只调整剖面声明、模型输入反向生成和必要测试。DDG分析算法、原HGT、tokenizer、监督/池化实现、训练器、标签、固定折及已有图/权重不改；无fit、无optimizer.step。独立产物目录为scripts/DFG/experiments/artifacts/dfg_v2/prompt1b_v1/，原prompt1_v1与recon不覆盖。before.json记录11072个受保护已跟踪文件摘要、允许修改清单、三文档旧长度/SHA及旧未跟踪路径。

**40.2 配置选择、原因和向后边界**

| 配置 | 正向语义关系 | 模型输入中的显式反向 | 用途 |
| --- | --- | --- | --- |
| G0 | 无v2关系 | 无v2反向 | 原HCG基线 |
| G1R | DATA_DEF_USE | REV_DATA_DEF_USE | 双向局部数据依赖 |
| G2R | G1R正向＋WRITES_STATE、READS_STATE | 对应三种REV | 双向状态读写关联 |
| G3R | G2R正向＋ENV_FLOW | 对应四种REV | 主方案，含环境上下文传播 |
| G3 | 四种正向关系 | 无 | 只有正向的方向对照 |

按用户已批准的Prompt 1b移除默认G1/G2名称，不把旧名字静默改成双向别名。历史P1文档及结果的G1/G2含义保持原样；本轮未迁移或重命名任何旧产物。以后若确需局部单向对照，可显式在PROFILES中登记G1={DATA_DEF_USE}等；测试已证明无须修改构造器。主配置选择来自用户本轮授权，不是根据新实验F1择优；本轮没有产生训练F1。

正向NetworkX图仍只存语义事实，人工REV只在模型输入阶段生成。对(s,R,t)生成(t,REV_R,s)，不把反向消息解释为反向定义—使用事实，也不把正反方向混入同一个关系参数。G3/G3R同一NetworkX图得到的DGL输入只差REV canonical；G0及普通CFG/CG关系保留原reflect行为。

**40.3 实际修改文件与核心逻辑**

| 文件（相对scripts/DFG/dfg_v2） | 修改内容与原因 |
| --- | --- |
| __init__.py | 默认PROFILES改为G0/G1R/G2R/G3R/G3；新增forward_relations、has_reverse；导入时校验REV必须同时声明对应正向，动态注册读取时也校验。 |
| model_input.py | materialize按has_reverse生成端点互换的独立canonical，不再硬编码profile等于G3R；build_dgl按是否允许ENV_FLOW判断env_source资格。 |
| tests/test_model_input.py | 旧G1/G2用例迁移到新主配置；增加各剖面反向数量/方向、同NX对照、原WRITES_STATE反射混淆、临时配置和导入错误测试。 |
| tests/test_model.py | 按forward_relations组装合成图；覆盖新主配置梯度；扩展双向aux监督/池化不变量；增加临时G1等价及两文件环境上下文干预测试。 |

model.py、supervision.py、hgt_layer.py均未修改。test_hgt_layer.py没有G1/G2引用，原5项测试保留并重新运行，未为满足文件清单而无谓改动。PROMPTS.md正文保持实施起点版本；本轮完成状态以本节和PROGRESS追加记录为准。

原输入拒绝规则继续生效：未知剖面、剖面外正向关系、NetworkX内REV、canonical冲突、错误端点类型/形状、类型内行号错位、跨文件边、错特征/标签/schema均拒绝。原节点、顺序、属性、标签、token、基础边key/属性的fingerprint不变；辅助节点仍不监督、不参加合约mean池化。没有通过删除样本或原边实现双向化。

**40.4 原反射风险与显式REV的验证**

保留已批准的P1事实：当前原reflect_graph已有DATA_DEF_USE特判，仍是单向；普通next_line仍反射。新测试直接证明，将WRITES_STATE交给原反射时：

1. 两端同类型，0→1与1→0被并入同一canonical键。
2. 两端不同类型，人工反向键与真实反方向WRITES_STATE同名；同时输入真实反向事实时，两类端点被合并，无法按关系名称区分。

v2适配器把这些正向事实隔离于原reflect之外，独立生成REV_WRITES_STATE，验证真实反方向事实保留原端点且不被人工反向覆盖。G1R/G2R/G3R每个新正向canonical都有端点交换、数量相同的独立反向；G3没有REV。测试包含同类型、异类型及同时存在真实相反方向事实的情况。

**40.5 环境上下文：实际前向证据及解释边界**

基于minimal.sol经原构图器生成两个互不连接的文件HCG，按文件各加一个相同键msg.sender、相同512维输入的env_source；两个使用处使用有意不同的合成512维向量。使用原HGT、两层、CPU、eval、seed43；不是新的tokenizer生成器或源码语义提取器。

在每个剖面内部重新创建两模型并逐张量确认初值相同，只扰动second.sol使用语句特征，读取每层真实env隐藏表示。按source_file和实际node_hetero_id定位，避免位置猜测；不直接用G3/G3R不同schema随机初值之差证明传播。

| 两层后最大绝对差 | G3 | G3R |
| --- | --- | --- |
| 两文件同键环境节点表示之差 | 0 | 0.22999882698 |
| 只改second.sol使用处后，其环境表示变化 | 0 | 0.23695075512 |
| 未改文件minimal.sol的环境表示变化 | 0 | 0 |

节点与合约构造两任务均得到上述结果；第一层也分别验证。说明REV_ENV_FLOW确实将使用上下文送入环境节点，且没有跨文件串联。完整数值保存在environment_context_probe.json。原模型前后向测试还覆盖所有新canonical的非零message参数梯度，但仅针对本测试中有监督路径的手工关系，不把真实数据无训练支持关系要求成必有非零梯度。

对第3.1节理由作必要限定，不擅改方案：
- “只有出边”等于沿该新关系无法接收使用者信息；不能推导原节点完全收不到其它CFG/CG路径的信息。
- G3无入边env仍有可学习投影、偏置/残差/norm；输入token固定不等于每层表示就是原始固定token。这里证明的是eval下缺少本图使用上下文，而非完全不能学习。
- “影响最大”尚无本步实验证据。反向增加信息通路，不保证F1提升；同文件环境中转提供共享键上下文，不证明不同函数处于相同调用者/交易。
- 状态读写中转关系不等于已完成精确别名、写覆盖或跨函数数据依赖。Prompt 1b没有扩大分析支持范围。

这些是结果表述边界，并未偏离已获同意的双向主方案或新增实验模块。

**40.6 测试命令、数量和警告**

沿用mando Python3.7.12、PyTorch1.8.1、DGL0.6.1和已有grammar，无依赖升级、无CUDA训练。先定向运行输入43项、模型38项，再执行全部v2及既有回归：

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_model_input.py
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_model.py
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

| 验收集合 | 通过 | 失败/跳过 | 警告 | pytest耗时 |
| --- | --- | --- | --- | --- |
| v2全部：输入43＋模型38＋诊断层5 | 86 | 0/0 | 8 | 13.16s |
| 原DDG＋graph_utils回归 | 223 | 0/0 | 29 | 6.19s |

最终集合共309项，不将定向重复运行重复计数，不代表全仓库所有测试。归档命令另加--junitxml，完整log/XML保存在prompt1b_v1；警告为已有DGL distutils及NetworkX gpickle弃用。G0原模型初值、RNG、train/eval forward和监督等价保持；诊断聚合原5项继续通过。独立只读复核确认干预测试没有不同初值混淆、跨文件错配或只查边存在的问题。

**40.7 保护、产物与三文档记录**

本轮4个代码/测试文件和三份记录为唯一已跟踪修改。11072个受保护文件逐SHA一致，包含PROMPTS、原HGT、v2模型/监督/诊断实现及冻结历史计算文件；旧未跟踪锁/CSV不删除、不stage。三文档按before.json的旧字节长度核对前缀SHA，只有末尾追加。新增产物只在prompt1b_v1，不混入代码提交。

before.json、v2_tests.log/xml、legacy_regression.log/xml、environment_context_probe.json与validation.json组成验收证据。validation记录代码摘要、测试计数、保护核验和执行边界；不改写P0/P1历史收据。按共享上下文第4.1节测试通过后提交本地dfg-v2，提交说明标明Prompt 1b。本轮没有新的push指令，未推送；不把起点已同步解释为新增提交已上传。

**40.8 完成程度与停止点**

已完成Prompt 1b配置和模型输入接入验收。尚未实施Prompt 2的L1扩展、L2状态锚点抽取或L3环境分析与编码；未生成真实v2增强数据集、未开展nested训练/显存预检、新图推理或F1评估。未下载/执行solc，解析生成测试图不等同编译合法性验证。

本步没有发现阻断双向接入的正确性问题；测试通过只证明指定接口与小图路由性质，不宣称完整Solidity DFG或检测增益。保留G3单向对照，后续效果由预定实验验证。完成本地提交后停止于Prompt 1b。实施、复核与记录AI：Codex。


## 41. 2026-10-24：DFG v2 Prompt 2函数内L1扩展及真实数据验收（Codex）

**41.1 授权、起点与不变部分**

用户要求先读PROMPTS第4.1节共享上下文，再实施Prompt 2；若提出实质替代方案须先征求同意并记录。已读取最新共享上下文、P2、原scalar/Stage J/K及P0/P1记录，pull --ff-only origin dfg-v2返回Already up to date。起点为55260099dc53603d5cc6f5a7a803d77fd5d77f98，Prompt 1b已按此前用户授权推送；本轮继续在ge-sc-llm-ddg-v11的dfg-v2分支开发。

本步全部生产和测试新增文件均位于scripts/DFG/dfg_v2/。旧DDG、原HGT、tokenizer、P1/P1b模型输入/监督代码、标签、固定折和历史产物不修改；不启动训练，不执行solc，不开始Prompt 3。before.json保存11077个受保护已跟踪文件SHA和三份文档原长度/SHA，验收目录为artifacts/dfg_v2/prompt2_v1/。

没有替换用户批准的方案，无新增待批准的设计选择。继续采用已有SupportedSourceView和已绑定版本元数据；旧成功函数走原SourceView与原标量结果。下面的AST形状适配和审计分类修正是实现明确要求的兼容性/正确性修复，不扩大程序分析范围。

**41.2 新增文件与职责**

| 文件（相对scripts/DFG/dfg_v2） | 内容 |
| --- | --- |
| l1_models.py | frozen V2Event，新增weak_writes，保留id/function/anchor/reads/writes/kind。 |
| l1_symbols.py | ExtendedSymbolTable保留声明身份和作用域，登记用户类型、数组、mapping引用、string/bytes与legacy单变量var；aggregate_info记录类型/位置，不改原Symbol。 |
| l1_access.py | ExtendedAccessExtractor：整体赋值/整体delete强写，成员/下标/push/pop/局部delete弱写，读取根和索引，拒绝嵌套写和重复目标。 |
| l1_cfg.py | V2CFGBuilder仅替换Stage J构造器的table/access，沿用ClosedScopeJ、StageFCallResolver、前缀modifier和原分支/循环/终止处理。复制来源及SHA写在文件头。 |
| l1_rd.py | solve_v2保留原工作队列、输出结构和统计；弱写GEN不KILL，强写KILL同一符号全部旧强/弱定义；块传递与事件顺序重放一致。复制来源及SHA写在文件头。 |
| l1.py | analyze_file及augment_l1：旧结果优先、只重试回退函数、函数级提交、按产生视图精确投影、端点去重及全局证据索引。 |
| l1_build.py | 冻结manifest/P0输入绑定、真实四任务构图、独立旧结果/solver/Projector核验、CPU模型注册与不覆盖产物。 |
| tests/test_l1_access.py | 38项类型/作用域/强弱访问/AST形状/嵌套拒绝测试。 |
| tests/test_l1_rd.py | 30项弱GEN、强KILL、分支、循环、不动点、无闭包、非法IR和旧solver全字段等价测试。 |
| tests/test_l1.py | 最终19项P2源码事实、回退无残留、投影、不变量、元数据和恢复route集成测试。 |
| tests/test_l1_build.py | 9项不覆盖、输入SHA/任务矩阵拒绝、零事实旧成功函数及证据篡改拒绝测试。 |

共7个生产模块、4个测试文件。既有代码没有修改；无FunctionType重绑定、无新模型结构或训练器。

**41.3 类型、作用域、强弱定义与CFG处理**

符号仍按函数/声明字节位置/名称唯一标识，继承原legacy/modern作用域与现代初始化自引用检查，不按同名字符串连边。类型位置在aggregate_info中记录，不能识别的类型和函数类型仍Unsupported。legacy单个var可恢复；当前grammar的var tuple没有原声明节点，仍整函数回退，不伪造声明身份。

整体赋值x=...和delete x为强写；x.f、x[i]、x.push/pop等基变量聚合操作为弱写。成员/下标访问读取根符号及索引；未知或状态根不升格成本地定义。tuple重复目标包括强弱目标重叠均拒绝。普通调用继续按已有规则读参数，不建立跨函数摘要或修改alias。

CFG是分析中间表示，未替换模型原CFG/CG。只支持Stage J已有的单个、无参、末尾唯一占位符的前缀modifier；复杂modifier、assembly、嵌套赋值/delete、无法确认终止调用等按原策略回退。模型节点集合不增加。

到达定义仍从真实分析CFG正向后继传播，分支取union、循环到不动点。强写覆盖旧强/弱定义；弱写仅追加可能定义；每个事件先读后写，不计算传递闭包。未能投影的定义仍参与覆盖，再在物化阶段丢弃无法映射的事实，不为补边猜近邻行号。

**41.4 实际grammar兼容处理与边界**

针对测试发现：现有tree-sitter将delete a[i]解析为array_access(base=unary(delete,a), index=i)，前缀--a[i]也类似。若只处理通常的unary(array_access)形状，会漏掉P2明确要求的delete下标弱写。

处理限于v2的顶层成员/下标base/object链：确认前缀操作符起点与整个表达式起点一致，沿AST字段识别根与索引，保留原始Span作为锚点。索引或调用参数中的赋值/update/delete仍触发Unsupported；不修改源码文本、grammar或原提取器。另覆盖透明括号的(arr).push(v)、(arr)[i]=v，避免遗漏弱定义。相关定向测试最初3失败/27通过，完成兼容处理与新增断言后38项全部通过。

这些样例由真实tree-sitter解析；部分用于解析器健壮性验证。本轮没有运行编译器，不能将解析成功、元数据中记录的compiled version或本地人工预期等同于独立solc合法性验证。

**41.5 旧结果优先、回退与投影**

analyze_file先调用原DDGBuilder.analyze_source。旧成功集合按函数清单减去明确回退记录判定，包含零事实函数；不以“有没有边”判断成功。旧成功函数事实按原顺序直接保留。只对旧回退函数尝试SupportedSourceView＋V2CFGBuilder＋solve_v2，旧文件级回退则逐函数重试。新视图失败时旧成功结果仍保留。

一个新函数完成CFG与RD后才提交事实；不支持语句即使出现在函数后半段，也不会留下前半段的部分DDG。任何definition/use锚点落在modifier_definition内的事实都过滤计数，避免把函数私有依赖挂到共享modifier节点；本批四任务计数均为0。

旧事实用原SourceView的Projector，新事实用SupportedSourceView的Projector。两视图可构造并可投影时by_ast完全相同；失败的来源不借用另一视图。Projector读取的label是保存AST身份的字符串，不是漏洞标签；分析不读取node_info_vulnerabilities、token或预测。

复用DDGBuilder.projected_edges：同端点合一、不加自环，ddg_fact_indices正确转为全局证据偏移；新边加dfg_v2_version及routes。证据中保留函数/符号/定义/使用身份和analysis_path。原节点、顺序、属性、源码映射、标签、token及CFG/CG边key/属性逐项保持；新图只增加正向DATA_DEF_USE，REV由P1b的G1R模型输入产生。

**41.6 恢复原因审计修正与保留证据**

首轮四任务已通过旧边、事实、solver和模型schema验收；检查报告时发现无名称的string或用户类型参数/返回值虽已通过扩展类型检查，却没有Symbol ID。因此仅检查aggregate_info会遗漏其v2_aggregate原因，少数函数被记为v2_retry或仅inheritance。

最终修复只改route判定：在已成功构造的函数中检查参数和局部声明是否需要扩展类型接受，包括未命名声明；并把顶层前缀AST适配单列v2_access_shape。新增两个回归用例，没有改变IR、facts、投影端点、原标签或模型计算。

首轮产物artifacts/dfg_v2/l1_build/保持不动。最终交付位于其新子目录artifacts/dfg_v2/l1_build/final_route_audit/。最终四任务全部重新验收，两个批次的每任务computation_fingerprint及投影事实身份多重集完全相等，只有审计route及相关边证明属性变化。比较证据为prompt2_v1/route_correction_comparison.json；旧收据未覆盖。

route可组合，表示实际采用的恢复手段，不是单因素因果贡献；不能把重叠route计数相加当作恢复函数总数。旧回退原因是原路径首先遇到的阻断，也不代表函数只存在该一种复杂结构。

**41.7 四任务最终真实数据结果（无训练）**

| 任务 | 原节点/原边 | 全部函数分母 | 旧支持→新支持 | 支持率前→后 | 原scalar DDG→L1 DDG | 增加 |
| --- | --- | --- | --- | --- | --- | --- |
| 重入合约 | 18312 / 19267 | 3404 | 2035→3128 | 59.78%→91.89% | 3561→5659 | 2098 |
| 访问控制合约 | 13432 / 15538 | 3148 | 2128→2791 | 67.60%→88.66% | 4032→5713 | 1681 |
| 重入节点 | 12036 / 11710 | 2045 | 1210→1960 | 59.17%→95.84% | 1894→3419 | 1525 |
| 访问控制节点 | 7710 / 8840 | 1958 | 1550→1856 | 79.16%→94.79% | 2836→3889 | 1053 |

函数分母与P0同一manifest和源码SHA绑定，包含文件级回退函数，不靠缩小分母提高支持率。节点任务仍为漏洞文件HCG节点任务，不改成去重源码行计分。这里只统计构图覆盖，没有新F1。

按旧首次回退原因分组的恢复数/原回退数：

| 任务 | modifier | inheritance_binding_not_supported | 非标量/推断类型 | 版本/多pragma/缺pragma等 |
| --- | --- | --- | --- | --- |
| 重入合约 | 251/441 | 374/374 | 218/258 | 247/287 |
| 访问控制合约 | 222/370 | 21/23 | 165/214 | 251/404 |
| 重入节点 | 83/127 | 363/363 | 130/161 | 171/177 |
| 访问控制节点 | 87/145 | 9/10 | 86/119 | 121/127 |

最终route分布（恢复手段可重叠；legacy单独为旧支持）：

| 任务 | legacy | modifier | inheritance | version | aggregate | access_shape |
| --- | --- | --- | --- | --- | --- | --- |
| 重入合约 | 2035 | 281 | 731 | 247 | 252 | 5 |
| 访问控制合约 | 2128 | 254 | 416 | 251 | 201 | 5 |
| 重入节点 | 1210 | 103 | 529 | 171 | 151 | 3 |
| 访问控制节点 | 1550 | 107 | 177 | 121 | 107 | 3 |

旧成功函数共6923个任务内实例（两粒度有重叠，非6923个独立源码函数）全部比较原solve与solve_v2的完整RDResult，facts/in/out/definitions/reachable/iterations/uses均一致；旧投影事实、端点和边重数逐函数一致，包括零投影事实函数569/286/382/159。by_ast对比通过文件实例为136/102/69/55；这仅统计两种视图都可构造的文件，并非把文件级版本回退排除出支持率分母。modifier事实过滤均为0。

四任务各用inside_token float32[512]、CPU、G1R构造一次对应模型并validate_registration。L1正向canonical数为21/22/21/22，对应独立REV相同数量，总新增类型组合42/44/42/44；逐canonical名称和边数存model_schema.json。参数量依次4871698、4871698、4715746、4789618。只做构造/注册，没有真实图forward、loss或optimizer。最终验收耗时约91.72/61.41/52.94/31.50秒，是CPU构图核验时间，不是训练耗时。

**41.8 剩余范围限制和结果解释**

四任务仍回退276/357/85/102个函数。完整Top10、旧原因→新route或仍回退原因的交叉表在各summary.json。主要类别是多个/带参数/带副作用或嵌套调用的modifier、版本域无证据或跨作用域边界、assembly、new_expression、inline_array_expression和真正嵌套写；均保留原文件和HCG。

当前L1是聚合基变量粒度：不同成员或数组元素会合并到同一声明的基变量上，弱定义是保守“可能更新”，不是字段敏感的数据流。用户类型中的contract/enum也按文档保守归为aggregate。ordinary call的聚合参数只记读取，内部函数对memory/storage引用的修改与别名传播没有摘要，因此不能宣称完整、无漏报的数据依赖分析。

单个前缀modifier恢复不等于新增控制依赖，也不等于支持任意modifier内联。新增跨函数状态锚点关系与环境源节点分别属于Prompt 3/4，尚未在本阶段实施。支持率与边数增加不证明漏洞检测F1提升，也未解决作者标签的历史争议。

**41.9 测试、实际运行命令与收据**

最终定向集合为38访问＋30RD＋19集成＋9验收入口，共96项。全部v2含P1/P1b共182 passed、0 failed/skipped、8条既有DGL/NetworkX弃用warning，8.06秒；原DDG＋graph_utils 223 passed、0 failed/skipped、29条既有warning，3.44秒。合计405项，不重复累计定向执行、不宣称全仓库测试全集。

MY_BANK.Collect预期5类def-use事实与acc弱写通过；弱写不KILL、整体赋值KILL、storage数组push、前缀modifier、string参数、晚失败无残留、旧fixture超集均通过。额外核验声明遮蔽、unknown/函数类型回退、重复tuple、嵌套mutation、空事实旧成功、SHA绑定版本、错投影不猜近邻以及标签/token干预不改变边。测试中最初版本元数据fixture不完整及CSV转义错误已按现有CSV/源码/行记录校验格式修正，未放宽生产校验。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l1_build --output scripts/DFG/experiments/artifacts/dfg_v2/l1_build/final_route_audit
~~~

上述构图命令是本轮实际执行命令；该目录已经存在，重跑须显式换新输出路径，不能覆盖。入口另支持--manifest、--baseline-summary、--max-iterations，未虚构原脚本参数。最终每任务含hcg.gpickle、audit/inputs/acceptance/model_schema/manifest/summary JSON；批次含summary.csv/json、run_inputs.json和receipt.json。输入图/源码/manifest/P0摘要、运行前后代码SHA均核验。原write_bundle会写旧adapter/version，本步在v2入口独立包装正确的v2 manifest，未修改旧工具。

完整测试log/XML、两次构图日志、route修正前后比较和最终validation在prompt2_v1。最终源代码与产物路径/摘要由该收据绑定，不把首轮旧route报告当作最终审计。11077个受保护文件SHA不变，三文档旧字节前缀一致。代码与三文档按共享约定本地提交，未stage图/锁文件或其他历史资产。

**41.10 停止点**

本轮完成Prompt 2的L1扩展、全部要求测试和四任务真实构图/模型注册验收，无方案替换待批。按共享约定本地提交后停止，未自动push、未启动Prompt 3/4/7/8或任何模型训练。实施、复核与记录AI：Codex。


## 42. 2026-10-24 DFG v2 Prompt 3：L2状态变量声明中转关系（Codex）

**42.1 起点、授权与修改边界**

本轮按最新PROMPTS.md第4.1共享上下文和Prompt 3实现。工作树为/home/zhao/SmartContract/ge-sc-llm-ddg-v11，分支dfg-v2，起点80afa66681ba46f848472895eae6871957a3c7ec；只读核验远端同一HEAD。before.json保存起点、11087个受保护已跟踪文件SHA、三文档原始字节数/SHA、l1_access.py原SHA和已有未跟踪清单。本轮不改PROMPTS、不改冻结DDG/HGT/tokenizer/训练代码，不覆盖旧图、标签、折或产物。实现、复核与记录AI均为Codex。

范围为在P2最终L1图上旁路添加L2；L2不依赖L1成功，不新建state节点，不实现L3、控制依赖或训练。旧HCG的节点集合、顺序、属性、标签和token，原CFG/CG边/key/属性及L1 DATA_DEF_USE边/证明属性均严格保留。模型仍由P1/P1b的G2R adapter生成独立REV关系，NetworkX中只存正向。

**42.2 文件清单与修改原因**

以下均在scripts/DFG/dfg_v2/：

| 文件 | 动作 | 核心职责/原因 |
| --- | --- | --- |
| projection_view.py | 新建 | 复制SourceView构造逻辑并注明原路径/SHA；只去掉scope_mode，mode=None，保留预处理token校验及raw/compat映射 |
| units.py | 新建 | AST精确投影并划分语句自己的表达式区域；有独立节点的for子表达式自己负责，缺投影的语句不得上挂父节点 |
| access_shape.py | 新建 | 抽取P2实际grammar的前缀delete/update访问链识别纯函数，L1/L2共用 |
| l1_access.py | 最小修改 | 原内联形状识别改调共享函数；6行增加、21行删除，四任务重建证明计算不变 |
| state_binding.py | 新建 | callable级保守局部遮蔽、C3/当前合约唯一状态绑定、常量排除、受限storage别名及接收者类型证据 |
| state_access.py | 新建 | 各Unit区域内READ/WRITE提取；赋值/复合/update/delete/tuple/index/确认数组push-pop及alias |
| l2.py | 新建 | 旁路加两种关系、去重、证据索引、分类回退与不变量检查 |
| l2_projection_audit.py | 新建 | 全部真实文件投影等价、声明锚点及恢复文件审计 |
| l2_build.py | 新建 | 绑定P2最终产物，四任务构图、L1回退独立覆盖、Top10度、固定抽边、CPU G2R注册、manifest/receipt |

新增测试8个：test_access_shape.py、test_projection_view.py、test_units.py、test_state_binding.py、test_state_access.py、test_l2.py、test_l2_projection_audit.py、test_l2_build.py，分别24/10/11/25/47/13/11/21项，合计162项。三份已有文档只追加本轮记录，所有原文保持。

**42.3 审查中确认的选择、用户批准与修复证据**

1. 用户明确批准push/pop类型核验。审批问题ID为call_813c0a5a2e4e40c890a79d25c61b0f9a，回复“同意，只对确认的数组记录 push/pop 写入（推荐）”。原模板按方法名识别，会把合约对象target.push(1)/target.pop()误判为写target。现只对接收者实际类型为动态数组或bytes记录READ+WRITE；固定数组、bytesN、string、合约和未知类型按普通调用读取可确认根及参数，记录跳过写入的理由。bytes是动态字节数组的实现口径，不泛化到所有字节/字符串类型。不增加完整类型系统或调用摘要。
2. 类型核验使用访问链选中后的类型，不只看状态根类型。struct.array、mapping[key]、多维数组元素逐层识别；alias初始化/重绑定保留指向位置类型，再解释alias后续访问链。union中有不同目标，分别依据证据判定。
3. legacy无数据位置的隐式storage只用于符合版本和类型证据的局部引用；参数/返回值不能仅因legacy就视作storage。memory/calldata不建storage别名；重复局部名禁用别名推断，名字仍用于保守遮蔽。这些是模板“局部p”的落实，不扩大支持范围。
4. 实际grammar的revert_arguments包装节点原先会漏遍历状态读取，已在新增L2提取器中修复并回归。原HCG无对应revert节点时，该读取被审计为unmapped，不猜测挂到相邻节点。
5. push/pop最小反例修复前定向测试2项失败，修复后相关state_binding/state_access共72项通过。证据在prompt3_v1/push_pop_fix/{before.log,after.log,after.xml,regression.json}，保存命令、前后SHA，不删除关键断言或更改错误期望。
6. 初次push_pop_review.json的顶层source字段被探针后续读取的Wallet源码覆盖，审计发现后保留原文件，新增push_pop_review_corrected.json。新记录绑定旧件SHA、正确反例源码SHA、旧反例事件、修复后重探结果和当前runtime；重新校验70处语料出现的源码SHA/字节跨度。明确旧事件与修复后事件不相同，不伪造“修复前输出”。该问题仅影响探针说明字段，未用于L2输入构图。
7. 原模板与实际既有代码无其他需要替换的方案。本轮未修订PROMPTS原文；批准的收紧在三文档与证据中记录，后续需按这些约束解释L2。

**42.4 语义、投影和失败处理**

局部遮蔽收集整个callable的参数/返回值/局部声明（包括出现在引用之后的声明）；按声明身份绑定，非同名即连边。C3必须获得唯一state_variable_declaration；ClosedScopeJ不支持时仅检查当前合约体内唯一声明，记录回退依据。this.x、Contract.x和a.x的属性x不会单独当状态；默认排除constant。

Unit中if/while/do只分析条件，for按现有独立HCG节点归属；callable节点只分析modifier实参，不吞入函数体。state声明只分析初始化表达式。分析器读取源码/元数据与AST，不从token/标签/预测提取关系。statement或state声明不能精确投影时记录unmapped/anchor_missing，保留样本，不按最近行号补边。

显式storage和有证据的legacy局部引用只接受状态根初始化/整体重绑定，可能目标取并集；不追踪alias-of-alias，不分析被调函数修改，不处理精确storage slot。L2本身流不敏感：跨函数“写→声明→读”表示共享状态上下文，不能解释为读必然读取该写的值。每个(src,dst,relation)只保留一条边，state_vars排序，via_alias取OR，evidence_indices保留所有对应事实；不加声明自环，不删除同端点其他关系。


**42.5 投影视图和L1无变化验收**

| 任务 | SourceView成功文件映射一致数 | P0 Supported锚点 | 本轮ProjectionView锚点 |
| --- | ---: | ---: | ---: |
| 重入合约 | 136 | 2360/2369 | 2369/2369 |
| 访问控制合约 | 102 | 872/922 | 922/922 |
| 重入节点 | 69 | 1788/1788 | 1788/1788 |
| 访问控制节点 | 55 | 403/403 | 403/403 |

四任务合计362个原SourceView成功文件实例，mapping/compat_ids/compat_nodes完全相同。R合约2个、AC合约6个原版本作用域受阻文件恢复9+50个声明锚点；ProjectionView失败文件为0。这里100%是已有状态声明的投影命中率，不是所有状态访问或语义的支持率。L1仍按既有SupportedSourceView策略，不因ProjectionView而放宽。

共享prefix helper提取后，四任务重新运行L1，完整graph_fingerprint和computation_fingerprint均与P2 final_route_audit逐项一致，DATA_DEF_USE仍为5659/5713/3419/3889条。L1复核耗时约31.15/22.74/20.34/12.62秒；未覆盖P2图。绑定证据在prompt3_v1/l1_equivalence/receipt.json和各任务记录。

**42.6 四任务真实L2构图与模型接入**

| 任务 | 文件 | 原节点 | 新WRITES | 新READS | 总L2 | L1回退函数有L2/总数 | 回退函数贡献边 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 重入合约 | 142 | 18312 | 3108 | 4314 | 7422 | 182/276 | 480 |
| 访问控制合约 | 114 | 13432 | 1609 | 2208 | 3817 | 224/357 | 707 |
| 重入节点 | 71 | 12036 | 2254 | 3070 | 5324 | 51/85 | 195 |
| 访问控制节点 | 57 | 7710 | 767 | 1091 | 1858 | 72/102 | 284 |

| 任务 | 跨callable写读对 | alias边/占L2比例 | unmapped出现 | L2 canonical含REV | 模型参数 | 构图及验收秒 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 重入合约 | 10667 | 231 / 3.1124% | 219 | 16 | 5003026 | 63.5195 |
| 访问控制合约 | 7009 | 148 / 3.8774% | 228 | 18 | 5019442 | 42.0626 |
| 重入节点 | 7692 | 223 / 4.1886% | 101 | 16 | 4847074 | 38.6041 |
| 访问控制节点 | 3974 | 148 / 7.9656% | 93 | 18 | 4937362 | 21.0660 |

cross_callable_pairs按同一声明的唯一写语句/读语句对统计，且callable不同；状态初始化不作为callable对。不代表跨函数控制流或可行路径。unmapped是访问出现数，不是文件数或节点数；四任务anchor_missing均0。L2 callable统计含modifier，不能拿它直接当L1函数支持率分母。

Top10 READS出度和WRITES入度逐声明完整列在各任务summary.json（变量/文件/节点/度）。例如spank_chain_payment.sol的Channels在重入任务READS出度85；热点未截断。每个新增canonical及正向/REV边数在model_schema.json；同一正反关系边数逐项相等。只构造四个CPU G2R模型并验证schema，inside_token维度512；没有真实图forward、fit或optimizer step，不据此宣称GPU显存或训练表现通过。

绑定unresolved主要为state_name_missing，四任务分别2340/2529/1550/1744次；state_name_ambiguous为96/51/18/17次。这里包括无法归到状态声明的普通调用名字，不等同全部是错误或漏掉的实际状态访问。别名未确认原因包括重复局部声明、RHS被局部遮蔽、非链式RHS、版本证据不足；详细分布及排除项分别存summary/audit，避免合并为一个“失败率”。

**42.7 测试、样本复核与证据强度**

先通过模块定向测试与push/pop前后回归，再完成全v2与旧DDG回归。最终v2 344 passed、0 failed/errors/skipped、8条warning、8.18秒；旧DDG＋tests/test_graph_utils.py为223 passed、0 failed/errors/skipped、29条warning、3.52秒。合计567项通过（不重复计入此前定向执行），不是全仓库测试全集。警告为既有DGL/NetworkX等弃用提示，无新增失败。

测试覆盖if/for/modifier/initializer单元边界、前缀delete/update、storage/memory/legacy及遮蔽、继承回退、状态重绑定、未知类型push/pop、缺失语句不误投影、标签/token干预不影响事实、图边去重及原始属性保留、错误输入摘要和重复输出目录拒绝。L1四图重建是独立于单元测试的计算不变证据。

每任务排序后random.Random(0)抽20条唯一L2边，四任务共80条。独立Codex复核80条边对应85处源码出现，含5条alias边；源码SHA、AST跨度、绑定、Unit归属和读写方向均核对，未发现具体错误。PROGRESS附各任务固定样本前5条共20条完整端点源码；完整80条在各任务edge_sample.json和prompt3_v1/manual_edge_review.json。此为AI辅助源码检查，尚无领域专家独立标注和外部solc编译验证。

最终另行只读复核355个当前runtime SHA、4任务manifest/file SHA和P2链式绑定，352个唯一输入/源码/产物路径、384个任务内源码实例和172个元数据路径实例均通过。原HCG与L1/新L2的节点、基础边、L1 key/属性再次逐项核验，80条样本审查身份仍一致。

**42.8 实际命令、产物与恢复**

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l2_projection_audit --output scripts/DFG/experiments/artifacts/dfg_v2/prompt3_v1/projection_audit
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l2_build --l1-directory scripts/DFG/experiments/artifacts/dfg_v2/l1_build/final_route_audit --output scripts/DFG/experiments/artifacts/dfg_v2/l2_build
~~~

这些输出目录已存在，重跑必须使用新输出目录，入口拒绝覆盖。测试完整log/XML保存在prompt3_v1，构图入口无resume训练含义。新图按l2_build/<task>/hcg.gpickle保存，配套audit、inputs、acceptance、model_schema、edge_sample、manifest、summary JSON；批次summary.csv/json、run_inputs.json、receipt.json绑定运行代码、源文件与输入SHA。include_constants默认False，可显式配置；本轮四任务均为False。

运行期间原图、原P2 L1产物和历史文档正文没有改动。最终保护校验、测试XML摘要与三文档追加前缀证明写入prompt3_v1/validation.json；本地提交SHA另写commit_receipt.json，避免文档嵌入自身提交哈希循环。产物不加入本轮Git提交，原有未跟踪资产/lock保留。

**42.9 限制、未执行事项和停止点**

当前L2为保守、流不敏感的状态基变量关系，字段/数组元素汇总到声明，alias多目标取并集可能增加过近似；不支持完整指针/引用分析、被调用函数摘要和精确存储位置。无版本证据只影响需要版本判定的alias分支，不以无版本为理由删整个文件。缺原HCG emit/revert等节点的事实仍未接入模型。构图正确不代表噪声和新增聚合参数不会影响后续训练。

本轮未下载/安装/执行新的solc，Solidity样例只进行了当前解析器和语义/投影测试，不能称编译验证通过。未启动Prompt 4/L3、环境节点、正式或smoke训练，没有新增F1结论。按共享上下文本地提交Prompt 3后停止，未自动push。后续Prompt 4可复用ProjectionView/Units，但须单独按其要求实施验收。


提交前补充：对新增文件执行暂存区格式检查时，发现 l2.py、projection_view.py、tests/test_l2.py 各多一个文件末尾空行；未发现其他格式问题。为保持已验收源码与四任务产物的 SHA 绑定，不再改动这三个文件。最终格式检查仅在该次命令中关闭 blank-at-eof 提示（未修改 Git 配置），其余空白错误检查仍启用；默认检查输出及此处理记入 staging_validation.json。这是格式提示，不涉及计算或测试结果。


## 43. 2026-10-24 Prompt 4.0：L2三个正确性修订与独立重建（Codex）

按更新后的PROMPTS.md（47f3f2c）先完成Prompt 4第0部分，未改变方案，也未提前加入L3文件。修改state_access.py让struct_field_assignment只访问value字段，避免把call选项名value/gas误读为状态；state_binding.py把精确string/bytes类型计入有版本证据的legacy局部storage引用，bytes1…bytes32不纳入；units.py增加try_statement的attempt区域，缺HCG节点计unmapped，不挂函数节点。l2.py/projection_view.py/tests/test_l2.py仅删除末尾多余空行。

新增test_prompt4_zero.py共20项，实际grammar先行核验。相同测试修复前10 failed/10 passed；修复后连相关既有测试126 passed。最终全v2 364 passed、旧DDG+graph_utils 223 passed，共587项，0失败/跳过，8/29条既有弃用warning。测试包含版本不确定、显式memory/calldata、var字符串/字节引用、名字字段和接收者读取、try独立归属及图不变量。仅解析器/语义测试，未执行solc。

四任务已重建至artifacts/dfg_v2/l2_build_r1/，原l2_build/只读保留。逐任务新增/删除边均0，边属性变化均0，完整图fingerprint全部一致。unmapped仍219/228/101/93，alias绑定仍45/29/42/29，WRITES/READS仍3108/4314、1609/2208、2254/3070、767/1091。说明这些反例缺陷确实已由回归覆盖，但本批真实图未触发改变投影结果的情况；不能据“图相同”认为修复无效。

后续L3及G2R使用l2_build_r1/。不重跑L1：本次修改的units/state_binding/state_access不在L1导入路径，l1*.py与其旧依赖SHA均保持，EOF清理无计算改变。P2最终L1作为输入仅核验manifest/SHA，不覆盖。原标签/token、CFG/CG、HGT和训练逻辑保持。

实际命令（环境同§4.1）：
~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l2_build --output scripts/DFG/experiments/artifacts/dfg_v2/l2_build_r1
~~~
输出已存在，禁止覆盖重跑。证据在artifacts/dfg_v2/prompt4_v1/p4zero/，包括grammar_probe、before/after、全回归日志/XML、rebuild.log和逐任务comparison.json（边差异证据列表为空）。本阶段单独本地提交“Prompt 4.0”，随后才实现第1–5部分；未push、未训练。实施、复核与记录AI：Codex。


## 44. 2026-10-24 Prompt 4 L3实施中：等待一项已确认的AST适配决策（Codex）

阶段4.0已提交71f19dc，后续实现目前尚未提交、未封存L3正式产物。新增env.py/tokens.py/l3.py/l3_build.py/l3_forward.py及test_env.py/test_tokens.py/test_l3.py/test_l3_build.py。已完成14键/18写法、词法遮蔽和明确import别名、辅助节点旁路叠加、离线冻结token编码、L2链式绑定及隔离CPU前向验收入口。未修改HGT、tokenizer原逻辑、训练脚本或原图标签。

独立定向测试：env 63项、tokens 42项、archive/forward guards 24项通过；L3集成除下述待决策反例外23项通过（1项明确deselected，不计作全套通过）。重入合约原图token离线抽样20/20逐位一致。首次集成测试另有5项因共享合成夹具正例缺category而失败，现仅补齐新测试夹具schema；没有修改真实标签、模型或降低断言。真实L3四任务构图和8次CPU前向尚未执行，无训练。

阻断反例：实际grammar把msg.gas + gasleft()解析成call_expression(function=binary_expression(...,gasleft))；this.balance + address(this).balance的最外member对象也可能是binary_expression。按文档仅识别裸function/direct object会漏识别合法写法。完整20例探针在prompt4_v1/env/call_precedence_probe.json。保留test_spellings_merge_per_file_and_edge_not_per_occurrence的失败断言，没有用改写源码或删测试掩盖问题。

已通过异步问题请求用户批准“受限AST后缀适配”：仅沿已确认的未加括号binary右侧/unary参数恢复已知ENV调用/成员，继续检查遮蔽；不越过显式计算括号，不修改grammar、源码、HCG或模型。此项超出文档字面AST匹配规则，按用户“替代方案须先征求同意”要求暂未应用。备选是保留规则并明确漏识别限制。待答复后继续完成测试、真实图验收、详细记录和Prompt 4第二次提交。状态证据在prompt4_v1/pending_decision.json。实施与记录AI：Codex。


## 45. 2026-10-24 Prompt 4 L3完成：环境源节点、ENV_FLOW与双向前向验收（Codex）

**45.1 起点、授权与历史关系**

本条是第44节“等待决策”的完成续记；保留第44节及 pending_decision.json 的原始内容，不把历史待审批状态改写成已获批。Prompt 4起点为47f3f2c7a12aa10fec740b17d80f1421179ffc63，已完成pull --ff-only与共享§4.1核对。第0部分已独立提交71f19dc6848e88fc24fb38be5759d1ebd0fcb326，本次第1–5部分随后单独本地提交，未push。没有自动开展Prompt 5。

用户通过 call_a73e5a2e373d45e8984d39d0f0d288e0 明确批准“同意增加受限 AST 适配（推荐）”。批准记录另存 prompt4_v1/approved_decision.json。修改理由是当前实际grammar的后缀优先级形状导致文档裸callee/direct receiver规则漏掉合法环境读取；并非为了增加图边数或改变标签。

**45.2 文件清单、复用与未变范围**

本次新增5个生产文件和4个测试文件，均在 scripts/DFG/dfg_v2/：

| 文件 | 职责与关键实现 |
| --- | --- |
| env.py | 固定14个ENV_KEYS、18种SPELLINGS；EnvExtractor只遍历Unit regions；整callable局部名/合约成员/文件级显式声明遮蔽；已确认grammar后缀适配与审计。 |
| tokens.py | TokenEncoder复用原TOKENIZER/REVISION/cached_tokenizer/encode_ids；冻结recipe与完整资产SHA校验，离线编码，不加载LLM权重。 |
| l3.py | augment_l3、strip_aux、输入与原图不变量；先在原节点图投影，后统一分配文件级环境节点及ENV_FLOW。 |
| l3_build.py | L2→L1→原任务输入链式只读核验；四任务构图、特征重编码对比、覆盖/抽样、CPU独立worker、manifest/receipt。 |
| l3_forward.py | 每profile一次CPU eval/no_grad前向；每层环境表示按键跨文件比较，输出shape/finite、canonical、参数量、RSS、时间和零差异文件对。 |
| tests/test_env.py | 84项环境键、写法、遮蔽、声明位置、assembly、实际AST及后缀边界回归。 |
| tests/test_tokens.py | 42项编码流程、类型/长度/特征recipe、资产绑定与加载前后核验。 |
| tests/test_l3.py | 24项辅助节点/边、原图不变量、别名合并、缺节点不误投影、同文件合并、监督池化排除和小图梯度。 |
| tests/test_l3_build.py | 24项归档链、拒绝错误输入/重复输出、token抽样一致性和按类型内行身份比较。 |

旧代码无本阶段修改：原process_graphs/sco_models、HGT、tokenizer生成逻辑、训练脚本、所有已冻结DDG模块与旧图/标签/折/产物保持。P4.0的7个代码/测试文件在本阶段也保持该提交的SHA。只追加HANDOVER.md、本训练文档及PROGRESS.md。未改PROMPTS.md。新产物保存在未跟踪artifacts/dfg_v2，不加入源码提交。

**45.3 获批解析调整与边界**

实际解析器将 msg.gas + gasleft() 的调用function置为整个binary_expression；this.balance + address(this).balance 的object也可能包含二元表达式。适配只沿原始未括号包围的 binary.right / unary.argument，并要求 child.end_byte 与父表达式结尾对齐，最后仍须匹配已有已知ENV写法。禁止穿越显式复合括号、三元表达式或任意计算callee；(a+msg).sender、(1+gasleft)() 不猜测。普通裸callee规则与遮蔽判定保持；this/address按模板作为保留语法处理。

每次适配记录 grammar_shape_recovered、原AST跨度、leaf跨度/文本、路径、checked_name及shadow_reason；EnvOccurrence接口不变。仍遍历左操作数和调用参数，避免恢复右侧时丢失其他读取。以相同最终test_env.py断言验证：修复前13 failed/71 passed，修复后84 passed；加test_l3原合并写法断言共108 passed。未删除测试、替换成错误期望或给源码加括号掩盖缺陷。证据 env/postfix_recovery_v1/receipt.json 与原20例AST探针均保留。

其他实现选择沿用文档：显式import alias只作为文件级已知遮蔽名，不读取外部文件；普通now名字字段、member property、类型名不当成环境值；builtin revert参数的当前grammar包装被遍历，自定义error名不当成值；assembly只计数不解释。Unit边界/ProjectionView/StateBinder直接复用P3，L1是否回退不阻止独立L3事实。绑定不明确或投影不到的事实审计丢弃，样本与原图保留。

**45.4 图、特征与监督约定**

一个(source_file,ENV_KEY)最多一个env_source，仅至少一条已投影用途时生成。按文件词典序及固定ENV_KEYS顺序，自最大原整数ID+1连续追加。每个(env,unit)一条正向ENV_FLOW；同语句多次读取合并为一条边，spellings排序、evidence_indices保留所有出现。因此“出现数”和“边数”不是同一统计。原节点、节点顺序、全部原属性、CFG/CG/L1/L2边及key/属性均逐项保持，strip_aux后fingerprint与输入完全一致，文件之间无连接。

新节点属性恰为9个原键加dfg_v2_aux；method为空、node_source_code_lines为空、node_info_vulnerabilities=None，没有伪造源码位置/标签。NetworkX只存正向；G3R通过既有模型输入adapter增加独立REV_ENV_FLOW，G3与G3R共用同一个NetworkX图。监督按env_source类型排除、合约_pool_rows排除；合约bookkeeping可包含辅助行，但不参与池化或损失。训练读取路径不调用需要source_path的get_function_boundaries，故无需额外添加属性。

原token实际类型为numpy.ndarray/float32/(512,)；保留原图code原样（含原存储引号），tokenizer取完整input_ids并包含special tokens，然后使用原encode_ids取前512、右补0；不启用truncation=True，不加载完整语言模型。固定TOKENIZER/REVISION/本地资产集合及SHA写入audit，加载前后和构图后再核验。四任务seed=0各抽20个原节点，80/80逐位一致且重复编码一致。访问控制合约抽样曾出现683>512的tokenizer提示，这是先完整分词再截512的预定流程；没有把超长序列传给LLM模型，最终形状与原特征严格一致。

**45.5 四任务真实验收统计**
| 任务 | 文件 | 原节点 | env节点 | ENV_FLOW | unmapped出现 | L1回退中有ENV的函数/回退总数 | 回退贡献ENV边 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 重入合约 | 142 | 18312 | 298 | 3857 | 288 | 56/276 | 108 |
| 访问控制合约 | 114 | 13432 | 261 | 2536 | 314 | 97/357 | 160 |
| 重入节点 | 71 | 12036 | 187 | 3200 | 126 | 26/85 | 42 |
| 访问控制节点 | 57 | 7710 | 182 | 1948 | 121 | 37/102 | 58 |

| 任务 | profile | 参数量 | 输出形状 | 前向秒（含hook） | 进程峰值RSS MiB | 两层同键跨文件最大差异 |
| --- | --- | ---: | --- | ---: | ---: | --- |
| 重入合约 | G3 | 5004308 | [142, 2] | 3.2534 | 2034.66 | 0.00000000 / 0.00000000 |
| 重入合约 | G3R | 5283380 | [142, 2] | 4.2754 | 2167.25 | 0.49534172 / 0.49247390 |
| 访问控制合约 | G3 | 5004308 | [114, 2] | 2.4988 | 1806.25 | 0.00000000 / 0.00000000 |
| 访问控制合约 | G3R | 5299796 | [114, 2] | 3.1733 | 1899.18 | 0.43592823 / 0.42361152 |
| 重入节点 | G3 | 4840148 | [12223, 2] | 2.3031 | 1734.73 | 0.00000000 / 0.00000000 |
| 重入节点 | G3R | 5111012 | [12223, 2] | 2.7119 | 1835.71 | 0.44532990 / 0.43481565 |
| 访问控制节点 | G3 | 4922228 | [7892, 2] | 1.8451 | 1561.85 | 0.00000000 / 0.00000000 |
| 访问控制节点 | G3R | 5217716 | [7892, 2] | 1.9676 | 1610.03 | 0.36489880 / 0.36927533 |

上述unmapped均来自原作者图缺少对应emit_statement节点的出现，不挂到函数节点，不创建孤立环境节点；均非丢弃文件。四任务无file/projection fallback、shadowed与unknown_env_member均为0；这些路径另有合成回归，不意味着所有真实源码不存在其他不支持语义。跳过assembly分别15/14/12/9处。获批AST恢复实际触发20/22/14/14次，均记录原跨度与恢复路径。

完整14键统计（包括零出现项）、各写法数量、unmapped AST类别、shadow原因、各文件与L1回退函数明细在每任务summary/acceptance/audit。ENV新增canonical：重入合约5正向+5反向、访问控制合约5+5、重入节点4+4、访问控制节点5+5；不是将14个ENV键分别注册为14种关系。环境键通过各env_source的code/token区分。

**45.6 真实模型前向与证据边界**

每任务G3与G3R各一次CPU、eval、torch.no_grad前向，共8次；没有loss、backward、optimizer或训练。小图单元测试的反传与真实图验收严格区分。节点输出包含辅助节点行，原监督mask仍排除这些行；合约输出是每文件两类logits。默认原HGT计算结构、512输入、128hidden/2层/8头保持。前向时间包含hooks与跨文件比较开销，RSS是独立worker进程峰值，不是GPU显存。

四任务两层G3同键跨文件最大差异全部为0；G3R两层最大差异见表，确认REV_ENV_FLOW让环境节点表示受使用处上下文影响。这是未训练初值上的消息接入证据，不是F1提升或纯语义因果效果。只有一个文件使用某键时没有跨文件可比对，不把它记为失败。

每个键和文件对的零/容差内差异均列入G3R_forward.json：同一incoming关系和上一层源表示集合是已确证解释；集合不同时保留“聚合碰撞/对称性未解析”分类，不伪造注意力因果。额外静态复核只读图、token和模型输入关系，不追加forward或训练；结论另附于下方及prompt4_v1/zero_pair_static_review/。部分不同邻域在1e-6内相同的确切数值原因仍未确定，不据此宣称所有文件表示都不同。

**45.7 测试、完整性与真实抽样**

最终DFG v2全集538 passed（相对P4.0新增174项），0 failed/error/skipped，8条既有DGL/NetworkX弃用warning，11.47秒；旧scripts/DFG/tests及tests/test_graph_utils.py为223 passed，0 failed/error/skipped，29条既有弃用warning，3.06秒。合计761项，通过数不重复叠加此前定向执行。新增样例按当前parser健壮性/语义边界测试理解，未执行Solidity编译验证。

初次L3合成集成测试另有5项因共享合成夹具正例缺category失败，仅在新test_l3夹具补齐该字段，不修改真实标签/模型。最初6失败和23 passed/1 deselected记录仍保留；当前最终全套无跳过。L2归档审查补充summary.all_acceptance_passed必须为True，错误来源/摘要/资产/图特征/重复任务/重复输出均拒绝。

冻结11095个既有受保护文件SHA未变；P4.0代码SHA未变；L3构建365个runtime SHA在开始、结束与提交前核对一致。三文档原文prefix保留。各任务receipt/manifest/input/graph/feature/source链式校验通过，原标签与特征不重新生成；新的token只用于新增环境节点。

独立最终复核final_independent_review.json已accepted：四任务祖先链/manifest、365个runtime文件、全部原图不变量、8份CPU收据通过；80条固定边共84处出现均验证源码SHA、字节区间、AST区域和精确原节点投影，复核没有再次运行模型。

四任务每任务seed=0抽20条ENV_FLOW，80条完整key、spellings和目标语句原code写入PROGRESS，完整source SHA和evidence在对应edge_sample/audit/inputs。复核是AI辅助源码检查，不等同独立专家Oracle或编译器证明。

**45.8 命令、输出与停止点**

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l3_build --l2-directory scripts/DFG/experiments/artifacts/dfg_v2/l2_build_r1 --output scripts/DFG/experiments/artifacts/dfg_v2/l3_build
~~~

上面构图命令已执行，输出目录存在时拒绝覆盖，勿直接重复。最终数据在artifacts/dfg_v2/l3_build/；测试日志/XML、批准前后证据、独立复核、提交收据在artifacts/dfg_v2/prompt4_v1/。本地正式图不自动上传GitHub。

仍保留范围限制：环境键是源码中的环境量类别，不是记录动态运行时取值；只实现文档14键，assembly不解释；不进行跨文件连边、完整Solidity类型/版本验证、调用语义总结或缺失HCG节点补建。旧P3全L2图此次P4.0重建虽逐图完全相同，反例修复仍有必要。L3新增关系是否有收益须留给后续既定训练阶段，本轮未训练、未测F1、未做GPU显存验收、未执行solc、未开始Prompt 5或推送。实施、复核与记录AI：Codex。

**45.9 零/容差内文件对静态补充（不再前向）**

原前向报告中未解析的1,970个“任务×层×键×文件对”里，900对满足token与canonical归一化邻域的参数无关充分条件，解释精确算术下的表示等价；另外1,070对仍未解析。此计数不是独立实验次数，也不是所有零差异对的总数。每对及原forward SHA保存在zero_pair_static_review/，原forward JSON保持不变。

| 任务 | 第一层：静态充分条件 / 未解析 | 第二层：静态充分条件 / 未解析 |
| --- | ---: | ---: |
| 重入合约 | 0 / 68 | 7 / 4 |
| 访问控制合约 | 435 / 44 | 11 / 435 |
| 重入节点 | 0 / 65 | 4 / 4 |
| 访问控制节点 | 435 / 105 | 8 / 345 |

例如访问控制buggy_11与buggy_14的this.balance分别接7条、4条相同token的_recipient.transfer(address(this).balance);，同canonical消息值相同，softmax加权和不会仅因重复次数改变。这适用于第一层，不能直接推广至第二层；其余不同输入但输出≤1e-6的情况可能涉及注意力集中、聚合或数值消差，但本轮没有保存attention权重，不将推测写成已证原因。900对的静态充分条件也不等于浮点计算的逐位因果证明。

Per-key coverage (nodes / ENV_FLOW / occurrences / unmapped; spelling counts):

#### 重入合约 / reentrancy_author_contract

| key | nodes | edges | occurrences | unmapped | spellings |
| --- | ---: | ---: | ---: | ---: | --- |
| msg.sender | 136 | 3381 | 4141 | 267 | {"msg.sender": 4141} |
| msg.value | 50 | 107 | 121 | 11 | {"msg.value": 121} |
| msg.data | 5 | 5 | 5 | 0 | {"msg.data": 5} |
| msg.sig | 0 | 0 | 0 | 0 | {} |
| tx.origin | 3 | 3 | 3 | 0 | {"tx.origin": 3} |
| tx.gasprice | 0 | 0 | 0 | 0 | {} |
| block.timestamp | 48 | 130 | 151 | 10 | {"now": 136, "block.timestamp": 15} |
| block.number | 4 | 10 | 10 | 0 | {"block.number": 10} |
| block.difficulty | 0 | 0 | 0 | 0 | {} |
| block.coinbase | 0 | 0 | 0 | 0 | {} |
| block.gaslimit | 0 | 0 | 0 | 0 | {} |
| blockhash | 2 | 2 | 2 | 0 | {"blockhash(...)": 2} |
| gasleft | 0 | 0 | 0 | 0 | {} |
| this.balance | 50 | 219 | 219 | 0 | {"address(this).balance": 217, "this.balance": 2} |

#### 访问控制合约 / access_control_author_contract

| key | nodes | edges | occurrences | unmapped | spellings |
| --- | ---: | ---: | ---: | ---: | --- |
| msg.sender | 112 | 979 | 1468 | 292 | {"msg.sender": 1468} |
| msg.value | 22 | 49 | 60 | 10 | {"msg.value": 60} |
| msg.data | 6 | 14 | 14 | 0 | {"msg.data": 14} |
| msg.sig | 0 | 0 | 0 | 0 | {} |
| tx.origin | 42 | 1114 | 1114 | 0 | {"tx.origin": 1114} |
| tx.gasprice | 0 | 0 | 0 | 0 | {} |
| block.timestamp | 22 | 85 | 98 | 11 | {"now": 84, "block.timestamp": 14} |
| block.number | 3 | 8 | 8 | 0 | {"block.number": 8} |
| block.difficulty | 0 | 0 | 0 | 0 | {} |
| block.coinbase | 0 | 0 | 0 | 0 | {} |
| block.gaslimit | 0 | 0 | 0 | 0 | {} |
| blockhash | 1 | 1 | 1 | 0 | {"blockhash(...)": 1} |
| gasleft | 0 | 0 | 0 | 0 | {} |
| this.balance | 53 | 286 | 287 | 1 | {"address(this).balance": 277, "this.balance": 10} |

#### 重入节点 / reentrancy_author_node

| key | nodes | edges | occurrences | unmapped | spellings |
| --- | ---: | ---: | ---: | ---: | --- |
| msg.sender | 70 | 2814 | 3310 | 111 | {"msg.sender": 3310} |
| msg.value | 36 | 81 | 88 | 6 | {"msg.value": 88} |
| msg.data | 2 | 2 | 2 | 0 | {"msg.data": 2} |
| msg.sig | 0 | 0 | 0 | 0 | {} |
| tx.origin | 2 | 2 | 2 | 0 | {"tx.origin": 2} |
| tx.gasprice | 0 | 0 | 0 | 0 | {} |
| block.timestamp | 33 | 87 | 102 | 9 | {"now": 97, "block.timestamp": 5} |
| block.number | 3 | 9 | 9 | 0 | {"block.number": 9} |
| block.difficulty | 0 | 0 | 0 | 0 | {} |
| block.coinbase | 0 | 0 | 0 | 0 | {} |
| block.gaslimit | 0 | 0 | 0 | 0 | {} |
| blockhash | 1 | 1 | 1 | 0 | {"blockhash(...)": 1} |
| gasleft | 0 | 0 | 0 | 0 | {} |
| this.balance | 40 | 204 | 204 | 0 | {"address(this).balance": 204} |

#### 访问控制节点 / access_control_author_node

| key | nodes | edges | occurrences | unmapped | spellings |
| --- | ---: | ---: | ---: | ---: | --- |
| msg.sender | 56 | 459 | 646 | 106 | {"msg.sender": 646} |
| msg.value | 14 | 33 | 40 | 6 | {"msg.value": 40} |
| msg.data | 4 | 11 | 11 | 0 | {"msg.data": 11} |
| msg.sig | 0 | 0 | 0 | 0 | {} |
| tx.origin | 42 | 1114 | 1114 | 0 | {"tx.origin": 1114} |
| tx.gasprice | 0 | 0 | 0 | 0 | {} |
| block.timestamp | 13 | 41 | 51 | 9 | {"now": 46, "block.timestamp": 5} |
| block.number | 3 | 8 | 8 | 0 | {"block.number": 8} |
| block.difficulty | 0 | 0 | 0 | 0 | {} |
| block.coinbase | 0 | 0 | 0 | 0 | {} |
| block.gaslimit | 0 | 0 | 0 | 0 | {} |
| blockhash | 1 | 1 | 1 | 0 | {"blockhash(...)": 1} |
| gasleft | 0 | 0 | 0 | 0 | {} |
| this.balance | 49 | 281 | 281 | 0 | {"address(this).balance": 273, "this.balance": 8} |


## 46. 2026-10-25 DFG v2 Prompt 5.0：注意力与 grammar 只读诊断（Codex）

### 46.1 范围、输入与实施选择

从 dfg-v2 分支 3379d2e7c281b7b9cbf389b4c979135510c0ffe9 开始；已执行 git pull --ff-only origin dfg-v2，读取更新后的 §4.1 与 Prompt 5。仅新增 attention_probe.py、grammar_shape_audit.py 及对应两份 tests；三份文档只追加。未修改旧分析器、HGT、tokenizer、图、标签、划分或训练程序。Prompt 5.0 与之后统一入口按要求分开本地提交，不自动推送。

用户已批准两项后续接口调整（call_5b82ed0af4c443a8ad73d74579bde566）：现有各层内部独立解析，故改为任务源码清单只加载/校验一次、各层各调用一次并复用中间图；通用类别验收由不足以执行5/10折的3文件改为20个小型合成身份。真实分析器和划分函数均保持，批准不等于允许修订 L1/L2/L3。

### 46.2 注意力诊断实现与事实

attention_probe 用 forward hook 捕获每层输入/输出，以 frozen HGT 自身参数重算 k/q/v、relation变换、dst softmax、sum、跨关系 mean、a_linear、skip 和 norm；只做 CPU eval/no_grad，无 loss、反传、优化器。每任务一次真实前向，四任务共4次，8个层输出的最大重算误差全部0（门槛1e-5）。1070/1070历史文件对重现1e-6容差内接近。单邻居权重1不作为饱和证据，报告多邻居目标/head分布；另保留同h/value邻居组的合计权重，避免重复邻居稀释单边权重导致误读。

| 任务 | 第一层 REV_ENV_FLOW max>=.99 | READS_STATE | next_line | 历史对 | RSS MiB | 诊断秒数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 重入合约 | 85.82% | 98.62% | 98.91% | 72 | 2179 | 29.88 |
| 访问控制合约 | 62.04% | 99.29% | 98.23% | 479 | 1911 | 23.53 |
| 重入节点 | 76.48% | 99.76% | 98.26% | 69 | 1841 | 18.79 |
| 访问控制节点 | 54.68% | 99.77% | 96.35% | 450 | 1627 | 8.81 |

第二层三类关系的多邻居 max>=.99 比例均为0%。第一层各类型h的abs_mean约111–1309，abs_max约14522–17001；第二层abs_mean约0.774–0.878、abs_max约5.95–6.06。adapt_ws只执行一次，第二层输入是前层归一化输出，不能声称每层重新投影token ID而持续饱和。

1070对中70对的各canonical消息与残差输入逐位相同；269对最高邻居value相同但只是解释证据，不能都归因为one-hot；其余731对全部在第二层，真实输出差均非零，仅为1.192e-7–9.537e-7的容差内接近。这731对完整canonical消息差最大4.029e-6，自身上一层输入差最大2.384e-7。未保存逐pair的skip前后/pre-norm张量，不把所有差异归因某单一步骤。重算完整输出吻合，未发现新关系未接入或模型计算错误。

模板中的“全部1070对由one-hot解释”及“G0同样存在”不能直接当作实测结论：本次测的是G3R中的ENV、READS_STATE及原next_line；G0使用同类原始token ID和计算机制，但未额外执行G0诊断。保留为可能机制，不更改特征或归一化，不声称F1收益。

### 46.3 grammar 普查与审查修正

按L3输入收据/图bundle/源码SHA，扫描四任务384个文件实例、256个唯一source path+SHA。直接后缀槽为binary/unary的次数依次363/296/218/164；被吞push/pop成员调用全部0，表达式位置user_defined_type全部0，解析失败0。真实类型/继承位置单独排除，不把解析成功称作Solidity编译通过。没有触发模板要求的分析器修订门槛。

独立复核后，仅修正新审计器两项健壮性：环境前缀允许点号周围空白；直接核验metadata引用的版本CSV/源码资产，避免版本回退吞掉输入漂移。旧分析器不变，原诊断保留，新结果写grammar_shape_audit_r1。详细逐文件证据、候选和SHA均在prompt5_v1，不按名字猜测源码。

### 46.4 验证与产物

最终测试数量与保护文件核验见本节末尾执行补记。警告仅已有DGL distutils、NetworkX gpickle弃用；未安装依赖或执行solc。attention_probe_tests保存17项定向测试及源码seal；attention_probe/保存4任务完整JSON、pair_summary.csv、summary/seal；grammar_shape_audit_r1为最终扫描。前一版grammar_shape_audit及phase0_v2_tests记录保留，不覆盖。

实际命令（mando环境，§4.1环境变量）：
~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
python -B -m scripts.DFG.dfg_v2.grammar_shape_audit --output scripts/DFG/experiments/artifacts/dfg_v2/prompt5_v1/grammar_shape_audit_r1
python -B -m scripts.DFG.dfg_v2.attention_probe --bundle <l3_build的任务目录> --static-review scripts/DFG/experiments/artifacts/dfg_v2/prompt4_v1/zero_pair_static_review --output <该任务的新诊断目录>
~~~

已有输出目录不得覆盖。以上真实诊断已完成，不是要求重复执行。下一步仅组合已有层与输入/图存储，不训练。实施、复核与记录AI：Codex。


Final verification: v2 597 passed (8 existing warnings), legacy DDG/graph_utils 223 passed (29 existing warnings); 820 passed, 0 failed/skipped. Grammar targeted 42 passed, attention targeted 17 passed. Logs: prompt5_v1/phase0_final_v2.log and phase0_final_legacy.log. All 11114 protected tracked file SHAs and all three original document prefixes verified unchanged. Grammar r1 task JSON SHAs equal the prior scan; only audit input guards improved.


## 47. 2026-10-25 DFG v2 Prompt 5 第1–5部分：统一入口与封存图存储（Codex）

### 47.1 基线、范围与文件

第0部分先独立提交d6c7007，随后才开始本部分。新增pipeline.py、tasks.py、inputs.py、store.py、cli.py、EXTENDING.md、tests/test_pipeline.py、tests/test_tasks.py、tests/task_fixtures.py、tests/test_cli.py，均位于scripts/DFG/dfg_v2/。原分析器、原模型、训练代码、tokenizer、标签、旧实验产物均不修改；三份主文档只追加。这里只构图和验收，不启动Prompt6–8或新实验。

### 47.2 决策、接口实际差异与理由

1. 用户批准的“加载一次”指输入源码文本每任务加载一次、每个augment仅调用一次、F2接F1/F3接F2；现有L1/L2/L3内部仍各自解析。没有伪称跨层共享单次AST，也没有为缓存去修改冻结分析器。
2. 通用类别验收按用户批准使用20个合成文件身份（10 clean/10 buggy；节点任务仅10 buggy），完整经过注册、原5/10折、构图、两粒度G3R小图前向。真实源码和冻结折不为测试而改动。
3. 原任务manifest不内嵌后来核验的版本元数据，因此注册表额外固定source_metadata_manifest及SHA；这是保留现有SupportedSourceView输入所需的实际接口补全，不猜编译器版本。
4. make_folds严格重建并逐字段核验已冻结nested文档，不能把新inputs SHA替代原prepared SHA，也不能误取旧paper_kfold路径。新类别第一次生成折的bootstrap调用原protocol.make_fold_document并拒绝覆盖，然后注册SHA；EXTENDING明确此顺序，未假称本轮已有run plan训练入口。
5. --graph-keys只保存显式请求的层与F0，所需前置层仍只计算一次但不额外保存；默认四任务F1/F2/F3对应20次CPU模型构造。F0没有新hcg文件，直接原路径和SHA。G3与G3R共用F3文件，REV只由原v2 adapter在模型输入时生成。
6. store额外单文件封装便于CLI复用。verify重新检查图和schema而不创建HGT模型，不比较当前源码runtime是否等于构建时runtime。构建开始与结束仍要求同一runtime。RSS注明为截至任务结束的进程累计高水位，不能写成各任务独立进程峰值。

### 47.3 核心实现与不变量

pipeline.build/iter_build只组合已有augment。图键由PROFILES正向集合推导，未来G1/G2无须加第二份映射；非法关系组合、未知关系名、非连续层、输入已有v2/REV、原图跨文件连接会拒绝。每层验证原节点ID/顺序/全部属性、原边key/属性/顺序和graph属性不变；所有新增边无自环/重复/跨文件，且证据端点、关系、投影状态和引用全集一致。F3去除env节点后与F2完整指纹相同。缺源码清单项是显式fallback，不删除原图；已登记源码消失或SHA改变则报错，不将输入漂移当fallback。

输入manifest绑定原HCG、源码逐文件path/SHA/metadata、graph labels、原nested折、原prepared身份及完整feature和tokenizer资产。版本metadata引用的原源码和CSV双SHA、唯一行、准确版本字符串也核验；不会让StateBinder吞掉错误后静默降级。构图分析器不读取标签/预测/token；输入与结果校验会检查标签和特征不变，这是验收用途。

store绑定manifest/seal、逐层图SHA/full fingerprint/computation fingerprint、audit SHA、正向关系、剖面方向、canonical schema与参数量、实际构建参数和runtime。G0使用已准备作者拓扑/作者标签、带本地冻结512维token IDs的原HCG；不把这些向量称作作者发布的token特征。默认真实模型检查仅CPU构造+validate_registration，无forward/loss/backward/optimizer。

### 47.4 测试、失败记录与修正

新增定向：pipeline43、tasks31、CLI/store28，全部通过。包括未来剖面映射、缺源码保留、证据损坏拒绝、构图确定性、真实四份nested逐字段一致、20身份完整链、源/CSV/标签/特征/schema/图/seal篡改拒绝、只新增无关py仍可verify、构图中runtime变化拒绝。CLI测试对classifier.forward设陷阱，默认20次模型构造仍通过；verify额外HGT构造0。

CLI首次26 passed/2 failed原因是测试格式假设：seal JSON末尾空白不改变其任何绑定语义，改为篡改store_sha256；argparse帮助自动折行，改为规范空白后核验原短语。没有放宽图、证据或schema关键断言。原失败日志保留于prompt5_v1/cli_tests/first.log。

最终全v2 699 passed、旧DDG+graph_utils 223 passed，共922 passed，0 failed/0 skipped；分别8/29条既有DGL distutils/NetworkX gpickle弃用warning。日志/XML在prompt5_v1/phase1_final_v2.*及phase1_final_legacy.*。未升级依赖、未执行solc；合成测试不宣称完成Solidity编译验证。

### 47.5 真实构图验收

四任务源码清单共384个实例（142/71/114/57），无缺源码；inputs与store分别独立seal。F0四项均为原路径与原文件SHA直引，未新建F0的hcg文件。默认构建得到12张新图+4个F0引用，共16项，记录20个CPU模型schema；无真实图前向、loss或训练。构图开始/结束runtime一致。独立读取12张新图的两种指纹均与历史P2/P3/P4参照一致，4/4 F3去辅助节点后精确等于F2；原节点、原边与各前层属性逐项保持。历史bundle/receipt/图SHA也重新核验，原产物没有覆盖。

实际每任务耗时包含加载、分析、序列化和schema构造；RSS为同一进程截至任务结束的累计高水位，不是各任务独立峰值：

| 任务 | 总秒数 | 进程累计峰值 MiB |
| --- | ---: | ---: |
| reentrancy_contract | 280.51 | 2293.73 |
| reentrancy_node | 175.84 | 2293.73 |
| access_control_contract | 200.96 | 2293.73 |
| access_control_node | 99.88 | 2293.73 |

验收绑定与产物：

- `inputs/manifest.json`: `a5d7f7a080a617dcda1ffc56804e581fa5b6ce2850c8d82f62ee47be75d23edf`
- `inputs/manifest.seal.json`: `81d36660f044ebc71921aaf98f165104a880bb2e3eced14354f2b4afe4d5c786`
- `graphs_v1/store.json`: `43e45227f7ccd9ebcbb034cb9e64b2cf430acf2c81dfb458b6ceadc344c67d5b`
- `graphs_v1/store.seal.json`: `ca6c7ea13cc7304a2de863c14ed9e6fbbac31ec554350894d61a5839197d46fb`
- `prompt5_v1/independent_graph_comparison.json`: `a5ed87cfd41d72cab51a05d55cf8f395e904aae9cdc636ceba980305e0145513`

完整build_summary.csv（与封存文件同内容，cumulative_seconds为该任务从开始到该层的累计耗时；new_canonical为对应剖面的最大新增数，方向区别见new_canonical_by_profile）：

~~~csv
task_id,graph_key,profiles,nodes,edges,DATA_DEF_USE,WRITES_STATE,READS_STATE,ENV_FLOW,env_nodes,new_canonical,new_canonical_by_profile,L1_functions,L1_supported,L1_support_fraction,state_declarations,anchored_state_declarations,state_anchor_fraction,cumulative_seconds
reentrancy_contract,F0,G0,18312,19267,0,0,0,0,0,0,"{""G0"": 0}",0,0,,0,0,,44.49224733401206
reentrancy_contract,F1,G1R,18312,24926,5659,0,0,0,0,42,"{""G1R"": 42}",3404,3128,0.918918918918919,0,0,,110.59969158700551
reentrancy_contract,F2,G2R,18312,32348,5659,3108,4314,0,0,58,"{""G2R"": 58}",3404,3128,0.918918918918919,2369,2369,1.0,177.51898770302068
reentrancy_contract,F3,"G3R,G3",18610,36205,5659,3108,4314,3857,298,68,"{""G3"": 34, ""G3R"": 68}",3404,3128,0.918918918918919,2369,2369,1.0,278.6237832000188
reentrancy_node,F0,G0,12036,11710,0,0,0,0,0,0,"{""G0"": 0}",0,0,,0,0,,24.43905459198868
reentrancy_node,F1,G1R,12036,15129,3419,0,0,0,0,42,"{""G1R"": 42}",2045,1960,0.9584352078239609,0,0,,65.26113055300084
reentrancy_node,F2,G2R,12036,20453,3419,2254,3070,0,0,58,"{""G2R"": 58}",2045,1960,0.9584352078239609,1788,1788,1.0,109.0333901779959
reentrancy_node,F3,"G3R,G3",12223,23653,3419,2254,3070,3200,187,66,"{""G3"": 33, ""G3R"": 66}",2045,1960,0.9584352078239609,1788,1788,1.0,174.89089208998485
access_control_contract,F0,G0,13432,15538,0,0,0,0,0,0,"{""G0"": 0}",0,0,,0,0,,30.342772722011432
access_control_contract,F1,G1R,13432,21251,5713,0,0,0,0,44,"{""G1R"": 44}",3148,2791,0.886594663278272,0,0,,79.46025053001358
access_control_contract,F2,G2R,13432,25068,5713,1609,2208,0,0,62,"{""G2R"": 62}",3148,2791,0.886594663278272,922,922,1.0,127.71584202800295
access_control_contract,F3,"G3R,G3",13693,27604,5713,1609,2208,2536,261,72,"{""G3"": 36, ""G3R"": 72}",3148,2791,0.886594663278272,922,922,1.0,199.33407922001788
access_control_node,F0,G0,7710,8840,0,0,0,0,0,0,"{""G0"": 0}",0,0,,0,0,,14.905203856003936
access_control_node,F1,G1R,7710,12729,3889,0,0,0,0,44,"{""G1R"": 44}",1958,1856,0.947906026557712,0,0,,38.528895382012706
access_control_node,F2,G2R,7710,14587,3889,767,1091,0,0,62,"{""G2R"": 62}",1958,1856,0.947906026557712,403,403,1.0,62.25203139000223
access_control_node,F3,"G3R,G3",7892,16535,3889,767,1091,1948,182,72,"{""G3"": 36, ""G3R"": 72}",1958,1856,0.947906026557712,403,403,1.0,99.24081490701064
~~~

11114个开始前受保护文件SHA和三份历史文档前缀均保持。新代码摘要见phase1_code_inventory.json；独立验收见independent_graph_comparison.json。具体输入/构图/verify命令日志在prompt5_v1/，完整schema与参数量在graphs_v1/store.json。

### 47.6 实际命令与后续使用

在mando环境、工作树根目录、§4.1环境变量下执行：
~~~bash
python -B -c "from scripts.DFG.dfg_v2.inputs import build_manifest; build_manifest('scripts/DFG/experiments/artifacts/dfg_v2/inputs')"
python -B -u -m scripts.DFG.dfg_v2.cli build \
  --manifest scripts/DFG/experiments/artifacts/dfg_v2/inputs/manifest.json \
  --tasks reentrancy_contract,reentrancy_node,access_control_contract,access_control_node \
  --graph-keys F1,F2,F3 \
  --output scripts/DFG/experiments/artifacts/dfg_v2/graphs_v1
python -B -m scripts.DFG.dfg_v2.cli verify \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v1/store.json
~~~

输入与图存储已生成，不应对已有目录重复build；程序会拒绝覆盖。后续步骤使用新的inputs/manifest与graphs_v1/store，不再把历史l1_build/l2_build_r1/l3_build当作运行入口；它们作为本次等价验收参照原样保留。

### 47.7 限制与停止位置

本轮证明的是统一入口不改变既有构图结果，不等于完整Solidity数据流分析或预测精度改善。L1/L2/L3已有支持范围、精确投影缺口与回退保持；注意力诊断限制见第46节，不因第一层集中而修改token ID或归一化。未运行正式训练、GPU显存预检、新seed、其他五类或下一Prompt。按要求第二次本地提交，未自动push。实施、交叉审查与记录AI：Codex。


Final acceptance: cli build exited 0; independent cli verify exited 0 (16 graph entries, 20 recorded schemas, 0 verification HGT constructions/forwards). Actual runtime SHA map still matches build-time; original 11114 protected files and historical document prefixes verified unchanged. Proof: prompt5_v1/final_acceptance.json.


## 48. 2026-10-25 DFG v2 Prompt 6：独立 Oracle 与正确性验证（Codex）

### 48.1 任务边界、版本与提交顺序

实施工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11，分支dfg-v2。开始HEAD为f5e1260a3b017640f0795c49bc4cc98e0c15881d（Refine Prompt 6 after Prompt 5 review）；按更新后的PROMPTS第4.1和Prompt 6执行，git pull --ff-only origin dfg-v2返回已是最新。本轮没有checkout/reset、迁移旧实验或改动用户原有修改。

严格执行“先独立期望、后运行比较、最后文档”的三次提交：
1. aded5023a0adb759cb458b2e238ccdc480be1d35，Prompt 6.1 oracle expectations，仅20个.sol及20个.expected.json。
2. f80073f34d6747a9e94fa67c0a1fefa93e231bc9，Prompt 6.2 sealed correctness checks and manual review tools，仅验证工具/测试/SEAL/分类。
3. 文档提交：HANDOVER、training_changes、本PROGRESS及PROMPT6_REPORT，本节记录对应实施。

手写期望阶段不运行分析器、不从结果倒推期望。SEAL绑定第1次提交及各文件SHA，比较器核验工作树内容和Git blob一致。看到不一致后没有修改原.sol/.expected.json，也没有重写seal以制造通过。所有源码样例都明确标记未执行编译验证；本轮使用解析器与图验证，不能称已通过Solidity编译。

真实图只读graphs_v1/store.json并先调用verify_store；不再读取历史分层目录作为运行入口。原L1/L2/L3、pipeline、HGT、tokenizer、作者图/标签、原折和训练逻辑没有修改。

### 48.2 用户批准的选择与未擅自扩展的范围

发现模板tuple“x只到a”与当前语句级HCG粒度不一致：整个(a,b)=(x,y)是同一模型节点，语句间关系不能证明节点内部的逐元素值流。已明确询问，用户答复“同意按语句粒度验证并记录限制（推荐）”。

采用：验证x/y定义→tuple语句、tuple语句→a/b后续使用，检查声明身份、KILL与禁止边；不增加表达式/变量节点、不调整分析器。限制：该Oracle不能验证tuple内部逐元素来源，不把语句关系结果解释成表达式级证明。

其余模板语义保持：L1字段写是基变量弱定义；L2通过状态声明中转且流不敏感，读先于写也可能形成声明连接。相关期望显式带approximation并单独计数，不能冒充精确到达定义。

可选Slither存在证据限制：冻结L1 audit只保存已投影定义—使用端点，不能恢复所有未参与关系的局部def/use出现。工具明确标记L1对照为partial，而非完整事件级召回。本轮不为可选外部验证修改冻结分析器；要补全必须另行确定新审计接口。L2使用现有原始字节出现位置。实际没有可用编译器，外部对照未执行，未用partial结果宣称通过。

### 48.3 新增文件与核心逻辑

| 新增文件（均在scripts/DFG/dfg_v2/） | 用途与限制 |
| --- | --- |
| oracle/*.sol、*.expected.json（各20个） | 独立手写赋值/分支/循环/终止/tuple/modifier、状态与环境量用例 |
| oracle/SEAL.json | 绑定原始期望提交与文件SHA；核对成对文件及18–20例范围 |
| oracle/CLASSIFICATIONS.json | 最终报告SHA、逐项issue ID、类别、理由及语言/代码证据 |
| oracle_check.py | 生成合成HCG、调用冻结pipeline，比较关系事实/图边、禁止项、计数及属性 |
| validate_slither.py | 离线能力检查、精确版本和可信编译器门禁、可选对照及跳过报告 |
| review_sheet.py | 只读F3图，固定随机抽样，原源码位置/evidence导出和封存 |
| score_review.py | 只允许verdict/note修改，统计正确比例与Wilson95%区间 |
| tests/test_oracle_check.py | 删除/多加/禁止边、重复文本、封存、属性、错误完整性等回归 |
| tests/test_validate_slither.py | 无工具/无版本跳过、API/位置/输入保护等回归 |
| tests/test_review_sheet.py | 确定性、来源、空表、篡改拒绝与统计回归 |
| PROMPT6_REPORT.md | 本轮结果、限制、后续6b输入及人工填写入口 |

Oracle合成HCG复用与test_l1相同的原generate_cfg_from_source路径，token_encoder固定float32[512]；额外测试0与17000常量编码不会改变边。投影采用ProjectionView/Projector身份与raw源码，规范化完整语句文本；不按最近行猜测。重复规范化端点文本拒绝比较，env使用ENV:键。

关系事实按(relation,src,dst,var)比较，图边按(relation,src,dst)另报；还校验env计数、unmapped、spellings/via_alias等已指定属性。原节点、边key/属性及labels保持。执行错误单列、metrics_complete=false，不能把异常转换为空图“通过”或静默从分母删除。新增关系的REV仍属于已有adapter职责，本轮未调整方向策略。

复核器要求分类文件精确对应所有差异并绑定报告SHA；期望错误必须附语言依据，同时保存HCG投影代码依据。存在差异时CLI仍以非零结束，不能把“已分类”伪装成原始Oracle全通过。


### 48.4 Oracle实际结果、逐项归因与6b输入

最终输出：artifacts/dfg_v2/prompt6_v1/oracle_run_v2/summary.json。20例全部执行；17例完全匹配，3例有差异；85条期望关系事实，32条禁止项，禁止边违反数0。24个期望条目明确标记设计近似。

| 关系 | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| DATA_DEF_USE | 47 | 4 | 3 | 92.16% | 94.00% |
| WRITES_STATE | 8 | 0 | 0 | 100% | 100% |
| READS_STATE | 15 | 0 | 0 | 100% | 100% |
| ENV_FLOW | 12 | 0 | 0 | 100% | 100% |

本批关系事实与图边级计数相同。这是对原始封存期望的原始比较，包含期望错误，不能用来宣称真实全语料准确率/召回率。8项差异分别如下，分类均已封存：

**04_for_update：6项expectation_error。** 手写期望认为i++没有独立HCG节点，把更新定义投到整个for。实际旧CFG_solidity.py在621–627、654–656创建并连接update_node_id；此例原始区间135:138对应节点32。实际7条关系反映更新的读/写、循环条件和退出使用。Solidity规定for更新发生于循环体之后，但模型节点粒度要由已有生成器判断。这里是期望中的投影假设错误，不能归咎于L1。保留原期望及SHA，通过分类说明，未调整代码或期望以强行通过。语言依据：[Solidity 0.5.17 control structures](https://docs.soliditylang.org/en/v0.5.17/control-structures.html#control-structures)。

**18_environment_synonyms：1项expectation_error。** 可选spellings属性期望写gasleft，而源码拼写是gasleft()；实际msg.gas与gasleft()都存在，合并为一个gasleft环境键。此项由新增属性断言检出，不能仅因ENV_FLOW边端点相同就认为两种语法都已覆盖。依据：[Solidity 0.4.26 block and transaction properties](https://docs.soliditylang.org/en/v0.4.26/units-and-global-variables.html#block-and-transaction-properties)。本轮未修改原封存期望。

**16_call_option_fields：1项implementation_error，属于覆盖缺口。** 例子先定义uint x = 1，再执行target.call{value: x}("")。L1的AccessExtractor.reads不支持此AST中的struct_expression，v2重试也未处理，最终函数级保守回退，漏掉x定义→调用的真实读取。定位scripts/DFG/access_extractor.py::AccessExtractor.reads（29–66）及scripts/DFG/dfg_v2/l1_access.py::V2AccessExtractor.reads（43–52）。该函数支持数0/1、partial_facts_published=false；原函数/HCG保留，没有基于不完整CFG发布部分DDG。L2正常读取target，不把value/gas/salt字段标签误当变量。调用选项中的value是表达式，x应被读取，参见[Solidity 0.6.12 external function calls](https://docs.soliditylang.org/en/v0.6.12/control-structures.html#external-function-calls)。

Prompt 6b应先针对该缺口补测试并修复，再用cli build输出新的graphs_v2、重跑Oracle和验收。不能修改graphs_v1、原SEAL或本轮报告。当前没有测量它在真实语料的恢复量，也没有依据称其造成历史F1停滞。本轮按验证限定未实现修复。

### 48.5 比较工具自身的复核与报告版本

初版oracle_run_v1检查边、禁止项和计数，18/20例匹配、7项差异。复核发现还需对期望指定的spellings/via_alias做断言，否则不同语法映射到同一边时可能掩盖漏识别。补充这些属性检查后，生成独立oracle_run_v2，变为17/20例、8项差异；v1未覆盖，原期望未改。

同时补齐：执行错误不能静默减少评分样本；源码/期望必须一一配对且数量合法；语句歧义拒绝；分类绑定最终报告。对验证程序自身的改进不改变被测L1/L2/L3。独立复核确认40个Oracle资产SHA未变，8个issue与CLASSIFICATIONS一一对应，最终报告摘要匹配，唯一实现缺陷描述准确。

### 48.6 Slither实际执行情况及限制

仅检查现有离线环境：slither-analyzer 0.8.0、crytic_compile 0.2.4可用；solc-select与获准的本地编译器资产不可用。没有下载、安装或运行新的solc。源码清单缺精确版本时不猜测pragma范围，也不借系统默认版本。

| 任务 | 文件数 | 有精确版本但无编译器 | 缺精确版本 | 比较数 |
| --- | ---: | ---: | ---: | ---: |
| reentrancy_contract | 142 | 27 | 115 | 0 |
| access_control_contract | 114 | 16 | 98 | 0 |

所有256个文件明确记录跳过；compilation_executed=false，编译失败0（因为根本未编译），Precision/Recall为null而非100%。结果/封存：prompt6_v1/slither/report.json、report.seal.json。不能把“工具具备可选入口”说成“已完成外部验证”。

未来启用时必须有准确metadata版本、可信编译器清单和现有授权。Slither API/源码映射缺失或无可比较CFG时不允许返回空集合成功；modifier内联、别名等差异独立列出。L2现有v2侧使用出现位置起始原始行，Slither侧来自CFG source mapping，粒度仍需解释；L1仅已投影端点partial，不能报告完整事件级覆盖率。

### 48.7 人工抽查表、原始位置与防篡改

真实F3图来自已verify的graphs_v1。seed=0，按稳定文件顺序R/AC各抽15个文件、每文件每关系最多5边，最终512行：R 254，AC 258；DATA_DEF_USE 132、WRITES_STATE 122、READS_STATE 129、ENV_FLOW 129。

交付目录scripts/DFG/experiments/artifacts/dfg_v2/review_v1/：
- review_sheet.csv：用户填写表，UTF-8 BOM。
- review_sheet.blank.csv：不可修改的空表参照。
- review_sheet.provenance.json：source SHA、原节点/边key、证据索引、原源码字节位置。
- review_sheet.seal.json：空表SHA与抽样参数。

CSV SHA：f274e5c0bcbbd0719a2622d71e662c2e52da57b9ae39ccda8c80d6301e438a62。
seal SHA：ff3bd40d23a03b52a9debacd2c3bee6d5b4d4ca3937b204fd86bdba73ae3a99d。

行号来自raw源码和字节证据，不使用预处理后的HCG行号；ENV源节点没有源码行则留空。L1证据标为statement_anchors，不能伪造标识符出现位置。grammar_recovered区分occurrence_confirmed、function_route_recorded、not_recorded，最后一类不等于已证明没有恢复。

只允许用户填写verdict（correct/wrong/unsure）和note。AI未填写任何判断；512行两列均为空。评分前核验封存参照、不可修改列、行数/顺序/唯一ID，拒绝篡改、删除/追加/重复行。每关系正确比例为correct/(correct+wrong)，报告Wilson95%区间；unsure与空白单列，不算分母。空表统计返回null，未将空白视为正确。人工审阅尚未完成。


### 48.8 实际测试、不变量、命令与编码处理

沿用mando、Python3.7.12与共享上下文环境，未升级依赖。Oracle定向19 passed，Slither定向19 passed，review定向28 passed，各4条已有warning。最终整套v2为765 passed（8 warning，约62.97秒），旧DDG＋graph_utils为223 passed（29 warning，约3.68秒），共988 passed、0 failed、0 skipped。warning为既有DGL distutils/NetworkX gpickle弃用提示。不要把测试框架通过与“被测Oracle完全匹配”混同；测试包含对正确检出不一致的断言。

本轮11128个受保护文件SHA未变；HANDOVER/training_changes/PROGRESS的任务前字节前缀保持。graphs_v1/store.json SHA仍为43e45227f7ccd9ebcbb034cb9e64b2cf430acf2c81dfb458b6ceadc344c67d5b。final_acceptance.json记录文件、空表、图store和测试结果；既有图、标签、token、折、checkpoint均未修改。

实际命令（工作树根目录；新输出目录已存在，不能直接覆盖重跑）：
~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_oracle_check.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_validate_slither.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_review_sheet.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py

python -B -m scripts.DFG.dfg_v2.oracle_check \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6_v1/oracle_run_v2
python -B -m scripts.DFG.dfg_v2.validate_slither \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v1/store.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6_v1/slither
python -B -m scripts.DFG.dfg_v2.review_sheet \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v1/store.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/review_v1

# 用户填写后可执行；不会修改抽查表
python -B -m scripts.DFG.dfg_v2.score_review \
  --csv scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.csv \
  --seal scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.seal.json
~~~

Oracle存在差异的退出码1是正确检出结果；分类不将其改成全通过。所有构建/报告输出拒绝覆盖既有目录，复验应指定新目录并按新报告摘要记录分类。

文档初次写入时Windows PowerShell管道把本轮中文转为字面问号；提交前发现并修复。修复仅重写本轮尚未提交的新增段落，依据before.json验证三份历史前缀SHA，使用ASCII管道承载Unicode转义、UTF-8写入，未猜测或更改历史正文。新报告同样修复。此问题未影响ASCII代码、JSON证据或测试结果。

### 48.9 验收结论、未执行项与下一步

满足本Prompt“Oracle全部通过或逐项归类、Slither有结果或明确跳过、空表和seal交付”的验证限定；不能据此宣布完整Solidity DFG正确、全图无错或模型性能提升。剩余项：
1. Prompt 6b修复call选项引起的L1函数级回退，并新建graphs_v2复验；本轮只登记1项实现覆盖缺口。
2. 人工表尚未填写；无正确率结论。
3. 没有可用可信solc，未执行Oracle/真实源码编译和Slither实质对照；L1外部事件对照仍partial。
4. tuple内部逐元素流未验证，L1/L2既有近似/不支持范围没有扩大。
5. 未运行Prompt 7/8、真实模型训练、GPU预检、新seed或其余五类实验。

本轮三次本地提交完成后停止，按共享上下文不自动push。独立复核与实施记录AI：Codex。


## 49. 2026-10-25 DFG v2 Prompt 6b：调用选项读取修复与图存储复验（Codex）

### 49.1 任务边界、提交与历史保护

工作树ge-sc-llm-ddg-v11，分支dfg-v2；按共享上下文及Prompt 6b执行。6c另报。修复提交为 f270ed68d218160be56f8bafba19e070737dab5d。审计实现提交c09bbbc；本节文档提交以Git历史为准，不在正文自引用未来提交SHA。

冻结代码、模型、特征、标签、折与原训练器不变；旧标量成功结果继续复用。graphs_v1、原Oracle期望/SEAL/分类、review_v1和历史产物保留；未训练。

### 49.2 根因、最小实现与用户批准的new_expression补充

Oracle16的target.call{value: x}("")被解析为struct_expression；旧/v2读取器均不支持，函数回退并漏掉x依赖。

实际修改位于dfg_v2/l1_access.py::ExtendedAccessExtractor.reads。对struct_expression读取type字段代表的调用基表达式，再递归读取各struct_field_assignment的value字段。name仅是选项标签，不因存在同名value、gas或salt局部变量就把标签当作使用。未知子表达式、嵌套副作用继续沿既有规则回退，不产生跨函数摘要。

模板同时要求new C{value: v}(...)。实测只补struct_expression仍会在new_expression失败；已先说明并获得用户批准做最小补齐：确认name字段为type_name时，该类型名本身不产生变量读取；构造参数和选项值由外层call/options提取。不新增节点，不扩展完整类型系统，不改变编译版本，不把C误当同名局部变量。未知new-expression形状继续回退。

### 49.3 修复前后证据及Oracle复验

保留失败日志，不删除测试或修改原Oracle期望：
- 调用选项定向回归：修复前9项失败；补struct_expression后9项通过。
- 获准补new_expression后：未实现该分支时7项失败、原9项通过；补齐后16项全部通过。
- Oracle重跑结果为18/20例匹配；16_call_option_fields通过。剩余04_for_update与18_environment_synonyms对应7项既有expectation_error。
- 新建并验证CLASSIFICATIONS_v2.json，记录16为fixed，绑定上述修复提交；原CLASSIFICATIONS、期望文件及SEAL保持不变。
- 6b与6c共同最终回归：v2共886 passed，旧DDG＋graph_utils共223 passed，合计1109 passed。最终日志为prompt6c_v1/v2_final.log与legacy_final.log，8/29条既有DGL/NetworkX弃用warning；0失败/跳过，约59.02/3.77秒。

18/20不是原始期望全通过；解析器和图断言也不代替编译验证。

### 49.4 逐图审计与锚点增强

store_diff先验证旧新store及输入身份，逐F0–F3保留节点ID/顺序/属性、图属性及旧边key/顺序；消失边为0。新增仅限恢复函数的DATA_DEF_USE，附函数、回退原因、源码SHA/区间、语句和事实。

L2/L3边、属性及语义审计逐项相同。其invariants含上游L1边数等派生值，仅排除该派生容器的直接相等要求；边、出现位置、证据和canonical统计不放宽。

锚点独立复核：旧node_id＋Span完整条目按多重集保留，允许既有共享node_id；新增仅限恢复函数合法原始字节范围。补测未抽样锚点篡改、删除、越界新增及共享ID。

### 49.5 用户批准的两项审计规则调整

**调整一：只允许全局证据引用编号重排。** 实际新增事实插入全局evidence数组后，会改变旧边ddg_fact_indices，但原事实可以完全不变。首次严格diff在重入合约F1的10380→10381、key=1处失败：buggy_44.sol的success依赖由索引3849变为3869，完整解析事实相同。未静默放宽；经用户明确同意后，仅对DATA_DEF_USE使用证据身份核验。

旧新索引必须是唯一、有效、非布尔的整数引用；解引用后的事实同序、同重数、全部字段完全相同，端点及self_fact也须正确。逐边记录old→new映射、两侧属性摘要和事实摘要。其余属性、节点、标签、边key严格不变。人工表对应的evidence_indices采用同一受限规则；不能把原始属性字节相同与语义证据相同混为一谈。错误引用、重复、越界、丢失、事实改动仍拒绝。

新增两个正向回归在旧规则下均失败，见reference_identity_before_v2.log；实现后定向77项通过，见reference_identity_after.log。原失败日志和目录保留。

**调整二：单列仍回退函数的原因推进。** 补new_expression后，spank_chain_payment.sol字节4070、5410、6033处的3个函数仍回退；后续限制分别为嵌套写入、assembly、嵌套写入。重入合约和节点两任务均出现这3例。旧新事实均为空、计数0，partial_facts_published=false；仅最后回退原因及对应诊断变化。

r1严格整体记录相等检查因此失败。再次先说明并获得用户批准：仅两侧status均fallback、事实列表为空/计数0且不发布部分结果时，允许reason及唯一对应v2_function_fallback.reason变化，逐文件逐函数记录reason_changes。身份、路由、old_reason、其他元数据、诊断结构、锚点与已支持函数规则不变。

新正例先在旧规则失败，见fallback_reason_before.log；实现后完整定向90项通过，见fallback_reason_after.log。真实源码SHA、函数源码和旧新诊断保存在fallback_reason_examples_r2.json。没有把这3个仍失败函数算作恢复。

### 49.6 构图失败、独立重建与真实恢复量

首次graphs_v2构图末尾源码摘要检查失败：运行期间临时候选以.py扩展名进入scripts/DFG树，而既有_runtime()递归扫描全部.py。该次未完成可接受封存，目录和日志保留。候选改为staging_fix/*.py.txt，正式源码固定后另建graphs_v2_r1；不修改扫描器、不篡改旧seal、不覆盖失败批次。

graphs_v2_r1的cli verify已通过；四任务12张F1/F2/F3增强图的直接compare_graphs预检全部通过，F0保留输入引用。详细记录为preflight_all_graphs_r2.json：

| 任务 | 恢复函数 | 每张增强图新增DATA_DEF_USE | 引用换号旧边 | 仍回退原因变化 |
| --- | ---: | ---: | ---: | ---: |
| reentrancy_contract | 7 | 51 | 2709 | 3 |
| reentrancy_node | 4 | 50 | 1294 | 3 |
| access_control_contract | 6 | 60 | 2231 | 0 |
| access_control_node | 3 | 34 | 1147 | 0 |

每任务F1/F2/F3计数相同、消失边0；节点、非引用属性、旧事实、锚点及L2/L3通过。累计图不可重复计数，合约/节点也含重叠源码。

真实恢复函数的旧最终回退原因均为Unsupported expression: new_expression。本轮真实恢复量主要来自获准补齐的new_expression路径，不能把这些数字全部归因于现代call选项；Oracle则独立证明call选项缺口已经修复。

后续Prompt 7/8的输入应在完整验收通过后登记为graphs_v2_r1/store.json；首次graphs_v2仅保留失败记录，不作为有效训练入口。

### 49.7 人工表沿用、最终绑定与实际命令

最终store_diff_r2为accepted；512条原表边语义相同，76行仅引用换号；两个合约任务F3新增111条未抽样。--equivalence评分退出0，原表仍512行空白、完成数0，正确比例null，不能宣称人工精确率通过。

新store登记4任务、16图项和20个schema。build退出0，891.38秒，387个运行SHA前后一致；独立cli verify退出0，80.29秒；最终差异267.02秒，等价评分281.39秒。11,172个未授权修改的任务前跟踪文件SHA未变，三份文档历史字节前缀保持。完整证据在prompt6c_v1/final_acceptance.json。

以下SHA均为实际文件摘要：
- `graphs_v1/store.json`: `43e45227f7ccd9ebcbb034cb9e64b2cf430acf2c81dfb458b6ceadc344c67d5b`
- `graphs_v2_r1/store.json`: `ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4`
- `graphs_v2_r1/store.seal.json`: `c12cb77c0e4e311e0ac7410e268c50ab5f82c203c1a69ebbf7075f48a7943bde`
- `prompt6b_v1/store_diff_r2/store_diff.json`: `c2c5bb5bfa20f4fa1c500a44a201756d15c7cf5452d95069deb5866461e16232`
- `prompt6b_v1/store_diff_r2/store_diff.seal.json`: `d04cfffcee583ce9de534add717e140eac2de996bde4dcd006f7dc8d1a4234eb`
- `prompt6b_v1/score_review_equivalent_r2.json`: `6807a8773862c26d5ac0b4113aa68ad0071602099e7a2b4c1127fc6d4fffc183`


~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m scripts.DFG.dfg_v2.cli build --manifest scripts/DFG/experiments/artifacts/dfg_v2/inputs/manifest.json --tasks reentrancy_contract,reentrancy_node,access_control_contract,access_control_node --graph-keys F1,F2,F3 --output scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1
python -B -m scripts.DFG.dfg_v2.cli verify --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json
python -B -m scripts.DFG.dfg_v2.store_diff --old-store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v1/store.json --new-store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json --review-seal scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.seal.json --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6b_v1/store_diff_r2
python -B -m scripts.DFG.dfg_v2.score_review --csv scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.csv --seal scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.seal.json --equivalence scripts/DFG/experiments/artifacts/dfg_v2/prompt6b_v1/store_diff_r2/store_diff.json
~~~

以上是实际执行命令；build/diff输出目录已存在，复验须使用新目录。verify/score为只读可重复执行。Oracle runner没有--store参数：手写用例使用同一当前pipeline，真实图不变量单独核验；绑定见oracle_store_binding.json。

### 49.8 研究结论与停止边界

仅证明特定缺口修复及证据保留，不能宣称完整DFG正确或性能提升。6c另报；未训练，不自动启动Prompt 7/8、多seed或其余五类。实施及复核AI：Codex。



## 50. 2026-10-25 DFG v2 Prompt 6c：完整 IR 读写事件与 Slither 外部对照（Codex）

### 50.1 本轮目标、授权与记录状态

工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11，分支 dfg-v2。依据更新后的 PROMPTS 第4.1节及 Prompt 6c，在 Prompt 6b 最小修复与新图验收之后启用真实 R/AC 语料的外部参照。Prompt 6c 不新增图关系、不构图、不改标签、tokenizer、HGT、划分、checkpoint 或训练逻辑。

正式工具与26个编译器准备、接口测试以及256文件的Slither尝试均已完成。239个文件可比较，11个solc编译失败，6个源码映射不完整不可比较。正式运行exit=0、219.89秒，结果封存在prompt6c_v1/slither_full/。实现提交7918427；没有把全部文件称为编译/比较成功。

更新模板原先要求“由用户本人安装，Codex不得自行安装”。本轮用户明确说“Prompt 6c may be need install solc verion, you can install and if needed you can download”，因此已获得下载与安装的任务授权；该指令覆盖模板旧限制。安装仍限定到当前 mando 环境所需工具和本地版本资产，没有全局切换 solc，没有因安装需要升级 Slither 或模型环境。

另经确认，版本选择继续严格保留仓库 auto_version_solc.py 的首个 pragma 匹配和无匹配默认0.4.25规则；将无 pragma 的6个文件明确标记为 fallback_default。没有偷偷改成选择最高版本、多 pragma 交集或编译失败后的第二版本。编译尝试版本不是原作者编译版本证明，也不写回源码元数据。

### 50.2 版本清单与来源分组

先 verify_store，再从输入 manifest 取得源码路径、源码 SHA 与原有 metadata。版本选择顺序为：
1. 已绑定源文件 SHA 的精确 metadata 版本。
2. 没有精确 metadata 时，仅调用仓库 get_solc_version 的只读规则；有正则匹配标 pragma_derived。
3. 没有匹配时沿用 DEFAULT_VERSION=0.4.25，标 fallback_default。

| 任务 | 文件数 | metadata | pragma_derived | fallback_default |
| --- | ---: | ---: | ---: | ---: |
| reentrancy_contract | 142 | 27 | 114 | 1 |
| access_control_contract | 114 | 16 | 93 | 5 |
| 合计 | 256 | 43 | 207 | 6 |

涉及26个不同版本。保存逐文件选择、原始 pragma 匹配列表、选择规则、来源类别、源码 SHA、auto_version_solc.py SHA 及版本清单 seal。不能把先前“213个缺 metadata”直接写为“213个 pragma 推导”；其中6个只是默认值。

例如重入0x966889549fe7b3b950063151f6e2ad7651becdb9.sol先出现^0.4.16，后面还有^0.4.20；旧规则仍选0.4.16。此规则可能导致编译失败，但本轮保留已指定的选择策略，失败原因如实记录，不为提高成功率改选其他版本。

### 50.3 安装、下载来源与二进制核验

mando 中仅新增 solc-select 1.0.4 和 pycryptodome 3.20.0。Slither 0.8.0、crytic-compile 0.2.4、Python3.7及模型依赖保持原版本。package_install_manifest.json 保存包文件、来源、版本和 SHA；environment_before.json、environment_after_install.json 用于核对环境变化。

Solidity 主下载端 binaries.soliditylang.org 返回 HTTP403。采用官方 ethereum/solc-bin 的 GitHub镜像清单与对应二进制；0.4.0、0.4.2、0.4.9使用 solc-select 原有 crytic/solc 旧版本来源。保存两份 list.json 及来源 SHA，不将 crytic 旧版来源误称为 Solidity 官方主站资产。

官方镜像清单 SHA256：b44c1d0e598ed0bcbf4ee49c86c5ae85b63718c1591689b02d12d7a11d45a2ac。
旧版清单 SHA256：a524a402d0657b7073ad967fedc4118f3dd758175124c93f181587e673a1db41。

下载后逐个核对清单 SHA256 和 Keccak256，再赋予可执行权限并运行 --version 核验。trusted_compilers_complete.json 绑定26个版本的绝对路径、SHA、来源和选择清单；compiler_version_checks.json 保存版本输出。没有运行 solc-select use 修改全局默认。

0.5.1曾发生一次下载失败，随后对同一 URL 重试下载并完成哈希校验。这是同一二进制的网络传输重试，不是源码编译失败后换版本，也不是重复实验或模型重训。

### 50.4 正式文件、接口与完整 L1 的准确含义

| 正式文件（scripts/DFG/dfg_v2/下） | 本轮作用 |
| --- | --- |
| l1_occurrences.py（新增） | 只读重建既有成功函数的 IR，导出完整事件读写、声明与函数身份、路由、入口初始化和不可达标记 |
| validate_slither.py（修改） | 版本清单、可信编译器门禁、Slither逐文件运行、完整L1/L2对照、分组统计、映射与异常审计 |
| tests/test_l1_occurrences.py（新增） | 没有DU边的定义、参数位置、同名声明、弱写、不可达、回退无残留等 |
| tests/test_validate_slither6c.py（新增） | 版本/身份/继承上下文/映射不完整/异常链、主入口与旧兼容接口验证 |

Prompt 6的L1候选只来自已投影的定义—使用端点，未用定义、无到达定义的读取、不可投影事件均可能缺失，因此当时不能计算完整出现层召回。此次复用 l1._analyze 确定真实路由：legacy已支持函数继续用原CFGBuilder；仅v2恢复函数用V2CFGBuilder。l1.analyze_file实际并不返回IR，不能假装它已有返回接口。

每个成功函数读取FunctionIR全部blocks/events的reads、writes及weak_writes；未形成DU关系的事件也保留。symbols记录声明字节区间、函数身份及名称，同名变量不能仅按名字混淆。失败函数不导出部分IR；重建成功函数的身份不符视为验证接口错误，不悄悄改成新回退。原始metadata保持原样，pragma/default选出的外部编译器版本绝不传给SupportedSourceView作为新版本证据。

“完整”限定为当前分析器支持函数的未投影IR事件—符号集合。Event本身会对同一语句中同一符号去重，所以x+x通常是一个USE事件项；这里不是逐token出现次数，也不是DATA_DEF_USE边的召回。普通事件使用原始源码语句anchor起始行，entry定义使用声明起始行。不可达事件仍保留并标记；完整出现集合不等同于可达DU边集合。

Slither端只收集实际CFG的local/state read/write集合，不补造参数或命名return的DEF来提高对齐数。v2入口初始化与Slither集合的差异作为entry_initialization筛查类别保留。弱写、别名、modifier、不可达事件等证据可追溯，不改变分析器语义。

主比较保持模板的(原始行,变量名,读/写类型)三元组；另附function/declaration字节身份、同一三元组多身份以及“共同三元组却没有共同声明”的审计。三元组匹配不等于证明声明绑定完全一致。L2继续只读冻结F3审计里的原始出现位置，不重新构建图。

### 50.5 分母、回退与外部参照限制

每个任务分别输出整体L1/L2precision/recall，同时按metadata、pragma_derived、fallback_default分组。L1还按Slither函数字节身份分为supported、fallback、unmapped：成功支持函数与整体参照分开；回退函数候选为空，Slither参考读写量单列；无法可靠匹配函数身份不按同名猜测，放入unmapped。

所有组同时保留原始参考三元组数量及排除上下文数量。只有模板已有alias、modifier_inlining从主错误计数排除，排除数必须可见。inheritance只是分类标签，不减主分母，不能把继承文件整体视为不可比或自动判对。

Slither的同一源码函数可能在多个继承上下文中出现。初始候选曾按源码span保留首个上下文，复核发现它可能让参考集合依赖遍历顺序。已修为收集所有上下文，再对三元组做set union；每条出现保留context_index、contract、declarer和继承标志，重复上下文另计。顺序置换和额外上下文事实不丢的测试已覆盖。

这些指标衡量的是当前v2读写事件相对于Slither集合的一致性，不是漏洞定位性能、完整Solidity语义正确率或图边召回。别名近似、入口语义、语句位置粒度、跨行表达式和声明身份歧义均可产生差异。每任务前20个不一致样例只是按稳定遍历顺序截取，保持requires_review；不得将其直接归为已确认实现缺陷，也不能当作随机代表性样本。

### 50.6 验证器自身的正确性复核

**部分映射不完整。** 初始候选将缺filename_absolute与真实foreign节点一起跳过；如果文件同时有有效节点，就可能拿部分参考集合报告完整P/R。现已区分有效foreign绝对路径、missing_filename、invalid_filename及缺失/非法start。任何不可靠CFG映射使整个文件为not_comparable，保留原因而不生成comparison；不能用其余可映射节点补成“完整”。真正foreign节点正常排除。函数或变量缺文件身份时保留None及unknown identity计数，不从当前上下文伪造target文件名。越界或不合法UTF-8字节位置显式报错。

**外部异常阶段。** Slither构造包含solc编译和后续分析两阶段。旧status=compile_failed仅为接口兼容，新增failure_phase、exception class/module和详情，区分solc_compile、slither_analysis、external_pipeline_unknown。Slither0.8会把InvalidCompilation包装为SlitherError，不能只看顶层异常类型。现优先遍历__cause__/__context__寻找InvalidCompilation，以对象身份集合防止循环链；找不到编译异常时再保留真正Slither分析错误或unknown类别。没有按错误文本猜测。

**暂存与摘要。** 6b构图运行时，已有_runtime会扫描scripts/DFG/**/*.py。6c候选因此转为artifact中的.py.txt；提前测试以内存加载方式接入，测试副本只放/tmp，避免新增候选进入6b运行摘要。正式接入在构图版本稳定后进行，四文件逐字节核对与候选一致。相关6b失败attempt及重建细节见第49节，旧产物未覆盖。

### 50.7 测试、日志与实际可用命令

候选接口先运行新测试与原Prompt6 Slither兼容测试。candidate_tests_01.log保留首轮46通过、1失败：候选文本替换误把inherited引用带入旧兼容helper，导致NameError。仅修复该验证器错误后candidate_tests_02.log为47通过；补完整runner集成用例后candidate_tests_03.log为49通过；补映射不完整负例后candidate_tests_04.log为58通过。各轮4条现有DGL distutils警告，无测试断言被放宽。

正式接入定向58通过；随后异常链分类补4项用例，failure_phase_directed.log中选中的6项通过、25项未选择，0警告。最终本轮全套v2测试886通过，旧DDG及graph_utils测试223通过，合计1109通过；测试统计包含本轮6b/6c新增验证，不能将其解释成真实源码全部能编译或Slither全部一致。

环境与工作目录：
~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

python -B -m scripts.DFG.dfg_v2.validate_slither --help
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/dfg_v2/tests/test_l1_occurrences.py \
  scripts/DFG/dfg_v2/tests/test_validate_slither6c.py \
  scripts/DFG/dfg_v2/tests/test_validate_slither.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

以下是已实际执行的版本清单与正式比较命令；这些输出目录已存在，重跑需指定新目录，不得覆盖：
~~~bash
python -B -m scripts.DFG.dfg_v2.validate_slither \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --list-versions \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/version_inventory

python -B -m scripts.DFG.dfg_v2.validate_slither \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --trusted-compilers scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/trusted_compilers_complete.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full
~~~

当前正式CLI的--help已返回0，参数均实际存在。必须conda activate mando或将mando/bin置于PATH；仅指定Python绝对路径而未激活环境，会使工具清单中的shutil.which找不到solc-select。--list-versions不安装、不编译；可信编译器清单之外的版本不能执行。真实运行每文件只使用预先选定版本一次，异常不会换版本重试。

准备与候选记录集中在scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/：安装前后环境、包manifest、两份编译器来源清单、trusted_compilers_complete.json、compiler_version_checks.json、版本清单及seal、候选/正式测试日志、staging及本草稿。正式结果为slither_full/report.json及report.seal.json；版本清单为version_inventory/；摘要为results_compact.json，原始逐事件大报告保留本地。

### 50.8 真实Slither结果、诊断与证据绑定

整体指标按文件内集合计数后跨文件累加计算，是micro事件一致性；不是等权文件均值，不是漏洞F1或DDG边召回。

|任务|总文件|可比较|solc编译失败|Slither分析失败|unknown异常|不可比较|工具跳过|
|---|---:|---:|---:|---:|---:|---:|---:|
|reentrancy_contract|142|131|8|0|0|3|0|
|access_control_contract|114|108|3|0|0|3|0|

|任务/版本来源|总数/可比/编译失败/不可比|L1候选/参考/匹配|L1 P/R (%)|L2候选/参考/匹配|L2 P/R (%)|
|---|---|---|---|---|---|
|reentrancy_contract/all|142/131/8/3|11821/9693/8623|72.9465/88.9611|7105/8082/7027|98.9022/86.9463|
|reentrancy_contract/metadata|27/25/0/2|767/687/583|76.0104/84.8617|508/637/501|98.6220/78.6499|
|reentrancy_contract/pragma_derived|114/105/8/1|11054/9004/8040|72.7339/89.2936|6591/7439/6520|98.9228/87.6462|
|reentrancy_contract/fallback_default|1/1/0/0|0/2/0|null/0.0000|6/6/6|100.0000/100.0000|
|access_control_contract/all|114/108/3/3|13956/9613/8447|60.5259/87.8706|3587/4128/3526|98.2994/85.4167|
|access_control_contract/metadata|16/14/0/2|62/70/40|64.5161/57.1429|117/124/117|100.0000/94.3548|
|access_control_contract/pragma_derived|93/89/3/1|13894/9219/8407|60.5081/91.1921|3308/3819/3249|98.2164/85.0746|
|access_control_contract/fallback_default|5/5/0/0|0/324/0|null/0.0000|162/185/160|98.7654/86.4865|

L1差异解释（保留主指标，不用更有利口径替换）：
- 重入extra=3198，其中3153（98.59%）带入口初始化差异；访问控制extra=5509，其中5132（93.16%）。这些多为参数/返回值入口DEF，Slither CFG没有对应写入集合项；不能直接认定为错误DDG边。
- 重入missing=1070，其中1033（96.54%）来自L1回退函数；访问控制missing=1166，其中1136（97.43%）来自回退。仅支持函数的未匹配参考为37/30，supported-only召回分别8623/8660=99.5727%、8447/8477=99.6461%。这些是诊断子集，不替换主召回88.9611%/87.8706%。
- 回退函数数为可比文件内264/333；不与全任务构图的269/351混为同一分母。没有删掉模型样本。supported/fallback/unmapped原始与排除量均在报告中；excluded集合为两侧上下文的并集，不能简单当作仅reference被删除的计数。

已核验的L2实例：重入0x01f8…第13行MinSum声明初始化，Slither合成构造函数记WRITE，现L2写证据只覆盖函数内赋值；这是真实范围差别。重入0x123456…第140–142行return，Slither记首行140，L2读取在141/142行且投影边3327→3359存在；访问控制0x01a47…第303–304行赋值，Slither读记303，L2 RHS读记304且边9673→9695存在。后两例是位置粒度差异，不是没有提取关系。全文身份、源码SHA与审计证据在result_review_l2_examples.json。不能把少量例证推广为全部L2差异已解释。

6个not_comparable来自旧0.4.0/0.4.2/0.4.9输出在当前Slither中缺少CFG文件名；不猜来源、不以部分数据输出P/R。本轮没有扩展旧工具源码映射兼容。名单及阻断原因：
- reentrancy_contract/0x6817178368e30a0cd92662442a966b428e8f2d49.sol (0.4.0): {"status": "not_comparable", "blockers": {"missing_filename": 3, "no_target_cfg_nodes": 1}, "foreign_nodes_excluded": 0}
- reentrancy_contract/etherbank.sol (0.4.0): {"status": "not_comparable", "blockers": {"missing_filename": 10, "no_target_cfg_nodes": 1}, "foreign_nodes_excluded": 0}
- reentrancy_contract/simple_dao.sol (0.4.2): {"status": "not_comparable", "blockers": {"missing_filename": 9, "no_target_cfg_nodes": 1}, "foreign_nodes_excluded": 0}
- access_control_contract/0x0bec4767cd170242895d244d7ff73feaff6c2598.sol (0.4.2): {"status": "not_comparable", "blockers": {"missing_filename": 3, "no_target_cfg_nodes": 1}, "foreign_nodes_excluded": 0}
- access_control_contract/parity_wallet_bug_2.sol (0.4.9): {"status": "not_comparable", "blockers": {"missing_filename": 227, "no_target_cfg_nodes": 1}, "foreign_nodes_excluded": 0}
- access_control_contract/simple_suicide.sol (0.4.0): {"status": "not_comparable", "blockers": {"missing_filename": 2, "no_target_cfg_nodes": 1}, "foreign_nodes_excluded": 0}

11个编译失败均保留原版本和错误详情；元数据版本组没有编译失败，失败来自pragma_derived。原规则取首个匹配版本字符串matches[0]，不是求所有pragma的最低兼容版本。1个文件的后续pragma要求更高版本，另10个在选定旧版本下出现语法或名称解析错误（pure、constructor、emit、require及tuple声明等）。这不证明源码在其pragma允许的其他兼容版本下也无法编译；本轮未切换版本重试，也未修改源码。每任务first_20_mismatches保持requires_review，自动类别只作筛查。剩余other、身份歧义、初始化与位置差异不在本轮修改分析器。

正式报告与输入摘要：
- `prompt6c_v1/slither_full/report.json`: `db56b7066430813540e468c900283414bf49c5e7c1f519cded8a874a760fd2a6`
- `prompt6c_v1/slither_full/report.seal.json`: `91e054c9cdd2331b7f21bc48e195a394d6034ffe85f878daa8fb013c9431e49c`
- `prompt6c_v1/version_inventory/versions.json`: `fede2ce63cb3da7cd2cb1b6bab7d2176eb13de0360d759312a979166b5b663ad`
- `prompt6c_v1/trusted_compilers_complete.json`: `c836e07304aa94f6036fda7c9aae43ee8095066b94cf68a72b116302ba0a4c7e`

运行末尾已重新验证源码、F3图及audit、store和计算文件摘要；final_acceptance.json核验11,172个其他任务前跟踪文件未变、三文档原始前缀未变。机器读写比较报告约152MB，作为本地产物保存，不默认把二进制、图或大报告提交Git。

### 50.9 交付边界及后续事项

本轮解决的是Prompt6“没有编译器只能跳过、L1仅投影端点无法计召回”的验证入口问题。完整L1事件清单仍受当前分析器的支持范围限制；Slither本身及版本/源码粒度也有限制。外部一致性、Oracle语义用例、人工边抽查和最终检测效果是不同证据，不能互相替代。

不增加新的DDG语义，不根据Slither差异自动修改标签/图，也不以一个低召回值直接推断历史99%F1的原因。没有运行Prompt7/8、正式模型训练、新seed或其余五类实验。本轮239个可比较文件上的结果已记录，不代表其余17个文件的正确性；人工边表尚未填写，新增111条边也不在旧抽样范围内。实施与复核AI：Codex。


## 51. 2026-10-25 DFG v2 Prompt 6d：跨度对照、差异分类及图不变验收（Codex）


实施与复核：Codex；日期：2026-10-25；起始提交 f14194be329cae5eab236da3270afdfa8f1b74a8，分支 dfg-v2。

已先读取更新后的 PROMPTS.md §4.1 与 Prompt 6d，并执行 git pull --ff-only origin dfg-v2，返回已是最新。Prompt 6b/6c 已完成，本轮复用其最终图 graphs_v2_r1/store.json 和封存 Slither 报告，不重做6b、不扩展分析范围、不训练或开始 Prompt 7。

本轮增加外部对照验证工具。唯一分析器改动是文档明确允许的 new_expression 直接 call_argument 防御分支。四任务语料该形状计数均为0；最终图身份以文末实际重建验收为准。

结论的适用范围：固定 seed=0 抽样172条 other，逐条读原源码与两侧证据，未发现违反当前已声明支持范围的 v2_defect。未抽中的事件仍未完成人工语义证明；这不是“全部DDG正确”，不是漏洞F1，也不是人工边精确率。

### 51.1 比较口径与修正

6c原指标完全保留；新指标以字节跨度计数，不替换原来的行/变量名/读写集合指标。新指标主表包含全部可比较上下文；排除 alias/modifier 的附加口径另列，因此两套分母也不同，不能把数值相减解释为分析器改善。

- L1候选取封存IR事件的语句anchor；入口定义取声明范围。每个不同IR event_id保留，不能因同一anchor和symbol合并事件。
- L2候选取F3 audit的occurrence；参考取封存Slither CFG节点start/end。使用半开字节区间，边界相接但无交集不匹配。
- 在同文件、同变量名、同读写类型内按起点贪心一对一匹配；同起点优先实际事件，再处理entry初始化，随后按终点和ID排序。不复用已匹配事件。
- Slither内部的 _scope_N 重命名，仅在参考声明起点与唯一AST声明身份吻合、源码原名得到验证时规范化。保留原名和证明；不会简单删除字符串后缀。
- 机械归类按Prompt顺序取首个成立条件。delete既处理完整链，也处理occurrence只记录operand标识符的情形；后者必须证明其直接AST父链为delete，普通赋值/其他一元表达式不归入。
- L2的supported/fallback分层沿用6c的L1函数状态，不能解释为L2自身回退。L2仍可能在L1回退函数中提取状态关系。

保留的比较局限：L1结构anchor可能覆盖子语句；名字＋跨度匹配不等于完整类型/绑定证明，声明一致性另记录；L2词法重复出现与Slither按CFG节点变量集合去重的分母不同。没有为提高指标改变图、标签或分析器策略。

已保存 alignment_v1、v2、v3 三轮输出。v1→v2修复不同IR事件合并、scope名称、entry抢配与delete链；v2→v3补齐identifier operand的两个delete分类。最终版本为dfg-v2-slither-span-alignment-v3。

### 51.2 原6c与跨度附加指标

两类分别131/142、108/114个文件可比较，仍有8/3个编译失败、3/3个来源不可比较。文件及失败数没有变化。P/R是事件一致性，不是检测指标。

#### 6c主指标（原样保留）

|任务|层|候选|参考|匹配|P (%)|R (%)|
|---|---|---|---|---|---|---|
|重入|L1|11821|9693|8623|72.9465|88.9611|
|重入|L2|7105|8082|7027|98.9022|86.9463|
|访问控制|L1|13956|9613|8447|60.5259|87.8706|
|访问控制|L2|3587|4128|3526|98.2994|85.4167|

#### 新跨度主指标（含全部上下文）

|任务|层|候选|参考|匹配|P (%)|R (%)|
|---|---|---|---|---|---|---|
|重入|L1|12345|10215|8974|72.6934|87.8512|
|重入|L2|7658|8563|7368|96.2131|86.0446|
|访问控制|L1|14359|10024|8719|60.7215|86.9812|
|访问控制|L2|3994|4425|3802|95.1928|85.9209|

#### 排除alias/modifier的辅助口径

|任务|层|候选|参考|匹配|P (%)|R (%)|
|---|---|---|---|---|---|---|
|重入|L1|12042|9796|8709|72.3219|88.9036|
|重入|L2|7260|8291|7086|97.6033|85.4662|
|访问控制|L1|14136|9705|8527|60.3212|87.8619|
|访问控制|L2|3733|4191|3578|95.8478|85.3734|

#### 按原L1函数状态分组

L2的状态列沿用L1，不代表L2全部回退。unmapped包括独立modifier、合成初始化等未纳入L1普通函数状态的参考上下文。

|任务|层|状态|候选|参考|匹配|P (%)|R (%)|
|---|---|---|---|---|---|---|---|
|重入|L1|supported|12345|9009|8974|72.6934|99.6115|
|重入|L1|fallback|0|1162|0|—|0.0000|
|重入|L1|unmapped|0|44|0|—|0.0000|
|重入|L2|supported|7027|7034|6760|96.2004|96.1046|
|重入|L2|fallback|503|577|480|95.4274|83.1889|
|重入|L2|unmapped|128|952|128|100.0000|13.4454|
|访问控制|L1|supported|14359|8755|8719|60.7215|99.5888|
|访问控制|L1|fallback|0|1240|0|—|0.0000|
|访问控制|L1|unmapped|0|29|0|—|0.0000|
|访问控制|L2|supported|3212|3197|3044|94.7696|95.2143|
|访问控制|L2|fallback|663|756|639|96.3801|84.5238|
|访问控制|L2|unmapped|119|472|119|100.0000|25.2119|

#### 按版本来源分组

|任务|来源|层|候选|参考|匹配|P (%)|R (%)|
|---|---|---|---|---|---|---|---|
|重入|metadata|L1|878|765|654|74.4875|85.4902|
|重入|metadata|L2|648|682|549|84.7222|80.4985|
|重入|pragma_derived|L1|11467|9448|8320|72.5560|88.0610|
|重入|pragma_derived|L2|7004|7875|6813|97.2730|86.5143|
|重入|fallback_default|L1|0|2|0|—|0.0000|
|重入|fallback_default|L2|6|6|6|100.0000|100.0000|
|访问控制|metadata|L1|64|70|40|62.5000|57.1429|
|访问控制|metadata|L2|128|130|123|96.0938|94.6154|
|访问控制|pragma_derived|L1|14295|9626|8679|60.7135|90.1621|
|访问控制|pragma_derived|L2|3694|4099|3508|94.9648|85.5818|
|访问控制|fallback_default|L1|0|328|0|—|0.0000|
|访问控制|fallback_default|L2|172|196|171|99.4186|87.2449|

#### 行口径到跨度口径的匹配变化

第二数列要求旧extra与missing两侧均未匹配而现在匹配；它也包含经声明证明的名称规范化收益，不能全部称为跨行修复。

|任务|层|两侧起始行不同但匹配|旧双未匹配→新匹配事件对|
|---|---|---|---|
|重入|L1|6|31|
|重入|L2|58|57|
|访问控制|L1|0|25|
|访问控制|L2|51|51|


### 51.3 全部差异的机械分类

共13,857条未匹配事件，每条恰归一类；other为773条，非other为13,084条。以下每格为数量（该任务、层、方向差异中的比例）。零值类别也保留，不能把类别归属当作已证明分析器正确。

#### L1

|类别|重入FP|重入FN|访问控制FP|访问控制FN|
|---|---|---|---|---|
|entry_initialization|3347 (99.29%)|0 (0.00%)|5278 (93.58%)|0 (0.00%)|
|v2_fallback|0 (0.00%)|1162 (93.63%)|0 (0.00%)|1240 (95.02%)|
|unreachable_ir|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|named_return_implicit|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|declaration_without_initializer|9 (0.27%)|0 (0.00%)|10 (0.18%)|0 (0.00%)|
|tuple_or_var_declaration|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|other|15 (0.44%)|79 (6.37%)|352 (6.24%)|65 (4.98%)|

#### L2

|类别|重入FP|重入FN|访问控制FP|访问控制FN|
|---|---|---|---|---|
|constant_excluded|0 (0.00%)|342 (28.62%)|0 (0.00%)|363 (58.27%)|
|state_initializer|0 (0.00%)|613 (51.30%)|0 (0.00%)|158 (25.36%)|
|write_base_read|0 (0.00%)|185 (15.48%)|0 (0.00%)|70 (11.24%)|
|modifier_inlining|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|alias|155 (53.45%)|2 (0.17%)|72 (37.50%)|2 (0.32%)|
|v2_binding_unresolved|0 (0.00%)|53 (4.44%)|0 (0.00%)|23 (3.69%)|
|assembly|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|push_pop_skipped|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|other|135 (46.55%)|0 (0.00%)|120 (62.50%)|7 (1.12%)|

每个非空分类的前5例（不足则全部）、原始行、Slither节点文本、v2证据和机械判据见 [PROMPT6D_CATEGORY_EXAMPLES.md](../scripts/DFG/dfg_v2/PROMPT6D_CATEGORY_EXAMPLES.md)，共119例/25组。完整字节证据与全量差异在本地产物category_examples.json及alignment_v3/report.json；这119例不是随机人工审阅样本。


### 51.4 固定样本的逐条判断

最终共有773条other；按每任务、层、方向独立 Random(0)，排序 difference_id 后最多抽30条，不足全取，共172条。先后两轮抽样保留；最终v3与v2相同的165条完整事件证据逐字段相等后复用原判断，另7条由Codex逐条新核验。独立复核确认172条身份唯一完整、524项源码范围/上下文无错配。所有判断文件绑定源码SHA与最终selection。

172条均判为slither_convention（包括参考工具的IR口径与v2明确的保守支持范围差异），0条v2_defect、0条未修复comparator_artifact、0条unclear。它们主要是：

- 独立modifier体及其参数/局部变量被Slither纳入参考，而冻结L1不单独分析modifier体。原记录已是unmapped并带modifier标签，不能说成分析器普通函数漏提取。
- 循环条件上Slither额外记录DEF/WRITE；原条件中没有相应源码赋值。已只读检查安装的Slither SSA更新方法，支持控制流汇合记写的解释；封存报告未保留逐条IR，未宣称每个具体节点的Phi都已直接验证。
- 同一语句重复读取同一状态变量时，Slither按变量集合去重，v2保留不同词法出现。
- 局部数组/结构写入的基对象，v2 L1按既定粗粒度语义读取；Slither的对应IR写目标未必再记这个读取。
- 独立的 x; 及未真正调用的 to.call.value(amount);，源码遍历与操作IR的读取集合有差别。

访问控制剩余7条L2 FN全部检查：6条位于0x0a43edfe106d295e7c1e591a4b04b5598af9474c.sol，源码使用var局部别名，且无pragma/metadata版本依据；v2已记录legacy_alias_version_unconfirmed和callable_local_shadows_state。Prompt3只在确认legacy模式后支持这种隐式storage别名，而Slither使用fallback_default=0.4.25。此为已接受的保守范围限制，不把默认编译器当成源码真实版本，也不保证补版本后所有类型问题都会消失。另1条是rubixi.sol第72行纯while条件处的balance写入约定。

v2_defect模式清单：本次抽样未发现，因此没有新缺陷最小复现或受影响事件数量估计。不能将“0个抽样模式”写成“未抽样事件均无缺陷”。已有Oracle18/20的原始结果与期望问题保持，不重写为20/20。

### 51.5 六文件映射与小项加固

六个缺CFG filename文件均只用已批准的原版本编译器做映射证据检查；没有import但仍不足以证明来源。254个节点中76个表达式与源码精确一致、98个没有独立表达式、80个文本不一致。任一节点不满足即整个文件继续not_comparable，六文件全部保持；没有公布部分匹配P/R，也没有并入6c报告。主要阻断是ENTRY/END没有可核对的独立文本，以及Slither格式化表达式与源码非逐字相同。

new_expression改动仅遍历其直接call_argument，类型名不记USE，原nested write/未知形状回退仍保留。修改前四任务new_expression总数为11/7/6/3（重入合约/节点、访问控制合约/节点），直接call_argument均0。测试覆盖new uint[](n)、new bytes(len)、new string(len)、new C(a,b)、直接参数的合成AST分支及嵌套写入拒绝；解析器测试不等同于solc语言合法性验证。

新增review_v1b对两类合约F3新增的111条DATA_DEF_USE全量导出：重入51、访问控制60。沿用原CSV/seal和score_review，不抽样、不自动填verdict/note。人工分母为0，precision/Wilson为空，completed=false。原review_v1的512行和原seal不改，也没有把AI的172条事件判断混成人工边精度。

CSV SHA256：75b97a5e545c6b9f61304b274e94e6c0f61ccf41a13d913cf0ecdd90813e358a。


### 51.6 文件与测试

|文件|改动及原因|
|---|---|
|l1_access.py、tests/test_l1_access.py|唯一分析器改动：new_expression直接参数读取；防止合法语法树形状变化时漏USE|
|slither_align.py、tests/test_slither_align.py|跨度一对一匹配、确定性分类、全部差异与分层指标、原指标保留|
|slither_mapping.py、tests/test_slither_mapping.py|6个缺filename文件的整文件可证明映射，失败继续不可比较|
|slither_review.py、tests/test_slither_review.py|固定抽样、source/selection/decision绑定、缺陷与比较器未完成门槛|
|review_supplement.py、tests/test_review_supplement.py|111条新边全量空白人工表及旧图等价证据核验|

最终v2全部测试970 passed，旧DDG/graph_utils 223 passed；合计1193通过，0失败/跳过。分别8/29条已有DGL distutils、NetworkX gpickle弃用warning。定向比较器34、映射23、抽样工具16项通过；L1/补充表/旧表组合92项通过（有重叠，不另加总）。

初始fixture导入和Path类型错误、映射测试异常包装预期，以及抽样工具局部ID不够唯一的候选问题均在正式验收前修复，旧日志保留；没有删除测试或放宽语义断言。抽样程序验证身份和绑定，无法自动证明AI语义判断正确，证据正文由本次独立人工辅助交叉检查补足。

实际环境与命令（已有输出目录不可覆盖，重跑须另取新目录）：
~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
python -B -m scripts.DFG.dfg_v2.slither_align \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --report scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full/report.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/alignment_v3
python -B -m scripts.DFG.dfg_v2.slither_review prepare \
  --alignment scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/alignment_v3/report.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/review_other_v3
python -B -m scripts.DFG.dfg_v2.slither_review validate \
  --selection scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/review_other_v3/selection.json \
  --decisions scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/review_other_v3/decisions.json
python -B -m scripts.DFG.dfg_v2.cli build \
  --manifest scripts/DFG/experiments/artifacts/dfg_v2/inputs/manifest.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/temp_graphs_verify
~~~

六文件映射与补充表的实际入口：
~~~bash
python -B -m scripts.DFG.dfg_v2.slither_mapping \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --old-report scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full/report.json \
  --trusted-compilers scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/trusted_compilers_complete.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/mapping/six_files
python -B -m scripts.DFG.dfg_v2.review_supplement \
  --diff scripts/DFG/experiments/artifacts/dfg_v2/prompt6b_v1/store_diff_r2/store_diff.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/review_v1b
~~~


### 51.7 临时重建与不变量验收

cli build成功退出0，耗时842.47秒；其末尾verify_store真实读取图并复算完整/计算指纹和DGL schema。新旧实际文件SHA又单独核对；12张增强图两种指纹全部相同，4个F0原文件引用不变，20个模型schema/profile记录相同；16个图项的gpickle SHA也逐字节相同。

|任务|图|节点|边|完整指纹|计算指纹|文件SHA|
|---|---|---|---|---|---|---|
|reentrancy_contract|F1|18312|24977|相同|相同|相同|
|reentrancy_contract|F2|18312|32399|相同|相同|相同|
|reentrancy_contract|F3|18610|36256|相同|相同|相同|
|reentrancy_node|F1|12036|15179|相同|相同|相同|
|reentrancy_node|F2|12036|20503|相同|相同|相同|
|reentrancy_node|F3|12223|23703|相同|相同|相同|
|access_control_contract|F1|13432|21311|相同|相同|相同|
|access_control_contract|F2|13432|25128|相同|相同|相同|
|access_control_contract|F3|13693|27664|相同|相同|相同|
|access_control_node|F1|7710|12763|相同|相同|相同|
|access_control_node|F2|7710|14621|相同|相同|相同|
|access_control_node|F3|7892|16569|相同|相同|相同|

唯一分析器防御分支没有触发现有语料。原HCG节点/属性、标签/token、CFG/CG、L1/L2/L3关系及model schema保持，不更换正式输入。graphs_v2_r1/store.json是Prompt7/8沿用的最终图存储；这只说明通过本阶段门槛，不等同已完成人工精度或新训练验收。

按Prompt6d要求，只删除本轮新建的temp_graphs_verify：31文件、839,208,415字节（约0.84GB）。删除前核验精确绝对路径在工作树内、无符号链接、目录文件名单与大小完全一致，保留temporary_rebuild_comparison.json、执行日志及清理收据。没有清理C盘、旧图或其他历史产物；本项目仍写入位于E盘的WSL。

原11,188个跟踪文件中只允许本轮两个旧v2文件和三份文档变化；其余11,183个文件须逐SHA一致，三份文档原始前缀须完全保留。最终保护收据为prompt6d_v1/final_acceptance.json。


### 51.8 执行偏差、保留事项与停止点

本轮没有另提或实施需要替代原方案的设计；比较器修正属于Prompt6d明确要求的错误修复。前轮用户批准的new类型处理、证据索引重排、回退原因推进、默认编译器单列等决定继续沿用，未扩大解释范围。

必须记录一项执行偏差：辅助复核过程中，代理额外对访问控制buggy_43.sol执行1次、buggy_30.sol执行2次只读Slither探针，超出了本轮仅允许重跑6个映射文件的范围。发现后已立即停止；共2文件3次调用，使用已有可信编译器，无安装下载、无源码/图/标签修改。其结果没有并入正式6c/6d统计，也没有用来替换封存证据；命令和原始输出保留在review_other_v1/unplanned_read_only_verification.json。这项偏差不被表述为用户批准的变更。

另有一次人工辅助判断被纠正：旧5条modifier事件本来就标为unmapped/modifier_inlining；初读误认为_scope误判，复核封存SHA后撤回。旧判断与v1_modifier_correction.json都保留，原selection/report未改。不能据此前误读再改比较器。

仍未执行：完整Slither重跑、现代Oracle样例的新增编译验证、人工111边判定、全部other人工检查、训练、Prompt7/8和push。6c的11个编译失败与6个不可比较文件保持；不删除数据集样本。

本轮结束在Prompt6d验收。若未来发现支持范围内的提取错误，应单独进入6e，不能为通过当前比较而直接改分析器。

### 51.9 产物、摘要与后续入口

所有本轮机器产物位于scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/；review_v1b单独位于同级目录。大图与百MB级报告继续本地保存，不随代码提交。

|相对artifacts/dfg_v2的路径|SHA256|
|---|---|
|graphs_v2_r1/store.json|ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4|
|prompt6c_v1/slither_full/report.json|db56b7066430813540e468c900283414bf49c5e7c1f519cded8a874a760fd2a6|
|prompt6d_v1/alignment_v3/report.json|c1f68cd9ea37d00653700545d3cce322114f132ce29db127f6222f8ae6cbd22a|
|prompt6d_v1/review_other_v3/selection.json|50be18b44f273821bb9f37a82e12ea8037caa335059659b35909b2ebac743188|
|prompt6d_v1/review_other_v3/decisions.json|99554b42ba8e92df7638f857e0b2662254873711555a9b955bc2d88efbffd619|
|prompt6d_v1/temporary_rebuild_comparison.json|d546366f3b2bea1ad19618e4386101f7e00b8c6d32ec68f3f78a63e65f03ed93|

机器统计：alignment_v3_compact.json、category_counts.csv；抽样与逐条依据：review_other_v3/；六文件证明：mapping/six_files/；新增空表：review_v1b/。旧v1/v2报告与判断均保留，不能把候选版本混作最终统计。


文档选择记录：没有新增替代方案审批请求；仅实施模板明示的小项加固与比较器纠错。已有6b/6c批准项继续有效，本轮额外3次探针属于已公开记录的执行偏差，不追认为授权。全部修改在dfg_v2内；其他训练/模型/分析器代码不改。按共享约束仅本地提交，未push。


## 52. 2026-10-25 DFG v2 Prompt 6d.1：计数单位与标签拆分、全量判据和实证复核（Codex）

修改AI：Codex。基于2e7d215；本节为本轮详细追加，前51节原文不改。


实施与复核：Codex。记录时间：2026-10-25 14:15 UTC。起始分支 dfg-v2，HEAD 2e7d21554521cc81a06e815f708b035198b01e77；git pull --ff-only origin dfg-v2 返回已最新。已先阅读更新后的 §4.1 及 Prompt 6d.1；Prompt 6b 复用已完成结果，不重复实现。

### 结论与验收边界

本轮完成规定的验证工具修改、六例直接实证、旧172条重分类、剩余other全查及五类各5条抽查。**没有新确认的 v2_defect，分析器和已有图未修改；这不等于全部DDG语义已经证明正确。**

L2单位修正消除了255条能够明确追溯到“同语句重复计数”的旧FP：重入135、访问控制120。773条旧other由255条已解决重复、517条新机械判据和1条仍未解释的rubixi状态循环组成。全部13,553条当前差异有机械分类；规定的剩余other已查1/1，未查other为0，但该1条判定仍是unclear。

合并旧重分类、剩余other、新判据样例共198条审阅记录，包含不同审阅目的对同一事件的重复记录：60 comparator_artifact、50 v2_scope_limit、72 slither_convention、16 unclear、0 v2_defect。16条unclear对应15个独立差异身份。另有76条绑定差异独立逐条核验。当前13,553条差异中，去重后203条做过逐条审阅，**13,350条未逐条语义判定**；五类新判据517条中126条已逐条查看，391条只做了机械分类。不得把“other清空到仅1条”写成“全部差异均已人工验证”。

固定图存储继续为 graphs_v2_r1/store.json，是后续Prompt7/8的固定输入，不创建新图版本。但当前审查状态为 unresolved_analyst_findings，仍有下述证据缺口；未自动开始Prompt7/8或训练，也未宣称无争议语义验收。

### 实际改动

- slither_units.py：仅验证端将L2按(文件、Unit语句跨度/角色、callable、变量名、READ/WRITE)归并；同键不同声明报错。保留全部词法出现、原证据及旧ID→新Unit映射。优先语句区间，必要时用statement与occurrence并集回退；缺statement不猜最近节点。
- slither_align.py：v4.2复用封存6c输出，L1仍为IR事件；L2参考仍是Slither CFG节点的变量集合。保留v3指标并重放原FP身份，区分重复归并和跨度匹配变化；集成新类别和绑定原因。旧v3版本、同一6c报告SHA、store、源码、实证及seal均校验。
- slither_patterns.py：五类精确AST/声明谓词；不按变量名直接判断。只在旧类别未命中时应用；L1/L2循环实证独立门控。suggested_verdict仅是机械建议，不能替代审阅结果。
- slither_review.py：保留旧v1读取；新增prepare-followup和五类verdict。独立冻结旧重分类、剩余other及每谓词5例。绑定完整事件/邻近证据/源码SHA/旧判定；scope需文档原句，convention需固定探针JSON定位，已解决artifact需新报告精确映射。
- slither_conventions.py及convention_cases/：六个固定手写文件，已有可信solc 0.5.11，保存Slither 0.8.0节点集合、IR/SSA、源码与编译器摘要。
- 新增三份测试：test_slither_units、test_slither_patterns、test_slither_conventions；扩展test_slither_review。
- 本报告和三份历史文档只新增/追加。本轮未改L1/L2/L3、pipeline、HGT、tokenizer、标签、fold、训练脚本或旧报告/人工边表。

没有采用需要替换用户设计的方案；发现的两个工具错误在本轮允许的比较器范围内修复。原批准选择继续保留，没有执行新的分析范围扩展。

### 单位修正前后指标

下表是**读写事件集合一致性，不是Buggy-F1，不是DDG边precision/recall**。参考文件集合与6c相同：重入131/142可比较；访问控制108/114可比较。原11编译失败和6映射不可比文件仍按原记录排除比较，但模型图中的样本不删除。6c原行集合指标原封不动。

|任务|层|版本|候选/参考/匹配|FP/FN|Precision %|Recall %|
|---|---|---|---|---|---:|---:|
|重入|L1|v3|12345/10215/8974|3371/1241|72.6934|87.8512|
|重入|L1|v4.2|12345/10215/8974|3371/1241|72.6934|87.8512|
|重入|L2|v3|7658/8563/7368|290/1195|96.2131|86.0446|
|重入|L2|v4.2|7485/8563/7368|117/1195|98.4369|86.0446|
|访问控制|L1|v3|14359/10024/8719|5640/1305|60.7215|86.9812|
|访问控制|L1|v4.2|14359/10024/8719|5640/1305|60.7215|86.9812|
|访问控制|L2|v3|3994/4425/3802|192/623|95.1928|85.9209|
|访问控制|L2|v4.2|3863/4425/3802|61/623|98.4209|85.9209|

L1匹配数量和全部指标完全不变。L2重入词法候选减少173（7658→7485），访问控制减少131（3994→3863）；匹配数量及FN不变。旧FP总数482→178，净减少304。其中255条旧FP已明确对应一个原本有匹配词法事件的同一Unit；余49是仍未匹配的alias Unit内部的重复归并。**净减少304与已匹配语句内消除255是不同口径，不能混写。** 本批因扩大跨度单独解决的旧FP为0。逐项证据在每文件unit_comparison.old_fp_resolution及units中。

语句Unit的if/loop AST跨度可能包含子语句，因此跨度匹配本身不能证明绑定/依赖正确；报告保留这一限制。分类时读取/写入是否位于某语句，必须改用实际occurrence位置，不能用整个外层Unit跨度推断。

### 全量互斥类别

单元格为该任务、层、方向内的“数量（比例%）”。FP/FN只是相对于Slither参考的额外/缺失项，不自动表示v2语义错误。解释列区分候选原因与逐条判定，不把未审项强制赋成convention。

#### L1

|类别|重入FP|重入FN|访问控制FP|访问控制FN|标签/证据状态|
|---|---:|---:|---:|---:|---|
|entry_initialization|3347 (99.29%)|0 (0.00%)|5278 (93.58%)|0 (0.00%)|入口建模差异；未逐条赋最终语义标签|
|v2_fallback|0 (0.00%)|1162 (93.63%)|0 (0.00%)|1240 (95.02%)|回退范围诊断；不等于所有回退都已验证合理|
|unreachable_ir|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|named_return_implicit|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|declaration_without_initializer|9 (0.27%)|0 (0.00%)|10 (0.18%)|0 (0.00%)|声明建模差异；未新增专项实证|
|tuple_or_var_declaration|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|modifier_body_unanalyzed|0 (0.00%)|44 (3.55%)|0 (0.00%)|29 (2.22%)|v2_scope_limit（抽查5条）|
|loop_header_merge_write|0 (0.00%)|35 (2.82%)|0 (0.00%)|36 (2.76%)|标量局部实证支持；aggregate/storage循环仍unclear|
|aggregate_base_use|13 (0.39%)|0 (0.00%)|12 (0.21%)|0 (0.00%)|memory实证支持；storage引用仍unclear|
|bare_expression_use|2 (0.06%)|0 (0.00%)|340 (6.03%)|0 (0.00%)|slither_convention（抽查5条；限定已确认地址调用形状）|
|other|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|1条rubixi状态循环WRITE，unclear|

#### L2

|类别|重入FP|重入FN|访问控制FP|访问控制FN|标签/证据状态|
|---|---:|---:|---:|---:|---|
|constant_excluded|0 (0.00%)|342 (28.62%)|0 (0.00%)|363 (58.27%)|明确排除常量的范围差异；机械类别|
|state_initializer|0 (0.00%)|613 (51.30%)|0 (0.00%)|158 (25.36%)|状态初始化范围差异；机械类别|
|write_base_read|0 (0.00%)|185 (15.48%)|0 (0.00%)|70 (11.24%)|14 delete有实证；241成员写未获得对应最小实证|
|modifier_inlining|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|alias|117 (100.00%)|2 (0.17%)|61 (100.00%)|2 (0.32%)|别名关联口径；未逐条判定|
|v2_binding_unresolved|0 (0.00%)|53 (4.44%)|0 (0.00%)|23 (3.69%)|76条逐条核验为v2_scope_limit|
|assembly|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|push_pop_skipped|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|loop_header_merge_write|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|标量局部实证支持；aggregate/storage循环仍unclear|
|legacy_alias_unconfirmed|0 (0.00%)|0 (0.00%)|0 (0.00%)|6 (0.96%)|v2_scope_limit（旧6条＋新固定5条核验）|
|other|0 (0.00%)|0 (0.00%)|0 (0.00%)|1 (0.16%)|1条rubixi状态循环WRITE，unclear|

### 审查记录、实证及仍有争议项

旧172条只改新判定与解释，原selection、decisions、source/excerpt/primary/nearby完整保留。最终旧172为60 artifact、40 scope、61 convention、11 unclear；初稿把3条array/storage-reference循环与标量Phi混用，root交叉检查声明后收紧为unclear，草稿仍保留。新25条谓词抽查全部predicate_verified=true，但10 scope、11 convention、4 unclear，不能把“谓词成立”当作“约定机制已证明”。rubixi额外的1条判为unclear。

|手写实证|直接观察|可支持的范围|
|---|---|---|
|while/for局部i|IF_LOOP含local WRITE和SSA Phi|支持标量局部循环合并写；不自动推广到storage引用|
|while状态s|条件仅READ，无state WRITE/Phi|未证明L2循环合并写|
|m[k]=v|只写m|不能解释所有结构体成员写的base读取|
|delete m[k]|读＋写m|支持14条同形状delete差异解释|
|m[k]+m[k]、s+s|同CFG节点只记一次对应READ|直接支持语句级去重|
|memory a[i]=v|只写a，不读a|支持memory数组base-use口径差异|
|带参modifier|条件节点归属modifier自身|支持上下文区别；不证明v2已内联modifier|
|x; / 未调用to.call.value(amount);|前者不读x；后者读to、不读amount|限定裸表达式/已确认地址低级调用选项；真正调用会读to和amount|

六个固定.sol文件各运行一次，6/6编译及Slither成功；无真实语料Slither重跑、无安装下载、无全局solc版本切换。scoped_conclusions是同份报告的只读派生，额外Slither调用0。源码、所有节点、IR/SSA及编译器版本/SHA在slither_conventions/保存。一次编译器的最小实证不证明所有历史版本和所有类型都完全一样。

剩余不确定内容：
1. rubixi.sol（访问控制，metadata 0.4.15）while条件2456:2498记录balance WRITE；源码条件仅读，循环体后续有send及balance -=。本轮状态循环最小例无Phi，旧封存参考没有此节点SSA，不能以局部Phi推测替代直接证据。保持unclear，不把它断言为v2漏写。
2. 已审的storage数组/引用写以及array/storage循环合并写：谓词可证，完整参考机制尚缺专项实证，保留unclear。
3. 既有write_base_read的255条中，14为delete，241为状态结构体/成员链赋值。后者只是机械来源核验，不纳入“全部已证明convention”；不以普通mapping赋值的反例或delete正例直接泛化。
4. 全量alias等旧机械类别没有在本轮逐条完成语义审查；原人工512边表和新增111边表仍未填写。此轮审查是AI辅助事件差异分析，不是独立人工DDG边精度标注。

### 76条绑定差异

重入53、访问控制23，涉及116条同名且实际跨度/声明/callable对应的诊断，全部reason=state_name_ambiguous，逐条标v2_scope_limit，引用§3.3“找不到或有歧义，只跳过这一处出现，不放弃整个函数”。逐文件、变量、声明、源码SHA、原句和诊断在binding_review/final_report.json。

本批“ClosedScopeJ失败→只看当前合约→继承状态找不到”的实际命中为0；测试有该子型的正反例，但不把测试构造当成真实语料现象。未通过修改绑定器增加覆盖。

### 测试、失败记录和不变量

最终：v2 1075 passed、8条既有warning；旧DDG/graph_utils 223 passed、29条既有warning；合计1298 passed，0 failed/skipped。warning为DGL distutils与NetworkX gpickle弃用。无训练。

保留中间失败/修订：
- targeted_tests_r1：补丁换行转义导致3个收集错误，修复后149通过，未删除/放宽测试。
- alignment_v4.log：首次真实集成因binding_audits漏初始化NameError失败；补集成反例后重跑。
- alignment_v4：整Unit跨度让34条body写被条件READ影响分类；精确occurrence修正后v4_r1仅剩1 other，匹配指标不变。
- 独立审查补v3版本及同一6c report SHA校验；v4_r2为最终，任务统计和所有差异与r1逐项完全相同，有alignment_guard_only_equivalence.json证明。所有旧目录/seal未覆盖。
- 全套v2测试在各实质修订后分别1070、1071、最终1075通过，最终值不累加历史测试次数。

最终run已只读验证16个图项和20个登记schema；源码/输入/运行时摘要再核验。最终保护快照见final_acceptance.json：除本轮验证工具与文档，其他原跟踪文件及三份文档历史前缀不变；11个封存输入摘要不变。未重建图，未调用HGT前向训练来比较F1。

### 产物与实际命令

正式产物根目录：
scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/
- alignment_v4_r2/report.json、report.seal.json：最终全量证据。
- metrics.csv、categories.csv、review_coverage.json：轻量结果。
- review_r2/selection.json、decisions.json、validation.json：198条目的完整审查。
- binding_review/final_report.json：76条完整绑定核验。
- slither_conventions/及scoped_conclusions：六文件直接实证。
- before.json、final_acceptance.json、日志：不变量及测试。中间版本均保留。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py

python -B -m scripts.DFG.dfg_v2.slither_conventions --trusted-compilers scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/trusted_compilers_complete.json --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/slither_conventions

python -B -m scripts.DFG.dfg_v2.slither_align --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json --report scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full/report.json --prior-alignment scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/alignment_v3/report.json --conventions scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/slither_conventions_scoped_conclusions.json --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/alignment_v4_r2

python -B -m scripts.DFG.dfg_v2.slither_review validate --selection scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/review_r2/selection.json --decisions scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/review_r2/decisions.json
~~~

上面的生成目录已经存在，不能原地重跑覆盖。新实验须另设目录并按需求授权；只读validate和pytest可直接运行。prepare-followup按API/CLI绑定旧v3 selection/decisions、最终alignment和两份conventions输入；全部SHA在selection里。

### 停止位置

本轮验证工作结束，不自动执行Prompt6e、7、8，不改变模型或标签以提高成绩。没有新确认缺陷模式需立即修复，但也不凭全绿测试解除上述语义不确定性。仍采用固定graphs_v2_r1，不覆盖或迁移旧实验。本地按共享上下文提交；本轮没有推送请求，不自动push。


## 53. 2026-10-25 DFG v2 Prompt 6d.2：定向实证、类别级验收与残留影响（Codex）

实施与审查：Codex；日期：2026-10-25。分支dfg-v2，开始HEAD 95775d3abee50c368070f33de48b6668fea8a8b7。按共享上下文pull --ff-only，从已完成6d.1的a32caa2前进到更新模板。本轮只增加验证工具和记录。

### 53.1 结论与验收范围

**通过用户批准后收紧的有界FN门槛：passed_with_bounded_FN_residuals。graphs_v2_r1/store.json确定为Prompt7/8最终图存储，携带本报告的10条残留及范围限制。** 这不是“所有差异清零”或“完整Solidity DDG已证明正确”。

原13,553条差异及alignment_v4_r2分类未改。按任务×层×方向×类别分28个非空组，各用独立Random(0)从排序身份抽10条/不足全取，共242条，逐条审阅机械判据。样本判断：129 slither_convention、110 v2_scope_limit、3 unclear。类别：25 accepted、3 accepted_with_residual。样本中3条未决对应全量10条，不能只报3条。

全量残留为9条聚合循环合并事件FN＋1条rubixi状态条件WRITE FN；当前弱定义抽象下定义覆盖/KILL及已有依赖影响已逐条核验，未确认v2_defect。分析器、pipeline、HGT、tokenizer、原图、token、标签、折、训练代码未改；无真实语料Slither重跑、依赖安装、图重建或正式训练。

原6d.1的16条unclear记录对应15个唯一事件：9个storage下标写获得实证解释；5个循环事件＋rubixi仍未解释。全量又纳入4个同类循环事件，最终残留10个；旧决定未覆盖。

图存储SHA：ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。
原对齐报告SHA：487640ab0b6a0993615f7a1f9fb39ccde426f244e411e3a5da1e884a713244e4。

### 53.2 已征求并采纳的调整

|调整|原因与用户选择|实际执行|
|---|---|---|
|收紧残留门槛|用户同意：≤20且全FN外，还须核查定义覆盖/KILL和已有依赖；漏写可能使旧定义错误传播|对10条逐项核验，validator和反例测试均实现|
|增加声明控制|原五组机制未直接覆盖入口、无初始化声明和状态初始化；用户同意在原fixture补极小控制|参数、具名返回、未初始化局部、局部/状态显式初始化，原11个case/version身份不变|
|alias按实际READ细分|模板按WRITE解释，但178个FP全为READ；用户同意补引用读取及复合赋值|旧分类不改，新182条逐项审计，无伪造WRITE|
|补形状实证|struct成员写不是storage数组下标写；scalar Phi不能直接解释bytes循环|用户批准额外1个小fixture两版各一次；负观察照实保留，不重跑真实语料|

按28个分层而非把类别跨R/AC或FP/FN混合抽样，是较严格的实现；不换seed挑样本。只有上述四项实质调整需征求并已获得用户同意。

### 53.3 实际代码、文件和逻辑

新增7个验证.py，均在scripts/DFG/dfg_v2：

- slither_targeted_probes.py：固定fixture白名单和两个已有可信版本，保存源码/编译器SHA、节点读写、IR/SSA及声明元数据，拒绝覆盖。
- slither_composite_retry.py：只允许记录中的保留词失败两个版本，按字节约束修复后重试。
- slither_shape_supplement.py、slither_shape_retry.py：获准的补形状验证，以及唯一失败版本的受限转换语法修复。
- slither_alias_audit.py：182条alias事件的AST、声明、初始化来源、唯一状态根/重复局部名身份检查，不运行原分析器。
- slither_bare_audit.py：穷尽342条bare表达式的AST形状，区分option setter与实际外层调用。
- slither_category_audit.py：固定抽样和前10形状直方图，验证文档quote、探针JSON pointer/value、事件身份、源码清单、残留影响及最终门槛。

新增5个对应测试：test_slither_targeted_probes.py、test_slither_shape_supplement.py、test_slither_alias_audit.py、test_slither_bare_audit.py、test_slither_category_audit.py。convention_cases/p6d2下9个fixture含失败原件和修正件；未来默认入口只选择合法修正件。

validator不自动推断语义verdict。Codex逐条决定独立存JSON；测试覆盖源码/身份/quote/pointer/value篡改、抽样遗漏/重复、虚构residual或defect、隐藏unclear、FP残留、21个FN，以及缺少KILL/已有事实影响证据的拒绝。

仅新增报告PROMPT6D2_REPORT.md，并在HANDOVER、training_changes、PROGRESS末尾追加。原training_changes正文按before SHA快照引用，避免本轮追加使历史scope引用失效。

### 53.4 两版本实证和真实失败记录

**实际16次Slither尝试＝13次成功＋3次保留的语法失败；13个不同case/version成功身份；真实语料调用0、下载/安装0。** 使用可信清单中的0.4.24、0.5.11，legacy var只在0.4.24。

- 原11次中9成功、2失败：手写fixture函数名误用了保留词indexed。只改为arrayWrite，独立目录重试失败的两版，原9个成功未重跑。
- 批准的补充2次中0.4.24成功、0.5.11因byte(1)转换语法失败；仅改成bytes1(uint8(1))，只重试失败的0.5.11一次。没有改循环体来追求Phi结果。
- 最初两个shell/PATH preflight失败发生在实际编译前，不计16次；补齐已有mando PATH后继续，没有安装依赖。
- 原失败源、报告、异常、seal和执行版本SHA全部保留。执行源归档为.py.txt，避免被原_runtime()的*.py全树扫描当作计算模块；relocation记录旧→新路径，未改旧seal。
- 文档首次写入调用出现JS字符串语法错误，脚本未执行、无文件写入；修正调用后才写文档，不影响测试或实验。

|机制|0.4.24与0.5.11实测|结论边界|
|---|---|---|
|balance循环有send/无send|条件都没有状态balance WRITE|未复现rubixi猜测|
|storage引用p循环|局部p有Phi/WRITE，状态根无条件WRITE|仅对该形状成立，不外推records/out|
|s.f、m[k].f、arr[i].f、s.inner.g赋值|状态根READ＋WRITE|支持成员链write_base_read差异|
|scalar mapping赋值 / delete|前者仅WRITE，后者READ＋WRITE|保留两者差别|
|storage p.f=v|局部p READ＋WRITE，状态根WRITE|不能声称所有storage基变量都无READ|
|storage数组/bytes下标赋值|局部基变量WRITE但无READ|对应真实25条下标写base-use|
|records/out循环条件|只有计数器i的Phi/WRITE，无records/out|真实9条聚合条件合并事件继续unclear|
|引用读取/复合赋值|状态READ缺失，复合赋值仍记状态WRITE|支持实际178条alias READ差异|
|引用重绑定后写|只写second，不写first|实际数据中没有多根并集FP|
|bare identifier/无外层调用option setter|目标READ缺失|对应穷尽核查的342条形状|
|参数/具名返回/未初始化局部|有声明元数据，入口/未初始化处无对应DEF IR|与v2入口/隐式初始化事件口径不同|
|自身状态初始化|Slither合成构造器计WRITE|v2按既有政策不计自身声明写/自环|

结论只对绑定的版本和形状成立。能被Tree-sitter解析不等于编译成功；这里区分13个成功身份、3次失败原件和未重新编译的真实语料。

### 53.5 全量重点核对及类别分布

alias FP：R117、AC61，全为单根状态READ（227原始occurrences）；状态WRITE缺失FP0、多根并集FP0。位置、局部声明、初始化来源、唯一状态根逐条匹配。

alias FN：R2、AC2，都是各自buggy_24.sol::calcDynamicCommission。不同for块中有2个storage和1个memory同名user；当前binder按callable整体拒绝重复局部名。目标块实际唯一storage声明，因此这是§42.3已记录的保守范围，**不是Solidity语言自身歧义**。L2不执行RD/KILL，不会因此让L1旧定义传播。

bare342：AC340＝334条to.call.value(amount);（没有最后的外层调用括号）＋6个独立标识符；R2均独立标识符。零实际外层调用、零判据错误，未触发修改旧分类。334条均0.5.x；8个identifier中7个0.4.x、1个0.5.x，补实证覆盖两版本族。

state_initializer771：全部是明确RHS初始化对自身声明的WRITE，符合原“不计自写/自环”要求；包括初始化表达式不等于加自身写边。v2_fallback2402：精确函数、原因、零events/occurrences/facts、partial_facts_published=false均核对。接受范围不等于恢复这些函数。aggregate_base_use25：12个storage固定结构体数组＋13个memory bytes，都是下标写，已全量复核而非套用p.f结论。

76个绑定差异、705个constant排除、6个无版本依据legacy别名等按原scope及随机样本验收。没有伪造编译器版本或修改标签。模板前10种形状及数量见categories/selection.json.histograms；仅用于描述，不驱动分类或分析。

|任务|层/方向|类别|总数|随机检查|状态|残留|
|---|---|---|---:|---:|---|---:|
|AC|L1 FN|loop_header_merge_write|36|10|accepted_with_residual|4|
|AC|L1 FN|modifier_body_unanalyzed|29|10|accepted|0|
|AC|L1 FN|v2_fallback|1240|10|accepted|0|
|AC|L1 FP|aggregate_base_use|12|10|accepted|0|
|AC|L1 FP|bare_expression_use|340|10|accepted|0|
|AC|L1 FP|declaration_without_initializer|10|10|accepted|0|
|AC|L1 FP|entry_initialization|5278|10|accepted|0|
|AC|L2 FN|alias|2|2|accepted|0|
|AC|L2 FN|constant_excluded|363|10|accepted|0|
|AC|L2 FN|legacy_alias_unconfirmed|6|6|accepted|0|
|AC|L2 FN|other|1|1|accepted_with_residual|1|
|AC|L2 FN|state_initializer|158|10|accepted|0|
|AC|L2 FN|v2_binding_unresolved|23|10|accepted|0|
|AC|L2 FN|write_base_read|70|10|accepted|0|
|AC|L2 FP|alias|61|10|accepted|0|
|R|L1 FN|loop_header_merge_write|35|10|accepted_with_residual|5|
|R|L1 FN|modifier_body_unanalyzed|44|10|accepted|0|
|R|L1 FN|v2_fallback|1162|10|accepted|0|
|R|L1 FP|aggregate_base_use|13|10|accepted|0|
|R|L1 FP|bare_expression_use|2|2|accepted|0|
|R|L1 FP|declaration_without_initializer|9|9|accepted|0|
|R|L1 FP|entry_initialization|3347|10|accepted|0|
|R|L2 FN|alias|2|2|accepted|0|
|R|L2 FN|constant_excluded|342|10|accepted|0|
|R|L2 FN|state_initializer|613|10|accepted|0|
|R|L2 FN|v2_binding_unresolved|53|10|accepted|0|
|R|L2 FN|write_base_read|185|10|accepted|0|
|R|L2 FP|alias|117|10|accepted|0|

### 53.6 十条残留及逐项影响证据

下表为**事件级FN，不是漏洞预测FN**。显示原始源码行，完整身份另含任务、文件SHA、声明和字节跨度；两类同名文件不能互换。完整证据在categories/category_decisions.json.residuals。

|任务|文件:原始行|变量|difference_id|
|---|---|---|---|
|R|buggy_24.sol:584|records|bc2926a02d4819e771eb18df8cc5e8120e80d4da9a00dc5419b07d4c67220895|
|R|buggy_24.sol:603|records|67752ea17725fdf910124558b448965e7a9478d3509e2e2bed5e4fe9359b8ac3|
|R|buggy_24.sol:620|records|d4992669d5b84e89772f1a96ddce3d8abbc389f5a4bfdd751504d8dce31046de|
|R|buggy_44.sol:282|out|5a3ba584c12b02fd45be60d690984736aec3a36704cfc4fbe3716f18baa53163|
|R|spank_chain_payment.sol:174|result|fb9ff767395025afb989b3209b96e05f68becabe57ac3e80de853f57c76b8fbc|
|AC|buggy_24.sol:484|records|2536e13abf586058374adc721247526bd552ebc9dfd97662cd335acc05c17d8b|
|AC|buggy_24.sol:497|records|032fbd78293a5c0e6c6a007a7a60c61341f5878226a0b7916527ec79a3ec6b97|
|AC|buggy_24.sol:509|records|1befae2915f10cbb22a96faf871123cb74e874545fd4ea847fed4aaccc16cca5|
|AC|buggy_43.sol:162|out|e215076b432233f2e6d39b891b87077cb4e0fb8bc1319839d2b3922191fc299b|
|AC|rubixi.sol:72|balance|bdf6280be639984106343991a13d0856cf2a2c0e25f534010c61da49455ab5cf|

聚合循环9条：条件均纯比较；同一声明的真实body弱DEF已存在。9条都有到循环后读取的非自环事实并保留初始化定义；6条有非自环循环回传，3条memory bytes通过分析自事实体现回传（没有给模型加自边）。前驱union和弱GEN不KILL保留这些依赖，因此没有遗漏实际条件写或KILL的证据。**仅在当前基变量弱定义抽象内通过**，Slither真实条件合并原因仍未复现。详见aggregate_loop_residual_impact.json。

rubixi：真实条件无赋值/更新/delete/调用，body balance-=的READ/WRITE均已投影。冻结L1只处理_fee、payoutToSend；L2在其后独立加hub边，不把条件事件送回RD。F1/F2/F3完整L1 audit及5773条DATA_DEF_USE端点/key/属性相同。真实历史0.4.15的条件WRITE成因仍未知，本轮未重跑该文件。详见rubixi_residual_impact.json。

没有把缺边写成模型信息等价，L2缺少关系仍可能影响消息传播。未证明完整字段敏感storage alias语义，也没有把未解释事件强改为convention。

附加独立pickle读取被自动审批拒绝，理由是反序列化可能执行代码；该动作未重试或绕过，改用冻结JSON事实和图文件SHA。另一路此前完成的正式cli verify通过16图/20schema，日志独立保存，不用未执行动作冒充验收。

### 53.7 测试、不变量与绑定

- 新增84测试：alias17、bare16、category28、targeted14、shape9，全部通过。
- 全部v2：1159 passed，8条既有warning，60.97秒（进程61.66秒）。
- 旧DDG＋graph_utils：223 passed，29条既有warning，3.09秒（进程3.65秒）。
- 合计1382 passed、0 failed、0 skipped；warning仅既有DGL/distutils和NetworkX gpickle弃用。
- cli verify：4任务16图20记录schema通过，验证模型构造0、模型前向0、训练0。
- 写文档前原11211个跟踪文件SHA全部相同；最终只向3份文档追加，11208个其余旧文件不变，3份旧字节前缀不变。9个选定旧报告/seal输入SHA再核对；token/标签/折资产由原store/manifest验证器核验。
- 独立审阅与测试并非全数据逐条人工图边证明。原512/111人工边表未代填，原Oracle结果未改。

最终categories/validation.json及seal：
selection SHA 94e545c3a56c41b9fa1d3bc967af6b928c79a2c2edd5bd0126a801420255c678；
decisions SHA b40a967a0dd9d27b65c4c1dbc2fb75440d2f2a163357b4c7c2ea6637008e21a5；
categories SHA 247a2379a3d61a27f71edcfcaf3c1aa798d8f521345337c2b63ab11e3d0c20cd。

### 53.8 命令、产物与停止点

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

python -B -m scripts.DFG.dfg_v2.slither_category_audit validate \
  --selection scripts/DFG/experiments/artifacts/dfg_v2/prompt6d2_v1/categories/selection.json \
  --decisions scripts/DFG/experiments/artifacts/dfg_v2/prompt6d2_v1/categories/decisions.json \
  --categories scripts/DFG/experiments/artifacts/dfg_v2/prompt6d2_v1/categories/category_decisions.json
python -B -m scripts.DFG.dfg_v2.cli verify \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

实际生成命令：
slither_category_audit prepare --alignment <alignment_v4_r2/report.json> --output <O>/categories；
slither_alias_audit --alignment ... --output <O>/alias_identity_audit_r2；
slither_bare_audit --alignment ... --output <O>/bare_audit。
O即scripts/DFG/experiments/artifacts/dfg_v2/prompt6d2_v1。目录已经存在，生成器拒绝覆盖，不能原地重跑。

手写入口参数：--trusted-compilers <prompt6c_v1/trusted_compilers_complete.json> --output <新目录>；
两种受限retry另需--failed-report <原失败report.json>。实际批次为probes、probes_retry1、probes_shape_supplement、probes_shape_retry1。默认runner现在选择合法修正源，未来新批次不是原失败attempt的逐字重播。

新产物在O保留before快照、执行源、全部成功/失败报告、全事件审查、直方图、旧未决followup、两类impact、测试XML/log与final_acceptance。沿用仓库惯例：运行原件留WSL本地，代码/fixture/可读报告及三文档进入本地提交。

本轮停止，不开始6e/7/8、不训练、不push。下一步可基于同一graphs_v2_r1进入Prompt7接入；本轮没有声称已经实现或执行它。


## 54. 2026-10-26 Prompt 7：冻结图上的嵌套训练接入与显存门槛停止

修改AI：Codex。开始HEAD 44f714c，dfg-v2；用户要求读取更新Shared Context和Prompt7，方案替代必须先征求意见。已pull --ff-only确认已最新。以下为本轮详细实施记录，历史正文不变。

### 54.1 方案选择、范围和依赖

### 54.1. 先读后写：依赖与最小适配

|原依赖|不兼容点/核验结果|本轮处理|
|---|---|---|
|paper_run.py::fit_variant|paper train/val、CV validation评分、只审计DATA_DEF_USE|复制到experiment/trainer.py，头部记录源SHA；保留Adam/OneCycle/每轮单step/post-update eval/无权CE；切换三部分监督和全部v2关系审计|
|paper_runtime.Supervision|无v2辅助节点约束|复用已完成DfgV2Supervision，保留原HGT前向；env_source不监督、不池化、不输出预测|
|graph_schema_and_support|原reflect_graph，只有train/val|experiment/support.py用v2 materialize，按三个文件分区统计全部canonical|
|gradient_audit|只有DATA_DEF_USE|逐canonical统计四种正向及显式REV_*的msg/att梯度，训练有边与仅保留集有边分开|
|checkpoint.StopMonitor/save/restore/snapshot|通用ddg-controlled-v1适用；paper_checkpoint写死协议不适用|包装通用checkpoint，绑定协议/角色/图/标签/折/初值/schema/profile/reducer；不改原文件|
|model_validation.capture_model_input|env_source和REV_*可确定序列化；不会自行记录reducer|复用，补外部binding，测试特征/标签/字典/掩码/实际边不一致被拒绝|
|stage_f.initialize_pair|要求同节点类型及state_dict键，无法直接处理env_source|新initialize_family按节点名和canonical对齐；保存未经训练初值|
|RECON §5与历史task.json|合约、节点学习率不同|读取各任务已绑定config，不统一覆盖；constructor/fit种子规则保留并明确扩展seed公式|

源训练器文件SHA：babbc0fb0f3c040bcee1282973a01745d183a5fc47ffe650077d51daed20d3e0。
HGT源码、DDG分析器、tokenizer、原训练脚本、图、标签、折、旧plan/seal均不修改。

### 54.2. 用户明确批准的两处选择

1. 初始化要求存在“所有同名共同参数相等”与“新增行按各剖面整块Xavier范围”冲突。用户批准后者：**与G0共有参数逐张量完全一致**；新增关系使用独立语义随机数，按各自完整关系库的Xavier范围缩放。新增关系在两个增强剖面间可能不逐位相同，不能宣称完全相同。env_source同名参数仍可跨G3/G3R相同。初始化版本为dfg-v2-semantic-family-own-bank-v1，独立于协议版本。
2. 文档“仅8次训练”与CPU两次/GPU一次各3轮等价性检查冲突。用户批准三次短检查单列为数值验收、不计正式实验；先CPU等价性，再G3R显存门槛，再GPU历史对照及其余pilot。**显存门槛失败后停止全部后续GPU运行**。实际只完成两次CPU短检查，GPU历史对照未执行。

完整固定任务图前向会计算保留文件的表示；严格隔离的是监督行/目标/损失及选best。没有跨文件边，outer_test.targets/forward只在训练完成、last保存后调用。没有把全图前向伪称为只前向训练子图。

### 54.3. 新文件与实现

新增experiment/下：__init__.py、protocol.py、support.py、init.py、checkpoint.py、resources.py、trainer.py、run.py、equivalence.py、README.md。
新增tests/下：test_experiment_protocol.py、test_experiment_init.py、test_experiment_trainer.py、test_experiment_run.py、test_experiment_resources.py。

- run支持plan/execute/verify/select/summarize；仅合成测试API允许CPU，正式CLI固定CUDA。
- plan只读核验store，绑定代码、包版本、图/特征/标签/折、配置及逐任务未训练初值；不重采样。
- 单进程锁与单模型GPU执行；每个job恢复原fit seed。成功收据核验复用；失败保留完整attempt，显式--retry从同一初值重跑整次fit。
- verify检查实际checkpoint payload和sidecar、权重摘要、binding、best/last epoch，预测逐文件/原节点身份与冻结真值核对，再独立重算指标。不能仅检查CSV行数或指标自洽。
- select只读内层预测；summarize必须有封存selection。只有fold0/不完整候选的pilot不可触发补种子，不作F1改善结论。
- GPU显存0.5秒采样并在同步检查点核验；当前采样失败拒绝使用旧读数。资源检查不会降配或切CPU。

### 54.4. 冻结图、划分和初始化

最终store仍为graphs_v2_r1/store.json，SHA：
ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。
cli verify通过4任务、16图、20记录schema；该核验不构造HGT、不前向、不训练。6d.2有界残留和既有范围限制继续保留。

|任务|inner_train/inner_val/outer_test文件数|G0/G3R参数量|G0/G3R canonical数|G3R训练新增关系边数（含REV）|
|---|---|---|---|---:|
|重入合约|90/23/29|4,526,962 / 5,283,380|165 / 233|23,060|
|重入节点|50/13/8|4,371,010 / 5,111,012|146 / 212|16,040|
|访问控制合约|72/19/23|4,510,546 / 5,299,796|163 / 235|15,032|
|访问控制节点|40/11/6|4,428,466 / 5,217,716|153 / 225|12,070|

合约initial_lr/max_lr/div_factor/weight_decay = 0.0005/0.01/20/5e-6；
节点为0.0002/0.005/25/0。共同：OneCycle总50步、final_div_factor=1、cycle_momentum=true、最多50轮、patience7、delta0.001，strict-min inner loss best。完整有效配置在plan与prepared中。

种子：constructor=10000+fold+(合约1000)+100000*(seed-1)，fit=constructor+1000000。当前seed1。每组G0共有语义参数摘要相同，G0不被改写，独立新增参数不依赖家族构造顺序/候选子集。

### 54.5. 实际测试与数值对照

|检查|结果|
|---|---|
|新增初始化|25 passed|
|新增协议/支持|33 passed|
|新增训练器/checkpoint|37 passed|
|新增runner|14 passed|
|新增资源门槛|4 passed|
|全部v2|1272 passed，8条既有warning，118.64s|
|旧DDG + graph_utils|223 passed，29条既有warning，4.66s|
|总计|1495 passed，0 failed，0 skipped|

警告为已有DGL/distutils和NetworkX gpickle弃用提示。初始化初次fixture遗漏TREE_SITTER_LIB_DIR曾出现invalid ELF设置错误；使用现有已记录库路径后通过，未安装依赖/更换解析器。

合成20文件完成plan→execute（2轮CPU）→verify→select→summarize；包括拒绝select前summarize、成功复用、失败保留/显式重试、payload/标签/身份/输入篡改、三分区mask、辅助节点排除。node/contract小图原/新引擎3轮损失≤1e-6，最终权重逐位相同。

真实R合约fold0 CPU对照使用历史113/29 paper划分，两引擎同初值、同fit seed、50步调度仅运行3轮；**每轮train/val损失最大绝对差=0.0**。这是一项数值检查，不是nested实验结果。历史未训练初值文件SHA 2f5c51836a12499cc0884f15431c5f87240285039ccaf79c33910834414814fe，tensor SHA 43ea285456a411190eaeaa46cf9bc1a03b0e5a0345efcfbf0bcc2228fdd57504。CPU best/last重载logits逐位一致。

### 54.6. GPU探针及停止原因

独立plan有8个job：四任务fold0，G0/G3R，seed1。唯一启动：
reentrancy_contract/0/1/G3R。

- 完成epoch0（第1轮），history中的轮耗时23.5301秒。
- Resources监控区间56.2470秒，包含GPU搬移/检查点/同步与采样等，不能把它当每轮纯训练耗时。
- peak allocated：3299.8477 MiB；peak reserved：3536 MiB。
- 整卡最低空闲：**12 MiB**；76次采样，采样错误0。
- epoch0后同步检查触发MemoryGateError；未报告CUDA OOM，未自动改模型/图/训练配置。
- 保留partial best.pt/best.json、history、binding、监督清单、资源与failure/started记录。没有last.pt、完整result或成功receipt；不能使用该partial best作为正式成绩。
- 外部只读监控也观察到16 MiB；尝试发送SIGINT前进程已自动退出，未实际发送任何信号/关闭其他程序。随后显存已释放。
- 0/8成功fit，1个失败attempt，0次重试；其余7个未启动，GPU三轮历史对照未启动。
- 每新canonical的GPU第一轮梯度明细在原实现完成fit后写出；本次提前停止未持久化完整梯度审计，不能宣称GPU全部新关系已通过非零梯度验收。CPU小图梯度集成测试已通过。

因此本轮没有8次F1比较结论，也没有依据更新150次主矩阵的可靠耗时估算。

### 54.7. 待用户决定的资源方案

模板中的选择保留，但不能假定一定有效：
- 关闭不需要的GPU程序后，明确授权从同一初值重试失败fit。Codex不会关闭用户程序。
- allocator的max_split_size_mb选项需先核实该旧PyTorch版本支持。对本地1.8.1的五个CUDA/c10库只读检查，未检出该选项或PYTORCH_CUDA_ALLOC_CONF字符串；这不是完整支持性证明，不能承诺设环境变量就有效。本轮未设置/升级。
- 每job独立进程有助于释放跨job上下文；本探针已经在独立execute进程且只有一个fit，因此它不能单独解决首次探针的固有峰值。
- 更大显存的兼容GPU可保持模型配置；迁移环境仍需另行验收。
- 混合精度、降维、减少层数/删边/采样会改变模型或数值，不属于本轮自动补救。

Prompt 7尚未全部验收；未经用户选择，不重试、不开展Prompt 8。


### 54.9 命令、产物、原件及停止点

O = scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/。
其中before_tracked.json、store_verify.log、plan_acceptance.json、v2_tests/legacy_tests的log/XML、cpu_equivalence/、pilot/、gpu_probe.log、allocator_option_probe.json均保留在WSL。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

python -B -m scripts.DFG.dfg_v2.cli verify \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py

python -u -B -m scripts.DFG.dfg_v2.experiment.equivalence \
  --manifest scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/prepared/reentrancy_author_contract/fold_0/task.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/cpu_equivalence --device cpu

python -B -m scripts.DFG.dfg_v2.experiment.run plan \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --tasks reentrancy_contract,reentrancy_node,access_control_contract,access_control_node \
  --profiles G0,G3R --seeds 1 --folds 0 \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/pilot

python -u -B -m scripts.DFG.dfg_v2.experiment.run execute \
  --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/pilot/plan.json \
  --only reentrancy_contract/0/1/G3R
~~~

上述输出已存在，不可覆盖。未经用户决定不加--retry。正式verify会因8个job未完成而拒绝完整验收，这是正确行为；只读verify(require_complete=False)可汇报进度。

只向三份记录文档追加；原11233跟踪文件写文档前SHA均不变，最终核验另存。代码/README/本报告/三文档本地提交；运行原件不加入Git，不自动push。


本轮实际新增9个experiment Python文件（含空__init__）、README与5个测试文件；另新增PROMPT7_REPORT.md并追加三文档。语义分析/消息传递/数值训练规则未改变。CPU诊断成功和GPU失败不混计为8个正式结果；失败best不进入任何主统计。修复期的fixture环境错误、标签格式测试收紧与内部审查发现的预测/checkpoint验收缺口均在最终测试前解决，没有修改已封存图或旧模型代码。


## 55. 2026-10-26 Prompt 7b：共享投影接入与 CPU 数值验收（Codex）

本节详细记录实施、批准选择、失败证据与停止原因。

日期：2026-10-26。实施、审查、测试与记录 AI：Codex。
基线：`dfg-v2@60aa23e`；已读共享上下文与更新后的 Prompt 7b，执行 `git pull --ff-only origin dfg-v2` 确认最新。

### 1. 结论与停止位置

**共享投影代码接入及回归测试完成，但 CPU 数值验收未通过；Prompt 7b 尚未全部完成。GPU 对照、显存探针、8 次 pilot 和 Prompt 8 均未启动。**

四组 mean 对照的初始逐层输出和 logits 逐位一致，逐参数梯度通过用户批准的门槛；但三轮 train/inner-val 损失差都超过原定 1e-6。随后 R 合约 G0 的 nonempty_mean 虽前向逐位一致，一个 query 权重梯度超标，按门槛停止，未训练该组，也未运行最后一组。

实际完成的是 **8 次 CPU 三轮数值诊断 fit（4 对，24 epoch）**，不是要求的 8 次 GPU pilot。后者为 0/8。代码测试 1366 项 v2＋223 项旧 DDG/graph_utils＝1589 passed，0 失败/错误/跳过，其中新增94项；测试通过不等于真实数值验收通过。

### 2. 实际修改文件与理由

- `hgt_layer.py`：新增 `HGTLayerSharedProjection` 和 `HGTLayerSharedProjectionNonEmptyMean`。直接继承构造器；每层每种节点类型只计算一次 k/v/q，再在各 canonical 中复用。关系 einsum、attention、聚合、残差、dropout、norm 保持原顺序。源码结构对照测试约束除投影放置外的 forward。原 `sco_models/model_hgt.py` 不改。
- `model.py`：新增 `layer_impl=original|shared_projection`，默认仍为 original；校验字段与实际层类相符。参数名/形状、构造时 RNG 均保持并有测试。
- `experiment/init.py`：记录 layer_impl，拒绝不同实现混在同一个初始化家族；语义共同初值算法不变。
- `experiment/checkpoint.py`、`trainer.py`：绑定实现，拒绝跨实现恢复；新增配置检查和结果字段，Adam/OneCycle/早停/best 数值循环不改。
- `experiment/run.py`：新增计划参数 `--layer-impl`，写入 plan/config/job/prepared/initial/receipt；旧文件缺省字段仅解释为 original，不修改或重封历史产物。
- `experiment/projection_validation.py`：独立 CPU/GPU 数值验收入口。复用 trainer.fit、冻结初值和划分，记录逐参数误差，拒绝 NaN/Inf、轮号错误和相互矛盾的汇总；资源记录覆盖 setup/fit/异常/退出。GPU 路径本轮未执行。
- 新增3个测试文件：`test_shared_projection.py`、`test_layer_impl_binding.py`、`test_projection_validation.py`；更新 experiment/README.md、本报告及三份实施记录。

没有修改 DDG 语义、tokenizer、原 HGT、图/特征/标签/fold、模型超参数或冻结训练规则。共享投影的数学定义等价，不代表浮点反向或多轮优化轨迹逐位相等。

### 3. 用户批准的选择与原失败证据

1. 用户明确要求执行更新后的 Prompt 7b，因此按第1部分实现可选共享投影层，保留 original 与全部历史批次。
2. 文档未定义“最大相对梯度差”的分母。用户批准按每个参数张量计算 `max(abs(new-old))/max(max(abs(old)),max(abs(new)))`，并另外记录逐元素相对差。两边都为零时比值为零，不用人为的大 epsilon 隐藏差异。
3. 小图纯相对门槛出现16项失败、25项通过；失败参数为近零 key bias，绝对差约1e-10～1.9e-9。原日志保留在 `shared_projection_original_gate.log`。用户随后批准固定公式：

```text
max_abs_gradient_difference <= 1e-8 + 1e-5 * max(max_abs_old, max_abs_new)
```

真实数据开始前已冻结上述公式。前向仍须 torch.equal，CPU三轮损失门槛仍为1e-6，GPU对照为1e-4，整卡最低空闲显存为100 MiB。本轮没有因真实结果失败继续提高这些阈值。

### 4. 真实 CPU 验收结果

| 任务 | 剖面 | reducer | 三轮最大损失绝对差 | 结果 |
|---|---|---|---:|---|
| reentrancy_contract | G0 | mean | 2.92062759e-06 | 轨迹门槛失败 |
| reentrancy_contract | G3R | mean | 7.03334808e-06 | 轨迹门槛失败 |
| access_control_node | G0 | mean | 8.82148743e-06 | 轨迹门槛失败 |
| access_control_node | G3R | mean | 2.31862068e-05 | 轨迹门槛失败 |
| reentrancy_contract | G0 | nonempty_mean | — | 梯度门槛失败，未训练 |
| reentrancy_contract | G3R | nonempty_mean | — | 此前门槛失败，未执行 |


所有已执行的5组静态对照，逐层输出与最终 logits 都逐位一致。四组 mean 梯度通过；R/G0/nonempty_mean 的失败参数是 `gcs.0.q_linears.7.weight`：绝对差1.5931533425828093e-8，梯度尺度2.279119689774234e-5，允许差1.0227911968977424e-8，张量相对差0.0006990214。因此在静态阶段停止，不能声称“所有梯度通过”。

四组 mean 每边各跑3轮，保留50-step OneCycle、patience7/delta0.001、原任务学习率、固定 nested fold0 和 fit seed；每边都从同一冻结未训练初值启动。8次诊断均完成 best/last 保存及 CPU 重载，logits 逐位一致。未使用诊断 F1 选择模型或宣称改善。

首个 AC/G0 的初版静态检查覆盖全体节点两层输出及监督行 logits；后来补充全部7710个节点的最终 logits，仍逐位一致，见 `first_full_forward_check.json`。没有重训，也没有覆盖原失败记录。补充脚本第一次因 PYTHONPATH 缺失在导入时退出，保留日志，显式项目路径后成功。

首组之后只收紧验收脚本的非有限值、历史身份和异常资源校验，并扩大静态 logits 覆盖，不改模型与 fit 数值规则。四组 mean 均完整收集，未选择性丢弃失败；nonempty_mean 静态失败时停止其训练和最后一组。报告生成脚本曾有一次 Python 引号语法错误，未写入任何报告/历史文件；随后直接按最终 JSON 生成记录，不影响计算。

### 5. 已排查的原因与结论边界

AC/G0 的只读证据见 `ac_g0_diagnosis.json` 与可复跑脚本：初值 digest 都是 `d03020d8...cb83`；三分区监督清单、optimizer_schedule、最终 Adam 参数组/step、标准化 scheduler 一致。binding 只在 layer_impl 和对应 config digest 上不同。未发现错图、错初值、错标签、错划分或优化器配置混用。

首次 backward 最大梯度绝对差2.9802322387695312e-8；362个参数中20个依靠绝对容差项通过。第三轮后265个参数张量有差异，最大参数差8.354708552360535e-4，位于 `gcs.0.q_linears.7.weight`。共享投影改变反向累加顺序，近零梯度可改变相对大小或符号；Adam 的 eps=1e-8，可能放大这种差异。这与观测相符，但没有逐步梯度/参数轨迹，不能证明它是唯一原因。

初始前向一致不能推出多轮训练满足1e-6；预测类别暂未变化也不能替代门槛。不能把这些数字直接解释为 DDG 标签/构图错误，也不能宣布整个实现已经通过等价性验收。

模板背景中“不是 v2 关系本身的代价”表述过强：重复投影可以优化，但新增关系仍有关系变换、attention、中间张量和参数成本。本轮未测共享实现 GPU 峰值，不能承诺已解决4GB显存问题。此处只记录分析，不擅自更换设计。

### 6. 测试、不变量与未执行事项

- 新增94项通过；完整v2 1366 passed（8条既有警告）；旧 DDG/graph_utils 223 passed（29条既有警告）；合计1589，0失败/错误/跳过。警告为 DGL/distutils、NetworkX gpickle 等既有弃用项。完整日志/XML留存。
- 允许修改范围外11061个已跟踪文件摘要一致；三份文档旧正文保留，只追加。旧 Prompt7 plan/seal/失败 attempt 保留，不在旧 plan 上切换实现或 retry。
- 固定图 cli verify 通过：4任务、16图、20个已记录 schema/model-construction；本次 verify 不构造模型、不前向。最终图仍为 `graphs_v2_r1/store.json`，SHA `ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4`。
- 未执行：nonempty_mean 两组三轮轨迹、最后一组静态对照、AC节点GPU历史对照、GPU新旧实现对照、R合约G3R显存探针、8次pilot、Prompt8。新pilot plan未封存；没有新的GPU峰值、完整梯度验收或可靠的Prompt8 GPU耗时估计。
- 没有实施第二级端点投影、批次化、AMP、降维/删边、优化器修改、依赖升级，未关闭用户程序。

AC节点历史记录已核验存在：51 train/6 val、constructor10000/fit1010000、原HCG与未训练初值；不能用本轮 nested 40/11/6 去比较历史损失。相关诊断代码已准备，但未真实运行 GPU。

### 7. 实际命令与产物

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
python -B -m scripts.DFG.dfg_v2.cli verify \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json

python -u -B -m scripts.DFG.dfg_v2.experiment.projection_validation cpu-case \
  --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/pilot/plan.json \
  --task access_control_node --profile G0 --reducer mean \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7b_v1/cpu/access_control_node_G0_mean
```

上述输出已存在，不能覆盖；复查优先读取已有证据。其余实际 CPU 命令及顺序见 `run_cpu_remaining.py` 和日志，遇静态失败即停止。

产物：`scripts/DFG/experiments/artifacts/dfg_v2/prompt7b_v1/`。包含 cpu/、测试XML/log、批准选择、源码摘要、全输出补核、只读诊断、store_verify、final_acceptance。运行原件留 WSL，不写入 C 盘临时目录；代码和记录本地提交，不自动 push。

建议下一步先针对固定初值做一步梯度—Adam 更新追踪，定位数值分叉，再由用户决定保留严格门槛或修订新的验收协议。未经批准不改 eps、不调高损失阈值、不推进 GPU。本轮停止在 `implementation_tests_passed_cpu_numerical_gate_failed`。


## 56. 2026-10-26 Prompt 7b.1：float64严格门槛诊断与保留失败（Codex）

日期：2026-10-26。实施、复核、测试和记录 AI：Codex。
基线：dfg-v2@c079e3ac934111a8e1ac8777a46fd3d716e3eeec。已读取更新后的§4.1与Prompt 7b.1，执行git pull --ff-only origin dfg-v2，结果Already up to date。

### 1. 结论与停止位置

**新增float64验收工具和回归测试完成；本轮数值验收未通过，Prompt 7b.1整体未完成。**

DGL 0.6.1 CPU支持本轮要求的float64操作。正常实现的小图前向输出逐位一致；但严格的纯相对梯度门槛在数学梯度为零的key bias上失败。按照文档“任何一项不满足：停下报告，不放宽门槛”，正式预检在第一个mean/use_norm=True案例停止，未启动6组真实图、三轮float64训练、GPU噪声重复、GPU历史对照、显存探针、8次pilot或Prompt 8。

代码回归为1393 v2＋223旧DDG/graph_utils＝1616 passed，0失败/错误/跳过；其中新增27项是子集，不能重复相加。**这些测试确认验收工具正确拒绝失败，不表示原/新HGT通过了规定的数值门槛。**

### 2. 新建和修改文件

- 新建experiment/precision_validation.py：独立CPU-only float64小图预检；执行原始公式，不引入绝对容差、不跳过bias。记录全参数梯度、前向差、权重身份、环境与源码SHA；输出拒绝覆盖、首个失败停止。
- 新建tests/test_precision_validation.py：27项检查，覆盖阈值边界、非有限值、dtype/shape、None梯度、近零相对误差失败传播、漏关系负例、拒绝覆盖与停止顺序。
- 新建本报告；仅向PROGRESS.md、HANDOVER.md、docs/training_changes_2026-10-07.md追加记录。
- 没有修改hgt_layer.py、model.py、trainer.py、优化器、旧projection_validation.py、DDG、tokenizer、图、标签、fold、历史plan/seal/checkpoint。PROMPTS.md未改。

本轮没有替代方案的实施或新的阈值批准。故障注入只作用于隔离诊断图，生产模型不包含故障注入。

### 3. 严格公式与正式预检

前向：maxabs(new-old) <= 1e-12。
梯度：maxabs(new-old) / max(maxabs(old), 1e-30) <= 1e-10。
分母按文档的参考梯度old计算，不使用上一轮的双边尺度，不添加atol。
三轮轨迹1e-9门槛未修改，但本轮未进入该阶段。

小图固定seed114、CPU threads2、8维/2head、dropout=0；先构造float32权重再.double()，两份模型state_dict完全相同，特征float64。包括共享投影的多canonical、同关系名不同类型端点、空关系、纯源/纯目标类型；执行edge_softmax、v_dot_u、u_mul_e/sum与multi_update_all。无optimizer、无训练epoch。

| 正式mean/use_norm=True预检项目 | 数值 |
|---|---:|
| 各节点类型前向最大绝对差 | 0，torch.equal全部为true |
| 全参数最大梯度绝对差 | 1.5265566588595902e-16 |
| 唯一未通过的参数 | k_linears.0.bias |
| 该参数maxabs(Δg) | 2.7647155398380363e-18 |
| 该参数maxabs(g_original) | 2.076247160309741e-17 |
| 该参数maxabs(g_shared) | 1.7997756063259374e-17 |
| 严格相对差 | 0.13315926892950392 |
| 规定上限 | 1e-10 |
| 状态 | failed_static_gate |

独立小图单元测试还检查mean/no-norm和nonempty_mean近零bias被拒绝的真实行为；这不表示剩余真实图任务通过。主预检没有在失败后进入下一验收阶段。

### 4. 为什么不能据此判定模型实现错误

对同一canonical、目标节点和attention head，key线性层的bias经过关系矩阵后，对该目标所有入边的attention logit增加同一个常量。softmax满足softmax(z+c)=softmax(z)，因此这个bias的精确梯度为零。浮点相消留下约1e-17的残差；两份残差只差约1e-18，相除仍可得到0.13。double减小绝对误差，却不能保证相对于“应为零的数值残差”的比值趋于零。

模板中“任何float64门槛失败就说明不是舍入、而是实现问题”的推断过强。同样，小图前向一致和很小的绝对梯度差不足以证明全部真实图、训练轨迹或GPU行为正确。

本轮仍按原阈值判为失败，没有排除近零参数、没有因负例检出而宣布全部等价、没有把上一轮四组float32轨迹重新判为通过。

### 5. 人为漏关系负例与诊断测试修复

只在一次性诊断图的multi_update_all之前将指定canonical的v消息乘0。节点、关系列表和聚合槽位不变，模拟遗漏该关系消息贡献；退出作用域后恢复，原模型源码与初始权重不改。

| reducer | 最大前向差 | 未通过的非bias梯度张量数 |
|---|---:|---:|
| mean | 0.06951759444847261 | 9 |
| nonempty_mean | 0.10319109526590353 | 9 |

两组均同时被前向和梯度门槛拒绝，证明可检出这一指定的逻辑缺陷，不能据此推断能检测所有错误。

最初故障注入直接移除multi_update_all中的关系，造成nonempty_mean的stack槽位与mask不一致；首次新测试23 passed、1 failed，日志保留。修正仅限诊断注入：保留槽位并抑制消息。关键断言未改、未删、未xfail，最终27 passed。第一次正式小图失败也保留；最终工具另建small_preflight_final记录相同严格失败，不覆盖历史。

### 6. 后续真实图接入约束（本轮未实施）

只读复核发现，未来float64诊断需要显式处理以下问题，不能关闭原校验：

1. 冻结图token为NumPy float32数组；model.double()不会转换DGL inp。model.py和原model_validation.py仍检查它与冻结token的dtype和值完全一致。
2. 原节点/合约forward的hiddens使用未指定dtype的torch.zeros，诊断须保证中间dtype一致，退出后恢复环境。
3. trainer校验初值tensor digest；转换后的float64 digest不能冒用原float32初值，须同时保留冻结源身份与诊断转换身份。
4. 文档提到的experiment/equivalence.py当前只允许重入合约；访问控制节点已有历史核对入口是projection_validation.py::run_gpu_diagnostic。

本轮未改这些接口，未转换真实图token，未生成新的float64训练初值。后续适配需要先确认，不能弱化生产输入绑定。

### 7. 测试、身份与未执行项目

- 新测试：27 passed，4条既有DGL/distutils弃用警告，5.60s。
- 全v2：1393 passed，8条既有DGL/NetworkX弃用警告，93.01s。
- 旧DDG/graph_utils：223 passed，29条既有弃用警告，3.42s。
- 11251个旧跟踪文件（三份可追加文档除外）SHA一致；上一轮prompt7b_v1的164文件SHA一致；三份文档旧正文仅追加。
- graphs_v2_r1/store.json SHA仍为ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。本轮没有重构图或重跑全图验收，摘要检查不等于新的图语义证明。
- 新增optimizer fit=0、真实图float64案例=0、GPU运行=0、pilot完成=0/8。没有新显存峰值、GPU噪声值、训练耗时估计或F1比较。
- P7b旧失败未覆盖/重新改为通过；P7旧失败attempt未重试。本轮不启动Prompt8，不自动push。

### 8. 命令和产物

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

# 原首轮命令；目录已存在，复跑需指定新的空目录。
# 预期退出码1代表严格验收失败，不是训练成功。
python -u -B -m scripts.DFG.dfg_v2.experiment.precision_validation --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7b1_v1/small_preflight

python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_precision_validation.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

产物：scripts/DFG/experiments/artifacts/dfg_v2/prompt7b1_v1/。
包含small_preflight及small_preflight_final、fault_injection.json、small_probe初次失败和最终测试日志/XML、v2/legacy日志/XML、冻结文件及旧产物摘要、final_acceptance.json。
最终主预检acceptance SHA：dd10f2c786164961110ec27ac17751ae6223257d982991ef963868a2b1a22e1b。
故障注入证据SHA：7b9f97b6c76e75ed5ed9af85cf719e3666f917c0585f3d75deb930d33e1126b0。
运行产物保存在现有WSL工作树，未转存C盘。

### 9. 尚待用户决定的建议

建议事先固定float64混合绝对/相对误差规则，例如maxabs(Δg)<=1e-12+1e-10×maxabs(g_original)，保留全部参数原始纯相对误差和漏关系负例。**仅为建议，本轮未采用。** 再为真实图设计隔离、可审计的dtype转换，不改生产特征、模型或训练算法。确认后仍需完成六组真实图与GPU对照，才能决定是否推进8次pilot。

停止状态：strict_float64_small_gate_failed_tests_passed；不能称Prompt 7b.1全部完成。


## 57. 2026-10-26：Prompt 7b.2 全局梯度判据、真实float64诊断与CPU资源停止

实施、复核与记录AI：Codex。工作树ge-sc-llm-ddg-v11，dfg-v2，开始HEAD=a2957d6；先读更新§4.1/P7b.2、pull --ff-only已最新。本节只追加；详细数值/命令见scripts/DFG/dfg_v2/PROMPT7B2_REPORT.md。

### 57.1 授权选择与不变项

用户本轮模板直接授权G=maxabs(所有参考梯度)，逐张量门槛1e-12*G+1e-10*maxabs(g_ref)，参考近零者候选也须<=1e-12*G；纯相对差只报告。前向1e-12/轨迹1e-9不变。PROGRESS运行前已登记，不事后放宽、不排除bias。
隔离float64循环已获模板授权：生产float32构造/校验→深拷贝无损拓宽→双摘要；默认dtype正常/异常恢复。两种实现共用循环，结论不等于生产trainer的float64兼容认证。
既有HGT/model/trainer/model_validation/优化器/DDG/token、所有旧.py、图/标签/折及计划/产物不改。没有另行替换用户方案。

### 57.2 新文件与实现

新增experiment/precision_gate.py、precision_real.py、precision_gpu.py及三个对应test；新增报告，三文档追加。
gate保留旧raw判定并独立重算，缺失/非有限/异常拒绝，G=0/阈值边界有测试。
real绑定冻结初值/图/标签/split/seed/config；权重/DGL inp转换，NX token不变；逐层完整输出/梯度、监督行、RNG一致性核验。循环沿用Adam/OneCycle50step、train后eval inner_val；3epoch，无生产checkpoint/outer监督。
gpu需六CPU案例清单+seal并独立重算证据/源码/input绑定；GPU噪声门槛固定，最低100MiB/低于300提醒。pilot仍委托原fit与receipt。
审查发现noise汇总曾只信任checkpoint roundtrip标记，未查实际权重。已补best/last .pt及sidecar/model_input SHA/格式/绑定/epoch，13项篡改/缺失测试；这是新验收器纠错，不改训练。真实GPU未执行，CPU证据绑定源码未变化。

### 57.3 数值执行

小图旧strict失败保留，新判据通过（G=24.020718399476486），两个漏消息负例仍拒绝。
六静态最大梯度差依次R/G0 mean5.03142e-17、R/G3R mean1.00088e-16、AC/G0 mean1.69510e-16、AC/G3R mean5.55112e-17、R/G0 nonempty4.22853e-16、R/G3R nonempty1.24700e-16。所有层/logits逐位一致，diff/tolerance最高0.000253323，双端近零不一致0；12次静态forward/backward、0optimizer。
R/G0 mean原/共享3epoch各一次成功，train差0、val最高1.5543122344752192e-15；循环约68.88/26.20s不含构造，不作性能基准。
26身份核验后，原float32→64三轮最高差1.4534227625873086e-6；旧float32配对差2.9206275939941406e-6仍保留。不能以单例宣布全部GPU等价。

### 57.4 零梯度清单与额外取证

近零张量76/74/82/81/76/74，不只是key bias。逐项静态清单含拓扑/监督路径；不能仅据拓扑解释者标observed numerical zero。
完成3次no-grad前向：R/G0先按边、再按不同源；AC/G0一次。R额外14=4单源不变+10初始饱和，AC额外22=4单源+18饱和；非胜出源权重最高2.41e-13/1.20e-27。饱和近零非恒零。
AC/G3R取证约22.48s后按内存提醒主动终止，保留日志。其余4案例额外项动态解释未完，不能套用G0结论。取证0backward/0step，初值不变，与训练分开计数；zero_audit保存脚本/证据/attempt_inventory/resource_stop。

### 57.5 停止原因与未执行

轨迹R/G0 mean成功后，R/G3R mean在original执行期间-9；内核2026-10-26 04:43:42明确OOM killer，anon-rss7595332KiB≈7.24GiB；WSL7865MiB RAM+2048MiBswap。这是CPU内存，不是CUDA或数值失败。
original.json没写出，具体完成epoch无持久化证据不臆报，shared未开始；其他4对未启动。partial trajectory.json保留running现场，resource_failure.json绑定其SHA和coordinator/kernel证据，最终状态明确失败。
共2完整诊断fit/6完成epoch、1中断fit；无六案例CPU成功seal，无GPU/显存探针，0/8pilot，无新pilot plan/150fit耗时估算。按失败即停不跳过案例、不自动重试。
短暂WSL服务0x8007274c在释放内存后恢复；未重启/改WSL/关闭用户程序。宿主约16GiB，故障后free约4.14GiB，增加WSL资源须先确认Windows余量及用户授权。

### 57.6 测试、产物与历史保护

最终新138通过/4warning（gate53/real32/gpu53），全部v2 1531通过/8warning，旧DDG+graph_utils223通过/29warning；总1754，0失败/跳过，不重复加新138。warning均既有DGL distutils/NetworkX read_gpickle弃用。
命令：python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests；同命令路径scripts/DFG/tests tests/test_graph_utils.py。完整argv、XML/log见O/test_commands.json与*_tests_final.*；中间日志保留。
11,254旧非三文档跟踪文件、184旧7b/7b.1产物、固定store34引用SHA不变；16图/20schema不变。store SHA=ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4；三文档旧前缀单独核验。
O=scripts/DFG/experiments/artifacts/dfg_v2/prompt7b2_v1，运行原件留WSL。新代码/文档本地commit，未自动push，旧未跟踪产物不提交。

### 57.7 后续门槛

状态implementation_tests_passed_static_numeric_passed_cpu_trajectory_resource_stopped，非整体验收完成。
先确认资源方案并获用户同意，在新attempt重跑失败完整对/未执行案例，不覆盖旧证据、不叫epoch续训；四组额外近零解释待补。之后才CPU acceptance→GPU noise/history→显存探针→8pilot。本轮未放宽阈值、改hidden/layers/图、降精度或绕过原实现。


## 58. 2026-10-26：Prompt 7b.3 收窄CPU轨迹、完成GPU数值验收及pilot资源停止

实施、复核、记录AI：Codex。工作树ge-sc-llm-ddg-v11，dfg-v2，开始HEAD=07a0846。阅读更新§4.1／7b.3，pull --ff-only已最新。详细数值、命令、限制见scripts/DFG/dfg_v2/PROMPT7B3_REPORT.md。本节只追加，不改历史正文。

### 58.1 授权选择、审查与冻结范围

用户更新模板在执行前已授权：复用六静态及R/G0mean成功轨迹；只补AC/G0mean、AC/G3Rmean、R/G0nonempty三对；每2秒采RSS，>6.5GiB主动终止、记skipped_cpu_memory、不重试；R/G3R两reducer明确不运行；额外维度AC/G3R或R/G0nonempty至少一项完成。PROGRESS先登记，再执行，没有根据结果追加放宽。
数值门槛沿用7b.2：float64轨迹1e-9，GPU max(1e-4,3×original重复差)，历史重放1e-4，显存最低100MiB／低于300提醒。
没有替换文档方案，未另行扩大支持范围。审查只收紧证据：外部SIGKILL不可伪装成主动RSS跳过、实际数值失败优先保留、同名参数跨关系结构证明要覆盖全部相关关系、有限案例不能声称普遍数学证明。更新模板的近零说明不作为新的数值门槛。
hgt_layer.py、model.py、trainer.py、model_validation.py、sco_models／旧DDG、tokenizer、优化器和scheduler、图／标签／fold／旧计划/初始化/产物不变。未调整WSL内存、swap或系统设置。

### 58.2 文件与实现

新增experiment/precision_guard.py：仅允许三规定case，stdlib父进程＋独立precision_real子进程，绑定argv/cwd/输入/源码，启动前记录MemAvailable与swap，2秒采RSS，超限SIGTERM、10秒不退出再SIGKILL，保留采样与stdout/stderr。原始数值或执行失败不可转为skip；return -9仅当确有主动SIGKILL升级才可资源跳过。外部内核kill、监测错误按失败处理。实际仅SIGTERM，未强杀其他程序。
新增experiment/precision_policy.py：schema=prompt7b3-cpu-release-v1；新CPU清单及seal独立存放。重验六组raw静态、冻plan/seal/prepared/config/split/初值/sourcehash、成功轨迹raw输出；两策略skip区分prior_oom与not_run，无伪造argv/RSS；三受监护组必须有完整guard；缺失／非规定跳过／实际失败／覆盖不足拒绝。
precision_gpu.py仅新增6行新schema分派，旧无schema清单保持六静态＋六轨迹严格门槛；未知schema拒绝。
新增experiment/precision_zero.py：冻结NX／物化边、节点排序、canonical字典、训练可达路径与旧static SHA校验；没有模型构造、forward/backward/optimizer。共享k/q参数b类需全部相关关系满足单不同来源；c限末层目标q/a/norm，不误扩展到源k/v或全部env参数。
新增三个对应测试44／48／38=130项。新增PROMPT7B3_REPORT.md，本节与HANDOVER／PROGRESS追加，运行证据只写新prompt7b3_v1。

### 58.3 CPU执行与回退

AC节点G0mean原/共享各3轮成功，train/val最大差1.1102230246251565e-16，采样峰值RSS4.105278GiB。
AC节点G3Rmean原/共享各3轮成功，最大差2.5868196473766147e-14，RSS5.849632GiB。
R合约G0nonempty在58.07秒采样RSS6.953140GiB，超过6.5，脚本SIGTERM，return -15。总58.737s，未得到完整轨迹对，原partial保留，guard明确终止；非内核OOM／非数值失败，不重试。2秒采样不是严格硬内存配额，存在采样间超过阈值后被检测的余量。
本轮CPU完整fit4／12epoch、部分fit1；旧R/G0mean2fit只读复用；R/G3Rmean旧OOM失败保留，nonempty未尝试。新清单六行：成功3（含复用），内存策略/采样跳过3；通过AC/G3R覆盖条件，不能写成六轨迹全通过。
静态近零463个跨case张量观测：a198、b180、c18、d67。d只数值近零，可能初始饱和但未新增证明；旧动态证据原样引用。解释的是监督梯度，weight decay仍可能更新；不是463个独立实验。

### 58.4 GPU数值与历史重放

AC节点fold0，G0/G3R各original_1、original_2、shared三轮。两剖面original重复差均0，shared对两次原实现最大差分别7.62939453125e-6、3.5762786865234375e-7，门槛均1e-4，通过。
另1次GPU原实现历史paper配置与51/6划分重放，三轮train/val与历史逐项差0；该诊断不与nested划分混用，不称独立测试。
共7完整GPU诊断fit／21epoch，非pilot。重新核验原始history、seal/文件SHA、binding、配置、best/last磁盘文件与重载；gpu_execution.jsonl逐调用记argv/返回码/耗时。
G0原两次allocated920.462MiB／reserved1004，最低free999；shared561.415／608，free1367。
G3R原两次allocated1459.798／reserved1594，free413／407；shared850.383／946，free869。
历史重放free966。计时包含构造/设备转移/训练/评分/重载，不当作kernel性能对比。

### 58.5 新pilot计划与资源停止

独立pilot/plan.json、plan.seal.json封存8项（四任务、G0/G3R、fold0、seed1、shared_projection）。原fixed store16图/20schema检查通过；8组实际tensor_digest与旧Prompt7未训练初值相同，optimizer_steps=0、原fit_seed、图/支持/config/split一致，仅layer_impl标识不同；详情pilot_initial_alignment.json。
先执行reentrancy_contract/0/1/G3R，最多50epoch、原Adam/OneCycle/earlystop/best规则不变。第1轮训练与inner_val完成，存best，trainer.py:136资源check抛MemoryGateError：minimum_free66MiB<100。allocated1824.08642578125MiB、reserved2048、64采样无错误，资源计时44.327s。无CUDAOOM。
旧Prompt7原实现同case历史探针allocated3299.84765625、reserved3536、free12保留。共享投影峰值分配降低约1475.76MiB／44.72%，但整卡资源门槛仍不满足；外部/驱动占用不同，不能将整卡差异全部归因于这一实现。
只完成1个epoch，partial best、binding、model_input、history保留；无last/result/成功receipt。首轮gradient_history未到最终落盘，不推断完整canonical审计已通过。pilot_matrix_verification=0/8完成，其余7未启动，无自动retry／换CPU／降维／改图／关闭其他程序。
七次GPU诊断重载通过与未完成的pilot大图重载分开。没有本批可比较的完整F1，不做漏洞效果结论；150次Prompt8按任务时长估算缺完整fit，不从一轮外推，明确待办。

### 58.6 验证、不变量与记录

新130项包含于v2全量1661通过/8warning/97.44s；旧DDG+graph_utils223通过/29warning/3.09s，共1884，0失败/pytest跳过。warning为既有DGL distutils／NetworkX gpickle弃用，不改变依赖。定向中间测试日志保留。
命令：
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
实际命令/JUnit/log在prompt7b3_v1，CPUguard与GPUexecution记录完整argv。新代码在全量测试后冻结，没有为了GPU结果修改规则。
11264旧跟踪文件只允许三文档和precision_gpu.py变化，其余SHA相同；246旧诊断产物相同；固定store SHA ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4，三文档旧前缀保留。新运行产物留现有WSL，未删除历史数据。
final_acceptance状态cpu_policy_gpu_numeric_passed_pilot_memory_stopped；probe_stop_evidence绑定失败文件，完整矩阵明确未验收。按共享上下文本地commit，不自动push。

### 58.7 未执行与下一步边界

本轮到显存门槛即停：不运行剩余7pilot、不开始Prompt8／150次、多seed、其他五类或新关系/模型。
下一步需用户选择资源方案再显式新attempt。从同一未训练初值重跑，不称epoch续训。可评估非必要Windows GPU占用、单独授权allocator设置、或更大显存设备；本轮已经独立进程串行，不能再以此作为尚未做的优化。reserved−allocated约224MiB不是保证可回收量。不擅自混合精度/改维度/采样，不能以测试通过宣称资源问题已解决。


## 59. 2026-10-26：Prompt 7b.4 显存基线、归属澄清及新探针停止

实施、审查、记录AI：Codex。开始54f21b5，按更新模板pull --ff-only到c97d737，分支dfg-v2。先读§4.1及7b.4。完整报告scripts/DFG/dfg_v2/PROMPT7B4_REPORT.md；本节只追加，不覆盖旧数值验收或失败记录。

### 59.1 用户批准的选择及原假设纠正

用户明确同意：（1）原“进程外占用”更名为“PyTorch分配器之外的未归属占用估计”；原公式保留，另记基线、context前后值和近时间配对读数；（2）新策略每次--only一项、单独进程，外部串行调度；无策略的旧计划行为不变。先写PROGRESS/HANDOVER登记，再运行。
原因：旧resources缺少total，4096来自独立查询；peak reserved/min free不一定同时。P7b3前置used464/free3512与“首次任务前已经2GiB外部占用”不符。本进程CUDA/DGL/driver/lazy library不在Torch allocator内，也能进入差额。不得把本轮context1292倒扣旧记录或断言其他程序是唯一原因。
本轮只读WSL nvidia-smi没有计算进程；Windows另列dwm/Code/chrome等专用显存计数，不能跨计数口径求和。未替用户关闭程序，未修改驱动/系统设置。total-used-free=120MiB原样保留。

### 59.2 修改文件与实现逻辑

新增experiment/preflight.py：stdlib单GPU查询UUID/total/used/free并核验有限值；检查本进程CUDA未初始化；基线低于登记值写preflight_blocked并停止，查询异常写preflight_error并停止，不创建训练attempt。不成功时不偷偷降阈值。
初始化使用确定性1元素Torch CUDA tensor和1节点1边DGL CUDA graph，无RNG/HGT算术；同步释放并empty_cache后记录context差值。仅是阶段观测，不保证之后所有CUDA库都已初始化。
通过继承冻结Resources记录raw samples、allocator当前值、时间窗口、两种未归属残差；原0.5秒等待和100MiB合作式检查保留。summary锁避免采样线程与hash/count不一致，记录实际UUID并拒绝换设备。

新增experiment/resource_plan.py：--from-plan只读旧seal/plan/prepared/实际initial；_initial逐个核验optimizer_steps=0、task/fold/profile/fit_seed及tensor摘要。新计划仅runtime/git_head/resource_policy/resource_origin四个字段不同；只允许run.py及两个新资源模块在runtime变动，原计算变化即拒绝。不生成新初值，不创建新模型。
修改experiment/run.py最小接入：新plan强制--only；成功attempt核验复用；低基线记录独立于fit attempt；真正训练失败仍须显式--retry。preflight对象与磁盘收据、当前PID/job/plan/policy一致；context在构造CPU模型前落盘。成功/失败resources都带preflight、context、策略与PID。新增校验raw sample SHA/count/index/min/peak/公式和context身份，不接受错绑收据。
新增tests/test_preflight.py（41），test_resource_plan.py与test_preflight_integration.py（共23）；合计64。新报告及三份追加记录。HGT/shared层、model/trainer/resources原文件、DDG、tokenizer、图/标签/fold、优化器/学习率/早停一律未改。

### 59.3 新计划、输入与实际运行

新产物O=scripts/DFG/experiments/artifacts/dfg_v2/prompt7b4_v1，拒绝覆盖；旧P7b3 plan/seal/失败现场保留。
新pilot plan SHA e0ff577cd73f7fa1da841cf2f1fdd1e890ebc2ede27ac047cf369ff2db5c8344，8项与旧P7b3相同、shared_projection、fold0/seed1、原max50/每任务config。直接引用旧8份initial实际文件，source_plan_comparison逐项记录，不是重新初始化后只比较种子。
baseline_minimum_free_mib=3000，running_minimum_free_mib=100；旧图仍graphs_v2_r1/store.json SHA ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。协议仍dfg-v2-nested-v1；inner_val选best，outer_test只计划最终评分，不混用paper_kfold。

先跑R合约G3R：baseline total4096/used450/free3526，通过3000。CUDA/DGL最小初始化后used1742/free2234，变化1292，Torch allocated/reserved均0。
训练peak allocated1824.08642578125/reserved2048，整卡minimum free76<100；60个采样、0错误，配对查询窗口0.202–0.378秒。原公式残差1972，减context观测后680；其中仍含基线570（used450+读数差120）及约110阶段差异，不将680全部叫其他程序。
退出后读4096/473/3503MiB。结合原始前后证据，更支持大量开销随本训练进程初始化和退出变化；不声称精确逐进程归属。

完成epoch0/显示第1轮，train_loss0.7187948226928711、inner_val_loss0.6839135885238647，epoch19.17s；guard42.999s，完整子进程119.563s。记录首轮学习率0.0005000000000000004与原OneCycle/Adam快照。失败为MemoryGateError，不是CUDAOOM。
partial best和sidecar保留；无last/result/成功receipt。梯度明细仅在正常结束后落盘，故首轮新canonical梯度验收本轮未完成；best/last重载及最终预测检查同样未完成，不用旧诊断通过代替。
pilot清点0/8成功、1失败、7未启动、0重试；严格完整矩阵verify应报错，另用require_complete=False如实清点，不把0/8叫验收通过。

### 59.4 历史公式重算与证据

O/historical_accounting.json绑定9份旧resources与旧启动查询。total统一参考独立4096设备记录，旧文件均无total字段。
原P7 R/G3R：3536reserved/12free/548残差；P7b3 AC G0 original两次1004/999/2093、shared608/1367/2121；AC G3R original1594/413/2089及1594/407/2095、shared946/869/2281；history1004/966/2126；R G3R shared2048/66/1982。
原算术可以重现，但不能据此判定多出1.5GiB一定来自其他程序，更不能保证清理后剩1.5GiB余量。本轮没有继续数值诊断或第二级模型优化。

### 59.5 测试与不变量

最终新增64通过/4warning；全v2 1725通过/8warning（114.45s），旧DDG+graph_utils223通过/29warning（3.50s）；总1948、0失败/跳过，64包含在1725中。警告为既有DGL distutils和NetworkX gpickle弃用，没有升级依赖。
实际argv、返回码、JUnit与日志在O/test_commands.jsonl、targeted_tests/v2_tests/legacy_tests.*。
11,271旧跟踪文件仅run.py和三文档可变化；538旧P7系列产物SHA保持；三文档原始字节前缀保留；原HGT/DDG/token/训练数学、store图与seal不改。源码hash在建plan后冻结，未因结果调整实现。
原始产物保留现有WSL（E盘承载），没有清理旧文件，没有向C盘写大模型日志。本地只提交本轮源码/测试/四份文档，产物不自动入Git、不自动push。

### 59.6 实际命令与后续边界

环境沿用mando/Python3.7、OMP/MKL2和原TREE_SITTER_LIB_DIR。详细可复制多行命令见PROMPT7B4_REPORT.md。
计划：python -B -m scripts.DFG.dfg_v2.experiment.run plan --from-plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7b3_v1/pilot/plan.json --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7b4_v1/pilot --baseline-min-free-mib 3000。
首项：python -B -m scripts.DFG.dfg_v2.experiment.run execute --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7b4_v1/pilot/plan.json --only reentrancy_contract/0/1/G3R。
测试：python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests；旧路径scripts/DFG/tests tests/test_graph_utils.py；三个新测试另先定向执行。

用户明确最终完整实验在显存充足服务器运行；当前4GiB只是本地限制。服务器设备/环境尚待实际核验，不能改写旧环境绑定来静默兼容。此轮不降门槛、不--retry、不续跑7项、不做150fit时长估算、不启动Prompt8/七类/新seed/第二级k-v改造。建议下一步准备服务器的环境/路径/输入初值身份核验，再继续独立验收；不为本地资源继续扩大数学改动。


## 60. 2026-10-26：Prompt 7c 本地资源策略与8项完整pilot（修改AI：Codex）

起点3aac85f3243abf60b884e023a57c8010c897ccc7，dfg-v2；先读共享§4.1及更新§4.9g。报告scripts/DFG/dfg_v2/PROMPT7C_REPORT.md；新产物prompt7c_v1，旧计划、失败和封存文件不改。

### 60.1 用户批准、范围选择及事实限定

用户本轮明确回复：“暂时不考虑服务器，当前实验只是在本机，就是之前配置”，以及“同意按 local_dev_v1 完成本地 8 次 pilot（推荐）”。对应完整记录在新批次local_policy_approval.json，SHA绑定进新plan；不是把无回复当成授权。
开始时读取的Prompt7c还是服务器迁移版本；同步到3aac85f后第4.9g已经改成本地8次pilot，按新文档和用户回复执行。服务器迁移推迟到第4.9h，没有新增迁移或环境安装功能。
对模板背景说明作事实限定：不同时刻的peak reserved与另一轮context差值相加超过4096MiB，不能证明已发生换出；本轮不改旧文字或伪造证据。possible_memory_spill只是时长启发式，checkpoint写盘、初始化、CPU/磁盘负载等同样可导致变慢。第一轮能跑完也不是后续一定不会OOM的保证。
实施细节：提醒基线固定为前三轮，检查从第4轮开始；resource_policy保留running_minimum_free_mib=100字段，版本明确决定其是硬门槛还是提醒。新计划额外变化的git_head/resource_origin是来源登记，训练计算不变。

### 60.2 文件修改、逻辑与原因

- 新增 experiment/local_dev.py：继承现有资源观察器；只将运行期低空闲判定改为提醒。直接读取冻结trainer原有history.jsonl，每轮seconds及连续epoch身份必须有效。前3轮中位数固定，从第4轮开始严格超过2倍才标possible_memory_spill。少于3轮明确不足以形成基线。
- 修改 experiment/preflight.py：独立注册local_dev_v1；启动≥3000MiB，运行100MiB字段在新版本中为提醒阈值。旧DEFAULT策略和默认行为保持。工厂仅显式新策略时创建LocalResources。
- 修改 experiment/resource_plan.py：新增prompt7c-local-resource-plan-v1来源协议；P7c→P7b4→P7b3逐层只读验证。绑定用户批准JSON、旧plan/seal与8项身份；逐一核验旧initial文件SHA/tensor digest/optimizer_steps=0/fit_seed。仅允许资源编排相关5个运行文件变化。
- 修改 experiment/run.py：新增--resource-policy local_dev_v1及--approval-record；向资源观察器传policy/history，result和receipt绑定提醒标志，验收从原采样与history独立重算。失败任务阻止新进程跳过后继续批次，只能用户确认后显式--retry同一任务，从原未训练初值开始。
- 修改 experiment/precision_gpu.py：audit_pilot_result只在显式传入新策略时切换资源验收。新canonical梯度、heldout支持及checkpoint逐位重载要求不变，默认调用仍保留旧100MiB门槛。
- 新增tests/test_local_dev.py；追加test_resource_plan.py和test_preflight_integration.py。覆盖低显存继续/旧策略停止、基线、OOM保留与批次停止、时长突增、篡改证据拒绝、成功复用、初值/来源不一致拒绝等。
- 本轮未修改hgt_layer.py、model.py、experiment/trainer.py、experiment/resources.py、原sco_models、DDG分析器、图/标签/token/fold或任何训练数值规则。

### 60.3 实际冻结计划和参数

沿用dfg-v2-nested-v1，不是此前paper_kfold。完整固定任务图前向；inner_train监督更新参数，inner_val早停并按严格最低loss保存best，结束后才计算outer_test。外层标签不参与训练或选择，但由于全图特征/拓扑参与前向，不能称完全归纳的未知图测试。节点按原HCG节点计分，env_source不参与监督/池化评分/预测输出。
实际配置从原plan逐项继承：shared_projection、mean聚合、hidden128、2层、8头、dropout0.2、inside_token、seed1/fold0、Adam/OneCycle、每轮一次step、最多50轮、patience7、delta0.001。合约initial/max LR=0.0005/0.01、weight_decay=5e-6；节点=0.0002/0.005、weight_decay=0。没有统一误填学习率，不使用smoke或上次partial best起跑。
plan SHA 363814c88c3dd9e22aa61a9bf6e2f5ee5f59b7dfc7262d6685e671e287aa94e5；直接来源P7b4 plan SHA e0ff577cd73f7fa1da841cf2f1fdd1e890ebc2ede27ac047cf369ff2db5c8344；祖先P7b3仍只读。新plan只变化runtime/git_head/resource_policy/resource_origin，比较文件绑定进seal链。原8份initial逐一验证optimizer_steps=0/fit_seed/tensor摘要，沿用同一路径，不仅比较seed。
图store SHA ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。protected原模型、DDG、tokenizer、数据、标签、fold、训练数学不动。

### 60.4 8次实际运行与验收证据

| 任务/剖面 | best/last轮 | 启动free | peak allocated/reserved | 最低free | 进程秒 |
| --- | --- | --- | --- | --- | --- |
| 重入合约/G0 | 8/15 | 3725 | 1229.7/1484 | 707 | 448.75 |
| 重入合约/G3R | 8/15 | 3538 | 1893.5/2148 | 81 | 415.64 |
| 重入节点/G0 | 17/24 | 3712 | 807.8/1002 | 1189 | 382.70 |
| 重入节点/G3R | 18/25 | 3709 | 1258.0/1494 | 662 | 455.54 |
| 访问控制合约/G0 | 9/16 | 3645 | 919.6/1118 | 976 | 316.81 |
| 访问控制合约/G3R | 9/16 | 3607 | 1401.1/1610 | 478 | 344.87 |
| 访问控制节点/G0 | 13/20 | 3611 | 561.4/640 | 1447 | 210.46 |
| 访问控制节点/G3R | 16/23 | 3601 | 850.4/946 | 1049 | 288.45 |

表显存MiB、轮次1起算；raw epoch仍0起算。8/8完成、0失败/重试；总进程耗时2863.21s。只有R合约G3R memory_tight=true（min81），8项possible_memory_spill均false，0采样错误/非有限/OOM。context前后差1284–1297MiB，不等于精确外部占用。
8项都从未训练初值开始，独立进程--only串行，先R合约G3R验收再其余7。best仍按严格最低inner_val loss选择；last保留停止时最后一轮，二者规则不变。全部checkpoint两评分角色重载logits逐位一致，env_source排除与原节点/文件/标签身份通过正式验收。

| G3R任务 | 训练支持canonical | 仅留出canonical | 非零训练梯度 | best/last重载 |
| --- | --- | --- | --- | --- |
| 重入合约 | 66 | 2 | 全部通过 | 全部逐位一致 |
| 重入节点 | 62 | 4 | 全部通过 | 全部逐位一致 |
| 访问控制合约 | 68 | 4 | 全部通过 | 全部逐位一致 |
| 访问控制节点 | 70 | 2 | 全部通过 | 全部逐位一致 |

四个G3R训练支持66/68/62/70，合计266个任务canonical检查非零；仅留出2/4/4/2共12个，监督梯度0。G0无新增relation。逐轮history、raw样本、preflight/context、resources、gradient_audit、binding、initialization_ref、checkpoint、预测、receipt完整保留。
对会话中断只核对后台状态，确认后台已完成8项，未重复启动。完整matrix JSON和逐项acceptance保存；再次CLI verify核验完整矩阵。

### 60.5 时长估算与限制

| 任务 | G0秒 | G1R估计秒 | G2R估计秒 | G3R秒 | G3估计秒 | 全折小时 |
| --- | --- | --- | --- | --- | --- | --- |
| 重入合约 | 448.75 | 428.30 | 420.51 | 415.64 | 432.19 | 2.98 |
| 重入节点 | 382.70 | 429.05 | 446.71 | 455.54 | 419.12 | 5.93 |
| 访问控制合约 | 316.81 | 333.96 | 340.97 | 344.87 | 330.84 | 2.32 |
| 访问控制节点 | 210.46 | 258.12 | 277.62 | 288.45 | 249.45 | 3.57 |

阶段A60fit约5.83h，阶段B90fit约8.95h，合计150fit约14.79h。中间3profile按canonical数在G0/G3R进程walltime线性插值，再乘任务折数；20个schema计数均复核。原公式及每项估计在prompt8_time_estimate.json。未扣除已跑8项，不自动假定可复用。
进程walltime含启动/fit/子进程验收，不含父验收；guard时间另存。单折早停/写盘/负载差异使估计不确定，不能用G3R总耗时更短证明计算优化。不作8pilot F1比较结论，不报告显著性或泛化证明。

### 60.6 测试、不变量、文档与存储

定向184 passed/4条既有warning；全v2 1792 passed/8条warning（112.49s）；旧DDG+graph_utils 223 passed/29条warning（3.13s）。合计2015通过，0失败/跳过；新增67项包含于1792，不重复相加。warning为DGL distutils及NetworkX gpickle弃用，未升级依赖。开发阶段新增篡改测试有3个fixture setup错误，修复为finally恢复共享合成fixture，未删除或放宽断言；最终上述三组均通过。
实际测试argv/返回码/耗时、日志及JUnit均在新批次。没有重新运行已验收的float64/CPU/GPU数值等价性短实验，也没有额外smoke。
11,277原跟踪文件、582旧P7产物与三文档前缀核验，最终invariants.json。hgt_layer/model/trainer/resources/sco_models不变。新增local_dev代码及测试在dfg_v2，其余原代码不改。
新PROMPT7C_REPORT、HANDOVER/PROGRESS及本节追加；不覆盖旧文。所有运行产物留现有WSL（E盘），没有清理历史/下载或C盘大型写入。源码/测试/报告按文档本地commit，不自动push。

### 60.7 实际命令与停止点

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64

# 已执行：目录存在时plan会拒绝覆盖
python -B -m scripts.DFG.dfg_v2.experiment.run plan --from-plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7b4_v1/pilot/plan.json --resource-policy local_dev_v1 --approval-record scripts/DFG/experiments/artifacts/dfg_v2/prompt7c_v1/local_policy_approval.json --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7c_v1/pilot

# 已执行8次：每次替换为execution_order.json中的一个身份，独立进程串行
python -B -m scripts.DFG.dfg_v2.experiment.run execute --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7c_v1/pilot/plan.json --only reentrancy_contract/0/1/G3R

# 现在可运行的只读完整验收
python -B -m scripts.DFG.dfg_v2.experiment.run verify --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7c_v1/pilot/plan.json

python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_local_dev.py scripts/DFG/dfg_v2/tests/test_preflight.py scripts/DFG/dfg_v2/tests/test_precision_gpu.py scripts/DFG/dfg_v2/tests/test_resource_plan.py scripts/DFG/dfg_v2/tests/test_preflight_integration.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

仅完成本轮8个fold0 pilot，不报告F1比较结论，不据此认定DFG有效或无效。完整5/10折、额外seed、其他五类、Prompt8、服务器迁移均未运行。时长估计不是启动授权。
最终正式实验将按用户计划放到显存充足的服务器；目前4GiB是本机开发限制。具体服务器型号、依赖兼容性及资源尚未实测，不能把计划当作验收通过。当前按用户最新选择留本机完成pilot，下一阶段仍等用户确认。
后台采样偶发错误的旧行为未扩展：同步check采样失败立即停止，后台瞬时错误写sampling_errors；本轮8项均为0。命令中断后只读核对确认后台已完整跑完，未重启或重复任何fit。




## 61. 2026-10-26：Prompt 8 完整实验准备、分阶段控制器与统计（修改AI：Codex）

起点4f537d9cb35952201fc70338a0091b930e782ab8，分支dfg-v2；先读共享4.1和更新4.10。报告scripts/DFG/dfg_v2/PROMPT8_REPORT.md，新产物prompt8_v1/batch1。本节只追加，旧正文和产物保持。

### 61.1 实际状态

已完成Prompt 8计划、分阶段调度、统计、报告及必要接入。150项CPU准备：已完成并封存（准备2172.81秒，未执行fit）；plan SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de；seal SHA 55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8；实际初值验收 150/150份通过，30个完整家族，零优化步数、实际tensor摘要、各剖面与G0共同语义参数逐值相等；独立验收20.82秒。
正式训练0/150：阶段A 0/60，阶段B 0/90。本轮批准是准备计划，阶段A仍需用户审阅具体计划、磁盘和排期后确认；阶段B还需A中间报告后的确认。未读取或报告pilot F1作为本轮实验依据。旧run verify为前置完整性验收会内部重算指标，但不将pilot分数用于选型。

### 61.2 用户批准的调整

- “同意新增独立批次授权记录（推荐）”：Prompt 7c批准只绑定旧8项pilot。旧批准不改，作为local_dev_v1历史依据；新batch_authorization.json绑定本轮请求、150项及A/B，authorized_scope=prepare_batch1_150_only、execution_authorized=false。不会扩大旧批准的作用范围。
- “同意按实际统计条件报告（推荐）”：合约5折只作描述；0.0625只指通常非零差值精确双侧检验的下限，不适用于所有zsplit近似情形。节点仍双侧Wilcoxon、zsplit，A报告原始p，B四项vs G0齐全后再Holm。

训练、标签、主要终点和G*选择规则均未改变。没有未经批准的新模型设计。

### 61.3 修改文件和实现

新增experiment/batch_plan.py、batch.py、stats.py、reporting.py及四个对应test文件；experiment/run.py最小接入新计划/授权/完整汇总，experiment/README.md追加命令。
batch_plan冻结150项、A/B顺序、输入SHA、原fold、实际config、initial、初始化版本、主要终点、统计/敏感性规范及批准；已有目录拒绝覆盖。pilot只提供checkpoint/initial文件大小和既有耗时，不提供选型依据。
batch每项独立子进程，单GPU串行，顺序任务→折→剖面，同折配对相邻。成功结果完整verify后可复用。失败或中断即使只产生preflight/started、没有fit目录，仍锁住批次，不能跳过。新批准绑定失败job和证据SHA后，显式--retry从原未训练初值重跑，非epoch恢复、非新seed。
stats纯函数提供折均值/样本标准差、配对差、Wilcoxon、A12、10000次seed0配对bootstrap及四比较Holm；多seed先平均折，本轮仅seed1。
reporting独立核对file/source SHA/node identity与冻结标签，重算指标及OOF；完整报告独立复算inner选择；输出排他创建并记录SHA。best和last分开，env_source不计分。
集成发现并修复两项接口错误：verify_stage返回job/attempt/result/audit包装，interim仅提取result传reporting；真实调用链测试修复前失败、之后通过。run summarize必须先识别正式批次再进入完整reporting，避免旧pilot摘要分支；同样补真实接口回归。未削弱结果校验。
未改DDG分析器、HGT/hgt_layer、model、trainer、tokenizer、原训练脚本、图/标签/token/fold或训练数学。

### 61.4 矩阵、协议与初始化

| 任务 | K | A: G0/G3R | B: G1R/G2R/G3 | 总数 |
| --- | --- | --- | --- | --- |
| reentrancy_contract | 5 | 10 | 15 | 25 |
| reentrancy_node | 10 | 20 | 30 | 50 |
| access_control_contract | 5 | 10 | 15 | 25 |
| access_control_node | 10 | 20 | 30 | 50 |
| 合计 | 30任务折 | 60 | 90 | 150 |

G0=原作者固定HCG；G1R=标量依赖双向；G2R再加状态读写/REV；G3R再加ENV_FLOW/REV及env_source；G3为全部正向关系的方向消融。REV只在模型输入阶段生成。
所有剖面shared_projection、mean、inside_token、seed1。graph store SHA ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。各任务原config逐项继承，不统一误填学习率。Adam/OneCycle、每轮一次step、最多50、patience7、delta0.001保持。
协议dfg-v2-nested-v1：inner_train更新，inner_val早停及严格最低loss选择best，训练结束后评估outer_test；last辅助。完整固定图参与前向，所以不是完全归纳的新图测试；G0也不能直接与旧paper_kfold或original层历史F1对比。
节点按原HCG节点计分，不是源码行去重指标；env_source不进入监督、池化目标和预测。
150份initial全部新生成且optimizer_steps=0，不用pilot、smoke或best/last。沿用已批准语义初始化：与G0共有参数逐值一致；新增关系语义种子一致，但按各profile自己的Xavier范围缩放，同名新增关系跨profile未必数值完全相同。未改此算法。

### 61.5 资源、磁盘和停止

A约5.83h，B约8.95h，共14.79h。中间三个剖面按canonical数在P7c G0/G3R耗时之间插值；早停、负载、写盘和稀疏结构导致不确定性，这是排期而非保证。150项全部新fit，不扣8pilot。
磁盘实数：checkpoint 23.42 GiB、初值估计2.93 GiB、总计26.35 GiB，两倍门槛52.70 GiB；准备时WSL内部空闲825.96 GiB。Windows CIM另核验承载盘E实际空闲248.15 GiB，WSL注册路径E:/Smartcontract/Ubuntu-22.04；两种容量口径分开，均通过。生成的初值实际2.73 GiB。逐任务取pilot G0/G3R实际best+last及initial最大字节，乘fit数量；准备前空闲至少是二者总估计2倍。余量用于JSON/日志/预测/临时写盘，不覆盖无限重试。CPU准备记录MemAvailable和5模型序列化权重上界；上界不含图/复制tensor/allocator，不等于RAM实测峰值。
RTX3050 4GiB，local_dev_v1启动free≥3000MiB；运行<100MiB仅memory_tight提醒；后续轮次>前三轮中位数2倍仅possible_memory_spill提示，不证明paging。OOM、非有限值、采样/验收错误仍停止；不自动缩图、降维、改超参、换CPU或关闭程序。
A报告后停止，用户确认才B；不因成绩好坏换折或改规则。失败保留，确认后整fit重试，不自动无限重试。

### 61.6 预登记统计与选择

主终点每任务best outer-test Buggy-F1的G3R−G0。A中间REPORT_INTERIM_A.md固定对比G3R/G0，不选G*，报告SHA写批次收据。
完整B后G*只读取inner_val best预测：各任务折均值后四任务等权；候选G1R/G2R/G3R/G3；与最优差<0.1pp按更少canonical、再profile名决定。所选G*−G0内层均值绝对差≥0.2pp仅记录补seed条件，不自动训练。完整报告必须有selection seal且独立复算一致，外层不参与选择。
按任务报告best/last、折均值±样本SD、配对提升/持平/下降、差值95%bootstrap、A12、原始及Holm p。G3R−G3方向消融单列。折共享训练数据，不能当独立seed；不将大量节点当独立试验。
pooled OOF与等权折均值分开，多seed各自列OOF，不复制样本充当额外独立数据。主结果始终不改标签、不删困难文件。
敏感性集合预登记六个category/file/source SHA：R buggy_18、buggy_36、0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol；AC buggy_18、buggy_26、parity_wallet_bug_2。来自targeted_label_review_v1五文件与模板R buggy_36并集。同名文件不跨类别混淆；另列排除结果。若过滤后某fold空，明确完整K折均值不可用，不静默删折。
机制统计按实际消息方向、每个新增canonical，计算含该关系的≤1/≤2边路径终点中纠错/新增错误节点数；REV独立，env可为中间点但不计分。A用固定G3R，完整B用inner选的G*。只描述关联，不证明语义因果；关系参数、聚合和优化轨迹也变化。
review_v1/review_v1b仍空白，精确率写“未完成”。不把空白当正确，不再开启全面标签修改。

### 61.7 验证与限制

最终定向175通过（含在v2中）、全部v2 1967通过、旧DDG+graph_utils223通过，合计2190，0失败/跳过；警告依次4/8/29，为既有DGL distutils与NetworkX gpickle弃用。未升级依赖。命令、日志、JUnit、返回码在prompt8_v1/*_final.*。
前置store及P7c完整verify通过。新统计报告只经合成数据与真实调用接口测试，尚无本轮真实训练结果；未新增GPU smoke/等价性训练。
旧11280跟踪文件、817历史产物及三文档前缀最终核验：通过（原文件只允许run.py、experiment/README.md与三份记录文档改变；817个历史产物SHA及三文档原字节前缀不变），结果保存invariants.json。新产物在E盘承载WSL，未删旧文件、未向C盘写大模型。
最终实验按用户计划在显存充足服务器进行；4GiB是本机开发限制。尚未服务器部署/验收；迁移整批重新绑定/训练，不混本机成绩。
未执行A/B正式训练、聚合诊断、补seed、其他五类、服务器迁移、Prompt9。测试通过不代表DDG增益、完整Solidity语义或泛化已证明。

### 61.8 命令与后续

完整准备命令见experiment/README.md；包含旧资源批准ref、新batch_authorization、report_spec及全150矩阵，输出prompt8_v1/batch1。现有目录拒绝覆盖。
阶段A命令（未执行，需实际新批准）：
~~~bash
python -u -B -m scripts.DFG.dfg_v2.experiment.batch execute --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage A --authorization-record <APPROVED_STAGE_A_JSON>
python -B -m scripts.DFG.dfg_v2.experiment.batch verify --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage A
python -B -m scripts.DFG.dfg_v2.experiment.batch interim --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage A
~~~
B完成后才run verify→run select→run summarize。当前完整run verify应报告训练矩阵未完成，不修改验收以伪造通过。
其他五类未来按EXTENDING.md：注册类别→锚点/token核验→封存fold→cli build→run plan(G0与R/AC内层选定G*)。不在新类别重新择优；当前不执行。
本轮停止于代码验收、真实计划准备及排期交付，等A确认；本地commit，不自动push。

详细实施补充：所有正式job的资源/数值/图特征标签/schema/initial校验继续调用原run和冻结trainer；新batch只负责串行进程、授权闩锁、成功复用、失败停止及报告分发。reporting不接受内层预测冒充outer、不按CSV行位置配对、不接受sourceSHA不同的同名文件，完整selection独立复算。测试记录包括interim包装接口修复前失败证据以及完整summarize真实接口验收。报告表格不挑有利fold/checkpoint，合约与节点、重入与访问控制分别展示。新增Python仅dfg_v2内4模块及4测试；原已有Python改动仅experiment/run.py，README和3交接/记录文档追加。参数、代码、初值在封存后不得根据结果改变。


实际配置补充：hidden=128、layers=2、heads=8、512维inside_token输入保持；合约initial/max LR=0.0005/0.01、weight_decay=5e-6；节点initial/max LR=0.0002/0.005、weight_decay=0。新计划只继承逐任务配置，不统一覆盖学习率。
全部150份初值、30份家族绑定和关系train/inner_val/outer_test支持量已验收/导出：prepared_acceptance.json与prepared_relation_support.csv。本轮未执行新的反向传播、正式梯度审计、best/last checkpoint重载或实际外层F1；这些须每个真实fit完成后再验收。
计划以起点HEAD加runtime逐文件SHA绑定本轮计算，随后仅追加文档并本地提交；提交哈希变化不等于计算文件变化，最终再次核对runtime。150份initial与plan/seal等运行产物留WSL，不把模型大文件自动加入Git。


## 62. 2026-10-26：Prompt 8A 阶段 A 执行启动与冻结验收（修改AI：Codex）

实施、审查与记录AI：Codex。本节为执行中记录；只登记已经完成的启动前验证、实际授权和已启动的执行流程，不将其写成60项训练完成或已经证明DDG增益。最终执行数量、成功/失败、统计与报告SHA将在结束或真实阻断后另行追加。

### 62.1 需求、代码起点与允许范围

用户要求读取更新后的PROMPTS.md §4.1共享上下文和Prompt 8A，基于现有实现执行阶段A；合理替代方案须先说明并征求同意，改变须留痕。还要求交接明确最终实验在显存充足服务器运行，目前只是本机资源限制。
按要求pull同步，运行起点为dfg-v2@6dd5d986bf6fa1fade1bc8b247a9fd3035712385。此次复用已完成的Prompt8控制器、训练器、验收与报告，不修改任何生产Python代码，也不改DDG、HGT、shared_projection层、tokenizer、图、标签、折、初始化算法、优化器、学习率、早停或best选择规则。
新增一次性辅助核验与进度脚本、启动收据和测试记录只放scripts/DFG/experiments/artifacts/dfg_v2/prompt8a_v1；正式fit仍按旧计划指定目录落盘，避免迁移或覆盖历史批次。

### 62.2 阶段 A 授权与计划身份

用户本轮要求执行Prompt8A的原文及时间已排他写入scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/stage_A_authorization.json。该文件绑定原plan/seal、60个A任务的精确身份与顺序、local_dev_v1；execution_authorized=true、stage_B_authorized=false。同时保留现有授权验证器要求的version、approved、plan ref、authorized_jobs、user_answer、recorded_at字段。没有改旧batch_authorization.json，旧准备授权也没有被当作新的执行授权。
原plan SHA：07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de。
原seal SHA：55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8。
整个计划仍150项；本轮只执行其中A的60项G0/G3R，B的90项G1R/G2R/G3仍未授权。每个任务沿原文件K折与seed1运行，合约5折、节点10折，不挑折、不更换seed、不复用旧pilot训练成绩。

### 62.3 已完成的前置检查与命令口径适配

已完成cli图store verify，固定输入仍为graphs_v2_r1/store.json；计划与runtime逐文件摘要一致。前置完整清点时正式结果为0/150，A60/B90。
Prompt8A写“batch verify应报告0/150”，但现有batch verify必须指定stage且要求该阶段全部完成；run verify的CLI也没有allow-incomplete参数。采用已有API run.verify(plan_path, require_complete=False)执行启动前只读清点，只输出任务总数/完成数等结构字段。最终仍必须执行batch verify --stage A通过60项，不修改验证器、不降低最终验收门槛，也不伪造CLI参数。
重新读取150份实际已保存untrained_initial，校验文件SHA、tensor digest、task/fold/profile、fit_seed与optimizer_steps=0；30个五剖面家族的G0共有节点类型和canonical语义参数逐值一致。没有重新随机初始化；新增关系仍保留既有各profile自身Xavier范围规则。
证据：prompt8a_v1/preflight_acceptance.json、authorization_acceptance.json、store_verify.command.json及对应日志。前置验收耗时约27.27秒，仅为核验，不是模型训练。

### 62.4 接入回归与资源条件

沿mando环境执行既有定向及全量回归，无依赖升级：

~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_batch.py scripts/DFG/dfg_v2/tests/test_batch_plan.py scripts/DFG/dfg_v2/tests/test_reporting.py scripts/DFG/dfg_v2/tests/test_stats.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

定向175通过，包含于全v2的1967项；旧DDG/graph_utils223项通过，独立计数合计2190，失败/错误/跳过均0。日志、命令JSON、JUnit及test_acceptance.json位于prompt8a_v1；没有用合成测试成绩代替正式实验。
启动前Windows E盘实际空闲264104554496字节；WSL虚拟盘空闲883910905856字节，二者分开记录，不能用虚拟盘容量替代宿主E盘空间。GPU启动前free3524MiB，通过local_dev_v1的3000MiB要求。资源事实保存在host_disk_preflight.json及前置收据。
产物继续放现有E盘承载的WSL，不向C盘写入新的大型模型产物，不清理或删除旧实验。

### 62.5 已启动流程、进度读取和异常边界

现有batch控制器按计划顺序，每项独立子进程串行执行A；不同时加载/训练多个模型。正式命令为：

~~~bash
python -u -B -m scripts.DFG.dfg_v2.experiment.batch execute --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage A --authorization-record scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/stage_A_authorization.json
~~~

本节追加时训练已启动且仍执行中；故不写容易过时的已完成数量或任何F1。运行辅助脚本execute_stage.py保留命令/开始/退出证据，progress_only.py仅展示任务、epoch、耗时及memory_tight/possible_memory_spill等资源字段。
冻结trainer本来会在子进程文件日志/history中写inner-val指标；此次不改trainer日志行为。为遵守60项验收完成前不看成绩的要求，不直接展示或tail完整训练日志，不打开/汇总F1，不据结果改变执行。控制器内部固定完整性验证包含指标重算，这用于核验身份一致性，并非选型或提前比较。
资源策略继续local_dev_v1：启动前free≥3000MiB；运行free<100MiB仅记录memory_tight与耗时线索，不能据此断言显存换出。OOM、非有限loss、输入/数值/校验错误立即停止整批，保留attempt与失败证据，不自动重试；显式失败重跑必须另经用户确认，仍从原未训练初值开始，不称epoch续训。
成功任务由原验证器检查绑定、best/last文件与tensor摘要、原节点/文件预测身份、env_source排除、训练结束时逐位checkpoint重载证据、首轮训练支持新增canonical的非零消息梯度。heldout-only关系保留并按无训练支持审计，不删除折或关系。

### 62.6 结束验收与报告边界（尚待执行完成）

只有A全部60项成功且batch verify --stage A通过后，才运行batch interim --stage A生成REPORT_INTERIM_A.md与CSV，并将报告文件SHA写入批次收据。该报告固定比较G3R与G0，best为主、last独立辅助，合约/节点与两类别分别报告；不执行B、不计算G*。
沿用dfg-v2-nested-v1：inner_train监督，inner_val早停并选strict-min best，训练结束才评分outer_test；全固定图参与前向，不能写成完全归纳测试，也不与旧paper_kfold混写。节点口径保持原HCG节点，env_source不计分。
统计仍按预登记规则：等权折均值与样本标准差、逐折配对差/改善持平下降、配对bootstrap区间、A12；节点原始Wilcoxon zsplit p，5折合约只描述；四项Holm校正等B完整后再算。pooled OOF与折均值分开，争议文件敏感性表保持冻结身份，机制1/2跳只描述关联。
耗时说明：当前result.seconds覆盖fit中的训练、验证、checkpoint保存/重载和预测导出，并非纯forward/backward时间；独立子进程墙钟与控制器开销另记。测试通过、启动成功或梯度非零都不等于DDG一定提升。
用户要求最终实验在显存充足服务器整批重跑；RTX3050 4GiB只是当前本机限制。服务器尚未实际部署/验收，后续仍需核验环境与输入/初值身份，不混用本地与服务器成绩。当前不部署服务器、不启动更多seed/其他五类/新关系/额外模型训练。


### 62.7 2026-10-27：阶段 A 实际完成与结束验收（Codex）

前述执行中记录保留；本节更新实际结束事实，不回写启动时状态。60项正式G0/G3R均成功：重入合约10、重入节点20、访问控制合约10、访问控制节点20；0失败、0重试、全部attempt_001。没有重跑旧pilot成绩，没有跳过下降/持平fold。B未执行，全部150任务中本轮已完成60、其余90仍待另行授权。
stage_A_execute.command.json、stage_A_verify.command.json和stage_A_interim.command.json退出码均0。独立batch verify --stage A通过后才阅读完整F1并生成中间报告；执行期只看进度与资源，没有据分数改变训练。
原plan SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de和seal SHA 55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8保持，起点dfg-v2@6dd5d986bf6fa1fade1bc8b247a9fd3035712385；本轮生产代码零修改，新增辅助脚本和核验文件仍在prompt8a_v1。原150初值、30家族、frozen graph/features/labels/folds和runtime逐文件身份沿旧计划验证。
全部60fit的best/last文件摘要、tensor摘要、binding/schema/config/initial、预测原节点或文件身份、env_source排除、训练结束时两角色best/last逐位重载证据通过。新增canonical共有2080条任务折级审计记录，其中1986条inner_train_edges>0的首轮relation_msg梯度非零，94条仅在留出部分出现的关系梯度0且保留；该数量不是2080种唯一关系，也不是所有DDG语义已被证明正确。
本轮回归2190项独立测试通过：v2 1967、旧DDG/graph_utils223；定向175是v2子集，不重复相加。失败/错误/跳过均0，旧弃用warning未通过升级依赖消除。没有新增生产逻辑或改变测试断言来追求成绩。

### 62.8 实际四任务结果：best为主、last辅助

单位均为百分数；每任务独立等权折均值±样本标准差。dfg-v2-nested-v1沿用inner_train监督、inner_val早停和最低val loss选best、训练结束才评分outer_test。完整固定任务图仍参与前向，因此不能把本轮称为完全归纳未见图评估，也不使用旧paper_kfold的CV validation名称或直接对比其历史数字。节点口径为原HCG节点，env_source不计分，未改成文件＋源码行去重指标。

best主表：

| 任务 | 剖面 | Buggy-F1 | Macro-F1 | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| 重入合约 | G0 | 92.7326 ± 5.4566 | 92.9185 ± 4.9304 | 94.6429 ± 5.3571 | 91.8095 ± 10.9285 |
| 重入合约 | G3R | 94.1612 ± 6.3579 | 94.3471 ± 5.8561 | 96.0714 ± 5.7031 | 93.2381 ± 11.5490 |
| 重入节点 | G0 | 96.4276 ± 6.5918 | 96.5833 ± 6.2102 | 94.8838 ± 10.7762 | 98.7007 ± 1.6415 |
| 重入节点 | G3R | 96.9344 ± 6.6127 | 97.1078 ± 6.2497 | 95.2233 ± 10.8731 | 99.3820 ± 0.5444 |
| 访问控制合约 | G0 | 94.6066 ± 1.6532 | 94.7247 ± 1.9229 | 98.3333 ± 3.7268 | 91.2121 ± 0.4149 |
| 访问控制合约 | G3R | 95.4075 ± 3.2189 | 95.5599 ± 3.2156 | 98.1818 ± 4.0656 | 92.8788 ± 3.9944 |
| 访问控制节点 | G0 | 96.1753 ± 6.2062 | 96.9674 ± 4.6915 | 94.9521 ± 10.7185 | 98.1252 ± 2.0006 |
| 访问控制节点 | G3R | 95.9716 ± 6.1255 | 96.8294 ± 4.6304 | 95.0941 ± 10.7852 | 97.5893 ± 2.1300 |

last辅助表：

| 任务 | 剖面 | Buggy-F1 | Macro-F1 | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| 重入合约 | G0 | 92.1620 ± 3.0510 | 92.2508 ± 2.9311 | 93.1429 ± 4.7213 | 91.7143 ± 7.2422 |
| 重入合约 | G3R | 95.7037 ± 4.7257 | 95.7701 ± 4.5528 | 97.5000 ± 5.5902 | 94.5714 ± 8.7131 |
| 重入节点 | G0 | 97.0827 ± 6.6227 | 97.1932 ± 6.2630 | 95.6442 ± 10.9093 | 99.2563 ± 0.8098 |
| 重入节点 | G3R | 97.1568 ± 6.4290 | 97.2679 ± 6.0542 | 95.6345 ± 10.6607 | 99.3890 ± 0.6033 |
| 访问控制合约 | G0 | 86.6580 ± 6.9124 | 86.7857 ± 7.5300 | 89.5152 ± 9.0475 | 84.2424 ± 7.0132 |
| 访问控制合约 | G3R | 84.9255 ± 5.7693 | 85.0532 ± 6.5443 | 87.8485 ± 9.3157 | 82.5758 ± 5.6692 |
| 访问控制节点 | G0 | 93.9087 ± 5.7938 | 95.1391 ± 4.3016 | 93.7821 ± 10.2900 | 95.0205 ± 6.1706 |
| 访问控制节点 | G3R | 94.7086 ± 5.9949 | 95.6912 ± 4.5592 | 93.5437 ± 10.8126 | 96.7570 ± 3.9015 |

best配对方向与差值：

| 任务 | G0 Buggy-F1 | G3R Buggy-F1 | G3R−G0（pp） | 提升/持平/下降折 |
| --- | --- | --- | --- | --- |
| 重入合约 | 92.7326 ± 5.4566 | 94.1612 ± 6.3579 | +1.4286 | 1/4/0 |
| 重入节点 | 96.4276 ± 6.5918 | 96.9344 ± 6.6127 | +0.5068 | 10/0/0 |
| 访问控制合约 | 94.6066 ± 1.6532 | 95.4075 ± 3.2189 | +0.8009 | 1/3/1 |
| 访问控制节点 | 96.1753 ± 6.2062 | 95.9716 ± 6.1255 | -0.2037 | 2/5/3 |

last配对方向与差值：

| 任务 | G0 Buggy-F1 | G3R Buggy-F1 | G3R−G0（pp） | 提升/持平/下降折 |
| --- | --- | --- | --- | --- |
| 重入合约 | 92.1620 ± 3.0510 | 95.7037 ± 4.7257 | +3.5417 | 3/1/1 |
| 重入节点 | 97.0827 ± 6.6227 | 97.1568 ± 6.4290 | +0.0741 | 8/0/2 |
| 访问控制合约 | 86.6580 ± 6.9124 | 84.9255 ± 5.7693 | -1.7325 | 0/3/2 |
| 访问控制节点 | 93.9087 ± 5.7938 | 94.7086 ± 5.9949 | +0.7999 | 3/2/5 |

best统计（G3R−G0）：

| 任务 | best ΔBF1均值±样本SD（pp） | 95%配对bootstrap区间（pp） | A12 | 原始p |
| --- | --- | --- | --- | --- |
| 重入合约 | +1.4286 ± 3.1944 | [0.0000, 4.2857] | 0.6000 | 不作检验 |
| 重入节点 | +0.5068 ± 0.5033 | [0.2515, 0.8416] | 0.6400 | 0.001953125 |
| 访问控制合约 | +0.8009 ± 4.6092 | [-2.5974, 5.0000] | 0.5800 | 不作检验 |
| 访问控制节点 | -0.2037 ± 0.7030 | [-0.6734, 0.0950] | 0.4650 | 0.605576616 |

重入节点best的10/10折改善，均值+0.506835pp，95%配对折bootstrap区间[0.251500,0.841574]，原始Wilcoxon p=0.001953125。last只+0.074054pp、8升2降、p=0.322265625；这说明checkpoint口径会影响观察到的增益大小，不能用较有利者替换预登记best。
重入合约best仅1升4平，+1.428571pp来自fold2；访问控制合约best为1升3平1降，均值+0.800866pp，区间包含0。访问控制节点best为2升5平3降、−0.203717pp，p=0.6055766163；last虽+0.799890pp，但3升2平5降且p=1.0。当前证据支持“重入节点best在本固定seed/folds上有方向一致的小幅收益”，不支持“两个漏洞、两种粒度全部稳定改善”。
合约5折不做推断性p检验；节点为双侧zsplit，含零差值时保存库给出的近似/警告。Holm四项比较家族尚未完整，继续pending_full_family；本轮原始p不宣称已通过多重校正。bootstrap按配对折10000次seed0；折共享训练数据，区间/SD是描述性，不是独立seed不确定性。A12为两组折分数交叉比较，不是提升折比例。
pooled OOF、冻结争议文件敏感性、逐文件错误/概率变化及方向正确的1/2跳机制分解均保存在原报告和对应CSV。主结果没有删困难文件或改标签。机制覆盖仅描述关联；新增参数、聚合和优化轨迹也改变，不能把全部分差解释为纯依赖语义贡献。

### 62.9 实测耗时、显存及重复完整性核验成本

控制器execute墙钟33548.077秒（9.319h）；60项result.seconds合计16202.666秒（4.501h），后者包括fit内部验证、checkpoint保存/重载和预测导出，并非纯GPU训练时间。独立verify208.231秒，interim432.694秒；interim内部再次verify并独立重算所有报告。与最初约5.83h排期相比实际控制器更久，不能归咎于每轮打印一条文字日志。
只读审计repeated_verification_timing_audit.json发现：每个新子进程正式attempt开始前对前面所有成功job做两遍完整验收，纯新鲜60项批次的这部分计数为2×sum(k−1)=3540次；未包括当前job的收尾/父控制器验收、最终verify/report。每次涉及图/文件SHA、CPU checkpoint加载及tensor校验等，累计工作随批次大小二次增长。本轮保持封存代码、门槛和顺序，不跳过这些核验。
其中定点计时只覆盖前31项：attempt前观察区间合计4310.602秒，子进程墙钟合计15966.277秒。该区间还包含进程导入、计划核验、锁/预检和系统负载，缺少逐函数计时，不能全部精确归因到某一个重复调用或把前31数据当作全60测量；context文件mtime也不是纯CUDA初始化时间。
后续若获用户授权，可设计不削弱篡改/恢复检测的验收复用或合并同进程重复检查，另封存计算批次并测试。当前只是诊断与未来建议，没有改本批数值或绕过验收，不承诺未经测量的提速幅度。
全批峰值allocated1893.4678MiB、reserved2148MiB，最低整卡空闲18MiB。5个memory_tight全部来自R合约G3R的fold0–4（最低分别51/39/46/18/41MiB）；1个possible_memory_spill为其fold2。该标志由后续epoch耗时超过前3轮中位数两倍触发，只是耗时线索，不证明GPU换出，保存和系统负载也可解释。无OOM、非有限loss或资源验收失败；仍按原local_dev_v1执行。

### 62.10 交付、限制与停止位置

完整中间报告目录：scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/interim_A/。
- REPORT_INTERIM_A.md SHA256：55933fa880ef9e4f26c6c1d502f4f959d469d0a8fc7aba734403d8a589443b51
- report.json SHA256：7501eecd75a5326bb50618dba0b9a693a24d6f5df70172242bfe9accc53b80c1
- report_receipt.json绑定报告及各表；batch1/batch_records/interim_A.json SHA256：d0cc6f8f2d778a27b194c46891c789eb23a457041de06dbfaf6af78587ba695d，status=complete、completed_jobs=60、selected_profile=null、next_stage_execution_authorized=false。
- 15份CSV包括fold_metrics、file_metrics、pooled_oof、error_changes、changed_predictions、mechanism、sensitivity_fold_means、best_fold_means、last_fold_means、paired、holm、fit_resources、relation_support_and_gradients、disputed_file_metrics、manual_dependency_review。

报告用排他新目录生成，旧报告、旧plan/seal/attempt未覆盖。新增易读摘要为scripts/DFG/dfg_v2/PROMPT8A_REPORT.md；本节、HANDOVER、PROGRESS只追加，保留启动记录与旧正文。
review_v1的512条和review_v1b的111条人工边判断仍为空，人工precision为“未完成”；不能将Oracle/测试通过等同人工标注完成。阶段B、G*、Holm完整校正、额外seed、聚合/方向细分实验、其他五类、服务器迁移均未执行。此A比较不能单独分离L1/L2/L3或反向边的因果贡献。
最终实验将在用户安排的显存充足服务器整批重跑；目前RTX3050 4GiB只是本机限制。服务器尚未实际部署或验收，届时需核验软件/硬件、输入/初值与新批次身份，不能混用本机和服务器成绩。本轮已停在60项A验收和中间报告完成，不自动启动90项B；下一阶段需要另行授权。实施、复核及记录AI：Codex。

### 62.11 GitHub结果归档（2026-10-27，Codex）

用户明确授权推送已完成结果。新增docs/github_archive_prompt8a_2026-10-27.json/.md，逐字节归档prompt8_v1与prompt8a_v1的1721个文本文件（321382664字节），包括全部60次fit的预测、history、梯度、资源及验收记录和阶段A报告。按原.gitignore排除270份.pt（12254508170字节；150初值、120 best/last）及1个空锁，权重SHA均保留在清单。原图/特征未上传，不能将此称为完整二进制复现包；原产物、模型计算和seal不变。只精确暂存清单内文件及本次归档说明，不带入无关旧目录。


## 63. 2026-10-27：DFG v2 Prompt 8B.0 执行器性能修订（Codex）

### 63.1 范围与版本

日期：2026-10-27（America/New_York）。实施、复核与记录AI：Codex。起点dfg-v2 @ 2d826c22160380760c375501fb0fb3a61dc16a8d；开始时pull --ff-only确认已同步。

**结论：两项真实证明与历史阶段A逐位一致，2331项测试及A的60项完整验收通过；阶段B未启动。** 本轮仅优化编排和校验。


原plan SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de、seal SHA 55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8保持。初值不重新生成；图/标签/token/folds、DDG、HGT/shared层、监督、Adam/OneCycle/早停/best选择和统计算法均未改。

训练计算指定17个文件（8个v2计算文件+9个sco_models文件）SHA与计划逐字节一致；修订检查还保护原runtime中全部其他文件。新增报告前，开始时13013个跟踪文件中13005个完全不变，只有4个编排/校验生产文件与4个测试适配文件改变；历史结果和原图相关跟踪文件均未改。三份记录文档只追加并另验旧正文前缀。

### 63.2 修改文件及理由

| 文件 | 本轮修改与理由 |
| --- | --- |
| experiment/acceptance_cache.py（新增） | 完整验收后排他封存缓存；可信 seal SHA 由活跃父控制器 ticket 传递；核对 receipt、小文件 SHA、大文件 size/mtime。变化时完整诊断并拒绝继续。 |
| experiment/input_guard.py（新增） | fit 的 start / after_training / after_evaluation 三个完整边界；保存、重载前后检查输入张量、mask、标签、schema、binding；边索引副本内容比较。 |
| experiment/amendment.py（新增） | 限定8个编排/校验文件的独立修订与 seal；其余 runtime 不允许变更；绑定精确证明、原 plan/seal 与用户原文。 |
| experiment/proof_performance.py（新增） | 仅允许指定2个AC节点fold0证明任务；复用保存初值/fit seed；输出目录必须在旧批次外；严格比较数值与预测。 |
| experiment/batch.py | 父控制器建立独立验收缓存代次与进程ticket；串行子进程复用验收；最终verify保留完整核验；不修改旧批次授权。 |
| experiment/run.py | 显式 --amendment / ticket 接入；消除重复启动扫描；仅新路径启用guard；verify/select/summarize完整验收，选型仍只读inner_val指标。 |
| experiment/checkpoint.py | 包装内按guard切换快速校验；保留文件SHA、binding、state digest、格式和加载规则；未启用guard走原路径。 |
| experiment/reporting.py | 仅新增amendment_path参数及向_load_plan传递，统计正文不改；修订验收将这两处还原后核对旧整文件SHA。 |
| tests/test_acceptance_cache.py、test_input_guard.py、test_amendment.py、test_runtime_optimization.py、test_proof_performance.py（新增） | 缓存/20文件流程、张量漂移、修订白名单、旧结果与失败恢复、输出范围和新旧接口回归。 |
| tests/test_batch.py、test_batch_plan.py、test_experiment_run.py、test_reporting.py | 适配新可选参数和完整验收前置；保留数值/选择关键断言。outer_test可被完整性检查读取，但不能进入_selection决策。 |

| 文件 | 原SHA256 | 新SHA256 |
| --- | --- | --- |
| scripts/DFG/dfg_v2/experiment/acceptance_cache.py | 新增 | a6afa11d40334cdbe49abed55e04129246a41ba6eeca8edf344f000544eae145 |
| scripts/DFG/dfg_v2/experiment/amendment.py | 新增 | 5623d85f55eeb2a170ce31ef7858cfe97ee9f0cbf8c0e2b6609eed781caa51d0 |
| scripts/DFG/dfg_v2/experiment/batch.py | 66356c9fc5d37277fcd898573a222abb8b6379326c6f86ffe3ec552efb618c5e | b03543950bd08761cfce181e96bf5841946408a01073400f354b9678ce542a45 |
| scripts/DFG/dfg_v2/experiment/checkpoint.py | ffd47875d23855e6b9889cece1067a01e41d60144d652f8e1a753527b92c607c | 96311a8f8bd2d064d84a396cd2923923c1b4c45cbf5932b865107aaaff4fa3bd |
| scripts/DFG/dfg_v2/experiment/input_guard.py | 新增 | 9b0259334c41b0905605e1af83c6f270b78c5aa0a8423169026fa95ea33413fc |
| scripts/DFG/dfg_v2/experiment/proof_performance.py | 新增 | e6d72edc13ff3125d1ec8cf68173292a5c017dbbc6c1f48079dd4613a904101b |
| scripts/DFG/dfg_v2/experiment/reporting.py | ab1819b6c57a36a67eec30493be9bf565a73dba6e4acb9fdbe9a4d6762488626 | 4d4064d6ed1420a835b804261eb9c7612b9bc3daeeade3f6424e6f085003a4b2 |
| scripts/DFG/dfg_v2/experiment/run.py | ca18d0c73eaf5c12610d378cce0af52ac1d3e231be7f166727213075dc1594e2 | 3670d4e6b7e953ec705e9863e5011b518a111bf74007be2a3a4e5833a3e5da2c |


### 63.3 用户选择与具体实施

1. 用户已批准：DGL 0.6.1 的边视图共享内存但不共享 PyTorch _version，单凭指针/版本会漏掉端点修改。因此增加启动副本与 torch.equal 内容比较，不重建图、不改消息传递；批准原文“同意增加边索引内容比较（推荐）”，完整问题和本轮请求在 user_decisions.json。
2. 缓存只跟随实际完整验收依赖。开发期实测发现泛化递归追踪历史授权中的所有路径，会误把历史 PROMPTS.md 内容要求套到本轮已更新文档。已改为精确依赖清单；没有修改旧授权，也没有一概排除 Markdown：阶段B依赖的 interim 报告仍必须核验。
3. 成功结果之后出现新的不完整/失败 attempt 必须报错，不能让旧成功缓存掩盖；此前失败、后来显式重试成功可以验收。没有无限重试、没有epoch续训。
4. 缓存不把磁盘自报SHA作为可信根。父进程保存seal SHA，ticket绑定进程PID与启动身份、计划、授权、修订和job；过期、错任务或直接绕过控制器的调用被拒绝。
5. “文件哈希一次”只指guard生命周期。计划加载、冻结trainer原有read_labels和最终验收仍按原逻辑核验。target代理仅记录原targets()返回值，没有提前读取outer_test监督或评分。
6. 原native checkpoint不改；包装复制的restore路径在文件头记录来源SHA 7ccef05371f0324271986dce7d274f3a81a45a9af0e3fe10e08c018dcdd2fb99。checkpoint保存格式、每次严格更低val loss保存best、last辅助、8次重载规则均保持。
7. 可选GPU采样对照未执行，采样间隔保持0.5秒。未增加额外旧代码重跑：两次证明已直接与历史A逐位相同，无需触发允许的legacy对照。
8. 快速元数据缓存不是防恶意篡改系统：同时恢复大小与mtime的内容变化可能不被该快速分支发现；最终完整SHA验收仍执行。普通Tensor通过.data绕过_version也不保证即时捕获，三个完整边界仍核对输入指纹；DGL已知视图漏洞单独用内容比较处理。

### 63.4 等价性与完整验收

仅运行 access_control_node/0/1/G0、access_control_node/0/1/G3R 两项新目录证明，复用原未训练初值与fit seed，没有重训正式A或启动B。G0运行20轮（0-based best=12、last=19），G3R运行23轮（best=15、last=22）。

两个任务六项比较全部为true：history损失/学习率/Adam beta/patience/best保存事件、epoch、best state、last state、inner_val预测、outer_test预测；最大损失绝对差均为0.0。binding、initialization_ref、effective_config、model_input相同；预测按完整身份及全部内容比较，不按行数猜测。四个state_dict摘要与旧A一致，见equivalence_result.json。没有放宽阈值，也未触发legacy重跑。

最终batch.verify_stage(A, amendment_path=...)绕过缓存重新核验60/60，耗时200.22秒；正式结果仍G0=30、G3R=30、B=0。新增两项是proof_only/formal_result=false，不进入正式指标。

### 63.5 性能测量与阶段B预算

| 指标（秒） | G0 | G3R |
| --- | ---: | ---: |
| 旧阶段A子进程总耗时 | 537.595 | 582.927 |
| 新证明命令总耗时 | 100.263 | 136.503 |
| 旧进程启动→attempt记录 | 339.232 | 344.231 |
| 新worker入口→fit之前（不含导入） | 10.174 | 9.724 |
| 旧result.seconds | 170.856 | 205.172 |
| 新result.seconds | 67.727 | 103.101 |
| 新result加计时器外首尾完整校验 | 73.154 | 109.781 |
| 旧保存轮−非保存轮均值差（仅代理） | 3.672 | 4.055 |
| 新best保存函数均值（实测） | 0.443 | 0.549 |
| 新训练后评估窗口（实测） | 9.070 | 11.922 |

两项各13次best保存、1次last保存、8次重载，guard均为3次完整校验、46次快速检查。G0/G3R最低整卡空闲1202/864MiB，无OOM、非有限值、memory_tight或possible_memory_spill；G3R的70条训练支持canonical消息梯度验收通过，2条heldout-only保留并不要求非零训练梯度。

旧进程在阶段A第41/42项位置承担此前结果的重复验收，新proof只独立核验旧参照，不承担正式controller的全部工作；新before_fit还排除Python导入。因此上表不能证明所有阶段B任务有相同倍数提速。新result.seconds不包含guard启动与结束深验，已另列加回值，避免通过移动计时边界夸大收益。旧日志没有独立保存/评估函数计时：保存轮差值受训练和系统负载影响，只作代理；旧result减轮次合计的74.673/73.560秒还包含其他工作，不能称为精确旧评估耗时。旧last.pt→result.json mtime间隔也不当纯评估计时。

独立真实缓存微测：完整验收1.8614秒，连同排他seal创建2.0013秒；三次命中为0.002231/0.002056/0.002447秒，32个依赖、185558538字节，不加载GPU。它直接测量缓存路径，未将全部旧启动时间归因到单个函数。

阶段B仍是原90项。按两个20/23epoch AC节点proof简单外推，90项同规模约2.51–3.41小时；其他任务、剖面、早停轮数和4GiB资源负载尚未实测。暂作工程预算3–6小时，最终完整验收与报告另留15–30分钟，保守预留6–8小时；不是测得的90任务时长或保证上界。等待阶段B独立授权，不改变配置以迎合估计。

### 63.6 测试命令、失败处理与最终结果

最终冻结代码测试命令（mando环境，PYTHONDONTWRITEBYTECODE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2及原TREE_SITTER_LIB_DIR）：

```bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

- v2：2108 passed，0 failed/errors/skipped，128.40秒，8条既有弃用警告。
- 旧DDG与graph_utils：223 passed，0 failed/errors/skipped，3.05秒，29条既有弃用警告。
- 合计2331项；前期定向测试包含于全量，不重复计数。警告是DGL的distutils版本比较与NetworkX gpickle弃用，未升级依赖。
- 合成20成功job与20文件实际CPU流程涵盖缓存命中、size/mtime/删除变化后完整诊断并报错、seal/可信锚篡改、失败attempt阻断、旧失败后成功，以及阶段结束verify/select/summarize仍完整核验。独立input_guard测试验证_version、schema、mask/标签、DGL端点内容变化与懒targets。
- 开发期间有旧测试mock接口及新增完整验收前置不匹配的失败；已修复fixture并保留选择/数值断言，失败日志保留。真实缓存benchmark第一次因历史PROMPTS的过宽依赖追踪失败，未生成成功seal；修正后v2 benchmark通过。没有掩盖训练失败或放宽数值容差。
- 实际argv、JUnit与输出为v2_frozen.command.json/.xml/.log、legacy_frozen.command.json/.xml/.log。

### 63.7 修订封存、运行入口与停止位置

- stage_B_amendment.json SHA256：d2c255fb50636f91066cd2a7503715619f5bdb422af3c884727557d261631c8f
- stage_B_amendment.seal.json SHA256：6d4bc3298d89f3fdc5d133dd4871b5f3b91a37327e824bcad5ef29575bd862b1
- proof/equivalence_result.json SHA256：a220362634e3a238e04017d4b42bd880265535544c2d14e4341704a0e6462b43
- performance_summary.json SHA256：dac88d56e4825d015881e88748dbabebfb211a6c895591bdd5f01fbea71c9439
- stage_A_final_full_verification.json SHA256：b57f65c2e0140a37dc7409543c16148a0521399aa365c18a5c6c71e3e33452a7

stage_B_amendment在新prompt8b0_v1目录排他创建，execution_authorized=false；旧plan/seal与历史A保持只读。完整报告PROMPT8B0_REPORT.md；本节与HANDOVER、PROGRESS按原格式追加，不替换旧文。

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
PLAN=scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json
AMENDMENT=scripts/DFG/experiments/artifacts/dfg_v2/prompt8b0_v1/stage_B_amendment.json
python -B -m scripts.DFG.dfg_v2.experiment.amendment verify --plan "$PLAN" --amendment "$AMENDMENT"
python -B -m scripts.DFG.dfg_v2.experiment.batch verify --plan "$PLAN" --stage A --amendment "$AMENDMENT"
```

本轮两次证明的实际入口为 proof_performance worker --plan <原plan> --output <新proof任务目录> --job access_control_node/0/1/G0 或 G3R；没有--legacy，保存完整argv，不应对已存在证明目录重复执行。随后proof_performance summarize封存equivalence_result。

后续阶段B入口已支持 batch execute --plan <原plan> --stage B --amendment <本次修订> --authorization-record <新的B授权记录>。新的授权文件本轮尚未创建，也未执行该命令；不能用阶段A或8B.0证明授权替代。成功任务验收后复用，失败需明确处置，不自动重试。阶段结束仍使用带--amendment的verify/select/summarize；selection只按原inner_val规则。

最终正式实验按用户安排在显存充足的服务器整批运行；当前RTX3050 4GiB只是本机开发限制。服务器尚未部署或实际验收，未来仍需核验环境、输入、初始化与独立批次身份，不混合服务器和本机成绩。当前停止在8B.0验收与修订登记：未执行90项B、未选G*、未做完整Holm、额外seed、其他五类或模型改造。按共享上下文仅本地提交，不自动push。


## 64. 2026-10-28：DFG v2 Prompt 8B 阶段B正式执行（Codex）

### 64.1 开始版本与授权

工作树/home/zhao/SmartContract/ge-sc-llm-ddg-v11，分支dfg-v2，起点220d258f284dacd52374ba95c7284f461005a23e，git pull --ff-only为Already up to date，原跟踪工作树干净。已完整读取共享上下文及更新4.10c；只读双路复核未发现执行接口阻断，无需修改生产代码或改变方案。新授权路径prompt8_v1/batch1/stage_B_authorization.json，SHA 5437695492ebacfde65f111275cb4d5ad0e60e7a86c3f609fb8f7fbbd8558f41。授权原文为本轮用户完整请求；version=prompt8-stage-execution-authorization-v1，approved=true/stage=B/90项，包含原顺序authorized_jobs、plan/seal/SHA、8B.0 amendment及seal、interim_A收据、资源策略和时间。旧准备/A授权、plan/seal、8B.0修订均不覆盖；B授权是独立文件，未伪造旧修订为执行批准。

### 64.2 冻结与资源前提

原plan07f1dbc9…、seal55aebf92…；修订d2c255fb…（8B.0已证明2项逐位一致）通过验证；现存B attempt=0，controller_failures为空。150任务列表与保存初值、图、标签、token、fold、inside_token/shared_projection/mean、学习率、Adam/OneCycle、50轮上限、patience7、delta0.001、严格val loss best均不改。B只执行G1R/G2R/G3，首项reentrancy_contract/0/1/G1R，末项access_control_node/9/1/G3。

预检GPU记录：NVIDIA GeForce RTX 3050 Laptop GPU, 4096 MiB, 467 MiB, 3509 MiB；E实际空闲235186520064字节，WSL虚拟可用另记preflight.json，二者不混淆。资源仍local_dev_v1：每项新进程、启动free≥3000MiB，运行memory_tight仅提醒，OOM/非有限值/校验失败停止，0.5秒采样不变。产物在E承载的WSL中，不清理旧数据、不向C盘写大型结果。

### 64.3 执行与结果读取边界（启动记录）

新prompt8b_v1/before.json记录开始时全部跟踪文件SHA和runtime；preflight.json登记身份/资源。先运行v2全部测试与旧DDG回归，成功后原batch execute --stage B --amendment ... --authorization-record ...；实际argv和输出独立保存stage_B_execute.started.json/.command.json/.log。父进程先完整验收既有A并建立新缓存代次；每个B fit独立子进程单GPU串行，失败保留且不自动retry；当前没有完整结果，不提前报告F1。

结束依次batch verify B、run verify 150、run select、run summarize，均显式带amendment。全部验收后才读成绩；独立核验A旧receipt和G3R−G0表格一致。Holm由pending转为完整家族、机制表改用G*属于预定变化；补seed条件从selection记录，本轮只报告不执行。协议dfg-v2-nested-v1，inner_train训练、inner_val早停/选G*、outer_test训练后评分；全固定图前向，并非新的外部来源独立测试，不沿用旧paper_kfold称谓。

最终服务器显存充足是用户后续安排；当前4GiB仅本机限制，服务器未部署/验收，后续整批运行且不混本机成绩。本节是开始记录，完成或失败结论另行追加；未运行聚合诊断、额外seed、其他五类或服务器迁移。修改与记录AI：Codex。


### 64.4 正式完成、全部验收与收尾命令（2026-10-28，Codex）

阶段B固定90项全部attempt_001成功，无失败、无重试、无删折；阶段A60项只读复用，完整矩阵150/150。控制器返回0，执行耗时16611.179秒（4.614小时）；阶段结束后另外完成batch verify B、run verify150、run select、run summarize，均显式使用原amendment，完整SHA检查没有省略。没有把8B.0的两次证明或此前smoke计入正式150项。

| 记录名 | 退出码 | 实际秒数 |
| --- | --- | --- |
| stage_B_execute | 0 | 16611.18 |
| stage_B_final_verify | 0 | 361.22 |
| all_150_verify | 0 | 542.51 |
| select | 0 | 745.36 |
| summarize | 0 | 1358.12 |
| v2_final | 0 | 143.96 |
| legacy_final | 0 | 7.69 |

收尾命令的完整argv/日志/退出码在prompt8b_v1/<记录名>.command.json/.log。select和summarize各自仍包含完整验收及身份核对，收尾时间另列，不算新增训练或GPU fit时间。

### 64.5 主结果和辅助结果

本轮为dfg-v2-nested-v1：inner_train更新参数，inner_val选择best和全局G*，outer_test只作结束评分；完整固定任务图前向，节点按原HCG节点计分且排除env_source。不是旧paper_kfold的CV validation，也不是新的外部独立数据测试。G0是作者下载图在本地冻结协议下训练所得基线，非论文表格原始数字。

G1R=局部DATA_DEF_USE及显式REV；G2R再加状态读写锚点关系及REV；G3R再加ENV_FLOW/REV及env_source；G3为三层全部正向的方向消融。反向关系在模型输入层生成，不修改原NetworkX原边。生产代码、DDG算法、模型、标签、token、折、原初值和超参数本轮均零改动，复用8B.0已批准的编排修订。

best主终点Buggy-F1，百分数，等权折均值±样本标准差：

| 任务 | G0 | G1R | G2R | G3R | G3 |
| --- | --- | --- | --- | --- | --- |
| 重入合约 | 92.7326 ± 5.4566 | 94.8490 ± 6.3676 | 94.8490 ± 6.3676 | 94.1612 ± 6.3579 | 94.8490 ± 6.3676 |
| 重入节点 | 96.4276 ± 6.5918 | 96.4492 ± 6.6020 | 96.9420 ± 6.6318 | 96.9344 ± 6.6127 | 96.8842 ± 6.6348 |
| 访问控制合约 | 94.6066 ± 1.6532 | 95.4037 ± 0.2268 | 95.4075 ± 3.2189 | 95.4075 ± 3.2189 | 95.4733 ± 0.3447 |
| 访问控制节点 | 96.1753 ± 6.2062 | 96.0510 ± 6.0462 | 95.6227 ± 5.9501 | 95.9716 ± 6.1255 | 95.9405 ± 6.0831 |

last辅助结果，不能替换best：

| 任务 | G0 | G1R | G2R | G3R | G3 |
| --- | --- | --- | --- | --- | --- |
| 重入合约 | 92.1620 ± 3.0510 | 94.9699 ± 4.2352 | 94.9699 ± 4.2352 | 95.7037 ± 4.7257 | 94.3262 ± 4.1789 |
| 重入节点 | 97.0827 ± 6.6227 | 96.8179 ± 6.6368 | 97.3801 ± 6.6268 | 97.1568 ± 6.4290 | 97.3428 ± 6.5011 |
| 访问控制合约 | 86.6580 ± 6.9124 | 84.2008 ± 5.6772 | 84.8065 ± 5.9793 | 84.9255 ± 5.7693 | 83.9763 ± 5.2135 |
| 访问控制节点 | 93.9087 ± 5.7938 | 94.1699 ± 6.4748 | 95.4570 ± 5.7513 | 94.7086 ± 5.9949 | 94.7351 ± 6.0385 |

BF1之外的Macro-F1、Precision、Recall和每折混淆矩阵、逐文件结果、pooled OOF、配对bootstrap区间/A12/Wilcoxon/Holm、方向消融、错误变化、争议文件敏感性、G*的1/2跳邻域机制表均在scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/。mean/std是折的描述统计，不是独立seed方差；不把节点数当作独立实验次数。

### 64.6 选型与结论边界

预注册主要对比保持为G3R−G0的best outer-test Buggy-F1；选择G*=G2R不能取代该终点。G3R−G0的四任务差值依次+1.4286/+0.5068/+0.8009/−0.2037pp，重入节点10折全提升、该task/checkpoint/metric家族Holm p=0.0078125；访问控制节点没有收益。自动REPORT前言保留通用的“阶段A等待阶段B补Holm”说明，完整表中的32个家族已经补齐/标明合约描述性状态，不表示本批统计仍待完成；旧封存报告正文不改。

selection.json按全部inner_val.best BF1先任务内折均值、再四任务等权选择，G*=G2R。内层均值G0=95.66258751，G2R=96.49445093，差+0.83186342pp。完整候选/矩阵为true、outer_test_used=false；未按outer_test选更有利剖面。selection SHA 4c78edc2a1921cc9d4c08d5bcb571efe4c4855580beedee6c8f70bc59253bdad，封存150份收据；选择结果与独立公式重算一致。

additional_seed_condition_met=true，但additional_seed_execution_authorized=false。本轮只报告条件，不开启新seed、聚合诊断、其余五类、推理或服务器迁移。G*是所有折内层分数汇总的全局剖面，不是每个外层折重新选型；无新增外部独立测试。

收益混合：重入节点G2R/G3R/G3相对G0均10折提升；G2R均值约+0.5145pp。访问控制节点best四个增强剖面均下降，G2R约−0.5526pp；两项合约提升集中少数折。last方向并不总一致，尤其访问控制合约全部低于G0，而访问控制节点last均值转正，不能择优替换终点。统计仅在对应task/checkpoint/metric的四项对G0家族内作Holm，方向消融单列，不作所有指标总体显著的宣称。

G2R相对G0的best节点错误：重入353→292，纠正79、新增18；重入buggy_18为221→219。访问控制207→243，纠正8、新增44；AC buggy_18仍94、buggy_26仍42，parity_wallet_bug_2为3→2。同名文件按类别/源码SHA区分；“错误”均指相对冻结作者标签，不能直接当作真实漏洞裁定。新增参数、聚合与优化轨迹也变化，不能把差值全部解释为纯依赖语义因果贡献。

### 64.7 资源、梯度与代码不变量

新B90项fit内部累计8743.099秒（2.429小时，含fit内部验证/保存/重载/导出），控制器整体4.614小时；不将二者差额全部归因于打印日志。B峰值allocated/reserved=1829.03/2026MiB，整卡最低free=53MiB，7项memory_tight，0项possible_memory_spill。全部150项累计fit内部24945.765秒，峰值1893.47/2148MiB、最低free18MiB（来自历史A），12项memory_tight、1项时长提醒；均无OOM或非有限值失败，时长提醒不证明显存换出。

全部150项保存的best/last在inner_val和outer_test逐位重载一致，无评分时创建新参数、无outer标签参与优化。首轮5923条fit×新增canonical记录有训练支持且消息梯度非零；287条没有训练支持，按策略保留，不要求非零监督梯度。这不是5923种全局不同关系。来源resource_invariant_audit.json。

298个运行源码SHA与开始快照完全一致；原plan、seal、amendment及阶段A原产物不变。只追加三份文档、新建PROMPT8B_REPORT.md和旁路审计/统计产物；未修改任何训练计算。

### 64.8 独立复核与测试

- 最终全v2：2108 passed、8条警告，旧DDG/graph_utils：223 passed、29条警告；共2331项不同测试通过，0失败/错误/跳过。前置与结束运行同一套，不累计为4662个不同测试。警告为既有DGL distutils和NetworkX gpickle弃用提示。
- 独立JSON审计对150项、256份源码SHA、冻结划分/节点身份/监督mask/跨profile目标一致性复算；独立二分类公式得到600逐折、3840逐文件、80 pooled OOF及320均值/标准差记录；600逐折、3840逐文件、80 pooled及best/last各80条均值/标准差已逐项对照正式报告，最大绝对差2.842170943040401e-14。合约target直接对冻结graph_labels.json；独立脚本的原图pickle直接读取被自动审批拒绝，改用JSON核验，不绕过。节点原图直接标签对照由官方full verify的_validate_predictions承担（read_graph→get_node_label→按source_file/original_node_id严格比target），不把两条证据链混写。
- 阶段A18份旧报告文件及60收据/120预测SHA不变，13张共同表5371行精确一致（含32组G3R−G0配对原始统计）；完整报告增加Holm家族及G3R−G3，机制表从中间固定G3R换到已选G2R，属于预登记变化。详细逐项审计见prompt8b_v1/independent_stage_a/audit.json。
- 独立指标脚本及comparison.json位于prompt8b_v1/independent_metrics/。未重写生产指标函数，浮点比较容差1e-10，历史A共同表要求精确一致。
- 人工512/111条依赖边抽查表仍未填写，报告明确“未完成”；自动Oracle、事件审计或模型梯度不能替代人工精确率。未宣称完整Solidity DFG/语义正确性或跨语料泛化已证明。

### 64.9 产物与停止点

正式报告：scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/REPORT.md；结构化report.json及15份CSV由report_receipt绑定。本轮说明：scripts/DFG/dfg_v2/PROMPT8B_REPORT.md；交接和PROGRESS同步追加，修改AI均标Codex。新核验记录在prompt8b_v1，旧A不覆盖；原150项计划、各best/last checkpoint仍在原目录。仅在验收完成后按共享上下文本地git commit，不自动push。

可只读核验（保持mando环境及原TREE_SITTER_LIB_DIR、OMP/MKL=2）：

```bash
PLAN=scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json
AMENDMENT=scripts/DFG/experiments/artifacts/dfg_v2/prompt8b0_v1/stage_B_amendment.json
python -B -m scripts.DFG.dfg_v2.experiment.batch verify --plan "$PLAN" --stage B --amendment "$AMENDMENT"
python -B -m scripts.DFG.dfg_v2.experiment.run verify --plan "$PLAN" --amendment "$AMENDMENT"
```

select/summarize已经成功且排他封存，不对原目录重复执行或覆盖。完整实际命令见command.json。最终实验将按用户安排在显存充足的服务器整批运行；当前RTX3050 4GiB只约束本机。服务器尚未部署或实际验收，后续不能混合本机与服务器成绩。 本轮在150项完整报告与文档交付处停止，没有自动继续更多训练或修改模型。


**64.10 2026-10-28 Prompt 8B GitHub归档补记（Codex）**

用户在结果完成后明确要求推送GitHub。已核对dfg-v2本地HEAD=22a57fc，已跟踪工作树无其他修改；实时远端仍为220d258。复用阶段A归档方式，范围限prompt8_v1新增文件、prompt8b0_v1和prompt8b_v1中的结果与验收文本。共2811个文件、871490009字节；新增正式result.json为90份，G1R/G2R/G3各30，A60不改不重训。逐文件原路径/大小/SHA256见docs/github_archive_prompt8b_2026-10-28.json。

summary.json（306458598字节）和stage_A_final_full_verification.json（101952163字节）保留原文件，另建确定性gzip副本（mtime=0），实际解压SHA与源文件完全相等，上传副本均低于90MiB。此为归档表示调整，不改变任何实验算法、数据或结果；旧收据仍绑定原JSON。其余选中文本保持原字节，拒绝密钥/token样式文本、符号链接和意外格式，模型权重、临时锁以及既有输入二进制不提交。

WSL直连失败原因为github.com DNS解析；采用项目已验证的Windows Git联网与WSL gh凭据助手，临时配置且不读出凭据、不改全局Git/DNS/代理。仅正常push origin HEAD:refs/heads/dfg-v2；远端SHA必须与本地一致才能报告完成。没有生产代码变更，因此本轮不重复2331项已通过的算法/训练测试；执行逐文件摘要、压缩回读、归档范围和Git检查。Git归档不等同完整权重/图资产云备份；人工依赖证据审阅未完成的限制继续保留。

归档核验：2811个Git暂存blob的SHA256与清单及原文件逐一相同，三份文档保持旧正文前缀不变。默认git diff --check对既有CSV的CRLF、历史测试日志/XML中的行尾空白和已封存自动报告末尾空行提出格式提示；为保持封存SHA，不修剪原产物。新写说明文档的diff --check单独通过。


## 65. 2026-10-28/29 Prompt 8C：完整诊断与实施记录（Codex）


实施与复核：Codex。工作树 `ge-sc-llm-ddg-v11`，分支 `dfg-v2`，起点 `ad2c8fe`。依据更新后的 PROMPTS §4.1、§4.10d。日期：2026-10-28/29。

本轮没有新训练、没有修改 DDG/HGT/tokenizer、冻结图/标签/折、150项历史结果、原 plan/seal/selection 或阶段 A/B 报告。新增逻辑均在 `diagnostics8c/`，新产物均在 `scripts/DFG/experiments/artifacts/dfg_v2/prompt8c_v1/`。E 的20次拟合仅有计划，仍未授权。

### 65.1 用户已批准的三项口径调整

1. 150项全部验收；100项节点结果做 orig/C1/C2，50项合约结果仅原标签分层参考，不把节点标签推断套到合约标签。
2. Wilson95%区间仅用于 pooled Precision/Recall，BF1只给点估计；非SolidiFI不计算折均值。节点/文件/克隆相关性使区间仅为描述。C1/C2不是已验证的漏洞真值。
3. G0P保留G0节点/特征/类型，只匹配原目标类型在G3R中的canonical数量，不新增env_source；证明限于相同输入的一层mean分母，不称最终logits固定倍数缩放。

其余调整均是诊断接口与正确性修复，没有改变上述实验方案，详见第8节及 training_changes §65。

### 65.2 A：标签证据

|项目|重入节点|访问控制节点|
|---|---:|---:|
|审计文件/节点|71/12036|57/7710|
|疑似截断文件|buggy_18|buggy_18、buggy_26|
|规则为正但冻结标签为0|214|93、42|
|非截断规则一致率|10467/10467|6755/6764|
|orig→C1正例数|6570→6784|2977→3112|
|溢出候选|0|30|
|C2排除节点|230|421|

候选规则严格按文档：非容器范围与映射后的BugLog行集合求交，contract_declaration只查起始行；library保持范围规则。C2的容器排除包括contract/library；仅作为评分视图排除，不从图或数据集中删除。

三个文件的已标正节点起点边界换回原始行分别为111、89、103，与首个重叠CSV条目的起始行一致。但节点附带的作者漏洞行列表仍存在后续高行号，最大为840、687、687，其中41、23、19行超出cleaned文件。因此“截断”指观测到的缺失正例模式，不能据此证明作者转换代码遇到重叠就停止，也不能说附带列表在73/55/83行字面结束。节点覆盖末行、节点起始行、附带标注最大行分别保存。

80份CSV均与SolidiFI固定commit `4b0573e1b3f7031396de6f48f7f3e7380222ad3a` 的Git对象逐字节相同；128份源码按manifest SHA核验，19746个节点直接对照冻结HCG target/source/type/coordinates。源码坐标转换用去注释、去空白后的顺序匹配，字符串内的注释符保留。

parity_wallet_bug_2的17行cleaned视图与原始注释226/233，以及0x627fa62…的raw94调用与changeOwner标签证据均单列在A/audit.json；不据此直接修改原标签。溢出仅为注入名称范围之外的候选，未经人工语义确认。

与参考审查脚本逐项对照424项：422项一致。两处差异都是buggy_35的未映射行计数：本实现0，参考1；参考脚本先处理块注释，将 `//*****` 中的字符错误识别为块注释开头，吞掉后续library SafeMath。保留差异与最小回归证据。截断清单、规则一致率和各剖面TP/FP/FN一致。

### 65.3 B：冻结预测的敏感性重评分

150/150原指标独立复算通过，最大浮点差 `1.421e-14`。G0是作者图结构/标签配合本地冻结token特征与协议训练的基线，不是论文原始数字。指标按HCG节点计分，不是按源码行去重后的指标。原标签仍是主结果；下表为诊断视图的best节点BF1等权折均值（%），不替换旧报告：

|任务/视图|G0|G2R|G3R|不学习的标识符规则|
|---|---:|---:|---:|---:|
|重入C1|98.49374|99.02494|99.01731|99.44418|
|重入C2|98.61818|99.10896|99.14177|99.48635|
|访问控制C1|98.76959|98.21754|98.56587|98.97434|
|访问控制C2|99.43359|98.86686|99.21690|99.62866|

补全疑似缺失标签提高绝对分数，却没有改变访问控制增强图落后于G0的方向。仅检查txorigin/re_ent名称的无学习规则已接近99%，表明合成注入特征使该评价具有很强的词法可预测性。

nonSolidiFI原标签pooled：访问控制G0/G2R/G3R均TP=0、FN=20，G1R为TP=1/FN=19；重入G0 TP/FP/FN=16/25/17、G2R=15/20/18、G3R=17/23/16。样本少、标签含争议，不宣称精确泛化水平；也不能把总体接近99%理解成真实合约上已接近完美。

B输出820条折指标、138条pooled、92条折均值、304条指标配对汇总及2720条配对折指标。没有增加Holm家族、重新选择G*或替换best/last规则。

### 65.4 C：实际模型图的结构

实际训练图中，重入193项、访问控制218项modifier_invocation语法均没有独立HCG调用节点；其中唯一绑定到modifier定义的178/195项，基类构造语法9/9项，无法确认6/14项。也核对了调用AST全部后代及节点文本，未发现遗漏的独立锚点。因此应报告“没有节点”，不能误称“节点入出度0”。

原NX图没有对应函数到modifier定义的直接或两跳路径。模型反射图中90/109项存在结构性两跳路径，常经合约容器；这不证明modifier执行/守卫语义已编码，且五个剖面相同。

G0原节点孤立数：重入1360/12036，访问控制513/7710；G2R/G3R为223/12036、233/7710。新增边改善连接覆盖，不等于所有连接具有正确漏洞语义。

cross mean每个目标类型的canonical数量（G0/G1R/G2R/G3R/G3）：
- expression_statement：两个任务均18/29/31/32/25。
- new_variable：重入16/26/36/37/24，访问控制15/25/36/37/23。参考表仅吻合访问控制，不宜直接套给重入。
- 实际schema没有全局空关系，但单节点没有某关系入边时仍得到零帧。
- 已保存安装DGL0.6.1的reduce_dict_data源码与SHA，确认stack后对关系帧mean。

### 65.5 D：只改注入标识符的checkpoint诊断

100项best置换前向全部完成，另有1项未改写门槛前向；本轮训练0次、optimizer更新0次。门槛argmax及float32正类概率与归档逐位一致，差值0；原归档不含logits，不声称比较了归档logits。

节点BF1等权折均值（%），每个剖面覆盖冻结10折：

|任务|剖面|orig未改名|orig改名后|C1未改名|C1改名后|分类改变节点数|
|---|---|---:|---:|---:|---:|---:|
|重入|G0|96.42758|35.61360|98.49374|35.97023|5274|
|重入|G1R|96.44921|38.12496|98.51904|38.55483|5151|
|重入|G2R|96.94204|36.83743|99.02494|37.08333|5301|
|重入|G3R|96.93441|38.48659|99.01731|38.88253|5169|
|重入|G3|96.88416|37.33155|98.95103|37.57524|5232|
|访问控制|G0|96.17531|10.70292|98.76959|10.85192|2859|
|访问控制|G1R|96.05098|11.47891|98.64649|11.63313|2845|
|访问控制|G2R|95.62274|19.88883|98.21754|19.78187|2686|
|访问控制|G3R|95.97159|10.52591|98.56587|10.65489|2852|
|访问控制|G3|95.94051|14.69410|98.53520|14.68959|2797|

G0重入Precision/Recall由94.88375/98.70072变为90.39494/22.65301；访问控制由94.95208/98.12521变为73.10469/6.28023，主要增加漏报。五剖面完整逐折、pooled、P/R/Macro-F1、概率变化和文件分布见D/summary的7张CSV。

原分数与B的80项指标完全一致。非SolidiFI在五剖面合计重入5725、访问控制2595行预测，分类及概率均逐位不变。19746原节点文本预检通过：重入5678、访问控制2328节点含目标标识符。

100worker内部合计2324.03秒（38.73分钟，含加载/校验/编码/前向，不是纯GPU时间），另门槛34.67秒；子进程启动开销另计。最大allocated/reserved572.07/588MiB，无OOM/非有限值/正式worker失败或自动重试。

相同文件按原始源码中标识符首次出现顺序映射为idN，跳过已有idN冲突；字符串、注释和其他文本不变。只重编码outer_test的原HCG节点；env_source及其余特征、图结构、标签、权重都保持原样。所有图仍作完整固定图前向。该测试测量词汇置换敏感性，也带来测试时分布变化，不能单独证明“模型只学名称”或分数差异的纯因果来源。

### 65.6 E：G0P计划与停止点

已生成20项未来节点拟合计划及独立seal、授权模板，`execution_authorized=false`、实际fit=0。每折绑定原G0未训练初值SHA、optimizer_steps=0证据、原fit_seed/配置/划分。保留G0节点与特征，重入新增62个、访问控制新增67个空canonical，不新增env_source。

CPU同输入单层证明：mean消息分母公式最大误差1.86e-9，经过原residual/norm的输出公式误差0。共有参数语义对齐完全相同，空关系未用参数确定性零/priority1，不消耗额外训练RNG。多层隐藏状态与attention会继续变化，因此不声称最终logits固定比例缩放。

20fit的历史参考约81–85分钟，未含额外编排/完整验收开销，不保证G0P实际吞吐。本轮不启动该训练，保持授权边界。G0P尚未接入正式训练器白名单；这里只准备了计划、构造辅助函数与数值证明，不声称现有训练CLI已经支持G0P参数。

### 65.7 F：重复样本与未来分组折

256个源码身份、32640对比较，得到2对精确重复、38对近重复、22个近重复连通簇。两个类别各自的buggy_22/buggy_36完全重复，且均跨外层折。

|任务|近重复对|跨外层折对|
|---|---:|---:|
|重入合约|26|17|
|重入节点|21|19|
|访问控制合约|7|7|
|访问控制节点|5|4|

近重复使用去注释、去空白后的SequenceMatcher ratio>=0.98，保持默认autojunk=True并记录排序方向；它是启发式源码相似度，不等同语义等价。连通簇是传递闭包，不表示簇内每对均过阈值。

F提供每簇四任务fold位置、inner train/val暴露和未来服务器分组折方案。当前折没有改变。未来按簇先分组再切外层/内层，可避免已知克隆穿越监督边界；需单独冻结批次，不与当前分数混合。

### 65.8 实施、验证与不变量

新增10个Python模块、README及8组测试；没有修改生产DDG/HGT/tokenizer/训练代码。三个既有记录文档只追加。150项原产物均只读。

开发期问题均单列，未悄悄调整门槛：
- 首次旧全量验证在第2项因新增诊断模块被视为runtime漂移而停止。新增只读历史清单适配，先逐文件核对旧计算SHA，再用原amendment/seal/proof验证；不修改旧seal，不赋予训练权限。之后150/150通过。
- A预检曾将attempt sidecar误当目录、遇None标签元数据；在成功审计前修复，失败记录保留。
- 代码复核发现pydot不会双重转义普通反斜杠；原诊断解码可能误判字符串边界。现只逆转pydot实际转义，加入反斜杠/字符串禁止改写回归。已完成首个诊断的每个最终改写文本SHA重新核对完全一致后复用，无挑分重跑。
- D汇总遇到manifest与冻结TokenEncoder对“原样code”的描述文字不同，仅接受两个已知精确字符串，仍拒绝normalization；未改变配方。首次2231项v2通过后，为新增回归重新运行最终全套。

最终测试：2232 v2 + 223旧DDG/graph_utils = **2455 passed**，0失败/错误/跳过。37条警告为既有DGL distutils/NetworkX gpickle弃用提示。测试子进程隐藏GPU，未与D推断竞争。原tokenizer先全长编码再按冻结规则截取512，日志中的长序列提示不代表此流程发生索引异常。

结束复查3480个受保护输入/产物引用和298个历史计算文件SHA，全部一致；文档追加前旧已跟踪文件零改动。详见protected_integrity.json、final_crosscheck.json。

### 65.9 当前结论与后续边界

本批证据最支持先解决评价可信度：注入词法标记、克隆跨折与标签疑点均有实际证据。DDG在重入的原协议下有小幅增益，但不能据此证明真实漏洞泛化改善；访问控制增强图下降也不能简单归因于DDG关系错误。下一步若获批准，可执行已准备的G0P对照；服务器正式批次应重新冻结分组评估，并明确词法处理和标签口径。

仍未完成：G0P20fit、独立外部测试/分组折训练、额外seed、其余五类、既有512/111条人工依赖证据表。不扩展新关系、状态分析或控制依赖。

最终实验将按用户安排在显存充足的服务器整批运行；当前RTX3050 4GiB仅是本机限制，服务器尚未部署/实测，本机和服务器结果不能混合。

实际命令和API见 diagnostics8c/README.md；完整数字见A/B/C/D/E/F结构化产物。本轮按共享上下文本地提交，**不推送GitHub**，停在E授权点。

### 65.10 文件、命令与实施边界

新增diagnostics8c模块：__init__.py、common.py、labels.py、scoring.py、structure.py、placebo.py、duplicates.py、inference.py、inference_batch.py、inference_summary.py；新增README、PROMPT8C_REPORT.md。新增8组test_prompt8c_*测试：labels/scoring/structure/placebo/duplicates/inference/inference_summary/common。原生产Python文件没有修改。

common只读适配历史验收；labels独立实现并对比参考输出；scoring独立公式复算；inference复用make_model/restore_checkpoint/DfgV2Supervision/TokenEncoder，eval/no_grad，不调用fit或optimizer；batch固定100项串行，首项当前文本SHA相同后复用；summary拒绝缺失/重复/错位/混合来源；structure直接核查实际图；placebo只准备计划；duplicates不改折。

用户三项答复已记录在本节和before.json。没有另改模型方案。诊断代码的pydot转义、历史清单和配方描述适配属于对实际接口的正确性修复，原计算与数值门槛不变。文档首次长脚本跨系统UTF-8传输失败在Python解析阶段，未写文档；改为WSL文件中保存UTF-8脚本执行，未猜测恢复文字。

实际命令/API见diagnostics8c/README.md。最终测试命令：
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
沿用mando及原TREE_SITTER_LIB_DIR，PYTHONDONTWRITEBYTECODE=1，OMP/MKL=2；测试子进程CUDA_VISIBLE_DEVICES=''，推断原CUDA，不切CPU。日志/JUnit在prompt8c_v1/tests。首次2231项v2通过日志保留，新增回归后最终2232项重跑；旧223项不重复累计。

之前只读环境覆盖评述没有产生代码变更；本轮没有扩展环境键、modifier节点或控制依赖。当前诊断不能替代原512/111条人工语义审查。产物写在WSL工作树，没有新checkpoint副本。仅本地提交、不push；E20fit需后续授权及独立接入。


## 66. 2026-10-29 Prompt 8D：300次诊断与分组基准准备（Codex）

日期：2026-10-29；实施与核验：Codex。起点 dfg-v2 @ dd70fb966b64df43ac9e75a6f94f0b675fcaa593。读取更新后的 §4.1/Prompt8D，git pull --ff-only 已同步；未切换、重置或迁移历史实验。

### 66.1 范围和保留项

新增分析位于 diagnostics8d/，新分组基准准备位于 benchmark_v2/，测试位于现有 v2/tests。旧DDG、HGT、tokenizer、原训练器与冻结150项实验均不改。8D产物在独立 prompt8d_v1/，旧8C和失败开发尝试保留。没有新增依赖安装、编译器下载、外部数据上传。

diagnostics8d：__init__.py、renaming.py、prepared.py、inference.py、inference_batch.py、inference_summary.py、stratification.py、line_provenance.py、keyword_baselines.py、README.md。
benchmark_v2：__init__.py、feature_view.py、grouping.py、prepare.py、equivalence.py、README.md。
新增7组test_prompt8d_*测试：readonly、renaming、inference、summary、grouping_plan、benchmark_feature、equivalence。

inference.py只复制调整原8C前向的输入视图装配，头部绑定原文件SHA；继续调用原make_model、restore_checkpoint、DfgV2Supervision、eval/no_grad。原模型数学与512维inside_token配方不变。当前特征是浮点存储的tokenizer ID序列，不是CodeT5隐藏状态。

### 66.2 用户批准的调整与依据

原C要求普通名称与全部标记名称等量、同token长度；80个SolidiFI文件实例均无法满足。用户批准保留B_full100次，另做B_matched100和C_matched100，共300次推断。匹配按文件内唯一名称数量和孤立名称token长度直方图；不把出现频率、修改节点数量说成已匹配。10个AC文件无可匹配名称，仍以恒等映射保留。

未增加新模型、关系、标签修正或正式训练。F仍停在用户选择标签策略、seed集合和本机/服务器的位置。用户先前最终服务器显存充足的安排已记录；本机RTX3050 4GiB只是当前开发限制，尚未核验服务器环境，禁止混合两地成绩。

### 66.3 逐节点改名验收

候选词表固定、确定性生成；检查原源码全部名称碰撞。普通对照名称要求AST可识别的用户声明并排除关键字、内建/全局名及标记名称。字符串和注释不改。
除了孤立标识符token数，还核验每个完整节点文本的未截断长度、每个编辑位置的token区间，以及编辑区间外全部token ID。之后按冻结规则截断/填充512。prepared视图封存源码SHA、文件/节点身份、原/新code和向量摘要、位置证据；每次worker重新核对映射及预期改名节点集合。

80文件共18082个SolidiFI节点。全量标记名称R2585、AC2222；匹配每侧R100、AC146。B_full修改代码节点R5678/AC2328；B_matched310/224；C_matched845/393。两侧修改节点和词法出现数量不同，必须与分数一起解释。
独立CPU审计重新编码6视图的9778条修改文本记录，所有未截断位置与512向量完全一致。部分修改在512之后：R三视图分别1/8/15条、AC1/1/11条文本改变但向量不变，计入代码修改、不计入特征修改。

### 66.4 执行、绑定和失败策略

新执行plan/seal绑定原计划、原150结果验收、原8C门槛、本次GPU恒等门槛、准备视图、用户批准和4个worker源码SHA。固定300任务，单GPU进程串行，每个任务独立进程，错误停止、不自动重试、不切CPU；失败日志不能当作成功复用。

每个worker只替换outer_test文件的输入行，其他特征、原NX属性、全部基础/新增边和模型权重保持。保存原/新概率与argmax，身份按task/fold/file/source SHA/original node ID。最终汇总拒绝缺失、重复、错位、错误收据、过期代码、错图/初值/标签/特征；额外核验当前环境门槛与实际checkpoint/state。该校验只强化证据，不重新跑模型。

原8C的idN、B_full和两匹配子集使用同一已训练best checkpoint；不是中性输入重新训练后的成绩。B_full与idN同时改变替代词token值及位移，不能把差值全部定量归于位移。匹配对照也不能消除词频、语义角色和修改节点暴露的差异。

### 66.5 F：只准备分组基准

256源码身份合并为227个已知近重复/精确重复连通组，保留单例与全部文件。
R合约142文件124组/5折，R节点71文件57组/10折；
AC合约114文件107组/5折，AC节点57文件52组/10折。
30个外层折及各自inner train/val均按组隔离；每文件恰好一次outer，合约各部分均有两个类。分组优先于精确分层，不换seed挑结果。已知文本克隆隔离不等于消除了所有注入模板或语义重复；完整固定任务图前向仍是transductive。

新idN特征视图覆盖全部训练/验证/测试原HCG节点，51490行全部独立重新编码一致；env_source和非SolidiFI保持原输入。40次原/中性视图模型装配核验保持节点/顺序/边/非token属性。原磁盘图不改，只在深复制的图上绑定独立token视图。

L-orig使用冻结作者target。L-audit使用C1 target并将C2排除节点从loss和主评分掩蔽，不删除图节点，不把排除项改成负例。两策略都另报全体原HCG节点的orig辅助分数；合约标签不变。C1/C2仍为诊断假设，不应宣称为确证真值。

170任务=5剖面×30折+G0P×20节点折，默认建议seed1；execution_authorized=false，实际label/seed/location均null。初值须在后续授权执行计划中重新封存，不能复用旧训练权重。配置逐任务沿用实际LR/Adam/OneCycle/50轮/patience7/delta0.001/最低inner_val loss选best，last独立。G0P采用原8C零边分母设计，不新增env_source。
既有训练CLI尚未支持这个完整新计划；未来需要明确feature/label/split/G0P接入测试，不能现在声称已有可执行170训练命令。

### 66.6 数值等价性与开发记录

F特征接入验收使用原G0和恒等视图各1个CPU epoch，共2个optimizer更新、0正式fit。前向、loss、参数、Adam、scheduler数值与best/last评分逐位相同。train loss=0.6978223323822021，inner val loss=0.6693451404571533。
第一次报告只因反序列化scheduler bound-method实例地址不同判失败；原报告保留。新checker核对实际__func__身份及全部数值字段，用保存checkpoint复核通过，额外更新0，未放宽数值容差、未重训。

A初次有38个synthetic else-if节点归属未解析；复用原CFG的return_if_root构造规则补齐准确AST身份，不按最近行猜映射。最终19746节点全部归属可解释。
renaming预检v1-v5均保留：缺少下划线候选；遗漏transfer排除测试；空格前缀token签名；任务feature描述字典差异；长文候选检查性能问题。固定候选库/明确排除/按实际tokenizer配方/安全前缀签名缓存修正后v6全80通过；最终节点全文校验从未放宽，没有正式GPU失败重试。
最终summary额外绑定当前GPU恒等门槛，17项针对篡改的回归通过。2643唯一测试通过（2420v2+223旧），0失败/错误/跳过，8/29条既有DGL/NetworkX弃用警告。第一次2403v2通过记录保留，不重复累计。

### 66.7 资源和未执行事项

历史本机任务中位耗时对应新170任务约8.2791小时，仅计划参考，另需编排、验收和早停变化余量。服务器硬件未指定，1x/2x/4x只是8.279/4.140/2.070小时的条件情景，并非实测预测。
不执行170正式fit、不加seed、不扩展其余5类、不新增关系、不改标签、不运行新的solc验证，不声称完整DDG语义或真实泛化已证明。既有512/111条人工依赖审查未在本轮补齐。

### 66.8 已完成结果与方法限制

|任务|剖面|原特征|8C idN|B全量同长|B匹配标记|C匹配普通名|
|---|---|---:|---:|---:|---:|---:|
|重入节点|G0|96.4276|35.6136|60.1317|95.3652|96.3192|
|重入节点|G1R|96.4492|38.1250|67.3088|95.4647|96.2647|
|重入节点|G2R|96.9420|36.8374|63.5171|95.7962|96.7517|
|重入节点|G3R|96.9344|38.4866|67.7559|95.8106|96.9344|
|重入节点|G3|96.8842|37.3315|62.7965|95.7675|96.3539|
|访问控制节点|G0|96.1753|10.7029|90.1299|95.9495|96.1753|
|访问控制节点|G1R|96.0510|11.4789|94.4348|95.9422|96.0008|
|访问控制节点|G2R|95.6227|19.8888|94.3651|95.5913|95.6382|
|访问控制节点|G3R|95.9716|10.5259|93.3903|95.7184|95.9526|
|访问控制节点|G3|95.9405|14.6941|93.5219|95.7997|95.9556|

**结果需要修正8C的简单解释。** 同长度、同位置改名明显高于原idN干预：重入G0/G3R分别从35.61/38.49到60.13/67.76；访问控制从10.70/10.53到90.13/93.39。因此，旧idN的剧烈降分不能全部解释为“删除注入名称线索”。两种处理的替代token值也不同，本轮未得到位移效应的独立因果估计。

**保持其他token位置不变后，重入仍明显退化。** B_full相对未干预BF1，重入G0/G3R下降36.30/29.18个百分点，访问控制下降6.05/2.58个百分点。这证明冻结模型对这些标识符取值敏感，不能推出它只依赖名称、完全没有学习语义。

|任务/剖面|B_full BF1|Macro-F1|Precision|Recall|
|---|---:|---:|---:|---:|
|重入G0|60.1317|67.6627|92.9512|45.7557|
|重入G3R|67.7559|72.8595|94.4532|53.9605|
|访问控制G0|90.1299|92.2052|94.8041|87.8965|
|访问控制G3R|93.3903|94.8194|95.1568|92.9752|

本小子集里，匹配标记改名比匹配普通名称改名影响更明显。重入G0：95.3652对96.3192；G3R：95.8106对96.9344。访问控制G0：95.9495对96.1753；G3R：95.7184对95.9526。只匹配了R100/2585（3.87%）、AC146/2222（6.57%）个标记名，C又修改了更多节点/词法出现，不能推广为所有普通名称都稳健或严格等剂量因果比较。

以orig pooled错误变化看，B_full的重入G0/G3R分别纠正123/111个旧错、新增3538/3032个错；AC分别纠正0/3、新增316/149。C_matched的重入G3R、AC G0虽然F1和分类都不变，仍分别有6047、2453个节点的正类概率发生变化。分数不变不等于输入没被读入，也不等于隐表示或概率不变。

G3R在B_full干预下高于G0，可描述为本次固定干预下较稳健；它不是重新训练后的外部测试，也不能证明纯DDG语义因果增益，不能据此重新选G*。

匹配保证每文件唯一名称数和孤立token长度直方图；不匹配出现频率、语义角色和受影响节点数。10个AC文件没有可匹配名称，原样保留，不删样本。

|干预|重入/AC唯一名称数|重入/AC修改代码节点数|重入/AC节点文本内改写次数|
|---|---:|---:|---:|
|B_full|2585/2222|5678/2328|14790/7777|
|B_matched|100/146|310/224|522/514|
|C_matched|100/146|845/393|2135/1115|

节点文本可嵌套包含同一源码；词法次数不等于独立源码位置。全部视图核验整段未截断token长度、每处编辑的token区间，以及区间外所有token ID。独立CPU重编码9778条修改记录，证明与512维冻结配方一致。R三组分别1/8/15条、AC1/1/11条改写在截断之外，代码变化但向量不变。

三组非SolidiFI预测逐位不变：每组五剖面共R5725、AC2595行，分类和概率变化均0。汇总按task/fold/file/source SHA/node identity对齐，拒绝缺失/重复/错位/混合来源，绑定当前环境门槛及原checkpoint与state。B_full相对8C idN同时改变替代词token值和位移行为；不能将分差全部当作位移的纯因果贡献。C匹配组的代码暴露量更大，不能把全部差异归结为“标记词特殊性”。



300个worker内部合计6563.23秒（109.39分钟，含加载、校验、前向），子进程墙钟合计7577.46秒；峰值allocated/reserved为572.06/588.00MiB。0失败、0重试、0正式训练。

### 66.9 新发现：F命名政策尚不能消除捷径

# F 选择性 idN 改名的残留标记风险

记录者：codex。本审计只创建本目录新证据，不修改 F 计划/特征、原图/标签、旧改名映射或运行中 B/C worker；无模型前向、无训练。

**已确认：只将注入标记名换成 idN，并没有消除可识别的注入标记类别，而是产生了新的规则性名称族。** F 的现有 feature_view.py 直接复用冻结 8C replacement_map/rewrite_code：仅 txorigin/re_ent 标记名称被改为 id0、id1……，普通名称不改。跨 train/val/test 一致执行可以消除“只在测试集改名”的分布差异，却仍允许模型重新学习 idN 与注入标签的相关性。按克隆组划分也不会自动消除这种跨组规则。

## 证据与复核

本审计读取 A_v2 精确作用域、旧 8C 的100份推理报告映射、原始图 code、已冻结源文件与 node_views。所有剖面的同文件映射必须一致；逐文件检查原 source SHA、映射与旧结果一致、idN 无命名碰撞。全部19,746节点的原 code 改写必须等于 A_v2；函数原文本由冻结 function_compat_span 从同一预处理源码提取，再核对改写后的精确文本，未用反向猜测或近邻行号。

识别规则为完整标识符 id[0-9]+（对应 idN 名称族，排除注释、字符串和长标识符中的子串）。原源码、原节点 code、原函数文本中此类名称均为0；所有新增命中都可追溯到标记名映射，未发现自然存在 idN 的混杂。

|任务/来源|文件身份数|新增名称数（按文件计）|原源码 idN 次数|改名后源码次数|改名后节点 code 次数|OR命中节点|
|---|---:|---:|---:|---:|---:|---:|
|访问控制/SolidiFI|40|2222|0|3333|7777|3160|
|访问控制/nonSolidiFI|17|0|0|0|0|0|
|重入/SolidiFI|40|2585|0|5517|14790|6860|
|重入/nonSolidiFI|31|0|0|0|0|0|

节点 code 计数可能重复原源码内容（例如容器/函数节点包含子语句）；不等于独立源码位置。文件身份总计128，含同名不同任务的独立身份；其中SolidiFI80。

## 无学习基线

预测：当前节点或其 AST 所属函数出现任意 idN 就预测正例。分别导出 node_text、function_text、OR；原始文本、改名后文本、仅新引入名称三个视图均保留。下表为改名后 OR 的 pooled HCG节点指标，不是等权折均值。orig/C1/C2 原样复用冻结诊断标签/掩码，不宣称 C1/C2 为真值。

|任务|来源|标签|评分节点|BF1|Precision|Recall|TN/FP/FN/TP|
|---|---|---|---:|---:|---:|---:|---|
|访问控制|SolidiFI|orig|7191|95.733203|92.658228|99.019276|4002/232/29/2928|
|访问控制|nonSolidiFI|orig|519|0.000000|0.000000|0.000000|499/0/20/0|
|访问控制|SolidiFI|C1|7191|97.952655|96.898734|99.029754|4001/98/30/3062|
|访问控制|nonSolidiFI|C1|519|0.000000|0.000000|0.000000|499/0/20/0|
|访问控制|SolidiFI|C2|7025|99.983625|99.967256|100.000000|3971/1/0/3053|
|访问控制|nonSolidiFI|C2|264|0.000000|0.000000|0.000000|244/0/20/0|
|重入|SolidiFI|orig|10891|97.589012|95.291545|100.000000|4031/323/0/6537|
|重入|nonSolidiFI|orig|1145|0.000000|0.000000|0.000000|1112/0/33/0|
|重入|SolidiFI|C1|10891|99.199177|98.411079|100.000000|4031/109/0/6751|
|重入|nonSolidiFI|C1|1145|0.000000|0.000000|0.000000|1112/0/33/0|
|重入|SolidiFI|C2|10755|99.977786|99.955582|100.000000|4001/3/0/6751|
|重入|nonSolidiFI|C2|1051|0.000000|0.000000|0.000000|1019/0/32/0|

原文本 idN 规则全部预测负例；改名后与“只检测新引入名称”规则逐节点完全相同。已独立用混淆矩阵重算全部108行 BF1，误差低于1e-12。规则无需训练便在SolidiFI C2上达到访问控制99.983625、重入99.977786，而非SolidiFI始终为0。

这证明 idN 变体仍有强烈的合成注入可识别性；**不证明某个 GNN 训练后一定取得上述分数**，也不是未来分组折中的正式成绩。函数 OR 使用完整词法作用域，不能等同于任意模型有限层消息可见范围；仍需保留 node_text/function_text 分解。C2排除了部分节点，不能把接近100的值当成未筛选任务性能。

## 对现有 F 计划的影响

- 现有准备产物应解释为“选择性标记名替换后的分组基准”，不可解释为已剔除全部注入词法捷径的基准。
- 旧8C测试时干预仍可用于判断原模型对原始标记拼写/特征的敏感性；本风险不否定已冻结的诊断结果。
- 若后续研究目标是去除标记捷径，应先向用户说明该风险并确认新的、对普通名称与注入名称一致适用的方案及审计标准。不得在已封存F计划内静默修改映射或重生成特征；本审计未实施任何替代方案。
- 在该决定前，不能用原有“中性化”措辞暗示已经完成 shortcut-free 验收；仍需明确标签视图、seed、执行位置和训练授权。

本目录提供 audit.py、risk.json、pooled_metrics.csv、file_counts.csv、totals.csv。本结果不使用 GPU，不影响运行中300次推理。

复现（已有产物拒绝覆盖）：

    cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. CUDA_VISIBLE_DEVICES='' python -B scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F_naming_risk/audit.py

risk.json SHA256：335c349c222d0b171df7cc0871e1a066a5debfd3dc2fda2bbc0fb11fda267537
脚本 SHA256：5fb557bc560a526a6dfd338e8b90c475ed142bc3e0d9ea4839d6b1ff80740d8a


### 66.10 A/D/E及F完整验收

## 本轮范围与最重要结论

日期：2026-10-29；实施与核验：codex。起点为 `dfg-v2@dd70fb966b64df43ac9e75a6f94f0b675fcaa593`。本轮按更新后的共享上下文及 Prompt 8D开展原因诊断，复用既有模型与结果；新增代码在 `diagnostics8d/`、`benchmark_v2/`，新产物独立保存于 `prompt8d_v1/`。原 DDG、HGT、tokenizer、训练器、作者标签、旧图、旧划分及150项正式拟合不变。

**本轮最需要影响下一步决策的发现是：F 只把注入标记名换成 `id0/id1/…`，仍然留下非常容易识别的注入名称类别。** 全部训练/验证/测试一致改名，解决的是只改测试输入造成的分布差异，并不自动消除可学习的标记捷径；按近重复组划分同样不能消除跨组共享的名称规则。因此，F 的工程准备已完成，但“去除泄漏成功”的研究前提未成立。170次正式拟合尚未执行，也没有据此形成新的性能结论。应先说明风险并取得用户对替代方案的批准，不能在已封存计划内静默改名或重建特征。

A/D/E均已完成。B/C的最终模型推断数字在本报告相应结果部分单独列出；本节不以早期单折结果代替完整批次。节点指标按原 HCG 节点身份计算，不是注入点个数，也不是按文件与源码行去重后的指标；`env_source`不参加标签评分。同名文件必须携带任务、来源及source SHA身份。

## A：节点自身文本和所属函数上下文的影响

A只读复用8C的100项节点级best预测，按orig标签重新分层，无新前向或训练。三层互斥，优先a：a为当前节点code实际被改名；b为节点code不变但AST所属函数名改变；c为其余节点。函数归属按精确AST身份，不能按文本包含、最近行或图连通性代替。

最终访问控制7710节点（普通AST7495、合成控制节点215）、重入12036节点（10977、1059）全部完成归属，未解析0。初次审计遗漏38个synthetic else-if节点，原因是原图用根if起始行配合末端else-if代码。仅在新增审计器复用原构图的`return_if_root`身份规则补齐；未改图、标签或模糊匹配。初次产物保留，最终使用独立[A_v2](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/A_v2/stratification.json)。

下表仅SolidiFI、orig标签，数值为全部折预测拼接的pooled BF1（%），不是等权折均值；“改名后”为旧8C的idN输入干预。

|任务/剖面|a层节点/正例|a层BF1 原→改名后|b层节点/正例|b层BF1 原→改名后|b层预测翻转|
|---|---:|---:|---:|---:|---:|
|访问控制G0|2328/2133|97.5677→7.6646|832/795|97.7259→22.7074|711|
|访问控制G3R|2328/2133|97.1666→3.7718|832/795|97.7259→28.1481|682|
|重入G0|5678/5393|98.0324→14.4475|1182/1144|98.1912→90.8163|166|
|重入G3R|5678/5393|98.2562→17.8427|1182/1144|98.3663→90.8839|165|

访问控制b层节点自身输入不变，却发生大量翻转，说明影响不限于当前语句文本，图内上下文敏感性已有实际证据。这不能确定某一种边是唯一传播路径，也不能把差值当成DDG语义的纯因果贡献。8C idN同时改变token值、长度和后续位置；B/C继续区分这些因素，但其匹配也有暴露差异。c层两任务均4031节点，访问控制仅29正例、重入0正例；其低BF1应结合组成和误报解释。

## D：作者附带漏洞行集合的来源核查

D固定SolidiFI提交`4b0573e1b3f7031396de6f48f7f3e7380222ad3a`，读取重入、tx.origin各50份源码及CSV，逐份绑定SHA，共100对。按冻结8C的`[loc,loc+length-1]`规则展开并换算坐标；旧8C覆盖的80份文件换算集合逐条一致。

查询是作者正例节点附带的`annotation.lines`并集，**不是正例节点自身源码行的集合，更不是正例节点数量**。分别与同类50份CSV换算集合、合约图和节点图的正例节点端点集合比较；节点`[start,end]`只取两个端点，未扩成区间。

|焦点文件|附带行数/最高行|CSV最近候选/Jaccard|本文件CSV Jaccard|buggy_24 CSV Jaccard|本文件正例端点Jaccard|
|---|---|---|---:|---:|---:|
|重入buggy_18|82/840|buggy_39、49 / 0.225564|0.120235|0.063361|0.475610|
|访问控制buggy_18|46/687|buggy_32 / 0.180952|0.134503|0.053763|0.489362|
|访问控制buggy_26|47/687|buggy_26 / 0.269231|0.269231|0.064865|0.583333|

三个焦点在合约图、节点图的端点候选中均以本文件为第一。预先按任务轮转和数字ID选出的5个非截断对照，其附带行与本文件CSV映射均J=1.0，为提取与坐标复用提供检查。

没有证据认定异常集合误拷自buggy_24。重入buggy_24最高行恰好840，但与重入buggy_18仅交集23、并集363；访问控制buggy_24最高行686，也不等于687。当前只能确认这些作者附带集合与公开CSV换算不一致，不能恢复唯一历史原因。本轮未修正作者标签或删除困难文件。详见[D行来源报告](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/D/line_provenance.json)。

## E：去除原标记拼写后的无学习规则

E使用冻结8C idN文本，排除注释、字符串后，访问控制检测`tx.origin`；重入检测`.call.value(`、`.send(`、`.transfer(`，允许空白。主规则为“节点或所属函数文本命中”，另存两者单独结果。它不训练、不选checkpoint、不调阈值，也不声称send/transfer必然为漏洞或已完成所有成员调用绑定。

|任务|来源/标签|评分节点/正例|BF1（%）|Precision（%）|Recall（%）|
|---|---|---:|---:|---:|---:|
|访问控制|SolidiFI/orig|7191/2957|95.6238|92.4534|99.0193|
|访问控制|SolidiFI/C1|7191/3092|97.8431|96.6846|99.0298|
|访问控制|SolidiFI/C2|7025/3053|99.8692|99.7386|100.0000|
|访问控制|nonSolidiFI/orig|519/20|14.2857|25.0000|10.0000|
|重入|SolidiFI/orig|10891/6537|85.0708|89.7031|80.8934|
|重入|SolidiFI/C1|10891/6751|86.3672|92.6378|80.8917|
|重入|SolidiFI/C2|10755/6751|87.0973|94.3341|80.8917|
|重入|nonSolidiFI/orig|1145/33|18.1269|10.0671|90.9091|

这是pooled HCG节点指标，不是折均值。结果说明合成注入标签有很强的词法与函数范围可预测性；非SolidiFI并未呈现相同表现。重入非SolidiFI的高Recall伴随低Precision，不能只报召回。C2进行了评分筛选，访问控制99.8692不能作为未筛选原任务成绩。C1/C2仍是诊断视图，未被确立为真实漏洞标签。Precision/Recall给Wilson描述区间，F1不套Wilson，节点相关性仍限制解释。详见[E规则与完整指标](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/E/keyword_baselines.json)。

## F：分组基准的准备结果与新发现的命名风险

F新协议为`dfg-v2-grouped-nested-v1`：外层合约5折、节点10折，各外层训练部分再固定inner train/val；inner val用于早停和best选择，outer留作最终评分。它有独立计划与目录，不覆盖或冒称原paper_kfold结果。完整固定图前向仍是transductive。

已将256个源码身份并为227个已知精确/近重复连通组，保留所有单例和样本。分组优先于完美分层，不更换seed挑结果。

|任务|文件|组|外层折|
|---|---:|---:|---:|
|重入合约|142|124|5|
|访问控制合约|114|107|5|
|重入节点|71|57|10|
|访问控制节点|57|52|10|

全部30折的inner train、inner val、outer test组间隔离，每个文件恰好一次outer，合约每个部分均含两类。已知文本克隆隔离不等于消除所有模板、语义相似性或跨组注入规律。

准备的170任务为5剖面×30折=150，加G0P×20个节点折。G0P延续8C的空关系分母对照，保留G0节点、不新增env_source；未假设旧CLI已支持该新计划。`execution_authorized=false`，实际标签/seed/位置均为空；默认建议L-audit、seed1不等于授权。新初值及feature/label/split/G0P执行绑定还需明确接入与测试，不存在现成可直接执行170次的新训练命令。

标签策略：

- L-orig保留冻结作者target。
- L-audit使用C1 target，并把C2排除项从loss及主评分掩蔽；不删除图节点，不把它们改成负例。重入掩蔽230、访问控制421节点。
- 两者都另报全部原HCG评分节点的orig辅助指标，包含被L-audit掩蔽者；合约标签始终不变。标签支持和计划要求已准备，尚未有新执行器运行验证。
- 各任务LR/Adam/OneCycle/50轮/patience7/delta0.001及最低inner-val-loss选best沿用实际配置；last独立。Holm比较族保留原定义，所选标签为主、orig为辅助，不能择优混报。

工程上，全部原HCG节点的51490行原始/选择性idN特征均独立重新编码一致，20个profile绑定、40次原/改名图装配检查通过。特征仍是512维浮点存储的tokenizer ID序列，不是CodeT5隐藏状态；未改变原tokenizer或HGT。只对深复制NX图绑定独立token视图，原磁盘图、节点、标签、边和其他属性不变，env及非SolidiFI特征保持原样。

但新增只读风险审计确认：原源码、原节点和原函数文本中的完整标识符`id[0-9]+`均为0；选择性改名后，访问控制新增2222个文件内名称、源码出现3333次，重入2585个名称、出现5517次。它们全部源于注入标记映射，普通名称没有同步改名。节点或所属函数出现idN就预测正例，无需训练得到：

|任务|SolidiFI orig BF1|C1 BF1|C2 BF1|C2 TN/FP/FN/TP|
|---|---:|---:|---:|---|
|访问控制|95.7332|97.9527|99.9836|3971/1/0/3053|
|重入|97.5890|99.1992|99.9778|4001/3/0/6751|

两任务nonSolidiFI该规则BF1始终0。108行指标已从混淆矩阵独立复算。这证明规则性新名称仍携带强烈注入身份信息，不证明某GNN重训后必然达到这些分数；函数OR可见完整词法范围，也不能等同于有限层模型的可见范围。C2筛选限制同样适用。

因此，[F独立复核](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F_final_review/review.json)的通过仅指输入、分组、标签mask支持和实现绑定正确，**不构成对“去捷径基准”研究有效性的验收**。后续[F命名风险报告](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F_naming_risk/CAVEAT.md)补充了这一实质限制；原F计划、seal和特征未被改写。可以考虑对普通及注入用户标识符一致适用、带声明绑定与碰撞核验的规范化方案，但这会改变已冻结输入，必须先征求用户并建立新版本。本轮没有擅自实施替代方案。

## 数值验收、保护与剩余边界

特征接入等价验收使用真实重入节点G0，原路径与恒等视图各1个CPU epoch，共2次optimizer更新、0次正式拟合。前向、loss、模型参数、Adam及scheduler数值、预测完全一致；train loss均0.6978223323822021，inner-val loss均0.6693451404571533。初次报告仅因反序列化bound-method实例地址不同判失败，原件保留；后续核对实际`__func__`实现与数值字段，用同一保存checkpoint复核通过，额外更新0，没有放宽数值容差或重训。证据见[等价复核](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/equivalence_review/equivalence.json)。

F独立复核检查334个引用摘要及全部30划分，并再次独立重新编码所有特征。全项目本轮最终测试2643个唯一用例通过（v2 2420、旧项目223），0失败/错误/跳过；两套分别8/29条既有DGL/NetworkX弃用警告。初次2403项v2通过记录保留但不重复累计。文档更新前保护核验4071个历史引用、298份历史运行源码，差异0、旧受保护tracked改动0，见[保护核验](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/protected_pre_documentation.json)。

本轮没有新增正式训练、多seed、其余五类、关系扩展、作者标签修改或新的solc验证。先前512/111条人工依赖审查未在本轮补齐，不能声称完整Solidity DDG已验证。已有checkpoint输入干预揭示敏感性，不能代替改名后重训性能；pooled结果、折均值、诊断标签及外部泛化应分别解释。

用户已说明最终实验会在显存充足的服务器运行，当前RTX3050 4GiB限制只针对本地开发。服务器型号、软件栈与实际性能尚未核验，不能据此承诺耗时或混合本机/服务器结果。历史本机中位耗时推算170任务约8.2791小时，只是未含编排与变化早停的参考；1x/2x/4x服务器情景约8.279/4.140/2.070小时，均非实测。

当前应先确认F新的命名方案及验收标准，再明确标签策略、seed集合和执行位置，封存新执行版本并补接入测试。已准备的[计划/seal与命令记录](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/execution_command.json)保留；生成命令拒绝覆盖已有F目录，查看应使用只读核验。不能因准备完成而自动启动170次拟合，也不能把旧诊断中的高F1直接作为DDG泛化已获证明的结论。


### 66.11 收尾记录

实际命令完整记录在diagnostics8d/README.md和benchmark_v2/README.md。300份推断收据、指标重算及非SolidiFI不变核验通过。4071历史引用和298计算SHA一致，三份文档旧正文只保留并追加。新增代码14模块、7组测试、2README及报告；不提交大权重或改变旧归档。F170仍未授权，命名策略需先讨论、标签/seed/位置尚未选定。本轮本地commit，不自动push。


Actual test commands in the existing mando environment (PYTHONDONTWRITEBYTECODE=1, OMP/MKL=2, existing TREE_SITTER_LIB_DIR):

    CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py


### 2026-10-29 Prompt 8D GitHub结果归档（Codex）

按用户推送请求，在5f31a66代码/报告提交之后，追加1176个Prompt8D文本结果和证据文件（约431.50MiB），覆盖300推断、汇总、审计、测试、候选分组计划及idN命名风险；文件清单见docs/github_archive_prompt8d_2026-10-29.json，说明见同名.md。原文件逐字节保留，4个CPU验收checkpoint和14个特征NPZ留在本地，不修改旧seal/图/标签或重跑模型。三份文档只追加。本次WSL Git直接连接GitHub已成功，正常推送dfg-v2，最终以本地/远端SHA核验一致为完成依据。F170仍未授权，命名替代方案尚需讨论。最终实验使用显存充足服务器的安排保持，当前本机限制与服务器结果不混用。


## 67. 2026-10-29 Prompt 8E：真实名称替换与泄漏门槛验收（Codex）

本节为详细实施记录。用户已批准的接口调整选择为“同意使用仅供验收的内存副本（推荐）”；没有批准改变名称池、门槛或失败后重测。源代码/诊断完成与基准可训练性分别验收。

日期：2026-10-29；修改 AI：Codex。分支：dfg-v2；起始 HEAD：70a37495f800f994812714c0c811a3a3d5a9dc87。

**结论：N-real 的代码、源码/事实核验和命名探针已执行，命名验收未通过，按 Prompt 8E 停止。没有生成可训练的新 170-fit 计划，没有正式训练。** 这不是“全部 8E 后续步骤已经通过”，也不是 DDG 模型的新成绩。

产物目录：[prompt8e_v1](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/)。
验收记录：[acceptance_decision.json](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/acceptance/acceptance_decision.json)；
完整探针：[summary.json](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/probes/summary.json)；
实际命令：[PROMPT8E_README.md](../scripts/DFG/dfg_v2/benchmark_v2/PROMPT8E_README.md)。

### 67.1. 范围与已批准的接口调整

先读取最新 §4.1、Prompt 8E、8D/F 计划与源码；本轮开始的 git pull --ff-only origin dfg-v2 返回 Already up to date。

新增五个旁路模块：

|文件|职责|
|---|---|
|benchmark_v2/real_names.py|七类角色名称池、证据、按出现频率加权的确定性映射、无碰撞与语法核验|
|benchmark_v2/prepare_real.py|绑定 128 份源码、A_v2、旧分组折；预先封存名字和探针定义，执行三个视图|
|benchmark_v2/leakage_probes.py|P1、inner-train 名字记忆 P2、按文件/已知重复组隔离的字符 LR P3|
|benchmark_v2/rename_parity.py|临时 code 改写副本，复用冻结分析器，核验归档/原文/改名事实与端点|
|benchmark_v2/acceptance_real.py|从逐节点预测重算指标、独立秩公式重算 AUC，失败关闭的验收记录|

新增两组测试、独立 README、本报告；三份旧记录只追加。原 DDG/HGT/tokenizer/训练器、图/节点属性/边/标签、特征、分组折及历史结果均不修改。未修改 PROMPTS.md。

**用户批准：** L2/L3 会严格核对源码与 HCG code，改名源码直接配原图会报文本不一致。用户明确同意仅创建内存验收副本，只改副本 code，保持初始节点、边、标签和 token 不变，复用原分析器检查后丢弃。验收过程中依赖层的临时输出也不落盘、不作为训练图。本轮没有重新生成原 CFG/CG。

旧 8D/F plan、seal、特征保持字节不变；“superseded”仅记录在新目录 naming/supersession.json。旧文件本身没有改状态。N-real 失败不使旧 idN 方案重新获得可训练资格。

### 67.2. 名称池、固定映射和语法

128 个源码身份：重入 71、访问控制 57；其中两类各 40 个 SolidiFI 文件。以 source SHA 区分同名文件。沿用 A_v2 精确函数 AST 作用域，所有归档的注入函数范围均有精确匹配，额外仅 AST 可见而旧图无对应的注入函数数为 0。

|角色|可用普通名称数|
|---|---:|
|合约函数|414|
|modifier|34|
|事件|95|
|状态变量|231|
|参数|372|
|局部变量|141|
|结构体字段|112|

名称必须有注入范围外的对应角色声明证据，出现频率按注入范围外词法出现次数计。相同拼写具有多个普通声明角色时分别计入有证据的角色池，不声称实现了所有引用的绑定解析。排除关键字、内建/全局名称、txorigin/re_ent 以及 idN。字段正确采用当前 grammar 的 struct_member；初步开发清点漏了该节点类型，定向测试前已补齐。未受影响的四类实际标记映射没有因此变更；早期清点文件保留为开发记录，不作为正式封存输入。

全部 4,807 个文件内标记名（重入 2,585，访问控制 2,222）成功映射。按文件 source SHA 和版本串导出随机种子，固定排序后整数权重抽样；同文件一对一，排除文件中全部已有标识符。没有追加后缀冒充真实名称，也没有耗尽池后静默回退。不同文件合计使用 872 个不同替换拼写。

80 个改写文件均通过冻结 grammar：ERROR=0、missing=0；函数/modifier/状态声明数量一致，完整 AST 节点类型与拓扑一致。非 SolidiFI 源码不改，字符串和注释内同形内容不改。

这只是语法和当前分析器支持域的验证；未运行 solc。公共函数名变化会改变外部 ABI 拼写，因此不宣称重写后合约具备完整部署行为等价性。本任务准备的是输入特征干预，原始合约文件没有被修改。

### 67.3. L1/L2/L3 事实与投影核验

在四个任务分别检查 40 个 SolidiFI 文件，共 **160/160** 通过：

1. 当前原文分析结果对归档 F3 证据；
2. 改名副本对当前原文分析结果；
3. 按未改变的 AST 拓扑建立严格字节坐标对应，将新符号拼写还原，仅作证据身份比较；
4. 比较证据多重集合、每函数支持状态/事实数、状态读写与环境键计数；
5. 原节点端点和关系逐项相等；env 端点按“文件＋环境键”比较，因为单文件临时分析的整数分配位置与全图不同；
6. 恢复临时 code 后，副本的原节点/边/标签/token 等全部属性指纹与输入一致。

|每类在单个检测粒度上的 40 文件|L1 原始事实|L1 投影证据|L2 证据|L3 证据|DATA_DEF_USE 边|READS_STATE 边|WRITES_STATE 边|ENV_FLOW 边|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|重入|3940|3567|4860|3425|2862|2724|1968|2923|
|访问控制|5522|5149|1789|2053|3853|945|676|1854|

同一类别的合约图和节点图都得到表中数值。事实、投影证据、去重边不是同一计数单位。表只覆盖发生改名的 40 个文件，不冒称整个任务总数。

事实量和证据保持说明本次重命名没有破坏当前已实现的依赖层；它不证明当前 DDG 已完整覆盖 Solidity，也不保证名称分布已消除预测线索。

### 67.4. 预先封存的探针定义

在查看任何探针分数前封存 naming/manifest.json、manifest.seal.json、映射和 probe_protocol.json。三视图共用同一协议，没有根据结果选择替换名、调整随机种子、参数或门槛。

- **P1**：替换拼写必须在普通名称池中有原始源码证据；同时分别统计替换名、全部池名称和未被选中池名称在注入/普通区域的词法出现比例。
- **P2**：支持数是“出现该拼写的不同 HCG 节点数”，同节点出现多次只计一次。只从旧分组折的 inner-train 学习；support≥3 且正类占比≥0.5。outer 节点自身或精确所属函数包含正类名即预测正。orig 与 C1 分别从对应 inner-train 标签学习。门槛按每任务/标签的 SolidiFI pooled OOF 比全正基线高不超过 5pp，另存全部逐折结果。
- **P3**：独立诊断分类器，样本为去重的“文件/角色/名字/注入声明状态”。区分注入作用域中的用户声明（包括未带原标记的声明）和普通声明，不把重复引用当成独立样本。沿用旧重复连通组身份，GroupKFold 5 折；char 2–4 gram、大小写保留；TF-IDF 只 fit 训练组；LR C=1、liblinear、balanced、max_iter=1000、seed=1。门槛为全部 128 文件 pooled OOF AUC≤0.60；每类别 AUC 另报。
- P3 共 3×5=15 次 CPU 逻辑回归拟合；HGT 正式训练、前向和 optimizer 更新均为 0。单元测试中的小型模型计算不属于新实验。
- 名称池按文档使用全部 128 文件，包含 outer 文件的无标签词汇；这是预先固定的 transductive 词汇准备，不能称未知词汇/外部数据泛化测试。
- P2/P3 是命名线索诊断，不等同于证明训练代码直接读取了 outer 标签；本轮源码构造不读取标签。

### 67.5. 探针实际结果

P1：原名、idN 的普通名称证据率均 0；N-real 为 **872/872=100%**，通过。N-real 中替换拼写共出现 31,218 次，注入区域 11,284 次，占 36.1458%；全部池名对应比例为 35.5988%，未选中池名为 32.2856%。100% 普通来源不意味着两个区域中的分布完全相同。

下表为 **SolidiFI pooled HCG 节点 BF1（%）**，不是 HGT 训练成绩、不是等权折均值，也不是去重源码行指标：

|任务/标签|全正基线|原名 P2|idN P2|N-real P2|N-real−全正（pp）|验收|
|---|---:|---:|---:|---:|---:|---|
|重入/orig|75.0172|95.1598|95.0834|64.7050|−10.3122|通过|
|重入/C1|76.5333|96.7677|96.7677|67.8373|−8.6960|通过|
|访问控制/orig|58.2775|85.0348|85.0348|67.7445|+9.4670|未通过|
|访问控制/C1|60.1381|87.2138|87.2138|69.4994|+9.3613|未通过|

|N-real P2|Precision（%）|Recall（%）|TN/FP/FN/TP|
|---|---:|---:|---|
|重入/orig|62.6127|66.9420|1741/2613/2161/4376|
|重入/C1|65.4636|70.3896|1633/2507/1999/4752|
|访问控制/orig|55.4074|87.1491|2160/2074/380/2577|
|访问控制/C1|57.6203|87.5485|2108/1991/385/2707|

P3 使用 10,347 个声明身份样本：

|视图|总体 AUC|重入子集 AUC|访问控制子集 AUC|
|---|---:|---:|---:|
|原名|0.999430|0.999808|0.999030|
|idN|0.998474|0.998750|0.998179|
|N-real|**0.643159**|0.666356|0.617017|

N-real 已明显削弱字符可识别性，但仍高于预先规定的 0.60。因此 P2 两项和 P3 一项阻断，未重采样或调参重测。

独立复核从导出的节点身份、冻结标签和分组 outer 名单重新核对，重算 12 份 P2 总表和 120 份折指标；P3 用与 sklearn 不同的 Mann–Whitney 秩公式重算三份 AUC，全部一致。复核通过表示结果可信，不代表验收门槛通过。

### 67.6. 关键字基线

N-real 下重新计算“节点或函数”规则，数值与旧 E 一致，因为内建环境和调用拼写没有改动：

|任务/SolidiFI 标签|BF1（%）|Precision（%）|Recall（%）|
|---|---:|---:|---:|
|重入/orig|85.0708|89.7031|80.8934|
|重入/C1|86.3672|92.6378|80.8917|
|访问控制/orig|95.6238|92.4534|99.0193|
|访问控制/C1|97.8431|96.6846|99.0298|

非 SolidiFI 只作 pooled 描述：重入 TN/FP/FN/TP=844/268/3/30，访问控制=493/6/18/2。原始机器记录保留 P/R/F1 供核算，但不把这些小子集当作足量独立泛化实验证据。

这些关键字具有语义含义，但仍只是词法规则；调用出现不等于真实漏洞被确认。C1 是诊断标签假设。本轮没有调整作者标签，也没有把这些基线变成训练标签。

### 67.7. 停止位置与未执行事项

当前状态：blocked_by_preregistered_leakage_gate，execution_authorized=false、ready_for_training=false。

已保存：名称池/固定映射/封存协议、160 项事实核验、P1/P2/P3/关键字明细、独立复核、acceptance_decision/seal、不可据此开训的 authorization_template。

**未执行：**

- N-real 全 HCG TokenEncoder 重编码、NPZ 特征生成、恒等/新视图装配验收；
- 新 170-fit 可运行计划及其 seal；
- N-anon；重新抽样名字、改阈值、再跑另一套探针；
- 新 HGT 拟合/新 seed/其余五类漏洞/新依赖关系或模型模块；
- 新编译验证。

这些后续步骤因文档明确的失败停止条件而未开展，不能把本轮 decision seal 当作训练 plan seal。旧 170 任务、分组折、标签方案和耗时参考被只读引用，没有扩大或替换其授权。旧本机中位耗时估算仍约 **8.2791 小时/170 fit**，不是 N-real 实测，也不是当前可以启动的承诺。

预先登记的解读规则保持：访问控制节点只作描述；主 DFG 依据为重入节点和两类合约；非 SolidiFI 只报 pooled 计数。即使之后允许 N-real 继续，它也应明确称“真实名称替换的敏感性/稳健性基准”，不能在门槛失败后称已去除命名线索。

若讨论替代方案，可讨论对普通及注入标识符一致适用的 N-anon 或重新界定研究问题；本轮没有擅自选择或实现。先讨论新协议及验收定义，再决定标签方案（文档默认建议 L-audit）、seed 数和位置，不能反复挑名称直到过门槛。

### 67.8. 测试、历史保护与记录

- 定向 27 项通过，包含七角色、无碰撞、确定性、AST 语法、P2 inner-train 隔离、P3 组隔离、证据/边篡改拒绝。
- 全部 v2 2,447 项通过；随后新增验收防篡改/边界测试 8 项通过。唯一 v2 测试共 2,455。
- 原项目回归 223 项通过。合计 **2,678**，失败/错误/跳过均 0；全 v2 与旧套件分别 8/29 条既有 DGL/NetworkX 弃用警告。首次 24 项和随后 27 项定向运行不重复累计。
- 337 个旧计划/源码等绑定引用核验通过；历史实际运行版本采用已批准 8B.0 amendment 后的 298 文件摘要，差异 0。
- 首次直接比对初始 Prompt 8 plan 的 294 文件列表时出现四个已存在的 8B.0 修订文件差异；初检原件保留，随后明确改用归档的真实运行版本核验。不是本轮修改旧训练器，也未改旧 seal 来迎合检查。
- 起始 HEAD 的既有 tracked 代码不变；三份旧文档保留原字节前缀后追加。新增模块和测试位于指定目录；本地源码/报告提交，不自动 push。

本轮仍未完成此前 512/111 项人工依赖核验，也不宣称实现完整 Solidity 语义。用户安排最终正式实验在**显存充足的服务器**完成；当前 RTX3050 4GiB 是本机开发限制。服务器配置与环境尚未实际验收，不能混合两处运行结果或把历史本机耗时当成服务器实测。

详细运行命令保存在 scripts/DFG/dfg_v2/benchmark_v2/PROMPT8E_README.md；各执行 argv 和输出日志保存在 prompt8e_v1。正式训练次数 0，P3 诊断 LR 15 次，二者不得混淆。本轮未自动推送 GitHub。


### 67.9. 2026-10-29 GitHub 代码与结果归档（Codex）

用户要求“推送github”。先核验当前 dfg-v2、本地代码提交 96aa742060cb4e9aad760ab57d4bc0bb6ebd577f、远端 70a37495f800f994812714c0c811a3a3d5a9dc87，tracked 工作区干净且暂存区为空。确认目标为用户拥有的私有仓库 cappuccinnuo/ge-sc-llm-private，具备 push 权限；作者 upstream 不作写入目标。

本次仅追加归档与文档，不改计算代码、不重跑实验。prompt8e_v1 共 64 个 JSON/日志，101824681 字节，逐文件 SHA256 和范围见 docs/github_archive_prompt8e_2026-10-29.json；无需压缩，文件均小于 16 MiB。包含早期开发证据、最终命名映射、160 项语义核验、P1/P2/P3、关键字规则、独立重算、acceptance_decision、测试日志和本地提交收据。历史 pushed=false 收据保留原字节，表示其生成时尚未推送。

归档检查：UTF-8 解码、JSON 解析、常见凭据模式检查通过；名称 manifest、探针 summary、验收 decision 的三份 seal 对应 SHA 核验；暂存 blob 对照归档清单逐项复核。三份旧文档只追加。旧图、标签、token、权重、计划、seal 和结果未重写；无关未跟踪文件不纳入本次提交。实现阶段 2678 测试通过的记录保留，本次不把格式/SHA 检查算作新增模型测试。

目标仅 origin/dfg-v2，正常非 force 推送，并以实时远端 SHA 等于本地 HEAD 验收完成。命名验收仍为 blocked_by_preregistered_leakage_gate；没有将停止决定改为训练计划，没有生成新 NPZ/权重或执行 170-fit。最终实验使用显存充足服务器的安排保持，本机资源限制不改变实验协议。


## 68. 2026-10-29 Prompt 8F：声明绑定 N-anon 与全语料一致性核验（Codex）

### 68.1. 请求、起点和实施范围

用户要求按更新后的PROMPTS.md先读§4.1，再执行§4.10g Prompt8F；替代设计须先征求用户并记录。另要求清理本轮生成的无关数据，以及注明最终实验会在显存充足的服务器运行。

起始HEAD为a204ba16b3800f999ea0f096bf54eccc82db748a，分支dfg-v2；git pull --ff-only origin dfg-v2返回已最新。初始tracked工作树干净。before.json保存683个既有源码/文档SHA；原模型、训练器、图、标签、token、冻结折及历史seal不改。

本轮实施绑定、改名、源图事实核验和明确停止入口；未因部分成功而生成可执行训练计划。所有新增逻辑在scripts/DFG/dfg_v2/benchmark_v2，实验证据在scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1。

### 68.2. 两项先征求用户的选择

1. 真实语料有51处旧式构造函数：contract C与function C必须同名。文档的“每声明独立编号”直接用于这两者会改变语义。用户批准构造函数名称作为所属合约的绑定引用，共用合约匿名名；其他可确认声明仍独立编号，不自行扩展重载和覆盖规则。
2. 全256个身份预检有159个整文件回退。原文保留会形成部分匿名、部分原名的混合视图。用户批准“先完成核验，回退阻止全量计划封存”，因此先保存全部来源与失败证据，阻止P2/P3、特征和170-fit新计划。不得删样本、把原名回退算作成功、或用小子集验收代替全量。

这两项不是执行时自行改规则；具体选择已写入naming/policy.json及接受决定。复杂绑定扩展另行确定。本轮没有通过调匿名名、换seed或修改门槛争取通过。

### 68.3. 文件与关键逻辑

|新增文件（相对scripts/DFG/dfg_v2）|修改目的与逻辑|
|---|---|
|benchmark_v2/anon_binding.py|受限声明/作用域解析、固定保留表、唯一字节绑定、确定性匿名排列、构造函数共名和无残留整文件回退|
|benchmark_v2/anon_parity.py|原HCG内存code副本、准确AST对应、归档/原文/改名三方L1/L2/L3数量/证据/端点比较|
|benchmark_v2/prepare_anon.py|names/semantic/decision入口；来源与seal核验；固定256源码/384任务引用；排他输出与全量停止|
|tests/test_prompt8f_anon_binding.py|18个绑定、遮蔽、成员、保留名、构造函数、碰撞及回退测试|
|tests/test_prompt8f_anon_parity.py|17个投影、语义字段规范化、篡改拒绝、源码绑定与完整性门槛测试|
|PROMPT8F_REPORT.md、benchmark_v2/PROMPT8F_README.md|结果、限制、批准记录、实际执行命令和禁止混合视图的使用说明|

HANDOVER.md、PROGRESS.md及本节只在旧正文后追加；不更改PROMPTS.md。没有改原DDG/HGT/tokenizer或既有训练逻辑。

匿名化以声明字节身份区分同名变量；作用域模式复用原版本证据，不将范围pragma伪装成确定编译器版本。有限支持同文件类型/成员、结构体具名字段、明确对象和using库扩展；覆盖/重载/未知receiver/super/assembly等不能证明时整文件回退。声明角色共用v前缀，source SHA派生固定随机排列，不按首次出现顺序编号，避开原文件已有vN。固定保留名含用户自定义transfer等同名项；保留清单与每文件计数可审计。

替换仅作用于绑定的identifier字节区间，字符串/注释不改；回退的rewritten等于原文、edits/bindings为空。不读取标签、预测或token决定绑定。当前解析器不是完整Solidity类型系统，tree-sitter通过不等于编译通过；本轮未运行solc。

### 68.4. 全量身份与绑定结果

256表示类别/文件/源码身份；同一源码用于合约及节点任务，384表示task×file引用。不能将二者当成相同分母。

|范围|源码身份|绑定可改写|整文件回退|依赖与投影通过|投影阻断|
|---|---:|---:|---:|---:|---:|
|重入|142|56|86|47|9|
|访问控制|114|41|73|40|1|
|合计|256|97|159|87|10|

97个可改写文件有4025个声明级匿名映射（各文件内唯一），9594处绑定替换。256份原文grammar无ERROR/missing；97份改名文grammar无ERROR/missing且AST拓扑相同。其余文件不计为匿名化成功。

97份成功改名的原/新关键字子串计数相同：msg.sender1172、tx.origin192、.call.value(140、.transfer(197、.send(102。这里只是字符串不变量，不是重新运行漏洞预测基线。

回退原因按“含该原因的文件数”统计，可重叠：覆盖/隐藏/重载107、引用绑定不唯一45、表达式类型不明37、super调度19、assembly17、版本证据不足/冲突8、复杂调用目标7、同作用域重复/重载6、遮蔽初始化4。unresolved_import_or_assembly类实际17个均为assembly，不能误报新增导入文件。这些表示转换器支持边界，不代表源文件已被证明错误。

两类各40个SolidiFI源码，均9个绑定通过、31个回退；重入这9个随后全部被合成节点投影阻断。不能据此宣称已覆盖重入注入数据，或用87个成功文件代替原256文件运行完整基准。

### 68.5. 图投影和依赖事实核验

|任务|task×file数|通过|绑定回退|投影阻断|
|---|---:|---:|---:|---:|
|重入合约|142|47|86|9|
|重入节点|71|21|41|9|
|访问控制合约|114|40|73|1|
|访问控制节点|57|24|33|0|
|合计|384|132|233|19|

通过132项同时要求归档、当前原文和改名副本的L1/L2/L3事实数量、规范化完整证据、投影端点/关系计数严格一致；原HCG fingerprint相同。副本仅在内存改code，恢复code后其他所有属性/节点/边完全相同；未写出正式新图或token。

原源码版本metadata先按source SHA核验；不得将其冒作改名源码的编译证据。改名临时分析只用未改的pragma，若因此支持范围或事实变化同样判失败。最终没有以放宽此条件保住通过率。

19项投影阻断对应10个独立文件、36个end_if/end_loop合成节点。此类节点没有保存唯一AST ID，同一原文本在多个函数中出现，声明不同则匿名名不同。例：重入buggy_15.sol原图节点17044的if(!success){revert();}有三个精确候选（兼容AST ID464/1114/1230），匿名success分别为v48/v2/v25，不能靠最近源码行猜选哪一个。

9个重入文件为buggy_15/19/2/29/3/39/49/6/7.sol；访问控制文件为0x00c8162c86a977edc10c641636bdff1c59327983.sol。projection_blockers.json保存完整类别、source SHA、节点、候选AST/行号和改写文本。这里是code副本映射失败，不是删除原CFG节点/边，也不直接证明原DDG事实错误。

### 68.6. 检查器开发修正与可追踪证据

旧8E的normalize_evidence可对所有字符串做逆名称替换；N-anon的v2恰好与固定analysis_path=v2冲突，导致把审计路径当匿名变量还原。新检查器借用原位置/env规范化，但inverse传空，仅在L1 symbol/definition末尾名称、L2/L3 state/statement的明确name字段恢复声明拼写。分析路径、角色、关系及其他证据不改。

首轮semantic_parity为68通过/233回退/83失败；中间semantic_verified为95/233/56；补齐状态初始化声明name规范化后semantic_final为132/233/19。剩余19均投影阻断，没有残留事实差异。变化来自新验收器修复，冻结分析器、标签和图未改；不是靠删除关键断言通过。

三轮目录均保留。implementation_snapshots及index.json保存早期/中间/最终实际模块内容和SHA，解决运行收据引用路径后来指向新检查器的问题；不重写旧manifest/seal。篡改端点/证据和审计路径测试确保新规范化没有掩盖这些变化。

### 68.7. 测试、首次失败和最终验收

最终定向35项通过。全v2最终2490项通过，8条既有警告；旧回归223项通过，29条既有DGL/NetworkX弃用警告。合计2713个唯一测试，0失败/错误/跳过，定向测试包含在全量中，不重复累计。

首次全v2为1886通过/603个fixture errors，旧回归204通过/19个fixture errors：原因是指定--basetemp的父目录遗漏。补建本轮临时父目录后完整重跑；未改断言或生产实现解决这些setup errors。首批日志和命令退出码原样保留。最终v2用时148.33秒，旧回归3.30秒；这是测试用时，不是训练时间。

采用既有mando、TREE_SITTER_LIB_DIR、PYTHONDONTWRITEBYTECODE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2、CUDA_VISIBLE_DEVICES=''。实际命令：

    python -B -m pytest -q -p no:cacheprovider --basetemp scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1/_test_tmp/v2_final scripts/DFG/dfg_v2/tests
    python -B -m pytest -q -p no:cacheprovider --basetemp scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1/_test_tmp/legacy_final scripts/DFG/tests tests/test_graph_utils.py

命令argv、环境、耗时、退出码分别保存在v2_final.command.json/legacy_final.command.json；定向结果见targeted_final。临时父目录已清理，复跑应建立新专用目录。README记录names→semantic→decision的确切命令及排他输出行为，不覆盖已完成产物。

### 68.8. 保护、清理、停止点和后续边界

追加文档前683个起始tracked源码/文档SHA一致，旧8E归档64个文件SHA一致；三文档追加前字节长度/SHA单独保存。原计算代码、PROMPTS及历史数据未改。完成文档后再校验旧字节前缀和冻结内容，收据保存在本轮目录。

按用户仅删除不重要自产数据的要求，删除本轮专用_test_tmp：20504个普通文件共214195220字节、737个临时链接；以及被正式逐文件命名清单取代的binding_development_audit.json（794648字节）。共214989868字节，约205.03MiB。先核验绝对路径位于本批目录且任务已结束，未跟随链接删除外部内容。cleanup.json保留路径、数量、原因和冗余汇总SHA。重要日志、失败证据、正式结果、旧实验、原源码及用户其他文件不动；未清理未知来源C盘文件。

最终acceptance/acceptance_decision.json及seal状态blocked_by_binding_or_semantic_gate；ready_for_probes、ready_for_training、execution_authorized均false。authorization_template不能用于启动；这不是新的170-fit plan/seal。

本轮没有运行P2/P3或分角色AUC、重新计算关键词预测基线、生成TokenEncoder NPZ、模型装配/恒等验收、新170-fit计划、HGT训练、编译验证。正式HGT拟合0、诊断分类器拟合0。旧170项矩阵、分组折、两种标签策略及约8.2791小时本机历史估算只读引用，不是新N-anon实测或已授权开训。

下一步建议先讨论有证据的同文件接口/覆盖声明共同绑定，以及合成节点能否凭原图结构证明唯一来源；不退回字符串替换，不扩展不确定绑定，不训练混合视图。即使这些通过，随机编号仍可能保留文件规模/声明数量信息，保留名仍存在，须继续按预定P2/P3门槛核验，不能先宣称消除了命名线索。此前512/111条人工依赖审查也不因本轮通过子集而视为完成。

用户计划最终实验放在显存充足服务器整批运行；当前RTX3050 4GiB只是本机开发限制。本轮停止原因是正确性，不是显存。服务器配置/环境尚未验收，不混合本机与服务器结果，不用历史本机耗时替代服务器实测。

按共享上下文完成源码、报告与三份文档的本地提交；本轮不自动push。新运行产物保存在现有WSL批次，推送归档另按用户指示进行。


### 68.9. 2026-10-29 GitHub 推送归档（Codex）

用户本轮明确请求“推送github”。先核验本地dfg-v2@9ab9080a886dfcb2cd604807d9572cf463d44989，tracked工作树与暂存区干净；实时远端为a204ba16b3800f999ea0f096bf54eccc82db748a。本地实现提交尚未推送，目标是用户私有origin（cappuccinnuo/ge-sc-llm-private），不向作者upstream写入。

追加归档prompt8f_v1全部322个JSON/日志/源码快照，共18097340字节（约17.26MiB），最大单文件684494字节。详单docs/github_archive_prompt8f_2026-10-29.json逐项记录路径、大小、SHA；同名.md说明范围。包括256源码命名结果、384任务文件最终核验、前两版检查及确切源码快照、36个合成节点阻断证据、测试/清理/完整性记录和停止seal。不修改原字节，不压缩替换原文件，不纳入其他批次未跟踪文件。

检查UTF-8、JSON解析和常见凭据模式（未匹配）；命名/语义/接受决定seal、256源码和逐文件决定、最终实现摘要、全部源码快照、64个旧8E归档摘要均核验。三份记录旧正文保持，新增归档说明。暂存严格限322个产物、两份新归档文档、三份记录追加；逐项比对暂存blob与清单再提交。源码和35个新增测试已含于9ab9080a；本轮不新增算法修改、不重跑2713测试或任何模型。

历史local_commit_receipt的pushed=false表示生成时未推送，保留原样；实时状态以push返回及远端分支SHA一致为准。正常非force推送origin/dfg-v2，不reset、不覆盖历史seal。当前仍87个源码通过、159个绑定回退、10个投影阻断，接受状态blocked_by_binding_or_semantic_gate，P2/P3、NPZ和新170可运行计划未做，HGT/诊断分类器拟合均0。不能将归档完成当作全量匿名化或训练门槛已通过。

最终实验按用户安排在显存充足服务器整批运行，本机4GiB限制不改变本轮正确性结论。服务器尚未实际验收，仍不混用本机/服务器结果。

归档格式补充：完整git diff --check检出早期pytest失败日志v2_tests.log中的行尾空格。这是原始诊断输出，保留原字节以保证SHA，不修剪日志；非日志文档/源码快照的差异检查单独通过。没有忽略代码或文档的空白错误。


## 69. 2026-10-29/30：Prompt 8G 全量 N-anon-s 特征、依赖核验与170项准备计划（Codex）

### 69.1. 请求、版本、范围与方案选择

用户要求“实现8g”，中断后要求继续完成。读取更新后的 PROMPTS.md §4.1/§4.10h，在 dfg-v2@62b73866c2b8fa488a087cc1839255f2f232ed18 开始，git pull --ff-only origin dfg-v2确认已最新。2026-10-29开始，2026-10-30完成恢复验收。修改/复核AI：Codex。

8F采用声明绑定，存在159个整文件回退及36个合成节点文本歧义；8G由用户更新的文档明确改为“同一文件内按AST identifier拼写建立双射”。这不是本轮未征求意见而替换设计，也不意味着补齐了8F Solidity绑定器。旧8F代码、322份归档、失败决定和seal全部只读保留，旧结果不会被新结果覆盖。

本轮仅新增匿名化与验收/特征/计划旁路，不修改原DDG/HGT/tokenizer/训练器/冻结图/标签/历史fold及已有checkpoint。新的170项计划在独立prompt8g_v1封存，execution_authorized=false，不训练。没有自动扩展到其他五类、追加seed或服务器迁移。

没有另外提出或实施改变本轮方案的替代策略，没有放宽语义/探针门槛。实际结构上的约束如“准备计划不能直接交给旧CLI”“语法identifier不等于全部语言名字”单独如实记录。

### 69.2. 文件、代码逻辑与复用

新增六个模块，全部位于scripts/DFG/dfg_v2/benchmark_v2/：

|文件|主要职责|
|---|---|
|spelling_names.py|按真实AST identifier选中位置；固定保留表；source SHA随机双射；精确字节/语法/拓扑/关键词复核；失败整文件无残留回退|
|spelling_parity.py|复用冻结构图器与8F证据规范化，比较归档/原文/改名L1/L2/L3事实、证据、端点；内存code副本检查|
|prepare_spelling.py|全256源码/384任务文件清单与seal；逐文件结果；历史36合成节点候选核验；完整性门槛和失败停止入口|
|spelling_probes.py|复用8E P2/P3及阈值、分组；相同OOF角色AUC、关键词基线和独立指标复算|
|spelling_features.py|冻结TokenEncoder生成新旧NPZ；跨剖面身份/label/特征/边schema绑定；CPU零步初值装配与G0恒等前向|
|spelling_plan.py|只重绑已验收特征；170项矩阵/配置/折/评分规则严格继承；新plan/seal、未授权模板和只读verify_plan|

新增tests/test_prompt8g_{spelling,parity,gate,probes,features,plan}.py，共83项。新增PROMPT8G_REPORT.md与benchmark_v2/PROMPT8G_README.md。三份原记录只追加，不修改旧正文。

特征适配文件头记录被参考的feature_view.py及SHA 390a16c62b9b2126b4301e8a347581dc034ec426abe921b555f66de2b306365b；旧接口仅针对SolidiFI，新适配明确对全部来源执行，并用恒等输入证明保持原行为。不改冻结函数globals/字节码，不复制重写完整训练器。

### 69.3. 命名规则与版本依据

规则版本prompt8g-spelling-bijection-v1。选中冻结grammar中类型严格等于identifier且不在8F保留表/固定类型正则中的节点；包括外部未声明成员。保留表与8F policy逐项核验，msg/sender/tx/origin/block/now/this/super/call/send/transfer等固定语义名字保留。字符串、注释、其他语法类型原字节不变，逐文件记录保留名次数。

按排序后的文件内不同拼写分配vN，编号由SHA256(version:sourceSHA)确定的随机排列产生；不是按首次出现顺序，所有角色共用v前缀，并避开原文件已存在的vN。同一拼写在不同作用域/声明处共用匿名名；这是有意保留拼写相等结构，不声明恢复了符号身份。

验证重新解析原文及改名文，ERROR/missing均0；类型拓扑相同；改写字节集合恰为已选中的identifier；不同拼写映射互异；字符串/注释等非选中片段不变。五类保留子串tx.origin、msg.sender、.call.value(、.send(、.transfer(数量相同。

原源码带版本metadata的身份共43个：重入27、访问控制16。原metadata先核验source SHA；改名临时分析不冒用原源码编译身份，只依据未改pragma。虽然移除该metadata可能影响受限分析器，本次384项实际比较全部一致；没有为保住通过率伪造编译器版本。本轮没有solc编译验证。

### 69.4. 全量数量与合成节点恢复

|类别|源码身份|不同拼写映射（逐文件累计）|identifier替换次数|回退|
|---|---:|---:|---:|---:|
|重入|142|9134|35018|0|
|访问控制|114|8025|31195|0|
|合计|256|17159|66213|0|

“256源码身份”以类别/文件/source SHA区分；“384”是合约/节点任务中的文件引用，不能把二者当相同分母。重入合约142、重入节点71、AC合约114、AC节点57，全部通过归档/原文/改名的L1/L2/L3数量、完整规范化证据、投影端点/关系计数比较。恢复code后原HCG所有属性、节点顺序和边fingerprint相同。

8F此前36个end_if/end_loop合成节点，在同文件同拼写映射下，所有精确AST文本候选得到同一改写文本；36/36通过，候选AST ID集合与历史证据相同。没有按最近行号选择候选，没有声明来源唯一的额外结论，也没有删除原合成节点。

命名目录同时保存原8F manifest和supersession新记录；旧8F阻断状态仍保留。原图仍是模型的语义结构；匿名源码只作为特征视图和分析一致性检查输入，不将改名图替换正式图。

### 69.5. P2/P3门槛与关键字证据

在命名/语义门槛通过后，先封存probe_plan与冻结PROTOCOL，再使用唯一固定映射执行，不调阈值或挑seed。P2使用旧inner_train规则、同组隔离折与全部原节点身份；C1仅诊断标签，不改输入图。

|SolidiFI任务/标签|P2 pooled BF1（%）|全正BF1（%）|差值pp|≤5pp|
|---|---:|---:|---:|---|
|重入orig|22.64879357|75.01721368|−52.36842011|通过|
|重入C1|27.46626687|76.53327287|−49.06700600|通过|
|AC orig|23.36633663|58.27749310|−34.91115647|通过|
|AC C1|24.28630534|60.13809200|−35.85178666|通过|

P3总体AUC=0.5261014389269172，≤0.60通过；重入/AC子集AUC=0.5349815789197857/0.515403308751046。10347个名称样本、冻结5折，只拟合5次CPU逻辑回归诊断，正式HGT拟合0。

角色统计使用同一pooled OOF预测的子集，不额外训练、没有新增角色门槛：
function 3875样本/2230正例/AUC0.53023716；
local 609/214/0.48257423；
parameter 2916/1311/0.52364678；
state 2176/1292/0.54144588；
event336/0、field318/0、modifier117/0的AUC未定义，不能写成0.5或通过独立角色分类验收。
独立复算P2每折及pooled混淆矩阵/指标、样本/源码/折身份完整性；用Mann–Whitney秩公式独立复算P3，结果一致。

关键词基线原/新每个节点预测完全相同。SolidiFI orig/C1 BF1：重入85.07078507/86.36723074，AC95.62377531/97.84310593；非SolidiFI原标签分别18.12688822/14.28571429。高关键词分数仍在，P2/P3通过不等于排除了所有模板/语义线索。预登记解释不改：AC节点仅作描述；主要DFG任务为重入节点、重入合约、访问控制合约。

### 69.6. TokenEncoder特征与模型装配

全部原HCG节点生成原文/匿名两种独立NPZ，四任务共8个数组：

|任务|总行数|匿名token实际改变|原token重编码逐位一致|
|---|---:|---:|---:|
|重入合约|18312|17101|18312|
|重入节点|12036|11224|12036|
|AC合约|13432|12766|13432|
|AC节点|7710|7436|7710|
|合计|51490|48527|51490|

每行绑定原node_id/file/source SHA/node_type/code SHA/旧新向量SHA，四任务与五剖面图fingerprint、标签/原边/节点顺序相符；只在模型内存副本替换原节点token，env_source原特征保持。向量仍为512维float32 tokenizer IDs，不是新语言模型embedding；不下载/加载CodeT5权重。冻结编码器先完整tokenize，再取前512个ID并补零；长文本警告不代表越界送入CodeT5模型，也未改截断策略。

最终model_proof_attempt2检查四任务×G0/G1R/G2R/G3R/G3=20项。G0分别执行direct、original恒等、anonymous；其他剖面anonymous一次，共28次完整CPU eval前向。加载旧存档零步初值只是接口验收，逐项检查kind=untrained_initial、optimizer_steps=0、文件SHA/tensor digest，前后state_dict摘要相同。四个G0 direct/original logits逐位一致；20个匿名视图全部输出有限，原监督节点口径不变。没有更新权重。

恢复执行时发现原model_proof日志停在第3任务末尾，无summary和命令退出收据，进程已不存在；确切退出原因无法追溯。保留3份已完成任务JSON（15剖面、21次有记录前向）及原日志，另建model_proof_attempt2完整重跑，不覆盖或假称epoch续训。独立复核3份旧任务记录与新记录完全相同。28只表示最终完整收据的次数，不把所有尝试累计冒报为28；未落盘的中断工作量不猜测。interruption_20261029.json如实记录恢复状态。

### 69.7. 170项新plan/seal与未授权模板

新目录prompt8g_v1/plan/含plan.json、plan.seal.json、verification.json、acceptance_decision.json、authorization_template.json。plan SHA256为be66792cbd43978588761393f354f1df89f1a181104bbee5d567252aae57536a。

以8D/F旧计划SHA为来源，全部jobs、fit_count、protocol、label_policies、统计/选型/初始化规则、fold/population/config/graph引用严格相同，仅将每任务特征指向已验收N-anon-s新视图。旧feature_equivalence等引用转为historical_*保留；新特征/命名/语义/探针/model proof和六个准备代码SHA均绑定，不修改旧plan或seal。

拟议一个seed=1：5个剖面×两个漏洞×(5合约+10节点折)=150，G0P只用于两个节点任务另20，总170。两种标签是待选择方案，当前不是同时跑两套。selected_label_policy、selected_training_seeds、selected_execution_location都为null，所有jobs及模板execution_authorized=false。

协议仍dfg-v2-grouped-nested-v1，冻结重复组和文件划分；inner_train更新、inner_val早停/选best/G*、outer_test最终评分，full_fixed_task_graph前向为transductive。不是paper_kfold的CV validation，也不是外部独立测试。best严格最低inner_val loss，last辅助，节点按原HCG节点而非去重源码行。

L-orig=作者原标签；默认建议L-audit=节点C1标签+C2_include损失/指标mask，不删图节点、不把排除节点改负例，合约标签不变；总是另报全部原节点的原标签评分。L-audit仍为诊断标注策略，不声明新的可信真值。初始化仍要求各fold fresh zero-step states、语义共同参数完全相同、新关系按各剖面原Xavier范围，G0P共用G0初值和历史空关系规则。

计划状态prepared_awaiting_label_seed_location_and_executor_binding。**尚非旧CLI可执行格式**，执行前还需明确匿名特征/选定标签mask/新分组折/G0P的运行绑定、生成新初值并完成接入验证；旧CLI没有新参数时不能假装已支持。该边界与8D原准备计划一致。本轮没有重写训练器或自动开始170fit。

本机历史每任务/剖面中位数之和29804.8006秒=8.2791小时，控制器开销另计；匿名特征与分组折会改变早停，此为预算参考，不是实测保证。最终实验按用户安排在显存充足服务器整批运行；当前RTX3050 4GiB仅限制本机开发，服务器尚未部署/实测，不把显存充足等同固定加速比，也不混用本机/服务器成绩。

### 69.8. 测试与实际命令

83项新增定向测试分批全部通过，包含在最终v2全套2573项中；旧回归223项通过，合计2796个唯一测试，0失败/错误/跳过。最终v2用时197.17秒、9条警告；旧回归3.48秒、29条警告。警告为DGL distutils及NetworkX gpickle弃用，新增探针测试调用冻结gpickle使v2比之前多一条同类警告，无算法异常。

实际mando环境：TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64，PYTHONDONTWRITEBYTECODE=1，OMP_NUM_THREADS=2，MKL_NUM_THREADS=2，CUDA_VISIBLE_DEVICES=''。命令argv/env/退出码/耗时见批次*.command.json；完整入口次序见benchmark_v2/PROMPT8G_README.md。

    python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests --basetemp scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/_test_tmp/v2_final
    python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py --basetemp scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/_test_tmp/legacy_final

这些临时目录测试结束后已清理；重跑应新建专用父目录。之前的v2 2538通过是在补齐探针/特征/计划测试前的中间记录，不与最终2573重复计数。

names、semantic、probes、features用时分别11.76、641.88、35.51、81.66秒；模型验收重跑和计划耗时见model_proof_attempt2.command.json与plan.command.json。这些是准备/诊断时间，不是HGT训练时间。

### 69.9. 独立复核、清理与交付

独立final_review.py重新核验语义门槛、20项装配记录/28前向、G0直接与恒等logits摘要、原初值文件、20个剖面/特征引用、6模块实现SHA、旧计划矩阵、新计划false授权、NPZ8个、全部51490行和48527改变量、各命令成功收据，结果final_review.json passed=true。三份中断任务记录与重新验收结果相同。

追加文档前，694个既有受保护文件（690 Python+4文档）SHA无变化，旧8F322归档SHA一致。追加后再次按before.json字节长度检查三个旧文档前缀，PROMPTS不改；只提交新六模块、六测试、两份报告/README和三份记录追加，不包含不相关未跟踪文件。新增运行产物保留WSL批次，本轮不自动push，后续归档按用户要求进行。

只删除本批专用_test_tmp：34850普通文件、1090临时链接，共354114729字节=337.71MiB；在两套测试完成后验证绝对路径属于prompt8g_v1，不跟随链接删除外部目标。cleanup.json记录范围，所有日志、正式NPZ、旧产物、中断证据、用户其他文件不动；未清理未知来源C盘文件。

### 69.10. 已知限制与停止点

1. 全256文件通过的是规定identifier范围，而非全部Solidity名字。冻结grammar有39个enum_value、75个yul_identifier不属于选中类型，114处中100处拼写也在普通identifier中出现；声明/引用改名可能不一致。按文档原规则保留，没有悄悄扩大AST选择范围。
2. 未声明外部成员也改名，外部ABI可能不保留；字符串/注释不改；不声明改名源码可编译、可部署或完整语义等价。L1/L2/L3验收只能证明当前受限分析输出不变。
3. 固定保留名、模板、结构、文件长度和匿名编号范围等仍可能有预测信息。P3 AUC通过只对应预登记探针；高关键词基线继续报告，AC节点维持描述性。
4. 原标签正确性、此前512/111条人工依赖检查仍未因本轮自动解决；不修改争议标签。
5. 本轮正式HGT fit=0、真实模型验收optimizer steps=0、P3 CPU诊断LR fit=5；没有N-anon-s新HGT F1或依赖增益结论。
6. 170计划已封存但未授权。下一次执行前用户需选择标签方案（默认建议L-audit）、seed数量（默认拟议1）及位置，再完成新运行绑定/初值验收。本轮不启动新训练、其余五类、多seed或新模型模块。


### 69.11. 2026-10-30 GitHub代码与完整文本结果归档（Codex）

用户本轮明确要求“推送github”。开始时本地dfg-v2@68e6ce122a06bb4b6003b875a9a8817583852de7，tracked工作树与暂存区干净，未改代码或重跑实验。源码、83新测试、报告、README和三文档实施记录已在该实现提交中。

新归档清单docs/github_archive_prompt8g_2026-10-30.json逐文件绑定349项、118831490字节（113.33MiB），同名.md解释内容与复现限制。范围含331 JSON、17日志和1份独立审计Python脚本：256源码改名映射、384依赖/投影检查、36合成节点恢复、P2/P3逐样本预测/角色AUC、关键词、8份特征manifest、20项完整模型检查和中断尝试、170项plan/seal/未授权模板及全部测试/核验/清理/提交记录。最大文件12027366字节，原样归档，不截断或替换原文件。

8份实际特征NPZ共2977008字节（2.84MiB）按历史方式留本地，路径、SHA、大小放入excluded_local_feature_files；这些不是被删除或漏记。原图、tokenizer资产和存档初值仍依照既有manifest提供；单独克隆仓库不等于取得全部本地模型/数据。其他阶段未跟踪文件不纳入。

归档前只读验证：plan/seal、冻结170矩阵与false授权、256源码及384项语义证据、36合成恢复、六模块源码摘要、特征和模型引用、旧8F322归档字节不变；全部文本UTF-8、331JSON能解析，常见凭据模式未匹配。所有正式文本按原字节保存，暂存blob逐个核对清单，再提交归档。三份记录仅追加，不改变历史正文；实施阶段2796测试通过沿用，本轮无额外前向、探针或训练。

WSL Git直连报Could not resolve host: github.com；Windows已有代理127.0.0.1:7897，WSL网关访问超时、WSL自身127.0.0.1连接拒绝。使用同一工作树的实际Git目录，由Windows Git走已有代理，并调用WSL既有gh auth git-credential；首次绝对/usr/bin/gh被MSYS路径转换造成找不到命令，改用gh命令后读取远端成功。没有更改代理/Git全局配置，没有新建或输出凭据，没有关闭用户进程。实时远端为62b73866c2b8fa488a087cc1839255f2f232ed18，属于本地历史；正常非force推送用户origin/dfg-v2，不向作者upstream推送，也没有分支保护策略拒绝。

local_commit_receipt中的pushed=false是实现提交完成时的历史事实，不为归档而改写；实时完成以push返回和远端refs/heads/dfg-v2与本地HEAD一致为准。新归档提交在实现提交之后，源码/报告/结果连续可追溯。

本轮正式HGT fit仍0、P3诊断LR fit仍5，170准备计划尚未授权；后续需要标签、seed、位置选择及执行器接入验收，不因推送而自动启动。最终用户计划在显存充足服务器整批运行，本机4GiB只是开发限制，服务器未实测且两地结果不混报。
