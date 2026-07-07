"""v1.5.3 Scan Session 生命周期测试。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ai_office_agent.core.file_index import FileEntry, FileIndex
from ai_office_agent.core.file_organizer import build_organize_plan_from_scan_session
from ai_office_agent.core.ownership import assign_ownership
from ai_office_agent.core.scan_controller import (
    init_scan_result_tables,
    save_scan_session,
    load_current_scan_session,
    has_valid_scan_session,
    invalidate_scan_session,
)
from ai_office_agent.core.scan_result import ScanResultItem, ScanResultSummary, MatchStatus


def _fe(name: str, path: str, ext: str = ".dwg") -> FileEntry:
    return FileEntry(
        file_name=name,
        full_path=path,
        extension=ext,
        normalized_name=Path(name).stem.lower(),
        parent_dir=Path(path).parent.name,
        parent_path=str(Path(path).parent),
    )


def _idx(files: list[FileEntry]) -> FileIndex:
    idx = FileIndex(root_path="/proj")
    idx.files = files
    for f in files:
        idx._file_index.setdefault(f.normalized_name, []).append(f)
    return idx


def test_scan_session_persistence_and_invalidation(tmp_path: Path) -> None:
    db = tmp_path / "scan_session.db"
    conn = sqlite3.connect(db, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        init_scan_result_tables(conn)
        point = "点位A"
        files = [_fe(f"{point}.dwg", f"/proj/{point}/{point}.dwg")]
        file_index = _idx(files)
        ownership = assign_ownership(file_index, [{"id": 1, "standard_point_name": point}])
        item = ScanResultItem(
            point_id=1,
            standard_point_name=point,
            matched_folder=point,
            matched_folder_path=f"/proj/{point}",
            match_score=1.0,
            match_status=MatchStatus.MATCHED,
            cad_status="有",
            budget_status="无",
            cad_file_count=1,
            scanned_files=[f"{point}.dwg"],
            file_owner_point_id=1,
            match_confidence=1.0,
        )
        summary = ScanResultSummary.from_items(
            [item], project_id=10, project_name="项目", scan_directory="/proj", scan_duration_ms=8
        )

        session_id = save_scan_session(conn, 10, "/proj", summary, file_index, ownership)
        assert session_id > 0
        assert has_valid_scan_session(conn, 10, "/proj")
        session = load_current_scan_session(conn, 10)
        assert session is not None
        assert session["project_id"] == 10
        assert session["scan_path"] == "/proj"
        assert session["file_index"]["files"][0]["file_name"] == f"{point}.dwg"
        assert "1" in session["ownership"]["point_files"]
        assert session["scan_result"]["items"][0]["file_owner_point_id"] == 1

        invalidate_scan_session(conn, 10)
        assert not has_valid_scan_session(conn, 10)
        assert load_current_scan_session(conn, 10) is None
    finally:
        conn.close()


def test_organize_plan_from_scan_session_does_not_rescan(monkeypatch) -> None:
    point = "点位A"
    file = _fe(f"{point}.dwg", f"/proj/{point}/{point}.dwg")

    def fail_assign(*_args, **_kwargs):
        raise AssertionError("整理计划不应重新执行 assign_ownership")

    monkeypatch.setattr("ai_office_agent.core.ownership.assign_ownership", fail_assign)

    plan = build_organize_plan_from_scan_session(
        point_files={"1": [file]},
        points=[{"id": 1, "standard_point_name": point}],
        project_path="/proj",
    )
    assert plan.total_files == 1
    assert point in plan.points
    assert plan.points[point][0].category == "图纸"


def test_scan_result_suggestion_does_not_ask_to_create_folder() -> None:
    """v1.5.5：未识别到归属文件时不应再提示创建点位文件夹。"""
    item = ScanResultItem(
        point_id=1,
        standard_point_name="某点位",
        match_status=MatchStatus.NOT_FOUND,
        cad_status="无",
        budget_status="无",
    )
    item.suggestion = ScanResultItem._generate_suggestion(item)
    assert "创建点位文件夹" not in item.suggestion
    assert "未在文件系统中找到对应文件夹" not in item.suggestion
    assert "未识别到该点位的归属文件" in item.suggestion


def test_organize_plan_target_uses_scan_session_path(tmp_path: Path) -> None:
    """整理目标目录必须使用 Scan Session 的 scan_path。"""
    point = "点位A"
    file = _fe(f"{point}.dwg", f"/selected/{point}/{point}.dwg")
    plan = build_organize_plan_from_scan_session(
        point_files={"1": [file]},
        points=[{"id": 1, "standard_point_name": point}],
        project_path="/selected",
    )
    assert plan.project_path == "/selected"
    result = plan.points[point][0]
    assert str(result.target_dir).replace("\\", "/").endswith(f"/selected/{point}/图纸")
