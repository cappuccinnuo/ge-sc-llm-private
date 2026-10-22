
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
