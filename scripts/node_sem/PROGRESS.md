# NodeSem 实施进度

## 2026-11-01 NS-P0：只读侦察完成（修改 AI：Codex）

**输入与范围**：node-sem，起始 HEAD 489cebe29181bddbd9fa6170fc4498f082fc9ac7；开始时 pull --ff-only origin node-sem 返回 Already up to date。完整阅读设计第1—4节、共享上下文5.1及NS-P0。只实现侦察，不提前创建NodeSemAdapter、特征/训练模块或NS-P1测试目录。

**新增文件**：RECON.md、recon.json，以及recon/inputs.py、carrier_probe.py、text_ast.py、cfg.py、run.py。另追加根HANDOVER和docs/training_changes_2026-10-07.md。原DFG目录、HGT/tokenizer、图/特征/标签/折/初值/plan/seal均未改。

**验收数字**：
- 60/60份G0/G3R成功收据、2137个唯一文件SHA，四任务30折完整；每折配置、prepared初值与receipt绑定一致。
- 真实重入节点G3R 12223节点/23703边：512→600维构造8.462→9.494秒，参数5111012→5302500；17个Linear(600,128)替换、注册与临时binding通过；篡改manifest正确拒绝。
- G0 layers=0节点/合约前向反向与梯度审计通过，独立公式逐位一致；0优化器更新、原图/参数不变。A/B没有做真实600维HGT前向，尚未验证完整NodeSemAdapter。
- 四任务原节点匿名文本全覆盖：18312/12036/13432/7710；删除注释后ERROR/MISSING仍0、执行token不变。覆盖的是文本与AST身份，不等于所有DDG支持。
- legacy→v2 CFG可构造3135/3404、1964/2045、2797/3148、1859/1958；这是CFG覆盖，不是完整RD支持。

**实际命令与结果**：在mando、CPU，设置PYTHONDONTWRITEBYTECODE=1、OMP/MKL线程2、TREE_SITTER_LIB_DIR为既有linux-x86_64库。
- python -B -m scripts.node_sem.recon.run：全量侦察断言通过，169.64秒；详细JSON含代码/输入SHA和逐函数/逐节点证据。
- python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests：2653通过，9条既有弃用警告，171.91秒。
- python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py：223通过，29警告，4.16秒。
- 合计2876项唯一测试、0失败/跳过；5份新脚本Python3.7语法通过。回归内部沿用合成fixture训练，未启动新的真实数据fit。

**用户批准与差异处理**：用户明确同意NS-P0用侦察断言和两套既有回归，专用NodeSem tests目录延至NS-P1。8H旧plan.runtime不是当前实际运行版本：此前已批准cache/resume修订，当前_code_refs与runtime_resume_v2一致且原execution.load通过；保留全部旧seal，不新增豁免。checkpoint的torch.load被自动审批拒绝后，仅做文件SHA及非执行ZIP/pickletools静态头检查，没有绕过；state_sha256跨JSON引用一致，未独立重算tensor digest或重载60个模型。

**待下一阶段征询，尚未更改方案**：
1. Projector需结构性label作AST身份，但特征白名单禁止任何label；需明确身份边界及扰动验收。
2. 所有DATA_DEF_USE边不直接带变量名；M2需明确绑定既有L1 sidecar和8G匿名化。
3. if/while条件支配不等于守卫通过；当前CFG无分支极性/显式require异常出口，NS-P3应区分未知。
另提醒后续配置必须保留layers=0，不能使用layers or default。

资源外推N-A/B/C/D仅历史fit计算约4.814/2.473/3.475/1.738小时，不包括特征编码/LLM/蒸馏、构造验收和新适配器；不是运行时承诺。最终实验按用户安排在显存充足服务器执行，当前RTX3050 4GiB仅是本机开发限制。

本轮结束于NS-P0验收与本地NS-P0提交；不自动推进NS-P1、正式训练或GitHub推送。
