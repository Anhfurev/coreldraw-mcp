"""模板管理工具 — 列出可用模板、查询尺寸变体规则"""

import json
import os

from core.models import ToolResult

_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "../config/template_registry.json")


def _load_registry() -> dict:
    with open(_REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def list_templates(filter_material: str = "", filter_keyword: str = "") -> ToolResult:
    """列出所有可用模板。filter_material 按材质过滤，filter_keyword 按名称/描述关键字过滤。
    返回每个模板的名称、描述、尺寸、占位符列表、是否有尺寸变体规则。"""
    try:
        registry = _load_registry()
    except Exception as e:
        return ToolResult.fail(f"无法读取模板库配置: {e}")

    templates = registry.get("templates", {})
    result = []

    for name, cfg in templates.items():
        if filter_material and filter_material.lower() not in cfg.get("material", "").lower():
            continue
        if filter_keyword:
            kw = filter_keyword.lower()
            if kw not in name.lower() and kw not in cfg.get("description", "").lower():
                continue

        entry = {
            "name": name,
            "description": cfg.get("description", ""),
            "file": cfg.get("file", ""),
            "width_mm": cfg.get("width_mm"),
            "height_mm": cfg.get("height_mm"),
            "material": cfg.get("material", ""),
            "placeholders": list(cfg.get("placeholders", {}).keys()),
            "has_size_variants": "size_variants" in cfg,
        }
        if "size_variants" in cfg:
            entry["size_variants"] = cfg["size_variants"]
        result.append(entry)

    return ToolResult.ok(
        f"找到 {len(result)} 个模板",
        total=len(result),
        templates=result,
    )


def get_template_info(template_name: str) -> ToolResult:
    """获取指定模板的完整配置，包括占位符详情、图层说明、尺寸变体规则和标题栏字段。"""
    try:
        registry = _load_registry()
    except Exception as e:
        return ToolResult.fail(f"无法读取模板库配置: {e}")

    templates = registry.get("templates", {})
    if template_name not in templates:
        available = list(templates.keys())
        return ToolResult.fail(f"模板 '{template_name}' 不存在，可用模板: {available}")

    cfg = templates[template_name]
    return ToolResult.ok(f"模板信息: {template_name}", name=template_name, **cfg)


def get_size_variant(template_name: str, room_number: str) -> ToolResult:
    """根据房间号字符数查询对应的页面尺寸变体。用于自动决定门牌宽度。"""
    try:
        registry = _load_registry()
    except Exception as e:
        return ToolResult.fail(f"无法读取模板库配置: {e}")

    templates = registry.get("templates", {})
    if template_name not in templates:
        return ToolResult.fail(f"模板 '{template_name}' 不存在")

    cfg = templates[template_name]
    if "size_variants" not in cfg:
        return ToolResult.ok(
            "此模板无尺寸变体规则，使用默认尺寸",
            width_mm=cfg.get("width_mm"),
            height_mm=cfg.get("height_mm"),
            variant_matched=False,
        )

    char_count = len(room_number.strip())
    variants = cfg["size_variants"].get("variants", [])
    for v in variants:
        if v.get("char_count") == char_count:
            return ToolResult.ok(
                f"房间号 '{room_number}'（{char_count}字符）→ 宽度 {v['width_mm']}mm",
                width_mm=v["width_mm"],
                height_mm=cfg.get("height_mm"),
                width_in=v.get("width_in"),
                char_count=char_count,
                variant_matched=True,
                rule=cfg["size_variants"].get("rule", ""),
            )

    return ToolResult.ok(
        f"房间号 '{room_number}'（{char_count}字符）无匹配变体，使用默认尺寸",
        width_mm=cfg.get("width_mm"),
        height_mm=cfg.get("height_mm"),
        char_count=char_count,
        variant_matched=False,
    )
