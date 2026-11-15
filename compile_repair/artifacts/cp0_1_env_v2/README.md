# cp0_1_env_v2：CP0.1 C 续生产确定性与回归（修改 AI：Codex）

2026-11-13，起点 3742fb75e535b5517ded58659e78737a01b51000，按 PROMPTS r2.5 §4.2c 执行。不新建环境、不下载或安装，不覆盖任何既有批次。正式工具版本沿用 B 的 production 0.11.6/0.4.2（Python 3.10.21）；回归为 mando 0.8.0/0.2.4（Python 3.7.12）。

## 结果与证据

| 验收项 | 预期与实测 | 证据（artifacts 下） |
|---|---|---|
| 两次生产编译/D3 | 各 846 次 solc rc0；各 843 D3，通过同一组文件；另 3 个 0.4.24 AssertionError 与 B 完全相同 | cp0_1_env_v2/production_run1.json、production_run2.json |
| 两次指纹 | 843/843 逐文件 node_facts_v2_sha256 相同；各 110,996 个成功节点 | production_run2.json counts |
| 与 B 归档比较 | 839 个成功文件逐组相同；另 4 个审查指定文件各只变 1 行 IR，类型/偏移/序号/length/声明种类不变 | 两次 production_run*.json 的 changed；cp0_1bc_review_v1/ir_object_repr.json |
| 地址残留/归档哈希 | 四份新归档共 2,208 组，残留 object at 0x 为 0；重算指纹与归档记录差异 0 | cp0_1_env_v2/archive_audit.json |
| mando 抽样回归 | 按 SHA256 排序后 Random(0).sample(...,20)；20/20 D3 且指纹与 A 归档相同，3,267 节点，规范化替换 0 次 | regression_sample_plan.json、regression_sample.json |
| 兼容性计划与执行 | 496 原组合 + 5 设置正对照 = 501；501/501 符合预期，未运行 0；按版本升序，未自动重试 | cp0_1_compilers_v2/compatibility_plan.json、compatibility.json |
| 默认设置正例 | 491/491 solc rc0、production D3 通过 | compatibility.json counts |
| 默认设置负对照 | 4 个 0.8.24 Cancun 探针 rc1、1 个 0.8.26 require 自定义错误探针 rc2，诊断与 r2.5 一致；均未运行 Slither | compatibility_invocations.jsonl、archive_audit.json |
| 设置正对照 | 四组 0.8.24 + --evm-version cancun、一组 0.8.26 + --via-ir，5/5 rc0、D3；Slither 记录同样的设置 | compatibility.json results |
| 上次成功组 | 原 C 的 224/224 结果、输入/编译器身份、节点内容与指纹全部相同 | compatibility.json previous_224_equal |
| 覆盖口径 | 可信支持快照 0.4.12–0.8.38 已安装 92/92；本次矩阵覆盖新增的 59 版，59/59 版计划完成 | cp0_1_compilers_v2/coverage.json、compatibility.json per_version |

## 文件

- baseline.json、implementation_audit.json、frozen_audit.json：起始身份、CP0 投影/语法/fixture 检查和最终冻结审计。
- production_command.txt、production_run1/2.json、对应 invocations.jsonl 与 node_facts_v2.jsonl.gz：独立进程两次运行，逐文件即时检查，首个异常即停。
- regression_sample_plan.json、regression_sample.json 与对应调用/节点归档：SHA 排序 Random(0) 抽样和逐组比较。
- archive_audit.json：独立重算全部节点归档哈希与对象地址残留。
- run_checks.txt、test_summary.json、unit_*/pytest_*.json/log：完整测试命令、退出码、耗时和跳过原因。
- *.stderr.log.gz、log_compression.json：原始诊断无损压缩、原始/压缩 SHA 与解压回读校验；原始 .stderr.log 本地保留、不重复提交。
- doc_check_*.jsonl 及调用记录、file_inventory.json、seal.json、seal_hashes.json：文档检查、完整提交清单和封存哈希。pytest 临时树不提交。

## 测试与复现

| 检查 | 实测 | 原始日志 |
|---|---|---|
| 新逻辑与分层（production / mando） | 各 27 passed | unit_production.log、unit_mando.log |
| 完整模块（production） | 506 passed，6 skipped，28.69 秒 | pytest_production.log |
| 完整模块（mando） | 83 passed，429 skipped，6.60 秒 | pytest_mando.log |
| 冻结 DFG v2（mando） | 2653 passed，9 warnings，181.50 秒 | pytest_dfg.log |

```bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
# 下列是实际等价命令；所有输出采用 x/xb 创建，已存在时拒绝覆盖。
env PYTHONNOUSERSITE=1 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/production_command.txt").read(), "production_command.txt", "exec"))' production_run1
env PYTHONNOUSERSITE=1 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/production_command.txt").read(), "production_command.txt", "exec"))' production_run2
/home/zhao/miniconda3/envs/mando/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/production_command.txt").read(), "production_command.txt", "exec"))' regression_sample
env PYTHONNOUSERSITE=1 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_compilers_v2/compatibility_command.txt").read(), "compatibility_command.txt", "exec"))'
# run_checks 会使用对应的已安装解释器、-x 和独立 --basetemp；完整 argv 在同名 json 中。
/home/zhao/miniconda3/envs/mando/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/run_checks.txt").read(), "run_checks.txt", "exec"))' pytest_production
/home/zhao/miniconda3/envs/mando/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/run_checks.txt").read(), "run_checks.txt", "exec"))' pytest_mando
/home/zhao/miniconda3/envs/mando/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/run_checks.txt").read(), "run_checks.txt", "exec"))' pytest_dfg
```

复现时须使用新的空批次目录并相应设置脚本的 out/envout 路径，不能原地重跑已封存批次。实际 Windows 调用为 UTF-8 PowerShell here-string 经 wsl.exe --cd 进入本工作树，执行相同脚本文本；没有 shell 字符串拼接 solc 参数。

## 停止边界

用户本轮明确要求执行 r2.5 §4.2c，并规定需要安装/下载或验收不符即停。本次未发生上述停止条件；没有新增授权请求，没有安装、下载编译器/语料/文档、LLM 调用、全局 solc 切换或 HGT 训练，费用 0 美元。A、B 结论、旧产物和既有 C 失败现场均保留。本步只完成工具链接口与验证：按错误自动触发设置、版本升序选择和两行设置表属于 CP1；第 10 行源码改写属于 CP6，均未实现。CP0.1 C 续已完成本机验收，仍须审查通过后才能开始 CP1。
