# CP4.1 缺包文件迁移与最终验收

修改 AI 为 Codex，日期为 2026-11-22（美东）。本批从 `0f690e6f` 的两个评分停点继续。14,196 个已纳入样本全部通过原位置精确还原，114 个有真实包缺失的样本也全部通过文件迁移评分。真值图、各次原分和校验后的分数均可按 SHA256 查回。[验收统计](acceptance.json) · [114 项逐项结果](packages.tsv)

## 复核顺序

1. 用上级目录的 `migration_stop_seal.json` 核对 128 份冻结文件。核对旧候选的 `original_reclassified.jsonl.gz`、新增及补充批的两份观测，再按批次、算子、单元 ID 和编辑 SHA 匹配评分。200 个对照的哈希在验收统计中。
2. 四次运行的通过行依次为 21、19、11 和 63。每一行含原位置与迁移位置的物理图、生产运行结果和调用日志的路径及哈希。完整外部资料位于本机 `compile-repair-local/`。程序使用已通过的旧行时校验整份文件的 SHA，首次发现新差异即留下 `stop.json`。[首批](results/package_scores.jsonl) · [元组续作](tuple_continuation/package_scores.jsonl) · [Yul 续作](yul_continuation/package_scores.jsonl) · [数组定义续作](definition_continuation/package_scores.jsonl)
3. 比较每条记录的 `score`、`migration.raw_migration_score` 和 `migration.migration_counters`。53 个迁移图可以直接匹配，61 个需要核验工具生成的名称。校验覆盖整个图，包括声明、节点、指令的操作和类型、CFG 边、调用目标、顺序和重数。实体同名、解包索引改变、源码或字面量与生成名称冲突都应被拒绝。[比较代码](../../../evaluation/benchmark.py) · [测试](../../../tests/test_cp41.py)
4. `cp3_00706` 的两次 AST 见证在原目录、原版本、原命令下取得。先逐字核对整份 solc stdout 的原 SHA，再核对完整闭包、每份 AST 的原 SHA、编译器源文件清单和 YulSwitch 的源码区间，仅此项目需要重取 stdout。原始输出保存在仓库外，见证摘要含其路径和哈希。[原位置](yul_continuation/witnesses/cp3_00706/truth/verified.json) · [迁移位置](yul_continuation/witnesses/cp3_00706/repaired/verified.json)
5. 最后核对两套模块测试、DFG 回归、代码范围、文档检查和本批封存。测试和评分采用仓库根目录，生产环境为 `compile-repair-production`，mando 用于兼容回归和 DFG。[测试目录](definition_continuation/suites/) · [代码范围](final_scope.json) · [文档检查](doc_check.json) · [封存](seal.json)

## 停点与调用口径

最初的收据核验曾把绝对路径直接与样本相对路径比较，启动编译前即停止。以各自记录的项目根转换路径后，18 个既存图输入闭包的 124 个文件逐一通过校验。两个历史样本的原分随后得到复现。[路径核验](initial_receipt_check.json) · [记录修正](receipt_path_adjustment.json)

用户批准 TMP 和 REF 的全图双射、TUPLE 的有定义且同族的双射，以及有编译器见证的 Yul 源文件编号核验。数组分配的打印器在赋值号前输出两个空格，核验程序按实际格式识别定义，仍逐字符比较两侧空格和其余指令。三处科学停点都复用了已生成的图。[编号授权](authorization.json) · [元组授权](tuple_continuation/authorization.json) · [Yul 授权](yul_continuation/authorization.json) · [数组定义授权](definition_continuation/authorization.json)

汇总脚本的第一版误设每个图都只尝试一个 solc。第二版直接核对调用日志与环境阶段全部尝试、计划前缀和返回码。8 个项目两种位置都先尝试 0.8.0、0.8.1，再由 0.8.2 通过。105 对新增图实测产生 242 次 solc 与 210 次 Slither，另复用 9 对已有图，AST 见证另计 2 次 solc。这次汇总修正只读取现有结果。[首版日志](acceptance.log) · [最终核验脚本](final_acceptance_v2.py)

WSL 的普通新命令曾因内核为 Hyper-V 新通道分配连续页失败而超时。保留的 Bash 完成了整个批次。美东 21:20 的四次普通新命令均在 0.36 秒内返回 UID 1000。已记录一次临时内存整理、已完成文件的缓存提示、期间再次超时及最终实测。[WSL 收据](wsl_recovery.json)
