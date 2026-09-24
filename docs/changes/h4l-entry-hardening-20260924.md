# H4l 完整入口的历史与完成状态加固

日期：2026-09-24。范围：按科研审查后续建议修改源代码、配置、文档与测试；本次不改动 `runs/`，不启动正式 MC、训练、bootstrap、Toy、assessment 或 T2。

## 已实现的行为

1. **跨目录访问历史。** `config/h4l_history_roots.json` 声明 `runs/` 和必需归档 `var/runs-test-01/`。扫描仅读取四类历史 ledger，不读取事件或 assessment 数值。缺失归档、损坏记录、路径越界及符号链接/junction 均拒绝；model-self 不消耗 assessment 访问。所有声明根目录通过第一个根目录的原子 population 占用记录协调新访问。归档旧记录不迁移、不改写。
2. **诚实的本地审核。** 新 `h4l-off-self-review-access-v2` 在发布前检查实际历史，记录根目录、配置路径/哈希及空匹配列表，只声明“在这些目录中未发现访问”，不声明全局独立性。发现历史时不发布新的 unused 审核。旧 v1 仍可读取，但不能绕过当前历史检查；同一 freeze 的恢复仍需既有绑定 receipt。
3. **只读预检与有限执行范围。** `h4l_all.py --plan-only` 输出方法、身份、历史和待执行命令，不创建运行目录、不启动子进程。没有 prepared 身份时明确标记待确认；实际执行在 prepare 后、训练前再次检查。默认方法仍为 `median-v1`，联合阈值必须显式选择且与已注册方法一致。`--stage-b-only` 在核验绑定计划及 Stage B 报告后停止。
4. **可核验的完成状态。** 预检/访问/support 阻断返回 `5`；子进程正常返回但完整证据不足时返回 `6`。完整结束前核验全部 36 个单元、终态内容哈希、计划/freeze/单元身份，以及最终报告与这些终态的一致性；可选择当前绑定的 `report-resume-*`。计划和 Markdown 报告也需有效文件 receipt。已发布数值失败可以是执行终态，因此执行完成与科学状态分别输出，资格始终为探索性、未独立验证。

权重定义、scale factors、T0/T1 区间算法、阈值选择算法和正式 replica/Toy 预算均未因本项工作改变。软件完成检查不能替代 F2 结果、低计数覆盖率、选择后覆盖率或物理适用性证据。

## 真实目录只读核验

```powershell
python scripts/h4l_all.py --run-name test03 --threshold-method median-v1 --plan-only
```

结果：退出码 `5`，`access_status=blocked_used_population`。当前 prepared population 为
`1059f531f6da7dd2aaae9ef4956c6f2a6465fbf1f5e1254bb0ee81b08fd42e00`，
与归档历史匹配，且存在不同或未知 freeze 的访问。这里的 claim 说明访问/预算已占用，不证明相应数值任务全部完成。

另以 `joint-support-v1` 对 test03 预检也返回 `5`，原因是该运行已注册 `median-v1`。不能在原运行中换方法；新方法需新 Stage B，且新目录仍不能消除同一 population 的既有访问。

新运行的计划示例：

```powershell
python scripts/h4l_all.py --run-name planned-joint-001 --threshold-method joint-support-v1 --plan-only
```

该例若没有 prepared 身份，只能得到 `pending_prepare_identity`；不能视为有资格启动完整 assessment。复用现有 prepared/train 而只构建新方法 Stage B 时，使用复现手册中的 `h4l_off_run.py --source-run-name ... --run-name ... --threshold-method joint-support-v1 --stage-b` 路径，不必重训。

## 验证记录

- 定向回归：历史、自审、预检、完成状态、入口路由和 marginal 工作流共 **60 passed**；补充报告 receipt 检查后相关测试组 **23 passed**。两组有重叠，不能相加。
- 回归先复现失败，再验证修复：跨根目录占用、报告终态被改动、嵌入值与终态不一致、只有计划文件的 Stage B、缺失 Markdown 报告。
- 全量测试：**621 passed, 5 skipped, 511 warnings**，退出码 `0`，耗时 1115.27 秒（18 分 35 秒）。警告为 pyhf 对 `jsonschema.RefResolver` 的弃用提示；跳过项目未计入通过证据。命令为 `python -m pytest -q --basetemp D:/t/h4l-entry-full -p no:cacheprovider`，运行前通过 `PYTHONPATH` 加载下述写入保护和本仓库 `src/`。
- 真实预检只读取元数据和历史；所有 Python 检查均注入 `runs/` 写入拒绝保护，临时目录在 `D:/t/`，日志在忽略目录 `var/h4l-entry-hardening-20260923/`。
- 与实施前 252 文件哈希基线比较，本任务之外的既有文件未改变；`git diff --check` 通过，任务文本统一 LF。

上述为 Windows/Python 3.12 的软件与合成契约证据。未执行本次正式 MC 数值验证、独立物理参考验证、跨平台兼容性验证或完整一键科学运算。
