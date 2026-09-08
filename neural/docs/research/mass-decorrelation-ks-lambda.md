# KS、λ 与质量去相关技术说明

本文从物理分析目标出发，说明四轻子质量 `m4l`、质量区间、工作点、质量去相关、
对抗网络、λ 和 KS 之间的关系，并结合
`atlas2020_4lep/development-inclusive-001` development OOF 结果解释当前行为。
本文讨论的所有结果均为 MC educational/technical demo，不是 ATLAS 结果或物理测量。

## 1. 为什么质量 `m4l` 如此重要

`m4l` 是四轻子系统的不变质量。对当前受控 MC 配对，Higgs 信号集中在约
125 GeV，而 ZZ 背景覆盖更宽的连续质量范围。如果直接把 `m4l` 交给分类器，模型很容易学到：

```text
m4l 接近 125 GeV -> 更可能是 Higgs
m4l 远离 125 GeV -> 更可能是 ZZ
```

这种分类器可以得到很高的 AUC，但高分筛选可能把原本连续的 ZZ 背景塑造成低质量凸起，
从而破坏后续对背景质量谱的解释。因此训练协议禁止把 `m4l` 作为分类器输入。

删除 `m4l` 输入并不等于模型不知道质量。轻子动量、四轻子横动量和角变量等运动学量与
`m4l` 存在物理相关性；模型仍可能利用它们间接恢复质量信息。当前 development 诊断中，
Higgs 几乎全部位于第一个报告质量 bin：该 bin 的上边界约为 148.15 GeV，包含约
61,648 个 Higgs 行；第二个 bin 只有 2 行，后续 bin 没有 Higgs。分类器因此天然倾向于识别
“低质量风格”的事件。

## 2. 什么是质量区间

本项目中的“质量区间”需要与 inclusive 范围和分类器工作点明确区分。

### 2.1 Inclusive 分析范围

当前 [inclusive 协议](inclusive-protocol.md) 不在预处理、训练或主评价阶段额外施加固定的
`m4l` 质量窗。通过基础选择的事件在整个质量范围内参与 development 五折 OOF；held-out
test 仍保持封存。Inclusive 表示不再额外裁剪固定质量窗，并不表示训练过程完全不使用质量信息。

### 2.2 对抗训练使用的 11 个质量 bin

每个 fitting fold 只使用该折的 ZZ 背景，按照 `abs(physical_weight)` 的加权分位数建立
11 个右闭、首尾无界的质量 bin。以当前报告边界为例：

```text
(-inf, 148.15]
(148.15, 186.69]
(186.69, 198.20]
...
(393.78, +inf)
```

这些 bin 不是等宽区间，而是尽量包含相近的背景绝对权重。每个背景事件因此获得一个质量类别，
供 adversary 预测。分位数分箱减少高统计量质量区域对对抗损失的支配；边界只由 fitting 数据
确定，不能使用 validation 或 held-out test。各 λ 候选在同一 fold 内共用相同边界。

### 2.3 loose、medium、tight 工作点

工作点不是质量区间，而是分类器分数阈值：

| 工作点 | 目标背景效率 |
|---|---:|
| loose | 0.50 |
| medium | 0.20 |
| tight | 0.10 |

对每个 λ 候选，系统把 development OOF ZZ 按模型分数从高到低排列，再确定达到目标背景绝对
权重所需的阈值。相同阈值随后用于 Higgs 和 ZZ，并计算实际背景效率、信号效率及 KS。

简言之：质量 bin 描述事件位于哪个 `m4l` 区域；工作点描述分类器筛选有多严格。

## 3. 什么是质量去相关

质量去相关的目标不是让分类器完全失去分类能力，而是让背景的分类器分数尽量不依赖 `m4l`。
理想条件可写为：

\[
P(\mathrm{score} > t \mid m_{4l}) \approx \mathrm{constant}.
\]

例如 tight 工作点在全局保留 10% 的 ZZ 背景，那么理想情况下，每个质量区域也应大致保留
10%。这样筛选主要改变背景总量，而不会显著改变背景质量形状。

当前 λ=0.5 候选的 tight 工作点并非如此：

```text
全局背景效率       约 10%
最低质量 bin       约 55%
第二个质量 bin     约 23%
高质量 bin         约  2%
```

这说明分类器仍强烈偏爱低质量 ZZ。筛选后的背景向 Higgs 所在质量区域集中，这一现象称为
质量雕刻（mass sculpting）。去相关就是要压制这种依赖，使各质量区域的背景选中效率更平坦。

## 4. 为什么引入 adversary

普通分类器只最小化 Higgs/ZZ 分类损失 `L_cls`。只要某种质量代理可以提高分类能力，普通训练
就没有理由放弃它。因此项目增加了一个 adversary：

```text
15 项运动学特征
        |
        v
    classifier
        |
        +-----------------> Higgs/ZZ 分类
        |
        v
 classifier logit
        |
        v
 gradient reversal
        |
        v
     adversary ----------> ZZ 的 11 个质量 bin
```

adversary 只观察背景事件的 classifier logit，并尝试预测其质量 bin。如果预测准确，说明
classifier 输出仍携带质量信息；如果接近随机，说明只通过 classifier 输出较难恢复背景质量。

adversary 自身最小化质量分类交叉熵 `L_adv`，classifier 则通过 Gradient Reversal Layer 接收
反向的 adversarial 梯度，主动学习让 adversary 更难预测质量。

## 5. λ 的精确作用

训练代码前向计算的总损失为：

\[
L_{total} = L_{cls} + L_{adv}.
\]

Gradient Reversal Layer 在前向传播中保持数值不变，在反向传播中把传给 classifier 的
adversarial 梯度乘以 `-lambda`。因此两个网络实际优化不同的目标：

\[
\text{adversary:}\quad \min_{\phi} L_{adv},
\]

\[
\text{classifier:}\quad \min_{\theta}\left(L_{cls} - \lambda L_{adv}\right).
\]

λ 控制分类能力与质量去相关之间的权衡：

| λ | 训练含义 |
|---:|---|
| 0 | 不施加去相关压力，只优化 Higgs/ZZ 分类 |
| 较小 | 分类优先，轻度抑制质量信息 |
| 较大 | 更愿意牺牲分类能力以减少质量依赖 |
| 过大 | 可能损失过多分类信息或造成训练不稳定 |

λ 不是 KS 门槛、质量窗口宽度、工作点阈值或普通 L2 正则化系数。它只是对抗梯度传回
classifier 时的强度系数。

协议还使用 warm-up 和 ramp：epoch 1--5 的 effective λ 为 0；epoch 6--15 逐步升至目标 λ；
epoch 16 以后保持目标 λ。这使 classifier 先建立基本分类能力，再逐渐承受去相关压力。

## 6. KS 究竟测量什么

对每个 loose、medium、tight 工作点，项目比较：

1. 全部 development OOF ZZ 的 `m4l` 分布；
2. 通过该工作点分数阈值的 development OOF ZZ 的 `m4l` 分布。

两者都使用 `abs(physical_weight)` 构造加权累计分布：

\[
F_{all}^{w}(m),\qquad F_{selected}^{w}(m).
\]

加权 KS 距离定义为：

\[
D_{KS}=\sup_m\left|F_{all}^{w}(m)-F_{selected}^{w}(m)\right|.
\]

它表示两个累计质量分布之间的最大垂直距离：

- KS 接近 0：筛选前后背景质量形状接近；
- KS 为 0.10：最大累计差约为 10 个百分点；
- KS 为 0.535：最大累计差约为 53.5 个百分点，表明显著质量雕刻。

这里的 KS 是质量形状变化量，不是训练集与测试集之间的过拟合 KS，也不是传统两样本 KS
假设检验的 p-value。本项目把它作为预注册的效果量门槛；三个工作点均要求 KS 不大于 0.10。
具体实现见 `src/training/qualification.py` 中的 `weighted_ks_distance()` 和
`working_point_metrics()`。

## 7. 为什么 tight KS 通常最难

loose 工作点保留约 50% 的背景，局部质量偏好会被大量普通背景稀释。tight 工作点只保留最高分
的约 10% 背景，分类器最依赖的质量代理通常集中在这部分极端高分事件中，因此残留相关性会被
显著放大。

当前 development OOF 结果体现了这一规律：

| 目标 λ | loose KS | medium KS | tight KS |
|---:|---:|---:|---:|
| 0.00 | 0.2137 | 0.5716 | 0.6837 |
| 0.05 | 0.0969 | 0.3707 | 0.6354 |
| 0.10 | 0.1034 | 0.3618 | 0.6085 |
| 0.20 | 0.0906 | 0.3451 | 0.5832 |
| 0.50 | 0.0791 | 0.2888 | 0.5354 |

λ 增大后去相关整体有效，但首先改善的是 loose 工作点；极端高分尾部仍然明显依赖质量。
λ=0.5 已使 loose KS 通过 0.10 门槛，但 medium 和 tight 仍分别约为 0.289 和 0.535。

## 8. AUC、KS 与 λ 的整体关系

项目面对的是一个带约束的分类问题：尽量提高 development OOF AUC，同时要求三个工作点的
背景质量 KS 均不大于 0.10。λ 用于探索两者之间的性能边界：

```text
lambda 太小
  -> 分类能力强、AUC 高
  -> classifier score 携带较多质量信息
  -> KS 高

lambda 增大
  -> 去相关压力增强
  -> KS 通常下降
  -> AUC 可能下降

lambda 合适
  -> AUC 仍满足最低要求
  -> loose、medium、tight KS 同时满足约束
```

本次 AUC 从 λ=0 的 0.9884 只下降到 λ=0.5 的 0.9863，而 KS 虽持续改善，medium 和 tight
仍远高于门槛。这说明当前 λ 范围尚未把 classifier 推入明显牺牲分类能力、换取质量独立性的
权衡区域。

同时需要注意，训练目标和最终验收并不完全相同：adversary 优化的是从 classifier logit 预测
11 个质量 bin 的平均交叉熵；KS 验收关注的则是 50%、20%、10% 分数尾部的连续质量累计分布。
平均质量预测变难，并不自动保证极端高分尾部已经质量平坦。因此，λ 决定对抗压力强度，KS
负责对最终筛选行为进行独立验收，AUC 则保证去相关没有完全破坏 Higgs/ZZ 分类能力。
