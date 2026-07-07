"""v1.5 唯一归属模型（Single Ownership Model）专项测试。

验证目标：
1. 每个文件只有一个归属点位（强制）
2. 点位详情文件不重叠
3. 图纸/预算分类稳定一致
4. score < 0.75 → 不归属任何点位
5. DWG/DXF/BAK/PDF 必须 stem 精确匹配，禁止 fuzzy
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ai_office_agent.core.file_index import FileIndex, FileEntry
from ai_office_agent.core.ownership import (
    assign_ownership,
    OwnershipResult,
    OWNERSHIP_THRESHOLD,
    DRAWING_EXTS,
)


def _make_file_entry(name: str, full_path: str, ext: str = ".dwg") -> FileEntry:
    return FileEntry(
        file_name=name,
        full_path=full_path,
        extension=ext,
        normalized_name=Path(name).stem.lower(),
        parent_dir=Path(full_path).parent.name,
        parent_path=str(Path(full_path).parent),
    )


def _build_index(files: list[FileEntry]) -> FileIndex:
    """用给定 FileEntry 列表构建一个 FileIndex（不扫描磁盘）。"""
    idx = FileIndex(root_path="/test")
    idx.files = files
    # 构建简单索引
    for fe in files:
        key = fe.normalized_name
        if key not in idx._file_index:
            idx._file_index[key] = []
        idx._file_index[key].append(fe)
    return idx


def test_single_ownership_one_file_one_owner() -> None:
    """规则1：每个文件只能属于一个点位。"""
    point_a = "安宁-太平新城街道-分纤箱扩容点位"
    point_b = "安宁-青龙街道-分纤箱扩容点位"

    files = [
        _make_file_entry(
            f"{point_a}.dwg",
            f"/proj/{point_a}/{point_a}.dwg",
            ".dwg",
        ),
        _make_file_entry(
            f"{point_b}.dwg",
            f"/proj/{point_b}/{point_b}.dwg",
            ".dwg",
        ),
    ]
    points = [
        {"id": 1, "standard_point_name": point_a},
        {"id": 2, "standard_point_name": point_b},
    ]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    # 验证：每个文件只归属一个点位
    for fe in files:
        decision = result.decisions[fe.full_path]
        assert decision.is_assigned, f"文件 {fe.file_name} 应已归属"
        assert decision.best_point_id is not None
        # 文件路径含 point_a → 归属 point_a（id=1）
        # 文件路径含 point_b → 归属 point_b（id=2）

    # 验证：两个点位的文件列表不重叠
    files_a = set(f.full_path for f in result.point_files.get(1, []))
    files_b = set(f.full_path for f in result.point_files.get(2, []))
    assert files_a & files_b == set(), "点位文件不应重叠"

    print("[OK] 规则1：一文件一归属，无重叠")


def test_threshold_below_075_not_assigned() -> None:
    """规则3：score < 0.75 → 不归属任何点位。"""
    # 一个与点位名完全无关的文件
    files = [
        _make_file_entry("random_file.dwg", "/proj/random/random_file.dwg", ".dwg"),
    ]
    points = [
        {"id": 1, "standard_point_name": "安宁-太平新城街道-分纤箱扩容点位"},
    ]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    decision = result.decisions[files[0].full_path]
    assert not decision.is_assigned, "无关文件不应归属"
    assert decision.best_score < OWNERSHIP_THRESHOLD, \
        f"得分应低于阈值 {OWNERSHIP_THRESHOLD}，实际 {decision.best_score}"
    print(f"[OK] 规则3：无关文件 score={decision.best_score:.2f} < {OWNERSHIP_THRESHOLD}，不归属")


def test_drawing_stem_exact_match_required() -> None:
    """图纸特殊规则：DWG/DXF/BAK/PDF 必须 stem 精确匹配，禁止 fuzzy。"""
    point_a = "安宁-太平新城街道-分纤箱扩容点位"
    point_b = "安宁-青龙街道-分纤箱扩容点位"

    files = [
        # point_a 的图纸（stem 精确匹配 point_a）
        _make_file_entry(
            f"{point_a}.dwg",
            f"/proj/{point_a}/{point_a}.dwg",
            ".dwg",
        ),
        # point_b 的图纸（stem 精确匹配 point_b，在 point_b 目录下）
        _make_file_entry(
            f"{point_b}.dwg",
            f"/proj/{point_b}/{point_b}.dwg",
            ".dwg",
        ),
        # 一个 fuzzy 相似但不精确匹配的图纸文件（放在无关目录下）
        _make_file_entry(
            "安宁-太平新城-分纤箱.dwg",  # 缺少"街道"和"扩容点位"
            f"/proj/其他目录/安宁-太平新城-分纤箱.dwg",
            ".dwg",
        ),
    ]
    points = [
        {"id": 1, "standard_point_name": point_a},
        {"id": 2, "standard_point_name": point_b},
    ]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    # point_a 的 .dwg → 归属 point_a
    d1 = result.decisions[files[0].full_path]
    assert d1.is_assigned and d1.best_point_id == 1, \
        f"{point_a}.dwg 应归属 point_a，实际 {d1.best_point_id}"

    # point_b 的 .dwg → 归属 point_b
    d2 = result.decisions[files[1].full_path]
    assert d2.is_assigned and d2.best_point_id == 2, \
        f"{point_b}.dwg 应归属 point_b，实际 {d2.best_point_id}"

    # fuzzy 相似的 .dwg（在无关目录下）→ 不归属（stem 不精确匹配，路径也不含点位名）
    d3 = result.decisions[files[2].full_path]
    assert not d3.is_assigned, \
        f"fuzzy 相似图纸不应归属，实际 score={d3.best_score:.2f} assigned={d3.is_assigned}"

    print("[OK] 图纸特殊规则：stem 精确匹配，禁止 fuzzy")


def test_no_overlap_between_points() -> None:
    """输出目标：点位详情文件不重叠。"""
    point_a = "盘龙-金辰街道-分纤箱扩容点位"
    point_b = "盘龙-联盟街道-分纤箱扩容点位"

    files = [
        _make_file_entry(f"{point_a}.dwg", f"/proj/{point_a}/{point_a}.dwg", ".dwg"),
        _make_file_entry(f"{point_b}.dwg", f"/proj/{point_b}/{point_b}.dwg", ".dwg"),
        _make_file_entry(f"{point_a}.pdf", f"/proj/{point_a}/{point_a}.pdf", ".pdf"),
        _make_file_entry(f"{point_b}.pdf", f"/proj/{point_b}/{point_b}.pdf", ".pdf"),
    ]
    points = [
        {"id": 1, "standard_point_name": point_a},
        {"id": 2, "standard_point_name": point_b},
    ]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    files_a = set(f.full_path for f in result.point_files.get(1, []))
    files_b = set(f.full_path for f in result.point_files.get(2, []))

    assert len(files_a) == 2, f"point_a 应有 2 个文件，实际 {len(files_a)}"
    assert len(files_b) == 2, f"point_b 应有 2 个文件，实际 {len(files_b)}"
    assert files_a & files_b == set(), "点位文件不应重叠"

    print(f"[OK] 无重叠：point_a={len(files_a)} point_b={len(files_b)}")


def test_drawing_exts_constant() -> None:
    """验证图纸扩展名常量。"""
    assert ".dwg" in DRAWING_EXTS
    assert ".dxf" in DRAWING_EXTS
    assert ".bak" in DRAWING_EXTS
    assert ".pdf" in DRAWING_EXTS
    print("[OK] 图纸扩展名常量：DWG/DXF/BAK/PDF")


def test_pdf_same_name_as_cad_binds() -> None:
    """图纸规则：PDF 与 CAD 同名才可绑定。

    验证 PDF 必须 stem 精确匹配点位名或路径含点位名才能归属。
    """
    point = "安宁-太平新城街道-分纤箱扩容点位"

    files = [
        # 同名 PDF（stem == point）
        _make_file_entry(f"{point}.pdf", f"/proj/{point}/{point}.pdf", ".pdf"),
        # 不同名 PDF（fuzzy 相似，放在无关目录下）
        _make_file_entry("太平新城.pdf", f"/proj/其他目录/太平新城.pdf", ".pdf"),
    ]
    points = [{"id": 1, "standard_point_name": point}]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    d1 = result.decisions[files[0].full_path]
    assert d1.is_assigned, "同名 PDF 应归属"

    d2 = result.decisions[files[1].full_path]
    assert not d2.is_assigned, "无关目录下的非同名 PDF 不应归属（禁止 fuzzy）"

    print("[OK] PDF 同名绑定规则")


def test_conflict_not_assigned() -> None:
    """冲突场景：Top1 ≈ Top2 → 不归属。

    当文件名同时精确匹配两个点位（如 point_a 是 point_b 的前缀）→ 冲突。
    """
    # point_a 是 point_b 的前缀，point_b.dwg 的 stem 以 point_a 开头
    point_a = "安宁-太平街道-点位"
    point_b = "安宁-太平街道-点位A"  # 只差一个 A

    files = [
        _make_file_entry(
            f"{point_b}.dwg",
            f"/proj/{point_b}/{point_b}.dwg",
            ".dwg",
        ),
    ]
    points = [
        {"id": 1, "standard_point_name": point_a},
        {"id": 2, "standard_point_name": point_b},
    ]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    # 文件名同时匹配 point_a（前缀）和 point_b（精确）→ 冲突
    d = result.decisions[files[0].full_path]
    assert d.is_conflict, "stem 同时匹配两个点位应判定为冲突"
    assert not d.is_assigned, "冲突文件不应归属"

    print("[OK] 冲突场景：同时匹配多点位 → 不归属")


def test_status_calculation_based_on_ownership() -> None:
    """状态计算基于唯一归属文件列表。"""
    point = "安宁-太平新城街道-分纤箱扩容点位"

    files = [
        _make_file_entry(f"{point}.dwg", f"/proj/{point}/{point}.dwg", ".dwg"),
        _make_file_entry("造价清单.xlsx", f"/proj/{point}/造价清单.xlsx", ".xlsx"),
    ]
    points = [{"id": 1, "standard_point_name": point}]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    cad, budget = result.status_for_point(1)
    assert cad == "有", f"CAD 状态应为有，实际 {cad}"
    assert budget == "有", f"预算状态应为有，实际 {budget}"

    print(f"[OK] 状态计算：CAD={cad} 预算={budget}")


def test_organize_plan_from_ownership() -> None:
    """验证 file_organizer.build_organize_plan_from_ownership 正常工作。"""
    from ai_office_agent.core.file_organizer import build_organize_plan_from_ownership

    point = "安宁-太平新城街道-分纤箱扩容点位"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        point_dir = root / point
        point_dir.mkdir()
        dwg = point_dir / f"{point}.dwg"
        dwg.write_text("dwg")

        file_index = FileIndex.build(root)
        points = [{"id": 1, "standard_point_name": point}]

        plan = build_organize_plan_from_ownership(file_index, points, str(root))

        assert plan.total_files >= 1, "应有至少 1 个文件"
        assert plan.drawing_count >= 1, "应有至少 1 个图纸"
        print(f"[OK] 整理计划：{plan.total_files} 文件，图纸={plan.drawing_count}")


def test_budget_keyword_any_extension() -> None:
    """v1.5.1：文件名含预算关键词（不限扩展名）→ 预算。

    场景：-设计预算-XXX.pdf 应归为预算，不是其他。
    """
    from ai_office_agent.core.file_organizer import classify_file, build_cad_index
    from ai_office_agent.core.file_index import FileEntry

    point = "云南财经职业学院-盘龙区金色大道113号一楼传输机房"
    file = FileEntry(
        file_name="-设计预算-云南财经职业学院-盘龙区金色大道113号一楼传输机房202606121434PDF.pdf",
        full_path=f"/proj/{point}/-设计预算-云南财经职业学院-盘龙区金色大道113号一楼传输机房202606121434PDF.pdf",
        extension=".pdf",
        normalized_name="设计预算",
        parent_dir=point,
        parent_path=f"/proj/{point}",
    )
    cad_index: dict = {}
    result = classify_file(file, cad_index, point, "/proj")
    assert result.category == "预算", f"含「预算」关键词的 PDF 应为预算，实际 {result.category}"
    print(f"[OK] 预算关键词不限扩展名：{result.reason}")


def test_budget_spreadsheet_no_keyword() -> None:
    """v1.5.2：表格类文件预算识别规则。

    - 文件名含业务关键词（CPMS结构数据/嘉陵版/安全事故防范/安全生产费依据）→ 预算
    - 文件名 stem 去数字后 == 点位名 → 预算（如「龙泉湾202606121457.xlsx」）
    - 无关键词且 stem 去数字 ≠ 点位名 → 其他（不再把所有表格类归预算）
    """
    from ai_office_agent.core.file_organizer import classify_file, build_cad_index
    from ai_office_agent.core.file_index import FileEntry

    point = "龙泉湾"
    # 应归为预算的文件
    budget_files = [
        ("CPMS结构数据--龙泉湾202606121457.xlsx", ".xlsx"),
        ("龙泉湾202606121457.xlsx", ".xlsx"),  # stem 去数字 = 龙泉湾 = 点位名
        ("龙泉湾202606121458_嘉陵版V1.xlsx", ".xlsx"),
        ("龙泉湾202606121458_安全事故防范.xlsx", ".xlsx"),
        ("龙泉湾202606121458_安全生产费依据.xlsx", ".xlsx"),
    ]
    cad_index: dict = {}
    for fname, ext in budget_files:
        file = FileEntry(
            file_name=fname,
            full_path=f"/proj/{point}/{fname}",
            extension=ext,
            normalized_name=Path(fname).stem.lower(),
            parent_dir=point,
            parent_path=f"/proj/{point}",
        )
        result = classify_file(file, cad_index, point, "/proj")
        assert result.category == "预算", \
            f"{fname} 应为预算，实际 {result.category}（{result.reason}）"
    print(f"[OK] 预算文件识别正确（{len(budget_files)} 个文件）")

    # 不应归为预算的文件（无关键词，stem 去数字 ≠ 点位名）
    other_file = FileEntry(
        file_name="照片.jpg",
        full_path=f"/proj/{point}/照片.jpg",
        extension=".jpg",
        normalized_name="照片",
        parent_dir=point,
        parent_path=f"/proj/{point}",
    )
    result = classify_file(other_file, cad_index, point, "/proj")
    assert result.category == "其他", \
        f"照片.jpg 应为其他，实际 {result.category}"
    print("[OK] 无关文件不归预算")


def test_scattered_file_recognized_by_path_evidence() -> None:
    """v1.5.5：文件在非标准子目录下也可通过文件名/路径证据归属。"""
    point = "安宁-太平新城街道-分纤箱扩容点位"

    files = [
        _make_file_entry(
            f"{point}预算.xlsx",
            f"/proj/其他资料/{point}预算.xlsx",
            ".xlsx",
        ),
        _make_file_entry(
            f"{point}说明.docx",
            f"/proj/其他文件/{point}说明.docx",
            ".docx",
        ),
    ]
    points = [{"id": 1, "standard_point_name": point}]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    for f in files:
        d = result.decisions[f.full_path]
        assert d.is_assigned, f"散落文件 {f.file_name} 应通过路径/文件名证据归属，实际 {d.reason}"

    print("[OK] 散落文件可按文件名/路径证据唯一归属")


def test_generic_directory_not_treated_as_point_evidence() -> None:
    """泛分类目录名本身不作为点位身份证据。"""
    point = "安宁-太平新城街道-分纤箱扩容点位"
    files = [
        _make_file_entry("图纸.dwg", "/proj/其他文件/图纸.dwg", ".dwg"),
    ]
    points = [{"id": 1, "standard_point_name": point}]

    idx = _build_index(files)
    result = assign_ownership(idx, points)
    d = result.decisions[files[0].full_path]
    assert not d.is_assigned, "通用名图纸在泛分类目录下不应归属"

    print("[OK] 泛分类目录不作为点位身份证据")


def test_budget_pdf_can_be_assigned() -> None:
    """v1.5.5：预算类 PDF 不被图纸严格规则一票否决。"""
    point = "安宁-太平新城街道-分纤箱扩容点位"
    files = [
        _make_file_entry(
            f"{point}-设计预算.pdf",
            f"/proj/资料包/{point}-设计预算.pdf",
            ".pdf",
        ),
    ]
    points = [{"id": 1, "standard_point_name": point}]
    idx = _build_index(files)
    result = assign_ownership(idx, points)
    d = result.decisions[files[0].full_path]
    assert d.is_assigned, f"预算 PDF 应可归属，实际 {d.reason}"

    print("[OK] 预算 PDF 可按预算资料归属")


def test_drawing_stem_match_not_path() -> None:
    """v1.5.3：图纸归属仅看 stem，不看路径。

    场景：文件 stem 匹配点位A，但物理路径在点位B目录下（误整理导致）。
    旧规则"路径包含点位名"会导致：
    1. 文件同时匹配A(stem)和B(path) → 冲突 → 不归属
    2. 其他点位文件在A目录下 → 错误归属到A

    新规则：仅 stem 匹配，路径不影响图纸归属。
    """
    point_a = "安宁-县街街道-分纤箱扩容点位"
    point_b = "安宁-太平新城街道-分纤箱扩容点位"

    files = [
        # point_a 的图纸，但物理在 point_b 目录下（误整理导致）
        _make_file_entry(
            f"{point_a}.dwg",
            f"/proj/{point_b}/图纸/{point_a}.dwg",
            ".dwg",
        ),
        # point_b 的图纸，在 point_b 目录下
        _make_file_entry(
            f"{point_b}.dwg",
            f"/proj/{point_b}/图纸/{point_b}.dwg",
            ".dwg",
        ),
        # 其他点位的文件，误放在 point_a 目录下
        _make_file_entry(
            "五华-丰宁街道-分纤箱扩容点位.dwg",
            f"/proj/{point_a}/图纸/五华-丰宁街道-分纤箱扩容点位.dwg",
            ".dwg",
        ),
    ]
    points = [
        {"id": 1, "standard_point_name": point_a},
        {"id": 2, "standard_point_name": point_b},
        {"id": 3, "standard_point_name": "五华-丰宁街道-分纤箱扩容点位"},
    ]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    # point_a 的图纸（即使在 point_b 目录下）→ 归属 point_a
    d1 = result.decisions[files[0].full_path]
    assert d1.is_assigned and d1.best_point_id == 1, \
        f"stem 匹配 point_a 应归属 point_a，实际 {d1.best_point_id}（{d1.reason}）"

    # point_b 的图纸 → 归属 point_b
    d2 = result.decisions[files[1].full_path]
    assert d2.is_assigned and d2.best_point_id == 2, \
        f"stem 匹配 point_b 应归属 point_b，实际 {d2.best_point_id}"

    # 五华-丰宁街道的图纸（在 point_a 目录下）→ 归属五华（stem匹配），不归 point_a
    d3 = result.decisions[files[2].full_path]
    assert d3.is_assigned and d3.best_point_id == 3, \
        f"stem 匹配五华应归属五华，实际 {d3.best_point_id}（{d3.reason}）"

    # 验证 point_a 下不会出现五华的文件
    files_a = [f.file_name for f in result.point_files.get(1, [])]
    assert "五华-丰宁街道-分纤箱扩容点位.dwg" not in files_a, \
        "五华文件不应出现在 point_a 下"

    print("[OK] v1.5.3 图纸仅 stem 匹配，路径不影响归属")


def test_budget_file_named_after_other_point_in_wrong_directory() -> None:
    """v1.5.6：文件名含点位A但物理在点位B目录下 → 应归属点位A（文件名优先）。

    真实场景：预算文件「盘龙-联盟街道-分纤箱扩容点位202606121558.xlsx」
    被放在「安宁-太平新城街道-分纤箱扩容点位/其他文件/」目录下。
    旧逻辑：点位A(stem) 0.9 vs 点位B(path) 0.9 → 冲突 → 不归属 → 预算丢失。
    新逻辑：Tier1 stem 含点位名 → 0.95 > Tier2 path → 0.85 → 归属点位A。
    """
    point_a = "盘龙-联盟街道-分纤箱扩容点位"
    point_b = "安宁-太平新城街道-分纤箱扩容点位"

    files = [
        # 预算文件（含点位A名），但放在点位B的"其他文件"目录下
        _make_file_entry(
            f"{point_a}202606121558.xlsx",
            f"/proj/{point_b}/其他文件/{point_a}202606121558.xlsx",
            ".xlsx",
        ),
        _make_file_entry(
            f"{point_a}202606121558_安全生产费依据.xlsx",
            f"/proj/{point_b}/其他文件/{point_a}202606121558_安全生产费依据.xlsx",
            ".xlsx",
        ),
        _make_file_entry(
            f"CPMS结构数据--{point_a}202606121558.xlsx",
            f"/proj/{point_b}/其他文件/CPMS结构数据--{point_a}202606121558.xlsx",
            ".xlsx",
        ),
    ]
    points = [
        {"id": 1, "standard_point_name": point_a},
        {"id": 2, "standard_point_name": point_b},
    ]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    for f in files:
        d = result.decisions[f.full_path]
        assert d.is_assigned, f"预算文件 {f.file_name} 应归属，实际 {d.reason}"
        assert d.best_point_id == 1, \
            f"文件名含「{point_a}」应归属 point_a(id=1)，实际 id={d.best_point_id}"

    # 验证 point_a 有预算文件
    _, budget_status = result.status_for_point(1)
    assert budget_status == "有", \
        f"point_a 预算状态应为「有」，实际「{budget_status}」"

    print(f"[OK] v1.5.6 文件名优先于路径：{len(files)} 个预算文件正确归属 point_a")


def test_other_point_files_not_assigned_to_wrong_point() -> None:
    """v1.5.7：其他点位的预算文件放在非点位目录下 → 不应被误归属。

    真实场景：「五华-丰宁街道-分纤箱扩容点位」的预算文件被放在
    「石林县宜奈一楼无线机房-...-SL-DZCC/III-GJ001」目录下。
    五华-丰宁街道 不在点位字典中，但文件名含「分纤箱扩容」，
    而石林县宜奈... 不含「分纤箱扩容」→ 反向排斥 → 不归属。
    """
    point_a = "石林县宜奈一楼无线机房-昆明石林县西街口镇大紫处村村委会门口资源点-SL-DZCC/III-GJ001"

    files = [
        # 五华-丰宁街道 的预算文件，放在 point_a 目录下
        _make_file_entry(
            "五华-丰宁街道-分纤箱扩容点位202606121434.xlsx",
            f"/proj/{point_a}/其他文件/五华-丰宁街道-分纤箱扩容点位202606121434.xlsx",
            ".xlsx",
        ),
        _make_file_entry(
            "五华-丰宁街道-分纤箱扩容点位202606121434_嘉陵版V1.xlsx",
            f"/proj/{point_a}/其他文件/五华-丰宁街道-分纤箱扩容点位202606121434_嘉陵版V1.xlsx",
            ".xlsx",
        ),
        _make_file_entry(
            "CPMS结构数据--五华-丰宁街道-分纤箱扩容点位202606121434.xlsx",
            f"/proj/{point_a}/其他文件/CPMS结构数据--五华-丰宁街道-分纤箱扩容点位202606121434.xlsx",
            ".xlsx",
        ),
        # point_a 自己的图纸文件（应正常归属）
        _make_file_entry(
            "石林县宜奈一楼无线机房-昆明石林县西街口镇大紫处村村委会门口资源点-SL-DZCCIII-GJ001.dwg",
            f"/proj/{point_a}/石林县宜奈一楼无线机房-昆明石林县西街口镇大紫处村村委会门口资源点-SL-DZCCIII-GJ001.dwg",
            ".dwg",
        ),
    ]
    points = [
        {"id": 1, "standard_point_name": point_a},
    ]

    idx = _build_index(files)
    result = assign_ownership(idx, points)

    # 五华-丰宁街道的文件不应归属到 point_a
    for f in files[:3]:
        d = result.decisions[f.full_path]
        assert not d.is_assigned, \
            f"五华-丰宁街道的文件 {f.file_name} 不应归属到 point_a，实际 {d.reason}"

    # point_a 自己的图纸文件应正常归属
    d_dwg = result.decisions[files[3].full_path]
    assert d_dwg.is_assigned and d_dwg.best_point_id == 1, \
        f"point_a 的图纸应归属，实际 {d_dwg.reason}"

    print("[OK] v1.5.7 反向排斥：其他点位文件不被误归到非匹配点位")


def main() -> int:
    test_drawing_exts_constant()
    test_single_ownership_one_file_one_owner()
    test_threshold_below_075_not_assigned()
    test_drawing_stem_exact_match_required()
    test_no_overlap_between_points()
    test_pdf_same_name_as_cad_binds()
    test_conflict_not_assigned()
    test_status_calculation_based_on_ownership()
    test_organize_plan_from_ownership()
    test_budget_keyword_any_extension()
    test_budget_spreadsheet_no_keyword()
    test_scattered_file_recognized_by_path_evidence()
    test_generic_directory_not_treated_as_point_evidence()
    test_budget_pdf_can_be_assigned()
    test_drawing_stem_match_not_path()
    test_budget_file_named_after_other_point_in_wrong_directory()
    test_other_point_files_not_assigned_to_wrong_point()
    print("\nV1.5_OWNERSHIP_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
