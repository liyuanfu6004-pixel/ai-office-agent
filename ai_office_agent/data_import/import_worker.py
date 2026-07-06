"""导入后台 Worker。

在独立线程中执行导入：
1. load：读取 Excel + 动态识别表头（耗时，发 loaded 信号回主线程）
2. run_import：按映射写入 SQLite

v0.6.0 语义（总体项目表为唯一主数据源，全量替换）：
- 导入前清空 projects 全表，再插入本次读取的数据（总体表是唯一来源，
  重导即全量替换，不留旧数据）
- project_type 按 Excel"项目类型列"分流；类型列为空或无法识别时
  project_type 写 NULL，该项目只显示在"全部项目"页
- county_count / site_count / completion_rate 不来自总体表，统一为 0
  （待规模表统计）
- 字段映射仅 5 项：项目名称（必填）、项目编码（必填）、年份/项目类型/状态（可选）

Worker 是 QObject，由"全部项目"页创建后 moveToThread 到工作线程。两段都为
无参槽，用无参信号 start_load / start_run_import 触发，回调用 QueuedConnection
回主线程。Worker 自行创建并关闭数据库连接。
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import QObject, Signal, Slot

from ..config import AppConfig
from ..core import project_categories, projects_repository
from ..core.database import Database
from ..data_import.excel_reader import read_sheet
from ..utils.logger import setup_logger

logger = setup_logger()


class ImportWorker(QObject):
    """Excel 导入后台 Worker。"""

    # 读取阶段完成：返回 (headers, data_rows)
    loaded = Signal(object, object)
    # 导入成功：返回 (总行数, 跳过的无项目名称行数)
    succeeded = Signal(int, int)
    # 导入失败：返回错误消息
    failed = Signal(str)
    # 进度（0~100）
    progress = Signal(int, str)

    start_load = Signal()
    start_run_import = Signal()

    def __init__(
        self,
        path: str,
        config: AppConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._config = config
        self._mapping: dict[str, str | None] | None = None

        self.start_load.connect(self.load)
        self.start_run_import.connect(self.run_import)

    def set_mapping(self, mapping: dict[str, str | None]) -> None:
        """主线程在用户确认字段映射后调用。"""
        self._mapping = mapping

    # ------------------------------------------------------------------ 读取

    @Slot()
    def load(self) -> None:
        """读取 Excel 并发出 loaded 信号。"""
        self.progress.emit(5, "正在读取 Excel ...")
        try:
            headers, data_rows = read_sheet(self._path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Excel 读取失败")
            self.failed.emit(f"读取 Excel 失败：{exc}")
            return
        if not data_rows:
            self.failed.emit("Excel 中没有数据行，请检查文件内容。")
            return
        self.progress.emit(20, f"读取完成：{len(data_rows)} 行")
        self.loaded.emit(headers, data_rows)

    # ------------------------------------------------------------------ 入库

    @Slot()
    def run_import(self) -> None:
        """按映射写入数据库（全量替换）。"""
        if self._mapping is None:
            self.failed.emit("尚未设置字段映射。")
            return

        self.progress.emit(25, "重新读取 Excel ...")
        try:
            _headers, data_rows = read_sheet(self._path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("读取 Excel 失败")
            self.failed.emit(f"读取 Excel 失败：{exc}")
            return

        if not data_rows:
            self.failed.emit("Excel 中没有数据行，请检查文件内容。")
            return

        self.progress.emit(40, "解析数据 ...")
        repo_rows: list[dict] = []
        skipped_no_name = 0
        for r, row in enumerate(data_rows):
            raw_name = _cell(row, self._mapping.get("project_name"))
            raw_code = _cell(row, self._mapping.get("project_code"))

            # 项目名称必填，缺失跳过
            if project_categories.normalize(raw_name) == "":
                logger.warning("第 %d 行缺少项目名称，跳过", r + 1)
                skipped_no_name += 1
                continue

            # 项目类型：有值则分流，无值/无法识别则 None（只显示在全部项目）
            raw_type = _cell(row, self._mapping.get("project_type"))
            category = (
                project_categories.resolve_category(raw_type)
                if raw_type is not None
                else None
            )

            repo_rows.append(
                {
                    "project_name": raw_name,
                    "project_code": raw_code,
                    "project_type": category,  # None 表示未分类
                    "year": _cell(row, self._mapping.get("year")),
                    "status": (
                        None
                        if not self._mapping.get("status")
                        else _cell(row, self._mapping.get("status"))
                    ),
                }
            )

        if not repo_rows:
            self.failed.emit("解析后没有可导入的有效数据（请检查项目名称列映射）。")
            return

        self.progress.emit(60, "写入数据库 ...")
        conn: sqlite3.Connection | None = None
        try:
            conn = Database.open_db_connection(self._config.database.path)
            projects_repository.init_projects_table(conn)
            # 总体项目表是唯一主数据源，导入即全量替换
            conn.execute("DELETE FROM projects")
            conn.commit()
            self.progress.emit(70, f"写入 {len(repo_rows)} 条 ...")
            inserted = projects_repository.insert_projects(conn, repo_rows)
            self.progress.emit(95, "收尾 ...")
            self.succeeded.emit(inserted, skipped_no_name)
        except Exception as exc:  # noqa: BLE001
            logger.exception("写入数据库失败")
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            self.failed.emit(f"写入数据库失败：{exc}")
        finally:
            if conn is not None:
                conn.close()


def _cell(row: dict, header: str | None):
    """从行字典中按表头取值；表头为 None 时返回 None。"""
    if not header:
        return None
    return row.get(header)
