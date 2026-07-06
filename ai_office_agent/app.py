"""应用程序入口与生命周期管理。

集中控制各模块的初始化顺序：日志 -> 配置 -> 数据库 -> 界面。
便于后续维护与扩展，避免初始化逻辑散落各处。
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .config import load_config
from .core.database import Database
from .core.project_profile_repository import init_project_profiles_table
from .core.projects_repository import init_point_dictionary_table, init_projects_table
from .core.scan_controller import init_scan_result_tables
from .core.scan_match_history_repository import init_scan_match_history_table
from .ui.main_window import MainWindow
from .ui.theme import STYLE_SHEET
from .utils.logger import setup_logger


def main() -> int:
    """程序主入口。

    初始化顺序：日志 -> 配置 -> 数据库 -> Qt 应用 -> 主窗口。
    程序退出时负责关闭数据库连接。

    Returns:
        应用程序退出码。
    """
    # 1. 日志最先初始化，保证后续步骤都能记录日志
    logger = setup_logger()
    logger.info("启动 AI Office Agent ...")

    # 2. 加载配置（文件缺失时自动用默认配置生成 settings.json）
    config = load_config()
    logger.info("配置加载完成")

    # 3. 初始化数据库连接并确保核心表存在
    database = Database(config.database.path)
    database.connect()
    # 启动时初始化/迁移所有核心表
    conn = database.connection
    init_projects_table(conn)
    init_point_dictionary_table(conn)
    init_project_profiles_table(conn)
    init_scan_match_history_table(conn)
    init_scan_result_tables(conn)
    logger.info("数据库初始化完成: %s", config.database.path)

    # 4. 创建 Qt 应用程序实例并应用全局样式
    app = QApplication(sys.argv)
    app.setApplicationName("AI Office Agent")
    app.setOrganizationName("AI Office Agent")
    app.setStyleSheet(STYLE_SHEET)

    # 5. 创建并显示主窗口
    window = MainWindow(config=config)
    window.show()
    logger.info("主窗口已显示")

    # 6. 进入 Qt 事件循环；退出时关闭数据库连接
    exit_code = app.exec()
    database.close()
    logger.info("程序退出，退出码: %s", exit_code)
    return exit_code
