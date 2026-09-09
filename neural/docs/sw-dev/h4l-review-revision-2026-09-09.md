# H4l 评审修订与验证记录

日期：2026-09-09。依据：[差距分析](../../../docs/4-Reviews/H4l-Research-Project-Implementation-Gap-2026-09-09.md)。用户已授权修改文档与代码。

## 本次修改

- 更新科研方案、当前状态、架构和artifact说明，区分已有软件与尚缺的科学证据，保留原计数快照。
- 新增`research_protocol_v2.json`，绑定逐epoch诊断及独立固定名义模板带符号μ点估计。v1协议不改写，旧模型日志不补造。
- 训练保存BCE/背景CE、λ、验证AUC、固定定义的质量诊断；生成单模型和同种子M6/λ=0配对图。附加eval不消耗训练随机数，既有优化和checkpoint规则不变。
- M5-abs在读取校准payload前验证同prepared、同协议且passed的G1。
- μ=0 Toy在原物理区间旁输出带符号μ诊断，逐箱保证正物理率、保留不可用及搜索边界状态。它固定名义模板及nuisance，不是T1剖面拟合或置信区间。
- 明确Toy区间校准尚待独立预注册和实现，覆盖检查不等于校准。

## 验证

使用本机Conda `pytorch`：`D:/apps/anaconda3/envs/pytorch/python.exe`，Windows/AMD64、Python 3.12.13、PyTorch 2.7.1。按已有`requirements-research.txt`安装可选pyhf 0.7.6及锁定依赖。

| 检查 | 状态 |
|---|---|
| 首轮针对性验证 | 22 passed；包含单箱解析MLE、正率/边界、协议兼容、损失分项、训练张量不变与G1守卫 |
| `pip check` | No broken requirements found |
| 研究全集 | 105 passed，72条pyhf依赖弃用警告，104.35秒 |
| 全套neural回归 | 499 passed，73条警告，319.60秒；无失败或跳过 |
| 最终图表增量复核 | 2 passed，16.67秒；另人工检查合成训练曲线，标题完整、普通模型不标对抗阶段 |
| 最终输入/G1守卫增量复核 | 10 passed，13.32秒；缺input-run返回输入错误，不触发内部异常 |
| 打包与文档检查 | wheel构建成功；18个研究源码/协议文件逐字节核对；7份文档本地链接有效；git diff --check通过 |

全套回归覆盖主体功能修订；图表呈现与缺失输入处理的最后调整另以上述局部复核验证，之后重建安装包。警告为现有TestOpeningResult收集提示及pyhf的jsonschema.RefResolver弃用提示。未将历史开发记录中的94/484等数值作为本轮结果。

未执行真实MC训练或先导、正式500次Toy评估、MELA后端物理参考验证、真实数据访问或held-out test开启。测试中的少量Toy与模型训练均为合成软件验证。ARM64权威验收与signed-MC T1适用性仍未验证。
