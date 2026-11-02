# NS-P2 实施报告（NS-P2b 校正）

实施 AI：Codex。NS-P2 实现提交为 f049d18e；本报告在 NS-P2b 中依据源码和封存证据重新编写。原文的中文已被替换成字面问号，无法恢复原句；原始字节、所在文件及起止字节位置保存在 artifacts/ns_p2b/corrupted_docs/。

新增 text_view.py、p2_acceptance.py、offline/asset_registry.py、offline/encode.py、offline/assets.json/seal、依赖锁和 README、configs/S2.json，以及 test_text_view.py、test_p2_acceptance.py、offline_checks.py；修改 carrier._aligned 与对应配置测试。模型权重与 NPZ 保留本地，不纳入 Git。

文本使用冻结 ProjectionView/Projector/node_code_view 的兼容 AST 身份截取。if/while 为条件、for 为头部；函数/构造器/modifier 为签名，合约/库/接口为头部，语句和 struct 为对应完整片段。end 节点使用占位符，env_source 使用环境键。空白规范化；锚点损坏直接拒绝，不猜行号。原/匿名两视图切片模式一致，逆改名后原文相同。

carrier._aligned 允许以 F3 为全集的 manifest 供 F0/F3 共用：F0 只省略经身份核验的辅助行，其余严格按原图顺序。原 TOKEN_IDS/S0/S1 保持。CODE manifest 含 dtype/shape、row_key、file、source/code/vector SHA、presence、F0/F3 图指纹、生产者和资产引用；产物与源码摘要不符则拒绝。S2 只注册 CODE/256/concat，真正 concat 训练仍留 NS-P4。

离线编码使用冻结 CodeT5、eval/inference_mode、GPU fp16、输出 float32、max_length=128、batch_size=32，模型自身输出归一化的 256 维向量；按模型摘要＋长度＋pooling＋文本去重，再按长度排序分批。GPU 使用既有 .training.lock，不与训练并行。没有修改 DFG/HGT/tokenizer、图、标签、折或训练计算。

## 环境、授权与模型

用户明确批准 Codex 创建独立 nodesem 并安装依赖，覆盖模板原先要求用户自行准备环境的限制；模型下载也已授权。实际 Python 3.10.21，torch 2.6.0+cu118，CUDA runtime 11.8，transformers 4.46.3，sentence-transformers 3.3.1。来源为本地官方快照及逐文件 SHA 校验，安装/下载记录在 artifacts/ns_p2/environment/，大文件位于 E 盘承载的 WSL；mando 不改。

安装初期 pip 看到了 Python 3.10 user-site，移除了 filelock 3.32.6, tqdm 4.70.1, typing_extensions 4.16.0；已按原版本与校验 wheel 恢复。后续统一 python -s/PYTHONNOUSERSITE=1；nodesem 激活禁用 user-site，encoder 拒绝在 user-site 启用时运行。此副作用不得写成“从未触及用户环境”，详细见 installation_scope.json 与 restore_user_site2.log。WSL 网络不稳定时经既有 Windows 代理获取下载文件，截断或摘要错误不能算完成。

清理记录仅删除 8 个自己产生的重复安装/临时文件，共 161907029 字节；模型/特征删除数为 0。没有删除用户其他资料。

| model | revision |
| --- | --- |
| BAAI/bge-small-en-v1.5 | 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a |
| Salesforce/codet5p-110m-embedding | d9f3a534af4252f04b10cd9f78e05037542d10f6 |
| microsoft/unixcoder-base | 5604afdc964f6c53782a6813140ade5216b99006 |

加载 local_files_only=True，CodeT5 自定义代码文件也核验 SHA，权重使用 weights_only=True。只有 CodeT5 完成全量编码，UniXcoder 的 masked mean 有单测但未做全量对照，BGE 留到后续教师阶段。

## 文本产物与截取方式

| task | F0 | env | F3 | header | full | signature | condition | placeholder | fallback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| reentrancy_node | 12036 | 187 | 12223 | 214 | 7614 | 2247 | 1089 | 1059 | 0 |
| access_control_node | 7710 | 182 | 7892 | 177 | 5074 | 2182 | 244 | 215 | 0 |
| reentrancy_contract | 18312 | 298 | 18610 | 543 | 11587 | 3981 | 1267 | 1232 | 0 |
| access_control_contract | 13432 | 261 | 13693 | 474 | 8730 | 3723 | 403 | 363 | 0 |

表中 full 包含环境节点。单视图 52418 行，两视图共 104836 行。F0/F3 的 9 个规定原属性及全部原节点属性一致，全部原基础边保留。4 任务×2 视图×3 项生产者扰动共 24 项：禁止属性和 DOT 前缀不影响输出，损坏锚点被拒绝；8 组均为 0 截取回退。文件名/行号只用于对齐元数据，不拼进特征文本。

## 八组编码结果

| task | view | rows | unique | dedup % | truncated | seconds | peak MiB | bitwise | max error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| reentrancy_node | original | 12223 | 2846 | 76.716 | 4 | 23.938 | 419.496 | True | 0.0 |
| reentrancy_node | anonymous | 12223 | 7223 | 40.906 | 3 | 28.778 | 392.980 | True | 0.0 |
| access_control_node | original | 7892 | 2567 | 67.473 | 4 | 16.761 | 380.050 | True | 0.0 |
| access_control_node | anonymous | 7892 | 5115 | 35.188 | 3 | 23.355 | 408.177 | True | 0.0 |
| reentrancy_contract | original | 18610 | 5636 | 69.715 | 4 | 28.952 | 418.792 | True | 0.0 |
| reentrancy_contract | anonymous | 18610 | 12014 | 35.443 | 3 | 40.036 | 372.825 | True | 0.0 |
| access_control_contract | original | 13693 | 4762 | 65.223 | 4 | 23.729 | 404.237 | True | 0.0 |
| access_control_contract | anonymous | 13693 | 9484 | 30.738 | 3 | 33.388 | 367.049 | True | 0.0 |

8 组均进行了两次独立完整编码，repeat_bitwise=true，最大误差为 0；没有优化器更新。原名视图每任务 4/4/4/4 行超过 max_length，匿名每任务 3/3/3/3 行；截断属于已记录输入限制。总墙钟 218.936 秒，包含编码流程，不是纯 kernel 时间；PyTorch peak allocated 为 367.049–419.496 MiB，仅对应离线编码，不等同于 HGT 显存。

## 历史测试与装配验收

| suite | passed | failed | skipped | warnings | seconds |
| --- | --- | --- | --- | --- | --- |
| node_sem | 216 | 0 | 0 | 4 | 6.610 |
| dfg_v2 | 2653 | 0 | 0 | 9 | 167.190 |
| legacy | 223 | 0 | 0 | 29 | 3.580 |
| offline | 18 | 0 | 0 | 0 | 1.900 |

NS-P2 原载体验收为 8 个模态加载、16 个 F0/F3 选择对齐通过；8H execution.load 与 _code_refs 对批准的 runtime_resume_v2 运行版本一致。原测试命令、时间、警告和日志引用见 artifacts/ns_p2/validation.json；这些是历史结果。本轮新的测试和只读复验另记 NS-P2B 报告，不修改旧 JSON。

## 边界、复现与后续

未运行 HGT 训练，无 F1 或收益结论；M2、concat、LLM 和蒸馏未实现。代码节点文本是按既有 AST 与 8G 文件级拼写双射产生，不能声称完成 Solidity 语义绑定/编译验证，或跨文件编号不变性。

最终实验按用户计划在显存充足服务器执行；当前 RTX3050 4 GiB 仅为本地开发限制，服务器尚未部署实测。复现命令见 offline/README.md；所有旧输入只读，新跑必须使用新目录，修改生产者后必须新生成特征，不能更改旧 manifest 来绕过校验。

NS-P2b 的文档编码保护、编号影响与残留词诊断另见 NS_P2B_REPORT.md。历史训练配置和所有既有特征保持不变。
