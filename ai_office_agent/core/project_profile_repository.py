"""项目配置文件数据访问层 — v1.1 引入，v1.3.1 扩展 project_folder。

project_profiles 表：规模表导入配置 + 项目文件夹映射。
v1.3.1：新增 project_folder 列 + set_project_folder/get_project_folder。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ..utils.logger import setup_logger

logger = setup_logger()

_PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS project_profiles (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id           INTEGER NOT NULL UNIQUE,
    sheet_name           TEXT,
    point_name_field     TEXT,
    county_field         TEXT,
    start_point_field    TEXT,
    end_point_field      TEXT,
    use_concatenation    INTEGER NOT NULL DEFAULT 0,
    dynamic_fields       TEXT,
    project_folder       TEXT,
    created_at           TEXT    NOT NULL,
    updated_at           TEXT    NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
)
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_project_profiles_table(conn: sqlite3.Connection) -> None:
    """创建 project_profiles 表 + 迁移旧表。"""
    conn.execute(_PROFILE_SCHEMA)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(project_profiles)")}
    if "project_folder" not in cols:
        conn.execute("ALTER TABLE project_profiles ADD COLUMN project_folder TEXT")
        logger.info("project_profiles 表已升级（v1.3.1：新增 project_folder 列）")
    conn.commit()
    logger.info("project_profiles 表已就绪（v1.3.1）")


def upsert_profile(
    conn: sqlite3.Connection,
    project_id: int,
    profile: dict[str, Any],
) -> None:
    """写入或更新项目配置（INSERT OR REPLACE 语义）。"""
    now = _now_iso()
    conn.execute(
        """
        INSERT OR REPLACE INTO project_profiles
            (id, project_id, sheet_name, point_name_field, county_field,
             start_point_field, end_point_field, use_concatenation,
             dynamic_fields, project_folder, created_at, updated_at)
        VALUES (
            (SELECT id FROM project_profiles WHERE project_id = ?),
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            COALESCE((SELECT created_at FROM project_profiles WHERE project_id = ?), ?),
            ?
        )
        """,
        (
            project_id, project_id,
            profile.get("sheet_name"),
            profile.get("point_name_field"),
            profile.get("county_field"),
            profile.get("start_point_field"),
            profile.get("end_point_field"),
            1 if profile.get("use_concatenation") else 0,
            json.dumps(profile.get("dynamic_fields") or [], ensure_ascii=False),
            profile.get("project_folder"),
            project_id, now, now,
        ),
    )
    conn.commit()
    logger.info("项目配置已保存：project_id=%s", project_id)


def fetch_profile(
    conn: sqlite3.Connection, project_id: int
) -> dict[str, Any] | None:
    """按项目 ID 查询已保存的配置。"""
    row = conn.execute(
        """
        SELECT * FROM project_profiles WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        return None
    dynamic_fields = []
    if row["dynamic_fields"]:
        try:
            dynamic_fields = json.loads(row["dynamic_fields"])
        except json.JSONDecodeError:
            pass
    return {
        "id": row["id"], "project_id": row["project_id"],
        "sheet_name": row["sheet_name"],
        "point_name_field": row["point_name_field"],
        "county_field": row["county_field"],
        "start_point_field": row["start_point_field"],
        "end_point_field": row["end_point_field"],
        "use_concatenation": bool(row["use_concatenation"]),
        "dynamic_fields": dynamic_fields,
        "project_folder": row["project_folder"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def set_project_folder(
    conn: sqlite3.Connection, project_id: int, folder_path: str,
) -> None:
    """v1.3.1：保存项目的关联文件夹路径。"""
    now = _now_iso()
    existing = conn.execute(
        "SELECT id FROM project_profiles WHERE project_id = ?", (project_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE project_profiles SET project_folder=?, updated_at=? WHERE project_id=?",
            (folder_path, now, project_id),
        )
    else:
        conn.execute(
            "INSERT INTO project_profiles (project_id, project_folder, use_concatenation, created_at, updated_at) VALUES (?,?,0,?,?)",
            (project_id, folder_path, now, now),
        )
    conn.commit()
    logger.info("项目文件夹已设置：project_id=%s → %s", project_id, folder_path)


def get_project_folder(
    conn: sqlite3.Connection, project_id: int,
) -> str | None:
    """v1.3.1：获取项目的关联文件夹路径。"""
    row = conn.execute(
        "SELECT project_folder FROM project_profiles WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return row["project_folder"] if row else None


def delete_profile(conn: sqlite3.Connection, project_id: int) -> None:
    """删除项目配置。"""
    conn.execute("DELETE FROM project_profiles WHERE project_id = ?", (project_id,))
    conn.commit()
    logger.info("项目配置已删除：project_id=%s", project_id)
