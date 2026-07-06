"""项目数据表定义与访问层。

集中管理 projects 表与 point_dictionary 表的创建与增删查改。

projects 表结构（v0.6.0 起含 project_code 等）：

    id / project_name / project_code / project_type /
    year / county_count / site_count / completion_rate /
    status / created_at / updated_at

字段说明：
- project_name / project_code：来自总体项目表，名称与编码均必填
- project_type：业务类别（7 类之一）；总体项目表可不填，为 NULL 时只显示在
  "全部项目"页，用户可后续手动指定
- year / status：来自总体项目表（可选）
- county_count / site_count / completion_rate：**不由总体项目表提供**，
  由系统在导入规模表后自动统计；导入总体项目表阶段为 0

point_dictionary 表结构（v1.0.0 引入——标准点位字典；v1.1.0 扩展 dynamic_data）：

    id / project_id / standard_point_name / county / original_name /
    dynamic_data

字段说明：
- project_id：外键关联 projects.id
- standard_point_name：标准化后的点位名称（文件系统匹配基准）
- county：所属区县
- original_name：Excel 原始点位名称（溯源）
- dynamic_data：JSON 文本，规模表动态字段（v1.1.0 新增，默认 NULL）

数据访问层不持有连接，所有方法接收调用方传入的连接。created_at / updated_at
由本层以 UTC ISO 时间填充。

本项目首次接入真实数据自 v0.4.0 起；v0.6.0 为架构调整后的稳定结构；
v1.0.0 引入文件系统治理阶段，新增 point_dictionary 标准点位字典表；
v1.1.0 新增 dynamic_data 列与 project_profiles 表。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..utils.logger import setup_logger

logger = setup_logger()


def _now_iso() -> str:
    """当前 UTC 时间的 ISO8601 字符串（含时区）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_projects_table(conn: sqlite3.Connection) -> None:
    """创建 projects 表（如不存在）并升级旧表结构到 v0.6.0。

    v0.6.0 变化：
    - 新增列 project_code、completion_rate
    - project_type 由 NOT NULL 改为可空（总体项目表可不填类型）
    - county_count / site_count / completion_rate 默认 0（统计字段）

    因 SQLite 的 ALTER TABLE 无法去掉列的 NOT NULL 约束，对存在旧表做
    "重建表"迁移：按 v0.6.0 结构新建临时表、复制数据、替换原表。
    """
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(projects)")}
    if not cols:
        # 全新库：直接建 v0.6.0 表
        conn.execute(_V06_SCHEMA)
        conn.commit()
        logger.info("projects 表已创建（v0.6.0）")
        return

    # 旧表存在：判断是否需要迁移
    needs_migration = False
    for col in ("project_code", "completion_rate"):
        if col not in cols:
            needs_migration = True
            break
    # project_type 若为 NOT NULL 也要迁移（v0.6.0 允许空）
    type_row = cols.get("project_type")
    if type_row is not None and type_row["notnull"] == 1:
        needs_migration = True
    # 主键缺失（早期 CREATE TABLE AS 迁移后遗症）也要重建
    pk = [r for r in conn.execute("PRAGMA table_info(projects)") if r["pk"]]
    if not pk:
        needs_migration = True

    if needs_migration:
        _rebuild_v06(conn)
        logger.info("projects 表已迁移到 v0.6.0 结构")
    else:
        conn.commit()
        logger.info("projects 表已是 v0.6.0 结构")


# v0.6.0 完整建表语句
_V06_SCHEMA = """
CREATE TABLE projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name    TEXT    NOT NULL,
    project_code    TEXT,
    project_type    TEXT,
    year            INTEGER,
    county_count    INTEGER NOT NULL DEFAULT 0,
    site_count      INTEGER NOT NULL DEFAULT 0,
    completion_rate INTEGER NOT NULL DEFAULT 0,
    status          TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
)
"""


def _rebuild_v06(conn: sqlite3.Connection) -> None:
    """按 v0.6.0 结构重建 projects 表，保留旧数据与约束。

    用完整 v0.6.0 schema 建新表（保留主键/默认值约束），再 INSERT 复制旧数据，
    最后替换。避免 CREATE TABLE AS 丢失主键导致后续自增 id 失效。
    """
    conn.executescript(
        f"""
        BEGIN;
        {_V06_SCHEMA.replace('CREATE TABLE projects', 'CREATE TABLE projects_new')};
        INSERT INTO projects_new
            (id, project_name, project_code, project_type, year,
             county_count, site_count, completion_rate, status,
             created_at, updated_at)
        SELECT
            id, project_name, NULL, project_type, year,
            COALESCE(county_count, 0), COALESCE(site_count, 0), 0, status,
            created_at, updated_at
        FROM projects;
        DROP TABLE projects;
        ALTER TABLE projects_new RENAME TO projects;
        COMMIT;
        """
    )


def clear_projects_by_type(conn: sqlite3.Connection, project_type: str) -> int:
    """删除指定类别的全部项目。"""
    cur = conn.execute(
        "DELETE FROM projects WHERE project_type = ?",
        (project_type,),
    )
    conn.commit()
    deleted = cur.rowcount
    logger.info("已清空类型[%s]项目 %d 条", project_type, deleted)
    return deleted


def clear_projects_by_categories(
    conn: sqlite3.Connection, categories: list[str]
) -> int:
    """删除多个类别的全部项目。"""
    if not categories:
        return 0
    placeholders = ",".join("?" for _ in categories)
    cur = conn.execute(
        f"DELETE FROM projects WHERE project_type IN ({placeholders})",
        list(categories),
    )
    conn.commit()
    deleted = cur.rowcount
    logger.info("已清空类别 %s 项目 %d 条", categories, deleted)
    return deleted


def insert_projects(
    conn: sqlite3.Connection,
    rows: list[dict],
) -> int:
    """批量插入项目数据（每行自带 project_type，可为 None）。

    每行 dict 需包含键：project_name, project_code, project_type, year, status
    （除 project_name 外均可为 None）。county_count / site_count /
    completion_rate 不由调用方提供，统一写入 0（待规模表统计）。
    """
    if not rows:
        return 0

    now = _now_iso()
    records = []
    for r in rows:
        records.append(
            (
                _coerce_str(r.get("project_name")),
                _coerce_str(r.get("project_code")),
                _coerce_str(r.get("project_type")),
                _coerce_int(r.get("year")),
                0,  # county_count 待统计
                0,  # site_count 待统计
                0,  # completion_rate 待统计
                _coerce_str(r.get("status")),
                now,
                now,
            )
        )

    conn.executemany(
        """
        INSERT INTO projects
            (project_name, project_code, project_type, year,
             county_count, site_count, completion_rate,
             status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    inserted = len(records)
    logger.info("导入项目 %d 条", inserted)
    return inserted


def fetch_projects_by_type(
    conn: sqlite3.Connection, project_type: str | None
) -> list[sqlite3.Row]:
    """查询指定类别的项目（按 id 升序）。

    project_type 为 None 时查询未分类项目（只显示在"全部项目"）。
    """
    cur = conn.execute(
        """
        SELECT id, project_name, project_code, project_type, year,
               county_count, site_count, completion_rate,
               status, created_at, updated_at
        FROM projects
        WHERE project_type IS ?
        ORDER BY id ASC
        """,
        (project_type,),
    )
    return cur.fetchall()


def fetch_all_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """查询全部项目（按 id 升序），供"全部项目"页展示。"""
    cur = conn.execute(
        """
        SELECT id, project_name, project_code, project_type, year,
               county_count, site_count, completion_rate,
               status, created_at, updated_at
        FROM projects
        ORDER BY id ASC
        """
    )
    return cur.fetchall()


def fetch_project_by_id(
    conn: sqlite3.Connection, project_id: int
) -> sqlite3.Row | None:
    """按主键查询单个项目，供项目详情页使用。

    返回包含全部字段的单行；不存在时返回 None。
    """
    cur = conn.execute(
        """
        SELECT id, project_name, project_code, project_type, year,
               county_count, site_count, completion_rate,
               status, created_at, updated_at
        FROM projects
        WHERE id = ?
        """,
        (project_id,),
    )
    return cur.fetchone()


def count_projects_by_type(
    conn: sqlite3.Connection, project_type: str | None
) -> int:
    """统计指定类别的项目数量。"""
    cur = conn.execute(
        "SELECT COUNT(*) AS n FROM projects WHERE project_type IS ?",
        (project_type,),
    )
    return int(cur.fetchone()["n"])


def update_project_type(
    conn: sqlite3.Connection, project_id: int, new_type: str | None
) -> bool:
    """修改单个项目的归属类别，并刷新 updated_at。

    new_type 为 None 表示取消分类（项目回到"全部项目"未分类）。
    """
    cur = conn.execute(
        "UPDATE projects SET project_type = ?, updated_at = ? WHERE id = ?",
        (new_type, _now_iso(), project_id),
    )
    conn.commit()
    return cur.rowcount > 0


# ====================================================================
# point_dictionary 表 —— 标准点位字典（v1.0.0）
# ====================================================================

# v1.0.0 point_dictionary 建表语句（v1.1.0 升级：新增 dynamic_data 列）
_POINT_DICT_SCHEMA = """
CREATE TABLE IF NOT EXISTS point_dictionary (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id           INTEGER NOT NULL,
    standard_point_name  TEXT    NOT NULL,
    county               TEXT,
    original_name        TEXT,
    dynamic_data         TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
)
"""


def init_point_dictionary_table(conn: sqlite3.Connection) -> None:
    """创建 point_dictionary 表（如不存在）并升级到 v1.1.0。

    v1.0.0 引入：标准点位字典，Excel 为唯一标准来源，
    所有文件匹配以 standard_point_name 为基准。
    v1.1.0 升级：新增 dynamic_data 列（JSON，存储规模表动态字段）。
    """
    conn.execute(_POINT_DICT_SCHEMA)
    # 检测 v1.0.0 旧表是否缺少 dynamic_data 列，如缺则追加
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(point_dictionary)")}
    if "dynamic_data" not in cols:
        conn.execute("ALTER TABLE point_dictionary ADD COLUMN dynamic_data TEXT")
        logger.info("point_dictionary 表已升级到 v1.1.0（新增 dynamic_data 列）")
    conn.commit()
    logger.info("point_dictionary 表已就绪（v1.1.0）")


def clear_points_by_project(conn: sqlite3.Connection, project_id: int) -> int:
    """删除指定项目的全部点位字典记录（导入前清空，保证可重入）。"""
    cur = conn.execute(
        "DELETE FROM point_dictionary WHERE project_id = ?",
        (project_id,),
    )
    conn.commit()
    deleted = cur.rowcount
    logger.info("已清空项目 id=%s 点位字典 %d 条", project_id, deleted)
    return deleted


def insert_points(
    conn: sqlite3.Connection,
    project_id: int,
    points: list[dict],
) -> int:
    """批量插入点位字典记录。

    每行 dict 需包含键：standard_point_name, county, original_name。
    original_name 为 Excel 原始名称，standard_point_name 为标准化后名称
    （去特殊字符、trim），作为文件系统匹配基准。
    v1.1.0 扩展：每行可含 dynamic_data（dict，将序列化为 JSON 存储）。
    """
    import json

    if not points:
        return 0

    records = [
        (
            project_id,
            _coerce_str(p.get("standard_point_name")) or "",
            _coerce_str(p.get("county")),
            _coerce_str(p.get("original_name")),
            json.dumps(p.get("dynamic_data") or {}, ensure_ascii=False),
        )
        for p in points
    ]

    conn.executemany(
        """
        INSERT INTO point_dictionary
            (project_id, standard_point_name, county, original_name, dynamic_data)
        VALUES (?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    inserted = len(records)
    logger.info("导入点位字典 %d 条（项目 id=%s）", inserted, project_id)
    return inserted


def fetch_points_by_project(
    conn: sqlite3.Connection, project_id: int
) -> list[sqlite3.Row]:
    """查询指定项目的全部点位字典记录（按 id 升序）。

    Returns:
        每行含 id / project_id / standard_point_name / county / original_name /
        dynamic_data。
    """
    cur = conn.execute(
        """
        SELECT id, project_id, standard_point_name, county, original_name, dynamic_data
        FROM point_dictionary
        WHERE project_id = ?
        ORDER BY id ASC
        """,
        (project_id,),
    )
    return cur.fetchall()


def fetch_points_with_status(
    conn: sqlite3.Connection, project_id: int
) -> list[dict]:
    """查询指定项目的点位字典，并附带图纸/预算状态（当前默认无）。

    v1.0.0 阶段1：状态字段先返回默认值「无」，待阶段4（文件扫描+匹配）
    接入真实文件系统后更新。
    v1.1.0 扩展：返回 dynamic_data 字段。

    Returns:
        每项 dict 含 id / standard_point_name / county / original_name /
        dynamic_data / drawing_status / budget_status。
    """
    import json

    rows = fetch_points_by_project(conn, project_id)
    result = []
    for r in rows:
        dynamic_data = {}
        raw = r["dynamic_data"]
        if raw:
            try:
                dynamic_data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        result.append({
            "id": r["id"],
            "standard_point_name": r["standard_point_name"],
            "county": r["county"] or "",
            "original_name": r["original_name"] or "",
            "dynamic_data": dynamic_data,
            "drawing_status": "无",
            "budget_status": "无",
        })
    return result


def count_points_by_project(conn: sqlite3.Connection, project_id: int) -> int:
    """统计指定项目的点位数量。"""
    cur = conn.execute(
        "SELECT COUNT(*) AS n FROM point_dictionary WHERE project_id = ?",
        (project_id,),
    )
    return int(cur.fetchone()["n"])


# ====================================================================
# 点位名称标准化（v1.0.0）
# ====================================================================


def normalize_point_name(raw: str | None) -> str:
    """将 Excel 原始点位名称标准化。

    规则：
    - 去除首尾空白
    - 去除特殊字符：/ \\ * ? : " < > | 空格
    - 连续空白合并

    标准化后的名称用于文件系统匹配基准。
    """
    if raw is None:
        return ""
    import re

    s = str(raw).strip()
    # 去除文件系统不允许的特殊字符
    s = re.sub(r'[/\\*?:"<>|]', "", s)
    # 合并连续空白
    s = re.sub(r"\s+", "", s)
    return s


# ------------------------------------------------------------------ 类型转换


def _coerce_int(value) -> int | None:
    """宽松转 int：None / 空串 → None；其余取整。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if s == "":
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _coerce_str(value) -> str | None:
    """宽松转 str：None → None；空串 → None；其余去空白字符串。"""
    if value is None:
        return None
    s = str(value).strip()
    return s if s != "" else None
