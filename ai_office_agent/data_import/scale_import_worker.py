"""规模表导入后台 Worker — v1.1 引入。

在独立线程中执行规模表导入：
1. 按已确认的字段映射，从 data_rows 构建点位字典记录
2. 写入 point_dictionary 表（先清空本项目旧数据，保证可重入）
3. 保存 project_profiles 配置（供下次导入复用）

与 ImportWorker 的区别：
- 不操作 projects 表（那是总体项目表的职责）
- 操作 point_dictionary 表 + project_profiles 表
- 支持动态字段（规模表特有字段写入 dynamic_data）
- 支持点位生成规则（单字段 / 起点+终点拼接）
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import QObject, Signal, Slot

from ..config import AppConfig
from ..core import project_profile_repository, projects_repository
from ..core.database import Database
from ..core.scale_table_engine import build_point_records
from ..utils.logger import setup_logger

logger = setup_logger()


class ScaleImportWorker(QObject):
    """规模表导入后台 Worker。

    用法：
    1. 构造 → moveToThread
    2. 主线程调用 set_params(project_id, mapping, dynamic_fields, use_concatenation)
    3. 主线程 emit start_import → run_import 执行
    4. 接收 succeeded / failed / progress 信号
    """

    # 导入成功：(inserted, skipped)
    succeeded = Signal(int, int)
    # 导入失败：错误消息
    failed = Signal(str)
    # 进度：0~100，描述
    progress = Signal(int, str)

    start_import = Signal()

    def __init__(
        self,
        data_rows: list[dict],
        config: AppConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._data_rows = data_rows
        self._config = config
        self._project_id: int | None = None
        self._mapping: dict | None = None
        self._dynamic_fields: list[dict] = []
        self._use_concatenation: bool = False
        self._sheet_name: str | None = None

        self.start_import.connect(self.run_import)

    def set_params(
        self,
        project_id: int,
        mapping: dict,
        dynamic_fields: list[dict],
        use_concatenation: bool,
        sheet_name: str | None = None,
    ) -> None:
        """主线程在用户确认后调用。

        Args:
            project_id: 目标项目 ID。
            mapping: 字段映射 {point_name, county, start_point, end_point}。
            dynamic_fields: 动态字段列表 [{name, label, type}]。
            use_concatenation: 是否起点+终点拼接。
            sheet_name: 用户选择的 Sheet 名称。
        """
        self._project_id = project_id
        self._mapping = mapping
        self._dynamic_fields = dynamic_fields
        self._use_concatenation = use_concatenation
        self._sheet_name = sheet_name

    # ------------------------------------------------------------------ 入库

    @Slot()
    def run_import(self) -> None:
        """按映射构建点位记录 → 写库 → 保存配置（v1.2.1 增强异常处理）。"""
        try:
            self._do_run_import()
        except Exception as exc:
            logger.exception("规模表导入未处理异常")
            self.failed.emit(f"导入过程发生意外错误：{exc}")

    def _do_run_import(self) -> None:
        """导入主逻辑。"""
        if self._project_id is None:
            self.failed.emit("未设置目标项目。")
            return
        if self._mapping is None:
            self.failed.emit("未设置字段映射。")
            return
        if not self._data_rows:
            self.failed.emit("没有可导入的数据行。")
            return

        self.progress.emit(10, "解析数据 ...")

        # 构建点位记录
        try:
            records = build_point_records(
                self._data_rows,
                self._mapping,
                self._dynamic_fields,
                self._use_concatenation,
            )
        except Exception as exc:
            logger.exception("构建点位记录失败")
            self.failed.emit(f"解析数据时出错：{exc}")
            return

        if not records:
            self.failed.emit("未能从数据中识别到任何有效点位，请检查字段映射。")
            return

        self.progress.emit(40, f"生成 {len(records)} 条点位记录 ...")

        # 将动态字段序列化为 JSON 存入 original_name 的扩展
        # （original_name 用于溯源，dynamic_data 另存）
        conn: sqlite3.Connection | None = None
        try:
            conn = Database.open_db_connection(self._config.database.path)
            projects_repository.init_point_dictionary_table(conn)
            project_profile_repository.init_project_profiles_table(conn)

            # 先清空本项目旧点位（保证可重入）
            projects_repository.clear_points_by_project(conn, self._project_id)

            self.progress.emit(60, "写入数据库 ...")

            # 批量插入点位字典
            inserted = projects_repository.insert_points(
                conn, self._project_id, records
            )

            self.progress.emit(80, "保存配置 ...")

            # 保存项目配置（下次导入复用）
            project_profile_repository.upsert_profile(
                conn,
                self._project_id,
                {
                    "sheet_name": self._sheet_name,
                    "point_name_field": self._mapping.get("point_name"),
                    "county_field": self._mapping.get("county"),
                    "start_point_field": self._mapping.get("start_point"),
                    "end_point_field": self._mapping.get("end_point"),
                    "use_concatenation": self._use_concatenation,
                    "dynamic_fields": self._dynamic_fields,
                },
            )

            self.progress.emit(100, f"导入完成：{inserted} 条")
            self.succeeded.emit(inserted, 0)

        except Exception as exc:
            logger.exception("规模表导入失败")
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            self.failed.emit(f"导入失败：{exc}")
        finally:
            if conn is not None:
                conn.close()
