# F4 / F11 / F12：证据版本与资格语义对齐

日期：2026-09-23。基线：`5275fc586ec25d41e84459e665c168dba6a31671`，本次改动未提交。
需求来源：[逐项解决方案](../4-Reviews/research-quality-audit-2026-09-23-review-confirm.md) 第 3 节及 F4/F11/F12。

## 修改与来源选择

- 自动 P0/T1 改用 v2 `contract_checked`。独立引用为 null，T1 不再把 schema 检查列作数值试验。来源审核、独立数值验证、物理适用性与确认资格各自为 false。
- prepare、G0、G1/check、训练包装器、T1 模型和 sample-efficiency 消费者支持 v2；旧 v1 仍只作为软件兼容输入。新审计不再仅凭非空引用把 `physics_sources_validated` 设为 true。独立证据包、访问历史及 assessment 门控继续单独约束科学资格。
- 旧运行字节不变。新导出记录保守资格解释，并保留原 report/audit 资格字段供审计；不追溯改写原 v1 的意义。
- 导出器以 `--report` 或 `--evidence-manifest` 为入口，沿 manifest/freeze 找到 Asimov、registration、带名 prepared 和可用评估。显式路径映射不改变 ID；字节、manifest 身份、协议内容摘要和主要谱系需匹配。旧 access 未列为 report upstream 时，由证据清单显式固定 access ID，再核对其 freeze/specification 绑定。
- Stage B、`invalid_or_consumed_output`、失败／完整 bootstrap 及两种 access independence 均保留真实状态；不再要求 bootstrap 区间为空或 access 必须 false。输出必须是新目录。
- 中英文采用同一固定快照。修正英文覆盖表与正文冲突，中文 model-self 完成度和历史执行版本架构。中文表格和英文图表从相同选择文件生成，构建拒绝不同结果混入现有文稿。

用户补充原 test01 位于 `var/runs-test-01/`，当前 `runs/` 为未完成运算。
逐哈希找到精确对应的是 **`h4l-off-test01-old1`**，另一个 `h4l-off-test01` 不同。
原快照 14 个来源文件的大小、SHA-256 和对应 manifest 哈希全部匹配。
75 个训练 manifest 的被引用 ID 均匹配，执行 revision 全为 `a4ecb8f3799729a01bb05aa00f1f5ef7c11b854a`；在该历史源码核对到两个 Dropout、三个 LayerNorm。
完整版本/来源/资格矩阵见[论文证据索引](../../paper/result-evidence.md)。

## 验证记录

实际环境是 Windows AMD64、Python 3.12.13，`pytorch` 环境路径为
`C:/Users/whchen/anaconda3/envs/pytorch/python.exe`。AGENTS 示例的 `D:/apps/anaconda3/Scripts/conda.exe`
在本机不存在，因此使用同名现存环境；没有改环境或安装依赖。

| 层次 | 本次执行与边界 |
|---|---|
| 首轮全套软件测试 | `python -m pytest -q --basetemp D:/t/h4l-f41112-all`：577 passed、5 skipped、509 warnings，902.18 s；该轮之后还修正了导出边界，不能代替最终轮 |
| 工作流包装器回归 | 新 v2 曾被旧 check/run 拒绝，测试先失败再修复；完整脚本测试 59 passed、1 skipped |
| 导出器及 T1 定向回归 | 11 passed、6 deselected、2 warnings：覆盖 v2 与 legacy 相同模型、拒绝资格提升、Stage B、完整／失败 bootstrap、归档迁移、丢失／篡改、协议不一致、快照防漂移 |
| 最终全套软件测试 | `python -m pytest -q --basetemp D:/t/h4l-f41112-final`：**596 passed、5 skipped、511 warnings，922.92 s**；无失败。警告为 pyhf 使用 jsonschema.RefResolver 的弃用警告；5 项跳过未计为通过。完整日志：`runs/f4-f11-f12-final-suite.log` |
| 归档原字节 | 14/14 原聚合文件及 manifest 校验；`var/paper-evidence/test01-restoration-20260923.json` |
| 新聚合导出 | 选定 test01：15 个文件；test03 Stage B：12 个文件，36 单元 `not_run`。80 nominal、4 Shapley、24 交互、105 配对代数复核 |
| 稿件一致性 | `python paper/scripts/sync_manuscript.py --check` 通过；英文数字宏从同一固定快照生成 |
| PDF | `python paper/scripts/build.py --evidence-manifest paper/evidence/test01-source.json` 通过；日期更新后再次构建通过。无未定义引用、overfull box 或 stuck float。PDF 共 13 页；最终第 9–10 页及此前第 8 页渲染检查无裁切／重叠，已消除来源段落单独溢出一页的情况；文本提取无 ?? 或替换字符 |
| 静态检查 | `git diff --check`、`pip check` 通过；32 个修改／新增文本检查无 CRLF，生成证据留在忽略目录 |
| 独立数值／科学资格 | **本次未执行**新独立数值验证、正式 MC bootstrap/Toy/assessment/T2 或物理适用性审核；软件与聚合复算不能授予这些资格 |

原有审查文档为用户未跟踪文件，本次保留。旧中文证据索引原文归档于
`paper/evidence/history/result-evidence-20260921.md`，旧聚合快照字节保持不变。
独立代码审查发现的包装器 v2 兼容、刷新 provenance 时间戳、未发布 bootstrap 失败状态及协议内容摘要问题，均以定向回归处理。

## 复现与重跑边界

```powershell
& 'C:/Users/whchen/anaconda3/envs/pytorch/python.exe' paper/scripts/collect_evidence.py --evidence-manifest paper/evidence/test01-source.json --output var/paper-evidence/test01-fresh-check
& 'C:/Users/whchen/anaconda3/envs/pytorch/python.exe' paper/scripts/sync_manuscript.py --check
& 'C:/Users/whchen/anaconda3/envs/pytorch/python.exe' paper/scripts/build.py --evidence-manifest paper/evidence/test01-source.json
```

纯导出与文稿修订不需要重做 prepare、训练或推断。若之后要发布使用 v2 审计合同的新运行，
必须在新根发布受影响审计、freeze 与下游资格记录；旧 artifacts 不原地升级。
独立验证与科学资格的缺口仍按原科学门控处理，不能由本次测试通过或来源恢复清除。

构建材料是本地归档，不是已经发布的永久外部归档。干净源码检出需要单独带入
选定快照／provenance 或已映射的原始归档；不能把“可以重新编译论文”表述为完整科学重跑。
