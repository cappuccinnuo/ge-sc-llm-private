# F4 接口准备与兼容性

本轮没有改原 HGT、tokenizer、训练器或 formal plan。
新适配器位于 state/stage_f/model_adapter.py。

四类增强关系 DATA_DEF_USE / STATE_DEF_USE / STATE_ACCESS_ORDER /
EXTERNAL_CALL_BEFORE_STATE_WRITE 均保持正向，原 CFG/CG 按原 reflect_graph 规则处理。
8 张真实候选图已逐 canonical 检查 DGL 边数，未额外生成增强关系反向边。

state/stage_f/initialization.py 沿用原 semantic paired initializer 的数值算法，
仅扩大已允许的增强 schema 集合，让 E2 可带已有 DATA_DEF_USE。
单独版本 state-forward-semantic-paired-v1，不冒用原冻结实验初始化版本。
共同节点类型/canonical 参数按语义对齐；新增关系独立初始化。
原 E0/E1 数据关系案例的初始化逐张量与旧算法一致，测试已覆盖。
没有使用已训练 E0/E1 权重给新候选初始化。

compatibility.py 为 CPU 合成检查工具，复用原 HGTLayer；
8维测试夹具不是把真实512维 tokenizer 改为8维。
没有 optimizer；只前向、反传一次、保存未训练初始化状态、重载核验输出。
三类新关系 relation_msg 梯度均非零，输入绑定检测图、特征、标签和 schema 错位。
F4_initial_synthetic.pt 明确 kind=untrained_synthetic_initial，不是 best/last 或实验权重。

## 正式入口的最小后续迁移清单（本轮未执行）

1. 新建 E2/E3 准备入口和协议版本；绑定本批 graph manifest、算法/初始化版本、原冻结文件折、特征/标签 SHA。
2. 在旁路模型装配中选择 forward adapter；不能直接让旧加载器反射 STATE_DEF_USE。
3. 训练实例支持与全图注册 schema 分开审计，保留训练无支持的关系，不在评分时创建随机参数。
4. 每对独立 fresh initialization，检查共同参数一致；不能把已训练旧 checkpoint 当新初始化。
5. 继续现有 paper_kfold 的 CV validation / 最低 val loss best 规则；不修改原封存批次。
6. 先实际全图非优化前向/反向显存测量，之后才申请/确认小折验证，最终完整 K 折另立计划。

RTX3050 4GB快照可用2913MiB；没有测量完整 E2/E3 配对模型峰值，不能据此声称显存足够。
本轮只测了合成CPU图，不具备“全量训练准备全部通过”的证据。
