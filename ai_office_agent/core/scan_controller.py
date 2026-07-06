"""扫描控制器 — v1.4 引入。

统一扫描入口，管理完整的扫描生命周期：

Step1：读取数据
    - point_dictionary
    - scan_match_history
    - scan_result_cache

Step2：执行扫描
    - scanner.scan_project()

Step3：匹配分析
    - matcher.match_file_to_points()

Step4：生成结果
    - ScanResultItem / Summary

Step5：写入数据库（必须）
    - scan_result
    - file_ownership
    - scan_match_history update

正确交互流程：
    进入项目 → 加载数据库结果（不扫描）
    用户点击"扫描" → 执行 scan → 写入 scan_result + ownership + history → 刷新 UI

禁止行为：
    - 禁止"只读不写"（scan → 只生成UI结果，不落库）
    - 禁止"扫描不闭环"（scan → UI显示 → 不更新 scan_result）
    - 禁止 on_project_open → scan_project()
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.logger import setup_logger

logger = setup_logger()


def _now_iso() -> str:
    """当前 UTC 时间的 ISO8601 字符串。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ====================================================================
# scan_result 表管理（持久化扫描结果）
# ====================================================================

_SCAN_RESULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_result (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL,
    point_id            INTEGER NOT NULL,
    standard_point_name TEXT    NOT NULL,
    county              TEXT,
    matched_folder      TEXT,
    matched_folder_path TEXT,
    match_score         REAL    NOT NULL DEFAULT 0.0,
    match_status        TEXT    NOT NULL DEFAULT 'NOT_FOUND',
    cad_status          TEXT    NOT NULL DEFAULT '无',
    budget_status       TEXT    NOT NULL DEFAULT '无',
    cad_file_count      INTEGER NOT NULL DEFAULT 0,
    budget_file_count   INTEGER NOT NULL DEFAULT 0,
    suggestion          TEXT,
    confirmed           INTEGER NOT NULL DEFAULT 0,
    match_method        TEXT    NOT NULL DEFAULT 'fuzzy',
    file_owner_point_id INTEGER,
    match_confidence    REAL    NOT NULL DEFAULT 0.0,
    scanned_files       TEXT,
    dynamic_data        TEXT,
    scan_time           TEXT    NOT NULL,
    scan_directory      TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (point_id) REFERENCES point_dictionary(id) ON DELETE CASCADE
)
"""

_FILE_OWNERSHIP_SCHEMA = """
CREATE TABLE IF NOT EXISTS file_ownership (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL,
    point_id            INTEGER NOT NULL,
    file_path           TEXT    NOT NULL,
    file_name           TEXT    NOT NULL,
    match_score         REAL    NOT NULL DEFAULT 0.0,
    ownership_time      TEXT    NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (point_id) REFERENCES point_dictionary(id) ON DELETE CASCADE
)
"""


def init_scan_result_tables(conn) -> None:
    """初始化 scan_result 和 file_ownership 表（幂等）。"""
    import sqlite3
    conn.execute(_SCAN_RESULT_SCHEMA)
    conn.execute(_FILE_OWNERSHIP_SCHEMA)
    # 索引
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scan_result_project "
        "ON scan_result (project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scan_result_point "
        "ON scan_result (project_id, point_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_ownership_project "
        "ON file_ownership (project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_ownership_point "
        "ON file_ownership (project_id, point_id)"
    )
    conn.commit()
    logger.info("scan_result / file_ownership 表已就绪（v1.4）")


def clear_scan_results(conn, project_id: int) -> int:
    """清空指定项目的扫描结果（可重入）。"""
    cur = conn.execute(
        "DELETE FROM scan_result WHERE project_id = ?", (project_id,)
    )
    deleted = cur.rowcount
    conn.commit()
    return deleted


def clear_file_ownership(conn, project_id: int) -> int:
    """清空指定项目的文件归属记录。"""
    cur = conn.execute(
        "DELETE FROM file_ownership WHERE project_id = ?", (project_id,)
    )
    deleted = cur.rowcount
    conn.commit()
    return deleted


def save_scan_results(
    conn,
    project_id: int,
    items: list,
    scan_directory: str = "",
) -> int:
    """批量写入扫描结果到 scan_result 表。

    Args:
        conn: 数据库连接。
        project_id: 项目 ID。
        items: ScanResultItem 列表。
        scan_directory: 扫描目录。

    Returns:
        写入的记录数。
    """
    scan_time = _now_iso()
    records = []
    for item in items:
        records.append((
            project_id,
            item.point_id,
            item.standard_point_name,
            item.county,
            item.matched_folder,
            item.matched_folder_path,
            item.match_score,
            item.match_status.name,
            item.cad_status,
            item.budget_status,
            item.cad_file_count,
            item.budget_file_count,
            item.suggestion,
            1 if item.confirmed else 0,
            item.match_method,
            item.file_owner_point_id,
            item.match_confidence,
            json.dumps(item.scanned_files, ensure_ascii=False),
            json.dumps(item.dynamic_data, ensure_ascii=False) if item.dynamic_data else None,
            scan_time,
            scan_directory,
        ))

    if not records:
        return 0

    conn.executemany(
        """
        INSERT INTO scan_result
            (project_id, point_id, standard_point_name, county,
             matched_folder, matched_folder_path, match_score, match_status,
             cad_status, budget_status, cad_file_count, budget_file_count,
             suggestion, confirmed, match_method,
             file_owner_point_id, match_confidence,
             scanned_files, dynamic_data, scan_time, scan_directory)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    logger.info("scan_result 写入完成：项目 id=%s，%d 条", project_id, len(records))
    return len(records)


def save_file_ownership_batch(
    conn,
    project_id: int,
    ownership_records: list[dict],
) -> int:
    """批量写入文件唯一归属记录。

    Args:
        conn: 数据库连接。
        project_id: 项目 ID。
        ownership_records: [{point_id, file_path, file_name, match_score}]

    Returns:
        写入的记录数。
    """
    now = _now_iso()
    records = [
        (project_id, r["point_id"], r["file_path"], r["file_name"],
         r.get("match_score", 0.0), now)
        for r in ownership_records
    ]

    if not records:
        return 0

    conn.executemany(
        """
        INSERT INTO file_ownership
            (project_id, point_id, file_path, file_name, match_score, ownership_time)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    logger.info(
        "file_ownership 写入完成：项目 id=%s，%d 条",
        project_id, len(records),
    )
    return len(records)


def load_scan_results_from_db(
    conn,
    project_id: int,
) -> list[dict] | None:
    """从数据库加载已有的扫描结果。

    Returns:
        扫描结果 dict 列表，如果无缓存返回 None。
    """
    cur = conn.execute(
        """
        SELECT * FROM scan_result
        WHERE project_id = ?
        ORDER BY id ASC
        """,
        (project_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return None

    from .scan_result import MatchStatus, ScanResultItem

    results = []
    for row in rows:
        scanned_files = []
        if row["scanned_files"]:
            try:
                scanned_files = json.loads(row["scanned_files"])
            except json.JSONDecodeError:
                pass

        dynamic_data = {}
        if row["dynamic_data"]:
            try:
                dynamic_data = json.loads(row["dynamic_data"])
            except json.JSONDecodeError:
                pass

        match_status = MatchStatus.NOT_FOUND
        try:
            match_status = MatchStatus[row["match_status"]]
        except KeyError:
            pass

        item = ScanResultItem(
            point_id=row["point_id"],
            standard_point_name=row["standard_point_name"],
            county=row["county"] or "",
            matched_folder=row["matched_folder"],
            matched_folder_path=row["matched_folder_path"],
            match_score=row["match_score"],
            match_status=match_status,
            cad_status=row["cad_status"] or "无",
            budget_status=row["budget_status"] or "无",
            cad_file_count=row["cad_file_count"],
            budget_file_count=row["budget_file_count"],
            suggestion=row["suggestion"] or "",
            confirmed=bool(row["confirmed"]),
            match_method=row["match_method"] or "fuzzy",
            file_owner_point_id=row["file_owner_point_id"],
            match_confidence=row["match_confidence"],
            scanned_files=scanned_files,
            dynamic_data=dynamic_data,
        )
        results.append(item)

    logger.info(
        "从数据库加载扫描结果：项目 id=%s，%d 条",
        project_id, len(results),
    )
    return results


# ====================================================================
# 扫描控制器（统一入口）
# ====================================================================


class ScanController:
    """扫描控制器 — 管理完整的扫描生命周期。

    唯一扫描入口，所有扫描操作必须通过本控制器。

    正确流程：
        run_scan(project_id, path)
            → Step1: 读取数据
            → Step2: 执行扫描
            → Step3: 匹配分析
            → Step4: 生成结果
            → Step5: 写入数据库（scan_result + file_ownership + history）
            → 返回 ScanResultSummary
    """

    @staticmethod
    def load_cached_results(
        conn,
        project_id: int,
    ) -> dict | None:
        """仅加载缓存的扫描结果（不触发扫描）。

        用于项目打开时快速显示已有结果。
        """
        items = load_scan_results_from_db(conn, project_id)
        if items is None:
            return None

        from .scan_result import ScanResultSummary
        summary = ScanResultSummary.from_items(
            items=items,
            project_id=project_id,
            project_name="",
            scan_directory="",
            scan_duration_ms=0,
        )
        return summary.to_dict()

    @staticmethod
    def run_scan(
        project_id: int,
        project_name: str,
        points: list[dict],
        scan_directory: str = "",
        db_path: str | None = None,
    ) -> dict:
        """执行完整扫描流程并写入数据库。

        这是唯一的扫描入口。所有扫描操作必须通过此方法。

        Args:
            project_id: 项目 ID。
            project_name: 项目名称。
            points: point_dictionary 点位列表。
            scan_directory: 扫描根目录路径。
            db_path: 数据库路径。

        Returns:
            ScanResultSummary.to_dict()。
        """
        import time
        from .scan_result import build_scan_results, ScanResultSummary
        from .database import Database
        from . import scan_match_history_repository as smhr

        start_time = time.perf_counter()
        logger.info(
            "ScanController.run_scan 开始：项目=%s (id=%s)，%d 个点位",
            project_name, project_id, len(points),
        )

        # ── Step1-4：执行扫描 + 匹配 + 生成结果 ──
        summary = build_scan_results(
            project_id=project_id,
            project_name=project_name,
            points=points,
            scan_directory=scan_directory,
            db_path=db_path,
        )

        if db_path is None:
            logger.warning("db_path 为空，跳过数据库写入")
            return summary.to_dict()

        # ── Step5：写入数据库 ──
        conn = Database.open_db_connection(db_path)
        try:
            # 5a. 清空旧结果（可重入）
            clear_scan_results(conn, project_id)
            clear_file_ownership(conn, project_id)

            # 5b. 写入 scan_result
            save_scan_results(
                conn, project_id, summary.items,
                scan_directory=summary.scan_directory,
            )

            # 5c. 写入 file_ownership（唯一归属）
            ownership_records = _collect_ownership_from_items(summary.items)
            save_file_ownership_batch(conn, project_id, ownership_records)

            # 5d. 更新 scan_match_history（已确认的点位）
            _update_match_history_from_items(
                conn, project_id, summary.items, smhr,
            )

        finally:
            conn.close()

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            "ScanController.run_scan 完成：%d 点位，%d 匹配，%d 未匹配，耗时=%dms",
            summary.total_points, summary.matched_count,
            summary.not_found_count, elapsed_ms,
        )

        return summary.to_dict()


def _collect_ownership_from_items(items: list) -> list[dict]:
    """从 ScanResultItem 列表收集文件唯一归属记录。"""
    records = []
    for item in items:
        if item.file_owner_point_id is not None and item.matched_folder_path:
            records.append({
                "point_id": item.point_id,
                "file_path": item.matched_folder_path,
                "file_name": item.matched_folder or "",
                "match_score": item.match_score,
            })
    return records


def _update_match_history_from_items(
    conn,
    project_id: int,
    items: list,
    smhr,
) -> None:
    """将已确认的点位写入 scan_match_history 表。"""
    for item in items:
        if item.confirmed and item.matched_folder:
            try:
                smhr.save_match_history(
                    conn,
                    project_id,
                    item.standard_point_name,
                    item.matched_folder,
                    item.match_method,
                )
            except Exception as exc:
                logger.warning(
                    "保存匹配历史失败（%s）：%s",
                    item.standard_point_name, exc,
                )
