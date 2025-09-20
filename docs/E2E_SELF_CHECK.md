## 端到端自检指南

本指南和脚本 `scripts/e2e_smoke.py` 帮助快速验证核心功能链路：

### 覆盖范围
1. 转换注册表 & 多类型文件转换 (Markdown / 文本 / 代码)
2. 不支持类型失败路径 & 错误记录
3. 会话级 (session_id) 首事件注入与完整事件序列
4. 中途取消流程 (cancelled -> done)
5. Retry 失败（不支持类型仍失败的稳定性）
6. conversion_types 过滤搜索

### 运行方式 (Windows CMD)
```cmd
python scripts\e2e_smoke.py
```
输出示例：
```
==== E2E SMOKE RESULT ====
Status: SUCCESS
Full ingestion stages: ['scan_start', 'scan_complete', 'file_processing', ... , 'done']
Cancel ingestion stages: ['scan_start', 'scan_complete', 'file_processing', 'cancelled', 'done']
Documents in DB: 4
```

### 判定标准
| 检查项目 | 期望 | 失败指示 |
|----------|------|----------|
| session_id | 第一条/早期事件出现 | 未出现报错 |
| 事件阶段 | 至少包含 scan_start / scan_complete / done | 缺少阶段报错 |
| 取消流程 | 取消后出现 cancelled 并随后 done | 未出现 cancelled |
| 转换类型 | 至少包含 DIRECT / TEXT_TO_MD / CODE_TO_MD | 缺少任一类型 |
| 不支持文件 | raw.xyz 生成 failed 文档 | 未记录 failed |
| Retry 行为 | 不支持类型重试仍失败 | 成功或未执行 |
| 搜索过滤 | conversion_types=TEXT_TO_MD 返回仅 TEXT_TO_MD 文档 | 返回混入其他类型 |

### 常见问题
1. IndentationError / ImportError：确认最近修改是否未保存或虚拟环境冲突。
2. Unsupported file type 提示增多：检查 config 中类型列表是否意外清空。
3. 取消无效：确认前端 Stop 发送了 JSON `{"session_id": "..."}`，或脚本中 `request_cancel_ingestion` 调用时机是否过晚。

### 后续可扩展自检
* 增加图片/视频/Draw.io/XMind 实际文件样本。
* 验证 OCR Caption 缓存策略（未来实现后加入）。
* 增加并发多会话并行导入压力测试。
