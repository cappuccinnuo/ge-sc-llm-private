# Prompt 8H：执行器已接入，首个试点完成，缓存验收阻断（Codex）

本轮起点：dfg-v2@39801a87。批次：scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/。授权：L-audit、N-anon-s、seed=[1]、本机local_dev_v1，共170次正式拟合。

**当前状态：正式训练完成1/170；首个试点完整只读验收通过，但控制器创建验收缓存失败，整批已停止。没有自动重试，第二个试点及剩余169次均未启动，尚无完整矩阵或最终F1统计。**

## 1. 已实现范围

新增benchmark_v2执行器、协议分派、L-audit监督mask、checkpoint绑定、三次深度校验/快速输入检查、G0P模型适配、归档核验、验收工具、完整矩阵统计入口及测试。原DDG/HGT/tokenizer和旧训练脚本未修改；703个起始Python文件SHA一致。详细文件列表与实施选择见training_changes§70。

节点主监督使用C1，C2_include=false排除直接loss、best选择和主指标；被排除节点仍保留图内传播。原标签辅助结果覆盖全部原HCG节点。合约标签不变。G0P保留G0节点与特征，只添加零边canonical；无新增env_source。

## 2. 获批的两项调整

1. 旧8B.0运行清单拒绝任何新增Python文件，用户批准只读归档核验：逐项检查历史绑定源码、输入、修订、seal及150个收据；新执行器单独封存，旧入口不放宽。
2. CPU初始化准备耗时较长，用户批准先证明逐位一致，再复用从未训练的增强剖面结构。每折G0新建，四种增强剖面全部参数由未修改的initialize_family重写，G0P逐折新建；正式worker仍是独立进程并加载各自封存初值。

真实重入合约3折×5剖面共15项、5562张量/74068122参数值与原逐折新建参照逐位一致。acceptance/structure_reuse.json保存证据；参照权重只用于比较，没有加载进待生成模型。两次中止的CPU准备保留，新最终输出prepared_attempt3/。

## 3. 门槛与测试

- 150个旧结果归档核验通过。
- 原输入CPU新旧路径各2轮：loss、参数、optimizer、scheduler及预测逐位一致。
- GPU完整历史重入节点fold0 G0：best epoch及全部best/last分类一致。
- 真实节点三个分区的mask数值核验通过；被屏蔽位置的直接logit梯度为0，改变这些标签不改loss/选择/主指标。
- G0P一轮CPU冒烟：空关系梯度0、参数不变；前向分母证明限于同输入单层，不声称最终logits固定倍数。
- v2全套2614通过，9条既有警告；原回归223通过，29条既有警告。总2837唯一测试，0失败/跳过。新增41项定向测试已包含在2614内。
- 新旧训练入口共用.training.lock的回归通过，防止跨协议并行占GPU。
- 开发期CPU缺import、测试临时目录与同源fixture更正均有保留记录，未放宽关键断言。

## 4. 正式计划与首个试点

170份零步初值/30折已生成。新plan SHA：

cb8daf22ed9fb9cd81fe575548d338408a5420f62e7a6da529d402c148eb8a2c

首个正式fit：reentrancy_contract / fold0 / seed1 / G0。完成19轮，best为第12轮（zero-based=11），last为第19轮（zero-based=18）；inner_val/outer_test的best/last重载一致。无OOM，非有限数值错误未出现。完整只读verify_one再次通过，记录cache_failure_diagnosis.json。

资源：peak allocated=1230.8384MiB，peak reserved=1410MiB，整卡最小空闲=400MiB，memory_tight=false。精确训练耗时与资源原始证据在诊断JSON及final_result.json中。此处不提前汇总F1，也不把1个试点当作170结果。

## 5. 阻断根因与影响

新execution.fit_one在资源采样器仍运行时保留trainer写出的result.json；退出采样器后另写final_result.json。旧experiment/acceptance_cache.py::_dependencies固定读取result.json的raw_samples_sha256，同时又读取已完整写完的相邻memory_samples.jsonl，于是同一路径得到两个SHA，触发Conflicting or changing dependency。

- 中间result记录：b42367719a11c6dc88be383e0da78b7cd5cff6edbf0a5c35dbc0b64f4d44230a。
- final_result记录和实际完整日志均为：d37dcf6f805e1d4013f1dd25dde1f09d40dcc21707c6ae6f48a918e6d7c8bdd0。
- 这是新增缓存接入接口缺陷，与DDG语义、模型梯度或训练数值无关。
- worker成功收据已写入，完整验收通过；控制器失败，尚未生成pilots总验收或启动第二个fit。
- 既有测试覆盖监督/模型/输入/锁，但没有覆盖“真实异步资源采样结束后再创建旧缓存”的接口组合，这是本轮测试缺口。

保留原计划/seal、result/final_result、采样日志、worker/控制器日志、成功收据和停止状态。未覆盖任何历史文件，未自行重跑或改变冻结计算源码。

## 6. 待批准修复

已向用户提出：仅新增8H缓存依赖适配，使其读取final_result.json作为最终资源记录，继续校验全部收据文件及采样原文SHA；旧缓存不改。新增独立运行版本修订记录绑定旧plan/seal与新适配代码，保持模型、初值、数据、训练规则不变。补充真实日志接口回归、篡改拒绝检查，通过后复用首个已验收fit，再继续剩余169项。

截至本报告条目，该修复与恢复执行尚在等待确认；未实施新的运行版本、未重签旧seal、未重训首个试点。Prompt8H明确要求任何失败后停止并等用户确认。

## 7. 运行与未执行事项

已执行acceptance archive/cpu/gpu、real_acceptance、initial_preparation、execution prepare、execution pilots。实际命令见benchmark_v2/PROMPT8H_README.md和orchestration.command.json。pilots已在缓存步骤停止，不能直接重跑命令冒称恢复完成。

未执行：第二个正式试点、其余完整矩阵、170/170最终验收、G*选择、F1/配对统计、更多seed、其他五类、服务器训练。L-audit仍是诊断标签视图，不是已证明的ground truth；人工512/111依赖核验等既有范围限制未因此解决。

仅清理本批两个可重建pytest临时树，共466323719字节（444.72MiB）；重要日志、权重、初值及用户文件保留。产物位于WSL，不另写C盘。

最终正式实验按用户安排在显存充足服务器运行；当前本机RTX3050 4GiB只是开发资源限制。本次停止由缓存一致性错误引起，不是显存不足。


### 2026-10-30 Prompt 8H缓存修复获批（修改 AI：Codex）

用户批准仅修复缓存接入并继续剩余169次。新增8H专用acceptance_cache/runtime_amendment，读取final_result而不更改中间result或原缓存，严格保留采样原文SHA/缓存库存校验。execution仅调整缓存导入与修订元数据，数值训练不改；旧plan/seal和首个成功fit保留，独立修订封存后复用首个结果。真实35依赖SHA与目录不变证明已通过；96定向/相关测试、223旧回归通过，完整v2回归进行中。批准与实施证据在cache_fix_v1，详细见training_changes§70.11。正式恢复尚待这些检查完成，最终服务器安排不变。


### 2026-10-30 Prompt 8H 缓存修复验收通过、获批恢复（修改 AI：Codex）

用户已明确批准“修复缓存接入并继续剩余169次”。定向/相关96通过（包含在全量内），v2全量2632通过、原项目223通过，共2855项唯一测试，0失败/跳过。警告分别为4/9/29条既有依赖/弃用警告，完整日志与SHA保存在cache_fix_v1/equivalence_proof.json。真实首个fit完整verify_one、final_result依赖缓存创建及缓存命中全部通过，new_fits=0；没有重训或修改该结果。

独立修订runtime_cache_fix_v1.json SHA：7a1e4ed3a280a40b881332ba0abbd01a5c9e5e3813c1c89c2b6660f4b37c0b22。原plan SHA仍为cb8daf22ed9fb9cd81fe575548d338408a5420f62e7a6da529d402c148eb8a2c，原seal、缓存及停止现场保留。修订仅允许execution.py五处接入/审计调整和两个新模块；数值循环及原模型/数据/初值未变。旧成功收据仅限清单中首个结果可没有新修订字段，后续fit必须绑定修订。

接下来串行执行pilots，再all，最后reporting。首个重入合约fold0 G0复用；第二试点重入节点fold0 G3R通过后进入剩余矩阵。总目标170，恢复时已完成1，不将恢复称为完成169。新控制器日志/状态使用resume_v1名称，旧停止记录不覆盖；失败停止且不自动重试。完整验收前只记录进度，不汇总F1。运行期间冻结Python文件，不自动push。

最终实验按用户安排在显存充足的服务器执行，本批仍按明确授权在本机local_dev_v1运行，不混用两个环境结果。


Prompt 8H正式恢复进度（Codex，2026-10-30）：独立修订和代码提交00c731e6生效；原首个成功fit完整复用，第二试点重入节点fold0 G3R通过，acceptance/pilots.json已封存。控制器已进入全部170项串行矩阵，目前2项完成；这是启动进度记录，不是最终结果。旧orchestration_status保留失败历史，新状态为orchestration_resume_v1_status.json。另清理本批cache_fix_v1/_test_tmp可重建临时树211615457字节（约201.81MiB），未跟随600个符号链接，不删除正式产物；cleanup_test_tmp.json留证。运行期无计算源码修改，尚未push。


### 2026-10-30 Prompt 8H 外部中断后的显式恢复准备（修改 AI：Codex）

用户在获知训练中断后明确要求“继续训练”。已完成71/170（重入合约25、重入节点46）全部重新完整verify_one通过；第72项重入节点fold7/G3的attempt_001停在第32轮，无成功receipt。Windows有约80分钟睡眠记录，末次采样仍有984MiB空闲；未找到OOM/Python异常/明确退出码，终止原因尚不确定，不将睡眠或显存认定为已证实根因。

现有执行器硬编码attempt_001并拒绝任何未完成尝试。为落实本次明确恢复指令，新增retry.py，最小调整execution的尝试选择、reporting的唯一成功收据定位、acceptance_cache依赖和runtime_amendment的修订链。原训练数值try主体、construct/binding_parts/prepared的AST保持一致；原trainer/DDG/HGT/tokenizer/特征/标签/折和初值不改。旧attempt_001及全部路径不迁移、不覆盖；仅指定失败任务可从封存零步初值重跑为attempt_002。已有71个成功结果复用，剩余99个正式结果待生成；不是从第32轮续训，也不是新seed。

resume_v2保留用户授权、71成功收据、全部中断文件SHA、4份修改前源码与精确编辑清单。将建立独立runtime_resume_v2.json与seal，引用原plan和旧cache修订，不重签旧文件。新尝试一旦再失败仍立即停止，无自动第三次尝试。80项定向测试通过，全套回归进行中；本条尚不是恢复训练已启动声明。最终显存充足服务器安排保持，本轮仍为已授权的本机批次。


Prompt 8H显式恢复验收完成（Codex，2026-10-30）：80项定向测试已含于2653项v2全量，原回归223项，总2876唯一通过，0失败/跳过；警告分别4/9/29条既有依赖警告。原71个成功结果完整核验通过；重试初值SHA和tensor digest匹配、optimizer_steps=0、原fit_seed=1010007，真实旧结果的新修订缓存创建/命中通过。runtime_resume_v2.json独立封存，SHA f18dd07d04d4cc00e5a232818a65febe6ea4d413e4e8e81d044504ae2e1d96b4；旧plan/cache修订及其seal未改。新增21项测试确保只有被授权的002可重跑，训练数值try主体和构造/监督绑定函数AST不变。即将启动独立会话控制器，先复用71，再重跑第72项与后续任务；不是已完成99次的声明。实际进度见orchestration_resume_v2_status.json和full_matrix_resume_v2.log。


Prompt 8H恢复控制器补记（Codex，2026-10-30）：本地提交02db061c后，首次恢复控制器在只读验收到16/170时退出；新fit尚未启动，attempt_002.start不存在。原因是我同时清理已结束pytest的临时树，旧_code_refs会先rglob遍历artifacts再过滤，遇到已删除目录触发FileNotFoundError。这是操作并发冲突，不是训练数值/缓存错误；已保留full_matrix_resume_v2.log及resume_v2/controller_scan_race.json，71成功receipt和全部中断文件SHA重新核对未变，运行版本核验通过。

清理仅涉及resume_v2/_test_tmp共211184809字节（约201.40MiB），599符号链接仅删除链接、未跟随目标，正式证据和用户文件均保留。清理已结束，后续运行期间不再删除任何目录。原runtime_resume_v2修订、计划和计算源码完全不变；根据本次“继续训练”授权重新执行只读验收并继续尚未消耗的一次attempt_002，不自动重试任何新失败fit。独立后台进程新日志/状态为orchestration_resume_v3_status.json、full_matrix_resume_v3.log，原v2停止现场保留。此处v3仅表示控制器启动记录，训练计算版本仍为runtime_resume_v2。


Prompt 8H已实际恢复训练（Codex，2026-10-30）：orchestration_resume_v3控制器完成71份历史结果复用验收后，已启动第72项reentrancy_node/fold7/seed1/G3，worker PID 1333914，输出attempt_002；新start绑定runtime_resume_v2，仍使用原fit_seed=1010007。原attempt_001及其32轮历史、best.pt和日志保留原路径。后台supervisor PID 1333862采用独立会话；后续99项按原矩阵顺序串行、每项独立进程，失败停止。新计算接入已提交本地02db061c，未push；训练期间不修改代码、不再清理目录。此条只确认恢复，不代表170项完成，最终统计仍须全部验收后生成。


## 最终完成补记：2026-10-31（Codex）

以下为本批最终状态；上文为保留的实施/停止/恢复历史。

完成状态：170/170 正式拟合已全部验收，complete.json 的 passed=true，orchestration_resume_v3_status.json 的 status=complete，reporting 已结束；本次检查未发现 benchmark_v2 / orchestration_resume 活动进程。按任务为重入合约25、访问控制合约25、重入节点60、访问控制节点60；节点任务包括每类10次G0P。恢复前71项成功结果只读复用，恢复后99项完成，其中重入节点fold7/G3使用获准的attempt_002，从同一封存零步初值开始，原attempt_001仍完整保留。不得将170个成功结果与中断尝试混为额外随机种子实验。

本次收尾仅追加文档与独立完成核验记录；没有改计算源码、图、特征、标签、划分、初值、学习率或早停规则，没有重训、换seed或删除结果。原plan/seal与runtime_cache_fix_v1、runtime_resume_v2均保留；训练运行版本仍为02db061c / runtime_resume_v2，v3只是控制器启动记录。本次逐一复核170份成功收据SHA、16份汇总产物SHA及报告绑定的plan/complete，并复核旧中断现场所有文件SHA。记录在prompt8h_v1/final_review_2026-10-31.json。

本批主口径为N-anon-s特征、L-audit节点标签视图、冻结分组nested划分：inner train更新，inner val选best/早停，outer仅评分，完整固定图前向。节点主指标排除C2_include=false，不是去重源码行F1；orig-all在全部原HCG节点上以原标签独立报告。合约标签维持原值。外层评价仍为同一数据集上的交叉验证，且完整图前向有传导式设定，不能称独立外部测试或已证明跨项目泛化；L-audit是诊断标签视图，未确立真实漏洞金标准。

**best主结果：各折等权Buggy-F1均值（%）**

| 任务 | G0 | G1R | G2R | G3R | G3 | G0P |
|---|---:|---:|---:|---:|---:|---:|
| 重入合约 | 93.6807 | 95.1111 | 95.0159 | 95.0159 | 95.1526 | — |
| 访问控制合约 | 91.0199 | 92.0589 | 92.0589 | 93.0075 | 93.0075 | — |
| 重入节点 | 98.0885 | 98.2683 | 99.1376 | 99.1246 | 98.9613 | 98.0312 |
| 访问控制节点 | 97.7105 | 97.7369 | 98.2142 | 98.3536 | 98.1856 | 97.5643 |

G0是同批匿名特征、分组划分及标签口径下的原HCG基线，不是论文表格数字。best严格取最低inner val loss，并非最高outer F1。

G3R−G0的配对BF1差值：重入合约+1.3352个百分点（2升/2平/1降）；访问控制合约+1.9876（2升/3平/0降）；重入节点+1.0361（10升/0平/0降）；访问控制节点+0.6431（9升/1平/0降）。合约5折仅描述性报告，不给显著性结论。预先指定主终点仍为重入节点G3R−G0：差值样本标准差0.6317个百分点、折bootstrap区间[0.6815,1.4253]、双侧Wilcoxon原p=0.001953125、四对照Holm后p=0.0078125。只有单seed，交叉验证折共享训练数据，这些统计不能解释成独立seed方差或以节点数夸大独立实验数量。

G*按预先固定的inner validation、各任务/折等权规则选择为G3（95.0935）；未使用outer指标选型。G*与主终点G3R是不同角色，不能因G2R重入节点均值略高而事后替换主终点。G2R重入节点99.1376与G3R99.1246接近，当前结果不能写成每新增一层关系都必然改善。G3R−G3在重入节点仅+0.1634个百分点，双侧p=0.193359375；不能据此断言双向总优于正向。

**last辅助结果（G0 → G3R，BF1均值%）**：重入合约91.8755→97.1921；访问控制合约79.1319→84.0331；重入节点98.2460→99.3010；访问控制节点97.9105→98.3999。方向与上述best一致，但last绝不替换best主结果。orig-all辅助best节点结果：重入95.8174→97.0159，访问控制93.5150→94.5056；不能与L-audit主表混用。

**关键词与外推限制**：同一L-audit pooled口径下，重入关键词BF1=85.5696，G3R=99.1158；访问控制关键词BF1=99.5114，G3R=98.3736。因此访问控制仍有明显关键词可解性与天花板，不能因模型均值改善就声称已摆脱数据捷径。访问控制nonSolidiFI仅20个正例，G0 TP=0/FN=20，G3R TP=2/FN=18；仍有困难真实样本未解决。小子集按预注册只给计数与P/R描述性Wilson区间，不给F1置信区间；pooled与等权折均值分开报告。图关系参数、消息聚合和优化路径都变化，不把差值全归因为纯依赖语义的因果贡献。

资源：170个成功fit记录的训练耗时合计17329.67秒（约4.81小时），不含准备、完整验收、先前中断fit和睡眠等待。峰值allocated=1895.21MiB，reserved=2094MiB，整卡最小free=44MiB；13次标记memory_tight，成功fit中possible_memory_spill=0。后者只是采样规则未触发，不能据此证明没有分页。local_dev_v1允许低显存记录而不中止；全部checkpoint重载检查通过。最终实验仍按用户计划在显存充足的服务器运行，本批是本机RTX3050 4GiB结果，不自动混入未来服务器结果。

测试沿用正式恢复前已完成验收：v2 2653通过＋原回归223通过＝2876项唯一测试，0失败/跳过；80定向包含在全量内，警告分别4/9/29为既有依赖/弃用警告。本次只追加文档与只读SHA核验，没有再运行训练或重复整套测试。缓存冲突修复、32轮外部中断、临时目录清理与只读扫描并发冲突的历史现场均保留，详见70.11—70.13，不抹去失败历史。

交付目录：scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/reports/，含REPORT.md、report.json、selection.json、逐折/均值/配对差值/Holm、best/last、orig-all、pooled OOF、关键词、错误概率变化、关系支持/梯度、资源及历史名称描述性对照共16项绑定产物；reports/receipt.json绑定它们的SHA。此次停止在完整170项及汇总，不启动更多seed、其他五类漏洞或模型扩展；未自动push。
