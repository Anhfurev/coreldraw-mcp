import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastmcp import FastMCP
from loguru import logger

load_dotenv(Path(__file__).parent.parent / ".env")

from core.connection import init_connection, close_connection, get_connection
from core.models import ToolResult


_MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")
_MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
_MCP_PORT = int(os.environ.get("MCP_PORT", "8765"))

mcp = FastMCP("coreldraw-signage")


def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    logger.add(
        "logs/server.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    )


def register_tools():
    from tools import document, shapes, text, colors, layers, export, preflight, data_merge, templates, engineering, vision, jersey

    mcp.add_tool(document.open_template)
    mcp.add_tool(document.create_document)
    mcp.add_tool(document.save_document)
    mcp.add_tool(document.close_document)
    mcp.add_tool(document.add_page)
    mcp.add_tool(document.set_page_size)
    mcp.add_tool(document.get_document_info)
    mcp.add_tool(document.list_all_text_shapes)
    mcp.add_tool(document.add_guideline)
    mcp.add_tool(document.switch_page)
    mcp.add_tool(document.delete_page)

    mcp.add_tool(shapes.create_rectangle)
    mcp.add_tool(shapes.create_ellipse)
    mcp.add_tool(shapes.create_line)
    mcp.add_tool(shapes.import_svg)
    mcp.add_tool(shapes.import_image)
    mcp.add_tool(shapes.set_shape_size)
    mcp.add_tool(shapes.set_shape_position)
    mcp.add_tool(shapes.boolean_operation)
    mcp.add_tool(shapes.convert_to_curves)
    mcp.add_tool(shapes.group_shapes)
    mcp.add_tool(shapes.find_shape_by_name)
    mcp.add_tool(shapes.align_shapes)
    mcp.add_tool(shapes.distribute_shapes)
    mcp.add_tool(shapes.set_z_order)
    mcp.add_tool(shapes.delete_shape)
    mcp.add_tool(shapes.rotate_shape)
    mcp.add_tool(shapes.ungroup_shapes)
    mcp.add_tool(shapes.scale_shape)
    mcp.add_tool(shapes.select_shapes)
    mcp.add_tool(shapes.powerclip)
    mcp.add_tool(shapes.rename_shape)
    mcp.add_tool(shapes.duplicate_shape)
    mcp.add_tool(shapes.duplicate_shape_batch)
    mcp.add_tool(shapes.duplicate_shapes)
    mcp.add_tool(shapes.set_shape_locked)
    mcp.add_tool(shapes.flip_shape)

    mcp.add_tool(text.set_text_content)
    mcp.add_tool(text.get_text_content)
    mcp.add_tool(text.set_text_style)
    mcp.add_tool(text.fit_text_to_frame)
    mcp.add_tool(text.check_text_overflow)
    mcp.add_tool(text.convert_text_to_curves)
    mcp.add_tool(text.create_text_frame)
    mcp.add_tool(text.create_artistic_text)

    mcp.add_tool(colors.set_fill_cmyk)
    mcp.add_tool(colors.set_fill_rgb)
    mcp.add_tool(colors.set_fill_pantone)
    mcp.add_tool(colors.set_outline)
    mcp.add_tool(colors.set_no_fill)
    mcp.add_tool(colors.set_no_outline)
    mcp.add_tool(colors.check_rgb_colors)
    mcp.add_tool(colors.set_fountain_fill)
    mcp.add_tool(colors.set_transparency)

    mcp.add_tool(layers.create_layer)
    mcp.add_tool(layers.get_layers)
    mcp.add_tool(layers.assign_to_layer)
    mcp.add_tool(layers.set_layer_visible)
    mcp.add_tool(layers.lock_layer)

    mcp.add_tool(export.export_pdf)
    mcp.add_tool(export.export_dxf)
    mcp.add_tool(export.export_ai)
    mcp.add_tool(export.export_svg)
    mcp.add_tool(export.export_png)
    mcp.add_tool(export.export_jpeg)
    mcp.add_tool(export.export_preview_png)
    mcp.add_tool(export.batch_export)

    mcp.add_tool(preflight.check_dimensions)
    mcp.add_tool(preflight.check_text_overflow_all)
    mcp.add_tool(preflight.check_missing_fonts)
    mcp.add_tool(preflight.get_color_report)

    mcp.add_tool(templates.list_templates)
    mcp.add_tool(templates.get_template_info)
    mcp.add_tool(templates.get_size_variant)

    mcp.add_tool(engineering.populate_title_block)
    mcp.add_tool(engineering.assemble_engineering_drawing)

    mcp.add_tool(data_merge.read_excel_data)
    mcp.add_tool(data_merge.merge_record)
    mcp.add_tool(data_merge.batch_merge)
    mcp.add_tool(data_merge.generate_barcode)
    mcp.add_tool(data_merge.generate_qrcode)

    mcp.add_tool(vision.view_canvas)

    mcp.add_tool(jersey.scan_jersey_rows)
    mcp.add_tool(jersey.set_jersey_player)
    mcp.add_tool(jersey.set_jersey_players)
    mcp.add_tool(jersey.duplicate_jersey_rows)


def main():
    setup_logging()
    logger.info("启动 CorelDRAW Signage MCP Server...")

    if init_connection():
        logger.info("CorelDRAW 连接成功")
    else:
        logger.warning("CorelDRAW 连接失败，服务器将启动但功能受限")

    register_tools()
    logger.info("工具注册完成")

    if _MCP_TRANSPORT != "stdio":
        logger.info(f"HTTP 模式启动，监听 http://{_MCP_HOST}:{_MCP_PORT}/mcp")
        logger.info("本地 Claude/OpenCode 可通过 .mcp.json 中的 url 连接")

    try:
        if _MCP_TRANSPORT != "stdio":
            mcp.run(transport=_MCP_TRANSPORT, host=_MCP_HOST, port=_MCP_PORT)
        else:
            mcp.run(transport=_MCP_TRANSPORT)
    finally:
        close_connection()
        logger.info("MCP Server 已关闭")


if __name__ == "__main__":
    main()