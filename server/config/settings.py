from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    coreldraw_app_name: str = "CorelDRAW.Application"
    coreldraw_visible: bool = True
    max_retry_attempts: int = 3
    retry_delay: float = 1.0

    templates_dir: Path = Path("templates")
    output_dir: Path = Path("output")
    logs_dir: Path = Path("logs")

    color_profile_pdf: str = "ISO_Coated_v2"
    dxf_export_version: str = "R14"
    default_dpi: int = 300

    class Config:
        env_prefix = "COREL_"
        case_sensitive = False


settings = Settings()