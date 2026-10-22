
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
