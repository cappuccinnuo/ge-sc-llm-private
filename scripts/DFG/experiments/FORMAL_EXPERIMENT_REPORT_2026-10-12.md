# MANDO-LLM + DDG 正式实验：准备与阶段 B 报告

修改 AI：Codex；日期：2026-10-12；时间以JSON的UTC记录为准。
基础提交：70c9d44b183dd81910fb5a9bdc30f3f9424e16b2。本地HEAD与origin HEAD只读核验相同；
没有pull/merge/checkout，本轮新增文件尚未提交。证据：audit/formal_20261012_v1/git_provenance.json。

**当前：阶段 A、B 通过；C未启动；没有完整CV汇总。**

## 1. E0/E1与冻结输入

| 项目 | E0基线 | E1增强 |
|---|---|---|
| 图 | 作者固定CFG+CG HCG | 同图只增加正向DATA_DEF_USE |
| 节点、标签、源码映射、原边 | 原样保留 | 与E0相同 |
| 节点特征 | 本地核验CodeT5p-770m tokenizer IDs，512维float32，inside_token | 完全相同 |
| 模型 | 原HGT，从E0自身schema注册 | 原HGT，从E1自身schema注册 |
| 初始化 | 语义共同初始化 | 共同参数按类型/关系对齐，新增关系独立初始化 |

E0是本地受控基线，不是论文表中的数值，也不是narrow图。作者标签版本固定为
released_author_node_labels；特征来自本地重建，已逐节点核验，不能声称是作者发布的特征。
tokenizer=Salesforce/codet5p-770m，
revision=3f7cc6e80aee6612f41253b5ee28f09f86faa35f，未加载完整LLM权重。
E0不塞空DDG，E1不使用训练后的E0权重。

| 类别/任务 | 文件 | 节点 | 基础边 | 新增DDG | 漏洞节点 |
|---|---:|---:|---:|---:|---:|
| 重入/合约 | 142 | 18312 | 19267 | 3363 | 6570 |
| 重入/节点 | 71 | 12036 | 11710 | 1711 | 6570 |
| 访问控制/合约 | 114 | 13432 | 15538 | 3765 | 2977 |
| 访问控制/节点 | 57 | 7710 | 8840 | 2632 | 2977 |

节点任务沿用buggy文件子集，指标统计单位仍是图节点，不在本轮增加去重源码行指标。

## 2. 执行计划与对模板的调整

主协议paper_kfold / ddg-paper-kfold-v1，初始化另记为semantic-paired-native-xavier-v1。
合约5折/节点10折，主train为旧inner_train与inner_val并集，val为旧outer_test。
完整固定任务图注册及前向；文件batch或节点mask监督。val用于早停选best并评分，
所有结果必须称CV validation，不是独立测试。nested_strict不参与本批统计。

- B的fold0属于正式任务，C复用，不重跑挑结果。两类共30配对折=60次拟合，B后剩58次；不是7类全量。
- 恢复仅到折级：成功折验证后复用，失败保留旧attempt并显式重试整对。原程序无可靠epoch-resume入口，不伪装支持。
- 显存既测双模型同时加载，又测完整图的一次训练/验证；权重占用不能代表训练峰值。
- 早停沿用当前冻结实现patience7/delta0.001，best保存严格最低val loss；
  不切回历史上游旧错误逻辑，不按最高F1挑轮。
- 阶段C增加显式--confirm-stage-c，须B验收通过；本轮只A/B。
- 额外保存逐样本错误转移。下降/无提升及无训练DDG支持的折均保留。
- 代码/图/标签/划分变化时当前批次拒绝继续，须另建版本，避免混合结果。
- narrow、nested、多seed、随机边对照保留为后续独立实验，不混入主结果。

## 3. 新代码与范围

全部在scripts/DFG/experiments/，原paper_run和模型代码未改：

| 文件 | 作用 |
|---|---|
| resource_probe.py | CUDA/nvidia-smi、主存检查；双模型加载与一次性Adam训练探针，失败blocked、不降级 |
| formal_worker.py | 包裹原make_model/fit_variant记录参数量、显存和monotonic耗时；finally恢复引用，不改数学计算 |
| formal_checks.py | 逐轮重放早停/LR；验收图/标签/schema/监督/初始化/checkpoint绑定；重算预测、差值、错误转移及完整折汇总 |
| formal.py | 冻结计划、B/C门槛、任务顺序、互斥锁、PID启动时间保护、失败保留/重试、成功复用 |
| tests/test_formal_checks.py | 历史、指标、完整性与汇总测试 |
| tests/test_formal_controller.py | 门槛、任务屏障、恢复、损坏拒绝、并发、代码/输入漂移及真实清点 |
| tests/test_formal_end_to_end.py | 原HGT两种任务真实小图full训练和验收，故意破坏checkpoint验证拒绝 |
| tests/test_formal_telemetry.py | 包裹异常恢复、CPU统计、CUDA缺失时禁止自动降级 |

小图是人工图夹具，不是Solidity编译验证。没有改DDG/HGT/tokenizer/原训练脚本，
没有重建图、改标签/特征/划分，没有覆盖旧nested结果。
README、training_changes第14节、HANDOVER仅追加；旧正文与字节备份保留。
67个本轮前记录文件的前后摘要核对见audit/formal_20261012_v1/final_verification.json。

## 4. 阶段A资源

WSL Ubuntu-22.04/mando，Python3.7.12，torch1.8.1+cu111，DGL0.6.1；
RTX3050 Laptop GPU 4096MiB，CUDA可用。最初空闲约3227MiB，后续探针约3454MiB；
均为当时采样。磁盘可用约885GiB。

| 任务 | 双模型加载峰值MiB | E0训练探针峰值MiB | E1训练探针峰值MiB |
|---|---:|---:|---:|
| 重入/合约 | 110.41 | 2099.29 | 2446.86 |
| 访问控制/合约 | 90.88 | 1535.12 | 1829.36 |
| 重入/节点 | 82.28 | 1340.36 | 1536.18 |
| 访问控制/节点 | 65.61 | 900.76 | 1071.86 |

表中是PyTorch allocated峰值，非整卡占用；另有CUDA上下文、缓存及桌面程序。
四任务探针通过，包含前向、反向、参数更新和验证，权重全部弃用。

正式B的E1峰值2.58GiB allocated/2.78GiB reserved，比一步探针高。
一次整卡采样达3917MiB，仅余59MiB；显存余量窄，未来竞争可能失败。
不能因此自行缩图/改超参。单折产物318MiB，按同规模30配对粗估9.3GiB；
不含重试备份，实际依任务不同；没有承诺全量耗时。

## 5. 阶段B实际结果：重入合约fold0

113训练文件、29验证文件（15正/14负）；CUDA、seed1、50epoch上限。
合约Adam初始lr0.0005，OneCycle max_lr0.01，div_factor20，weight_decay5e-6；
节点预定0.0002/0.005/div25/weight_decay0，尚未正式运行。
共同设置hidden128、2层、8头、dropout0.2、patience7/delta0.001。

E0/E1均第14轮早停，best均第7轮；JSON epoch从0计数为6/13。

| 权重/方法 | Buggy-F1% | Macro-F1% | 正类Precision% | 正类Recall% |
|---|---:|---:|---:|---:|
| best E0 | 84.6154 | 86.0577 | 100 | 73.3333 |
| best E1 | 84.6154 | 86.0577 | 100 | 73.3333 |
| best E1−E0（百分点） | 0 | 0 | 0 | 0 |
| last E0 | 92.8571 | 93.0952 | 100 | 86.6667 |
| last E1 | 88.8889 | 89.6057 | 100 | 80 |
| last E1−E0（百分点） | -3.9683 | -3.4895 | 0 | -6.6667 |

best的离散预测相同：25正确、4漏报。last中E1新增simple_dao.sol漏报，
没有修正其他错误。best loss约0.28165/0.28257。
F1更高不等于交叉熵更低，不能事后改为last主评分或重新挑epoch。

| 审计项 | E0 | E1 |
|---|---:|---:|
| 参数总数 | 4526962 | 4641874 |
| canonical relations | 165 | 179 |
| 训练DDG边 | 0 | 2665 |
| 14轮DDG message监督梯度L1累计 | 0 | 4.781603 |
| DDG message权重变化L1 | 0 | 1494.641465 |
| fit+验证+checkpoint IO/重载耗时秒 | 105.59 | 132.22 |

E1多114912参数，不能说参数量完全相同。梯度是跨轮/关系/层累计量，
不是标准化效果指标；参数变化还可能含weight decay。
best/last重载logits逐位相同，预测重算、LR、监督、checkpoint/输入绑定均通过；
评分期间未创建参数。本折无验证独有关系，其他折仍按原策略审计并保留。

实际重新调用stage-b，只打印REUSE verified，没有新attempt或训练。
单折明细：audit/formal_20261012_v1/stage_b_summary.csv/json。
完整权重与预测：新批次jobs/reentrancy_author_contract_fold0/attempt_001/。
只有一折，不能计算完整CV均值/标准差，不能判定DDG最终有效或无效。

## 6. 测试与可运行命令

mando环境：PYTHONDONTWRITEBYTECODE=1、OMP_NUM_THREADS=1、MKL_NUM_THREADS=1、
TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64。

~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/experiments/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests
python -B -m pytest -q -p no:cacheprovider tests
~~~

实验133 passed/4 warnings，DDG170/28，原项目25/7，共328 passed，0失败/跳过。
警告为既有distutils、NetworkX弃用；无依赖升级。
DDG pytest打印了负计时，外部monotonic约3.4秒；保留原日志；
训练计时用perf_counter，不采用这个负值。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm

python -B -m scripts.DFG.experiments.formal verify \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1

# 已完成时只复用验收结果
python -u -B -m scripts.DFG.experiments.formal stage-b \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1

# 仅在明确决定继续全部其余折后执行
python -u -B -m scripts.DFG.experiments.formal stage-c \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1 \
  --confirm-stage-c
~~~

失败先检查日志，显式追加--retry-failed才重跑整对。仍活着的旧worker会阻断重复启动；
成功结果损坏不会被静默重训掩盖。不是epoch续训。
C顺序为重入合约5→访问控制合约5→重入节点10→访问控制节点10，
每任务完整验收才继续；不删折、不换seed。输出路径和tail命令详见README末尾。

## 7. 后续分析及未执行

下一步需用户确认再做剩余29配对/58次。之后看等权折均值/样本标准差(ddof1)、
逐折成对差值、错误转移、DDG支持/回退覆盖与best/last分歧。
没有提升也保留，禁止根据验证成绩修改标签/折或挑选超参。

未执行全CV汇总、narrow/nested新实验、多seed、随机边控制、独立源码行F1、
状态/mapping/跨函数扩展、反向关系、新solc；不宣称完整Solidity DDG。
论文数字仅外部参考。作者标注历史仍不完全明确，文件切分未消除模板复用，
同val选模评分有偏差。新增关系同时增加参数并影响HGT关系聚合；
E0/E1衡量这次增强整体效果，不能单独证明所有收益来自依赖语义。
