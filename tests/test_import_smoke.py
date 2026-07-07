"""导入与仓储冒烟测试（无 GUI）。

验证 v1.0.0：
- project_categories：类型分流
- excel_reader：表头动态识别 + 数据读取
- projects_repository：
  - projects 表：建表/迁移、插入（含 project_code，统计列默认 0）、
    按类型查询、fetch_all、update_project_type、fetch 未分类（NULL）
  - point_dictionary 表（v1.0.0 新增）：建表、清空、插入、查询、统计、
    normalize_point_name 标准化
- import_worker 核心逻辑：读取→分流→全量替换写库（无 project_type 行写 NULL）
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402
import pytest  # noqa: E402

from ai_office_agent.core import project_categories, projects_repository  # noqa: E402
from ai_office_agent.data_import import excel_reader  # noqa: E402


@pytest.fixture
def tmp(tmp_path: Path) -> Path:
    """兼容脚本模式的旧 tmp 参数名。"""
    return tmp_path


def make_sample_xlsx(path: Path) -> None:
    """造带前导空行、多类型、含/不含类型的样例 .xlsx。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "项目"
    ws.append(["通信设计部 - 总体项目表（2026 年度）"])
    ws.append([])
    # 表头：v0.6.0 字段（无区县/点位）
    ws.append(["项目名称", "项目编码", "年份", "项目类型", "状态"])
    ws.append(["浦东社区改造", "PRJ-001", 2026, "社区", "进行中"])
    ws.append(["数字家庭工程", "PRJ-002", 2026, "数字家庭", "进行中"])  # →社区
    ws.append(["集客专线A", "PRJ-003", 2026, "专线", "进行中"])          # →集客
    ws.append(["未分类项目B", "PRJ-004", 2026, "", "待启动"])            # type 空→NULL
    ws.append(["不明类型C", "PRJ-005", 2026, "外星人工程", "进行中"])     # 无法识别→NULL
    ws.append([])  # 空行跳过
    ws.append(["", "PRJ-006", 2026, "社区", "进行中"])  # 项目名称为空→跳过
    wb.save(path)


def test_categories() -> None:
    assert project_categories.resolve_category("社区") == "社区"
    assert project_categories.resolve_category("数字家庭") == "社区"
    assert project_categories.resolve_category("专线") == "集客"
    assert project_categories.resolve_category("优化") == "城域网"
    assert project_categories.resolve_category("配套") == "机房配套"
    assert project_categories.resolve_category("外星人工程") is None
    assert project_categories.resolve_category(None) is None
    assert project_categories.resolve_category("") is None
    print("[OK] project_categories: 分流 + 合法性")


def test_excel_reader(tmp: Path) -> None:
    xlsx = tmp / "sample.xlsx"
    make_sample_xlsx(xlsx)
    headers, rows = excel_reader.read_sheet(xlsx)
    assert "项目名称" in headers
    assert "项目编码" in headers
    # 数据行 = 6（空行跳过）
    assert len(rows) == 6, f"数据行数: {len(rows)}"
    print("[OK] excel_reader: 表头识别 + 数据读取 (%d 行)" % len(rows))


def test_repository(tmp: Path) -> None:
    db_path = tmp / "t.db"
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row

    projects_repository.init_projects_table(conn)
    # 验证 v0.6.0 列存在
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(projects)")}
    for c in ("project_code", "project_type", "county_count",
              "site_count", "completion_rate"):
        assert c in cols, f"缺列: {c}"
    # 二次调用（迁移幂等）
    projects_repository.init_projects_table(conn)

    rows = [
        {"project_name": "A", "project_code": "C1", "project_type": "社区",
         "year": 2026, "status": "进行中"},
        {"project_name": "B", "project_code": "C2", "project_type": None,
         "year": None, "status": None},  # 未分类
    ]
    n = projects_repository.insert_projects(conn, rows)
    assert n == 2

    # 统计列默认 0
    a = projects_repository.fetch_projects_by_type(conn, "社区")[0]
    assert a["county_count"] == 0 and a["site_count"] == 0 and a["completion_rate"] == 0
    assert a["project_code"] == "C1"

    # fetch 未分类（NULL）
    unassigned = projects_repository.fetch_projects_by_type(conn, None)
    assert len(unassigned) == 1 and unassigned[0]["project_name"] == "B"

    # fetch_all
    assert len(projects_repository.fetch_all_projects(conn)) == 2

    # update_project_type：NULL → 社区
    b_id = int(unassigned[0]["id"])
    assert projects_repository.update_project_type(conn, b_id, "社区")
    assert projects_repository.count_projects_by_type(conn, None) == 0
    assert projects_repository.count_projects_by_type(conn, "社区") == 2

    # fetch_project_by_id：按 id 查单条（供详情页）
    fetched = projects_repository.fetch_project_by_id(conn, b_id)
    assert fetched is not None
    assert int(fetched["id"]) == b_id
    assert fetched["project_name"] == "B"
    assert projects_repository.fetch_project_by_id(conn, 999999) is None
    print("[OK] projects_repository: v0.6.0 列/插入/NULL 查询/改类型/按 id 查")

    conn.close()


def test_worker_logic(tmp: Path) -> None:
    """复刻 worker.run_import：读取→分流→全量替换写库。"""
    xlsx = tmp / "sample.xlsx"
    make_sample_xlsx(xlsx)
    headers, data_rows = excel_reader.read_sheet(xlsx)
    mapping = {
        "project_name": "项目名称",
        "project_code": "项目编码",
        "project_type": "项目类型",
        "year": "年份",
        "status": "状态",
    }

    repo_rows = []
    skipped = 0
    for row in data_rows:
        raw_name = row.get(mapping["project_name"])
        if project_categories.normalize(raw_name) == "":
            skipped += 1
            continue
        raw_type = row.get(mapping["project_type"])
        category = (
            project_categories.resolve_category(raw_type)
            if raw_type is not None and project_categories.normalize(raw_type)
            else None
        )
        repo_rows.append({
            "project_name": str(raw_name or "").strip(),
            "project_code": row.get(mapping["project_code"]),
            "project_type": category,
            "year": row.get(mapping["year"]),
            "status": row.get(mapping["status"]),
        })

    # 5 条有效（缺名称行1条被跳过）：社区2 + 集客1 + NULL2
    assert len(repo_rows) == 5, f"分流行数: {len(repo_rows)}"
    assert skipped == 1

    db_path = tmp / "w.db"
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    projects_repository.init_projects_table(conn)
    conn.execute("DELETE FROM projects")
    conn.commit()
    n = projects_repository.insert_projects(conn, repo_rows)
    assert n == 5

    assert projects_repository.count_projects_by_type(conn, "社区") == 2
    assert projects_repository.count_projects_by_type(conn, "集客") == 1
    assert projects_repository.count_projects_by_type(conn, None) == 2
    print("[OK] import_worker 核心逻辑: 分流+全量替换 (5 入库, 1 跳过, 2 未分类)")
    conn.close()


def test_point_dictionary(tmp: Path) -> None:
    """v1.0.0 标准点位字典表：建表、插、查、清空、标准化。"""
    db_path = tmp / "pd.db"
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # 建表
    projects_repository.init_point_dictionary_table(conn)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(point_dictionary)")}
    for c in ("project_id", "standard_point_name", "county", "original_name"):
        assert c in cols, f"point_dictionary 缺列: {c}"

    # 二次调用幂等
    projects_repository.init_point_dictionary_table(conn)

    # 插入
    points = [
        {"standard_point_name": "SiteA", "county": "浦东", "original_name": "Site A"},
        {"standard_point_name": "SiteB", "county": "浦东", "original_name": "Site/B"},
        {"standard_point_name": "SiteC", "county": "", "original_name": "Site C"},
    ]
    n = projects_repository.insert_points(conn, 1, points)
    assert n == 3

    # 查询
    rows = projects_repository.fetch_points_by_project(conn, 1)
    assert len(rows) == 3
    assert rows[0]["standard_point_name"] == "SiteA"
    assert rows[0]["original_name"] == "Site A"

    # fetch_points_with_status（带状态默认值）
    status_rows = projects_repository.fetch_points_with_status(conn, 1)
    assert len(status_rows) == 3
    assert status_rows[0]["drawing_status"] == "无"
    assert status_rows[0]["budget_status"] == "无"

    # 统计
    assert projects_repository.count_points_by_project(conn, 1) == 3
    assert projects_repository.count_points_by_project(conn, 999) == 0

    # 清空
    deleted = projects_repository.clear_points_by_project(conn, 1)
    assert deleted == 3
    assert projects_repository.count_points_by_project(conn, 1) == 0

    # 空插入
    assert projects_repository.insert_points(conn, 1, []) == 0

    # normalize_point_name 标准化
    assert projects_repository.normalize_point_name("Site A") == "SiteA"
    assert projects_repository.normalize_point_name("Site/B") == "SiteB"
    assert projects_repository.normalize_point_name(" Site*C ") == "SiteC"
    assert projects_repository.normalize_point_name("A:B<C>D|E") == "ABCDE"
    assert projects_repository.normalize_point_name(None) == ""
    assert projects_repository.normalize_point_name("") == ""

    print("[OK] point_dictionary: 建表/插入/查询/清空/统计/标准化（v1.0.0）")
    conn.close()


def test_scanner() -> None:
    """v1.0.0 架构升级：项目资料 → 图纸根目录 → 点位。"""
    from ai_office_agent.core.normalizer import for_filesystem
    from ai_office_agent.core.scanner import (
        compute_all_statuses_for_sites,
        compute_budget_status,
        compute_drawing_status,
        match_project_sites,
        match_single_folder,
        scan_project_root,
    )

    projects = scan_project_root()
    assert len(projects) >= 3, f"沙盒至少3个项目，实际 {len(projects)}"

    # ── 找到"社区改造工程2026" ──
    proj = None
    for p in projects:
        if p.name == "社区改造工程2026":
            proj = p
            break
    assert proj is not None

    # ── 验证第一步：项目整体资料 ──
    doc_cats = {d.category for d in proj.docs}
    for expected in ("规模表", "材料表", "照片", "勘察报告", "流程文件", "批复", "其它资料"):
        assert expected in doc_cats, f"应识别资料分类: {expected}"
    assert len(proj.root_files) >= 1  # 项目说明.txt
    print(f"  [资料] 识别 {len(proj.docs)} 类：{sorted(doc_cats)}")

    # ── 验证第二步：图纸根目录 ──
    assert proj.drawing_root is not None, "应识别到图纸根目录"
    assert proj.drawing_root.name == "设计图", f"图纸根目录应为'设计图'，实际'{proj.drawing_root.name}'"
    assert len(proj.drawing_candidates) >= 1
    print(f"  [图纸根目录] {proj.drawing_root.name}（候选数={proj.drawing_candidates[0].candidate_count}）")

    # ── 验证第三步：点位 ──
    assert len(proj.sites) == 3, f"应有3个点位，实际 {len(proj.sites)}"
    site_names = {s.name for s in proj.sites}
    assert site_names == {"SiteA", "SiteB", "SiteC"}, f"点位名称不符: {site_names}"

    # 验证 SiteNode 子文件夹识别
    siteA = next(s for s in proj.sites if s.name == "SiteA")
    assert siteA.drawing_dir is not None, "SiteA 应有图纸子文件夹"
    assert siteA.budget_dir is not None, "SiteA 应有预算子文件夹"

    # ── 验证匹配 ──
    point_list = [
        {"id": 1, "standard_point_name": "SiteA"},
        {"id": 2, "standard_point_name": "SiteB"},
        {"id": 3, "standard_point_name": "SiteC"},
    ]
    matches, unmatched = match_project_sites(proj, point_list)
    assert len(matches) == 3
    assert len(unmatched) == 0, f"应全部匹配: {unmatched}"
    for m in matches:
        assert m.is_matched and m.match_score == 1.0
        # 状态已在 match_project_sites 中填入
        assert m.drawing_status in ("有", "无")
        assert m.budget_status in ("有", "无")

    # ── 验证状态 ──
    siteA_match = next(m for m in matches if m.point_name == "SiteA")
    siteB_match = next(m for m in matches if m.point_name == "SiteB")
    siteC_match = next(m for m in matches if m.point_name == "SiteC")
    assert siteA_match.drawing_status == "有", f"SiteA 图纸应有: {siteA_match.drawing_status}"
    assert siteA_match.budget_status == "有", f"SiteA 预算应有: {siteA_match.budget_status}"
    assert siteB_match.drawing_status == "有", f"SiteB 图纸应有: {siteB_match.drawing_status}"
    assert siteB_match.budget_status == "无", f"SiteB 预算应无: {siteB_match.budget_status}"
    assert siteC_match.drawing_status == "有"
    assert siteC_match.budget_status == "有"
    print(f"  SiteA: 图纸={siteA_match.drawing_status} 预算={siteA_match.budget_status}")
    print(f"  SiteB: 图纸={siteB_match.drawing_status} 预算={siteB_match.budget_status}")
    print(f"  SiteC: 图纸={siteC_match.drawing_status} 预算={siteC_match.budget_status}")

    # ── 验证匹配辅助函数（v1.1.1：使用 RapidFuzz 引擎，得分范围 0.0~1.0） ──
    assert match_single_folder("SiteA", "/test/SiteA", point_list).match_score >= 0.95
    # 子串包含 → 得分应较高
    result = match_single_folder("SiteA-ext", "/test/SiteA-ext", point_list)
    assert result.match_score >= 0.70, f"Expected >= 0.70, got {result.match_score}"
    assert match_single_folder("Unknown", "/test/Unknown", point_list).match_score == 0.0
    # v1.1.1：走 normalizer.for_filesystem（保留单词间的空格用于更好匹配）
    assert for_filesystem("Site A") == "site a"
    assert for_filesystem("Site/A") == "sitea"

    # ── 验证 SiteNode 状态计算 ──
    statuses = compute_all_statuses_for_sites(proj.sites)
    for st in statuses:
        assert st["drawing_status"] in ("有", "无")
        assert st["budget_status"] in ("有", "无")

    # 直接调用 compute_* 也正确
    for site in proj.sites:
        dwg = compute_drawing_status(site)
        bud = compute_budget_status(site)
        assert dwg in ("有", "无")
        assert bud in ("有", "无")

    # ── 验证项目2：集客专线（图纸根目录=CAD） ──
    proj2 = next(p for p in projects if p.name == "集客专线2026")
    assert proj2.drawing_root is not None
    assert proj2.drawing_root.name == "CAD", f"图纸根目录应为'CAD': {proj2.drawing_root.name}"
    assert len(proj2.sites) == 2  # 点位D + Site_E
    site_names2 = {s.name for s in proj2.sites}
    assert "点位D" in site_names2

    # ── 验证项目3：接入段工程（图纸根目录=施工图） ──
    proj3 = next(p for p in projects if p.name == "接入段工程2026")
    assert proj3.drawing_root is not None
    assert proj3.drawing_root.name == "施工图", f"图纸根目录应为'施工图': {proj3.drawing_root.name}"
    assert len(proj3.sites) == 2  # SiteF + SiteG

    print("[OK] scanner: 项目资料+图纸根目录+点位识别+匹配+状态（架构升级 v1.0.0）")


def test_scan_match_history(tmp: Path) -> None:
    """v1.2.2: scan match history CRUD."""
    from ai_office_agent.core import scan_match_history_repository as smhr
    from ai_office_agent.core import projects_repository
    from ai_office_agent.core.database import Database

    conn = Database.open_db_connection(str(tmp / "test_smh.db"))
    try:
        projects_repository.init_projects_table(conn)
        # insert a dummy project satisfying all NOT NULL columns
        conn.execute(
            "INSERT INTO projects (project_name, project_code, project_type, year, "
            "county_count, site_count, completion_rate, status, created_at, updated_at) "
            "VALUES (?,?,?, 2026, 0, 0, 0, 'active', datetime('now','localtime'), datetime('now','localtime'))",
            ("test_project", "T001", "社区"),
        )
        conn.commit()
        smhr.init_scan_match_history_table(conn)
        sid = smhr.save_match_history(conn, 1, "SiteA", "SiteA_actual", "manual")
        assert sid > 0
        smhr.save_match_history(conn, 1, "SiteB", "SiteB_folder", "fuzzy")
        hist = smhr.fetch_project_history(conn, 1)
        assert "SiteA" in hist
        assert hist["SiteA"]["actual_folder"] == "SiteA_actual"
        rec = smhr.fetch_match_by_point(conn, 1, "SiteA")
        assert rec is not None
        assert smhr.fetch_match_by_point(conn, 1, "None") is None
        # upsert
        smhr.save_match_history(conn, 1, "SiteA", "SiteA_renamed", "manual")
        hist2 = smhr.fetch_project_history(conn, 1)
        assert hist2["SiteA"]["actual_folder"] == "SiteA_renamed"
        # delete
        deleted = smhr.delete_project_history(conn, 1)
        assert deleted >= 2
        assert smhr.fetch_project_history(conn, 1) == {}
        print("[OK] scan_match_history: CRUD+upsert (v1.2.2)")
    finally:
        conn.close()


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="iao_smoke_"))
    try:
        test_categories()
        test_excel_reader(tmp)
        test_repository(tmp)
        test_worker_logic(tmp)
        test_point_dictionary(tmp)
        test_scanner()
        test_scan_match_history(tmp)
    finally:
        for f in tmp.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass
    print("\nALL_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
