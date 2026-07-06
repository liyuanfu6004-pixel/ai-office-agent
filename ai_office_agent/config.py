"""配置管理模块。

负责加载与保存应用程序配置。配置采用 JSON 格式存储于 config/settings.json。
若配置文件缺失，则使用内置默认配置并自动生成文件，保证首次运行即可启动。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# 项目根目录：本文件位于 ai_office_agent/config.py，向上回退一级即根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 配置文件目录与路径
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "settings.json"
# 日志目录
LOG_DIR = PROJECT_ROOT / "logs"


@dataclass
class DatabaseConfig:
    """数据库相关配置。"""

    # 数据库文件路径（相对项目根目录）
    path: str = "data/ai_office_agent.db"
    # SQLite 连接超时（秒），暂未启用，预留给业务使用
    timeout: float = 5.0


@dataclass
class UIConfig:
    """界面相关配置。"""

    # 主窗口默认宽度（像素）
    width: int = 1280
    # 主窗口默认高度（像素）
    height: int = 800
    # 左侧树形导航默认宽度（像素）
    nav_width: int = 260
    # 应用程序窗口标题
    title: str = "AI Office Agent"


@dataclass
class AppConfig:
    """应用总体配置，聚合各子配置。"""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化为 JSON 的字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        """从字典构造配置，缺失字段使用默认值。"""
        db = DatabaseConfig(**(data.get("database") or {}))
        ui = UIConfig(**(data.get("ui") or {}))
        return cls(database=db, ui=ui)


def load_config() -> AppConfig:
    """加载配置。

    - 配置文件不存在：使用默认配置并写入文件。
    - 配置文件存在：读取并解析。
    - 解析异常：回退到默认配置，保证程序可启动。

    Returns:
        AppConfig 配置对象。
    """
    if not CONFIG_FILE.exists():
        config = AppConfig()
        save_config(config)
        return config

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return AppConfig.from_dict(data)
    except (json.JSONDecodeError, TypeError) as exc:
        # 配置损坏时回退默认值，避免程序无法启动
        print(f"[警告] 配置文件解析失败，使用默认配置: {exc}")
        return AppConfig()


def save_config(config: AppConfig) -> None:
    """将配置写入 JSON 文件。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
