# 决策索引

> **Agent 使用规则**：
> - Session 开始时：只读最近 5 条，了解近况
> - Session 结束时：在最前面追加新条目（不是末尾）
> - 不要读完整历史，用条目里的文件链接按需查阅

格式：`[日期 时间] [类型] 一句话摘要 → 详情文件`

类型说明：
- `DONE` 完成功能 · `WIP` 进行中 · `BLOCKED` 阻塞
- `DECISION` 架构决策 · `CONSTRAINT` 新发现约束 · `FIX` 修复问题

---

[2026-09-05 23:35] DISCOVER 延续上一条性能优化讨论，回答了三个具体问题：(1) "5秒内完成简单编辑"可行——不是靠换更快模型，而是简单任务走代码直接路径（跳过 LLM），AI 分析/视觉核查异步并行做、不阻塞返回结果；(2) 多人使用是否需要各自 API Key——小规模可共享同一个 key（各自 .env 放同一份，零新代码），需要按人限流/计费时才是 feat-011 LiteLLM Proxy 要解决的问题（backlog 已有，未实现）；(3) 用户尚未提供 OpenRouter key/模型 slug，接入 Hermes 系模型的代码改动仍未开始
[2026-09-05 23:20] FIX 面料代码标签"3016"从约 5mm 高放大到 10mm（1cm），用户反馈原尺寸太小看不清；保持左上角锚点不变，等比缩放宽度，全部 22 处（11 正 + 11 反）已更新
[2026-09-05 23:15] DISCOVER 讨论性能/成本优化三个方向（轻量模型路由、跳过 LLM 的规则路由、用文档对象模型工具替代截图视觉检查），均未拍板实现，记入 backlog.md 待评估区

[2026-09-05 22:45] FIX 面料标签"3016"补齐到全部 11 个正面板（此前只放了背面板，用户纠正"正反都要有"）；同时修正 backlog 里一条过时记录（行间距误记为 200mm，已按用户后续纠正改为 20mm）。待办不变：性别文字待用户提供、text.py 的 char_spacing 修复仍未 commit
[2026-09-05 22:35] FIX 修复文字居中的真实 bug 并完成面料标签批量化：之前给号码收紧字间距后重新居中，误用"文字自己修改前的 center_x"当目标（如果这个文字更早已经跑偏，等于把旧错误原样保留），改为始终以"文字所在面板矩形的真实几何中心"为基准重新计算，扫出并修复了 12 处偏移 9~48mm 的号码，验证后偏移全部归零。另外把用户手工放置的面料代码"3016"标签（相对背面板左上角的小号文字）复制到全部 10 件球衣的背面板，样式位置与用户原始范例一致。待办：性别文字（эрэгтэй/эмэгтэй）等用户按人提供后添加为标签第二行；server/tools/text.py 的 char_spacing 修复仍未 commit
[2026-09-05 22:10] FIX 修复了 set_text_style 的真正 bug 并解决数字间距问题：text.py 的 char_spacing/line_spacing 原本用 `float=0` + `>0` 判断是否生效，但 CorelDRAW 真实语义是 0=正常、正值只会加宽、永远无法收紧或显式重置——这是之前两次"修复"反而让间距变得更差的根本原因。已改为 Optional[float]=None 哨兵值（对齐 bold/italic 参数风格），重启 MCP Server 后验证：char_spacing=-15 是紧凑且自然的号码间距（-30 太挤）。已对全部 10 人+参考件的 14/17/23/34/88 等多位数号码应用 -15 并重新居中，含之前遗漏的 NGUYEN 前片号码。代码改动（server/tools/text.py）尚未 commit，等待用户最终确认整批效果后再固化
[2026-09-05 21:45] FIX 球衣批量生成修复与收尾：(1) HASSAN 行大码体型缺失 resize 导致 gap 超大，重建整行并验证尺寸 ✅；(2) 2+ 位号码数字框过大（duplicate 保留原尺寸），char_spacing 实验失败已回滚，标记为待重做（需从头用 create_artistic_text 或 CorelDRAW 手工调）；(3) 确认用户需求：fabric_code 标签必填、性别标记（эрэгтэй/эмэгтэй）按人提供、20mm 行间距锁定 ✅、RGB→CMYK 验证通过 ✅
[2026-09-05 21:15] BUILD/临时探索 球衣批量原型第三轮，本轮才算基本做对：改用"先 group 后 duplicate"模式批量生成 10 个球员（顺序改为参考件第1位、其余依次向下排，间距 20mm），修复了三个真实 bug——(1) 改文字内容后不应再 set_shape_size 强行拉伸（导致单字符号码被过度拉伸的根因）；(2) set_page_size 会围绕中心对称缩放导致坐标整体偏移（连续错位两次的根因）；(3) select_shapes 的 by_type="text" 映射表把文字错映射成线条类型码。另外把误自作主张改的队名 "BIRDS" 改回用户原文 "beards"，用 char_spacing=80 收紧多位数号号间距。发现一个来源不明的小文字"3016"，询问后确认是用户放的面料代码标签示例，要求以后每件球衣都要问一次面料代码并写上。批量生成代码仍未提交 git，等待用户最终确认后再考虑固化为正式工具
[2026-09-05 19:40] BUILD/临时探索 完成球衣批量原型第二轮：修正了对位标记的真实规则（正面 21cm 垂/14cm 平，背面 14cm 垂/40cm 平，姓名对齐背面标记而非之前误判的 40cm 处）；在用户手动完成的参考页基础上新增 10 页代表 10 个随机球员（3 档体型：童装/成人/大码，尺寸为占位编造值），批量导出 10 张 PNG 并按姓名_号码命名。过程中再次确认"用户会直接在 CorelDRAW 手动操作，与 Agent 脚本同一文档同时进行"的协作风险（已写入 backlog 已知约束）。create_artistic_text 及批量生成脚本仍未提交 git，等待用户确认
[2026-09-05 18:20] BUILD/临时探索 用户口述了一个全新业务场景（运动球衣印刷）并要求现场用 MCP 试做：新增 create_artistic_text 工具（text.py，此前项目只有段落文本框创建，没有可精确测量包围盒的美术字创建能力）；用真实 CorelDRAW 搭建了单件球衣原型（前后片面板 + 姓名等比缩小到 25cm 内 + 号码按前13cm/后19cm 精确定高）并截图人工核查通过；过程中发现并记录了 set_shape_position 与创建类工具 y 参数基准不一致的坑（见 backlog.md 已知约束）。此业务线尚未过 DISCOVER/DESIGN 评审，规则细节记在 backlog.md 待评估区，create_artistic_text 的代码改动本次会话尚未提交（等待用户确认）
[2026-09-05 16:35] VERIFY 端到端联调 MCP Server（真实 CorelDRAW + Windows 环境）：Windows 侧无真实 Python（.venv 是 OneDrive 同步残留的 macOS venv），重建 64-bit Python 3.11 venv 并安装依赖；启动 HTTP 模式 server，验证 81 个工具注册成功，实测 get_document_info/create_rectangle/view_canvas/set_fill_rgb/export_pdf 均对真实 CorelDRAW 生效；发现并修复 colors.py 中 4 处 `.Selection`（惰性绑定下是未调用的 bound method）→ `.Selection()` 的 bug，修复后验证选区填色路径正常 → 详见 backlog.md 已知约束区
[2026-06-04 FIX] 新增英文 README，原中文版改为 README-CN，修正两处 License 行错写的 MIT → Apache 2.0

[2026-06-04 FIX] 版权主体改为深圳市玄熵智能科技有限责任公司，新增 NOTICE 文件，格式与 My-Hermes-Desktop 一致

[2026-06-04 FIX] 补充开源发布文件：Apache 2.0 LICENSE、CONTRIBUTING.md、pyproject.toml license 元数据、.gitignore 排除 harness sessions

[2026-06-04 FIX] prompts.py 补充 CorelDRAW 坐标系说明，修正 AI 绘图上下颠倒问题

[2026-06-04 FIX] README 修正：Streamlit 无需同时启动 server.py，双 COM 会冲突

[2026-06-04 FIX] runner.py 缺少 init_connection 导致 Streamlit 路径所有工具返回"CorelDRAW 未连接"

[2026-06-04 FIX] OpenAI 超时 300s + DeepSeek reasoning_content 显示 + 错误终止消息修正

[2026-06-03 STATUS] 查看项目完成情况 — feat-001~005/012~015 全部 passes=true，feat-011/010 延后，feat-006~009 预留

[2026-04-30 DISCOVER] DISCOVER CorelDRAW COM API 工具缺口调研，11 大类未暴露能力写入 backlog → sessions/2026-04-30-discover.md

[2026-06-03 00:00] WIP Session 开始，处理 git 问题 → （进行中）

[2026-06-03 00:10] FIX app.py 页面标题从"标识行业"改为"CorelDRAW 调试"

<!-- 新条目追加到这里（上方） -->

[2026-04-30 13:45] VERIFY test_e2e.py 测试覆盖率审计：21/28 通过，7 失败（3 个 ExportEx），~40+ 工具零测试 → sessions/2026-04-30-1345.md

[2026-04-29 00:01] FIX X6 兼容性多轮修复完成，测试从 13→21/28 通过，PNG/DXF 导出待最终验证 → sessions/2026-04-29-0001.md


[2026-04-27 22:52] WIP 第二阶段架构规划完成，feat-005✅，feat-011/010 待实现，多智能体预留设计固化 → sessions/2026-04-27-session.md
[2026-04-28 20:30] FIX CorelDRAW X6 兼容性修复 — 形状 duck-typing、disconnect 不 Quit、reconnect_on_failure=False、ExportEx 无 struct、测试步骤顺序修正 → sessions/2026-04-28-1921.md

[2026-04-28 19:21] DONE Session Q&A — 提供 CorelDRAW X6 MCP 连通性测试指南，用户待跑 test_e2e.py 验证 → sessions/2026-04-28-1921.md

[2026-04-28 11:30] DONE feat-012/013/014/015 全部完成 — P0批量合并修复、P2代码质量、模板管理增强、工程图标题栏工具 → sessions/2026-04-28-1130.md

[2026-04-28 10:00] DECISION 新增 feat-012/013/014/015 修复批量合并/模板管理/工程图/代码质量问题，feat-011/010 延后 → decisions/sprint-2-plan.md

[2026-04-28 00:38] WIP Session 开始，状态汇报完成，等待确认 feat-011 任务 → sessions/2026-04-28-0038.md


[2026-04-27] DECISION 公司派单升级为多智能体模式：Supervisor + Local Agent SubGraph，SSE 长连接通信，JWT 认证，预留设计已固化 → decisions/sprint-2-plan.md

[2026-04-27] DECISION 架构调整：Agent 移至本地运行，新增 feat-011 LiteLLM Proxy，feat-006/007/008/009 标记为公司派单预留暂不实现 → decisions/sprint-2-plan.md

[2026-04-27] DECISION 新增 feat-010：Agent 层迁移至 LangGraph，支持 RAG + 记忆 + 公司级多业务域，在 feat-006 完成后启动 → decisions/sprint-2-plan.md

[2026-04-27] DECISION 第二阶段规划完成，新增 feat-005～feat-010（多工作站分布式架构 + LangGraph 迁移） → decisions/sprint-2-plan.md

[2026-04-27] DONE feat-005 MCP Server HTTP 模式完成 — server.py 支持 MCP_TRANSPORT env，新增 .mcp.json，uvicorn 依赖已补 → decisions/sprint-2-plan.md

[2026-04-27] DONE 第一阶段MVP完成 — feat-002/003/004 全部 passes=true，Agent编排层+端到端测试就绪 → sessions/2026-04-27-session.md

[2026-04-27] DONE feat-002核心工具实现完成，53个MCP工具函数上线，feat-002→passes=true → sessions/2026-04-27-session.md

[2026-04-23] DECISION 项目 harness 初始化完成 → .harness/registry/decisions/init.md

[2026-04-23 13:49] FIX 修复 install.sh 中 Codex/OpenCode 源文件名错误（致命 bug），更新 README 目录结构和初始化说明 → sessions/2026-04-23-1349.md

[初始化日期] DECISION 项目 harness 初始化，建立 Session 协议框架 → decisions/init.md
