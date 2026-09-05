# 需求池（Backlog）

> 所有未规划的需求、想法、用户反馈都先进这里。
> 随时可以告诉 Agent："把这个加到 backlog：[描述]"，Agent 立即记录。
> Sprint 规划时从"待评估"区取材，不直接跳到 features.json。

---

## 待评估

> 格式：`- [日期] [来源] 描述`
> 来源可以是：自己、用户反馈、竞品观察、技术债、临时想法

- [2026-04-27] [设计文档] 多 CorelDRAW 实例并发 — 应对大批量订单，多台 VM 并行处理不同批次
- [2026-04-27] [设计文档] Web UI / 订单系统对接 — 工厂订单系统通过 API 提交任务，Web 页面展示进度和结果
- [2026-04-27] [设计文档] 自动报价联动 — 根据尺寸、材料、工艺自动计算报价，与生成流程联动
- [2026-04-27] [设计文档] 操作记录与可追溯性 — 记录每次生成的参数、时间、结果，支持回溯和审计
- [2026-04-27] [技术债] runner.py 批量模式改为代码层按 record 迭代，而非依赖 LLM 自己做 for 循环
- [2026-04-27] [技术债] Agent 会话持久化 — 任务中断后可从断点恢复，不丢失上下文
- [2026-04-27] [技术债] Token 消耗统计与成本追踪
- [2026-04-27] [技术债] Python 64-bit 版本检查 — 启动时检测并提示（32-bit Python 会导致 COM 调用失败）
- [2026-09-05] [用户反馈] 新业务线：运动球衣印刷（Jersey）— 与现有门牌信号业务完全不同的应用场景。前后片各一个面板：背面=姓名+号码，正面=号码。已获取的具体规则（口述，尚未正式设计评审）：
  - 姓名最大宽度 25cm，超出时等比例缩小（不允许非等比拉伸变形），需视觉核查效果
  - 号码高度：成人男子（含男子排球）前 13cm / 后 19cm；女子/女排/儿童 前 12.5cm / 后 18cm（近似值，允许一定容差，避免每次都完全一样导致视觉呆板）
  - 儿童号码高度按该儿童尺码前后片实际矩形尺寸按比例决定，无固定值
  - 数字"拉伸"规则未给出精确公式，用户明确表示"用视觉判断，看着顺眼就行"（如 17 不需要额外拉伸，25 可能需要）——已用 view_canvas 截图人工判断验证一次，结论：需要建立可复用的视觉判断标准或干脆保留为人工循环校验步骤
  - 批量生产需求：前后片间需留裁剪间隙，用户口述修正为 17mm（曾误用 50mm）；成品需按打印机最大出片长度（用户提到约 1500cm/900cm，单位存疑，需在正式立项时重新确认）分页；面料丝缕方向需保持竖直（即不可旋转 90°）；文件需按人名/号码分别保存
  - 前后片排列顺序：正面（front）在左（先印），背面（back）在右 —— 与最初假设相反，曾做错方向
  - 每片上都有"十字对位标记"（crosshair，垂直线下垂到一条水平短线，呈"⊥"状，非完整十字）：**正面**＝从面板顶部垂直下垂 21cm，末端水平线宽 14cm；**背面**＝从顶部垂直下垂 14cm，末端水平线宽 40cm。背面姓名的顶部应与背面标记的水平线对齐（即姓名从"距顶 14cm"处开始，不是最初误以为的 40cm）。用户强调这是"habitually 使用但有时会不同"的经验值，不是硬性公式，且**用户会在 CorelDRAW 里手动放置这个标记**，Agent 批量生成时按此规则程序化复现即可
  - 正面除号码外还有队名（如 "BIRDS"），位置结构与背面姓名一致（标记下方一段间距处），但用户说"跟背面不一样，没有精确数字，我自己放"——即队名的具体位置容差更大，人工判断优先于固定公式
  - **重要操作风险**：用户会直接在 CorelDRAW 里手动摆放参考标记，与本 Agent 的脚本化操作发生在同一个文档、同一时间——Agent 曾两次因此误删/误解用户手动添加的内容（把手动放置的对位标记当成"脏数据"删除）。以后处理这类交互式协作场景时，发现无法解释来源的形状，应先询问用户而不是假设是 bug 并删除
  - **已完成一轮批量测试**（2026-09-05）：在用户手动完成的参考页（page 1）基础上，新增 10 页分别代表 10 个随机球员（3 童装 45×80cm/55cm、5 成人 60×80cm、2 大码 75×85cm，均为编造的占位尺寸，非用户提供的真实体型数据），每页复现前后片+对位标记+队名+姓名+号码的完整规则，用 batch_export 一次性导出 10 张 PNG 并按"姓名_号码"重命名。结果已发给用户，尚未收到反馈；真实生产还需要用户提供实际体型数据（当前 3 档尺寸为 Agent 编造的占位值）
  - 尚未正式过 DISCOVER/DESIGN 评审，仅做了原型验证（单件 + 10 人批量），未来若要产品化需要走完整流程并把此条从"待评估"移到"已规划"（建议届时把 create_artistic_text 工具的批量生成逻辑固化成 tools/jersey.py 之类的专用模块，而不是每次现写脚本）

## 已规划

> 已进入某个 Sprint 的需求，从"待评估"移过来，注明 Sprint。

- [2026-04-27] Sprint-1 (Phase 1 MVP) — MCP Server 基础框架搭建 → features.json feat-001 ✅
- [2026-04-27] Sprint-1 (Phase 1 MVP) — 核心工具实现（文档/文字/导出等 53 个工具） → features.json feat-002 ✅
- [2026-04-27] Sprint-1 (Phase 1 MVP) — 单条记录门牌生成端到端验证（Agent 编排层 + 测试脚本） → features.json feat-003 ✅
- [2026-04-27] Sprint-1 (Phase 1 MVP) — 视觉预览反馈基础版（PNG→Base64→LLM 视觉检查闭环） → features.json feat-004 ✅
- [2026-04-27] Sprint-1 (Phase 1 扩展) — GUI Agent 对话框（Streamlit Chat UI + run_single_stream 生成器） → features.json feat-005 ✅ (commit e1595fd)
- [2026-04-27] Sprint-2 (Phase 2 批量生产) — Excel 数据读取与批量合并 → 待开始
- [2026-04-27] Sprint-2 (Phase 2 批量生产) — 质检工具全套完善 → 待开始
- [2026-04-27] Sprint-2 (Phase 2 批量生产) — 错误处理与任务日志 → 待开始
- [2026-04-27] Sprint-2 (Phase 2 批量生产) — 条码/QR 生成集成 → 待开始
- [2026-04-27] Sprint-3 (Phase 3 稳定化) — COM 崩溃重连机制增强 → 待开始
- [2026-04-27] Sprint-3 (Phase 3 稳定化) — 任务队列管理 → 待开始
- [2026-04-27] Sprint-3 (Phase 3 稳定化) — 多模板管理与版本控制 → 待开始

## 已知约束

> 格式：`[YYYY-MM-DD] 描述 — 原因`

- [2026-09-05] Windows 机器可能完全没有真实 Python 安装（只有 Microsoft Store 别名占位符）；项目 `.venv` 若通过 OneDrive 在 Mac/Windows 间同步，会残留另一平台的 venv（如 `pyvenv.cfg` 指向 `/Users/.../homebrew` 路径），在当前平台完全不可用 — 换机器验证环境时必须先检查 `.venv/Scripts/python.exe`（Windows）是否真实存在且可执行，不能假设 `.venv` 存在就等于可用。
- [2026-09-05] `view_canvas`（及 `export_preview_png` 等共用 ExportBitmap+Export fallback 模式的导出函数）在当前页面完全没有任何形状（0 个对象）时，`ExportBitmap` 和 fallback 的 `Export` 会先后失败，抛出 COM 通用异常 `(-2147352567, 'Exception occurred.', ...)` — 这是 CorelDRAW 导出滤镜本身在空白页面上的行为，不是代码 bug；页面上有至少一个形状后再截图即可。
- [2026-09-05] 形状定位的 Y 轴基准在"创建"和"重新定位"两类 API 之间不一致：`create_rectangle`/`create_artistic_text` 等创建类工具的 `y` 参数取的是形状底边（bottom），而 `set_shape_position` 的 `y` 参数取的是形状顶边（top，因为 CorelDRAW 页面坐标系 Y 轴向上）——同一个"y"字面量在两类调用里含义相反。混用会导致形状被移到页面外（例如把一个 190mm 高的文字对象按"底边=80mm"的意图调用 set_shape_position(y=80)，实际会把顶边设到 80mm，底边落到 -110mm，直接飞出页面）。需要精确定位时，应先用 find_shape_by_name 读回 PositionX/Y 与 CenterX/Y 校验语义，而不是假设与创建时同一套坐标含义。

> 决定不做的需求。必须写原因，不允许静默删除。

<!-- 格式：- [日期] 否决原因 — 描述 -->
- [2026-04-30] [技术债/测试审计] test_e2e.py 仅覆盖 ~18 个工具调用，约 40+ MCP 工具零测试覆盖（shapes 全部未测、data_merge/engineering/templates 全部未测、colors 未测、export 部分未测）。需要系统化测试策略。

- [2026-04-30] [技术调研] CorelDRAW COM API 工具缺口分析 — 本次调研发现 11 大类未暴露的 API 能力：
  1) 布尔运算（Weld/Trim/Intersect/Combine/BreakApart）、
  2) AlignAndDistribute / Z-Order 排序、
  3) 文字排版高级功能（TextRange 列/制表位/段落格式/文本框链接/Tab/Columns/FitTextToFrame）、
  4) 效果（Blend/Contour/Extrude/DropShadow/Lens/Envelope/Perspective/InnerShadow）、
  5) 页面操作（InsertPage/DeletePage/MovePage/PageActivate/Page.Name/MasterPage）、
  6) 颜色管理（Palette/ColorManager/ICC Profile/ColorHarmony/ConvertToPalette）、
  7) 文档元数据（Metadata.Author/Keywords/Title/Copyright/LastAuthor）、
  8) 打印设置（PrintSettings/PrintJob/PrintOptions/Prepress/Separations）、
  9) 辅助线/网格/标尺（Guide/Grid/Ruler）、
  10) 符号库（Symbol/SymbolDefinition/SymbolLibrary/CreateSymbol/RevertToShapes）、
  11) 位图操作（Bitmap.Resample/Crop/ConvertToBW/Trace/PowerTRACE）
