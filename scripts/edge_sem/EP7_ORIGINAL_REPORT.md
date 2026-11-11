# EP7 原名主视图修订

日期：2026-11-11。原实现与匿名准备提交：d81e7c1d。用户选择“先调整主视图，再封存执行方案”，并明确授权8个GPU探针、1个范数试点和20个正式G3R拟合。结合用户此前“后面的实验使用原来的，不在匿名化上开展”的明确要求，本轮主视图改为原名S0；匿名接口保留供以后对比，本轮不训练匿名视图。

## 方案与授权

- D1：原名S0为主视图。原匿名计划仅作历史封存，不执行，也不与原名结果混合。
- D2：保留P2，50轮、按严格最低inner_val loss选best、使用新鲜G3R锚初值。
- D3：保留原请求中EP9后冻结关系/属性/超参数并用于七类的规则，不按类别调参。
- 执行顺序：8次单轮显存探针 → 1次50轮G4R-A仅训练范数试点 → 20次G3R正式拟合。沿用3.5GiB探针门槛，错误停止，不自动重试。
- 原始答复及解释单列于 `artifacts/ep7_original_v1/user_decision.json`，未将用户选择改写成“同意匿名主视图”。

新批次：`scripts/edge_sem/artifacts/ep7_original_v1/`。旧 `ep7_v1/`、旧protocol_p2登记、初值、计划和seal均原字节保留。新登记位于新批次 `protocol_p2/registration.json`；提交后另建decisions和执行授权。

## 实际改变与不变项

只切换原名token特征引用，并重新绑定特征/初始化来源和运行版本。原图、节点顺序、标签、划分、边、边属性、P2配置、种子、模型结构及初始张量不变。没有添加NodeSem CODE/CTX/STATIC或LLM模态。

原名特征路径取自已封存的 `8H.source_preparation.tasks[task].feature_view.original`，未凭文件名猜测，也未重新编码。继续调用冻结 `spelling_features.assemble`；该函数已经同时支持original和anonymous。

| 任务 | 原始节点数 | 匿名→原名向量变化节点 |
|---|---:|---:|
| reentrancy_node | 12036 | 11224 |
| access_control_node | 7710 | 7436 |

每行仍为float32[512]；两视图的节点身份和顺序完全一致。原名装配后的整图指纹与原图完全相同，辅助节点特征未变。

## 验收

26个准备配置全部完成。逐个验证：原名新构造的参数与旧封存零步张量逐位相同，严格reload相同，原图token精确恢复，support与edge binding相同。直接引用原26份零步文件，新增权重文件为0，避免复制550093510字节。

新增原名/匿名选择、错任务、错NPZ、混合计划、登记视图、决策不匹配和源SHA篡改拒绝测试；连同原训练数值等价/执行策略，**26项定向测试通过**。此前4318项完整回归作为历史验收保留，不把它们写成本次全部重新执行。

新plan封存后再次从各自初值构造真实重入fold0 G3R及G4R-A，完整绑定和监督接入通过。CPU验收未初始化CUDA，optimizer_steps=0。原三个匿名计划仍可只读核验；299份旧EP7文件、750份冻结源码及1134份更早产物全部不变。

证据：
- `cpu_acceptance.json`、`sealed_plan_cpu.json`
- `preparation/index.json`及seal、26项proof
- `feature_difference.json`
- `targeted_revision2/result.json`、原始日志和JUnit
- `archive_revision_checks.json`

只读语法探针首次误向Python3.7的ast.parse传入较新版本的feature_version参数，在读取计划之前停止；改用Python3.7原生ast.parse后通过。未涉及训练或输入修改，诊断保留于development_syntax_check.json。

## 代码与历史比较边界

新增 `feature_views.py` 和 `recon/ep7_original.py`，扩展execution的显式视图分派、protocol_p2的视图决策和analysis_ep7的报告身份。正式trainer、优化器、调度、监督、评分算法未改。新运行清单为28个EdgeSem模块加354个冻结引用，共382项。

和历史8H的比较仍只作描述：除了P2与新鲜锚初值，现在还存在匿名/原名token视图差异，不能将分数差异解释为单一因素收益。EP8/EP9如继续，须沿用本轮原名G3R基线和同一主视图；本轮授权不自动涵盖这两个阶段。

最终实验计划在显存充足的服务器运行，当前4GiB限制仅属于本机。

## 实际执行命令

```bash
# mando，WSL工作树；CPU阶段 CUDA_VISIBLE_DEVICES 为空
python -B -m scripts.edge_sem.recon.ep7_original prepare
python -B -m scripts.edge_sem.recon.ep7_original seal
python -B -m scripts.edge_sem.recon.ep7_original frozen

# 提交新登记并生成独立授权后，GPU阶段取消空 CUDA_VISIBLE_DEVICES
python -B -m scripts.edge_sem.recon.ep7_original authorize --registration-commit <真实提交SHA>
python -u -B -m scripts.edge_sem.recon.ep7_run --root scripts/edge_sem/artifacts/ep7_original_v1
```

准备与验收已完成；训练执行情况以下方追加记录与批次内complete/failure收据为准。禁止覆盖已存在输出目录。
