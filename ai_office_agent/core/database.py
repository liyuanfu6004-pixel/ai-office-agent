"""SQLite 数据库管理模块。

封装数据库连接的建立与关闭。当前阶段仅负责连接管理，
不创建任何数据表；后续业务功能在各自模块中按需建表。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# 复用配置模块中定义的项目根目录
from ..config import PROJECT_ROOT


class Database:
    """SQLite 数据库连接管理器。

    负责建立与关闭数据库连接。路径支持相对路径（相对项目根目录）或绝对路径。
    """

    def __init__(self, path: str) -> None:
        """初始化数据库管理器。

        Args:
            path: 数据库文件路径，相对路径以项目根目录为基准。
        """
        # 相对路径则以项目根目录解析
        db_path = Path(path)
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path
        self.db_path = db_path
        # 真实的 sqlite3 连接，延迟到 connect() 创建
        self._connection: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """建立数据库连接。

        自动创建数据库文件所在目录；连接启用自动提交与外键约束，
        并配置 Row 工厂以便按列名访问结果。

        Returns:
            sqlite3.Connection 数据库连接对象。
        """
        # 确保数据库文件目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = sqlite3.connect(
            self.db_path,
            # 自动提交事务，简化业务层代码
            isolation_level=None,
        )
        # 启用外键约束
        self._connection.execute("PRAGMA foreign_keys = ON")
        # 按列名访问行
        self._connection.row_factory = sqlite3.Row
        return self._connection

    @property
    def connection(self) -> sqlite3.Connection:
        """获取当前连接；未连接时报错。"""
        if self._connection is None:
            raise RuntimeError("数据库尚未连接，请先调用 connect()")
        return self._connection

    @staticmethod
    def open_db_connection(path: str) -> sqlite3.Connection:
        """在调用方所在线程打开独立的数据库连接并返回。

        用于后台线程（如 Excel 导入 Worker）访问数据库——SQLite 连接不可
        跨线程共享，因此子线程需自行建一连。相对路径以项目根目录解析；
        自动建目录、启用外键、Row 工厂，与 Database.connect() 行为一致。

        调用方负责在使用后关闭返回的连接。

        Args:
            path: 数据库文件路径，相对路径以项目根目录为基准。

        Returns:
            新建的 sqlite3.Connection。
        """
        db_path = Path(path)
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(db_path, isolation_level=None)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
