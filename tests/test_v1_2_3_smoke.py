"""v1.2.3 冒烟测试：区域标准化 + 全量索引扫描引擎。
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ai_office_agent.core.normalizer import for_matching, for_filesystem_path


def test_normalizer_matching() -> None:
    """test: match_name 生成正确。"""
    # / 去除
    assert for_matching("Site/A") == "sitea"
    # 非法字符去除
    assert for_matching("站点:名称*测试?") == "站点名称测试"
    # 全角转半角 + lowercase
    assert for_matching("SiteＡ") == "sitea"
    # 去括号
    assert for_matching("机房(最终)", remove_parens=True) == "机房"
    # 中文括号
    assert for_matching("机房（最终）", remove_parens=True) == "机房"
    print("[OK] normalizer: match_name 生成")


def test_filesystem_path() -> None:
    """test: filesystem_name 生成正确。"""
    # / → -
    assert for_filesystem_path("A/B社区") == "A-B社区"
    # 保留中文
    assert "社区" in for_filesystem_path("社区Site")
    # 无非法字符
    result = for_filesystem_path("站点:名称*测试?")
    for c in r'/:*?"<>|':
        assert c not in result
    print("[OK] normalizer: filesystem_name 生成")


def test_region_profile() -> None:
    """test: 区县语义归一化。"""
    from ai_office_agent.core.region_profile import RegionProfile, reset_profile

    # 加载 profile
    profile = RegionProfile.load()
    assert len(profile.active_counties) >= 1, "应有负责区县"

    # alias 归一
    assert profile.normalize("安宁") == "安宁市"
    assert profile.normalize("安宁市") == "安宁市"
    assert profile.normalize("安宁区") == "安宁市"
    assert profile.normalize("晋宁") == "晋宁区"

    # 未知区县返回原值
    assert profile.normalize("福州") == "福州"

    # is_active
    assert profile.is_active("安宁") is True
    assert profile.is_active("安宁市") is True
    assert profile.is_active("福州") is False
    assert profile.is_active(None) is False

    reset_profile()
    print("[OK] region_profile: alias 归一 + active 判断")


def test_region_filter() -> None:
    """test: 非负责区域过滤。"""
    from ai_office_agent.core.region_profile import get_profile, reset_profile

    profile = get_profile()
    active = profile.active_counties

    # 负责区县可通过
    for c in active:
        normalized = profile.normalize(c)
        assert profile.is_active(normalized), f"负责区县 {normalized} 应通过"

    # 非负责区县被拦截
    assert not profile.is_active("福州")
    assert not profile.is_active("上海")

    # None 处理
    assert profile.normalize("") is None

    reset_profile()
    print("[OK] region_filter: 非负责区县被拦截")


def test_file_index_scan() -> None:
    """test: FileIndex 递归扫描 + 乱目录识别。"""
    from ai_office_agent.core.file_index import FileIndex

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # 乱目录结构
        (root / "deep" / "nested" / "path").mkdir(parents=True)
        (root / "deep" / "nested" / "path" / "file1.dwg").write_text("")
        (root / "deep" / "file2.xlsx").write_text("")
        (root / "root_file.txt").write_text("")

        index = FileIndex.build(root)
        assert len(index.files) == 3, f"应扫描到3个文件: {len(index.files)}"
        assert len(index.dirs) >= 3, f"应扫描到>=3个目录: {len(index.dirs)}"

        # 深层文件
        deep_files = [f for f in index.files if "file1" in f.file_name]
        assert len(deep_files) == 1

    print("[OK] file_index: 乱目录递归扫描")


def test_file_index_global_match() -> None:
    """test: 文件深层嵌套 + / 等非法字符匹配。"""
    from ai_office_agent.core.file_index import FileIndex

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "Site_A").mkdir()
        (root / "Site_A" / "图纸1.dwg").write_text("")
        (root / "deep" / "Site_A_files").mkdir(parents=True)
        (root / "deep" / "Site_A_files" / "预算.xlsx").write_text("")

        index = FileIndex.build(root)

        # 全局匹配——不管路径在哪
        matching = index.global_match_point("Site A")
        assert len(matching) >= 1, f"应匹配到文件: {matching}"

        # / 不影响匹配
        matching2 = index.global_match_point("Site/A")
        assert len(matching2) >= 1, f"/不应该影响匹配: {matching2}"

    print("[OK] file_index: 全局匹配 + / 不影响")


def test_file_index_dwg_status() -> None:
    """test: 基于 FileIndex 的图纸状态判断。"""
    from ai_office_agent.core.file_index import FileIndex

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "ZZZ_Point_A").mkdir()
        (root / "ZZZ_Point_A" / "设计.dwg").write_text("")
        (root / "XXX_Empty_Point").mkdir()

        index = FileIndex.build(root)
        # Point A has .dwg → "有"
        assert index.compute_drawing_status("ZZZ_Point_A") == "有", \
            f"ZZZ_Point_A 有 dwg: {index.compute_drawing_status('ZZZ_Point_A')}"
        # Empty has no .dwg → "无"
        assert index.compute_drawing_status("XXX_Empty_Point") == "无", \
            f"XXX_Empty_Point 应无: {index.compute_drawing_status('XXX_Empty_Point')}"

    print("[OK] file_index: 图纸状态判断")


def test_imports() -> None:
    """test: v1.2.3 新模块可导入。"""
    from ai_office_agent.core.scanner import (
        scan_with_file_index,
        match_points_from_index,
        FileIndex,
    )
    from ai_office_agent.core.region_profile import RegionProfile, get_profile, reset_profile
    assert callable(scan_with_file_index)
    assert callable(match_points_from_index)
    print("[OK] imports: v1.2.3 新模块可导入")


def main() -> int:
    test_normalizer_matching()
    test_filesystem_path()
    test_region_profile()
    test_region_filter()
    test_file_index_scan()
    test_file_index_global_match()
    test_file_index_dwg_status()
    test_imports()
    print("\nV1.2.3_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
