# Stage H2 执行与验收报告

2026-10-15，Codex。26个新E3a结果、4个Stage G fold0复用，共30个；联合E2/E3a/E3b共90个正式结果。
新增收据数=26；失败sidecar数=0。完整三变体结果、逐折统计和解释见[E2_E3_COMPLETE_ABLATION_REPORT.md](E2_E3_COMPLETE_ABLATION_REPORT.md)。
HEAD：cef8fb9bac5f855d657b7d72a04d650f03465469。原H1/H2预留plan及seal未改；原预留execution_authorized=false保持，新H2独立plan记录本轮授权。
沿用H1专用只读归档核验。启动前H1 60结果、30份E3a初值、四个G E3a fold0通过验证；本批封存89份运行源码、1525项固定资产。
必要测试71通过/0失败/0跳过，4条既有DGL弃用警告。未重跑四任务smoke或扩大静态审查。原fit、模型装配、监督、checkpoint算法直接复用。
best/last重载一致由每fit收据验证；90组预测与冻结标签按身份独立复算；OOF无重复文件/节点，仍为CV validation。
源文件身份和跨cohort同名文件在导出中携带source SHA；困难文件没有删除或重标。
代码范围：scripts/DFG/experiments/e23_h2/；新产物仅stage_h2_v1/；历史H1/G结果只读。训练数值代码封存后未改。
正式运行命令：

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONPATH=$PWD
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -u -B -m scripts.DFG.experiments.e23_h2.control run
python -B -m scripts.DFG.experiments.e23_h2.control verify
python -B -m scripts.DFG.experiments.e23_h2.control summarize
~~~

已成功结果自动核验复用；本轮结束后不需要重训。若HEAD在后续归档发生变化，不改旧seal；新增只读归档验收另行处理。

## 消融结论与下一步证据边界（Codex，2026-10-15）

1. **状态 Def–Use 单独的增量较小，且方向不一致。** E3a−E2 的节点 best Buggy-F1：重入 −0.0384pp（3升/3平/4降），访问控制 +0.0648pp（3升/5平/2降）；Macro-F1 分别 −0.0438pp、+0.0608pp。两个合约任务的 best 指标及每个合约类别预测均不变。这不支持“仅增加 STATE_DEF_USE 就能稳定改善两个漏洞”的结论，也不能据此证明更完整的状态依赖无价值。

2. **H1 的重入小幅收益主要出现在顺序关系增量中。** 重入节点 E3b−E3a 的 best BF1 为 +0.2072pp（6升/2平/2降），抵消状态 Def–Use 的轻微退化，得到 E3b−E2 +0.1688pp。访问控制两段均为小幅正向：E3a−E2 +0.0648pp，E3b−E3a +0.0865pp，合计 +0.1512pp。访问控制固定图没有调用→写入边，此处顺序增量来自 STATE_ACCESS_ORDER 及随之发生的参数/聚合/优化变化。重入同时加入两类顺序关系，不能分辨它们各自的贡献。

3. **合约级没有分类收益，但并非模型输出完全没变。** 两类合约的 best 概率都发生变化，argmax 类别完全一致：重入142个、访问控制114个样本均未翻转。不能只用类别持平认定关系未接入；实际梯度和参数审计已验证接入。反过来，有梯度也不等于有有效的漏洞定位信息。

4. **已有困难文件的主结果未改变。** 在 best 下，重入 buggy_18.sol 的275个错误、buggy_36.sol 的58个错误，访问控制 buggy_18.sol 的94个错误、buggy_26.sol 的42个错误，三变体均未发生离散预测改变。两类同名文件具有不同 source SHA，已在表中区分。E3a 的变化发生在其他文件：重入净增加2个错误（纠正12、新增14），访问控制净减少4个（纠正9、新增5）。访问控制 fold7 的6个纠正分布在 arbitrary_location_write_simple.sol、buggy_17.sol、buggy_34.sol、wallet_02_refund_nosub.sol，未修复该折 buggy_18.sol。完整原始 node_id、概率和文件SHA在 error_changes.csv，不以文件名或CSV行序猜测身份。

5. **绝大部分变化仍是概率变化，best/last 的方向不能混称一致。** E3a−E2 的 best 类别变化仅重入26/12036、访问控制14/7710；E3b−E3a 分别44/12036、12/7710。E3a−E2 的 last BF1 重入 +0.0360pp，与 best 的负向相反；访问控制 +0.0178pp，但 last MF1 为 −0.0044pp。E3b−E3a 的 last BF1 则为重入 −0.0869pp、访问控制 −1.3236pp；访问控制合约 E3a/E3b 的 last 相对 E2 下降0.7333pp。预定主结果仍是最低 val loss 的 best，没有根据更有利的 F1 重新选择 checkpoint。

6. **状态 Def–Use 的实际支持非常稀疏。** 四个固定任务图按重入合约、访问控制合约、重入节点、访问控制节点排列，仅6、11、3、4条 STATE_DEF_USE。节点任务分别有8/10、7/10折的 val 不包含这种边。每折在关系名称汇总层面均有 train 支持，但某些 canonical relation 仍无 train 实例；两者不能混淆。全部90个模型的1605项增强 canonical 梯度记录中，1564项有训练支持者观察到非零有限梯度，41项无训练支持者单列保留，非有限记录0。没有把缺少训练实例误判为接入失败，也没有临时创建测试参数。远离新增边的节点也可能因共享参数/优化轨迹改变而改变概率，因此这些变化不能直接算作局部依赖语义的证据。

**下一步最有根据的研究方向（仅建议，本轮未执行）：** 优先研究“顺序关系是否提供可复核的有效上下文”，先对本批已改变节点和持续困难文件进行有限机制解释，区分直接新增关系影响与共享参数变化；若将来扩大实验，应预先固定分别移除两类顺序关系的对照，以及匹配参数量/连接数量的控制，避免将参数增加全算作语义贡献。权限场景的 guard/modifier 控制约束仍未在本批验证；不能因本批 STATE_DEF_USE 稀疏就直接开始更多训练或宣称无效。可靠性还缺独立 seed、独立评估或组级泛化证据，以及未覆盖语义的人工验证。上述均需另定任务，不在本轮自动执行。

历史 E0/E1 数值已附表，初始化版本不同，仅作历史参考；访问控制合约本批仍低于历史 E0/E1，不能宣称全面超过原基线。当前证据足以支持有限的顺序关系机制研究，尚不足以宣称七类漏洞均获益。

## 本轮资源与交付验收补充

新增26个fit均为 attempt_001，0失败、0重试、0 OOM；4个Stage G fold0只读复用，不计作本轮新训练。新fit耗时合计4296.9452秒；控制器5521.9853秒，包含校验、启动、保存和重载等开销。仅统计本轮新fit的 peak allocated 最大2466.5654 MiB、peak reserved 最大2628 MiB、整卡空闲最低54 MiB。上方跨变体资源表同时包含历史Stage G/H1的测量，因此其最小free可能更低，不能与新fit范围混淆。

首个新fit曾受Windows显存占用影响。用户表示会自行关闭不需要的程序；没有代关程序、重启该fit或改参数，也没有独立确认GameViewerServer退出。负载与早停轮数不同，资源表不能作为公平速度优劣结论。

实际新增代码仅 e23_h2 调度/归档绑定/汇总与必要测试；本轮没有改变 DDG、HGT、tokenizer、标签、fold 或训练数值。71项必要测试通过，0失败/跳过，4条既有DGL弃用警告；四任务完整性门槛及最终 verify/summarize 均成功。未重做真实smoke、编译/Oracle验证、全面标签审核或独立测试，不声称完整Solidity DDG已实现。

停止位置：26次新拟合完成，30个E3a验收，90个正式结果完整消融。H1/G旧计划与seal及预留H2的未授权标志保持原样；没有自动提交、推送、再训练或扩展其他五类。
