"""Streamlit Chat UI — CorelDRAW 调试对话框

启动: streamlit run server/app.py
"""

import base64
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode

# 读取 .env，侧边栏的 API Key 留空时即可回退到环境变量（与 server.py 行为一致）
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 确保 server/ 目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.runner import SignageAgent
from tools.jersey import (
    duplicate_jersey_rows,
    resize_jersey_row,
    scan_jersey_rows,
    set_jersey_material,
    set_jersey_players,
)


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


# Зурган дээрх өгөгдлийг заавал JSON блок болгож гаргуулна — AI буруу уншсан нэр/дугаарыг
# хэрэглэгч энд шалгаж засаад, зөвхөн засварласны дараа л CorelDRAW руу бичнэ ("material
# бэлдэхээс өмнө материал дэмий үрэхгүй байх" гэсэн зорилготой, хэрэглэгчийн шаардсанаар).
_EXTRACTION_PROMPT = """This app is exclusively for sports jersey production. ALWAYS assume any
photo sent to you shows player data — a roster, size chart, handwritten list, or measurement
sheet with names, jersey numbers, and/or sizes — even if the caption is vague or empty. Do not
treat it as a generic "describe this image" request.

First answer in plain English: summarize what you found. If the photo/caption does not make
clear which SPORT (volleyball or basketball) and which GENDER (male or female) this roster is
for, you MUST ask the user for both — do not guess, since jersey width/length are computed
differently per sport and gender. Also ALWAYS end by asking what fabric/material they want
these jerseys made from (never specified yet, required before production).

Then, ALWAYS output a fenced JSON code block — even if you truly find no player data at all
(in that case output an empty array) — with this exact shape, one object per player/row you
can see in the photo:

```json
[{"name": "...", "number": "...", "height_cm": "...", "weight_kg": "...", "chest_cm": "...", "shoulder_cm": "..."}]
```

height_cm/weight_kg/chest_cm/shoulder_cm are numbers as plain strings (e.g. "170"), not text like "170cm".
Leave any field as an empty string "" if it is not visible. Never skip this block — a human
will review it in an editable table before anything is written to production, specifically
to catch cases where you misread a name or number."""


# Хэрэглэгч хүснэгтэд гараар засварласан (томьёогоор тооцсоноос өөр) утгыг энд хадгална —
# дараа удаа ижил төстэй хүн ирвэл томьёо биш ЭНЭ бодит засварыг эхлээд ашиглана.
# Ялангуяа томьёо огт байхгүй хоосон нүдийг хүн гараар бөглөх бүрт энд хадгалагдаад,
# цаг өнгөрөх тусам жинхэнэ дүрмийг олж мэдэхэд хэрэг болно.
_CORRECTIONS_PATH = Path(__file__).resolve().parent / "data" / "jersey_size_corrections.jsonl"


def _load_corrections() -> list[dict]:
    if not _CORRECTIONS_PATH.exists():
        return []
    out = []
    for line in _CORRECTIONS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _lookup_correction(
    height_cm: float, weight_kg: float, gender: str, sport: str, field: str,
    height_tol: float = 3.0,
) -> float | None:
    """Ойролцоо өндөртэй (±height_tol см) өмнөх засваруудаас утга гаргана. Зөвхөн яг ойрыг
    (±1.5см/±3кг) л авдаг байсан хуучин хувилбар өгөгдөл цөөхөн үед хэт олон хоосон нүд
    гаргадаг байсан (жишээ: 169см/50кг, 169см/62кг гэх мэт цэгүүд байхад завсрын
    56кг асуувал юу ч олдохгүй байсан) — хэрэглэгч "урт гарахгүй байна" гэж шаардсан
    тул одоо ижил өндрийн (±3см) бүх бодит цэгүүдийн ДУНД жингийн интерполяци хийнэ:
      - зорилтот жингийн ДООД ба ДЭЭД талд бодит цэг олдвол хоёуланг нь шугаман
        интерполяци хийнэ (жишээ 169см: 50кг→112, 62кг→118 гэдгээс 56кг-г ~115 гэж гаргана)
      - зөвхөн нэг тал байвал (жин хэт бага/их) хамгийн ойр цэгийн утгыг шууд ашиглана
        (нэг талын мэдээллээр хэтрүүлж таамаглах — яг биш ч хоосноос дээр)
      - тухайн өндрийн орчимд (±3см дотор) ЯМАР Ч бодит цэг байхгүй бол л None буцаана
        (жишээ 190см — 164/169/170-аас хэт хол, тохирохгүй)."""
    candidates = []
    for c in _load_corrections():
        if c.get("gender") != gender or c.get("sport") != sport or field not in c:
            continue
        try:
            ch = float(c.get("height_cm", 0))
        except (TypeError, ValueError):
            continue
        if abs(ch - height_cm) > height_tol:
            continue
        cw = c.get("weight_kg")
        try:
            cw = float(cw) if cw not in (None, "") else None
        except (TypeError, ValueError):
            cw = None
        candidates.append((ch, cw, c[field]))

    if not candidates:
        return None
    if not weight_kg:
        return min(candidates, key=lambda t: abs(t[0] - height_cm))[2]

    with_weight = [c for c in candidates if c[1] is not None]
    if not with_weight:
        return min(candidates, key=lambda t: abs(t[0] - height_cm))[2]

    def _score(c):
        return abs(c[0] - height_cm) + abs(c[1] - weight_kg)

    below = [c for c in with_weight if c[1] <= weight_kg]
    above = [c for c in with_weight if c[1] >= weight_kg]
    if below and above:
        b, a = min(below, key=_score), min(above, key=_score)
        if b[1] == a[1]:
            return b[2]
        t = (weight_kg - b[1]) / (a[1] - b[1])
        return b[2] + t * (a[2] - b[2])
    return min(below or above, key=_score)[2]


def _compute_jersey_width(height_cm: float, gender: str, sport: str, weight_kg: float = 0) -> float | None:
    """Тоглогчийн өндрөөс жинсэн (front/back) өргөнийг тооцно — зөвхөн хэрэглэгчийн өгсөн
    жишээнүүдээр 100% тохирсон томьёо: урт тооцох дүрэм (энэ функцэд байхгүй, доор тайлбарласан
    шалтгаанаар) хараахан баталгаажаагүй тул зөвхөн ӨРГӨНИЙГ тооцно, урт нь хоосон үлдэнэ —
    хэрэглэгч энэ тал дээр тодорхой дүрэм өгөөгүй (зөвхөн 1-2 жишээ цэг байсан, тэдгээрээр
    ерөнхий томьёо гаргах боломжгүй, буруу таамаглаж материал үрэхээс зайлсхийв).
    Санамж: "урт (length) заавал тэгш тоо байх ёстой" дүрэм ЗӨВХӨН урт-д хамаарна, өргөнд
    (width) хамаарахгүй — хэрэглэгчийн баталгаажуулсан өргөний утгууд дунд 63/71/73/75/77
    гэх мэт сондгой тоо хэвийн байгаа.
        Волейбол эмэгтэй: 63 + 0.5×(өндөр-160)   — 160→63, 165→65, 170→68 (хэрэглэгчийн жишээтэй тохирно)
        Волейбол эрэгтэй: 71 + 0.4×(өндөр-170)   — 170→71, 172→72, 175→73, 180→75 (яг тохирно)
        Баскетбол эрэгтэй: волейбол эрэгтэйн утга + 2 — 175→75, 180→77 (хэрэглэгчийн жишээтэй тохирно)
        Баскетбол эмэгтэй: хэрэглэгч огт дурдаагүй тул тооцохгүй."""
    gender, sport = (gender or "").strip().lower(), (sport or "").strip().lower()
    if height_cm <= 0:
        return None
    override = _lookup_correction(height_cm, weight_kg, gender, sport, "width_cm")
    if override is not None:
        return override
    if sport == "volleyball" and gender == "female":
        return round(63 + 0.5 * (height_cm - 160))
    if sport == "volleyball" and gender == "male":
        return round(71 + 0.4 * (height_cm - 170))
    if sport == "basketball" and gender == "male":
        return round(71 + 0.4 * (height_cm - 170) + 2)
    return None


def _round_to_even(x: float) -> int:
    """Урт (length) утга ЗААВАЛ тэгш тоо байх ёстой (хэрэглэгчийн дүрэм — 111/117 гэх мэт сондгой
    тоо хэрэггүй, учир нь энэ утгыг цаашид 2-т хуваадаг тул тэгш байх шаардлагатай). Хамгийн
    ойрын тэгш тоо руу дугуйлна: 121→120 эсвэл 122 (ижил зайтай үед 2×round(x/2) 60-руу
    дугуйлдаг тал руугаа ордог, ялгаа алга)."""
    return int(2 * round(x / 2))


def _compute_jersey_length(
    height_cm: float, weight_kg: float, gender: str, sport: str,
) -> float | None:
    """Урт тооцно. ЗӨВХӨН өмнөх засварын жагсаалтаас ойролцоо өндөр/жинтэй бодит тохирол
    олдвол утга буцаана; олдохгүй бол ХООСОН (None) — цээжээр автоматаар "цээж+20" гэж
    тооцохгүй болгосон (энэ функцийн өмнөх хувилбар үүнийг хийдэг байсан бөгөөд хэрэглэгч
    үүнийг бодит алдаа гэж заасан: жишээ нь 164см/66кг — сорилтын мужид (169-170см) байхгүй
    тул засварын жагсаалтад тохирол олдоогүй, гэтэл функц чимээгүйгээр цээж+20 руу шилжиж
    буруу тоо (жишээ нь 100) гаргасан). Одоо цээжийг зөвхөн хэрэглэгч өөрөө "цээж ер бусын
    том" гэж үзээд ХҮСНЭГТЭД ГАРААР бичихэд л ашиглана — автоматаар таамаглахгүй."""
    gender, sport = (gender or "").strip().lower(), (sport or "").strip().lower()
    if height_cm <= 0:
        return None
    value = _lookup_correction(height_cm, weight_kg, gender, sport, "length_cm")
    # Интерполяци хийсэн үр дүн 111/117 гэх мэт сондгой тоо гарч болзошгүй тул тэгш болгоно —
    # яг бодит цэгтэй давхцвал аль хэдийн тэгш байгаа тул өөрчлөгдөхгүй.
    return _round_to_even(value) if value is not None else None


def _extract_roster_json(text: str) -> list[dict] | None:
    """Хариултаас JSON массивыг ялгаж авна — эхлээд ```json ... ``` хашилтаас, олдохгүй бол
    эхний [ -с сүүлийн ] хүртэлхийг оролдоно. Задлаж чадахгүй бол None (хүснэгт үзүүлэхгүй)."""
    match = re.search(r"```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = match.group(1) if match else None
    if raw is None:
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end != -1 and end > start:
            raw = text[start:end + 1]
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, list) else None


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
            for data_uri in msg.get("images", []):
                st.image(data_uri, width=250)
            st.markdown(msg["content"])

    elif role == "error":
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            st.error(msg["content"])

# =============================================================================
# 用户输入与 Agent 执行
# =============================================================================

submission = st.chat_input(
    "Анхууштай чатлах…",
    accept_file=True,
    file_type=["png", "jpg", "jpeg", "webp"],
)

if submission:
    prompt_text = submission.text or "Extract the player roster data (names/numbers/sizes) from this photo."
    uploaded_images = []  # [(mime, base64_str), ...]
    for f in submission.files:
        mime = f.type or "image/png"
        b64 = base64.b64encode(f.getvalue()).decode()
        uploaded_images.append((mime, b64))

    if not st.session_state.connected or st.session_state.agent is None:
        st.error("Эхлээд зүүн талын хажуу самбар дээр загвараа тохируулж «🔗 Холбох» товчийг дарна уу")
        st.stop()

    data_uris = [f"data:{mime};base64,{b64}" for mime, b64 in uploaded_images]

    # 展示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt_text, "images": data_uris})
    with st.chat_message("user", avatar=USER_AVATAR):
        for uri in data_uris:
            st.image(uri, width=250)
        st.markdown(prompt_text)

    # Зурагтай бол ЗААВАЛ Gemini-ээр (одоо холбогдсон нь ямар ч provider байсан хамаагүй) —
    # ердийн чат руу холбогдсон загвар (жишээ нь minimax-m3:free) зураг ойлгож чаддаггүй нь
    # баталгаажсан (улаан зурган дээр "Black" гэж хариулж байсан). Зургийн текстийн санал
    # асуулга бус ердийн харилцаа хэвээрээ session_state.agent-аар явна.
    if uploaded_images:
        if "_vision_agent" not in st.session_state:
            try:
                st.session_state._vision_agent = SignageAgent(
                    provider="openai", model="gemini-3.1-flash-lite",
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                )
            except Exception as e:
                st.error(f"Gemini-тэй холбогдож чадсангүй (GEMINI_API_KEY шалгана уу): {e}")
                st.stop()
        agent: SignageAgent = st.session_state._vision_agent
        content_blocks = [{"type": "text", "text": prompt_text}] + [
            {"type": "image_url", "image_url": {"url": uri}} for uri in data_uris
        ]
        agent_input = content_blocks
        run_system_prompt = _EXTRACTION_PROMPT
    else:
        agent: SignageAgent = st.session_state.agent
        agent_input = prompt_text
        run_system_prompt = None

    # 运行 Agent，实时渲染事件 —— 思考/工具调用放进可折叠的 status（真正的"加载中"效果），
    # 最终答案作为普通聊天气泡显示在 status 外面，不再用一整块绿色 success 框包住回答
    with st.chat_message("assistant", avatar=BOT_AVATAR):
        tool_results_buffer = {}
        final_text = ""
        final_event = None

        with st.status("Thinking…", expanded=True) as status:
            for event in agent.run_single_stream(agent_input, system_prompt=run_system_prompt):
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
                    break  # 不能只 set 不 break——生成器紧接着还会 yield 一个通用文案的
                           # "final" 事件，如果这里不 break，下一轮循环会把 final_event
                           # 覆盖成那个通用事件，真正的错误原因（event["error"]）就丢了

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
            roster = _extract_roster_json(text) if uploaded_images else None
            # Хэрэглэгчид JSON блокыг харуулах шаардлагагүй — доор хүснэгт болгож харуулна,
            # эндхийн хариулт зөвхөн AI-ийн үг хэллэгийн тайлбар байх ёстой
            display_text = re.sub(r"```json\s*\[.*?\]\s*```", "", text, flags=re.DOTALL).strip()
            st.write_stream(_typewriter(display_text or text))
            st.caption(f"Total {final_event['turns']} turns, {final_event['tool_calls']} tool calls")
            st.session_state.messages.append({"role": "assistant", "content": display_text or text})
            if roster:
                def _to_num(v):
                    try:
                        return float(v) if v not in (None, "") else None
                    except (TypeError, ValueError):
                        return None

                # AI-ийн буцаасан height_cm/weight_kg/chest_cm бүгд string (жишээ нь "170") —
                # хүснэгтэд бодит тоо болгож хадгална, эс тэгвэл нэг багана дотор string ба
                # тоо холилдож st.data_editor-ийн багана төрөл таних логикийг эвдэж, зарим
                # нүд засварлагдахгүй/хачин харагдах шалтгаан болдог.
                for r in roster:
                    for key in ("height_cm", "weight_kg", "chest_cm", "shoulder_cm"):
                        r[key] = _to_num(r.get(key))
                    r.setdefault("width_cm", None)
                    r.setdefault("length_cm", None)
                st.session_state.pending_roster = roster
                # Шинэ зурган роостер ирсэн тул доорх AgGrid-ийг бүрэн шинээр ачаалуулна
                # (өмнөх зургийн хүмүүсийн дотоод grid төлөв үлдэхгүйн тулд).
                st.session_state.roster_grid_version = st.session_state.get("roster_grid_version", 0) + 1
        elif final_event:
            msg = f"❌ {final_event['message']}"
            st.error(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})

# =============================================================================
# Зурганаас уншсан өгөгдлийг шалгах хүснэгт — CorelDRAW руу бичихээс ӨМНӨ хүн
# нэр/дугаарыг засаж болно (AI буруу уншсаны улмаас материал дэмий үрэхгүйн тулд).
# submission блокоос ГАДНА байх ёстой — эс тэгвэл хүснэгтийг засах/товч дарах бүрт
# дахин ачаалахад pending_roster алга болно.
# =============================================================================

if st.session_state.get("pending_roster"):
    st.divider()
    st.subheader("📋 Зурганаас уншсан өгөгдөл")
    st.caption(
        "AI-ийн уншсан нэр/дугаар/өндөр/жин/цээж — эндээс шалгаад буруу бол нүд дээр дараад засаарай. "
        "«Start Jersey» дарахад энэ хүснэгт дэх хүн бүрт шинэ джерси үүсгэж нэр/дугаарыг "
        "бичнэ, мөн өргөн/урт хоёулаа байвал панелийг яг тэр хэмжээнд өөрчилнө "
        "(хоосон бол загвар мөрийн хэмжээгээр үлдэнэ, таамаглахгүй)."
    )

    _GENDER_TAGS = {"": "", "эрэгтэй": "male", "эмэгтэй": "female"}

    col_sport, col_gender, col_material, col_calc = st.columns([1, 1, 1.4, 1])
    with col_sport:
        sport = st.selectbox("Спорт", ["", "volleyball", "basketball"], key="roster_sport")
    with col_gender:
        gender_tag = st.selectbox("Хүйс", list(_GENDER_TAGS.keys()), key="roster_gender")
        gender = _GENDER_TAGS[gender_tag]
    with col_material:
        material = st.text_input("Материал/Fabric", key="roster_material", placeholder="жишээ нь: 3016")
    with col_calc:
        st.write("")
        if st.button("🧮 Хэмжээ тооцоолох", use_container_width=True):
            def _num(v):
                try:
                    return float(v or 0)
                except (TypeError, ValueError):
                    return 0

            for r in st.session_state.pending_roster:
                h, wt = _num(r.get("height_cm")), _num(r.get("weight_kg"))
                r["width_cm"] = _compute_jersey_width(h, gender, sport, weight_kg=wt)
                r["length_cm"] = _compute_jersey_length(h, wt, gender, sport)
            # Гаднаас (Python талаас) roster-ийг өөрчилсөн тул AgGrid-ийг доор шинэ
            # утгуудаар ЭХЛЭЭД ачаалуулахын тулд түүний key-г өөрчилнө — key өөрчлөгдөхгүй
            # бол AgGrid хуучин (component-ийн өөрийн санаж байгаа) утгаа буцаад бичих нь
            # тестээр батлагдсан bug (доорх тайлбарыг үз).
            st.session_state.roster_grid_version = st.session_state.get("roster_grid_version", 0) + 1
            st.rerun()
    if not sport or not gender:
        st.caption("⚠️ Спорт/хүйс сонгоогүй тул өргөн тооцохгүй (буруу таамаглахаас зайлсхийв).")
    if not material:
        st.caption("⚠️ Материал/fabric оруулаагүй байна — «Start Jersey» дарахад заавал хэрэгтэй.")

    # CorelDRAW-д яг ямар джерси мөр(үүд) байгааг үргэлж эхлээд ЭНД ИЛЭРХИЙ илрүүлж,
    # харуулж, хэрэглэгчээр батлуулна — урьд нь source_row=1-ийг чимээгүй таамагласнаас болж
    # хэрэглэгчийн жинхэнэ бэлдсэн джерсийг олж чадаагүй асуудал давтагдахгүйн тулд.
    template_scan = scan_jersey_rows()
    scan_rows = (template_scan.data or {}).get("rows", []) if template_scan.success else []
    source_row = None
    if scan_rows:
        row_labels = [f"Мөр {r['row']}: {r['team']} / {r['name']} #{r['number']}" for r in scan_rows]
        # Анхны сонголт: "TEAM"/"NAME" гэсэн жинхэнэ бус placeholder биш мөрийг илүүд үзнэ —
        # гэхдээ энэ зөвхөн анхны сонголт, хэрэглэгч доороос үргэлж өөрчилж болно.
        default_idx = next(
            (i for i, r in enumerate(scan_rows) if r["team"] != "TEAM" and r["name"] != "NAME"), 0
        )
        chosen_label = st.selectbox(
            "🎯 Загвар джерси (CorelDRAW-с илрүүлсэн, үүнээс хуулбарлаж шинэ мөр үүсгэнэ)",
            row_labels,
            index=default_idx,
            key="jersey_source_row_label",
        )
        source_row = scan_rows[row_labels.index(chosen_label)]["row"]
        if len(scan_rows) > 1:
            st.caption(f"⚠️ CorelDRAW-д нийт {len(scan_rows)} мөр илэрлээ — дээрээс зөв загвараа сонгосон эсэхээ шалгаарай.")
    else:
        st.error("⚠️ CorelDRAW-с ямар ч джерси мөр (REF_* нэртэй объект) илэрсэнгүй. Эхлээд загвар нэг мөр бэлдэнэ үү — «Start Jersey» ажиллахгүй.")

    # st.data_editor өөрөө нүдийг өнгөлж чадахгүй (canvas дээр зурагддаг тул CSS хүрэхгүй) —
    # харин st.data_editor-ийг бүрэн хасахад засварлах боломж алга болдог тул үүний оронд
    # streamlit-aggrid ашиглаж, ЗАСВАРЛАХ БОЛОМЖТОЙ, length/width баганыг нь цэнхэр өнгөтэй
    # ганц хүснэгт л үлдээв (хэрэглэгчийн хүсэлт: "we need to edit" + "just need blue colored table").
    roster = st.session_state.pending_roster
    if roster:
        # Хэрэглэгчийн дараалал: нэр → цээж/мөрний урт/урт/өргөн (нэрний ард) → өндөр/жин → дугаар (СҮҮЛД).
        preview_cols = ["name", "chest_cm", "shoulder_cm", "length_cm", "width_cm", "height_cm", "weight_kg", "number"]
        preview_df = pd.DataFrame(roster)
        for c in preview_cols:
            if c not in preview_df.columns:
                preview_df[c] = None
        preview_df = preview_df[preview_cols]

        _CENTER_STYLE = {"textAlign": "center"}
        _BLUE_STYLE = {"color": "#1a73e8", "fontWeight": "600", "textAlign": "center"}
        gb = GridOptionsBuilder.from_dataframe(preview_df)
        gb.configure_default_column(editable=True, resizable=True, minWidth=110, cellStyle=_CENTER_STYLE)
        gb.configure_column("length_cm", cellStyle=_BLUE_STYLE)
        gb.configure_column("width_cm", cellStyle=_BLUE_STYLE)
        gb.configure_grid_options(domLayout="autoHeight", stopEditingWhenCellsLoseFocus=True)

        # reload_data=True биш, харин key-г "roster_grid_version" тоолуураар хувиргана:
        # тестээр батлагдсан bug — reload_data=True бол хэрэглэгч өөрөө нүдэнд бичиж буй
        # ЗАСВАР нь AgGrid-ийн буцаах утганд орохгүй, учир нь тухайн rerun дотор Python
        # талын preview_df хараахан шинэчлэгдээгүй хуучин утгаараа AgGrid рүү дахин "props"
        # болгож бичигдэж, хэрэглэгчийн дөнгөж хийсэн засвар дээгүүр давхар бичигддэг.
        # Харин key ЗӨВХӨН "Хэмжээ тооцоолох" мэт ГАДНААС (Python талаас) roster-ийг
        # өөрчилсөн үед л өөрчлөгддөг тул энгийн нүд засах үед грид өөрийн дотоод төлөвөө
        # хадгалж, зөв утгаа буцаана; харин тооцоолсны дараа шинэ key-тэй бүрэн шинээр
        # ачаалж шинэ утгуудыг зөв харуулна.
        grid_version = st.session_state.get("roster_grid_version", 0)
        grid_response = AgGrid(
            preview_df,
            gridOptions=gb.build(),
            update_mode=GridUpdateMode.VALUE_CHANGED,
            data_return_mode=DataReturnMode.AS_INPUT,
            fit_columns_on_grid_load=False,
            allow_unsafe_jscode=False,
            key=f"roster_aggrid_v{grid_version}",
        )
        roster = grid_response["data"].to_dict("records")
        st.session_state.pending_roster = roster

    def _roster_names_numbers() -> list[dict]:
        return [
            # Джерси дээр нэрийг үргэлж том үсгээр бичнэ (жишээ нь "Anu" → "ANU") —
            # хэрэглэгчийн тодорхой хүсэлт; хүснэгтэд харуулж буй бичлэгийг өөрчлөхгүй,
            # зөвхөн CorelDRAW руу бичихдээ л том үсэгжүүлнэ.
            {"name": str(r.get("name", "")).upper(), "number": r.get("number", "")}
            for r in roster
            if r.get("name") or r.get("number")
        ]

    def _roster_sizes() -> list[tuple]:
        """_roster_names_numbers-тэй яг ижил шүүлтүүрээр, ижил дараалалтай (width_cm, length_cm)
        хосуудыг буцаана — хоёуланг нь мөр бүрт зэрэгцүүлж хэрэглэхийн тулд."""
        def _num(v):
            try:
                return float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None

        return [
            (_num(r.get("width_cm")), _num(r.get("length_cm")))
            for r in roster
            if r.get("name") or r.get("number")
        ]

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("👁️ Урьдчилан харах", use_container_width=True):
            people = _roster_names_numbers()
            st.info(f"{len(people)} шинэ джерси үүсгэнэ:")
            st.json(people)
    with col2:
        if st.button("🏐 Start Jersey", type="primary", use_container_width=True):
            people = _roster_names_numbers()
            if not people:
                st.error("Хүснэгт хоосон байна — нэр эсвэл дугаар оруулаагүй байна.")
            elif not material:
                st.error("Материал/fabric оруулаагүй байна — дээрх талбарт бичээд дахин дарна уу.")
            elif source_row is None:
                st.error("Загвар джерси илрээгүй тул үүсгэх боломжгүй — дээрх алдааг үзнэ үү.")
            else:
                # Дээрээс хэрэглэгчийн сонгосон (эсвэл автоматаар илрүүлсэн) жинхэнэ загвар
                # мөрийг хуулбарлаж яг хэдэн хүн байгаагаар нь шинэ мөр үүсгэнэ, дараа нь яг
                # тэр шинэ мөрүүдэд нэр/дугаарыг бичнэ.
                #
                # ЭНД ЗААВАЛ 1 нэгээр нь duplicate+resize хийх ёстой, бөөнөөр нь count=N дуудаад
                # дараа нь тус тусад нь resize хийж болохгүй: duplicate_jersey_rows нэг удаад
                # бүх шинэ мөрийг ЗАГВАРЫН (өмнөх, өөрчлөгдөөгүй) хэмжээгээр зайг нь тооцож
                # байрлуулдаг тул хожим resize_jersey_row-ээр том болговол дараагийн мөртэй
                # давхцах эрсдэлтэй (тестээр олж мэдсэн бодит асуудал). 1 нэгээр нь хийвэл
                # duplicate_jersey_rows дуудагдах бүрд өмнөх мөрийн ЖИНХЭНЭ (аль хэдийн
                # resize хийгдсэн бол шинэ хэмжээгээр) байдлыг харж зайг зөв тооцно.
                total_before = scan_jersey_rows()
                total_before = (total_before.data or {}).get("total", 0) if total_before.success else 0
                sizes = _roster_sizes()

                new_rows: list[int] = []
                dup_error = None
                resize_errors = []
                for i, (width_cm, length_cm) in enumerate(sizes):
                    dup_result = duplicate_jersey_rows(source_row=source_row, count=1)
                    if not dup_result.success:
                        dup_error = f"{i + 1}-р хүн дээр зогсов: {dup_result.error}"
                        break
                    new_row = total_before + 1 + i
                    new_rows.append(new_row)
                    # Нэр/дугаар бичихээс ӨМНӨ хэмжээг өөрчилнө — учир нь content бичсэний
                    # дараа дахин SizeWidth/Height тохируулах ёсгүй (текст дахин суналт болно,
                    # энэ дүрмийг өмнө нь бодит алдаагаар олж мэдсэн).
                    if width_cm and length_cm and width_cm > 0 and length_cm > 0:
                        rsz = resize_jersey_row(new_row, width_cm=width_cm, length_cm=length_cm)
                        if not rsz.success:
                            resize_errors.append(f"{new_row}-р мөр: {rsz.error}")
                if resize_errors:
                    st.warning("Зарим мөрийн хэмжээ өөрчлөгдсөнгүй (нэр/дугаар хэвээр бичигдэнэ): "
                               + "; ".join(resize_errors))

                if dup_error:
                    st.error(dup_error)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": f"❌ Джерси үүсгэж чадсангүй: {dup_error}"}
                    )
                else:
                    fill_updates = [
                        {"row": r, **p} for r, p in zip(new_rows, people)
                    ]
                    fill_result = set_jersey_players(fill_updates, dry_run=False)
                    if not fill_result.success:
                        st.error(fill_result.error)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": f"❌ Нэр/дугаар бичиж чадсангүй: {fill_result.error}"}
                        )
                    else:
                        mat_result = set_jersey_material(new_rows, material)
                        labels_written = sum(
                            r.get("labels_updated", 0) for r in (mat_result.data or {}).get("results", [])
                        ) if mat_result.success else 0
                        if not mat_result.success:
                            st.warning(f"Нэр/дугаар бичигдсэн ч материалын шошго амжилтгүй: {mat_result.error}")
                        st.success(f"{len(people)} джерси үүсгэж, мэдээллийг бичлээ!")

                        # Дуусаад чат руу нэг тайлан бичнэ — хэрэглэгчийн хүсэлт: зөвхөн
                        # энэ хэсэгт л харагдаад ширээ дээрээс алга болчих success/warning
                        # мессежийг чатын түүхэнд бас үлдээх (алгасахгүй, дараа буцаад харах боломжтой).
                        resized_count = sum(1 for w, l in sizes if w and l and w > 0 and l > 0)
                        summary = (
                            f"✅ {len(people)} джерси үүсгэж, {source_row}-р мөрийг загвар болгон "
                            f"{new_rows[0]}-{new_rows[-1]}-р мөрүүдэд нэр/дугаарыг бичлээ. "
                            f"Материал: «{material}». Хэмжээ: {resized_count}/{len(people)} хүнд "
                            f"өргөн/уртаар нь панелийг өөрчилсөн"
                            + (f", {len(people) - resized_count} нь загвар мөрийн хэмжээгээр үлдсэн "
                               "(өргөн/урт тооцоогдоогүй)." if resized_count < len(people) else ".")
                        )
                        if labels_written == 0:
                            summary += (
                                " ⚠️ Гэхдээ загвар мөрд материалын шошго (жижиг текст) огт "
                                "олдоогүй тул шинэ мөрүүдэд ч материалын шошго бичигдсэнгүй — "
                                "загвар мөрөндөө эхлээд материалын шошгоо гараар нэмээрэй."
                            )
                        st.session_state.messages.append({"role": "assistant", "content": summary})
                        del st.session_state.pending_roster
                        st.rerun()
    with col3:
        if st.button("❌ Цуцлах", use_container_width=True):
            del st.session_state.pending_roster
            st.rerun()
