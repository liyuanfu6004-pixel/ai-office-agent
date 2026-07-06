"""日志工具模块。

提供统一的日志配置。日志同时输出到控制台与 logs/app.log 文件。
"""
from __future__ import annotations

import logging

from ..config import LOG_DIR, PROJECT_ROOT  # noqa: F401  (PROJECT_ROOT 保留供外部引用)

# 日志文件名
LOG_FILE = LOG_DIR / "app.log"
# 统一的日志器名称
LOGGER_NAME = "ai_office_agent"


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    """配置并返回根日志记录器。

    日志同时输出到控制台与文件（logs/app.log）。
    重复调用不会重复添加处理器，便于多模块安全调用。

    Args:
        level: 日志级别，默认 INFO。

    Returns:
        配置好的 Logger。
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    # 已配置过则直接返回，避免重复添加处理器
    if logger.handlers:
        return logger

    # 日志格式：时间 级别 模块:行号 消息
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台处理器
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 文件处理器（自动创建 logs 目录）
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
