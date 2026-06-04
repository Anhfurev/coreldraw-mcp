"""Agent 主循环 — 调用 LLM API 编排 CorelDRAW MCP 工具，支持单条+批量两种模式

支持的 Provider:
    - anthropic (默认): Claude 系列，api.anthropic.com
    - openai: OpenAI 兼容接口，支持 DeepSeek/Qwen/通义千问等

示例:
    agent = SignageAgent(provider="openai", model="deepseek-chat",
                         base_url="https://api.deepseek.com", api_key="sk-xxx")
    result = agent.run_single("生成门牌 301 研发中心")
"""

import base64
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Optional, Callable, Literal

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger("runner")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

from agent.prompts import get_system_prompt

# =============================================================================
# 工具注册与定义（与 provider 无关）
# =============================================================================

_TOOL_REGISTRY: dict[str, Callable] = {}

_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def _build_tool_def_anthropic(func: Callable) -> dict:
    """Anthropic 格式 tool definition"""
    sig = inspect.signature(func)
    props, required = {}, []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        ptype = param.annotation if param.annotation is not inspect.Parameter.empty else str
        json_type = _TYPE_MAP.get(ptype, "string")
        prop = {"type": json_type, "description": f"{name} 参数"}
        has_default = param.default is not inspect.Parameter.empty
        if has_default:
            val = param.default
            if (json_type == "string" and val != "") or (json_type == "number" and val != 0):
                prop["default"] = val
        props[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "name": func.__name__,
        "description": (func.__doc__ or f"CorelDRAW 工具: {func.__name__}").strip().split("\n")[0],
        "input_schema": {"type": "object", "properties": props, "required": required},
    }


def _build_tool_def_openai(func: Callable) -> dict:
    """OpenAI 兼容格式 tool definition"""
    anthropic_def = _build_tool_def_anthropic(func)
    return {
        "type": "function",
        "function": {
            "name": anthropic_def["name"],
            "description": anthropic_def["description"],
            "parameters": anthropic_def["input_schema"],
        },
    }


def _register_tools():
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY:
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools import document, shapes, text, colors, layers, export, preflight, data_merge

    modules = [document, shapes, text, colors, layers, export, preflight, data_merge]
    _TOOL_REGISTRY = {}
    for mod in modules:
        for name, obj in inspect.getmembers(mod):
            if inspect.isfunction(obj) and not name.startswith("_") and obj.__module__.startswith("tools."):
                _TOOL_REGISTRY[name] = obj
    logger.info(f"Agent 工具注册完成，共 {len(_TOOL_REGISTRY)} 个工具")


def _execute_tool(name: str, arguments: dict) -> dict:
    if name not in _TOOL_REGISTRY:
        return {"success": False, "error": f"未知工具: {name}"}
    try:
        result = _TOOL_REGISTRY[name](**arguments)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result if isinstance(result, dict) else {"result": str(result)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _read_image_base64(path: str) -> Optional[str]:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


# =============================================================================
# SignageAgent — 统一入口，内部按 provider 分发
# =============================================================================

class SignageAgent:
    """标识行业自动化设计 Agent

    Args:
        provider: "anthropic" (默认) 或 "openai"
        model: 模型名称。Anthropic 例 "claude-sonnet-4-6";
               OpenAI 兼容例 "deepseek-chat" / "qwen-max" / "gpt-4o"
        api_key: API Key。Anthropic 默认读 ANTHROPIC_API_KEY，
                 OpenAI 兼容默认读 OPENAI_API_KEY 或 DASHSCOPE_API_KEY
        base_url: OpenAI 兼容 API 地址。
                  DeepSeek: https://api.deepseek.com
                  千问: https://dashscope.aliyuncs.com/compatible-mode/v1
                  通用: 任意 OpenAI 兼容 endpoint
    """

    def __init__(
        self,
        provider: Literal["anthropic", "openai"] = "anthropic",
        model: str = "",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model or self._default_model()
        self.api_key = api_key or self._resolve_api_key()
        self.base_url = base_url
        self.tools: list[dict] = []
        self._client = None
        self._init_tools()

    def _default_model(self) -> str:
        if self.provider == "anthropic":
            return "claude-sonnet-4-6"
        return "deepseek-chat"

    def _resolve_api_key(self) -> Optional[str]:
        if self.provider == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY")
        return (
            os.environ.get("OPENAI_API_KEY")
            or os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
        )

    # ---- 工具初始化 ----

    def _init_tools(self):
        _register_tools()
        if self.provider == "anthropic":
            self.tools = [_build_tool_def_anthropic(f) for f in _TOOL_REGISTRY.values()]
        else:
            self.tools = [_build_tool_def_openai(f) for f in _TOOL_REGISTRY.values()]
        # 去重
        seen = set()
        unique = []
        for t in self.tools:
            key = t.get("name", t.get("function", {}).get("name", ""))
            if key not in seen:
                seen.add(key)
                unique.append(t)
        self.tools = unique

    # ---- 客户端 ----

    def _get_client(self):
        if self._client:
            return self._client
        if self.provider == "anthropic":
            try:
                import anthropic
            except ImportError:
                raise ImportError("请安装 anthropic: pip install anthropic")
            self._client = anthropic.Anthropic(api_key=self.api_key)
            return self._client
        else:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url.rstrip("/") + "/v1" if not self.base_url.endswith("/v1") else self.base_url
            self._client = OpenAI(**kwargs)
            return self._client

    # =====================================================================
    # Anthropic 调用循环
    # =====================================================================

    def _run_anthropic(self, task: str, system: str, max_turns: int) -> dict:
        client = self._get_client()
        messages: list[dict] = [{"role": "user", "content": task}]
        turn, total_calls, errors = 0, 0, []

        while turn < max_turns:
            turn += 1
            logger.info(f"Agent 第 {turn} 轮请求…")

            try:
                response = client.messages.create(
                    model=self.model, max_tokens=4096,
                    system=system, tools=self.tools, messages=messages,
                )
            except Exception as e:
                logger.error(f"Claude API 调用失败: {e}")
                errors.append(f"API 错误: {e}")
                break

            stop = response.stop_reason

            if stop == "end_turn":
                text = "".join(b.text for b in response.content if b.type == "text")
                return {"success": True, "message": text, "turns": turn, "tool_calls": total_calls, "errors": errors}

            elif stop == "tool_use":
                tool_results = []
                assistant_blocks = []

                for block in response.content:
                    if block.type == "text":
                        assistant_blocks.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        total_calls += 1
                        tool_name = block.name
                        tool_input = block.input if isinstance(block.input, dict) else {}
                        logger.info(f"  调用工具: {tool_name}({tool_input})")
                        result = _execute_tool(tool_name, tool_input)

                        assistant_blocks.append({
                            "type": "tool_use", "id": block.id,
                            "name": block.name, "input": block.input,
                        })

                        image_b64 = None
                        if tool_name == "export_preview_png" and result.get("success"):
                            png_path = tool_input.get("path", "") or result.get("data", {}).get("path", "")
                            if png_path:
                                image_b64 = _read_image_base64(png_path)

                        tr_block = {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        }
                        if image_b64:
                            tr_block["content"] = [
                                {"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)},
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                            ]
                        tool_results.append(tr_block)

                messages.append({"role": "assistant", "content": assistant_blocks})
                messages.append({"role": "user", "content": tool_results})
            else:
                errors.append(f"意外的 stop_reason: {stop}")
                break

        return {"success": False, "message": f"达到最大轮次 {max_turns}", "turns": turn, "tool_calls": total_calls, "errors": errors}

    # =====================================================================
    # OpenAI 兼容调用循环
    # =====================================================================

    def _run_openai(self, task: str, system: str, max_turns: int) -> dict:
        client = self._get_client()
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]
        turn, total_calls, errors = 0, 0, []

        while turn < max_turns:
            turn += 1
            logger.info(f"Agent 第 {turn} 轮请求…")

            try:
                response = client.chat.completions.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                )
            except Exception as e:
                logger.error(f"API 调用失败: {e}")
                errors.append(f"API 错误: {e}")
                break

            choice = response.choices[0]
            msg = choice.message

            # 有 tool_calls → 执行工具
            if msg.tool_calls:
                total_calls += len(msg.tool_calls)

                # 追加 assistant 消息（含 tool_calls）
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                })

                preview_images = []  # 收集预览 PNG 路径，后续作为 user 消息发送

                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_input = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_input = {}
                    logger.info(f"  调用工具: {tool_name}({tool_input})")
                    result = _execute_tool(tool_name, tool_input)

                    # OpenAI 每个 tool 结果是一条独立 role=tool 消息
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })

                    # 收集预览图
                    if tool_name == "export_preview_png" and result.get("success"):
                        png_path = tool_input.get("path", "") or result.get("data", {}).get("path", "")
                        if png_path and os.path.isfile(png_path):
                            preview_images.append(png_path)

                # 视觉反馈：预览图导出后，追加 user 消息让模型看图
                for img_path in preview_images:
                    image_b64 = _read_image_base64(img_path)
                    if image_b64:
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"这是刚才导出的预览图 {os.path.basename(img_path)}，请仔细检查设计是否符合要求。"},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                            ],
                        })
                        logger.info("  预览图已发送给模型进行视觉检查")

            # finish_reason == "stop" → 对话结束
            elif choice.finish_reason == "stop":
                return {
                    "success": True,
                    "message": msg.content or "",
                    "turns": turn,
                    "tool_calls": total_calls,
                    "errors": errors,
                }
            else:
                errors.append(f"意外的 finish_reason: {choice.finish_reason}")
                break

        return {"success": False, "message": f"达到最大轮次 {max_turns}", "turns": turn, "tool_calls": total_calls, "errors": errors}

    # =====================================================================
    # 公开接口
    # =====================================================================

    # ---------- 生成器版本（供 Streamlit 等 GUI 消费） ----------

    def _run_anthropic_stream(self, task: str, system: str, max_turns: int):
        """Anthropic 调用循环 — 生成器版本，逐事件 yield"""
        client = self._get_client()
        messages: list[dict] = [{"role": "user", "content": task}]
        turn, total_calls, errors = 0, 0, []

        hit_max = False
        while turn < max_turns:
            turn += 1
            yield {"type": "thinking", "turn": turn}

            try:
                response = client.messages.create(
                    model=self.model, max_tokens=4096,
                    system=system, tools=self.tools, messages=messages,
                )
            except Exception as e:
                yield {"type": "error", "error": f"API 错误 (第{turn}轮): {e}"}
                errors.append(f"API 错误: {e}")
                break

            stop = response.stop_reason

            if stop == "end_turn":
                text = "".join(b.text for b in response.content if b.type == "text")
                yield {"type": "text", "content": text}
                yield {"type": "final", "success": True, "message": text, "turns": turn, "tool_calls": total_calls, "errors": errors}
                return

            elif stop == "tool_use":
                tool_results = []
                assistant_blocks = []

                for block in response.content:
                    if block.type == "text":
                        assistant_blocks.append({"type": "text", "text": block.text})
                        yield {"type": "text", "content": block.text}
                    elif block.type == "tool_use":
                        total_calls += 1
                        tool_name = block.name
                        tool_input = block.input if isinstance(block.input, dict) else {}
                        yield {"type": "tool_call", "name": tool_name, "input": tool_input}

                        result = _execute_tool(tool_name, tool_input)
                        yield {"type": "tool_result", "name": tool_name, "result": result}

                        assistant_blocks.append({
                            "type": "tool_use", "id": block.id,
                            "name": block.name, "input": block.input,
                        })

                        image_b64 = None
                        png_path = ""
                        if tool_name == "export_preview_png" and result.get("success"):
                            png_path = tool_input.get("path", "") or result.get("data", {}).get("path", "")
                            if png_path:
                                image_b64 = _read_image_base64(png_path)
                                if image_b64:
                                    yield {"type": "preview", "path": png_path, "base64": image_b64}

                        tr_block = {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        }
                        if image_b64:
                            tr_block["content"] = [
                                {"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)},
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                            ]
                        tool_results.append(tr_block)

                messages.append({"role": "assistant", "content": assistant_blocks})
                messages.append({"role": "user", "content": tool_results})
            else:
                yield {"type": "error", "error": f"意外的 stop_reason: {stop}"}
                errors.append(f"意外的 stop_reason: {stop}")
                break
        else:
            hit_max = True

        final_msg = f"达到最大轮次 {max_turns}" if hit_max else f"任务因错误终止（共 {turn} 轮）"
        yield {"type": "final", "success": False, "message": final_msg, "turns": turn, "tool_calls": total_calls, "errors": errors}

    def _run_openai_stream(self, task: str, system: str, max_turns: int):
        """OpenAI 兼容调用循环 — 生成器版本，逐事件 yield"""
        client = self._get_client()
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]
        turn, total_calls, errors = 0, 0, []

        hit_max = False
        while turn < max_turns:
            turn += 1
            yield {"type": "thinking", "turn": turn}

            try:
                response = client.chat.completions.create(
                    model=self.model, max_tokens=4096,
                    messages=messages, tools=self.tools, tool_choice="auto",
                )
            except Exception as e:
                yield {"type": "error", "error": f"API 错误 (第{turn}轮): {e}"}
                errors.append(f"API 错误: {e}")
                break

            choice = response.choices[0]
            msg = choice.message

            if msg.tool_calls:
                total_calls += len(msg.tool_calls)

                messages.append({
                    "role": "assistant", "content": msg.content or "",
                    "tool_calls": [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                   for tc in msg.tool_calls],
                })

                preview_images = []

                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_input = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_input = {}
                    yield {"type": "tool_call", "name": tool_name, "input": tool_input}

                    result = _execute_tool(tool_name, tool_input)
                    yield {"type": "tool_result", "name": tool_name, "result": result}

                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": json.dumps(result, ensure_ascii=False, default=str)})

                    if tool_name == "export_preview_png" and result.get("success"):
                        png_path = tool_input.get("path", "") or result.get("data", {}).get("path", "")
                        if png_path and os.path.isfile(png_path):
                            preview_images.append(png_path)

                for img_path in preview_images:
                    image_b64 = _read_image_base64(img_path)
                    if image_b64:
                        yield {"type": "preview", "path": img_path, "base64": image_b64}
                        messages.append({
                            "role": "user", "content": [
                                {"type": "text", "text": f"这是刚才导出的预览图 {os.path.basename(img_path)}，请仔细检查设计是否符合要求。"},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                            ],
                        })

            elif choice.finish_reason == "stop":
                text = msg.content or ""
                yield {"type": "text", "content": text}
                yield {"type": "final", "success": True, "message": text, "turns": turn, "tool_calls": total_calls, "errors": errors}
                return
            else:
                yield {"type": "error", "error": f"意外的 finish_reason: {choice.finish_reason}"}
                errors.append(f"意外的 finish_reason: {choice.finish_reason}")
                break
        else:
            hit_max = True

        final_msg = f"达到最大轮次 {max_turns}" if hit_max else f"任务因错误终止（共 {turn} 轮）"
        yield {"type": "final", "success": False, "message": final_msg, "turns": turn, "tool_calls": total_calls, "errors": errors}

    # ---------- 同步接口 ----------

    def run_single(self, task: str, system_prompt: Optional[str] = None, max_turns: int = 30) -> dict:
        """执行单条任务的 Agent 循环"""
        system = system_prompt or get_system_prompt("full")
        if self.provider == "anthropic":
            return self._run_anthropic(task, system, max_turns)
        return self._run_openai(task, system, max_turns)

    def run_single_stream(self, task: str, system_prompt: Optional[str] = None, max_turns: int = 30):
        """执行单条任务的 Agent 循环 — 生成器版本，逐事件 yield 供 GUI 消费

        Yields events: thinking, text, tool_call, tool_result, preview, final, error
        """
        system = system_prompt or get_system_prompt("full")
        if self.provider == "anthropic":
            yield from self._run_anthropic_stream(task, system, max_turns)
        else:
            yield from self._run_openai_stream(task, system, max_turns)

    def run_batch(
        self, task: str, output_dir: str = "output",
        system_prompt: Optional[str] = None, max_turns_per_record: int = 20,
    ) -> dict:
        """执行批量任务的 Agent 循环"""
        os.makedirs(output_dir, exist_ok=True)
        batch_task = f"""{task}

请按流程处理每个文件：
1. 打开模板
2. 替换所有占位符文字
3. 视觉检查（导出预览图观察）
4. 印前处理（转曲、CMYK检查）
5. 导出 print/ 和 laser/ 子目录下的文件
6. 每条记录完成后汇报进度

输出目录: {output_dir}"""
        return self.run_single(batch_task, system_prompt=system_prompt, max_turns=max_turns_per_record * 50)

    def check_visual(self, image_path: str, context: str = "") -> dict:
        """对生成的预览图进行视觉检查"""
        image_base64 = _read_image_base64(image_path)
        if not image_base64:
            return {"success": False, "error": f"无法读取图片: {image_path}"}

        system = get_system_prompt("visual")
        user_msg = f"请检查这张门牌预览图。{context}" if context else "请检查这张设计预览图。"

        try:
            if self.provider == "anthropic":
                client = self._get_client()
                response = client.messages.create(
                    model=self.model, max_tokens=1024, system=system,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                            {"type": "text", "text": user_msg},
                        ],
                    }],
                )
                text = "".join(b.text for b in response.content if b.type == "text")
                return {"success": True, "result": text}
            else:
                client = self._get_client()
                resp = client.chat.completions.create(
                    model=self.model, max_tokens=1024,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": [
                            {"type": "text", "text": user_msg},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                        ]},
                    ],
                )
                return {"success": True, "result": resp.choices[0].message.content or ""}
        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# 便捷入口
# =============================================================================

def run_signage_task(
    task: str,
    mode: str = "single",
    provider: Literal["anthropic", "openai"] = "anthropic",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    output_dir: str = "output",
) -> dict:
    """便捷入口：执行标识设计任务

    Args:
        task: 任务描述或 Excel 文件路径
        mode: "single" 或 "batch"
        provider: "anthropic" 或 "openai"
        model: 模型名称
        api_key: API Key
        base_url: OpenAI 兼容 endpoint（仅 provider="openai" 时需要）
        output_dir: 批量模式输出目录

    示例:
        # Claude
        run_signage_task("生成门牌 301 研发中心")

        # DeepSeek
        run_signage_task("生成门牌 301 研发中心", provider="openai",
                         model="deepseek-chat", api_key="sk-xxx",
                         base_url="https://api.deepseek.com")

        # 千问
        run_signage_task("生成门牌 301 研发中心", provider="openai",
                         model="qwen-max", api_key="sk-xxx",
                         base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    """
    agent = SignageAgent(provider=provider, model=model or "", api_key=api_key, base_url=base_url)
    if mode == "batch":
        return agent.run_batch(task, output_dir=output_dir)
    return agent.run_single(task)
