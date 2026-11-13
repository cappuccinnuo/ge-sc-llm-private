# EP8 E-A 结果报告

原名主批60次、匿名敏感性批80次已完成，另只读复用EP7的20个G3R结果。
原名是唯一主终点；匿名结果不进入Holm检验族。best为预登记主结果，last单列。

|视图|任务|剖面|checkpoint|BF1均值±样本标准差|
|---|---|---|---|---|
|original|reentrancy_node|G3R|best|99.7295 ± 0.2056|
|original|reentrancy_node|G3R|last|99.7882 ± 0.1712|
|original|reentrancy_node|G3R-T|best|99.7226 ± 0.2248|
|original|reentrancy_node|G3R-T|last|99.8110 ± 0.1611|
|original|reentrancy_node|G4R|best|99.7414 ± 0.1733|
|original|reentrancy_node|G4R|last|99.8212 ± 0.1354|
|original|reentrancy_node|G4R-P|best|99.4863 ± 0.6756|
|original|reentrancy_node|G4R-P|last|99.7214 ± 0.1838|
|original|access_control_node|G3R|best|99.2027 ± 1.0804|
|original|access_control_node|G3R|last|99.5682 ± 0.2691|
|original|access_control_node|G3R-T|best|99.2058 ± 1.1216|
|original|access_control_node|G3R-T|last|99.4569 ± 0.4009|
|original|access_control_node|G4R|best|99.6044 ± 0.2361|
|original|access_control_node|G4R|last|99.4960 ± 0.3428|
|original|access_control_node|G4R-P|best|99.5189 ± 0.2863|
|original|access_control_node|G4R-P|last|99.5380 ± 0.2293|
|anonymous|reentrancy_node|G3R|best|98.9298 ± 1.2223|
|anonymous|reentrancy_node|G3R|last|99.1850 ± 0.7335|
|anonymous|reentrancy_node|G3R-T|best|98.9409 ± 1.1272|
|anonymous|reentrancy_node|G3R-T|last|99.3138 ± 0.6660|
|anonymous|reentrancy_node|G4R|best|99.2493 ± 0.8848|
|anonymous|reentrancy_node|G4R|last|99.4119 ± 0.4746|
|anonymous|reentrancy_node|G4R-P|best|99.1036 ± 1.0382|
|anonymous|reentrancy_node|G4R-P|last|99.3420 ± 0.5759|
|anonymous|access_control_node|G3R|best|98.1526 ± 2.9729|
|anonymous|access_control_node|G3R|last|98.5048 ± 2.7447|
|anonymous|access_control_node|G3R-T|best|98.8580 ± 1.1266|
|anonymous|access_control_node|G3R-T|last|98.9119 ± 1.2316|
|anonymous|access_control_node|G4R|best|98.9907 ± 0.9776|
|anonymous|access_control_node|G4R|last|98.7615 ± 1.7423|
|anonymous|access_control_node|G4R-P|best|98.9573 ± 1.0925|
|anonymous|access_control_node|G4R-P|last|98.7466 ± 1.6162|

|视图|H1两项均值均为正|H1原始p|max-p后的处理|
|---|---|---|---|
|original|True|0.199677|pending_H2_EP9|
|anonymous|True|0.160156|outside_Holm_descriptive|

|任务|对照|checkpoint|原名差值(pp)|匿名差值(pp)|原名p|匿名p|原名/匿名零差折|
|---|---|---|---|---|---|---|---|
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

|视图|任务|剖面|语料|best TN/FP/FN/TP|best pooled BF1|
|---|---|---|---|---|---|
|original|reentrancy_node|G3R|all|4997/26/10/6773|99.7349|
|original|reentrancy_node|G3R|SolidiFI|3987/17/1/6750|99.8668|
|original|reentrancy_node|G3R|nonSolidiFI|1010/9/9/23|71.8750|
|original|reentrancy_node|G3R-T|all|4996/27/10/6773|99.7276|
|original|reentrancy_node|G3R-T|SolidiFI|3986/18/0/6751|99.8669|
|original|reentrancy_node|G3R-T|nonSolidiFI|1010/9/10/22|69.8413|
|original|reentrancy_node|G4R|all|4997/26/9/6774|99.7423|
|original|reentrancy_node|G4R|SolidiFI|3983/21/0/6751|99.8447|
|original|reentrancy_node|G4R|nonSolidiFI|1014/5/9/23|76.6667|
|original|reentrancy_node|G4R-P|all|4964/59/14/6769|99.4637|
|original|reentrancy_node|G4R-P|SolidiFI|3955/49/4/6747|99.6088|
|original|reentrancy_node|G4R-P|nonSolidiFI|1009/10/10/22|68.7500|
|original|access_control_node|G3R|all|4184/32/19/3054|99.1719|
|original|access_control_node|G3R|SolidiFI|3947/25/0/3053|99.5922|
|original|access_control_node|G3R|nonSolidiFI|237/7/19/1|7.1429|
|original|access_control_node|G3R-T|all|4181/35/16/3057|99.1727|
|original|access_control_node|G3R-T|SolidiFI|3945/27/0/3053|99.5598|
|original|access_control_node|G3R-T|nonSolidiFI|236/8/16/4|25.0000|
|original|access_control_node|G4R|all|4207/9/16/3057|99.5928|
|original|access_control_node|G4R|SolidiFI|3965/7/0/3053|99.8855|
|original|access_control_node|G4R|nonSolidiFI|242/2/16/4|30.7692|
|original|access_control_node|G4R-P|all|4203/13/17/3056|99.5116|
|original|access_control_node|G4R-P|SolidiFI|3966/6/0/3053|99.9018|
|original|access_control_node|G4R-P|nonSolidiFI|237/7/17/3|20.0000|
|anonymous|reentrancy_node|G3R|all|4918/105/50/6733|98.8621|
|anonymous|reentrancy_node|G3R|SolidiFI|3909/95/42/6709|98.9893|
|anonymous|reentrancy_node|G3R|nonSolidiFI|1009/10/8/24|72.7273|
|anonymous|reentrancy_node|G3R-T|all|4923/100/52/6731|98.8835|
|anonymous|reentrancy_node|G3R-T|SolidiFI|3916/88/40/6711|99.0554|
|anonymous|reentrancy_node|G3R-T|nonSolidiFI|1007/12/12/20|62.5000|
|anonymous|reentrancy_node|G4R|all|4961/62/45/6738|99.2123|
|anonymous|reentrancy_node|G4R|SolidiFI|3949/55/31/6720|99.3642|
|anonymous|reentrancy_node|G4R|nonSolidiFI|1012/7/14/18|63.1579|
|anonymous|reentrancy_node|G4R-P|all|4938/85/42/6741|99.0668|
|anonymous|reentrancy_node|G4R-P|SolidiFI|3927/77/34/6717|99.1805|
|anonymous|reentrancy_node|G4R-P|nonSolidiFI|1011/8/8/24|75.0000|
|anonymous|access_control_node|G3R|all|4198/18/93/2980|98.1716|
|anonymous|access_control_node|G3R|SolidiFI|3962/10/74/2979|98.6097|
|anonymous|access_control_node|G3R|nonSolidiFI|236/8/19/1|6.8966|
|anonymous|access_control_node|G3R-T|all|4200/16/55/3018|98.8374|
|anonymous|access_control_node|G3R-T|SolidiFI|3963/9/36/3017|99.2597|
|anonymous|access_control_node|G3R-T|nonSolidiFI|237/7/19/1|7.1429|
|anonymous|access_control_node|G4R|all|4198/18/45/3028|98.9704|
|anonymous|access_control_node|G4R|SolidiFI|3961/11/28/3025|99.3595|
|anonymous|access_control_node|G4R|nonSolidiFI|237/7/17/3|20.0000|
|anonymous|access_control_node|G4R-P|all|4200/16/49/3024|98.9367|
|anonymous|access_control_node|G4R-P|SolidiFI|3964/8/33/3020|99.3258|
|anonymous|access_control_node|G4R-P|nonSolidiFI|236/8/16/4|25.0000|

逐折差值与零差折、错误减少率、pooled混淆矩阵、两层语料的Wilson P/R区间、
名称规则与两条无学习边规则、非SolidiFI节点、持续漏报案例和资源记录见 results 下同名 JSON/CSV。
分层规则直接复用冻结8C；名称规则沿用原名审核记录，两视图数值相同，不冒称匿名输入上的预测器。
零错误基线的相对错误减少率记为空；未知守卫等规则输入不当作已知不存在。

折间标准差为描述统计。pooled OOF仍不是独立测试；模型参数和优化轨迹也有变化，
不能把分数差异全部归因于纯语义作用。最终七类实验将另建服务器批次，显存充足；当前限制仅来自本机。

运行入口：python -B -m scripts.edge_sem.recon.ep8_run run --root /home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/edge_sem/artifacts/ep8_v1
分析入口：python -B -m scripts.edge_sem.recon.ep8_run analyze --root /home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/edge_sem/artifacts/ep8_v1

本报告对应：/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/edge_sem/artifacts/ep8_v1/results/summary.json
