# Prompt 8B.0：执行器性能修订与精确等价性证明

日期：2026-10-27（America/New_York）。实施、复核与记录AI：Codex。起点dfg-v2 @ 2d826c22160380760c375501fb0fb3a61dc16a8d；开始时pull --ff-only确认已同步。

**结论：两项真实证明与历史阶段A逐位一致，2331项测试及A的60项完整验收通过；阶段B未启动。** 本轮仅优化编排和校验。

## 1. 文件与接入

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

## 2. 决策与实际调整

1. 用户已批准：DGL 0.6.1 的边视图共享内存但不共享 PyTorch _version，单凭指针/版本会漏掉端点修改。因此增加启动副本与 torch.equal 内容比较，不重建图、不改消息传递；批准原文“同意增加边索引内容比较（推荐）”，完整问题和本轮请求在 user_decisions.json。
2. 缓存只跟随实际完整验收依赖。开发期实测发现泛化递归追踪历史授权中的所有路径，会误把历史 PROMPTS.md 内容要求套到本轮已更新文档。已改为精确依赖清单；没有修改旧授权，也没有一概排除 Markdown：阶段B依赖的 interim 报告仍必须核验。
3. 成功结果之后出现新的不完整/失败 attempt 必须报错，不能让旧成功缓存掩盖；此前失败、后来显式重试成功可以验收。没有无限重试、没有epoch续训。
4. 缓存不把磁盘自报SHA作为可信根。父进程保存seal SHA，ticket绑定进程PID与启动身份、计划、授权、修订和job；过期、错任务或直接绕过控制器的调用被拒绝。
5. “文件哈希一次”只指guard生命周期。计划加载、冻结trainer原有read_labels和最终验收仍按原逻辑核验。target代理仅记录原targets()返回值，没有提前读取outer_test监督或评分。
6. 原native checkpoint不改；包装复制的restore路径在文件头记录来源SHA 7ccef05371f0324271986dce7d274f3a81a45a9af0e3fe10e08c018dcdd2fb99。checkpoint保存格式、每次严格更低val loss保存best、last辅助、8次重载规则均保持。
7. 可选GPU采样对照未执行，采样间隔保持0.5秒。未增加额外旧代码重跑：两次证明已直接与历史A逐位相同，无需触发允许的legacy对照。
8. 快速元数据缓存不是防恶意篡改系统：同时恢复大小与mtime的内容变化可能不被该快速分支发现；最终完整SHA验收仍执行。普通Tensor通过.data绕过_version也不保证即时捕获，三个完整边界仍核对输入指纹；DGL已知视图漏洞单独用内容比较处理。

## 3. 冻结身份

原plan SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de、seal SHA 55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8保持。初值不重新生成；图/标签/token/folds、DDG、HGT/shared层、监督、Adam/OneCycle/早停/best选择和统计算法均未改。

训练计算指定17个文件（8个v2计算文件+9个sco_models文件）SHA与计划逐字节一致；修订检查还保护原runtime中全部其他文件。新增报告前，开始时13013个跟踪文件中13005个完全不变，只有4个编排/校验生产文件与4个测试适配文件改变；历史结果和原图相关跟踪文件均未改。三份记录文档只追加并另验旧正文前缀。

## 4. 两项证明

仅运行 access_control_node/0/1/G0、access_control_node/0/1/G3R 两项新目录证明，复用原未训练初值与fit seed，没有重训正式A或启动B。G0运行20轮（0-based best=12、last=19），G3R运行23轮（best=15、last=22）。

两个任务六项比较全部为true：history损失/学习率/Adam beta/patience/best保存事件、epoch、best state、last state、inner_val预测、outer_test预测；最大损失绝对差均为0.0。binding、initialization_ref、effective_config、model_input相同；预测按完整身份及全部内容比较，不按行数猜测。四个state_dict摘要与旧A一致，见equivalence_result.json。没有放宽阈值，也未触发legacy重跑。

最终batch.verify_stage(A, amendment_path=...)绕过缓存重新核验60/60，耗时200.22秒；正式结果仍G0=30、G3R=30、B=0。新增两项是proof_only/formal_result=false，不进入正式指标。

## 5. 计时与预算

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

## 6. 测试

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

## 7. 修订与证据

新产物目录为 scripts/DFG/experiments/artifacts/dfg_v2/prompt8b0_v1/。stage_B_amendment及seal均在旧批次外排他创建，execution_authorized=false。缓存代次也在新目录；不改旧plan、seal、attempt或interim报告。修订绑定8个文件的新旧SHA、计算文件身份、用户原文、证明SHA；未列出的runtime变化一律拒绝。

- stage_B_amendment.json SHA256：d2c255fb50636f91066cd2a7503715619f5bdb422af3c884727557d261631c8f
- stage_B_amendment.seal.json SHA256：6d4bc3298d89f3fdc5d133dd4871b5f3b91a37327e824bcad5ef29575bd862b1
- proof/equivalence_result.json SHA256：a220362634e3a238e04017d4b42bd880265535544c2d14e4341704a0e6462b43
- performance_summary.json SHA256：dac88d56e4825d015881e88748dbabebfb211a6c895591bdd5f01fbea71c9439
- stage_A_final_full_verification.json SHA256：b57f65c2e0140a37dc7409543c16148a0521399aa365c18a5c6c71e3e33452a7

user_decisions.json保存批准原文，proof/保存两个任务全部本地checkpoint、预测、资源与验收记录；失败开发日志保留。大二进制产物留本地，文本报告不等于完整复现包。

## 8. 已执行及可运行命令

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

## 9. 停止位置与限制

最终正式实验按用户安排在显存充足的服务器整批运行；当前RTX3050 4GiB只是本机开发限制。服务器尚未部署或实际验收，未来仍需核验环境、输入、初始化与独立批次身份，不混合服务器和本机成绩。当前停止在8B.0验收与修订登记：未执行90项B、未选G*、未做完整Holm、额外seed、其他五类或模型改造。按共享上下文仅本地提交，不自动push。
