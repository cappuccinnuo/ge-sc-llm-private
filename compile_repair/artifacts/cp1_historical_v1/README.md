# CP1 历史编译器与生产 D3（修改 AI：Codex）

依据 PROMPTS r2.6 §4.3 第 6 节，只测量、不修改 0.4.12 候选下限。plan.json 绑定四个已安装历史编译器与全部输入：CP0 矩阵里 0.4.0/2/9/11 的 rc0 文件分别 9/4/2/4，另每版一份 compat_04，合计 23 组合。

前置 compile_file 在仓库根执行，每组合一次，23/23 rc0。每个组合随后在仓库根和 / 分别运行 run_slither(profile=production)，共 46 次；实际 CWD 和先前编译命令分别记录，不能将 equivalent_solc_argv 误当作 Slither 内部未暴露的子进程退出码。版本与信任沿用原记录，未获取新编译器。

两个 CWD 的结果逐版相同：0.4.0 每个 CWD 0/10 D3、缺 filename 287 节点；0.4.2 为 0/5、50；0.4.9 为 0/3、362；0.4.11 为 5/5、0。总计 10 次 D3 通过、36 不通过，缺 filename 1,398 个节点。逐条 D3(a)/(b) 与失败诊断在 invocations.jsonl，汇总在 results/counts.json。测量 3.887 秒，完整进程 7.351 秒。

建议保持 0.4.12；0.4.11 的五份输入结果只支持有限测量结论，不代表任意源码或完整图语义已验证。若扩展需先审查与用户决定。本轮不更改源码、探针、编译参数或已有 CP0/CP0.1 文件。执行脚本为 ../cp1_development_v1/run_historical.py，原命令与压缩日志在同目录 historical.json/log.gz；总报告见 ../../CP1_REPORT.md。
