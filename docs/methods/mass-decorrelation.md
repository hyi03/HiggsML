# 质量去相关与条件校准

## 物理问题

在 `H -> ZZ* -> 4l` 中，`m4l` 对信号和连续背景具有强判别力。即使模型不直接输入质量，轻子运动学、Z 重建量和角变量仍可能携带质量代理信息。高分区域若偏爱特定质量范围，就会改变背景质量谱，即质量雕刻。

当前 H4l 协议允许各表示显式接收共同的 `m4l` 条件，因此比较必须在相同质量信息、相同角色和相同模板网格下进行。目标不是抹去所有质量信息，而是分离质量本身与条件运动学判别信息，并控制背景分数随质量的变化。

## 对抗训练

背景 adversary 从 classifier logit 预测质量类别。梯度反转使 adversary 最小化质量分类损失，同时使 classifier 接收相反方向、由 `lambda` 缩放的梯度：

\[
\min_\theta\left(L_{cls}-\lambda L_{adv}\right).
\]

更大的 `lambda` 增强去相关压力，但可能损失分类能力或训练稳定性。Adversary 的分类损失、AUC 和质量切片诊断衡量不同性质，必须分别报告。

## 条件 CDF

条件映射定义为

\[
u=F_b(t\mid m),
\]

其中 `t` 是判别分数，`m` 是 `m4l`，`F_b` 由独立 calibration 角色的背景拟合。若估计充分，背景 `u` 在质量切片内应近似均匀，从而把预测模型和去相关后处理分开研究。

实现支持 raw、physical 和 absolute 权重语义。协议固定质量网格、插值、tails、ties、稀疏与负权重规则；冻结映射同时应用于 template 和相应伪事件。使用 absolute optimizer weight 的模型仍须通过 physical-CDF 桥接检查，不能只报告训练分布中的平坦性。

## 诊断与推断边界

质量切片的背景接受率用于直接检查 mapped/raw 的形状依赖。Signed physical weight 用于物理产额和冻结映射拟合；acceptance 稳定性报告使用协议规定的 absolute-weight 分母，避免权重抵消导致不稳定比值。

主问题是在共同质量条件、共同 calibration 和同一模板误差模型下，engineered19 或 compact 表示是否相对 decay7 缩小 `mu=1` 的预期区间，同时保持偏差和覆盖。AUC 或单一去相关指标不能替代联合质量—分数 likelihood、有限 MC 传播和伪实验验证。
