"""Streamlit Chat UI — CorelDRAW 调试对话框

启动: streamlit run server/app.py
"""

import sys
from pathlib import Path

import streamlit as st

# 确保 server/ 目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.runner import SignageAgent


st.set_page_config(page_title="CorelDRAW 调试", page_icon="🏗️", layout="wide")

st.title("🏗️ CorelDRAW 调试")
st.caption("用自然语言操控 CorelDRAW，自动生成门牌、导向标识等设计文件")

# =============================================================================
# 侧边栏 — 模型配置
# =============================================================================

with st.sidebar:
    st.header("⚙️ 模型配置")

    provider = st.selectbox(
        "Provider",
        ["anthropic", "openai"],
        index=0,
        help="Anthropic = Claude 系列；OpenAI 兼容 = DeepSeek / Qwen / 通义千问等",
    )

    if provider == "openai":
        base_url = st.text_input(
            "API Base URL",
            value=st.session_state.get("base_url", ""),
            placeholder="https://api.deepseek.com",
            help="DeepSeek: api.deepseek.com | 千问: dashscope.aliyuncs.com/compatible-mode/v1",
        )
        default_model = "deepseek-chat"
    else:
        base_url = ""
        default_model = "claude-sonnet-4-5-20250929"

    model = st.text_input("Model", value=st.session_state.get("model", default_model))

    api_key = st.text_input(
        "API Key",
        type="password",
        value=st.session_state.get("api_key", ""),
        help=f"Anthropic 默认读 ANTHROPIC_API_KEY；OpenAI 兼容读 OPENAI_API_KEY / DASHSCOPE_API_KEY",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔗 连接", use_container_width=True):
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
                st.success(f"已连接 {model}")
            except Exception as e:
                st.error(f"连接失败: {e}")
                st.session_state.connected = False
    with col2:
        if st.button("🗑️ 清空对话", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    if st.session_state.get("connected"):
        st.success(f"✅ {st.session_state.get('model', '')}")

    st.divider()
    st.caption("提示：首次使用需先点「🔗 连接」初始化 Agent")

# =============================================================================
# 初始化 session state
# =============================================================================

if "agent" not in st.session_state:
    st.session_state.agent = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "connected" not in st.session_state:
    st.session_state.connected = False

# =============================================================================
# 渲染历史消息
# =============================================================================

for msg in st.session_state.messages:
    role = msg["role"]

    if role == "separator":
        st.divider()

    elif role == "reasoning":
        with st.chat_message("assistant"):
            with st.expander("🧠 推理过程", expanded=False):
                st.markdown(msg["content"])

    elif role == "tool_call":
        with st.chat_message("assistant"):
            with st.expander(f"🔧 {msg['name']}", expanded=False):
                cols = st.columns(2)
                with cols[0]:
                    st.caption("参数")
                    st.json(msg.get("input", {}))
                with cols[1]:
                    st.caption("结果")
                    result = msg.get("result", {})
                    if isinstance(result, dict):
                        st.json(result)

    elif role == "preview":
        with st.chat_message("assistant"):
            st.image(
                f"data:image/png;base64,{msg['base64']}",
                caption=msg.get("path", "预览图"),
                width=400,
            )

    elif role in ("assistant", "user"):
        with st.chat_message(role):
            st.markdown(msg["content"])

    elif role == "error":
        with st.chat_message("assistant"):
            st.error(msg["content"])

# =============================================================================
# 用户输入与 Agent 执行
# =============================================================================

if prompt := st.chat_input("请输入设计指令，如：生成门牌301，部门名研发中心…"):
    if not st.session_state.connected or st.session_state.agent is None:
        st.error("请先在左侧边栏配置模型并点击「🔗 连接」")
        st.stop()

    # 展示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    agent: SignageAgent = st.session_state.agent

    # 运行 Agent，实时渲染事件
    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        tool_results_buffer = {}  # tool_name → result, 用于 tool_call + tool_result 配对

        for event in agent.run_single_stream(prompt):
            etype = event["type"]

            # ---- thinking ----
            if etype == "thinking":
                status_placeholder.info(f"🤔 思考中… (第 {event['turn']} 轮)")

            # ---- reasoning (DeepSeek 推理模型的思维链) ----
            elif etype == "reasoning":
                with st.expander("🧠 推理过程", expanded=True):
                    st.markdown(event["content"])
                st.session_state.messages.append({"role": "reasoning", "content": event["content"]})

            # ---- text ----
            elif etype == "text":
                if event["content"].strip():
                    st.markdown(event["content"])
                    st.session_state.messages.append({"role": "assistant", "content": event["content"]})

            # ---- tool_call ----
            elif etype == "tool_call":
                name = event["name"]
                inp = event["input"]
                status_placeholder.info(f"🔧 调用工具: {name}")
                tool_results_buffer[name] = {"input": inp, "result": None}

            # ---- tool_result ----
            elif etype == "tool_result":
                name = event["name"]
                result = event["result"]
                inp = tool_results_buffer.get(name, {}).get("input", {})

                with st.expander(f"🔧 {name}", expanded=True):
                    cols = st.columns(2)
                    with cols[0]:
                        st.caption("参数")
                        st.json(inp)
                    with cols[1]:
                        st.caption("结果")
                        st.json(result)

                st.session_state.messages.append({
                    "role": "tool_call", "name": name,
                    "input": inp, "result": result,
                })

            # ---- preview ----
            elif etype == "preview":
                st.image(
                    f"data:image/png;base64,{event['base64']}",
                    caption=event.get("path", "预览图"),
                    width=400,
                )
                st.session_state.messages.append({
                    "role": "preview", "base64": event["base64"],
                    "path": event.get("path", ""),
                })

            # ---- error ----
            elif etype == "error":
                st.error(event["error"])
                st.session_state.messages.append({"role": "error", "content": event["error"]})

            # ---- final ----
            elif etype == "final":
                status_placeholder.empty()
                if event["success"]:
                    msg = f"✅ {event['message']}\n\n> 共 {event['turns']} 轮，{event['tool_calls']} 次工具调用"
                    st.success(msg)
                else:
                    msg = f"❌ {event['message']}"
                    st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                break
