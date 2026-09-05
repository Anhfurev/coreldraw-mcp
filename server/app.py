"""Streamlit Chat UI — CorelDRAW 调试对话框

启动: streamlit run server/app.py
"""

import base64
import sys
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# 读取 .env，侧边栏的 API Key 留空时即可回退到环境变量（与 server.py 行为一致）
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 确保 server/ 目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.runner import SignageAgent


st.set_page_config(page_title="CorelChamp", page_icon="🏆", layout="wide")

st.title("🏆 CorelChamp")
st.caption("Champ Sport CorelDRAW Jersey Automated AI — made by anhuush")
st.markdown(
    '<div style="height:4px;background:#00A651;border-radius:2px;margin:-8px 0 16px 0;'
    'width:120px;"></div>',
    unsafe_allow_html=True,
)

# Bot avatar: small green circular badge (data URI) so it reads as "CorelChamp", not a generic robot
_BOT_AVATAR_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<circle cx='32' cy='32' r='32' fill='%2300A651'/>"
    "<rect x='30' y='13' width='4' height='9' rx='2' fill='white'/>"
    "<circle cx='32' cy='11' r='3' fill='white'/>"
    "<rect x='17' y='23' width='30' height='21' rx='8' fill='white'/>"
    "<circle cx='25' cy='34' r='3.4' fill='%2300A651'/>"
    "<circle cx='39' cy='34' r='3.4' fill='%2300A651'/>"
    "</svg>"
)
BOT_AVATAR = "data:image/svg+xml," + _BOT_AVATAR_SVG
USER_AVATAR = "😎"


def _typewriter(text: str, delay: float = 0.015):
    """把已经拿到的完整回答按词分段 yield，配合 st.write_stream 做打字机效果——
    底层 API 调用本身不是流式的（一次性拿到完整结果），这里只是让呈现变顺滑，
    不是真的逐 token 流式（那需要改 runner.py 的 API 调用方式，是更大的改动）。"""
    words = text.split(" ")
    for i, w in enumerate(words):
        yield w + (" " if i < len(words) - 1 else "")
        time.sleep(delay)

# Chat bubbles: user on the right (green tint), assistant on the left (neutral) —
# Streamlit's default st.chat_message has no built-in side, so this targets its
# real DOM (data-testid) directly.
st.markdown(
    """
    <style>
    /* Custom (non-emoji-default) avatars drop Streamlit's stChatMessageAvatarUser/Assistant
       testid. Verified in the live DOM: the bot avatar renders as a bare <img> (SVG data URI,
       not wrapped in a div), the user avatar is plain emoji text — no <img> at all. Note: if a
       user-side photo-upload feature is added later, user messages may also contain <img> and
       this selector will need revisiting. */
    div[data-testid="stChatMessage"]:has(img) div[data-testid="stChatMessageContent"] {
        background: #E3F3E8;
        border-radius: 14px;
        padding: 10px 14px;
    }
    div[data-testid="stChatMessage"]:not(:has(img)) {
        flex-direction: row-reverse;
    }
    div[data-testid="stChatMessage"]:not(:has(img)) div[data-testid="stChatMessageContent"] {
        background: #C9EBD3;
        border-radius: 14px;
        padding: 10px 14px;
        text-align: right;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# 初始化 session state — OpenRouter/minimax-m3:free анхны тохиргоогоор
# =============================================================================

if "agent" not in st.session_state:
    st.session_state.agent = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "connected" not in st.session_state:
    st.session_state.connected = False
if "provider" not in st.session_state:
    st.session_state.provider = "openai"
if "base_url" not in st.session_state:
    st.session_state.base_url = "https://openrouter.ai/api/v1"
if "model" not in st.session_state:
    st.session_state.model = "minimax/minimax-m3:free"
if "api_key" not in st.session_state:
    st.session_state.api_key = ""

# Анх ачаалахад .env-ийн key-ээр автоматаар холбогдож үзнэ — хэрэглэгч Provider/URL/Model
# гараар бичих шаардлагагүй, дэлгэрэнгүй тохиргоог хажуу самбарт нээж болно.
if not st.session_state.connected and not st.session_state.get("auto_connect_tried"):
    st.session_state.auto_connect_tried = True
    try:
        st.session_state.agent = SignageAgent(
            provider=st.session_state.provider,
            model=st.session_state.model,
            base_url=st.session_state.base_url or None,
        )
        st.session_state.connected = True
    except Exception:
        pass  # API key олдоогүй эсвэл холбогдож чадаагүй — хажуу самбараас гараар оруулна

# =============================================================================
# Хажуу самбар — Загварын тохиргоо
# =============================================================================

with st.sidebar:
    st.header("⚙️ Загварын тохиргоо")

    if st.session_state.connected:
        st.success(f"✅ {st.session_state.model}")
    else:
        st.warning("Холбогдоогүй байна")

    with st.expander("Дэлгэрэнгүй тохиргоо", expanded=not st.session_state.connected):
        provider = st.selectbox(
            "Provider",
            ["anthropic", "openai"],
            index=["anthropic", "openai"].index(st.session_state.provider),
            help="Anthropic = Claude цуврал; OpenAI-тэй нийцэх = DeepSeek / Qwen / OpenRouter гэх мэт",
        )

        if provider == "openai":
            base_url = st.text_input(
                "API Base URL",
                value=st.session_state.base_url,
                placeholder="https://openrouter.ai/api/v1",
                help="DeepSeek: api.deepseek.com | Qwen: dashscope.aliyuncs.com/compatible-mode/v1 | "
                     "OpenRouter: openrouter.ai/api/v1",
            )
            default_model = "deepseek-chat"
        else:
            base_url = ""
            default_model = "claude-sonnet-4-5-20250929"

        model = st.text_input("Model", value=st.session_state.model or default_model)

        api_key = st.text_input(
            "API Key",
            type="password",
            value=st.session_state.api_key,
            help="Anthropic нь ANTHROPIC_API_KEY-г, OpenAI-тэй нийцэх нь OPENAI_API_KEY / "
                 "DASHSCOPE_API_KEY / OPENROUTER_API_KEY-г .env-ээс уншина; хоосон орхиж болно",
        )

        if st.button("🔗 Холбох", use_container_width=True, type="primary"):
            try:
                st.session_state.agent = SignageAgent(
                    provider=provider,
                    model=model,
                    api_key=api_key or None,
                    base_url=base_url or None,
                )
                st.session_state.provider = provider
                st.session_state.model = model
                st.session_state.api_key = api_key
                st.session_state.base_url = base_url
                st.session_state.connected = True
                st.success(f"{model} холбогдлоо")
            except Exception as e:
                st.error(f"Холболт амжилтгүй боллоо: {e}")
                st.session_state.connected = False

    if st.button("🗑️ Ярианы түүх цэвэрлэх", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# =============================================================================
# 渲染历史消息
# =============================================================================

for msg in st.session_state.messages:
    role = msg["role"]

    if role == "separator":
        st.divider()

    elif role == "reasoning":
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            with st.expander("🧠 Reasoning", expanded=False):
                st.markdown(msg["content"])

    elif role == "tool_call":
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            with st.expander(f"🔧 {msg['name']}", expanded=False):
                cols = st.columns(2)
                with cols[0]:
                    st.caption("Parameters")
                    st.json(msg.get("input", {}))
                with cols[1]:
                    st.caption("Result")
                    result = msg.get("result", {})
                    if isinstance(result, dict):
                        st.json(result)

    elif role == "preview":
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            st.image(
                f"data:image/png;base64,{msg['base64']}",
                caption=msg.get("path", "Preview"),
                width=400,
            )

    elif role in ("assistant", "user"):
        with st.chat_message(role, avatar=BOT_AVATAR if role == "assistant" else USER_AVATAR):
            st.markdown(msg["content"])

    elif role == "error":
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            st.error(msg["content"])

# =============================================================================
# 用户输入与 Agent 执行
# =============================================================================

if prompt := st.chat_input("Анхууштай чатлах…"):
    if not st.session_state.connected or st.session_state.agent is None:
        st.error("Эхлээд зүүн талын хажуу самбар дээр загвараа тохируулж «🔗 Холбох» товчийг дарна уу")
        st.stop()

    # 展示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    agent: SignageAgent = st.session_state.agent

    # 运行 Agent，实时渲染事件 —— 思考/工具调用放进可折叠的 status（真正的"加载中"效果），
    # 最终答案作为普通聊天气泡显示在 status 外面，不再用一整块绿色 success 框包住回答
    with st.chat_message("assistant", avatar=BOT_AVATAR):
        tool_results_buffer = {}
        final_text = ""
        final_event = None

        with st.status("Thinking…", expanded=True) as status:
            for event in agent.run_single_stream(prompt):
                etype = event["type"]

                if etype == "thinking":
                    status.update(label="🤔 Thinking…", state="running")

                elif etype == "reasoning":
                    st.markdown(event["content"])
                    st.session_state.messages.append({"role": "reasoning", "content": event["content"]})

                elif etype == "text":
                    final_text = event["content"]

                elif etype == "tool_call":
                    name = event["name"]
                    inp = event["input"]
                    status.update(label=f"🔧 Calling tool: {name}", state="running")
                    tool_results_buffer[name] = {"input": inp, "result": None}

                elif etype == "tool_result":
                    name = event["name"]
                    result = event["result"]
                    inp = tool_results_buffer.get(name, {}).get("input", {})

                    with st.expander(f"🔧 {name}", expanded=False):
                        cols = st.columns(2)
                        with cols[0]:
                            st.caption("Parameters")
                            st.json(inp)
                        with cols[1]:
                            st.caption("Result")
                            st.json(result)

                    st.session_state.messages.append({
                        "role": "tool_call", "name": name,
                        "input": inp, "result": result,
                    })

                elif etype == "preview":
                    st.image(
                        f"data:image/png;base64,{event['base64']}",
                        caption=event.get("path", "Preview"),
                        width=400,
                    )
                    st.session_state.messages.append({
                        "role": "preview", "base64": event["base64"],
                        "path": event.get("path", ""),
                    })

                elif etype == "error":
                    status.update(label="❌ Error", state="error")
                    final_event = event

                elif etype == "final":
                    status.update(label="✅ Done" if event["success"] else "❌ Failed",
                                   state="complete" if event["success"] else "error")
                    final_event = event
                    break

        # 真正的回答内容 —— 普通聊天气泡，只有失败时才用红色错误框
        if final_event and final_event["type"] == "error":
            st.error(final_event["error"])
            st.session_state.messages.append({"role": "error", "content": final_event["error"]})
        elif final_event and final_event["success"]:
            text = final_text or final_event["message"]
            st.write_stream(_typewriter(text))
            st.caption(f"Total {final_event['turns']} turns, {final_event['tool_calls']} tool calls")
            st.session_state.messages.append({"role": "assistant", "content": text})
        elif final_event:
            msg = f"❌ {final_event['message']}"
            st.error(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})
