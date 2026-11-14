# CP1 生产小样本（修改 AI：Codex）

PROMPTS r2.6 §4.3 第 5 节。sample_plan.json 固定 95 份输入身份：规则 A 不通过 25，七类各 10 个通过文件共 70；三个指定 Slither 失败文件已经在 25 份之内。每类按 SHA256 排序后独立 Random(0).sample(pool,10)，最终路径排序；不按名称决定版本，类别只用于规定的抽样分组。

每个 cases/NNN 都调用同一 cli.main 的 repair --regression mando --order ascending，独立新输出目录，检查该文件结果后才处理下一份。计划和判断条件见 ../cp1_development_v1/run_sample.py；完整命令在 acceptance.jsonl。production profile 固定 0.11.6/0.4.2，92 个支持范围编译器，原文件只读。

结果：95/95 符合预期，92 成功、3 个已知 Slither 侧失败；91 个选版与 CP0 相同，1 个因新增更低的 0.5.5 而不同，无法归因差异 0。197 次 solc、101 次 Slither，347.413 秒。三个失败文件各在 0.4.24/25/26 rc0 后 AssertionError。全部文件改动等级 none，成功节点 11,822 个且标记均 original。无覆盖或跨系列；实际 metadata 命中 0、无 pragma 1。

cases 下 input_record 保存调用方输入和版本证据；input.sol 是字节相同副本；result/manifest 保存尝试链及 provenance；nodes 只含带标记的 node_facts，不是 CP2 完整图；失败无 nodes 文件；invocations 记录每次 solc/Slither；seal 绑定全部 case 字节和工具/代码身份。archive_audit.json 独立回验 95 份 seal、节点计数和差异归因。

复验：读取 acceptance.jsonl 的 cli_argv，将 --output 换为不存在的目录后在 production 环境调用 python -B -m compile_repair.cli。已有证据一律不覆盖。总报告见 ../../CP1_REPORT.md，顶层 seal 哈希见 ../cp1_development_v1/seal_hashes.json。


归档补记（修改 AI：Codex）：95 个原始源码副本中 57 个含原有行尾空白；为保持源码原字节和所有 case seal，将 852 个 case 文件（12,212,867 原字节）确定性打包为 cases.tar.gz，逐成员回读 SHA256/长度全部相同。原 case 目录本地保留且不改，Git 提交无损包和 case_archive_index.json；报告中的 cases/NNN 路径是包内路径。未清理源码空白或排除已暂存文件的检查。审查时在全新目录解包，逐文件按 index 与各 case seal 校验，不能覆盖本地现有 cases。
