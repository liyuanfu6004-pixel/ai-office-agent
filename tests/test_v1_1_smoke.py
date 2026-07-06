"""v1.1.0 规模表智能识别引擎 冒烟测试。

测试：
- scale_table_engine 核心逻辑
- project_profile_repository CRUD
- point_dictionary 升级到 v1.1.0
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_office_agent.core import project_profile_repository as ppr
from ai_office_agent.core import projects_repository as pr
from ai_office_agent.core import scale_table_engine as ste
from ai_office_agent.core.database import Database
from ai_office_agent.utils.logger import setup_logger

logger = setup_logger()


def test_scale_table_engine() -> None:
    """测试 scale_table_engine 核心功能。"""
    headers = ["点位名称", "区县", "长度", "芯数", "起点", "终点", "建设内容"]
    rows = [{h: f"val_{i}_{h}" for h in headers} for i in range(5)]

    # Sheet scoring
    score = ste.score_sheet_likelihood(headers, rows)
    assert score > 0.3, f"Sheet score too low: {score}"

    # Field detection
    assert ste.detect_point_name_field(headers) == "点位名称"
    assert ste.detect_county_field(headers) == "区县"
    assert ste.detect_start_field(headers) == "起点"
    assert ste.detect_end_field(headers) == "终点"

    # Point name generation
    row = {"点位名称": "SiteA", "区县": "某某区"}
    name = ste.generate_point_name(row, point_field="点位名称", use_concatenation=False)
    assert name == "SiteA"

    row2 = {"起点": "A端", "终点": "Z端"}
    name2 = ste.generate_point_name(
        row2, start_field="起点", end_field="终点", use_concatenation=True
    )
    assert name2 == "A端-Z端"

    # should_concatenate
    assert ste.should_concatenate("接入段") is True
    assert ste.should_concatenate("城域网") is True
    assert ste.should_concatenate("社区") is False
    assert ste.should_concatenate(None) is False

    # Dynamic fields
    occupied = {"点位名称", "区县"}
    dynamic = ste.classify_dynamic_fields(headers, occupied)
    dynamic_labels = [d["label"] for d in dynamic]
    assert "长度" in dynamic_labels
    assert "芯数" in dynamic_labels

    # Field candidates
    candidates = ste.build_field_candidates(headers)
    assert candidates.point_name == "点位名称"
    assert candidates.county == "区县"

    # Build point records
    mapping = {
        "point_name": "点位名称",
        "county": "区县",
        "start_point": None,
        "end_point": None,
    }
    records = ste.build_point_records(rows, mapping, dynamic, use_concatenation=False)
    assert len(records) == 5
    assert records[0]["standard_point_name"] == "val_0_点位名称"
    assert records[0]["county"] == "val_0_区县"
    assert "长度" in records[0]["dynamic_data"]

    # Preview
    preview = ste.build_preview_rows(
        rows, mapping, dynamic, use_concatenation=False, preview_count=3
    )
    assert len(preview) == 3
    assert preview[0]["point_name"] == "val_0_点位名称"

    logger.info("[OK] scale_table_engine: 9 项测试全部通过")


def test_project_profile_repository() -> None:
    """测试 project_profile_repository CRUD。"""
    db_path = str(Path(__file__).resolve().parent.parent / "data" / "ai_office_agent.db")
    conn = Database.open_db_connection(db_path)

    # Init tables
    pr.init_projects_table(conn)
    ppr.init_project_profiles_table(conn)

    # Get a real project ID
    row = conn.execute("SELECT id FROM projects LIMIT 1").fetchone()
    if not row:
        now = "2026-07-05T00:00:00Z"
        conn.execute(
            "INSERT INTO projects (project_name, project_code, project_type, year, created_at, updated_at) "
            "VALUES ('测试项目', 'TEST-001', '社区', 2026, ?, ?)",
            (now, now),
        )
        conn.commit()
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        pid = row["id"]

    # Clean any leftover profile
    ppr.delete_profile(conn, pid)

    # Upsert
    ppr.upsert_profile(
        conn,
        pid,
        {
            "sheet_name": "点位规模表",
            "point_name_field": "站点名称",
            "county_field": "区县",
            "start_point_field": None,
            "end_point_field": None,
            "use_concatenation": False,
            "dynamic_fields": [
                {"name": "长度", "label": "长度", "type": "长度"},
                {"name": "芯数", "label": "芯数", "type": "芯数"},
            ],
        },
    )

    # Fetch
    profile = ppr.fetch_profile(conn, pid)
    assert profile is not None
    assert profile["sheet_name"] == "点位规模表"
    assert profile["point_name_field"] == "站点名称"
    assert profile["use_concatenation"] is False
    assert len(profile["dynamic_fields"]) == 2

    # Exists
    assert ppr.profile_exists(conn, pid) is True
    assert ppr.profile_exists(conn, 99999) is False

    # Delete
    assert ppr.delete_profile(conn, pid) is True
    assert ppr.fetch_profile(conn, pid) is None

    conn.close()
    logger.info("[OK] project_profile_repository: 5 项测试全部通过")


def test_point_dictionary_upgrade() -> None:
    """测试 point_dictionary 表已升级到 v1.1.0。"""
    db_path = str(Path(__file__).resolve().parent.parent / "data" / "ai_office_agent.db")
    conn = Database.open_db_connection(db_path)

    pr.init_point_dictionary_table(conn)
    pr.init_projects_table(conn)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(point_dictionary)")}
    assert "dynamic_data" in cols, "point_dictionary 表应含 dynamic_data 列"

    # Get a real project ID
    row = conn.execute("SELECT id FROM projects LIMIT 1").fetchone()
    if not row:
        now = "2026-07-05T00:00:00Z"
        conn.execute(
            "INSERT INTO projects (project_name, project_code, project_type, year, created_at, updated_at) "
            "VALUES ('测试项目2', 'TEST-002', '集客', 2026, ?, ?)",
            (now, now),
        )
        conn.commit()
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        pid = row["id"]

    # Test insert with dynamic_data
    pr.insert_points(
        conn,
        pid,
        [
            {
                "standard_point_name": "TestSite",
                "county": "测试区",
                "original_name": "TestSite",
                "dynamic_data": {"长度": "100", "芯数": "12"},
            }
        ],
    )

    # Test fetch with dynamic_data
    points = pr.fetch_points_with_status(conn, pid)
    test_point = [p for p in points if p["standard_point_name"] == "TestSite"]
    if test_point:
        dd = test_point[0].get("dynamic_data", {})
        assert dd.get("长度") == "100", f"Expected 长度=100, got {dd}"

    # Cleanup
    conn.execute("DELETE FROM point_dictionary WHERE standard_point_name = 'TestSite'")
    conn.commit()

    conn.close()
    logger.info("[OK] point_dictionary 升级到 v1.1.0: dynamic_data 列正常")


def main() -> int:
    try:
        test_scale_table_engine()
        test_project_profile_repository()
        test_point_dictionary_upgrade()
        logger.info("ALL v1.1.0 SMOKE TESTS PASSED")
        print("v1.1.0_SMOKE_OK")
        return 0
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
