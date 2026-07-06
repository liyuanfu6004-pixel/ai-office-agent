"""扫描匹配历史记录仓储 — v1.2.2 引入。

scan_match_history 表保存用户的人工确认/重新匹配结果，
供下次扫描时优先使用历史记录，跳过模糊匹配。

表结构：
    id                  INTEGER PRIMARY KEY AUTOINCREMENT
    project_id          INTEGER NOT NULL          -- 关联 projects(id)
    standard_point_name TEXT NOT NULL             -- 标准点位名称
    actual_folder       TEXT NOT NULL             -- 实际匹配到的文件夹名称
    match_method        TEXT NOT NULL DEFAULT 'manual'  -- fuzzy / history / manual
    confirmed_by        TEXT DEFAULT NULL         -- 确认人（预留）
    confirmed_at        TEXT NOT NULL             -- ISO 格式确认时间
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

使用方式：
    1. 用户确认/重新匹配 → save_match_history()
    2. 下次扫描 → fetch_project_history() → 按 standard_point_name 查找
    3. 历史命中 → 跳过模糊匹配，直接使用历史文件夹
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..utils.logger import setup_logger

logger = setup_logger()

_TABLE_NAME = "scan_match_history"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_match_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL,
    standard_point_name TEXT    NOT NULL,
    actual_folder       TEXT    NOT NULL,
    match_method        TEXT    NOT NULL DEFAULT 'manual',
    confirmed_by        TEXT    DEFAULT NULL,
    confirmed_at        TEXT    NOT NULL,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
)
"""

_INDEX_PROJECT = """
CREATE INDEX IF NOT EXISTS idx_scan_history_project
ON scan_match_history (project_id)
"""

_INDEX_POINT = """
CREATE INDEX IF NOT EXISTS idx_scan_history_point
ON scan_match_history (project_id, standard_point_name)
"""


def init_scan_match_history_table(conn: sqlite3.Connection) -> None:
    """创建 scan_match_history 表（幂等）。"""
    conn.execute(_SCHEMA)
    conn.execute(_INDEX_PROJECT)
    conn.execute(_INDEX_POINT)
    conn.commit()
    logger.info("scan_match_history 表已就绪（v1.2.2）")


def save_match_history(
    conn: sqlite3.Connection,
    project_id: int,
    standard_point_name: str,
    actual_folder: str,
    match_method: str = "manual",
    confirmed_by: str | None = None,
) -> int:
    """保存一条匹配历史记录（INSERT OR REPLACE 语义：同项目+同点位则更新）。

    Returns:
        插入/更新的记录 id。
    """
    confirmed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 先删除同项目+同点位的旧记录（实现 upsert）
    conn.execute(
        "DELETE FROM scan_match_history WHERE project_id = ? AND standard_point_name = ?",
        (project_id, standard_point_name),
    )

    cur = conn.execute(
        """
        INSERT INTO scan_match_history
            (project_id, standard_point_name, actual_folder, match_method,
             confirmed_by, confirmed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            standard_point_name,
            actual_folder,
            match_method,
            confirmed_by,
            confirmed_at,
        ),
    )
    conn.commit()
    record_id = cur.lastrowid
    logger.debug(
        "匹配历史已保存：project_id=%s point=%s folder=%s method=%s",
        project_id, standard_point_name, actual_folder, match_method,
    )
    return record_id


def fetch_project_history(
    conn: sqlite3.Connection,
    project_id: int,
) -> dict[str, dict]:
    """获取项目下所有匹配历史，返回 {standard_point_name: {...}} 映射。

    Returns:
        {standard_point_name: {actual_folder, match_method, confirmed_at, confirmed_by}}
    """
    cur = conn.execute(
        """
        SELECT standard_point_name, actual_folder, match_method,
               confirmed_at, confirmed_by
        FROM scan_match_history
        WHERE project_id = ?
        ORDER BY confirmed_at DESC
        """,
        (project_id,),
    )
    result: dict[str, dict] = {}
    for row in cur.fetchall():
        pname = row["standard_point_name"]
        # 保留最新一条（已按 DESC 排序）
        if pname not in result:
            result[pname] = {
                "actual_folder": row["actual_folder"],
                "match_method": row["match_method"],
                "confirmed_at": row["confirmed_at"],
                "confirmed_by": row["confirmed_by"],
            }
    return result


def fetch_match_by_point(
    conn: sqlite3.Connection,
    project_id: int,
    standard_point_name: str,
) -> dict | None:
    """查询特定点位的历史匹配记录。

    Returns:
        None 如果没有历史记录。
    """
    cur = conn.execute(
        """
        SELECT actual_folder, match_method, confirmed_at, confirmed_by
        FROM scan_match_history
        WHERE project_id = ? AND standard_point_name = ?
        ORDER BY confirmed_at DESC
        LIMIT 1
        """,
        (project_id, standard_point_name),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "actual_folder": row["actual_folder"],
        "match_method": row["match_method"],
        "confirmed_at": row["confirmed_at"],
        "confirmed_by": row["confirmed_by"],
    }


def delete_project_history(
    conn: sqlite3.Connection,
    project_id: int,
) -> int:
    """删除指定项目的全部历史记录。

    Returns:
        删除的记录数。
    """
    cur = conn.execute(
        "DELETE FROM scan_match_history WHERE project_id = ?",
        (project_id,),
    )
    conn.commit()
    deleted = cur.rowcount
    logger.info("已删除项目 id=%s 的 %d 条匹配历史", project_id, deleted)
    return deleted
