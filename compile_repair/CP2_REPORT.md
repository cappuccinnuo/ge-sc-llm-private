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


## CP2.2：D20a、6c 续跑与降序比较（2026-11-14，修改 AI：Codex）

### 实现与范围

先 git pull --ff-only origin compile-repair，Already up to date，起始 HEAD=36c6109fa9271608feb8f4634eca6ab7ff6a192a。完整读取 PROMPTS r2.10，重点 §1.12/1.13/4.4/4.4b/4.4c 与共享上下文；读 HANDOVER §0–5、DECISIONS、CHANGE_LOG §21/22、cp2_1_review_v1/README、docs/README 和 REPORT_TEMPLATE。用户 2026-11-14 原话“同意 D20a”先保存于 artifacts/cp2_2_v1/authorization.json，并把 DECISIONS 改为已定。

生产代码、测试文件与旧产物均不修改；驱动和审计仅写 cp2_2_v1，新结果写 cp2_6c_v3、cp2_desc_v1。新文件及用途见三个目录 README，最终精确清单见 delivery_inventory.json。生产 .py 仍为 14；D3、D5、D16、occurrence 键及原始路径/版本/CWD 不变。run_replay import 复用旧 CP2.1 的 occurrence_keys、historical_target、ranges、archive_extraction，不导入审查脚本；冻结 validate_slither 的 _compile 和 slither_full_facts 未改（SHA256 4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8）。

D20a 必须实际观察到每个失败键的参考重数；仅扩大 min/max 范围但未出现该值不能通过。各键分别观察到即可，不要求同时发生；首次满足全部目标即停，最多 100 次。每次完整提取和失败键计数均保存。旧 D20 结论原样保留，新增波动另记，全部样本仍稳定的键必须相同。11 个合成边界检查通过，没有为开发检查额外抽取语料。

### 真实验收

| 项目 | 预期 | 实测 / 证据 |
|---|---|---|
| 第 227 份 D20a | 最多 100 次，首次满足即停 | 第 1 次通过；cp2_6c_v3/d20a/0227 |
| 前 226 份 | 不重跑，原结论不变 | 沿用旧 223 精确 + 3 D20；逐行复算一致 |
| 第 228–239 份 | 一个新进程按原顺序，差异按 D20/D20a | 11 精确；第 239 份另取 10 次后 D20 通过 |
| 合计 | 239/239 通过 | 234 精确、4 D20、1 D20a，剩余 0 |
| 本轮新增提取 | 不重做旧主运行 | 23 = 12 主样本 + 10 D20 + 1 D20a |
| 重放审计 | 不放宽键、重数或稳定事实 | 239 份独立只读复算通过，新增提取 0 |
| 生产降序 | 仅三份已知 Slither 侧失败 | 846 输入，843 成功 / 3 已知失败，92 支持版本 |
| 跨版本 | 每份比较 key5 + 规范化有序 IR | 229 同版、614 不同版，843/843 相同，差异 0 |
| source length | 仅诊断 | 815 相同、28 不同 |

证据为 cp2_6c_v3/summary.json、cp2_2_v1/captured_replay_audit.json、descending_receipt.json、descending_comparison.json。本轮新 23 次调用来自三个不同 PID（D20a、续跑主运行、D20）；旧 227 主样本 + 旧 40 D20 + 新 23 = 累计保留 290 次提取。本轮没有重抽第 1–227 份的主样本或第 227 份的固定 10 样本。

第 227 份 reentrancy/buggy_44.sol 的 SHA256=8e037273ea617a302b2db77c278ba36931dd57474df202f78aa3c4b0ba815f86，solc 0.5.0。原失败键 function/node/declaration start=9070/9337/9172，MultiHashWrapper 声明上下文、非继承，fact=[282,out,DEF]，参考 1、旧 11 次全 0、新第 1 次 1。同文件 Feed 上下文新样本为 0，是另一个键，未合并。旧 CP2.1 的 D20 失败历史保留，本次是授权后的 D20a 通过。

### 全部不稳定键

12 个键均为 L1 DEF；L1 USE/READ/WRITE 与 L2 DEF/USE/READ/WRITE 均 0。5 个继承、7 个非继承。完整键、SHA、偏移与计数在 captured_replay_audit.json.unstable_facts；下表 main+D20 为按时间顺序的 11 次，D20a 为本轮追加。

| 序号/文件 | 函数 / 上下文（继承） | 变量 / 行 | 参考重数 | main + D20 十次 | D20a |
|---|---|---|---:|---|---|
| 87 access_control/buggy_43.sol | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) / MultiHashWrapper（否） | out / 162 | 0 | 0,0,0,1,1,0,0,1,1,0,1 | 未追加 |
| 87 access_control/buggy_43.sol | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) / Post（是） | out / 162 | 1 | 0,0,0,0,0,1,1,0,0,1,0 | 未追加 |
| 87 access_control/buggy_43.sol | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) / ProofHash（是） | out / 162 | 0 | 1,0,1,0,0,1,1,0,0,1,0 | 未追加 |
| 207 reentrancy/buggy_24.sol | FomoFeast.addInvestRecord(address,uint256,uint256,uint256) / FomoFeast（否） | records / 584 | 1 | 0,1,0,1,1,1,0,1,1,1,1 | 未追加 |
| 207 reentrancy/buggy_24.sol | FomoFeast.addStaticCommissionRecord(address,uint256,uint256) / FomoFeast（否） | records / 603 | 1 | 1,1,0,1,1,1,1,0,1,1,0 | 未追加 |
| 226 reentrancy/buggy_43.sol | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) / MultiHashWrapper（否） | out / 225 | 0 | 0,1,0,0,0,0,1,1,1,1,1 | 未追加 |
| 226 reentrancy/buggy_43.sol | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) / Post（是） | out / 225 | 0 | 0,0,0,1,0,1,1,1,1,1,1 | 未追加 |
| 226 reentrancy/buggy_43.sol | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) / ProofHash（是） | out / 225 | 0 | 1,0,1,1,1,1,0,0,0,0,0 | 未追加 |
| 227 reentrancy/buggy_44.sol | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) / Feed（是） | out / 282 | 0 | 0,1,0,0,0,0,0,0,0,0,0 | 0 |
| 227 reentrancy/buggy_44.sol | MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash) / MultiHashWrapper（否） | out / 282 | 1 | 0,0,0,0,0,0,0,0,0,0,0 | 1 |
| 239 reentrancy/spank_chain_payment.sol | ECTools.substring(string,uint256,uint256) / ECTools（否） | result / 174 | 1 | 0,0,0,0,0,0,0,0,0,0,1 | 未追加 |
| 239 reentrancy/spank_chain_payment.sol | ECTools.uintToString(uint256) / ECTools（否） | b / 156 | 1 | 1,1,0,1,1,1,1,1,1,1,1 | 未追加 |

逐键所在行源码同样写在 JSON 的 source_line，原文为：

- 序号 87/226/227，out，行 162/225/282：for (i = 0; i < 32; i++) {
- 序号 207，records，行 584/603：for (uint256 i = 8; i > 0; --i) {
- 序号 239，result，行 174：for (uint i = _startIndex; i < _endIndex; i++) {
- 序号 239，b，行 156：while (_uint != 0) {

第 239 份为 reentrancy/spank_chain_payment.sol（SHA256 15724a9aecd227749e4e3441bf408892ead6639d7c2830b116014183fb537d09，solc 0.4.23）。新增观测包含 while 条件上的 DEF，不能将上轮十键的 for 描述推广为全部波动键的必要条件。未定位内部根因，也不能用有限样本通过证明全状态确定性。

### 降序比较与分布

使用同一生产 CLI --regression mando --order descending、唯一 rules/environment.py 策略，覆盖全部 846 输入。614 个不同版本均在同一小版本系列内，例如 0.4.12→0.4.26 为 26 份、0.5.0→0.5.17 为 124 份、0.5.11→0.5.17 为 105 份，节点与有序 IR 均相同。完整 843 份版本对、逐文件结果及汇总在 descending_comparison.json，different_entries=[]；没有实际 IR 差异需要归因，不构造差异示例。28 份 length 差异只诊断，完整值在 descending_acceptance.jsonl 的 cross_version.source_length 中。

降序只作验证，不替换升序主存储。未修复为 reentrancy_bonus.sol、reentrancy_cross_function.sol、reentrancy_insecure.sol，均 slither_side_failure，无 graph。CLI 因三份预期失败返回 2，外层验收确认符合预期后返回 0。按类别分组仅使用目录，不读取标签；版本来源、系列、补丁版和各标志完整分布在 descending_comparison.json.distribution。

### 测试与开发记录

production：585 passed/6 skipped（64.70 秒）；mando：147 passed/444 skipped（13.29 秒）；冻结 DFG：2653 passed/9 既有 warnings（160.04 秒）。11 个合成边界检查通过。生产跳过为 backport/0.8.0 专属，mando 跳过为 production/标准库专属；完整原因在日志。实际命令、rc、临时目录、耗时和哈希在 pytest_production/mando/dfg.json，原日志 gzip 无损交付。6c 驱动 28.14 秒（外层 33.57 秒），降序 265.68 秒（外层 267.45 秒）。

WSL 未安装 rg，定位改用现有 git ls-files 与 Python 定向读取，不安装工具。文档写入封装首次因 Markdown 反引号触发 JavaScript 语法错误，未执行任何文件操作；改用普通 UTF-8 文本和缩进命令段后写入。旧 CP2.1 未执行的降序驱动只列 843 个成功输入，本轮新驱动按 r2.10 覆盖 846 并验收三份已知失败。没有变更生产策略或冻结判据，没有实际测试失败、运行重试或审批拒绝。最终保护和文档结果见 frozen_audit.json、doc_check_v*。

### 归档与复现

cp2_6c_v3 seal SHA256=4bb3dda023b41937839673469bfc8f512407eb46f40a46d30bac8fe4dce6f31d；56 文件 + seal = 57 成员，tar SHA256=b432b70257e061a5b57bc19a80f8754fdd1d03e27f2bcee3e64b64084d2a724b。cp2_desc_v1 seal SHA256=d1f469766ddacff40fc161c857a0f82d463865d8bc47a7e8cdf738696f402aab；4,228 文件 + seal = 4,229 成员，tar SHA256=02ccc74dce4a9acde715d0d8a133d87d87345cbb9fcbba7951a3bc82d4ceb2c1。两个归档逐成员 SHA 回读相同，散文件保留；前 227 份原始提取依赖旧 cp2_6c_v2，未复制 EdgeSem 报告。编译器路径/版本/SHA、命令、profile、实现指纹见 trust、invocations、seal、evidence_seal。

实际执行入口如下；结果拒绝覆盖，不能对现有批次再次采样：

    cd /home/zhao/SmartContract/ge-sc-llm-compile
    export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
    export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_2_v1/run_replay.py --self-check
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_2_v1/launch_phase.py replay
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_2_v1/launch_phase.py descending
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_2_v1/run_checks.py production
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_2_v1/run_checks.py mando
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_2_v1/run_checks.py dfg

### 停止位置与后续边界

本机验收完成，待独立审查后进入 CP3。本轮未改生产代码、旧产物、原语料或环境；没有安装/下载包、编译器、语料或文档，没有 LLM、训练、GPU 锁或全局 solc 操作，费用 0。没有发现需改变本步方案的问题；有限采样的结论边界只登记，未实施替代方案。强制记录、doc_check 和冻结检查全部通过后本地提交，实际提交号见 git log，不自动 push。

最终检查补记（修改 AI：Codex）：doc_check v1 的 8 份文档全部通过，补记后 v2 最终复检记录在 cp2_2_v1。frozen_audit 通过，14 个生产文件字节未变；28,512 受保护跟踪文件、17,315 旧 seal 成员、239 原始目标、354 DFG 引用和 96 solc 文件未变；mando 118 / production 145 份环境元数据集合与内容相同，五份文档历史保留。git diff --check 通过；本轮只按 delivery_inventory 精确提交允许文件，旧产物和历史未跟踪文件保留。


## CP2.3：独立读取 pragma 与接受非 UTF-8 输入（2026-11-17，修改 AI：Codex）

### 实现与范围

执行 PROMPTS r2.11 §4.4d；先读 §4.1，再完整阅读 PROMPTS、HANDOVER §0–5、DECISIONS、CHANGE_LOG §23/24、docs/README、REPORT_TEMPLATE 与 cp2_2_review_v1/README、probe_inputs.json。compile-repair 上 git pull --ff-only origin compile-repair 返回 Already up to date，起始 HEAD=361772f74b28b4dce0ad094907dc3dbf27a17794。本轮仅修改 rules/environment.py 与 pipeline.py，生产文件保持 14；不迁移到 rtx5080-rebuild。

rules/environment.py 新增共用 _pragma_spans：在 code_only 等长遮盖注释/字符串后的字节上识别 Solidity pragma，仅接受花括号深度为 0 的指令，返回原字节区间；pragma_interval 与 pragma_patches 共用定位。新 _expression_interval 仅复制冻结 stage_f/versioning.py 的表达式求值（原 SHA256=130251d6a9e46ec176ba183a0a66fa5a30210b43c1ab8faa2bfcf5a676d2ed18），保留 ^、~、关系运算、补丁版加一、空交集与不支持表达式的异常语义；冻结 interval 与 parse 只在本轮等价测试中调用，不改原模块。定位失败不会触发整文件解析；已识别但缺少分号的 pragma 抛 Unsupported，其他语法留编译器判定。

版本表达式与 infer_interval 使用无损 Latin-1 解码，pragma 改写保持字节处理、等长空格、CR/LF 与原偏移。pipeline.repair_unit 只捕获 Unsupported 为 unsupported_version_constraints，不再把 UnicodeDecodeError 归为该标志。mando_known_version 的 UTF-8/元数据哈希校验、D3/D5/key5、存储格式、settings_retry 均保持；原始源码只读。

| 生产文件/函数 | 新增行 | 删除行 |
|---|---:|---:|
| environment.py::_pragma_spans（新增） | 22 | 0 |
| environment.py::_expression_interval（新增） | 30 | 0 |
| environment.py::pragma_interval | 9 | 3 |
| environment.py::infer_interval | 1 | 1 |
| environment.py::pragma_patches | 4 | 7 |
| pipeline.py::repair_unit | 1 | 1 |

函数行数按函数正文差异统计；文件级 git diff --numstat 含导入、模块说明与空行：environment.py +72/-15，pipeline.py +1/-1，共 +73/-16。证据 code_change_summary.json。新增 tests/test_pragma_bytes.py；新增 tests/fixtures/pragma_inputs/ 下 latin1_comment.sol、no_pragma_latin1.sol、masked_pragma.sol、two_pragmas.sol、nested_pragma.sol、union_pragma.sol。Latin-1 注释夹具逐字节复制自审查目录（SHA256=18b5d22ac65f1f5895bc244cf590f3c53afca54ae4d7900fd5087c23f4af5aed），旧夹具不改。

### 真实验收

| 验收项 | 预期与实测 | 证据（artifacts/cp2_3_v1 下） |
|---|---|---|
| 修改前复现 | 5 个新语法输入抛 Unsupported、Latin-1 输入抛 UnicodeDecodeError；6 个 CLI 输入均拒绝 | reproduction.json、reproduction_cli |
| 直接工具对照 | 5 个新语法在 0.8.38；Latin-1 在 0.4.24/0.5.17/0.8.0/0.8.38；9/9 solc rc0、production D3 成立 | reproduction_invocations.jsonl |
| MANDO 冻结等价 | 两环境各 846/846 区间与异常类型、pragma 补丁字节区间相同 | equivalence.json、test_evidence_*.json.gz |
| 全部可解析夹具 | 36 个文件中冻结 parse/UTF-8 路径可处理 28 个，28/28 相同；其余 8 个明列原因 | 同上 fixtures/excluded |
| 生产 CLI 正例 | 9/9 成功、D3 成立、无源码改动；含要求的 6 个输入及伪 pragma、双 pragma、无 pragma Latin-1 对照 | probes.json、cli_probe_stores.tar.gz |
| 不支持的并集 | 含双竖线的 pragma 仍记录 unsupported_version_constraints，调用编译器 0 次 | 同上 unsupported 存储 |
| 顶层与字节边界 | 合约体内 pragma 不计；注释/字符串不计；双 pragma 交集、反向补丁、CR/LF/字节偏移、非 UTF-8 推断均通过 | test_pragma_bytes.py、pytest_* |
| 全量 production | 846 个输入，843 success、3 已知 slither_side_failure；92 个支持版本 | regression.json |
| 与 v3 记录相同 | 状态、reason、选定版本、设置、标志各 846/846 | regression_acceptance.jsonl |
| 与 v3 图相同 | 843/843 graph.json 字节相同；差异 0；失败输入没有 graph | 同上 |
| 6c | 本 CP 不重放，新增抽取 0 | 执行入口与记录 |

8 个不纳入冻结等价的夹具是原 5 个新语法、两个 Latin-1 文件及故意将 pragma 放在 contract 体内的非法夹具；它们有独立正/负测试，不把排除写成通过。13 组运算符/无效约束还直接与冻结表达式求值器比较，覆盖 ^0.0.x、^1.x、各关系符、缺补丁版、不支持表达式、空交集与并集。

CLI 选版依次为：using_global 0.8.13、user_operator 0.8.19、transient 0.8.28、file_event 0.8.22、layout_at 0.8.29、latin1_comment 0.4.24、masked_pragma 0.5.0、two_pragmas 0.5.1、no_pragma_latin1 0.4.16。全部由原升序策略选择；未指定回归标签或 known version，不靠文件名选版。嵌套 pragma 夹具只验证定位忽略，未声称它可编译。

v5 使用与 v3 相同顺序、同一 CLI、--regression mando --order ascending；三份已知失败仍为 reentrancy_bonus.sol、reentrancy_cross_function.sol、reentrancy_insecure.sol。repair CLI 返回 2 表示这三份未修复，严格逐文件验收驱动返回 0。运行耗时 239.81 秒（外层 241.22 秒）；不读取标签，不重跑已完成的旧批次。

### 测试与开发记录

production 模块 607 passed/6 skipped，69.72 秒；mando 模块 167 passed/446 skipped，13.33 秒；mando DFG v2 2653 passed/9 条既有弃用警告，150.01 秒。模块共 613 项，新增 22 项；生产的 6 个跳过为旧 profile/backport 专属，mando 的 446 个跳过为生产 profile/标准库专属。两个环境均运行等价测试；分层测试通过。详见 pytest_production/mando/dfg.json 与无损日志。生产 CLI 测试的已成功结果经 audit_tests 只读复算、原字节打包，没有为出报告重复编译。

基线准备首次遍历所有名为 seal.json 的旧文件时，发现 cp0_1_compilers_v1/README.md 与首次 seal 的哈希不同。其 README 已明确首次 seal 被 seal_v2.json 替代；当前 README 与上一轮基线及 seal_v2 均相同，最终 seal SHA=36724427a5c88c4c6c4b5e2d63f92a5d6c5216e317b674bebc0005ee830e7d6f。处理为：所有旧跟踪文件按起始 HEAD 保护，沿用前轮已审计的结果 seal 成员集合并加入 CP2.2 新存储；没有修改旧证据或放宽 CP2.3 验收。现场与依据见 development_issues.json。文档首次写入命令超过 Windows 创建进程的长度限制（os error 206），进程未启动、文档未变；改为分块写入本批 write_documents.py 后执行，并保留问题记录。正式复现、测试、CLI 正负例与全量回归均无意外失败、无自动重试；没有审批拒绝。

没有发现需要改变 CP2.3 方案的实质问题。本轮未实施替代方案。既有两项缺口继续登记而未处理：并集 pragma 仍不支持，Slither 进程内仍无超时；按 r2.11 留 CP3 分类并提出后续实现方案。9 个正例与 846 回归通过不证明任意源码、任意未来版本或图语义已穷举。

### 归档与复现

新批次 cp2_3_v1 保存复现、基线、测试、逐份比较、归档审计与记录；cr_store_mando_v5 保存新 production 存储。v5 seal SHA256=db925ee1642b5f8eae79d20defbbec673ffbaa7b4a0bb37cc270027bb1a8372b；4,228 文件加 seal 共 4,229 成员，无损 store.tar.gz 为 14148449 字节，SHA256=de29da390672b53d185c920bb994cbcee62b6dd53fd76510d952c92880d2c622，逐成员回读相同。9 个正例和 1 个负例的 CLI 存储另打包为 cli_probe_stores.tar.gz（58 成员），不依赖临时目录长期存在；SHA 与成员清单见 probes.json。完整交付文件与哈希见 delivery_inventory、delivery_seal。

production Python 3.10.21/Slither 0.11.6/crytic-compile 0.4.2；mando Python 3.7.12/0.8.0/0.2.4。OMP/MKL=2，全部 CPU，未测峰值资源。运行环境见 runtime.json；每次编译器绝对路径、版本/SHA、命令、设置、耗时、rc 与 profile 见 invocations、trust、seal 和测试存储；费用 0、LLM 调用 0。

以下是本次实际执行入口，批次文件均拒绝覆盖；只读审查直接读取已有产物，不重跑。完整 846 个输入路径的 CLI argv 见 regression_plan.json。

    cd /home/zhao/SmartContract/ge-sc-llm-compile
    export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
    export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/launch_phase.py reproduction
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/run_checks.py production
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/run_checks.py mando
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/run_checks.py dfg
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/launch_phase.py probes
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/launch_phase.py regression

### 停止位置与后续边界

CP2.3 本机功能和回归验收通过，待独立审查后进入 CP3。6c 已结束，不新增采样；D3/D5/D20/D20a 与其他既有决定不变。没有安装、下载编译器/依赖/语料/文档、LLM、训练、GPU 锁、全局 solc 或网络配置变更。强制记录及最终检查完成后本地提交，实际提交号见 git log；本轮不自动 push。doc_check 与最终完整性结果在文末补记。


最终检查补记（2026-11-17，修改 AI：Codex）：首次 frozen_audit.json 的实现指纹项未通过，原因是新收集的证据包含旧 settings 测试手工创建的 6 个空实现指纹 seal（code_commit=test），并非生产代码差异。test_seal_diagnosis.json 逐条列出；保留首次结果和 audit_frozen_initial.py，审计明确验证恰好这 6 个手工 seal，再核对全部 3 个真实 CLI seal 的 14 文件指纹，最终 frozen_audit_v2.json 全部通过。测试、生产代码与正式回归没有重跑或修改，未改变验收标准。其余保护项两次均通过：28,574 受保护跟踪文件（模块外 27,845、旧产物 668、旧夹具 30）、21,599 旧结果成员、239 原始目标、354 DFG 引用、96 solc 文件与两环境元数据集合/内容（production 145、mando 118）均未变；12 个非目标函数 AST 保持，生产文件仍 14 且仅两份获授权修改，测试与 v5 实现指纹相同，文档旧历史保留。

doc_check v1 的 7 份文档全部通过；本补记与新目录说明更新后的最终复检记录在 doc_check_v2.jsonl 和 doc_check_v2_invocation.json。git diff --check 已通过。按精确 delivery_inventory 暂存并核对字节后本地提交，不 push；CP2.3 本机验收完成，独立审查尚未进行。


暂存检查补记（修改 AI：Codex）：首次 git diff --cached --check 指出新 v5 README 文件末尾多一个空白行，记录于 staging_attempt1.json。只删除该冗余换行，正式存储/tar 与生产代码字节不变；前一版 evidence_seal.json 保留为文档格式整理前的快照，最终交付使用 evidence_seal_v2.json 和 delivery_seal.json。处理已登记 development_issues，七份文档最终再检结果见 doc_check_v3；提交前重新核对全部暂存字节与空白格式。


## CP2.4：pragma 内注释与未结束指令（2026-11-17，修改 AI：Codex）

### 实现与范围

按用户要求先读共享上下文，再通读 PROMPTS r2.12（尤其 §1.15、§3.3、§3.10、§4.4e），以及 HANDOVER §0–5、DECISIONS、CHANGE_LOG §25/26、记录模板和 cp2_3_review_v1/README、edge_cases。git pull --ff-only origin compile-repair 返回 Already up to date；起始 HEAD 为 7e32d85c6d02049fd606a9410759dbfb9f18fb7a。新批次只有 artifacts/cp2_4_v1；CP0–CP2.3 原产物和已审查结论保留。

生产仅修改 rules/environment.py 的 _pragma_spans 和 pragma_interval，共 +5/-4 行（含说明文字），生产文件仍为 14。前者遇到分号之前的左/右花括号或文件结束时，抛出 F: unterminated pragma directive；后者从 code_only 的等长遮盖字节中读取同一区间的表达式，再交给原 _expression_interval。pragma_patches 仍使用原始字节，不改变区间、替换内容、CRLF 或后续源码偏移。pipeline、选版策略、metadata、D3、key5、settings_retry 和图存储均不改。

新增 tests/test_pragma_comments.py（15 个测试实例）与 tests/fixtures/pragma_comments 下 comment_inside、line_comment_inside、missing_semicolon 三个原样夹具。旧 test_pragma_bytes.py 只追加两个新注释夹具的明确例外：先证明冻结 interval 抛 Unsupported，再交给新测试验证预期成功；所有旧夹具的冻结比较保留。夹具来源和 SHA256 见 fixture_sources.json。CP2.3 参照保存为 environment_cp23.py，SHA256=f0d4f4b9274532c0b3760d67341f37dba7f2f81430d9aad091f42644483429e0，与起始提交原文件逐字节相同；只在测试中载入，不用于生产或替换冻结函数。

### 真实验收

| 项目 | 预期与实测 | 证据（artifacts/cp2_4_v1/） |
|---|---|---|
| 修改前复现 | 两种注释分别在 solc 0.8.0/0.5.17 rc0、生产 D3 成立，但旧模块拒绝；缺分号在 0.5.17 报 Expected ';' but got end of source；四个 CLI 输入均旧同一错误且不编译 | reproduction.json、reproduction_invocations.jsonl、reproduction_cli/ |
| MANDO 等价 | 两环境各 846/846：pragma_interval、完整 Patch 和 EnvironmentPlan 全字段相同；升降序各比较一次 | equivalence.json、test_evidence_*.json.gz |
| 夹具等价 | 当前 39 文件中原 CP2.3 能读取的 35/35 全同；4 个异常文件明确列出：两个注释、缺分号、既有并集 | 同上 |
| 计划字段 | interval、effective_interval、origin、groups、priority、flags、inference、override 全部比较；每环境 881 个输入、1,762 份计划 | 同上 |
| 块注释 CLI | [0.8.0, 0.9.0)，选 0.8.0；solc rc0、production D3，源码零改动 | cli_acceptance.json |
| 行注释 CLI | [0.5.0, 0.6.0)，选 0.5.0；solc rc0、production D3，源码零改动 | 同上 |
| 缺分号 CLI | unrepaired、unsupported_version_constraints；error_first_line=F: unterminated pragma directive；没有工具调用 | 同上 |
| 并集 CLI | 标志不变；error_first_line=F: unsupported pragma expression；没有工具调用 | 同上 |
| 其他错误 | 非法表达式与空交集消息不变；左右花括号/EOF、伪分隔符、CRLF/Latin-1、原始补丁字节均有测试 | test_pragma_comments.py |
| 代码边界 | 非测试生产文件 14，仅 environment.py 两个函数改动；其余函数 AST、模块、DFG 引用保护 | frozen_audit.json、code_change_summary.json |

本轮未重跑 846 全量生产编译；这是 §4.4e 明确规定的验收方式，完整 make_plan 相同加其他生产代码不变，证明本次改动未改变这些输入的选版计划。上轮 843 成功/3 个已知失败、843 图字节相同是 CP2.3 的历史结论，不标作本轮重测。6c 回归未重放。

### 测试与开发记录

| 环境/测试 | 实测 | 证据 |
|---|---|---|
| dfg | 2653 passed, 9 warnings in 155.25s (0:02:35) | pytest_dfg.json / .log.gz |
| mando | 181 passed, 447 skipped in 21.12s | pytest_mando.json / .log.gz |
| production | 622 passed, 6 skipped in 80.43s (0:01:20) | pytest_production.json / .log.gz |

两环境的 CP2.4 等价明细完全相同。production 的 6 个跳过是 Python 3.7 回退或 regression_6c 专用；mando 的 447 个跳过由生产 profile 或 Python >=3.8 条件触发。DFG v2 在 mando 运行，既有 warning 明细保存在日志。pytest 全部首轮通过，无失败后自动重试；没有额外重跑成功的 CLI，只读审计和打包其原产物。

开发记录见 development_issues.json：Windows rg 读取 WSL UNC 返回 os error 5，改用 WSL Python/git 读取，未改权限或网络配置；不是自动审批拒绝。旧冻结测试对新注释夹具的失败预期需与 r2.12 的有意偏离一致，因此明确记录两项例外并保留所有既有输入的等价断言。此处理在正式测试前完成，没有放宽验收。没有发现需先咨询的新替代方案。

### 归档与复现

production 为 Python 3.10.21、Slither 0.11.6、crytic-compile 0.4.2；mando 为 Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4。runtime.json 是现场版本记录。可信安装 96 个，其中支持范围 92 个；工具信任链和每次 solc 路径、SHA256、命令、退出码、诊断、耗时、费用均在 invocations 和 CLI seal。CPU，OMP/MKL=2，费用 0，无 LLM。

新 CLI 存储归档 cli_acceptance_store.tar.gz，SHA256=ff5bc10faded5855479e34b4edc3c398ee98d6ad3fc04eb9afdee8f2442ab48a，21 个成员回读一致；seal SHA256=802cdd364105afcfc5bf26e1fa24563b1eae0282872b0fedab402d9dfc552084。其两成功、两预期拒绝共 2 次 solc 和 2 次 Slither，拒绝输入调用数 0。旧代码和旧产物按 baseline/frozen_audit 校验；新证据的最终哈希清单见 evidence_seal.json，精确交付清单见 delivery_inventory.json。原临时结果保留，不清理历史文件。

从仓库根可复现测试（输出使用新的批次或临时目录，不覆盖 cp2_4_v1）：

    export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
    export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
    /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -ra -x -p no:cacheprovider scripts/DFG/dfg_v2/tests

实际命令、独立临时目录和运行耗时以 pytest_*.json 为准。reproduce.py 用于修改前复现并校验旧实现哈希，当前新实现上不得再运行；audit_results.py 只读已有结果，写新证据时拒绝覆盖。doc_check 检查本轮六份文档；结果在 doc_check_v*_invocation.json，CHANGE_LOG §27.5 补记。

### 用户授权、差异与停止位置

用户 2026-11-17 明确要求执行更新文档的 CP2.4。本轮按 r2.12 授权，有意偏离冻结实现的两个拒绝行为：pragma 内注释现在接受；未结束指令仍拒绝但消息单列。已追加 DECISIONS 历史；既有 D3/D5/D16/D18/D20/D20a 状态和其他待定决定保持。未提出或实施方案外替代方案。

仅登记既有问题：六个测试模块的本机路径依赖，在 CI/迁移时处理；并集 pragma 与 Slither 进程内超时留后续 CP3 分类。不安装、不下载、不调用 LLM、不启动训练或读写 GPU 锁，不切换全局 solc。CP2.4 本机验收通过，完成记录、完整性和 doc_check 后本地提交；提交号见 git log，不自动 push。停止于待独立审查，CP3 未开始。
