

#### 2026-10-13：DDG 诊断补记与 v1.1 正确性修复完成（修改 AI：Codex）

本条接续原封存实验及诊断归档记录，不改写此前结果。详细修改、原因、验证及限制见
docs/training_changes_2026-10-07.md 第16、17节。

- 上一轮冻结权重诊断已经完成：97项测试通过；30个配对折best及7个试点initial/last。
  DDG消息置零使四任务分类翻转分别为1、0、13、1，说明DDG确实参与计算，
  但不能据此推断已获得稳定净收益。重复片段及标注上下文、标量范围和图信息冗余均需区分。
  旧诊断目录、历史input_audit/final_drift与归档数据保留，未为当前HEAD改写。
- 本轮从359a7f1创建隔离工作树 /home/zhao/SmartContract/ge-sc-llm-ddg-v11，
  修改只位于该工作树的 scripts/DFG/projection.py、semantic_cfg.py、__init__.py，
  新增定向测试及审计代码。原业务源码未升级；没有提交、推送或覆盖原图/权重/plan/seal。
  原仓库仅追加本交接文档与training_changes，旧正文的字节前缀保留。
- v1.1修复DOT源码序列化精确比较，以及if/else直接子节点comment误选为body。
  保留严格AST身份、分支、GEN/KILL及回退；额外拒绝序列化物理多行字符串歧义。
  没有更改HGT、tokenizer、标签、训练配置或标量DDG支持范围。
- 修复后的四套图独立保存为E2，旧E0/E1仍封存：

| 任务 | 原E1 DDG边 | E2 DDG边 | 恢复边 | 新canonical |
|---|---:|---:|---:|---:|
| 重入/合约 | 3363 | 3561 | 198 | 0 |
| 重入/节点 | 1711 | 1894 | 183 | 2 |
| 访问控制/合约 | 3765 | 4032 | 267 | 0 |
| 访问控制/节点 | 2632 | 2836 | 204 | 1 |

- 原节点、ID、类型、标签、token、源码映射及CFG/CG多重边完全不变；
  旧DDG端点、canonical及语义事实全部保留。投影回退恢复与新增语义事实分开统计。
  两个clean函数因注释修复恢复，节点任务主要为原事实恢复投影；未把恢复边数写成F1提升。
- D2核验12案例、480个train重复来源：447个完整函数精确回映，33个明确因多pragma未回映；
  918项源码字节跨度核验和121项原输入SHA核验通过，标签、预测与图身份明确绑定。
  R buggy_18节点2706作者为负、公共CSV覆盖、37个训练同文本为正，仍不能唯一确定作者规则。
  AC owner_txorigin部分是参数且已有DDG；纯算术误判也已有DDG，不能全归因于缺状态依赖。
  mapping_write的map是数组；权限guard→敏感操作属于控制依赖，不冒充Def–Use。
- D3仅交付状态位置、读写事件、别名、入口未知、调用HAVOC、强弱更新及投影接口设计。
  9个真实函数候选Oracle与5个合成规格已写明；独立人工批准与solc编译验证均为0。
  入口读余额→调用→清零可能没有具体函数内state Def–Use，应先核验表达价值，
  再决定状态/控制/访问顺序等独立关系。没有实施状态模块或开始E2/E3训练。
- 本轮累计399个不同测试通过。首次18个环境/绝对资源路径失败日志保留；
  使用原已有语法库SHA一致副本，原绝对路径测试在原目录执行，未放宽断言。
  原正式归档只读reporter核验四任务完成/零待办。6217项原资产及新增文件检查、
  两文档授权追加记录见新目录protected_before/after及documentation_update。
- 新目录（在隔离工作树内）：
  scripts/DFG/experiments/audit/ddg_v11_correctness/。
  README为入口；D1_FIX_REPORT与覆盖CSV、D2_CONTEXT_REVIEW/CASE_AUDIT、
  D3_STATE_AWARE_DDG_DESIGN/ORACLE_SPEC/IMPLEMENTATION_PLAN均已交付。
  新图在after/reentrancy_author/与after/access_control_author/的E2_contract/E2_node.gpickle。
- 当前仍有未支持语义回退、标签历史不明、独立人工Oracle未批准、无编译验证等限制；
  新节点canonical也可能增加参数。后续先验收小型状态原型与真实投影信息，再另建训练计划。
  本轮停止于正确性修复、审计与设计，不宣称完整Solidity DDG或检测性能提升。
