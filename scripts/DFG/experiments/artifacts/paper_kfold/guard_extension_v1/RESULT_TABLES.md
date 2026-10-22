# Complete numeric tables: CV validation

Source: report.json and complete identity-aligned predictions. F1/precision/recall are percentages; deltas are percentage points. SD is sample SD across frozen folds, not across independent seeds. HCG-node scoring for node tasks.

## best equal-fold statistics

|Task|Variant|Folds|Buggy-F1 mean +/- SD|Macro-F1 mean +/- SD|Precision mean +/- SD|Recall mean +/- SD|
|---|---|---:|---:|---:|---:|---:|
|reentrancy_author_contract|HCG|5|94.159348 +/- 5.834654|94.345245 +/- 5.282687|96.166667 +/- 5.639641|93.238095 +/- 11.548969|
|reentrancy_author_contract|HCG_DDG|5|94.159348 +/- 5.834654|94.345245 +/- 5.282687|96.166667 +/- 5.639641|93.238095 +/- 11.548969|
|reentrancy_author_contract|HCG_DDG_GUARD|5|94.159348 +/- 5.834654|94.345245 +/- 5.282687|96.166667 +/- 5.639641|93.238095 +/- 11.548969|
|access_control_author_contract|HCG|5|93.559006 +/- 2.562592|93.831616 +/- 2.385049|98.333333 +/- 3.726780|89.393939 +/- 4.251883|
|access_control_author_contract|HCG_DDG|5|93.559006 +/- 2.562592|93.831616 +/- 2.385049|98.333333 +/- 3.726780|89.393939 +/- 4.251883|
|access_control_author_contract|HCG_DDG_GUARD|5|93.559006 +/- 2.562592|93.831616 +/- 2.385049|98.333333 +/- 3.726780|89.393939 +/- 4.251883|
|reentrancy_author_node|HCG|10|96.057994 +/- 10.173047|96.008804 +/- 10.483234|94.636614 +/- 14.738811|98.581672 +/- 2.422963|
|reentrancy_author_node|HCG_DDG|10|96.102732 +/- 10.074797|96.044073 +/- 10.333102|94.617248 +/- 14.606342|98.664331 +/- 2.273235|
|reentrancy_author_node|HCG_DDG_GUARD|10|96.121036 +/- 10.123245|96.064330 +/- 10.401441|94.752111 +/- 14.701669|98.576531 +/- 2.298435|
|access_control_author_node|HCG|10|95.972344 +/- 7.449917|96.876413 +/- 5.528670|94.992408 +/- 11.294173|97.466879 +/- 3.036968|
|access_control_author_node|HCG_DDG|10|95.888668 +/- 7.347579|96.806319 +/- 5.444667|94.892938 +/- 11.133600|97.390543 +/- 3.113429|
|access_control_author_node|HCG_DDG_GUARD|10|95.917092 +/- 7.371314|96.815485 +/- 5.460925|94.946691 +/- 11.154222|97.390543 +/- 3.113429|

## best paired statistics

|Task|Contrast|BF1 delta mean +/- SD|MF1 delta mean +/- SD|BF1 up/tie/down|
|---|---|---:|---:|---:|
|reentrancy_author_contract|HCG_DDG-HCG|+0.000000 +/- 0.000000|+0.000000 +/- 0.000000|0/5/0|
|reentrancy_author_contract|HCG_DDG_GUARD-HCG_DDG|+0.000000 +/- 0.000000|+0.000000 +/- 0.000000|0/5/0|
|reentrancy_author_contract|HCG_DDG_GUARD-HCG|+0.000000 +/- 0.000000|+0.000000 +/- 0.000000|0/5/0|
|access_control_author_contract|HCG_DDG-HCG|+0.000000 +/- 0.000000|+0.000000 +/- 0.000000|0/5/0|
|access_control_author_contract|HCG_DDG_GUARD-HCG_DDG|+0.000000 +/- 0.000000|+0.000000 +/- 0.000000|0/5/0|
|access_control_author_contract|HCG_DDG_GUARD-HCG|+0.000000 +/- 0.000000|+0.000000 +/- 0.000000|0/5/0|
|reentrancy_author_node|HCG_DDG-HCG|+0.044739 +/- 0.485855|+0.035269 +/- 0.469425|7/1/2|
|reentrancy_author_node|HCG_DDG_GUARD-HCG_DDG|+0.018303 +/- 0.451298|+0.020257 +/- 0.434322|3/2/5|
|reentrancy_author_node|HCG_DDG_GUARD-HCG|+0.063042 +/- 0.236205|+0.055526 +/- 0.252240|6/1/3|
|access_control_author_node|HCG_DDG-HCG|-0.083676 +/- 0.198055|-0.070094 +/- 0.165780|2/4/4|
|access_control_author_node|HCG_DDG_GUARD-HCG_DDG|+0.028424 +/- 0.287140|+0.009166 +/- 0.236885|3/4/3|
|access_control_author_node|HCG_DDG_GUARD-HCG|-0.055252 +/- 0.293769|-0.060928 +/- 0.259305|4/3/3|

## best pooled OOF (still CV validation)

|Task|Variant|N|Buggy-F1|Macro-F1|Precision|Recall|TN,FP,FN,TP|
|---|---|---:|---:|---:|---:|---:|---|
|reentrancy_author_contract|HCG|142|94.285714|94.365079|95.652174|92.957746|[68, 3, 5, 66]|
|reentrancy_author_contract|HCG_DDG|142|94.285714|94.365079|95.652174|92.957746|[68, 3, 5, 66]|
|reentrancy_author_contract|HCG_DDG_GUARD|142|94.285714|94.365079|95.652174|92.957746|[68, 3, 5, 66]|
|access_control_author_contract|HCG|114|93.577982|93.847814|98.076923|89.473684|[56, 1, 6, 51]|
|access_control_author_contract|HCG_DDG|114|93.577982|93.847814|98.076923|89.473684|[56, 1, 6, 51]|
|access_control_author_contract|HCG_DDG_GUARD|114|93.577982|93.847814|98.076923|89.473684|[56, 1, 6, 51]|
|reentrancy_author_node|HCG|12036|96.819735|96.393663|94.584785|99.162861|[5093, 373, 55, 6515]|
|reentrancy_author_node|HCG_DDG|12036|96.812068|96.385309|94.583999|99.147641|[5093, 373, 56, 6514]|
|reentrancy_author_node|HCG_DDG_GUARD|12036|96.853849|96.436711|94.705455|99.101979|[5102, 364, 59, 6511]|
|access_control_author_node|HCG|7710|96.501409|97.127049|95.284872|97.749412|[4589, 144, 67, 2910]|
|access_control_author_node|HCG_DDG|7710|96.419098|97.059144|95.188216|97.682230|[4586, 147, 69, 2908]|
|access_control_author_node|HCG_DDG_GUARD|7710|96.451078|97.086029|95.250573|97.682230|[4588, 145, 69, 2908]|

## last equal-fold statistics

|Task|Variant|Folds|Buggy-F1 mean +/- SD|Macro-F1 mean +/- SD|Precision mean +/- SD|Recall mean +/- SD|
|---|---|---:|---:|---:|---:|---:|
|reentrancy_author_contract|HCG|5|90.886700 +/- 4.054699|90.850757 +/- 3.962380|90.476190 +/- 6.135285|91.619048 +/- 5.759740|
|reentrancy_author_contract|HCG_DDG|5|91.014708 +/- 3.136613|90.823648 +/- 3.137820|89.803922 +/- 6.921319|93.142857 +/- 8.169131|
|reentrancy_author_contract|HCG_DDG_GUARD|5|91.616858 +/- 3.257201|91.555492 +/- 3.079355|90.833333 +/- 5.833333|93.142857 +/- 8.169131|
|access_control_author_contract|HCG|5|85.924675 +/- 6.425582|85.899582 +/- 7.117090|88.104895 +/- 9.176920|84.242424 +/- 7.013204|
|access_control_author_contract|HCG_DDG|5|84.675205 +/- 5.292155|84.070647 +/- 6.623113|84.775225 +/- 11.283096|85.909091 +/- 8.117027|
|access_control_author_contract|HCG_DDG_GUARD|5|84.542857 +/- 7.757054|84.137244 +/- 9.038670|85.564103 +/- 12.316236|84.242424 +/- 7.013204|
|reentrancy_author_node|HCG|10|97.150393 +/- 6.806239|97.313467 +/- 6.441251|95.691303 +/- 11.058435|99.339507 +/- 0.854928|
|reentrancy_author_node|HCG_DDG|10|96.910872 +/- 6.707814|96.988755 +/- 6.373908|95.772018 +/- 11.119294|98.816272 +/- 1.419738|
|reentrancy_author_node|HCG_DDG_GUARD|10|97.134213 +/- 6.820278|97.233294 +/- 6.497787|95.764266 +/- 11.204386|99.274256 +/- 0.785389|
|access_control_author_node|HCG|10|95.801033 +/- 5.819577|96.613303 +/- 4.361505|94.320163 +/- 10.295135|97.989314 +/- 1.760652|
|access_control_author_node|HCG_DDG|10|94.151734 +/- 6.081629|95.207461 +/- 4.621633|92.331153 +/- 10.865623|96.959062 +/- 3.901214|
|access_control_author_node|HCG_DDG_GUARD|10|94.121361 +/- 6.602140|95.355555 +/- 4.921749|93.804402 +/- 11.288105|95.528368 +/- 5.922733|

## last paired statistics

|Task|Contrast|BF1 delta mean +/- SD|MF1 delta mean +/- SD|BF1 up/tie/down|
|---|---|---:|---:|---:|
|reentrancy_author_contract|HCG_DDG-HCG|+0.128008 +/- 2.812522|-0.027109 +/- 2.459133|2/2/1|
|reentrancy_author_contract|HCG_DDG_GUARD-HCG_DDG|+0.602151 +/- 1.346450|+0.731844 +/- 1.636454|1/4/0|
|reentrancy_author_contract|HCG_DDG_GUARD-HCG|+0.730159 +/- 3.245799|+0.704735 +/- 2.927850|2/2/1|
|access_control_author_contract|HCG_DDG-HCG|-1.249470 +/- 5.333584|-1.828934 +/- 5.036230|2/1/2|
|access_control_author_contract|HCG_DDG_GUARD-HCG_DDG|-0.132348 +/- 4.952211|+0.066596 +/- 4.437568|2/1/2|
|access_control_author_contract|HCG_DDG_GUARD-HCG|-1.381818 +/- 4.191940|-1.762338 +/- 5.013156|1/2/2|
|reentrancy_author_node|HCG_DDG-HCG|-0.239521 +/- 0.836857|-0.324712 +/- 0.842527|3/2/5|
|reentrancy_author_node|HCG_DDG_GUARD-HCG_DDG|+0.223341 +/- 0.820617|+0.244539 +/- 0.953288|4/2/4|
|reentrancy_author_node|HCG_DDG_GUARD-HCG|-0.016181 +/- 0.542630|-0.080173 +/- 0.519440|4/1/5|
|access_control_author_node|HCG_DDG-HCG|-1.649300 +/- 2.173270|-1.405842 +/- 1.739000|0/2/8|
|access_control_author_node|HCG_DDG_GUARD-HCG_DDG|-0.030373 +/- 2.626331|+0.148094 +/- 2.315759|4/1/5|
|access_control_author_node|HCG_DDG_GUARD-HCG|-1.679672 +/- 3.542389|-1.257749 +/- 2.534263|1/2/7|

## last pooled OOF (still CV validation)

|Task|Variant|N|Buggy-F1|Macro-F1|Precision|Recall|TN,FP,FN,TP|
|---|---|---:|---:|---:|---:|---:|---|
|reentrancy_author_contract|HCG|142|90.909091|90.844616|90.277778|91.549296|[64, 7, 6, 65]|
|reentrancy_author_contract|HCG_DDG|142|91.034483|90.840982|89.189189|92.957746|[63, 8, 5, 66]|
|reentrancy_author_contract|HCG_DDG_GUARD|142|91.666667|91.547619|90.410959|92.957746|[64, 7, 5, 66]|
|access_control_author_contract|HCG|114|85.714286|85.960591|87.272727|84.210526|[50, 7, 9, 48]|
|access_control_author_contract|HCG_DDG|114|84.482759|84.205665|83.050847|85.964912|[47, 10, 8, 49]|
|access_control_author_contract|HCG_DDG_GUARD|114|84.210526|84.210526|84.210526|84.210526|[48, 9, 9, 48]|
|reentrancy_author_node|HCG|12036|97.875841|97.611066|96.220588|99.589041|[5209, 257, 27, 6543]|
|reentrancy_author_node|HCG_DDG|12036|97.403572|97.091885|96.062759|98.782344|[5200, 266, 80, 6490]|
|reentrancy_author_node|HCG_DDG_GUARD|12036|97.734579|97.451005|96.047024|99.482496|[5197, 269, 34, 6536]|
|access_control_author_node|HCG|7710|96.192517|96.861361|94.433657|98.018139|[4561, 172, 59, 2918]|
|access_control_author_node|HCG_DDG|7710|94.491803|95.443327|92.283061|96.808868|[4492, 241, 95, 2882]|
|access_control_author_node|HCG_DDG_GUARD|7710|94.438894|95.445494|93.628260|95.263688|[4540, 193, 141, 2836]|

## Probability and classification changes

|Task|Checkpoint|Contrast|Complete N|Sparse rows|Fixed|Regressed|Class flips|Mean absolute probability delta over complete N|
|---|---|---|---:|---:|---:|---:|---:|---:|
|reentrancy_author_contract|best|HCG_DDG_GUARD-HCG_DDG|142|142|0|0|0|0.004434548|
|reentrancy_author_contract|best|HCG_DDG_GUARD-HCG|142|142|0|0|0|0.014258666|
|reentrancy_author_contract|last|HCG_DDG_GUARD-HCG_DDG|142|140|1|0|1|0.011914486|
|reentrancy_author_contract|last|HCG_DDG_GUARD-HCG|142|141|2|1|3|0.022097320|
|access_control_author_contract|best|HCG_DDG_GUARD-HCG_DDG|114|114|0|0|0|0.004328109|
|access_control_author_contract|best|HCG_DDG_GUARD-HCG|114|114|0|0|0|0.010117803|
|access_control_author_contract|last|HCG_DDG_GUARD-HCG_DDG|114|113|2|2|4|0.029440949|
|access_control_author_contract|last|HCG_DDG_GUARD-HCG|114|113|1|3|4|0.038165640|
|reentrancy_author_node|best|HCG_DDG_GUARD-HCG_DDG|12036|12035|25|19|44|0.010589220|
|reentrancy_author_node|best|HCG_DDG_GUARD-HCG|12036|12036|30|25|55|0.011874827|
|reentrancy_author_node|last|HCG_DDG_GUARD-HCG_DDG|12036|12036|76|33|109|0.016954077|
|reentrancy_author_node|last|HCG_DDG_GUARD-HCG|12036|12036|22|41|63|0.016706027|
|access_control_author_node|best|HCG_DDG_GUARD-HCG_DDG|7710|7710|7|5|12|0.010131486|
|access_control_author_node|best|HCG_DDG_GUARD-HCG|7710|7710|5|8|13|0.012311471|
|access_control_author_node|last|HCG_DDG_GUARD-HCG_DDG|7710|7710|56|54|110|0.023961212|
|access_control_author_node|last|HCG_DDG_GUARD-HCG|7710|7710|17|120|137|0.031239815|

Full per-fold values, confusion matrices, predictions and resources are in the adjacent CSV files. No folds excluded.
