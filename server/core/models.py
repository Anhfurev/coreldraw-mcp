"""Pydantic 数据模型定义"""

from typing import Optional, List, Literal, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator


# ========== 枚举定义 ==========


class Unit(str, Enum):
    """尺寸单位"""
    MM = "mm"
    CM = "cm"
    INCH = "inch"
    POINT = "pt"
    PIXEL = "px"


class ColorMode(str, Enum):
    """颜色模式"""
    CMYK = "CMYK"
    RGB = "RGB"
    PANTONE = "Pantone"
    SPOT = "Spot"


class ExportFormat(str, Enum):
    """导出格式"""
    PDF = "pdf"
    DXF = "dxf"
    AI = "ai"
    SVG = "svg"
    PNG = "png"
    CDR = "cdr"


class BooleanOp(str, Enum):
    """布尔运算类型"""
    UNION = "union"
    INTERSECT = "intersect"
    SUBTRACT = "subtract"
    EXCLUDE = "exclude"


# ========== 文档相关模型 ==========


class DocumentInfo(BaseModel):
    """文档信息"""
    name: Optional[str] = None
    path: Optional[str] = None
    pages: int = 1
    width: float = 0
    height: float = 0
    unit: Unit = Unit.MM
    has_modified: bool = False


class PageInfo(BaseModel):
    """页面信息"""
    index: int
    name: Optional[str] = None
    width: float
    height: float
    unit: Unit = Unit.MM


class SizeInput(BaseModel):
    """尺寸输入"""
    width: float = Field(..., gt=0, description="宽度")
    height: float = Field(..., gt=0, description="高度")
    unit: Unit = Field(default=Unit.MM, description="单位")


# ========== 形状相关模型 ==========


class RectangleInput(BaseModel):
    """矩形创建输入"""
    x: float = Field(..., description="X 坐标")
    y: float = Field(..., description="Y 坐标")
    width: float = Field(..., gt=0, description="宽度")
    height: float = Field(..., gt=0, description="高度")
    corner_radius: Optional[float] = Field(default=0, ge=0, description="圆角半径")


class EllipseInput(BaseModel):
    """椭圆创建输入"""
    cx: float = Field(..., description="中心 X 坐标")
    cy: float = Field(..., description="中心 Y 坐标")
    rx: float = Field(..., gt=0, description="X 轴半径")
    ry: float = Field(..., gt=0, description="Y 轴半径")


class LineInput(BaseModel):
    """直线创建输入"""
    x1: float
    y1: float
    x2: float
    y2: float


class ShapeQuery(BaseModel):
    """形状查询"""
    name: Optional[str] = Field(None, description="按名称查找")
    layer: Optional[str] = Field(None, description="按图层查找")
    type: Optional[str] = Field(None, description="按类型查找")


# ========== 文字相关模型 ==========


class TextStyle(BaseModel):
    """文字样式"""
    font: Optional[str] = Field(None, description="字体名称")
    size: Optional[float] = Field(None, gt=0, description="字号")
    bold: Optional[bool] = Field(None, description="粗体")
    italic: Optional[bool] = Field(None, description="斜体")
    color: Optional[str] = Field(None, description="颜色（CMYK 或 RGB）")
    alignment: Optional[Literal["left", "center", "right"]] = Field(None, description="对齐")
    line_spacing: Optional[float] = Field(None, gt=0, description="行距")
    char_spacing: Optional[float] = Field(None, ge=0, description="字间距")


class TextContentUpdate(BaseModel):
    """文字内容更新"""
    shape_id: str = Field(..., description="形状 ID 或名称")
    content: str = Field(..., description="新文字内容")


# ========== 颜色相关模型 ==========


class CMYKColor(BaseModel):
    """CMYK 颜色"""
    c: float = Field(..., ge=0, le=100, description="青色 0-100")
    m: float = Field(..., ge=0, le=100, description="品红 0-100")
    y: float = Field(..., ge=0, le=100, description="黄色 0-100")
    k: float = Field(..., ge=0, le=100, description="黑色 0-100")


class RGBColor(BaseModel):
    """RGB 颜色"""
    r: int = Field(..., ge=0, le=255, description="红色 0-255")
    g: int = Field(..., ge=0, le=255, description="绿色 0-255")
    b: int = Field(..., ge=0, le=255, description="蓝色 0-255")


class PantoneColor(BaseModel):
    """Pantone 专色"""
    code: str = Field(..., min_length=1, description="Pantone 色号，如 '485 C'")


class FillUpdate(BaseModel):
    """填充更新"""
    shape_id: str
    cmyk: Optional[CMYKColor] = None
    rgb: Optional[RGBColor] = None
    pantone: Optional[PantoneColor] = None
    no_fill: bool = False


class OutlineUpdate(BaseModel):
    """描边更新"""
    shape_id: str
    width: float = Field(..., ge=0, description="描边宽度")
    color_mode: ColorMode = ColorMode.CMYK
    color: Optional[str] = None
    no_outline: bool = False


# ========== 图层相关模型 ==========


class LayerInfo(BaseModel):
    """图层信息"""
    name: str
    visible: bool = True
    locked: bool = False
    color: Optional[str] = Field(None, description="图层颜色标识")


class LayerAssign(BaseModel):
    """图层分配"""
    shape_id: str
    layer_name: str


# ========== 导出相关模型 ==========


class PDFExportOptions(BaseModel):
    """PDF 导出选项"""
    color_profile: str = Field(default="ISO_Coated_v2", description="色彩配置文件")
    bleed: float = Field(default=3.0, ge=0, description="出血 mm")
    crop_marks: bool = Field(default=True, description="是否包含裁切线")
    compression: Literal["none", "jpeg", "zip"] = "zip"
    multi_page: bool = Field(default=False, description="是否多页导出")


class DXFExportOptions(BaseModel):
    """DXF 导出选项"""
    version: Literal["R12", "R14", "R2000", "R2004"] = Field(default="R14")
    layer_filter: Optional[List[str]] = Field(None, description="导出的图层列表")
    export_hidden: bool = Field(default=False, description="是否导出隐藏图层")


class PNGExportOptions(BaseModel):
    """PNG 导出选项"""
    dpi: int = Field(default=300, ge=72, description="分辨率")
    color_mode: ColorMode = ColorMode.RGB
    width: Optional[int] = Field(None, ge=100, description="输出宽度（px）")
    background_transparent: bool = Field(default=False)


# ========== 质检相关模型 ==========


class DimensionCheck(BaseModel):
    """尺寸校验请求"""
    expected_width: float
    expected_height: float
    tolerance: float = Field(default=0.5, ge=0, description="容差 mm")


class ColorReport(BaseModel):
    """色彩报告"""
    rgb_colors: List[Dict[str, Any]] = Field(default_factory=list, description="发现的 RGB 颜色")
    pantone_colors: List[str] = Field(default_factory=list, description="使用的 Pantone 色号")
    spot_colors: List[str] = Field(default_factory=list, description="使用的专色")


class QualityCheckResult(BaseModel):
    """质检结果"""
    passed: bool
    issues: List[str] = Field(default_factory=list)
    details: Optional[Dict[str, Any]] = None


# ========== 数据合并相关模型 ==========


class DataSourceConfig(BaseModel):
    """数据源配置"""
    path: str
    sheet: Optional[int] = Field(default=0, description="工作表索引")
    has_header: bool = Field(default=True, description="是否有表头")


class MergeRecord(BaseModel):
    """单条合并记录"""
    template_path: str
    data: Dict[str, str]
    output_path: str


class BatchMergeConfig(BaseModel):
    """批量合并配置"""
    template_path: str
    data_path: str
    output_dir: str
    naming_pattern: str = Field(default="{room}", description="输出文件命名模式")


# ========== 条码相关模型 ==========


class BarcodeSpec(BaseModel):
    """条码规格"""
    type: Literal["code128", "ean13", "code39", "qr"] = Field(..., description="条码类型")
    data: str = Field(..., min_length=1)
    x: float = Field(..., description="X 坐标")
    y: float = Field(..., description="Y 坐标")
    width: float = Field(..., gt=0, description="宽度")
    height: float = Field(..., gt=0, description="高度")


# ========== 工具返回结果模型 ==========


class ToolResult(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, msg: Optional[str] = None, **data) -> "ToolResult":
        return cls(success=True, message=msg, data=data if data else None)

    @classmethod
    def fail(cls, err: str, msg: Optional[str] = None) -> "ToolResult":
        return cls(success=False, error=err, message=msg)


# ========== 工具上下文 ==========


class ToolContext(BaseModel):
    """工具调用上下文（自动注入）"""
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: Optional[str] = None