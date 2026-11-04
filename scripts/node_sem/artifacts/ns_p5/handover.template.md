## 2026-11-03 NodeSem NS-P5：N-A原名计划完成（修改 AI：Codex）

按r16封存artifacts/batch_NA_v1：{S0o,S1o,S2,S4}×{G0,G3R}×30折=240个新fit计划；本轮训练0次、CUDA未初始化。32套载体、240份零步初值逐一CPU严格重载；32组fresh fold1证明参数逐位一致，16组原token一致。S0o全参数及其他配置共同参数取对应8H零步锚点，旧匿名分数不作原名配对基线。

用户批准本机RTX3050先导、服务器另建，以及先证明再复用未训练结构。保留分组嵌套协议、inner_val选best/outer_test最终评分、L-audit/seed1/默认TF32，同一比较族不混设备。G0+S4仍含DFG派生特征，不是无DFG对照。非SolidiFI节点正例32/20核对通过。

3722测试通过，0失败/跳过，42既有警告；8H、旧P4和三文档前缀核验通过。准备@@MIN@@分钟，正式fit名义估算@@LOW@@–@@HIGH@@小时，仅假设估算；合约S4单轮最低空闲44MiB，不能保证全量稳定。

新增batch_na.py/p5_prepare.py/test_batch_na.py，旧执行器/冻结代码不变；授权模板false，NS-P5A另绑worker与授权，不改旧seal。报告NS_P5_REPORT、详细选择/命令见training_changes§84。最终实验使用用户安排的显存充足服务器，本机4GiB仅开发限制，服务器未部署实测。重产物留WSL、不额外写C盘；本地提交，不自动推送、不启动训练。
