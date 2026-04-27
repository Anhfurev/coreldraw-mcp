"""Agent 主循环 — 调用 Claude API 编排 CorelDRAW MCP 工具，支持单条+批量两种模式"""

import base64
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Optional, Callable

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("runner")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

from agent.prompts import get_system_prompt

# ---- 工具注册表：从 tools/ 模块收集所有工具函数 ----

_TOOL_REGISTRY: dict[str, Callable] = {}

# Python type → JSON Schema type mapping
_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def _build_tool_def(func: Callable) -> dict:
    """从 Python 函数签名构建 Claude Tool Definition"""
    sig = inspect.signature(func)
    props = {}
    required = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        ptype = param.annotation if param.annotation is not inspect.Parameter.empty else str
        json_type = _TYPE_MAP.get(ptype, "string")

        prop = {"type": json_type, "description": f"{name} 参数"}
        has_default = param.default is not inspect.Parameter.empty
        if has_default:
            default_val = param.default
            if (json_type == "string" and default_val != "") or (json_type == "number" and default_val != 0):
                prop["default"] = default_val

        props[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "name": func.__name__,
        "description": (func.__doc__ or f"CorelDRAW 工具: {func.__name__}").strip().split("\n")[0],
        "input_schema": {
            "type": "object",
            "properties": props,
            "required": required,
        },
    }


def _register_tools():
    """从 tools/ 模块收集所有公开工具函数"""
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
    """执行工具并返回结果"""
    if name not in _TOOL_REGISTRY:
        return {"success": False, "error": f"未知工具: {name}"}

    func = _TOOL_REGISTRY[name]

    try:
        result = func(**arguments)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result if isinstance(result, dict) else {"result": str(result)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _read_image_base64(path: str) -> Optional[str]:
    """读取图片文件的 base64 编码"""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


# ---- Agent 主循环 ----

class SignageAgent:
    """标识行业自动化设计 Agent"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-5-20250929"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.tools: list[dict] = []
        self._init_tools()

    def _init_tools(self):
        _register_tools()
        self.tools = [_build_tool_def(f) for f in _TOOL_REGISTRY.values()]
        # 去重（同名工具如 check_rgb_colors 在 colors 和 preflight 都有，保留第一个）
        seen = set()
        unique_tools = []
        for t in self.tools:
            if t["name"] not in seen:
                seen.add(t["name"])
                unique_tools.append(t)
        self.tools = unique_tools

    def _get_client(self):
        try:
            import anthropic
            return anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("请安装 anthropic: pip install anthropic")

    def run_single(self, task: str, system_prompt: Optional[str] = None, max_turns: int = 30) -> dict:
        """执行单条任务的 Agent 循环"""
        client = self._get_client()
        system = system_prompt or get_system_prompt("full")

        messages: list[dict] = [{"role": "user", "content": task}]
        turn = 0
        total_tool_calls = 0
        errors = []

        while turn < max_turns:
            turn += 1
            logger.info(f"Agent 第 {turn} 轮请求…")

            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system,
                    tools=self.tools,
                    messages=messages,
                )
            except Exception as e:
                logger.error(f"Claude API 调用失败: {e}")
                errors.append(f"API 错误: {e}")
                break

            # 检查 stop_reason
            stop = response.stop_reason
            logger.info(f"Claude 响应: stop_reason={stop}")

            if stop == "end_turn":
                # Claude 完成了，没有更多工具调用
                final_text = ""
                for block in response.content:
                    if block.type == "text":
                        final_text += block.text
                return {"success": True, "message": final_text, "turns": turn, "tool_calls": total_tool_calls, "errors": errors}

            elif stop == "tool_use":
                # Claude 需要调用工具
                tool_results = []
                assistant_blocks = []

                for block in response.content:
                    if block.type == "text":
                        assistant_blocks.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        total_tool_calls += 1
                        tool_name = block.name
                        tool_input = block.input if isinstance(block.input, dict) else {}
                        logger.info(f"  调用工具: {tool_name}({tool_input})")

                        result = _execute_tool(tool_name, tool_input)

                        assistant_blocks.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

                        # 检查是否是预览图导出，如果是则读取图片
                        image_base64 = None
                        if tool_name == "export_preview_png" and result.get("success"):
                            png_path = tool_input.get("path", "") or (result.get("data", {}).get("path", ""))
                            if png_path:
                                image_base64 = _read_image_base64(png_path)

                        tool_result_block = {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        }

                        if image_base64:
                            tool_result_block["content"] = [
                                {"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)},
                                {"type": "image", "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64,
                                }},
                            ]

                        tool_results.append(tool_result_block)

                # 追加 assistant 消息和 tool_result 消息
                messages.append({"role": "assistant", "content": assistant_blocks})
                messages.append({"role": "user", "content": tool_results})

            else:
                errors.append(f"意外的 stop_reason: {stop}")
                break

        return {"success": False, "message": f"达到最大轮次 {max_turns}", "turns": turn, "tool_calls": total_tool_calls, "errors": errors}

    def run_batch(
        self,
        task: str,
        output_dir: str = "output",
        system_prompt: Optional[str] = None,
        max_turns_per_record: int = 20,
    ) -> dict:
        """执行批量任务的 Agent 循环"""
        client = self._get_client()
        system = system_prompt or get_system_prompt("full")
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

        return self.run_single(batch_task, system_prompt=system, max_turns=max_turns_per_record * 50)

    def check_visual(self, image_path: str, context: str = "") -> dict:
        """对生成的预览图进行视觉检查"""
        client = self._get_client()
        image_base64 = _read_image_base64(image_path)
        if not image_base64:
            return {"success": False, "error": f"无法读取图片: {image_path}"}

        system = get_system_prompt("visual")
        user_msg = f"请检查这张门牌预览图。{context}" if context else "请检查这张设计预览图。"

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                        {"type": "text", "text": user_msg},
                    ],
                }],
            )
            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text
            return {"success": True, "result": text}
        except Exception as e:
            return {"success": False, "error": str(e)}


def run_signage_task(
    task: str,
    mode: str = "single",
    output_dir: str = "output",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """便捷入口：执行标识设计任务

    Args:
        task: 任务描述或 Excel 文件路径
        mode: "single" 单条任务，或 "batch" 批量任务
        output_dir: 批量模式的输出目录
        api_key: Anthropic API Key
        model: Claude 模型名称
    """
    agent = SignageAgent(api_key=api_key, model=model or "claude-sonnet-4-5-20250929")

    if mode == "batch":
        return agent.run_batch(task, output_dir=output_dir)
    return agent.run_single(task)
