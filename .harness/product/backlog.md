# 需求池（Backlog）

> 所有未规划的需求、想法、用户反馈都先进这里。
> 随时可以告诉 Agent："把这个加到 backlog：[描述]"，Agent 立即记录。
> Sprint 规划时从"待评估"区取材，不直接跳到 features.json。

---

## 待评估

- [2026-09-06] [DISCOVER][用户口述，语音转文字，未确认] 球衣尺寸（长/宽）计算公式——根据身高/体重/性别/运动项目推算球衣面板尺寸，目的是让 duplicate_jersey_rows 将来能自动选对体型模板，而不是靠猜。用户口述较乱，已尽力整理成表格发给用户确认，但用户下线前未回复确认，下次 Session 必须先复述这份重建结果、拿到确认或修正后才能写入 jersey.py。

  **已重建、置信度较高**：
  - 排球·女：160cm/50kg → 长116/宽63；160cm/90kg(偏胖) → 长140/宽67；170cm → 宽68。宽度疑似规律"宽 = 63 + 0.5×(身高-160)"（165cm→65 与此吻合，但用户原话是"65cm 是65"，怀疑是"165cm"的口误)。
  - 排球·男：170cm→71，172cm→72，175cm→73，180cm→75（只有宽度，没有长度数据）。
  - 篮球·男：宽度 = 排球·男同身高宽度 + 2（175cm→75，180cm→77）。长度基准：平均60kg男≈118，即使40kg瘦子也不太往下降，下限约114~116。
  - override 规则：如果实际胸围明显大于身高/体重推算值，改用"长度=胸围+20"（例：160cm/55kg女正常应是长116，但胸围实测100 → 改用长120）。

  **待用户澄清（未重建出来，不能瞎猜）**：
  1. 排球·男的"长"怎么算？只给了宽度数据。
  2. 排球·女的"长"是否也随身高变化（像宽度一样），还是主要跟体重走？只有一个"正常体重"的数据点（160cm/50kg→116）。
  3. 原话里"divide 118 to 59, 75, add 7, becomes 82"这一段完全没理清是在算什么（另一个面板？袖子？还是别的尺寸），需要用户重新解释。
  4. 体重的调整是有具体规则（比如"超出该身高预期体重多少 kg，宽度/长度各加多少"），还是纯靠经验目测判断？

- [2026-09-06] **【紧急/未解决】20 件球衣的真实文件疑似丢失，需要下次 Session 第一件事确认**：文件全程未保存（未命名/无路径），本次会话后期发现 CorelDRAW 里只剩一个空白文档（Untitled-1，8 个形状），之前一直在操作的球衣文件（Untitled-3，1500×30733mm，220 个形状，含 20 件完整球衣）已不在 `Documents` 列表里。已确认 CorelDRAW 进程本身从会话开始到现在没有重启过（同一 PID），排除了崩溃重启的可能，说明是文档被主动关闭。已搜索 Corel 用户数据目录、Documents/Desktop/Downloads、Temp 目录，未找到任何 .cdr 备份/自动保存文件。**下次 Session 开始必须先问用户：文件是否还在（比如用户自己关闭后又开着别的窗口）；如果确认丢失，需要重新生成——好消息是现在有 `duplicate_jersey_rows` + `set_jersey_players`，重新做一遍 20 件球衣预计 1 分钟内，不需要再从头摸索。**
- [2026-09-06] [用户反馈] 照片识别球衣数据的完整工作流（用户明确要求，尚未开始设计/开发）：用户发一张尺码表/名单照片 → AI 提取姓名/号码/尺码到一个**可编辑表格**（用户先肉眼核对，纠正 AI 读错的地方，避免因为识别错误浪费面料）→ 确认无误后再问材质/面料型号、逐人确认性别标签（эрэгтэй/эмэгтэй，per 用户明确说"不要自己猜"）→ 全部确认后才开始批量生成。技术方向初步讨论：Streamlit 的 `st.data_editor` 是做"AI 填表、人工核对"这类场景的原生控件，适合用在这里。这是一个新功能，需要单独设计/排期，本次会话仅完成了它依赖的前置能力（图片理解本身），表格审核+材质/性别追问的具体交互流程还没设计。
- [2026-09-06] [待验证] 图片上传功能的浏览器真实文件选择路径未经人工验证：本次用 JS 脚本（构造 File 对象 + 派发 change 事件）模拟了文件上传来测试，Gemini 报错"Unable to process input image"，但同一张图片直接用 Python 调 API 测试是 100% 正确的——怀疑是 JS 模拟上传绕过了 Streamlit 真实的上传传输机制，导致服务器收到的字节损坏/不完整，不是代码本身的 bug。但这只是推测，需要用户在真实浏览器里手动点「上传文件」选一张真实图片测试，结果未知。

- [2026-09-05] [参考] Gemini 的 OpenAI 兼容接口已核实可作为 OpenRouter 免费额度打满时的备用视觉方案：base_url=`https://generativelanguage.googleapis.com/v1beta/openai/`，免费 Key 在 https://aistudio.google.com/apikey 申请（Google 官方文档核实，与 OpenRouter 账号完全独立、配额不共享）；消息格式与 OpenAI 的 `image_url`/base64 完全一致，runner.py 的 openai provider 不需要改代码就能接。免费档位是 Flash 系列，15 RPM/1500 RPD，具体哪个型号名称在免费档需要拿到真实 Key 后用类似今晚 OpenRouter 的方法实测确认（不能直接信文档示例里的型号名，要验证）；Pro 系列已从免费档移除。**用户已提供 Key，已存入 .env 的 GEMINI_API_KEY（未提交 git，.env 本身被忽略）**，尚未测试哪个型号真正可用/能看图，下次会话可直接用今晚 OpenRouter 用过的红色像素测试法验证。
- [2026-09-05] [用户反馈] CorelDRAW 侧边栏自定义 Docker（把 CorelChamp 做成原生停靠面板）——用户截图确认"Links and Rollovers"、"Sources"就是普通 Docker（在 Window > Dockers 勾选列表和右侧竖排图标栏里，与 Object Manager 同一套机制），证实了 SDK 里 DockerTemplateJS 模板的真实性。真要做需要单独的 C#/.NET SDK 插件项目（不是这个 Python/Streamlit 项目能直接扩展的），且旧版模板用的是 IE 旧引擎渲染（非确认过的 WebView2），现代 SDK 是否已升级还没查证。当前仅确认"可行"，未评估工作量，未立项。**环境核查（2026-09-05）：本机没有 .NET SDK、没有 Visual Studio、没有 CorelDRAW SDK（只有 CorelDRAW Technical Suite 25 这个应用本身），WebView2 运行时也未在预期注册表位置找到**——真要立项，光装 Visual Studio + 找到并下载 Corel 官方 SDK 就不是几分钟的事，用户曾要求"10分钟做完"，已明确告知不现实并说明真实工作量（装环境 → 找 SDK → 跑通最小 addon 加载 → 才轮到接 WebView），用户当时未确认是否要开始，待用户回复。


- [2026-09-05] [多文档并发] CorelDRAW 里同时开着多个文档时，`conn.app.ActiveDocument` 只指向"当前有焦点的那个"——本次会话中因为另一个 Streamlit 会话在测试"生成20件球衣"，切换了焦点文档，导致我这边的探测脚本一度以为真实文件"丢了"（实际是查到了另一个空白测试文档 Untitled-4）。后来发现 CorelDRAW 里同时开着 4 个文档（Untitled-1~4），真实文件（Untitled-3, 121 形状）安然无恙。未来任何"文档信息异常"排查，第一步应该是 `conn.app.Documents` 遍历确认真的在操作哪个文档，而不是假设 ActiveDocument 就是目标文件。是否要给 jersey.py 之类的工具加"按名称/路径指定文档"的参数，待评估。

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
  - **批量生成的正确做法（用户明确要求，第三轮才做对）**：不要逐元素现算尺寸/位置再创建，而是把参考件（面板+对位标记+队名+姓名+号码，共 9 个形状）**先 group 成一个整体**，之后每个人 = duplicate 整个 group（1 次调用，字体/样式/内部相对位置全部自动保留）→ 如需不同体型整体等比缩放（非等比会拉伸文字，避免）→ ungroup → 按"X 坐标分前后两侧、高度大小分队名/姓名 vs 号码"识别出 4 个文字子形状 → 只改 set_text_content，**不要重新 set_shape_size**（换内容后形状会沿用原有的缩放变换按新文字的自然比例渲染，宽度自动跟着变，不会拉伸；如果换成 set_shape_size 强制填满旧文字的宽高，短文字就会被拉伸——这正是之前号码显示过度拉伸的根因）。多位数号码只需极小幅度加宽（约 3%~5%）即可，不需要对齐到固定宽度
  - 排列顺序：参考件（如 MARTINEZ）算"第 1 人"，后续每个人依次往下排（即 Y 递减方向），彼此间距固定 **20mm**（用户最初口述 200mm，后明确改口纠正为 20mm——球衣与球衣之间只是留裁剪余量，不是视觉留白；与前后片之间的 17mm 间隙是两回事，不要混淆）
  - **面料代码标签**：用户会在 CorelDRAW 里手动放一个很小的文字（如"3016"，字号约 5mm 高）标注这批货用的面料型号，**正面和背面都要有**（不是只放背面）；批量生成时应从用户已放置的这一个示例复制到每个人的正面和背面面板，相对面板左上角的偏移量与用户范例保持一致。用户后续可能要求加第二行标注性别（如蒙古语"эрэгтэй"男/"эмэгтэй"女，用户按每个人实际情况口述提供，Agent 不要自己猜测/推断性别）
  - **已完成一轮批量测试**（2026-09-05，共三次尝试才做对）：基于用户手动完成的参考件（page 1），用上述 group-duplicate 方法生成了 10 个球员（3 童装、5 成人、2 大码，均为 Agent 编造的占位尺寸），已发截图给用户核对，尚未收到最终确认；真实生产还需要用户提供实际体型数据
  - 尚未正式过 DISCOVER/DESIGN 评审，仅做了原型验证（单件 + 10 人批量），未来若要产品化需要走完整流程并把此条从"待评估"移到"已规划"（建议届时把 create_artistic_text 工具的批量生成逻辑固化成 tools/jersey.py 之类的专用模块，而不是每次现写脚本）

- [2026-09-05] [用户反馈] 性能/成本优化方向讨论（三条，均未拍板，等用户回复先做哪个）：
  1) SignageAgent 简单任务路由到免费/轻量开源模型 — `agent/runner.py` 已有 `provider="openai"` + 自定义 `base_url` 机制（DeepSeek/千问同款接法），理论上可直接复用同一路径接入 Hermes 系模型；用户口头提到的"OpenClaw"不是已知的真实 API，疑似指 OpenRouter 或笔误，需用户提供真实文档链接/API base URL 才能接线，不能凭空猜测 URL。核心风险：开源模型的 function-calling 可靠性参差不齐（本 Agent 完全依赖工具调用驱动 CorelDRAW），换模型前必须先用真实多步工具调用任务测试，不能只看单轮问答效果
  2) 简单任务完全跳过 LLM、用规则/模式匹配直接调工具（省掉一次模型调用）— 仅讨论，未设计，需要先定义"简单任务"的判定标准
  3) `view_canvas`（截图 + 视觉模型）调用应降级为兜底手段：优先用已存在的 `get_document_info`/`list_all_text_shapes`/`check_text_overflow_all`/`check_rgb_colors`/`get_color_report`/`find_shape_by_name`/`get_layers` 等直接读取文档对象模型的工具，只在真正需要人眼审美判断（如排版是否顺眼）时才截图；这条是可直接采纳的调用习惯调整，不需要新代码

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
- [2026-09-05] **`set_page_size`／`page.SetSize()` 会围绕页面中心对称缩放，不是固定左下角原点**：页面变高变宽时，已存在形状的 ruler-relative 坐标（PositionX/Y）会整体偏移约 (新旧尺寸差)/2，而不是保持不变。这会导致"先记录坐标，再调整页面大小，再用旧坐标定位"的脚本全部错位（本次球衣批量生成因此错位过两次）。正确做法：**只在最开始 resize 一次到目标终尺寸**，然后立刻用 `find_shape_by_name` 重新读取关键参照形状的当前坐标作为后续计算基准，不要用 resize 前记录的坐标；同时页面若中途还要再调整尺寸，之前放置的内容坐标不会跟着变，会与新页面边界错位（表现为"内容跑到页面外，view_canvas 截图缺失部分行/列"）。
- [2026-09-05] **改文字内容后不要再调用 `set_shape_size` 强制指定宽高**：`duplicate_shape` 复制出的美术字形状带着原内容的缩放变换；`set_text_content` 换成新文字后，若不再动 size，新文字会按同一变换比例自然渲染出正确宽度（如"17"换成"3"，高度不变、宽度自动变窄，不会被拉伸）。如果换内容后又调用 `set_shape_size(旧宽,旧高)`，会把新文字强行拉伸/压缩到旧文字的包围盒尺寸，导致单字符号码看起来被过度拉伸——这是本次球衣批量生成中"数字被拉伸"问题的根本原因。多位数号码需要"稍微加宽"时，应在测量新内容实际自然宽度之后，只做一个很小幅度（如 3%~5%）的宽度微调，而不是对齐到某个固定值。
- [2026-09-05] **批量复制同一版式的正确模式：先 group 后 duplicate，不要逐元素重算**：把一份完整参考件（多个形状）先用 `group_shapes` 合并成一个 group，之后每份新记录只需 `duplicate_shape` 复制整个 group（自动保留所有形状的字体/样式/相对位置关系）+ 如需整体缩放就对 group 做等比 `set_shape_size` + `ungroup_shapes` 拆开 + 只替换文字内容的子形状。相比"对每个子形状分别 duplicate/测量/计算偏移"，这样调用次数少一个数量级，且不会因为手动累计偏移算错而错位。识别 ungroup 后的子形状可以用：X 坐标聚类分左右两侧、同一侧内用高度大小区分"标题类文字 vs 号码类文字"，不依赖形状名称（duplicate 出的子形状会保留原名称，多份副本会重名）。
- [2026-09-05] **人机协作场景下，删除/移动来源不明的形状前必须先问用户**：本次会话中 Agent 两次把用户手动在 CorelDRAW 里添加的参考标记误判为"孤立脏数据"并直接删除/覆盖，引发返工。CorelDRAW 里通常是用户和 Agent 交替甚至同时操作同一个文档，遇到无法从自己的操作历史解释来源的形状，应先展示给用户询问"这是什么，需要删除吗"，明确说明"如果是有意添加的（比如 logo、手工标记）留着就好"，而不是默认当作垃圾清理。
- [2026-09-05] **`select_shapes` 的 `by_type` 参数映射表有误**：`shapes.py` 的 `_TYPE_MAP` 把 `"text"` 映射到 CorelDRAW 类型码 3，但实际 CorelDRAW 里美术字/段落文字的 `Shape.Type` 是 6，类型码 3 对应的其实是直线/曲线（line/curve）。同样怀疑 `"bitmap":6` 也对不上。这导致 `select_shapes(by_type="text")` 实际筛选出的是线条而非文字，且没有报错（静默返回错误结果）。**临时规避方法**：不要用 `by_type` 参数筛选文字，改为拿全部形状（`select_shapes()` 不传 `by_type`）后自己在结果里过滤 `type==6`。这个映射表本身需要找机会systematic 核对修正。
- [2026-09-05] **[已修正] `set_text_style` 的 `char_spacing`/`line_spacing` 原本用 `> 0` 才生效的判断是真 bug，已修复**：`text.py` 原代码用 `float = 0` 做默认值、`if char_spacing > 0` 判断是否要改——但 CorelDRAW 真实的 `CharSpacing` 属性语义是"0 = 正常间距，正值 = 在正常间距基础上再加宽"，导致这个 API 从设计上就**只能加宽、永远无法收紧**，且无法显式重置回 0（传 0 会被当成"不修改"）。已改为 `Optional[float] = None` 作为"不修改"哨兵值（与 bold/italic/underline 参数风格一致），判断改为 `is not None`，允许显式传 0（重置为正常）或负数（收紧）。2+ 位数号码字符间距过松时，实测 `char_spacing=-15` 是紧凑但仍自然的良好值（-30 会显得过挤）；修改前必须重启 MCP Server 进程（代码改动不会热加载）。
- [2026-09-05] **重新居中文字时，基准必须是"所在面板的真实几何中心"，不能是"文字自己修改前的 center_x"**：批量给号码加 char_spacing 收紧间距后，为保持视觉居中会重新计算横坐标——错误做法是拿"这个文字形状自己原来的 center_x"当作目标中心去对齐（`new_x = old_center_x - new_width/2`），因为如果这个文字在更早的某一轮操作里就已经跑偏了，这样"居中"只是把错误的偏移原样保留、每次新一轮修改都在旧错误基础上继续对齐旧错误，误差不会被发现也不会被纠正。正确做法：先找到文字所在的面板矩形（按 Y 范围 + X 范围匹配），用 `面板.x + 面板.width/2` 算出面板的真实几何中心，再拿这个作为居中目标。批量改完任何位置/尺寸相关的操作后，应该用这种"对照面板真实中心"的方式扫一遍全部文字做校验，而不是想当然认为"我这次加了居中逻辑所以肯定居中了"。
- [2026-09-06] **红色 1x1 像素测试图会让所有视觉模型答错，不能用来下结论"某模型不能看图"**：之前用一张 1x1 纯红色像素 PNG 测试 minimax-m3:free 和多个 Gemini 型号做视觉问答，全部答错（一律说"Black"），一度以为是全行业视觉能力普遍不可靠。换成正常尺寸（200x200）的真实图片后，`gemini-3.1-flash-lite` 立刻答对，且能正确读出图片里的文字/数字（"23"、"175cm"）并结合内容直接调用工具——证明退化的极小测试图片本身会让模型的图像预处理管线失效、进而"瞎猜"一个常见颜色作为兜底答案，这是测试方法的系统性偏差，不是视觉能力的真实体现。以后测试任何模型的视觉能力，必须用正常尺寸（建议至少 100x100 以上）的图片，不能用 1x1 像素这类退化输入。**结论修正**：`minimax-m3:free` 确认不能可靠看图（正常尺寸图也失败），`gemini-3.1-flash-lite` 可以（通过 OpenAI 兼容层，base_url=https://generativelanguage.googleapis.com/v1beta/openai/，key 存在 .env 的 GEMINI_API_KEY）。
- [2026-09-06] **多 provider 场景下，API key 不能按固定顺序 fallback，必须按 base_url 匹配**：`runner.py` 原来的 `_resolve_api_key()` 不管 base_url 是什么，永远按 `OPENAI_API_KEY→DASHSCOPE→DEEPSEEK→OPENROUTER→GEMINI` 固定顺序取第一个存在的 key。一旦 .env 里同时配置了 OPENROUTER_API_KEY 和 GEMINI_API_KEY，想用 Gemini 时会因为 OPENROUTER_API_KEY 排在前面而被错误地发给 Gemini 的 endpoint，直接 400 拒绝。已修复为按 base_url 里的域名（openrouter.ai / generativelanguage.googleapis.com / deepseek.com / dashscope.aliyuncs.com）匹配对应的 key，匹配不到才退回固定顺序兜底。同时发现 `SignageAgent.__init__` 里 `self.api_key = api_key or self._resolve_api_key()` 原本写在 `self.base_url = base_url` **之前**，导致 `_resolve_api_key()` 内部读 `self.base_url` 永远是 None——这类"先用后赋值"的顺序错误在 `__init__` 里很隐蔽，加新逻辑时要检查依赖的属性是否已经赋值。
- [2026-09-06] **Gemini 的 OpenAI 兼容层要求 tool_calls 必须带 thought_signature 才能支持多轮工具调用**：调用 Gemini 生成的 tool_call 对象里有个 `extra_content.google.thought_signature` 字段，不是标准 OpenAI schema 的一部分。如果构造下一轮请求时回填 assistant 消息的 tool_calls 只保留标准字段（id/type/function）、丢了这个字段，Gemini 会在第二轮直接报 400："Function call is missing a thought_signature"。也就是说单轮"看图+调一次工具"能成功，但只要话轮想继续（比如工具结果需要模型再想一步），必挂。已在 `runner.py` 新增 `_tool_call_dict()` 统一处理，用 `getattr(tc, "extra_content", None)` 透传（其他 provider 没这个字段，不受影响）。这类"厂商私有扩展字段藏在 OpenAI 兼容层里"的坑，以后接入新的 OpenAI 兼容 provider 时要留意，不能假设都是纯标准 schema。
- [2026-09-06] **Streamlit 生成器里"error"事件之后必须 break，不能只 set 变量**：`app.py` 处理 `agent.run_single_stream()` 的事件流时，遇到 `type=="error"` 只设置了 `final_event = event` 但没有 `break`，而 `runner.py` 的生成器在 yield 完 "error" 事件后紧接着还会 yield 一个通用文案的 "final" 事件（"任务因错误终止"，不含具体原因）——外层循环继续跑下去，"final" 事件把 `final_event` 覆盖掉，真正有意义的错误信息（`event["error"]` 里的具体 API 报错）就永久丢失了，用户只能看到一句没有诊断价值的通用提示。已修复为 error 事件也立即 break。教训：消费一个"可能连续 yield 多个终止态事件"的生成器时，处理第一个终止事件后要立刻停止消费，不能假设后面不会有更多事件把它覆盖。
- [2026-09-05] **`OPENROUTER_API_KEY` 免费额度是按天限流的，没充值过的账号额度很小**：连续测试几个免费模型后触发 `Rate limit exceeded: free-models-per-day`，OpenRouter 官方错误信息原话是"Add 10 credits to unlock 1000 free model requests per day"——没充值过的账号每天能调用免费模型的次数很少（本次一晚上高强度测试就打满了），不是网络问题也不是代码 bug。以后要连续测试多个免费模型，要么分开几天测，要么提示用户先充值 $10（一次性，解锁每天 1000 次，不是消耗性的）。
- [2026-09-05] **CorelDRAW COM 的 `GetBoundingBox()` 不能当作 `PositionX/Y/SizeWidth/SizeHeight` 的性能替代品**：实测 GetBoundingBox() 单次调用比分别读 4 个属性快 3 倍（220 个形状：4.03s vs 1.33s），单个形状对照测试数值也完全一致，看起来是安全的优化——但在真实 20 件球衣文件上跑一遍后，好几个形状的居中偏移从 <0.1mm 错报成 200+mm。怀疑 GetBoundingBox() 对某些形状（可能是带描边/效果的）返回的是视觉包围盒而不是几何 Position/Size，两者不总是相等。**教训：COM 属性访问的性能优化必须在真实、有代表性的完整数据集上验证正确性，不能只用一两个形状抽查就下结论**——已在 jersey.py 的 `_collect()` 注释里记录，改回原始的分离属性读取方式。
- [2026-09-05] **球衣行与行之间的间距不是固定值，靠面板尺寸推算行间距会算错**：11 件球衣里混了至少两档体型（600×800mm 面板 和 750×1000mm 面板），不同体型面板高度不同，导致"锚点到锚点"的行间距在 622~944mm 之间浮动，不是一开始以为的固定 820mm。真正固定的是相邻两行"面板边缘到面板边缘"的留白 20mm（已向用户确认）。`duplicate_jersey_rows` 因此不能假设/校验"现有行间距必须一致"，而要用被复制行自身的真实高度（`_shape_y_extent` 量出的顶边/底边）+ 20mm 固定留白，从当前页面最高点往上一行一行推算新行位置。
- [2026-09-05] **批量创建型操作（复制新行）和批量编辑型操作（改内容）都要"先校验全部、再动手写"，不能边写边查**：`duplicate_jersey_rows` 和 `set_jersey_players` 早期版本都在循环里"边处理边校验"，如果处理到第 k 个才发现第 k+1 个不合法（行号超范围/间距算不出来/页面放不下），前面 k 个已经是真实调用了 COM 写入/复制，但函数整体返回失败——调用方看到"失败"，却不知道其实已经改了一部分。两个函数都已改成先把全部目标（行号、位置、内容）算完/校验完，全部通过才进入真正写入的循环。以后新增任何"批量"类型的 jersey 工具都要遵守这个模式。
- [2026-09-05] **免费模型会把工具返回的中文原文抄进英文回答里**：`list_all_text_shapes` 等工具的 `message` 字段是中文（如"第1页共 88 个文字形状"），即使系统提示词要求用英文回复，minimax-m3:free 有时会直接把这段中文摘抄进最终答案，读起来像是回答"坏掉"了。已在 `agent/prompts.py` 加了一条"工具结果里的中文只能转述、不能原样引用"的显式约束；这类问题只能在 Agent 层面缓解，treats 症状而非根因——根因是 `tools/` 目录下所有工具的 message 字段全是中文（项目既有约定），要根治得把面向用户展示的文案和面向开发者调试的文案分开，是更大的改动，本次未做。
- [2026-09-05] **`streamlit run` 默认监听 0.0.0.0，等于把"能操控 CorelDRAW 的聊天框 + 你的 API Key"暴露给整个局域网**：启动时会打印 Network URL / External URL，同网段任何人打开该地址就能直接下指令改设计文件、并消耗 .env 里的 API Key（UI 的 Key 输入框留空时用的就是服务器端的 .env）。给设计师用需要局域网访问是合理的，但要清楚这一点：默认没有任何认证。只给本机用应加 `--server.address 127.0.0.1`。
- [2026-09-05] **Streamlit 聊天框按 Enter 不发送，必须点右侧箭头按钮**：Enter 只是换行。第一次用的人会以为卡住了或没连上。
- [2026-09-05] **（观察，非结论）MCP Server 与 Streamlit 同时连 COM 本次未出现冲突**：README 记录过"Streamlit 无需同时启动 server.py，双 COM 会冲突"，但本次会话中 MCP Server 全程在跑，同时又跑了 6+ 次独立 Python 脚本连接和一次 Streamlit 连接，读写都正常。可能原始冲突另有具体触发条件（如同时写入同一形状）。**先不要据此改文档结论**，遇到 CorelDRAW 行为异常时仍应优先怀疑并关掉其中一个。
- [2026-09-05] **`list_all_text_shapes` 会把所有美术字误报成 `curve` 且 `writable:false`（真 bug，会误导 Agent）**：在真实球衣文件上实测，该工具返回"88 个文字形状，0 个可写入"、每个 text_type 都是 curve、content_preview 全空；但直接用 COM 逐个读 `Shape.Type` 得到的是 **6**（美术字），`Shape.Text.Story.Text` 也能正常读出 MARTINEZ/17 等真实内容，`set_text_content` 同样能正常写入。根因与已记录的 `select_shapes` by_type 映射表是同一类问题——代码里假设文字类型码是 3（`text.py:8 _CDR_TEXT_SHAPE = 3`、`shapes.py` 的 `_TYPE_MAP`），而 CorelDRAW 实际是 6，类型码 3 是直线/曲线。危害比 select_shapes 更大：Agent 看到"0 个可写入"会直接得出"这个文件的文字已经转曲、改不了"的错误结论而放弃操作。**判断文字是否可写不要信这个工具的 text_type/writable 字段，改为直接试读 `shape.Text.Story.Text`**（`text.py` 的 `_find_text_shape` 就是靠这个 duck-typing 兜底才一直没出错）。
- [2026-09-05] **形状名称在批量文件里会重复，且小标签会"冒用"正式名称**：球衣批量文件里每一行的 4 个文字都叫 REF_BACK_NAME/REF_BACK_NUM/REF_FRONT_NUM/REF_FRONT_TEAM，11 行完全重名，因此**只能靠 Y 坐标区分是哪一件**，不能靠名字定位。更隐蔽的坑：面料代码标签"3016"（约 30×10mm）里有一个也叫 `REF_BACK_NAME`（复制时沿用了原名），只按名字收集会导致 (1) 多识别出一件不存在的球衣、(2) 归行时按"最近的行"把它并进 OCONNOR 那一行并**覆盖掉那一行真正的姓名形状**，后果是改姓名改到了小标签上。`tools/jersey.py` 用"高度 ≥ 20mm"在收集阶段就排除这类小标签（真实球衣文字高 35~65mm，面料标签 10mm）。以后凡是按名字批量定位形状的代码都要考虑这两点。
- [2026-09-05] **Agent 单任务耗时的 85% 是 LLM 往返，不是 CorelDRAW**（2026-09-05 实测，OpenRouter + minimax-m3:free）：一个最简单的只读任务端到端 5.9s，其中 LLM 第 1 轮（决定调哪个工具）3.8s + LLM 第 2 轮（把结果写成一句话汇报）2.9s，而 CorelDRAW 真正执行只用 0.8s、工具注册+COM 连接只用 0.2s。含义：(1) 任何"让 Agent 更快"的努力如果只是换更快的模型，天花板很低——单次往返就要 2~7s，而一个任务最少需要两轮往返；(2) 想进入亚秒级只有一条路：可预测的简单任务直接走代码路径、完全不调 LLM；(3) 即使必须调 LLM，最后那轮"总结汇报给人看"的往返对机器任务是纯开销（~3s），批量场景里可以省掉。
- [2026-09-05] **未经用户同意不要"纠正"/替换用户自己写的占位文字**：用户在参考件里手打的队名是小写 "beards"，Agent 出于"这明显是想打 birds"的判断自作主张全部批量替换成大写 "BIRDS"，引发用户强烈不满（"do what it was at start... ask from me"）。哪怕看起来像是打字错误或口误，只要是用户在 CorelDRAW 里親手输入的内容，批量复制时应原样保留，需要修改必须先问，不能凭常识判断"用户应该是想要 X"就自行替换。

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
