"""v1.3 文件自动整理引擎测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ai_office_agent.core.file_index import FileIndex, FileEntry
from ai_office_agent.core.file_organizer import (
    build_cad_index,
    classify_file,
    build_organize_plan,
    apply_organize_plan,
)


def _fe(name: str, path: str, ext: str = ".dwg") -> FileEntry:
    return FileEntry(
        file_name=name, full_path=path, extension=ext,
        normalized_name=name.lower(), parent_dir=str(Path(path).parent),
        parent_path=str(Path(path).parent),
    )


def test_cad_index() -> None:
    """CAD 索引构建正确。"""
    files = [
        _fe("siteA.dwg", "/proj/siteA/siteA.dwg"),
        _fe("siteA.dxf", "/proj/siteA/siteA.dxf"),
        _fe("预算.xlsx", "/proj/siteA/预算.xlsx"),
        _fe("报告.pdf", "/proj/siteA/报告.pdf"),
    ]
    ci = build_cad_index(files)
    assert "sitea" in ci, f"应包含 stem 'siteA': {list(ci.keys())}"
    assert len(ci["sitea"]) == 2  # dwg + dxf
    print("[OK] CAD 索引构建")


def test_classify_drawing() -> None:
    """直接图纸文件归类为图纸。"""
    ci: dict = {}
    f = _fe("siteA.dwg", "/proj/siteA/siteA.dwg")
    r = classify_file(f, ci, "siteA", "/proj")
    assert r.category == "图纸", f"dwg 应为图纸: {r.category}"
    print("[OK] dwg → 图纸")


def test_classify_pdf_matches_cad() -> None:
    """同名 PDF 匹配 CAD → 图纸。"""
    ci = {"sitea": [_fe("siteA.dwg", "/proj/siteA/siteA.dwg")]}
    f = _fe("siteA.pdf", "/proj/siteA/siteA.pdf", ext=".pdf")
    r = classify_file(f, ci, "siteA", "/proj")
    assert r.category == "图纸", f"同名PDF应为图纸: {r.category}"
    print("[OK] 同名PDF → 图纸")


def test_classify_budget() -> None:
    """预算文件归类正确。"""
    ci: dict = {}
    f = _fe("造价清单.xlsx", "/proj/siteA/造价清单.xlsx", ext=".xlsx")
    r = classify_file(f, ci, "siteA", "/proj")
    assert r.category == "预算", f"造价.xlsx应为预算: {r.category}"
    print("[OK] 预算关键词 → 预算")


def test_classify_other() -> None:
    """其他文件归类。"""
    ci: dict = {}
    f = _fe("照片.jpg", "/proj/siteA/照片.jpg", ext=".jpg")
    r = classify_file(f, ci, "siteA", "/proj")
    assert r.category == "其他", f"jpg应为其他: {r.category}"
    print("[OK] 未知 → 其他")


def test_point_name_with_slash_sanitized() -> None:
    """v1.6.1：点位名含 / 时，直接删除 /（不是替换为 -）。"""
    original_name = "SL-DZCC/III-GJ001"
    point_files = {
        original_name: [
            _fe("siteA.dwg", "/proj/siteA/siteA.dwg"),
        ],
    }
    plan = build_organize_plan(point_files, "/proj")
    for pname, items in plan.points.items():
        for r in items:
            path_str = str(r.target_dir).replace("\\", "/")
            parts = path_str.split("/设计文件/其他区县/")
            assert len(parts) == 2, f"路径格式异常: {path_str}"
            point_segment = parts[1].split("/")[0]
            assert point_segment == "SL-DZCCIII-GJ001", \
                f"点位名应删除 /：{point_segment}（期望 SL-DZCCIII-GJ001）"
    print("[OK] 点位名含 / → 直接删除 /")


def test_organize_plan() -> None:
    """整理计划生成。"""
    point_files = {
        "siteA": [
            _fe("siteA.dwg", "/proj/siteA/siteA.dwg"),
            _fe("siteA.pdf", "/proj/siteA/siteA.pdf", ext=".pdf"),
            _fe("预算.xlsx", "/proj/siteA/预算.xlsx", ext=".xlsx"),
        ],
    }
    plan = build_organize_plan(point_files, "/proj")
    assert plan.total_files == 3
    assert plan.drawing_count == 2  # dwg + 同名pdf
    assert plan.budget_count == 1
    print(f"[OK] 整理计划: {plan.total_files}文件 图纸={plan.drawing_count} 预算={plan.budget_count}")


def test_apply_organize() -> None:
    """执行整理 - 实际移动文件（v1.6：目标路径在 设计文件/ 下）。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # 创建源文件
        (root / "siteA").mkdir()
        dwg = root / "siteA" / "siteA.dwg"
        pdf = root / "siteA" / "siteA.pdf"
        xls = root / "siteA" / "预算.xlsx"
        dwg.write_text("dwg")
        pdf.write_text("pdf")
        xls.write_text("xls")

        files = [
            FileEntry(file_name="siteA.dwg", full_path=str(dwg), extension=".dwg",
                      normalized_name="sitea", parent_dir="siteA", parent_path=str(root / "siteA")),
            FileEntry(file_name="siteA.pdf", full_path=str(pdf), extension=".pdf",
                      normalized_name="sitea", parent_dir="siteA", parent_path=str(root / "siteA")),
            FileEntry(file_name="预算.xlsx", full_path=str(xls), extension=".xlsx",
                      normalized_name="yusuan", parent_dir="siteA", parent_path=str(root / "siteA")),
        ]
        point_files = {"siteA": files}
        plan = build_organize_plan(point_files, str(root))
        result = apply_organize_plan(plan)

        assert result["moved"] == 3, f"应移动 3 个: {result}"
        # v1.6：目标路径 = 设计文件/{区县}/siteA/图纸/，测试无区县→"其他区县"
        assert (root / "设计文件" / "其他区县" / "siteA" / "图纸" / "siteA.dwg").exists()
        assert (root / "设计文件" / "其他区县" / "siteA" / "图纸" / "siteA.pdf").exists()
        assert (root / "设计文件" / "其他区县" / "siteA" / "预算" / "预算.xlsx").exists()
        print(f"[OK] 执行整理: 移动={result['moved']} 冲突={len(plan.conflicts)}")


def test_imports() -> None:
    """新模块可导入。"""
    from ai_office_agent.core.file_organizer import (
        ClassificationResult, OrganizePlan, build_cad_index,
        classify_file, build_organize_plan, apply_organize_plan,
    )
    assert ClassificationResult is not None
    assert OrganizePlan is not None
    print("[OK] v1.3 模块可导入")


def test_organize_plan_no_cross_point_drawing() -> None:
    """图纸文件不应归属到非本点位（v1.4.2 修复）。

    模拟 global_match_point fuzzy 匹配导致的跨点位污染：
    「盘龙-金辰街道」的匹配结果里混入了「盘龙-联盟街道」的图纸文件。
    整理计划生成时应当过滤掉其他点位的图纸文件。
    """
    point_a = "盘龙-金辰街道-分纤箱扩容点位"
    point_b = "盘龙-联盟街道-分纤箱扩容点位"

    point_files = {
        point_a: [
            _fe(
                "盘龙-金辰街道-分纤箱扩容点位202606121601.bak",
                f"/proj/{point_a}/盘龙-金辰街道-分纤箱扩容点位202606121601.bak",
                ext=".bak",
            ),
            # 错误混入：联盟街道的文件不应被金辰街道收录
            _fe(
                "盘龙-联盟街道-分纤箱扩容点位202606121601.bak",
                f"/proj/{point_b}/盘龙-联盟街道-分纤箱扩容点位202606121601.bak",
                ext=".bak",
            ),
            # 同名 PDF 也因 CAD 索引被过滤而不应归入图纸
            _fe(
                "盘龙-联盟街道-分纤箱扩容点位202606121601.pdf",
                f"/proj/{point_b}/盘龙-联盟街道-分纤箱扩容点位202606121601.pdf",
                ext=".pdf",
            ),
        ],
    }
    plan = build_organize_plan(point_files, "/proj")
    assert plan.drawing_count == 1, f"金辰街道应只含 1 个图纸，实际 {plan.drawing_count}"
    # 联盟街道的 .bak 被标记为「非本点位图纸」→ 归入"其他"，仍在文件列表中
    assert plan.total_files == 3, f"应保留 3 个文件（1图纸+2其他），实际 {plan.total_files}"
    assert plan.other_count == 2, f"联盟街道的 .bak + .pdf 应为其他，实际 {plan.other_count}"
    assert len(plan.points[point_a]) == 3, f"金辰街道点位应含 3 条分类，实际 {len(plan.points[point_a])}"
    print("[OK] 跨点位图纸文件被正确过滤：drawing=1 other=2")


def main() -> int:
    test_cad_index()
    test_classify_drawing()
    test_classify_pdf_matches_cad()
    test_classify_budget()
    test_classify_other()
    test_point_name_with_slash_sanitized()
    test_organize_plan()
    test_organize_plan_no_cross_point_drawing()
    test_apply_organize()
    test_imports()
    print("\nV1.3_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
