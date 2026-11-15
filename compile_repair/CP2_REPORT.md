# CP2：MANDO 回归运行、图存储与检查（修改 AI：Codex）

## 实现与范围

起始提交 d56c6e0874bd30a004d7a5c7b4ce9e361d28ed18，执行 git pull --ff-only origin compile-repair 后快进到该提交。已完整读取 PROMPTS r2.8、共享上下文 §4.1、HANDOVER §0–5、DECISIONS、CHANGE_LOG §17/18、cp1_review_v1 与 cp1_1_review_v1 的 README。本步沿用已审查的版本策略和 D3，增加 §3.8/§4.4 的图存储；任意检测输入仍是模块目标，MANDO 只是回归语料。

生产文件改动为 toolchain/slither.py（图序列化）、pipeline.py（标记并写图、逐输入验收回调）、cli.py（将可选验收回调传给流水线）。测试改动为 tests/test_pipeline.py 的替身增加图字段；新增 tests/test_graph.py、tests/fixtures/graph_calls.sol。生产 .py 仍 14 个，符合 §3.10 的目录表和分层；没有新增表外生产模块，没有复制或修改冻结 DFG 函数。

slither.py 的 node_facts、contract_coverage、CP0 投影及原有函数保持；production 在 D3 通过后增加 graph_facts，regression_6c 不启用新图序列化。调用按操作确切类映射，LibraryCall 独立于其 HighLevelCall 父类；任何其他 Call 子类按类名保留。函数目标可解析时记录所属声明合约与 full_name，自由函数所属合约为 <top-level>；不能解析为声明函数时保留规范化操作文本。图序列化自身异常会停止批次，不改变候选或放宽 D3。

### 存储 schema

每个成功输入保存 units/input_NNNN/graph.json，schema 为 compile-repair-graph-v1：

| 字段 | 内容与顺序 |
|---|---|
| declarations | 声明合约/库/接口的函数与修饰器，以及编译单元顶层函数；保留 Slither 遍历顺序，含空 CFG 声明 |
| nodes | key5、node_type、length、declaration_kind、规范化有序 ir、provenance；按 function.nodes 顺序，key5 序号不去重 |
| cfg_edges | source/target 均为 key5；按声明、节点、sons 顺序；kind 为 true、false、next |
| calls | node=调用点 key5，ir_index=节点内操作序号，operation=确切类名，kind=四类标准名称或其他 Call 类名，callee=声明目标或规范化文本 |

JSON 对象键排序，列表保持 Slither 顺序。graph.json 不包含时间或文件绝对路径；这些身份和调用信息保留在清单/调用日志。nodes.json 保留原节点投影形式，新增图不改变原 D3 指纹。失败输入只保留输入与诊断清单，不生成 nodes.json/graph.json。seal 绑定输出文件、编译器身份、工具版本、起始提交和实际 14 个实现 SHA256；费用和 LLM 调用均为 0。

pipeline 的 result_check(record, output_path) 在当前记录已写入并 flush 后执行，只用于验收，不参与选版。检查异常由批次既有停止/封存逻辑处理；测试确认第二个输入不会开始。正式运行仍经 cli.main 的 repair --regression mando 入口；完整 argv 保存在各阶段 plan.json，未建立第二套选版实现。

## 用户批准与原文差异

前置核验发现 §4.4 第 2 节的三类归因不能描述一个既有差异：reentrancy/source_files/0xa2e4fb662ba999a1e1bac839340c4d34e36e5d19.sol，SHA256 为 5ec2ee307684c021492194d5e63593834e164bcf878d1cddb48a0b1e1ad13237，在 6c 为 0.4.11，cp0_v2 已选 0.4.12；原生产归档同样为 0.4.12、11 个节点。0.4.12 原已安装，既不是新装更低版本，也不是 Slither 升级或设置重试造成。

按用户与 §4.1 要求，先暂停正式运行并给出具体建议。2026-11-14 用户回复“允许单列既有下限差异，记录后继续”。仅在 CP2 与 6c 的版本归因中单列该项；CP2 与 cp0_v2 仍严格按 (a)/(b)/(c)，D3、0.4.12 下限和 239/239 精确重放标准保持。授权在 artifacts/cp2_development_v1/attribution_authorization.json，DECISIONS 已追加；PROMPTS 原文未修改。

请求文件曾把所有可信编译器 96 个写在 current_supported_compilers 字段下，已保留原记录并用 compiler_count_clarification.json 澄清：92 个支持版本、4 个历史对照；生产候选按原规则排除历史对照。没有变更实际支持范围、安装或下载。

## 测试与开发记录

| 检查 | 实测 | 来源（cp2_development_v1 下） |
|---|---|---|
| production 模块 | 567 passed / 6 skipped；54.56 秒 | pytest_production.json、压缩日志 |
| mando 模块 | 130 passed / 443 skipped；12.85 秒 | pytest_mando.json、压缩日志 |
| mando 冻结 DFG v2 | 2653 passed / 9 个既有警告；159.05 秒 | pytest_dfg.json、压缩日志 |
| 真实调用探针 | 7 个声明、41 节点、36 边、15 调用，覆盖全部 10 类 | test_evidence_production.json.gz 中 graph_probe.json |
| 图确定性单测 | 同一合约在两个输出目录中图字节相同，节点全 original | test_real_graph_storage 的归档 |
| 停止单测 | 当前输入记录先 flush，验收异常后停止、封存，第二个输入未启动 | test_acceptance_callback 的归档 |
| 序号与分支 | 重复节点 key4 的 key5 序号保留；sons 顺序与 true/false/next 均验证 | test_graph.py |

15 次调用分别为 internal 3、high-level 2、low-level 1、library 1、InternalDynamicCall 1、Send 1、Transfer 1、SolidityCall 3、EventCall 1、NewContract 1。LibraryCall 未归为 high-level，modifier 与顶层函数均覆盖。这里只验证图抽取与存储，不据此宣称证明所有 EVM 语义。

三轮 pytest 均首次通过，没有失败重试。前置工具问题已记录于 baseline.json：PowerShell 直接读 UNC 被拒后改用已有的 scoped WSL；两次只读 Python 命令转义错误在写文件前修正；WSL 没有 rg，使用现成 grep/sed/Python。冻结 code_refs 导入首次误放 production，该环境无 torch；在创建基线文件前失败，随后改用已安装的 mando，未新增依赖。测试临时目录位于 /tmp，旧产物和旧测试临时树未删改。

测试证据的阶段封存为 cp2_development_v1/evidence_seal.json，SHA256 f698f41bf19ce39cee51b363199c32b6293ca6446ddedf850be4ee8c5eb608b9。它记录的是归因授权前已完成的开发证据，status=awaiting_attribution_review 是该时点状态；后续授权与正式结果另行追加，不回写此快照。

实际测试命令由 run_checks.py 保存到 pytest_*.json，核心命令如下（环境变量 PYTHONDONTWRITEBYTECODE=1、PYTHONNOUSERSITE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2、TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64）：

```bash
/home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests --basetemp=/tmp/cp2_production_pzbrwr0d/pytest
/home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests --basetemp=/tmp/cp2_mando_0get6xoe/pytest
/home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -ra -x -p no:cacheprovider scripts/DFG/dfg_v2/tests --basetemp=/tmp/cp2_dfg_2y6ev6tl/pytest
```

以上是本轮已执行命令。复测必须改用新的临时目录和新批次，不能覆盖本次证据。


### 6c 精确重放的路径绑定

运行前只读核验报告中的原始绝对路径：239/239 均位于 /home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code，文件存在且 SHA256 与 6c 及本工作树输入相同，见 historical_source_path_audit.json。精确重放保留这些 6c 原调用目标，从用户指定的 compile-repair 仓库根运行；不将原始目标重定位为新工作副本，不修改原文件。路径与工作目录会影响旧 0.4.11 的映射行为（既有 §1.9 结论），因此把原目标路径纳入 plan/invocations，并在编译前后核对 SHA；比较仍严格使用已批准 occurrence 多重集合键。此为未运行前的路径选择，不是失败后的重试或放宽标准。


## 真实验收：生产运行通过，6c 第 87 个输入停止

来源为 cp2_development_v1/cp2_summary.json、ascending1/2_acceptance.jsonl、各阶段 receipt/invocation 和 cp2_6c_v1 的 summary/comparison。CP2 整体未通过；以下逐项区分通过、失败与未运行。

| §4.4 项目 | 预期 | 实测与状态 |
|---|---|---|
| 第一次生产全量 | 846 个输入，仅三份已知 Slither 侧失败 | 843 success / 3 unrepaired，通过 |
| 第二次生产全量 | 同上，成功图逐单元确定 | 843 success / 3 unrepaired；843/843 graph.json 字节相同，846/846 状态与版本相同，通过 |
| 图存储 | 节点、CFG 边、所有 Call 子类、改动标记 | 每轮 110,996 节点、87,645 边、45,565 调用；节点全 original，通过 |
| CP0 版本归因 | 不同项限 (a)/(b)/(c) | 成功文件 842 同版本、1 项 (a)，通过 |
| 同版本生产归档 | key5 + 规范化 IR 逐组相同 | 842/842 相同，通过；1 个不同版本不纳入同版本比较 |
| CP2 与 6c 选版 | 列出全部差异及原因 | 238 同版本、1 个已批准的既有下限差异，通过；不是重放通过数 |
| 6c 精确重放 | 239/239 occurrence 多重集合相同 | 87 已运行：86 相同、1 不同；首差即停，不通过；152 未运行 |
| 降序跨版本 | 成功文件升降序 key5、有序 IR 比较 | 未运行；6c 停止后没有继续该阶段 |
| 分布审计 | 按目录统计，不读标签 | 已从第一次生产清单离线汇总，见下表 |

两轮未修复均仅 reentrancy/source_files 下的 reentrancy_bonus.sol、reentrancy_cross_function.sol、reentrancy_insecure.sol。失败单元保存输入/诊断清单，没有节点与图产物，未实施 CP6 第 10 行改写。生产 CLI 因存在这三个 unrepaired 返回 2；验收包装器验证它们确为预期集合后返回 0，此处不是把失败当成功。6c 包装器则以 2 退出并记录 stopped，没有替换为通过。

第一次主阶段耗时 275.856 秒、完整命令 276.722 秒；第二次 276.572 / 277.496 秒。它们是本机实测，不能直接沿用 PROMPTS 的每轮 50–60 分钟估计；未测定时间差的原因或外推其他机器性能。第一次调用日志包含 948 次前置 solc、852 次 Slither API 调用，累计记录耗时 70.651 / 170.138 秒，均能追到版本、可执行文件 SHA、设置与结果。没有读取旧图替代本次编译。

CP0 唯一版本差异是 unchecked_low_level_calls/source_files/0x366cf49c6bc3986b20ecf4fd7c05f0c617332e8c.sol，SHA256 f0028ebd798334727aa07d9857bc3996563b8dc250b899882cb1346fc5d24014，CP0 的 0.5.6 → 本轮 0.5.5；0.5.5 不在 CP0 的 37 版清单中，已由 CP0.1 安装并纳入可信清单。本轮该版本 solc rc0、production D3=true，属于 (a)“新装更低版本”，不是本轮下载安装。对应 input_0683 的图有 151 节点、116 边、61 调用。其余 842 个成功输入与 cp0_1_env_v2/production_run1_node_facts_v2.jsonl.gz 同文件同版本比较，不按 length 判差。

### 按类别目录的分布（不是安全标签）

来源列顺序为 pragma_intersection / no_pragma_inferred / no_pragma_guess；版本列只统计成功文件的 0.4 / 0.5 系列，失败文件没有选定版本。类别名仅用于此处汇总，不用于选版或判定漏洞。

| 类别目录 | 输入 | 成功 / 未修复 | 来源三类 | 版本两系列 | flags |
|---|---:|---:|---|---|---|
| access_control | 114 | 114 / 0 | 109 / 3 / 2 | 56 / 58 | known_version_below_slither_floor=2；no_pragma_guess=2；no_pragma_inferred=3 |
| arithmetic | 120 | 120 / 0 | 117 / 2 / 1 | 52 / 68 | no_pragma_guess=1；no_pragma_inferred=2 |
| denial_of_service | 92 | 92 / 0 | 91 / 1 / 0 | 37 / 55 | no_pragma_inferred=1 |
| front_running | 88 | 88 / 0 | 87 / 0 / 1 | 32 / 56 | no_pragma_guess=1 |
| reentrancy | 142 | 139 / 3 | 141 / 0 / 1 | 73 / 66 | Slither 侧失败=3；known_version_below_slither_floor=2；no_pragma_guess=1 |
| time_manipulation | 100 | 100 / 0 | 96 / 2 / 2 | 44 / 56 | no_pragma_guess=2；no_pragma_inferred=2 |
| unchecked_low_level_calls | 190 | 190 / 0 | 183 / 5 / 2 | 106 / 84 | no_pragma_guess=2；no_pragma_inferred=5 |

总计来源 824 / 13 / 9，成功版本系列 400 / 443。CFG 边为 next 76,631、true 5,593、false 5,421。调用分类为 SolidityCall 19,458、internal 8,353、library 5,353、Transfer 4,568、EventCall 4,315、Send 1,641、high-level 1,087、low-level 509、NewStructure 216、NewElementaryType 29、NewContract 27、NewArray 9。实际语料遇到的额外 Call 子类也按类名保留；InternalDynamicCall 在手写探针覆盖，不以语料频率决定是否支持。

### 6c 差异：仅定位到原始抽取层，底层根因未证明

停止文件为 access_control/source_files/buggy_43.sol，源码 SHA256 7e0232977cf6d105598c2b137ffa185bd4bac95da9cf4e40925957c4744f77f2。solc 为 0.5.0，二进制 SHA256 c1bb15b520f5076aebd7aa9ef4ce5fa245b6f210a91cbd2064b9e383e6510e08。前置编译 rc0，冻结 _compile 构造成功，原始路径与源码 SHA 校验通过；两侧均 325 个 source_nodes_seen/CFG 节点、46 个重复函数上下文，comparability=comparable、blockers 为空。

| 原报告独有 occurrence 字段 | 精确值 |
|---|---|
| layer / fact / tags | L1 / [162, out, DEF] / [inheritance]，重数 1 |
| function_name / start | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) / 4887 |
| context_contract / declarer | Post / MultiHashWrapper，inherited_context=true，modifier=false |
| node.start / declaration.start | 5154 / 4989 |
| canonical_name | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash).out |
| 原始节点文本 | 第 162 行的循环条件 i < 32（字节 5154:5160） |

原报告有 252 条，本次 251 条；only_reference=1、only_replay=0。停止后只读比较了包含 filename、end、context_index 在内的完整原始行，251 条本次记录全部在旧报告中逐字段存在，仍只差上述 1 条，排除了本次比较键投影造成差异。函数表仅 Post 上下文的 occurrences 从 15 变 14；counts、comparability、duplicate_contexts、ambiguous_triples、parameter_writes_synthesized 完全相同。所有差异条目与旁证在 replay_discrepancy_analysis.json，未丢弃重数或放宽键。

冻结 validate_slither.py 的 483–488 行直接从 node.local_variables_written 生成 L1 DEF；文件 SHA256 4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8。mando Slither 的 node.py 在 _find_read_write_call 和 update_read_write_using_ssa 中填充/合并本地写集合。由此只能把差异定位为旧工具链原始局部写抽取差异，不能证明 SSA 或继承遍历非确定性是根因；归档未保存该节点的 SSA 中间状态。这里只登记该假设供独立审查，没有重新编译验证、改动旧提取器或删除 out DEF。

6c 阶段耗时 36.032 秒，完整命令 41.043 秒。extractions/0087.json.gz 解压后 SHA256 为 7483006e788d1f0d14da8a986da7fc901494775d1c82fc86a71ca90e4adbea8c。参考报告与 seal 的 SHA 分别为 db56b7066430813540e468c900283414bf49c5e7c1f519cded8a874a760fd2a6、91e054c9cdd2331b7f21bc48e195a394d6034ffe85f878daa8fb013c9431e49c。

## 归档与复现

每份正式存储以 store.tar.gz 无损交付，原始散文件和 seal 留本地不改、不删除；所有 archive_audit.json 都逐成员回读相同。存储 tar 的根即原输出目录，包含 manifest、summary、trust/plan、invocations、成功单元图/节点/来源或 6c extraction；README 与 tar 本身是交付包装，不属于原运行 seal。两份生产归档各 4,229 成员（含 seal），6c 停止归档 93 成员。精确成员清单和长度/SHA 在 cp2_development_v1/*_archive_audit.json。

| 批次 | 成员数 | store.tar.gz SHA256 | 原 seal.json SHA256 |
|---|---:|---|---|
| cr_store_mando_v1 | 4229 | 246bd09d1eddc4167b1caf951742d2e0578d77ec6cc0a937778f983dcd0f8d86 | 6a677dbac2d113a973cb0f652d500c9f69dcf5194b3e296952e4175b02933c31 |
| cr_store_mando_v2 | 4229 | d6935d46d2a7199737cb81608893bde6061772f9fc62f6b79e0659ed1bb0332f | e02d966a80c871f7367d1480631c9bebccca737e8c6562b935a15d419a158668 |
| cp2_6c_v1 | 93 | a4a90b5c76aab316a734bce3de682fc7b501c45086c789f78cb4be002673dea1 | 28fbe6fe70787536f0becba9976c6f273101d237ee456324bf246020ba906132 |

本轮生产环境 Python 3.10.21、Slither 0.11.6、crytic-compile 0.4.2；6c 使用 mando Python 3.7.12、0.8.0、0.2.4。完整编译器路径、SHA256 与各输入实际参数保存在 trust、seal 和 invocations。支持快照 92 版；96 个可信安装中的另 4 版仅供历史对照。正式调用均从 /home/zhao/SmartContract/ge-sc-llm-compile 开始，实际已执行的命令如下；run_corpus 通过 cli.main(repair --regression mando --order ascending ...) 输入全部 846 个源文件，argv 完整展开在 ascending1/2_plan.json。

    /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B compile_repair/artifacts/cp2_development_v1/run_corpus.py ascending1
    /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B compile_repair/artifacts/cp2_development_v1/run_corpus.py ascending2
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_development_v1/run_replay.py

以上环境变量见测试节及 *_invocation.json；launch_phase.py 负责原始日志逐行 flush、压缩日志与命令收据。此处是已执行命令记录，现阶段禁止为追求通过而重跑。后续若另获批准复验，必须使用新批次路径并重新绑定实现身份，现有路径拒绝覆盖。离线查看归档无需编译：

    tar -tzf compile_repair/artifacts/cr_store_mando_v1/store.tar.gz
    tar -xOzf compile_repair/artifacts/cp2_6c_v1/store.tar.gz comparison.jsonl

检查脚本、日志、收据、授权、差异分析及分布在 cp2_development_v1，全文档检查与冻结核验随后补记。最终提交范围以 delivery_inventory.json / delivery_seal.json 为准；旧 evidence_seal 是开发时点快照，不能替代最终交付清单。

## 停止位置与后续边界

已停止于 §4.4 第 2 节精确重放，239/239 尚未满足；剩余 152 文件、整个降序跨版本比较、CP3 均未运行。两次生产运行及单元测试通过不替代这项失败验收。用户仅批准单列已有版本下限差异，没有批准改变重放标准；D3、D5、D16、D18 和 D19 状态保持。

下一步先独立审查这条 legacy 抽取差异和停止现场；若需要新探针、再次运行或方案改变，先提交具体建议并获得用户确认，再使用新批次。当前只完成停止后的文档、离线审计与本地 CP2 提交，不 push。没有安装、下载、LLM 调用、HGT 训练、GPU 锁读写或全局 solc 切换，费用 0 美元。

停止后的辅助读取有一次自动审批超时（非安全判定），按工具允许仅重试一次只读命令并成功；没有改用直连或改变权限/网络策略。完整原始代码、语料、旧产物与环境的保护检查见 frozen_audit.json。


辅助文档写入补记（修改 AI：Codex）：一次合并文档命令超过 Windows 进程命令长度限制（os error 206），进程未启动、没有写入文件；改为分文档短命令后成功。此工具限制与正式编译/重放无关，未重试正式运行，证据 documentation_write_issue.json，CHANGE_LOG §19.2 和交接已记录。


## 最终保护与文档检查（修改 AI：Codex）

frozen_audit.json 已通过：28,373 受保护跟踪文件（其中 27,845 模块外、473 旧产物、28 旧 fixture）、354 code_refs、96 solc、239 原始重放源码不变；本轮登记的 mando 90 / production 114 份包元数据文件相同。旧文档历史保留，14 个实现 SHA 与测试封存一致，原工具链函数 AST 除本轮授权接入外保持。9 份文档 doc_check_v1 全部通过；补记后再用 doc_check_v2 核对最终内容并记录文档 SHA，见 CHANGE_LOG §19.5。精确暂存检查与交付清单在 staging_check / delivery_inventory / delivery_seal；CP2 整体仍因 6c 差异停止，不宣称全部验收通过。


## CP2.1：条件边修复完成，6c 在 D20 门槛停止（2026-11-14，修改 AI：Codex）

### 实现与授权

本节追加在原 CP2 报告之后，保留原 20,093 字节。用户要求执行 PROMPTS r2.9 §4.4b；已 pull --ff-only origin compile-repair，起始 HEAD 为 1ed79a6708f505ecb9aa80b157a43f9e07608c9f，结果 Already up to date。已通读 r2.9、HANDOVER §0–5、DECISIONS、CHANGE_LOG §19/20、cp2_review_v1/README；沿用 docs/README 的五段式记录和 REPORT_TEMPLATE。

用户于 2026-11-14 明确批准 D20，原话“同意 D20”；开始实现前已落盘 artifacts/cp2_1_v1/authorization.json，并更新 DECISIONS 当前表和历史。没有修改 D3、D5、D16、编译设置或 occurrence 键。生产代码只修改 toolchain/slither.py 的 graph_facts，非测试 Python 文件数仍为 14：按 node.sons 顺序消费 true/false 两个分支 occurrence，即使目标相同也各保留一次；非条件边为 next；缺分支、额外分支、错误目标或跨函数端点均抛错。

新增 tests/test_graph_branches.py 和 fixtures/graph_branches.sol，18 个用例覆盖空 if、空 else、两支皆空、有 else、while、for、同目标分支、反向 sons 顺序及畸形 CFG。原 fixture 未修改。新批次的 run_corpus.py、run_replay.py 使用已有 CLI 与冻结函数，不 import 审查脚本；其余脚本负责检查、无损打包、只读复算与记录，均位于 artifacts/cp2_1_v1。原 scripts/DFG/dfg_v2/validate_slither.py SHA256 为 4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8；_compile 与 slither_full_facts 只 import，不改写。

### 真实验收

| 项目 | 预期 | 实际与证据 | 状态 |
|---|---|---|---|
| production 两次全量 | 每次 843 成功、3 个既有失败 | v3/v4 均 843/3，支持 92 版；ascending1/2_receipt.json | 通过 |
| 两次图字节 | 843/843 一致 | ascending2_acceptance.jsonl 全部 repeat_equal | 通过 |
| 与 CP2 v1 图差异 | 仅指定 86 个 IF、40 文件各一边 true→false | 两次均精确命中；节点、调用及其余边完整 JSON 相等 | 通过 |
| 条件节点与完整性 | 每个 IF/IFLOOP 一 true、一 false，无跨函数端点 | 5,507 条 true、5,507 条 false、76,631 条 next；总 87,645 边 | 通过 |
| 原节点/调用及 D3 | 保持原事实与成功条件 | 每轮 110,996 节点、45,565 调用，全部 provenance=original；D3 通过 | 通过 |
| 同版本生产归档 | 保持 key5、有序 IR | 842/842；另 1 个既有新增编译器归因 (a) | 通过 |
| 6c | 239 文件按 D20 全部通过 | 227 已测：223 精确同、3 个仅波动差异通过、1 失败；12 未运行 | 未通过，已停 |
| 降序跨版本 | 同一 CLI --order descending；列出全部差异 | 因上一项停止，0 个运行；cp2_desc_v1 未创建 | 未运行 |

三份已知失败仍为 reentrancy/source_files 下的 reentrancy_bonus.sol、reentrancy_cross_function.sol、reentrancy_insecure.sol，reason=slither_side_failure，不进入图存储。每轮 CLI 因它们返回 2 属预期，验收驱动器成功返回 0；不要将这两种返回码混淆。生产升序耗时 262.80 秒和 271.14 秒；6c 驱动内耗时 135.41 秒（外层命令 140.85 秒）。类别、选版分布、完整逐份结果见 cp2_1_summary.json 和 acceptance.jsonl，版本直方图仅统计 843 个成功选版，失败的 selected_version=null 单列。

### 6c 的固定采样与停止事实

main 按 CP2 plan 的相同 239 文件顺序在 mando 的一个进程运行，逐项保持原始 target、版本、仓库根 CWD。每个主运行差异各另起一个进程，在该新进程连续提取恰好 10 次；四份差异共 4 个追加进程、40 次追加提取，与 227 次主运行合计 267 次提取。没有在主进程插入额外提取，没有追加第 12 个样本。原报告/seal 的 SHA256 先验证，plan 与 CP2 plan 完全相等。

| 顺序 | 文件 | 主运行/6c occurrence 总数 | 波动键数 | 结果 |
|---|---|---|---|---|
| 87 | experiments/ge-sc-data/source_code/access_control/source_files/buggy_43.sol | 252/252 | 3 | D20 通过 |
| 207 | experiments/ge-sc-data/source_code/reentrancy/source_files/buggy_24.sol | 792/793 | 2 | D20 通过 |
| 226 | experiments/ge-sc-data/source_code/reentrancy/source_files/buggy_43.sol | 391/390 | 3 | D20 通过 |
| 227 | experiments/ge-sc-data/source_code/reentrancy/source_files/buggy_44.sol | 357/358 | 1 | 停止：1 个 reference-only 键 |

D20 比较的是每个 occurrence 键的重数，不能用总 occurrence 数相同代替。例如 access_control/buggy_43.sol 总数都为 252，键仍不同；reentrancy/buggy_43.sol 的 6c 总数 390 不在总数样本区间 391–392 内，但每一个键均满足 D20，因此按原文通过。没有增加或改成总数范围判据。

**全部失败键只有 1 个**，位于第 227 个 reentrancy/buggy_44.sol：

- 源 SHA256：8e037273ea617a302b2db77c278ba36931dd57474df202f78aa3c4b0ba815f86；原始 solc 0.5.0。
- 函数 MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash)，function start=9070、node start=9337、declaration start=9172；canonical name 为该函数的 .out。
- layer=L1、fact=[282, out, DEF]、modifier=false、context_contract=context_declarer=MultiHashWrapper、inherited_context=false、tags=[]。
- 6c 重数 1；main 与追加 10 次均为 0，min=max=0。它是 reference_only 键，触发 D20 的明确失败条件；不能当作已观察到的不稳定键忽略。

该文件有一个 Feed 继承上下文的 out DEF 波动键，不能替代上面缺失的声明上下文键。原始参考行、完整键、全部 11 次计数保存在 captured_replay_audit.json；相应原始提取在 cp2_6c_v2/store.tar.gz 的 extractions/0227.json.gz 和 additional/0227/extractions/01–10.json.gz。audit_replay.py 只读取已保存字节与已核验的参考报告，重新计算全部 227 个 main 比较及 4 个 D20 判定，结果完全相同；该检查新增编译/提取/采样均为 0。

### 全部波动键（观察范围为已执行的 227 份）

9 个不同键全为 L1 DEF；L1 USE/READ/WRITE、L2 DEF/USE/READ/WRITE 均 0。其中 5 个键 inherited_context=true、4 个为 false，不能说全部处于继承上下文。下表计数按 main、追加 1–10 顺序；每项最小/最大均为 0/1，参考重数均落在该范围。缺失的 reference_only 键另列于上一节，不属于这 9 个波动键。

| 顺序 | 函数 | 上下文 | 行 | 变量 | inherited | 6c 重数 | 范围 | 11 次重数 |
|---|---|---|---|---|---|---|---|---|
| 87 | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) | MultiHashWrapper | 162 | out | False | 0 | 0–1 | 0,0,0,1,1,0,0,1,1,0,1 |
| 87 | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) | Post | 162 | out | True | 1 | 0–1 | 0,0,0,0,0,1,1,0,0,1,0 |
| 87 | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) | ProofHash | 162 | out | True | 0 | 0–1 | 1,0,1,0,0,1,1,0,0,1,0 |
| 207 | FomoFeast.addInvestRecord(address,uint256,uint256,uint256) | FomoFeast | 584 | records | False | 1 | 0–1 | 0,1,0,1,1,1,0,1,1,1,1 |
| 207 | FomoFeast.addStaticCommissionRecord(address,uint256,uint256) | FomoFeast | 603 | records | False | 1 | 0–1 | 1,1,0,1,1,1,1,0,1,1,0 |
| 226 | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) | MultiHashWrapper | 225 | out | False | 0 | 0–1 | 0,1,0,0,0,0,1,1,1,1,1 |
| 226 | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) | Post | 225 | out | True | 0 | 0–1 | 0,0,0,1,0,1,1,1,1,1,1 |
| 226 | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) | ProofHash | 225 | out | True | 0 | 0–1 | 1,0,1,1,1,1,0,0,0,0,0 |
| 227 | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) | Feed | 282 | out | True | 0 | 0–1 | 0,1,0,0,0,0,0,0,0,0,0 |

以上只说明本次固定 11 样本中的观测结果，未证明内部根因，也未证明第 227 份的缺失键在更多运行中绝不出现。没有通过改 seed、GC、输入顺序、键字段或样本数寻找通过结果；原 DFG 与 6c 结论保持原样。

### 测试与开发记录

| 环境/检查 | 结果 | 时间与证据 |
|---|---|---|
| production 全模块 | 585 passed、6 skipped、0 failed | 63.99 秒；pytest_production.json / .log.gz |
| mando 全模块 | 147 passed、444 skipped、0 failed | 12.61 秒；pytest_mando.json / .log.gz |
| mando 冻结 DFG | 2653 passed、9 个既有警告、0 failed | 152.21 秒；pytest_dfg.json / .log.gz |
| D20 规则边界 | 12 项通过 | d20_rule_checks.json，含缺参考键、稳定不等、区间端点与错误样本数 |
| 停止现场只读复算 | 227 主运行、4 组 11 样本全部与原判定一致 | captured_replay_audit.json；这是审计通过，不是 6c 验收通过 |

跳过均为工具链专属用例：production 跳过旧版 CP0/负对照与 metadata backport；mando 跳过 production 特征与 stdlib metadata。没有测试失败后重跑。实现前通过 baseline.json 保存 28,457 个已跟踪文件、8,548 个旧 seal 成员、239 个原始 6c 目标、354 个冻结代码引用、96 个 solc 文件和两环境元数据。最终保护审计、文档检查与精确交付清单见 frozen_audit.json、doc_check_v*、delivery_inventory.json、delivery_seal.json。

### 归档与复核

生产环境为 Python 3.10.21 / Slither 0.11.6 / crytic-compile 0.4.2；regression_6c 为 mando Python 3.7.12 / 0.8.0 / 0.2.4。96 个可信安装中支持快照为 92 个；本轮无新增安装、下载或全局 solc 变更。失败文件 solc 路径为 /home/zhao/.solc-select/artifacts/solc-0.5.0/solc-0.5.0，SHA256 c1bb15b520f5076aebd7aa9ef4ce5fa245b6f210a91cbd2064b9e383e6510e08；全部实际版本、编译器 SHA、argv、设置、观察到的 solc rc 与 Slither API 调用在各 store 的 invocations/plan/trust/seal 中，不伪造 API 未暴露的子进程返回码。

| 新批次 | tar 成员数 | store.tar.gz SHA256 | seal.json SHA256 |
|---|---|---|---|
| cr_store_mando_v3 | 4229 | 29a4ccba5612d2a6a1df896647a66d4babd7f6e175b424ece695f152eddba513 | 2d44f95b7ffb5cc8c2dba6a468042c8d3565e455f6974ceb744ad45b067ce075 |
| cr_store_mando_v4 | 4229 | 54f9f53d666df7e6bc51ee9954843aaec9bdfc34290fea891add03aaee7a75e5 | 22fe73285f04f857e071da3cb2890cdca582014ba8daee6805b3a05aa93381b1 |
| cp2_6c_v2 | 309 | 6dee59c464bf066930b55546f2d1c7a704fddefab2f132284797b6374c7beae0 | b443421f192f7bdb5c109c65f56364b1e3e395ac677290d082ea4cc86e29cdb2 |

三份归档逐成员回读完全一致，原始散文件保留。旧 CP0–CP2 归档不覆盖；本轮没有创建 cp2_desc_v1。图本身一致不要求时间、路径和日志所在的 manifest/seal 字节相同。所有实际命令与环境完整写入 *_invocation.json、*_plan.json 和 pytest_*.json；实际入口是新批次 launch_phase.py ascending1 / ascending2 / replay。这些目录已存在且当前验收已停止，不要直接重跑入口；任何续验须新的明确范围和新批次。

以下为可直接执行的只读摘要复核命令（不会调用编译器或 Slither）：

```bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
/home/zhao/miniconda3/envs/mando/bin/python -B -c 'import json,tarfile; t=tarfile.open("compile_repair/artifacts/cp2_6c_v2/store.tar.gz"); print(json.dumps(json.load(t.extractfile("summary.json")),indent=2))'
```

### 停止位置、问题与后续边界

CP2.1 的生产代码修复和两次生产验收完成；整体 CP2.1 未通过，停止在 §4.4b 第 3 项。剩余 12 份 6c、全部降序比较、CP3 均未运行，跨版本相同/不同计数及归因不能填成 0 或“通过”。

需审查的问题：D20 的固定 11 样本没有覆盖参考报告中的上述键，现有证据不足以判断其内部原因；应先独立复核已经封存的原始行、源码/版本身份和运行契约，再由用户决定下一步。没有实施替代方案、增加采样或放宽判据。D20 批准仍有效，它并不保证本次能通过。按用户要求，停止后仍完成交接、训练改变记录、文档与保护检查并本地提交，不自动 push；没有 LLM、HGT 训练、GPU 锁操作或 CP6 第 10 行改写。
