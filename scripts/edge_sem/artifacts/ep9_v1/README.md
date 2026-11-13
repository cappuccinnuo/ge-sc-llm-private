# EP9 E-B 执行记录

本批按 PROMPTS r18 执行原名主批60次、匿名敏感性批60次。只读验收并复用 EP7/EP8 的120个 G3R、G3R-T、G4R结果。当前以 `pipeline_complete.json` 和对应 seal 为完成标志；缺少完成标志不能解释为已训练完成。

流程：CPU逐折初值与真实fold0闸门 → 三套CPU回归 → 验收 → 独立plan/seal → 本地提交登记 → 绑定本轮用户授权 → 原名60次 → 验收 → 匿名60次 → 验收、分析、schema冻结与本地提交。任何失败停止并保留现场。

- CPU准备：`python -B -m scripts.edge_sem.recon.ep9_run prepare`
- CPU回归：`python -B -m scripts.edge_sem.recon.ep9_run tests`
- 已运行准备的后续流程：`python -B -m scripts.edge_sem.recon.ep9_run finish-preparation --request scripts/edge_sem/artifacts/ep9_v1/authorization.json`
- 直接执行已授权计划：`python -B -m scripts.edge_sem.recon.ep9_run run`
- 只读旧边界核验：`python -B -m scripts.edge_sem.recon.ep9_run frozen`

以上命令不应重复启动已运行或失败的批次。进度见 `preparation.log`、`regressions.log`、`pipeline.log`、两份计划目录中的各任务收据。相应进程登记为 `preparation_process.json`、`cpu_tests_process.json`、`pipeline_process.json`。权重与检查点只保留本地，提交脚本不会把它们加入Git，也不会推送远程。

原名是唯一主终点；匿名描述性结果不进入Holm族。H1从EP8封存原始p只读获取，H2按原登记的两项配对对比取max-p，最终Holm族为H1/H2。先导范围仅重入与访问控制的节点任务。最终七类实验将另在显存充足的服务器执行，本轮不自动开始服务器阶段。


## Git 无损交付

大于等于1MiB的JSON以github_delivery/objects中的gzip副本交付，原始JSON保留在本地；manifest包含原SHA、字节数和恢复命令，恢复时拒绝覆盖不同内容。先恢复再使用指向原始JSON的plan/seal。正式权重与NPZ不进入Git。最新等待调度见delivery_revision1/pipeline_process.json，回归见cpu_tests_delivery1。原进程和首轮回归记录保留。
