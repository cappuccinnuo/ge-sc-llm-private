# EdgeSem v1 E-A/E-B 综合报告

本轮原名60次、匿名60次正式拟合均已验收；原名是唯一主视图，匿名为预登记的描述性敏感性检查。
P2固定50轮，最低inner_val loss选best，last为辅助；本批仅两个节点任务。
本批不是合约级检测，也不能直接对比论文原始协议下的分数。

## 登记检验

|假设|原始p|Holm校正p|两项差值均正|登记条件通过|
|---|---|---|---|---|
|H1|0.19967679|0.39935358|True|False|
|H2|0.95693921|0.95693921|False|False|

H1原始p约0.1997，EP8已不显著；Holm不会改变这一结论。匿名结果不进入检验族。
差值单位为百分点；折间标准差为描述统计。

## 两视图登记对照

|任务|对照|checkpoint|原名差值|匿名差值|原名原始p|匿名原始p|零差折原/匿|
|---|---|---|---|---|---|---|---|
|reentrancy_node|G4R-A − G4R|best|-0.0189|+0.0790|0.956939|0.0737088|8/3|
|reentrancy_node|G4R-A − G4R-Api|best|+0.0074|+0.0907|0.633839|0.347755|7/6|
|reentrancy_node|G3R-TA − G3R-T|best|+0.0089|+0.0302|0.560444|0.959248|7/3|
|reentrancy_node|G4R-A − G4R|last|-0.0097|+0.0862|0.633839|0.113188|7/3|
|reentrancy_node|G4R-A − G4R-Api|last|+0.0066|+0.0348|0.711025|0.475246|7/2|
|reentrancy_node|G3R-TA − G3R-T|last|+0.0171|+0.0018|0.5791|0.845703|9/0|
|access_control_node|G4R-A − G4R|best|+0.0007|-0.3494|1|0.385033|6/3|
|access_control_node|G4R-A − G4R-Api|best|-0.0112|-0.0456|1|0.683286|6/2|
|access_control_node|G3R-TA − G3R-T|best|+0.0587|-0.2088|0.53547|0.67952|5/5|
|access_control_node|G4R-A − G4R|last|+0.1020|-0.0916|0.304937|0.331621|8/3|
|access_control_node|G4R-A − G4R-Api|last|-0.0156|+0.0814|0.5791|0.076133|9/6|
|access_control_node|G3R-TA − G3R-T|last|+0.0492|-0.1802|0.560444|0.711025|7/7|
|reentrancy_node|G4R − G3R-T|best|+0.0188|+0.3083|0.199677|0.0488281|4/0|
|reentrancy_node|G4R − G4R-P|best|+0.2551|+0.1456|0.0388671|0.160156|5/0|
|reentrancy_node|G3R-T − G3R|best|-0.0069|+0.0111|0.633839|1|7/0|
|reentrancy_node|G4R − G3R-T|last|+0.0102|+0.0981|0.504845|0.625|4/0|
|reentrancy_node|G4R − G4R-P|last|+0.0998|+0.0699|0.0526332|0.610067|2/2|
|reentrancy_node|G3R-T − G3R|last|+0.0228|+0.1288|0.296818|0.130859|6/0|
|access_control_node|G4R − G3R-T|best|+0.3986|+0.1328|0.201447|0.414823|3/1|
|access_control_node|G4R − G4R-P|best|+0.0855|+0.0335|0.136838|0.798346|4/3|
|access_control_node|G3R-T − G3R|best|+0.0031|+0.7054|0.572558|0.136838|4/4|
|access_control_node|G4R − G3R-T|last|+0.0391|-0.1504|0.504845|0.759614|4/2|
|access_control_node|G4R − G4R-P|last|-0.0420|+0.0149|0.878167|0.683286|3/2|
|access_control_node|G3R-T − G3R|last|-0.1113|+0.4071|0.17939|0.756684|5/5|

## 逐折BF1汇总

|视图|任务|剖面|checkpoint|均值±样本标准差|
|---|---|---|---|---|
|original|reentrancy_node|G3R|best|99.7295 ± 0.2056|
|original|reentrancy_node|G3R|last|99.7882 ± 0.1712|
|original|reentrancy_node|G3R-T|best|99.7226 ± 0.2248|
|original|reentrancy_node|G3R-T|last|99.8110 ± 0.1611|
|original|reentrancy_node|G3R-TA|best|99.7315 ± 0.2065|
|original|reentrancy_node|G3R-TA|last|99.8282 ± 0.1517|
|original|reentrancy_node|G4R|best|99.7414 ± 0.1733|
|original|reentrancy_node|G4R|last|99.8212 ± 0.1354|
|original|reentrancy_node|G4R-A|best|99.7225 ± 0.1952|
|original|reentrancy_node|G4R-A|last|99.8115 ± 0.1699|
|original|reentrancy_node|G4R-Api|best|99.7151 ± 0.2275|
|original|reentrancy_node|G4R-Api|last|99.8049 ± 0.1624|
|original|access_control_node|G3R|best|99.2027 ± 1.0804|
|original|access_control_node|G3R|last|99.5682 ± 0.2691|
|original|access_control_node|G3R-T|best|99.2058 ± 1.1216|
|original|access_control_node|G3R-T|last|99.4569 ± 0.4009|
|original|access_control_node|G3R-TA|best|99.2645 ± 1.1044|
|original|access_control_node|G3R-TA|last|99.5061 ± 0.3179|
|original|access_control_node|G4R|best|99.6044 ± 0.2361|
|original|access_control_node|G4R|last|99.4960 ± 0.3428|
|original|access_control_node|G4R-A|best|99.6051 ± 0.2710|
|original|access_control_node|G4R-A|last|99.5979 ± 0.2545|
|original|access_control_node|G4R-Api|best|99.6163 ± 0.2109|
|original|access_control_node|G4R-Api|last|99.6135 ± 0.2325|
|anonymous|reentrancy_node|G3R|best|98.9298 ± 1.2223|
|anonymous|reentrancy_node|G3R|last|99.1850 ± 0.7335|
|anonymous|reentrancy_node|G3R-T|best|98.9409 ± 1.1272|
|anonymous|reentrancy_node|G3R-T|last|99.3138 ± 0.6660|
|anonymous|reentrancy_node|G3R-TA|best|98.9712 ± 1.1344|
|anonymous|reentrancy_node|G3R-TA|last|99.3156 ± 0.6166|
|anonymous|reentrancy_node|G4R|best|99.2493 ± 0.8848|
|anonymous|reentrancy_node|G4R|last|99.4119 ± 0.4746|
|anonymous|reentrancy_node|G4R-A|best|99.3282 ± 0.8809|
|anonymous|reentrancy_node|G4R-A|last|99.4982 ± 0.4087|
|anonymous|reentrancy_node|G4R-Api|best|99.2376 ± 0.8817|
|anonymous|reentrancy_node|G4R-Api|last|99.4634 ± 0.4150|
|anonymous|access_control_node|G3R|best|98.1526 ± 2.9729|
|anonymous|access_control_node|G3R|last|98.5048 ± 2.7447|
|anonymous|access_control_node|G3R-T|best|98.8580 ± 1.1266|
|anonymous|access_control_node|G3R-T|last|98.9119 ± 1.2316|
|anonymous|access_control_node|G3R-TA|best|98.6492 ± 2.1067|
|anonymous|access_control_node|G3R-TA|last|98.7317 ± 1.9372|
|anonymous|access_control_node|G4R|best|98.9907 ± 0.9776|
|anonymous|access_control_node|G4R|last|98.7615 ± 1.7423|
|anonymous|access_control_node|G4R-A|best|98.6413 ± 1.8708|
|anonymous|access_control_node|G4R-A|last|98.6699 ± 1.5575|
|anonymous|access_control_node|G4R-Api|best|98.6869 ± 1.6951|
|anonymous|access_control_node|G4R-Api|last|98.5885 ± 1.6563|
|original|reentrancy_node|G4R-P|best|99.4863 ± 0.6756|
|original|reentrancy_node|G4R-P|last|99.7214 ± 0.1838|
|original|access_control_node|G4R-P|best|99.5189 ± 0.2863|
|original|access_control_node|G4R-P|last|99.5380 ± 0.2293|
|anonymous|reentrancy_node|G4R-P|best|99.1036 ± 1.0382|
|anonymous|reentrancy_node|G4R-P|last|99.3420 ± 0.5759|
|anonymous|access_control_node|G4R-P|best|98.9573 ± 1.0925|
|anonymous|access_control_node|G4R-P|last|98.7466 ± 1.6162|

## 非SolidiFI与名字规则

|视图|任务|剖面|best TN/FP/FN/TP|BF1|
|---|---|---|---|---|
|original|reentrancy_node|G3R|1010/9/9/23|71.8750|
|original|reentrancy_node|G3R-T|1010/9/10/22|69.8413|
|original|reentrancy_node|G4R|1014/5/9/23|76.6667|
|original|reentrancy_node|G4R-A|1011/8/9/23|73.0159|
|original|reentrancy_node|G4R-Api|1010/9/9/23|71.8750|
|original|reentrancy_node|G3R-TA|1011/8/9/23|73.0159|
|original|access_control_node|G3R|237/7/19/1|7.1429|
|original|access_control_node|G3R-T|236/8/16/4|25.0000|
|original|access_control_node|G4R|242/2/16/4|30.7692|
|original|access_control_node|G4R-A|243/1/16/4|32.0000|
|original|access_control_node|G4R-Api|241/3/16/4|29.6296|
|original|access_control_node|G3R-TA|238/6/17/3|20.6897|
|anonymous|reentrancy_node|G3R|1009/10/8/24|72.7273|
|anonymous|reentrancy_node|G3R-T|1007/12/12/20|62.5000|
|anonymous|reentrancy_node|G4R|1012/7/14/18|63.1579|
|anonymous|reentrancy_node|G4R-A|1012/7/9/23|74.1935|
|anonymous|reentrancy_node|G4R-Api|1012/7/9/23|74.1935|
|anonymous|reentrancy_node|G3R-TA|1007/12/14/18|58.0645|
|anonymous|access_control_node|G3R|236/8/19/1|6.8966|
|anonymous|access_control_node|G3R-T|237/7/19/1|7.1429|
|anonymous|access_control_node|G4R|237/7/17/3|20.0000|
|anonymous|access_control_node|G4R-A|235/9/16/4|24.2424|
|anonymous|access_control_node|G4R-Api|235/9/16/4|24.2424|
|anonymous|access_control_node|G3R-TA|237/7/19/1|7.1429|
|original|reentrancy_node|G4R-P|1009/10/10/22|68.7500|
|original|access_control_node|G4R-P|237/7/17/3|20.0000|
|anonymous|reentrancy_node|G4R-P|1011/8/8/24|75.0000|
|anonymous|access_control_node|G4R-P|236/8/16/4|25.0000|
- 名字规则 original / reentrancy_node / all：BF1 99.7414；混淆矩阵 [5020, 3, 32, 6751]。
- 名字规则 original / reentrancy_node / SolidiFI：BF1 99.9778；混淆矩阵 [4001, 3, 0, 6751]。
- 名字规则 original / reentrancy_node / nonSolidiFI：BF1 0.0000；混淆矩阵 [1019, 0, 32, 0]。
- 名字规则 original / access_control_node / all：BF1 99.6410；混淆矩阵 [4214, 2, 20, 3053]。
- 名字规则 original / access_control_node / SolidiFI：BF1 99.9673；混淆矩阵 [3970, 2, 0, 3053]。
- 名字规则 original / access_control_node / nonSolidiFI：BF1 0.0000；混淆矩阵 [244, 0, 20, 0]。
- 名字规则 anonymous / reentrancy_node / all：BF1 99.7414；混淆矩阵 [5020, 3, 32, 6751]。
- 名字规则 anonymous / reentrancy_node / SolidiFI：BF1 99.9778；混淆矩阵 [4001, 3, 0, 6751]。
- 名字规则 anonymous / reentrancy_node / nonSolidiFI：BF1 0.0000；混淆矩阵 [1019, 0, 32, 0]。
- 名字规则 anonymous / access_control_node / all：BF1 99.6410；混淆矩阵 [4214, 2, 20, 3053]。
- 名字规则 anonymous / access_control_node / SolidiFI：BF1 99.9673；混淆矩阵 [3970, 2, 0, 3053]。
- 名字规则 anonymous / access_control_node / nonSolidiFI：BF1 0.0000；混淆矩阵 [244, 0, 20, 0]。

名字规则沿用原名审计记录，两视图相同；不是从匿名输入预测的规则。
逐折错误变化、相对错误减少率、分层Wilson P/R区间、非SolidiFI正例和误报逐节点、持续案例、两条无学习边规则见同名JSON/CSV。
每次fit的best检查点均读取u/U范数和outer_test目标入边偏置；按层/关系族/头/目标标签汇总，仅作描述，不作独立节点显著性检验。
机制输出见 parameter_norms.json 与 attention_bias.json；不上传权重。

## 冻结与局限

- fallback/receive function nodes are unavailable in the frozen projector; MOD_APPLY is not_in_graph; E-C0 must report owner type.
- The anonymous gate covers about 16%/14% of attribute rows and only 3 library calls per task.
- Attribute bit 61 can be unknown when pragma has no upper bound; report the sealed per-task proportions.
- Bits 46/50/51/53 describe the source-side near endpoint.
- MOD_APPLY guard-type bit is always 47.
- Modified functions and synthetic nodes lack semantic CFG (unk_cfg).
- ENV/state edges lack a use_context evidence source.
- Original names leak injected patterns; the frozen lexical rule can match or exceed the model.
- Folds share training data; one seed and pooled OOF are not independent external validation.
- P/R Wilson intervals are descriptive and do not model within-file node dependence.
- Graph parameters, aggregation and optimization change too; score gains do not isolate pure semantic causation.
- 第61位未知 access_control_node：1605/21830条属性行（7.35%）；分母为全部正向属性行。
- 第61位未知 reentrancy_node：2274/31372条属性行（7.25%）；分母为全部正向属性行。

冻结schema：/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/edge_sem/artifacts/frozen_schema/schema.json
最终七类实验将在显存充足的服务器另建批次；当前显存限制仅来自本机，本轮不自动启动服务器阶段。
结果来源：/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/edge_sem/artifacts/ep9_v1/results/summary.json
E-A来源：/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/edge_sem/artifacts/ep8_v1/results/summary.json

执行：python -B -m scripts.edge_sem.recon.ep9_run run
分析：python -B -m scripts.edge_sem.recon.ep9_run analyze
