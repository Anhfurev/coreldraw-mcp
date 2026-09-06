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

[2026-09-06 14:15] FIX "Start Jersey" 曾硬编码 source_row=1，改成先检测再选：用户要求"每次都要先从头检测已有的对象，确认后再直接在那个模板上操作"。之前 duplicate_jersey_rows(source_row=1,...) 完全不看文档里实际有什么，只assumed"第1行"是模板——当天文档里同时有假占位模板和用户真实红色球衣时，第1行正好是假的，点 Start Jersey 会用错模板。已加一个下拉框，先跑 scan_jersey_rows() 把实际检测到的每一行（团队/姓名/号码）列出来让用户确认/选择，duplicate_jersey_rows 改用选中的 source_row。同一时段用户自己把之前 Agent 建的 48 个占位形状手动删了，文档现在只剩真实球衣（8 形状，scan 正确报 1 行）。已用独立浏览器测试对真实文档验证检测结果正确。
[2026-09-06 14:10] FIX 核对表 length_cm/width_cm 改成真正的蓝色文字（原来只在表头加🔵图标，用户明确指出这不是他要的）：st.data_editor 本身画在 canvas 上没法给单元格上色，改为在可编辑表格下方加一个只读的 pandas Styler 预览表，length/width 两列用真蓝色（#1a73e8）文字渲染，已用独立浏览器测试截图确认生效（commit 待定，见下方）。同一时段发现更关键的问题：用户此前抱怨"为什么不从我准备好的红色球衣开始"，排查后发现那件红色球衣其实一直在同一个 Untitled-1 文档里（左侧、负 X 坐标），只是 4 个文字对象从未改名成 REF_* 系列，导致 scan_jersey_rows 完全找不到它——Agent 之前误判文档是空的，还在同一文档另建了一套假占位模板（TEAM/NAME 假数据 48 个形状）。已把红色球衣的 4 个文字改名归位（已验证 scan_jersey_rows 能正确识别、居中偏移 0.0），假占位模板暂未删除（批量删除形状被 auto-mode 拦截，已问用户确认，等回复）。详见 backlog.md 已知约束区两条新记录。
[2026-09-06 13:40] DONE 核对表列顺序改成 name/number/length/width/height/weight/chest + 长宽列标题加🔵标记（commit 08cd42e）。查证确认 st.data_editor 是 canvas 渲染表格，CSS 无法像聊天气泡那样精确到单元格，NumberColumn 参数里也没有 background/color 选项（inspect.signature 核实），因此"格子背景变蓝"的原始要求无法实现，用标题图标做了替代方案并如实告知限制。已用独立测试脚本+真实浏览器验证列顺序和标记正确渲染。仍未做真实CorelDRAW端到端测试（无球衣文件）。
[2026-09-06 13:30] FIX 核对表空白格子编辑不了的问题（commit b44ce31）：用户反馈"write on empty...not available"。根因：width_cm/length_cm用""表示未算出、算出后又变数字，同列string+number混用；height_cm/weight_kg/chest_cm从AI提取出来后一直是字符串从未转数字——都容易导致st.data_editor自动推断列类型出错、格子编辑不了。改为统一用None表示空、AI提取时立刻转成真正的float，并给data_editor加显式column_config（TextColumn/NumberColumn）不依赖自动推断。已用独立最小复现脚本在真实浏览器验证：空的length_cm和name格子都能正常双击编辑并保存。这个bug修复后，之前已建好的"修正记录会越用越准"的学习循环现在才能真正跑起来（之前编辑不了，用户根本存不进修正）。仍未做真实CorelDRAW端到端测试（无球衣文件）。
[2026-09-06 13:15] FIX 长度查找从严格容差匹配改成同身高数据点间插值（commit d166060）：用户反馈"很多长度都出不来"——上次刚去掉胸围兜底（正确），但当时的容差(±1.5cm/±3kg)太窄，配上目前只有169/170/164cm几个身高的种子数据，稍微偏离体重就查不到、显示空白。改成按身高±3cm筛出真实数据点后按体重线性插值（区间内插值，单侧数据外推到最近点，插值结果强制取偶数），真正无覆盖的身高（如200cm）仍正确返回空而非编造。已用6组用例验证（区间插值/双向外推/跨身高聚簇优先更近的/真正无覆盖）。核对表持续使用会不断把手动修正存进corrections文件，覆盖率会越来越好。仍未做真实CorelDRAW端到端测试（无球衣文件）。
[2026-09-06 13:05] FIX 修复长度计算的真 bug（commit 1d34537）：用户报"164cm/66kg 得到100"，排查确认是 _compute_jersey_length 的胸围兜底分支（查不到身高体重修正就退回胸围+20）在作怪——之前只种了169-170cm的修正数据，164cm超出容差，每次都悄悄退到胸围公式，与用户"胸围只在明显偏大时才该用"的要求矛盾。已彻底删除胸围自动兜底，长度现在只从修正记录查，查不到就是空，绝不再编数字。种入新数据：169cm/62kg→118（延续60-64kg档位），164cm/66kg→122（新身高点）。顺手把变孤儿的 _round_to_even 改造成"保存核对表时校验长度必须是偶数，奇数自动纠正并提示"。已用4组用例验证（含一个完全未覆盖的组合，确认正确返回空而非编造值）。仍未做真实 CorelDRAW 端到端测试（无球衣文件）。
[2026-09-06 12:55] DONE 面料标签写入 + 表格改进 + 修正一个真 bug（commit 9278750）：(1) jersey.py 新增 set_jersey_material(rows, material)，按 Type==6+高度<20mm 识别面料标签（"3016"那类），写入用户输入的材质，已注册进 server.py；(2) app.py 核对表加材质输入框（Start Jersey 前必填）+ column_order 把宽/长挪到身高/体重前面方便对比；(3) 把用户新给的尺寸数据（170cm/50kg→112，169cm 各体重段）直接种进 jersey_size_corrections.jsonl，不用等用户重新在表格里填。过程中用独立脚本验证种子数据时发现 _lookup_correction 真 bug——原来是"文件里最后一条匹配的赢"而非"最近的赢"，169cm/54kg 精确命中却被更晚写入但差2.5kg的记录覆盖，已改成按距离选最近的并重新验证 6 组用例全部通过。**仍未端到端测试**——CorelDRAW 里没有球衣文件，"Start Jersey"和材质标签写入都还没有真实验证过。
[2026-09-06 12:45] FIX 按钮文案改回英文"Start Jersey"（commit c9075e4）——用户之前明确要求过英文，上次误改成蒙古语「Джерси эхлүүлэх」，用户点名纠正。教训：不是所有 UI 文案都要蒙古语化，要按用户对具体元素的明确要求来，不能自作主张统一语言风格。
[2026-09-06 12:40] DONE 尺寸修正持久化学习（commit 5424823）：用户手动改的宽/长会自动存进 server/data/jersey_size_corrections.jsonl（故意不 gitignore，是真实业务数据），下次遇到相近身高(±1.5cm)/体重(±3kg)/同性别同项目会优先用存档值而不是公式，公式本来是空的格子（如排球男的长）只要用户填过一次，以后也会被记住。已用独立脚本验证匹配容差逻辑正确（精确/临近命中，超范围或性别项目不符正确返回空）。这个功能同时也是"逐步攒够数据、以后能把公式补完整"的路径，不需要每次都重新问用户。
[2026-09-06 12:30] DISCOVER 用户补充了排球女 169cm 下长度随体重分段的数据（48-52kg→112, 53-55kg→114, 55-58kg→116，每约3kg跳增2，符合偶数规则），已记入 backlog.md。发现与此前"170cm/50kg→114"疑似矛盾（169cm/~50kg→112，1cm身高差却2单位长度差），已提请用户下次确认是否为口误。公式仍未收敛，未写入代码。
[2026-09-06 12:20] DONE 核对表改造两处（commit 50adfb6, 6a5c8ee）：(1) 长度值强制取最近偶数（用户新规则：111/117 这类奇数不行，因为要除以2），只影响 length，不影响 width（已确认宽度里本来就有 63/71/73/75/77 等奇数，注释里写清楚了区分依据）；(2) 核对表从"更新已有行"模式改成"生成新球衣"模式——去掉手动填起始行号，改为按人数自动 duplicate_jersey_rows+set_jersey_players；按钮文案改"🏐 Джерси эхлүүлэх"；性别下拉框改蒙古语标签 эрэгтэй/эмэгтэй。用户反馈"面料提问没出现"，已用真实图片+完整76工具Agent链路复现测试但未能复现该问题，需要用户下次提供出问题时的实际AI回复内容。**新的"生成新球衣"按钮本次未能端到端测试**——CorelDRAW 目前只有空白 Untitled-1，没有球衣模板可供 duplicate_jersey_rows 复制，仍卡在"20件球衣文件疑似丢失"这个未解决问题上（backlog.md 第一条），用户尚未答复是否重建。
[2026-09-06 12:05] DONE 实现球衣宽度计算（commit 362840e），只实现有确凿数据点支撑的部分：排球男女、篮球男的宽度公式（8/8 用户举例全部验证通过），以及胸围→长度的唯一明确规则（长=胸围+20）。所有"身高/体重→长度"的情况故意留空——用户口述的数据点不足以归纳出公式，编造会真实浪费面料。extraction 提示词加了 height_cm/weight_kg/chest_cm 字段，模型看不出项目/性别时会主动反问（不猜）。核对表加了 运动/性别 下拉 + 一键重算按钮。已用真实图片走通整条链路验证（正确读出号码+身高，正确反问项目/性别+面料）。宽/长目前只是给用户看的参考数值，还没接到 CorelDRAW 面板缩放逻辑（那是更大的后续工作，且 backlog.md 里还有 4 个未解决的公式空白待用户澄清：排球男的长、排球女长随身高的变化、"82"那段计算、体重调整是否有具体规则）。
[2026-09-06 11:50] DISCOVER 用户口述了球衣尺寸（长/宽）随身高/体重/性别/项目变化的计算逻辑（排球男女、篮球男，含胸围override规则），语音转文字内容较乱，已尽力整理成表格+4个待澄清问题写入 backlog.md，发给用户确认但未等到回复。下次 Session 开始必须先处理：(1) 20件球衣文件疑似丢失待确认，(2) 这份尺寸公式待用户确认/补充，两者都在 backlog.md 待评估区最前面。
[2026-09-06 11:35] FIX 每张图片默认当作球衣名单/尺码数据处理，回答里强制追问面料（commit 250bd20）：用户明确要求"发图片永远当成人的尺码数据"+"问一下面料就完事"。已用真实图片验证：正确读出号码，追问了面料，JSON 数据块照常输出。至此"拍照→表格核对→追问面料"链路的 AI 侧行为已完整实现并验证；仍未验证的只剩浏览器真实文件选择（用户尚未反馈用真实图片测试的结果）。
[2026-09-06 11:30] BLOCKED ⚠️ 20 件球衣的球衣文件（Untitled-3）疑似丢失——检查 CorelDRAW 时发现只剩一个空白 Untitled-1，进程本身没重启过（同一 PID），说明文档被关闭而非崩溃；已搜索所有常见备份/自动保存位置均无结果。同时完成了图片核对表功能（commit b53a72a）：视觉 Agent 现在会额外输出 JSON 数据块，app.py 解析后渲染成 st.data_editor 可编辑表格，配三个按钮（预览/写入/取消），写入前用户可以先纠正 AI 读错的姓名号码。此功能本身代码已验证（JSON 解析单测通过），但完整"拍照→表格→写入"链路因同样的模拟上传局限未能端到端跑通。**下次 Session 必须先处理文件疑似丢失的问题，再继续新功能**，详见 backlog.md 待评估区第一条。
[2026-09-06 11:10] FIX 图片消息自动路由到 Gemini（commit 6a07817）：用户反馈侧边栏连着 minimax-m3:free 时上传图片仍发给它处理（该模型已确认不能可靠识别图片）。原实现只是"按当前 provider 拼图片格式"，但调用的还是 session_state.agent——如果连的是不支持视觉的模型，图片照样发过去。改为图片消息一律走单独缓存的 Gemini 实例（session_state._vision_agent，用 GEMINI_API_KEY），文字消息不受影响、继续用主聊天连的模型。已验证：侧边栏仍显示 minimax-m3:free 的情况下发图片，报错信息明确来自 Gemini（developers.generativeai.google 域名），证明路由生效。图片本身因用 JS 模拟上传（非真实文件选择）导致 Gemini 报"Unable to process input image"，这是已知的测试方法局限（见 backlog.md），已让用户用真实图片手动验证，结果待用户反馈。
[2026-09-06 10:55] DONE 新增 watch_coreldraw.py + 注册进 Windows Startup（commit f9f8b83），实现"CorelDRAW 打开自动拉起 MCP Server+CorelChamp，关闭自动停止"，用户以后无需手动启动任何东西。过程中定位两个真 bug：(1) pythonw.exe 无控制台运行时 sys.stdout/stderr 是 None 而非受限流，reconfigure()/print() 会在第一行就崩溃且无痕迹——改为 None 时重定向到 watch_coreldraw.log；(2) 进程名大小写误写（CorelDrw.exe vs 真实的 CorelDRW.exe）导致 Python 端大小写敏感比较永远匹配失败，tasklist 命令本身不区分大小写掩盖了问题。验证方式：多次用 .bat+cmd.exe 测试出现假阴性（本环境 shell 对含西里尔字母路径的处理不稳定，与改动本身无关），改用 subprocess.Popen(creationflags=DETACHED_PROCESS) 直接复现"无控制台启动"场景后才定位到真因。另外发现本 session 恢复时 MCP Server/Streamlit 进程都已不在（上次 session 结束时被清理），已重启两者验证 CorelDRAW 连接、Gemini 视觉、球衣数据全部正常。
[2026-09-06 00:35] DONE Gemini vision 接入 + 修复三个真实 bug（commit 2206407）：(1) api_key 解析改按 base_url 匹配对应服务，不再是固定顺序 fallback（同时配置多个 provider key 时会把错误的 key 发给错误的服务）；(2) 新增 _tool_call_dict() 透传 Gemini 的 thought_signature（藏在 extra_content.google 里，不透传会导致多轮工具调用第二轮必定 400）；(3) 修复 app.py 里"error"事件不 break 导致被后续"final"事件覆盖、真实报错信息丢失的 bug。app.py 加了 st.chat_input(accept_file=True) 图片上传支持。**关键实证**：之前用 1x1 红色像素测试图让所有模型（含 minimax-m3:free 和多个 Gemini 型号）都答错"Black"，一度以为视觉能力普遍不可靠；换成 200x200 正常尺寸图片后 gemini-3.1-flash-lite 立刻答对且能读出图中数字并结合内容调工具，minimax-m3:free 仍答错——证明退化测试图会让模型视觉管线失效、不是视觉能力的真实体现，同时确认 gemini-3.1-flash-lite 是可用的视觉方案。**未完全验证**：浏览器真实文件选择路径（用 JS 模拟上传测试报错"Unable to process input image"，怀疑是模拟上传本身的问题不是代码 bug，需要用户手动上传真实图片验证，结果未知）。用户提出下一步要做"AI 提取数据到可编辑表格供人工核对+追问材质/性别标签"的完整工作流，尚未设计，记入 backlog.md 待评估区。
[2026-09-05 23:45] VERIFY 回答用户三个问题并各有实证：(1) 免费模型能否识别照片——不能，且当晚测试已把 OPENROUTER_API_KEY 的免费额度打满（真实 API 报错 free-models-per-day 限流），确认了 OpenRouter 免费额度是按天限流、没充值的账号额度很小；(2) CorelDRAW 侧边栏能否放自定义 Docker——用户截图证实"Links and Rollovers"/"Sources"就是普通 Docker（与 Object Manager 同机制），确认可行但需要独立 C#/.NET SDK 插件项目；(3) COM 调用能否再提速——实测发现 GetBoundingBox() 比分离读 4 个属性快 3 倍，但应用到 jersey.py 后在真实 20 件球衣文件上跑出错误结果（居中偏移从 <0.1mm 错报成 200+mm，怀疑视觉包围盒与几何 Position/Size 不等价），已回滚（commit ee1949e）并在代码注释里记录教训。三条发现均写入 backlog.md 已知约束/待评估区。
[2026-09-05 23:20] DONE 新增 duplicate_jersey_rows（commit 98feee3），彻底解决"20件球衣靠 AI 一步步做太慢"：不经 LLM 复制整件球衣（11 个形状/行，按 Y 坐标识别，不靠名称），行间距按被复制行的真实高度 + 固定 20mm 留白动态推算（不是假设均匀）。已在真实生产文件上从 11 件扩到 20 件全部验证通过（新建 9 件 + 批量填姓名号码），总耗时约 35~40 秒，对比之前 AI 逐步生成同样任务跑满 30 轮仍失败。过程中：(1) 发现该文件混了 600×800/750×1000 两档体型面板，行间距原来就不是固定 820mm，是我最初的错误假设；(2) 修了两处"先写后查导致部分写入却报整体失败"的校验时机 bug（duplicate_jersey_rows 和 set_jersey_players 都改成先全部校验再写）；(3) 期间因另一 Streamlit 会话同时在测试同一文档，一度以为文件"丢了"，确认是 CorelDRAW 同时开了 4 个文档、焦点切走了，真实文件安然无恙——再次印证多会话并发编辑同一文档的风险是真实存在的，不是假设。同时提交 CorelChamp UI 改版（commit f06dea4）：头像+左右分栏+st.status 进度折叠+打字机效果+统一绿色调+免手动连接（默认 OpenRouter/minimax-m3:free）。详见 backlog.md 已知约束区三条新记录。
[2026-09-05 21:15] VERIFY 端到端验证 Way 2（Streamlit + OpenRouter 免费模型聊天框）：装好 streamlit 后用浏览器实操启动 app.py，配置 provider=openai/base_url=openrouter/model=minimax-m3:free 并连接成功；发只读提问"现在文档里有多少个形状"，模型正确调用 get_document_info 并如实汇报 121 个形状、未做修改，2 轮 1 次工具调用。UI 侧发现两个可用性问题（已记入 backlog）：(1) 回车不发送、必须点箭头按钮，第一次用容易以为卡住；(2) `streamlit run` 默认监听 0.0.0.0，把"能操控 CorelDRAW 的聊天框 + .env 里的 API Key"暴露给整个局域网，无任何认证。另外记录一条观察：本次 MCP Server 全程在跑的同时又开了 Streamlit 连 COM，多次读写均未出现 README 里记录的"双 COM 冲突"，暂不确定原冲突的具体触发条件，未改动相关文档结论。**用户文档仍未保存**（未命名/无路径，121 个形状全在内存里），已提醒用户但未代为保存。
[2026-09-05 20:55] DONE 交付三条使用路径并固化其中两条（commit 58fc712）：(1) `jersey_batch.py`（项目根目录）——设计师改 PLAYERS 列表即可批量改名改号，默认 DRY_RUN 只预览，运行时先列出全部球衣及居中偏移（可代替截图核查），实测在真实文件上列出 11 件、最大偏移 0.04mm；这是重复性工作应该走的路径，不调 LLM、无成本、0.26s/件。(2) `app.py` 补上 load_dotenv（此前全项目只有 server.py 加载 .env，Streamlit UI 每次都得手动粘贴 API Key，现在留空即可回退到 .env）。Streamlit 本身当时仍在后台安装（依赖树大），装完后 `streamlit run server/app.py` 侧边栏填 provider=openai / base_url=https://openrouter.ai/api/v1 / model=minimax/minimax-m3:free 即可用自己的免费模型对话。**注意 Streamlit 与 MCP Server 不能同时开**（双 COM 冲突，已有记录）。
[2026-09-05 20:30] DONE 新增 tools/jersey.py 球衣确定性快速路径（commit 4887360，不经 LLM）：scan_jersey_rows 用数据代替截图核查（返回每件的姓名/号码/队名 + 相对面板真实几何中心的偏移量），set_jersey_player/set_jersey_players 一次调用改完背面姓名+两个号码。实测 11 件批量 dry-run 2.9s（0.26s/件），逐个调用约 2s/件（每次都要重扫整页）；真实写入已在生产文档上验证非破坏性（文字/字体/字号/宽高全不变，仅 x 因重新居中动了 0.01mm）。过程中发现两个真 bug 并写入 backlog 已知约束：(1) **list_all_text_shapes 把所有美术字误报成 curve/不可写**（实际 Shape.Type=6，能正常读写）——会让 Agent 误以为文件已转曲而放弃；(2) 面料标签"3016"冒用了 REF_BACK_NAME 名字，只按名字收集会多出一件球衣且覆盖掉 OCONNOR 那行真正的姓名形状。注意：server.py 的注册改动尚未 commit（该文件同时携带前几次 session 遗留的 vision/create_artistic_text 等未提交改动，不便代为提交）；新工具需重启 MCP Server 才可见 → 详见 sessions/2026-09-05-2030.md
[2026-09-05 19:50] DONE OpenRouter 接入完成并实测通过（commit 8e45eca）：runner.py 的 key 解析链加入 OPENROUTER_API_KEY、requirements.txt 补声明 openai（此前 openai provider 分支的依赖从未声明、venv 里没装）。`minimax/minimax-m3:free` 免费模型 function-calling 完全可用，含单轮并行多工具调用；完整 Agent 驱动真实 CorelDRAW 只读任务 5.9s 成功。**关键实测数据**：这 5.9s 里 LLM 占 ~85%（两轮往返 3.8s + 2.9s），CorelDRAW 实际执行仅 0.8s，工具注册+COM 连接 0.2s —— 证明"5 秒目标"靠换模型达不到（单次往返 2~7s、一个任务至少两轮），必须靠简单任务跳过 LLM 走代码直接路径 → 详见 sessions/2026-09-05-1950.md
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
