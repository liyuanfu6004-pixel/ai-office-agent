"""统一扫描结果数据模型 — v1.2 引入。

扫描结果中心（Scan Center）的核心数据模型，所有模块统一使用。

每个 ScanResult 代表一个点位在文件系统中的匹配结果，包含：
- 标准点位名称（来自 point_dictionary）
- Excel 原始名称
- 实际匹配到的文件夹
- 匹配分数
- CAD 状态 / 预算状态
- 匹配状态枚举
- 建议说明

匹配状态枚举：
    MATCHED          — 成功匹配（score ≥ 85）
    PARTIAL_MATCH    — 部分匹配（score ≥ 70 且 < 85）
    NOT_FOUND        — 未找到匹配（score < 70 或无候选）
    MULTIPLE_MATCH   — 多个候选文件夹（score 接近）

数据来源：
    - point_dictionary（标准点位字典）
    - scanner（文件系统扫描）
    - matcher（RapidFuzz 匹配引擎）

本模块仅定义数据模型，不包含匹配逻辑。所有匹配逻辑由 core/matcher.py
和 core/scanner.py 提供。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any


# ====================================================================
# 匹配状态枚举
# ====================================================================


class MatchStatus(Enum):
    """点位文件夹与标准点位字典的匹配状态。

    MATCHED:        完全/高度匹配，score ≥ 85
    PARTIAL_MATCH:  部分匹配，score ≥ 70 且 < 85
    NOT_FOUND:      未找到匹配，score < 70 或无候选
    MULTIPLE_MATCH: 多个候选文件夹得分接近（差值 < 10）
    """

    MATCHED = auto()
    PARTIAL_MATCH = auto()
    NOT_FOUND = auto()
    MULTIPLE_MATCH = auto()

    @property
    def label(self) -> str:
        """中文标签。"""
        labels = {
            MatchStatus.MATCHED: "已匹配",
            MatchStatus.PARTIAL_MATCH: "部分匹配",
            MatchStatus.NOT_FOUND: "未找到",
            MatchStatus.MULTIPLE_MATCH: "多候选",
        }
        return labels.get(self, "未知")

    @property
    def color(self) -> str:
        """对应颜色（HEX）。"""
        colors = {
            MatchStatus.MATCHED: "#107C10",        # 绿色
            MatchStatus.PARTIAL_MATCH: "#FFB900",   # 黄色
            MatchStatus.NOT_FOUND: "#D13438",       # 红色
            MatchStatus.MULTIPLE_MATCH: "#FF8C00",  # 橙色
        }
        return colors.get(self, "#8A8A8A")


# ====================================================================
# 扫描结果数据模型
# ====================================================================


@dataclass
class ScanResultItem:
    """单个点位的扫描匹配结果。

    每个点位在 point_dictionary 中对应一条记录，本数据类将点位字典、
    文件扫描、匹配引擎三者的数据合并为一个统一视图。

    Attributes:
        point_id: point_dictionary 表的主键 id。
        standard_point_name: 标准点位名称（文件匹配基准）。
        original_name: Excel 原始点位名称（溯源）。
        county: 所属区县。
        matched_folder: 实际匹配到的文件夹名称（无匹配时为 None）。
        matched_folder_path: 匹配文件夹的绝对路径。
        match_score: 匹配得分（0.0 ~ 1.0）。
        match_status: 匹配状态枚举。
        cad_status: CAD 图纸状态（"有"/"无"）。
        budget_status: 预算状态（"有"/"无"）。
        suggestion: 建议说明文本。
        cad_file_count: 图纸子文件夹内 .dwg 文件数量。
        budget_file_count: 预算子文件夹内文件数量。
        scanned_files: 扫描到的文件列表（文件名列表）。
        dynamic_data: 规模表动态字段（来自 point_dictionary.dynamic_data）。
    """

    # ---- 点位字典字段 ----
    point_id: int | None = None
    standard_point_name: str = ""
    original_name: str = ""
    county: str = ""

    # ---- 匹配结果字段 ----
    matched_folder: str | None = None
    matched_folder_path: str | None = None
    match_score: float = 0.0
    match_status: MatchStatus = MatchStatus.NOT_FOUND

    # ---- 状态字段 ----
    cad_status: str = "无"
    budget_status: str = "无"

    # ---- 建议 ----
    suggestion: str = ""

    # ---- 文件统计 ----
    cad_file_count: int = 0
    budget_file_count: int = 0
    scanned_files: list[str] = field(default_factory=list)

    # ---- 扩展数据 ----
    dynamic_data: dict[str, Any] = field(default_factory=dict)

    # ---- v1.2.2 人工确认 ----
    confirmed: bool = False
    match_method: str = "fuzzy"  # fuzzy / history / manual

    # ---- v1.3.1 唯一归属 ----
    file_owner_point_id: int | None = None  # 文件的唯一归属 point_id
    match_confidence: float = 0.0           # 匹配置信度

    @property
    def confirmed_label(self) -> str:
        """确认状态中文标签。"""
        return "已确认" if self.confirmed else "未确认"

    @property
    def match_percent(self) -> int:
        """匹配率（0-100 整数）。"""
        return round(self.match_score * 100)

    @classmethod
    def from_point_dict(
        cls,
        point: dict,
        match_result: dict | None = None,
    ) -> ScanResultItem:
        """从点位字典 + 匹配结果构造 ScanResultItem。

        Args:
            point: point_dictionary 行 dict，含 id/standard_point_name/
                  original_name/county/dynamic_data。
            match_result: 来自 scanner.match_project_sites 的 MatchResult，
                          含 folder_name/folder_path/match_score/
                          drawing_status/budget_status。

        Returns:
            ScanResultItem 实例。
        """
        item = cls(
            point_id=point.get("id"),
            standard_point_name=point.get("standard_point_name", ""),
            original_name=point.get("original_name", ""),
            county=point.get("county", ""),
            dynamic_data=point.get("dynamic_data") or {},
        )

        if match_result:
            item.matched_folder = match_result.get("folder_name")
            item.matched_folder_path = match_result.get("folder_path")
            score = match_result.get("match_score", 0.0)
            item.match_score = score
            item.cad_status = match_result.get("drawing_status", "无")
            item.budget_status = match_result.get("budget_status", "无")
            item.scanned_files = match_result.get("scanned_files", [])
            item.cad_file_count = match_result.get("cad_file_count", 0)
            item.budget_file_count = match_result.get("budget_file_count", 0)

            # 判断匹配状态
            if match_result.get("is_multi_candidate", False):
                item.match_status = MatchStatus.MULTIPLE_MATCH
            elif score >= 0.85:
                item.match_status = MatchStatus.MATCHED
            elif score >= 0.70:
                item.match_status = MatchStatus.PARTIAL_MATCH
            else:
                item.match_status = MatchStatus.NOT_FOUND
        else:
            item.match_status = MatchStatus.NOT_FOUND

        # 生成建议
        item.suggestion = cls._generate_suggestion(item)
        return item

    @staticmethod
    def _generate_suggestion(item: ScanResultItem) -> str:
        """根据匹配状态和文件状态生成建议。"""
        parts = []
        if item.match_status == MatchStatus.MATCHED:
            if item.cad_status == "有" and item.budget_status == "有":
                parts.append("匹配成功，文件齐全")
            elif item.cad_status == "无":
                parts.append("缺少 CAD 图纸文件")
            elif item.budget_status == "无":
                parts.append("缺少预算文件")
            else:
                parts.append("匹配成功")
        elif item.match_status == MatchStatus.PARTIAL_MATCH:
            parts.append("建议人工确认匹配")
            if item.cad_status == "无":
                parts.append("补充 CAD 图纸")
            if item.budget_status == "无":
                parts.append("补充预算文件")
        elif item.match_status == MatchStatus.MULTIPLE_MATCH:
            parts.append("存在多个候选文件夹，建议人工选择")
        elif item.match_status == MatchStatus.NOT_FOUND:
            parts.append("未在文件系统中找到对应文件夹")
            if item.cad_status == "无":
                parts.append("请创建点位文件夹并导入图纸")
        return "；".join(parts) if parts else "—"

    def to_dict(self) -> dict:
        """转为可序列化的 dict。"""
        return {
            "point_id": self.point_id,
            "standard_point_name": self.standard_point_name,
            "original_name": self.original_name,
            "county": self.county,
            "matched_folder": self.matched_folder,
            "matched_folder_path": self.matched_folder_path,
            "match_score": self.match_score,
            "match_status": self.match_status.name,
            "cad_status": self.cad_status,
            "budget_status": self.budget_status,
            "suggestion": self.suggestion,
            "cad_file_count": self.cad_file_count,
            "budget_file_count": self.budget_file_count,
            "scanned_files": self.scanned_files,
            "dynamic_data": self.dynamic_data,
            "confirmed": self.confirmed,
            "confirmed_label": self.confirmed_label,
            "match_method": self.match_method,
        }


# ====================================================================
# 扫描结果汇总
# ====================================================================


@dataclass
class ScanResultSummary:
    """扫描结果汇总统计（v1.2.3：统一数据源）。

    供扫描结果中心页面 + 项目列表统计使用。
    所有统计从此汇总取数，禁止使用 point_dictionary count 或旧 DB 字段。
    """

    project_id: int | None = None
    project_name: str = ""
    scan_time: str = ""
    scan_duration_ms: int = 0
    scan_directory: str = ""

    total_points: int = 0
    matched_count: int = 0
    partial_match_count: int = 0
    not_found_count: int = 0
    multiple_match_count: int = 0
    cad_missing_count: int = 0
    budget_missing_count: int = 0
    confirmed_count: int = 0
    # v1.2.3：完成率统计
    completed_points: int = 0
    completion_rate: int = 0
    # v1.3.1：冲突文件
    conflict_file_count: int = 0
    conflict_files: list[str] = field(default_factory=list)

    items: list[ScanResultItem] = field(default_factory=list)

    @classmethod
    def from_items(
        cls,
        items: list[ScanResultItem],
        project_id: int | None = None,
        project_name: str = "",
        scan_directory: str = "",
        scan_duration_ms: int = 0,
    ) -> ScanResultSummary:
        """从 ScanResultItem 列表生成汇总统计。

        Args:
            items: 扫描结果项列表。
            project_id: 项目 ID。
            project_name: 项目名称。
            scan_directory: 扫描目录。
            scan_duration_ms: 扫描耗时。

        Returns:
            ScanResultSummary 含统计计数。
        """
        summary = cls(
            project_id=project_id,
            project_name=project_name,
            scan_time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            scan_duration_ms=scan_duration_ms,
            scan_directory=scan_directory,
            total_points=len(items),
            items=items,
        )

        for item in items:
            status = item.match_status
            if status == MatchStatus.MATCHED:
                summary.matched_count += 1
            elif status == MatchStatus.PARTIAL_MATCH:
                summary.partial_match_count += 1
            elif status == MatchStatus.MULTIPLE_MATCH:
                summary.multiple_match_count += 1
            elif status == MatchStatus.NOT_FOUND:
                summary.not_found_count += 1

            if item.cad_status == "无":
                summary.cad_missing_count += 1
            if item.budget_status == "无":
                summary.budget_missing_count += 1
            if item.confirmed:
                summary.confirmed_count += 1
            # v1.2.3：完成 = CAD有 + 预算有
            if item.cad_status == "有" and item.budget_status == "有":
                summary.completed_points += 1

        # v1.2.3：计算完成率
        if summary.total_points > 0:
            summary.completion_rate = round(
                summary.completed_points / summary.total_points * 100
            )

        # v1.2.3：缓存到全局
        if project_id is not None:
            _cache_summary(project_id, summary)

        return summary

    def to_dict(self) -> dict:
        """转为可序列化的 dict。"""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "scan_time": self.scan_time,
            "scan_duration_ms": self.scan_duration_ms,
            "scan_directory": self.scan_directory,
            "total_points": self.total_points,
            "matched_count": self.matched_count,
            "partial_match_count": self.partial_match_count,
            "not_found_count": self.not_found_count,
            "multiple_match_count": self.multiple_match_count,
            "cad_missing_count": self.cad_missing_count,
            "budget_missing_count": self.budget_missing_count,
            "confirmed_count": self.confirmed_count,
            "completed_points": self.completed_points,
            "completion_rate": self.completion_rate,
            "items": [item.to_dict() for item in self.items],
        }

    def to_json(self) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ====================================================================
# 扫描结果生成器（协调 scanner + matcher + point_dictionary）
# ====================================================================


def build_scan_results(
    project_id: int,
    project_name: str,
    points: list[dict],
    scan_directory: str = "",
    db_path: str | None = None,
) -> ScanResultSummary:
    """从点位字典 + 文件扫描 + 历史确认生成统一扫描结果。

    本函数是扫描结果中心的入口——协调 scanner（文件扫描）、
    matcher（匹配引擎）、point_dictionary（标准点位字典）、
    scan_match_history（历史确认），生成统一的 ScanResultItem 列表。

    v1.2.2 新增：优先使用 scan_match_history 中已确认的匹配，
    已确认点位跳过模糊匹配。

    Args:
        project_id: 项目 ID。
        project_name: 项目名称。
        points: 从 point_dictionary 加载的点位列表。
        scan_directory: 扫描根目录路径。
        db_path: 数据库路径（用于读取 scan_match_history）。
    """
    import time

    from ..utils.logger import setup_logger
    logger = setup_logger()

    start_time = time.perf_counter()

    # ── v1.2.2：加载历史确认 ──
    history_map: dict[str, dict] = {}
    if db_path is not None:
        try:
            from .database import Database
            from . import scan_match_history_repository as smhr
            conn = Database.open_db_connection(db_path)
            try:
                smhr.init_scan_match_history_table(conn)
                history_map = smhr.fetch_project_history(conn, project_id)
            finally:
                conn.close()
        except Exception:
            pass

    # ── v1.2.3：区县过滤 + FileIndex 扫描 ──
    from .region_profile import get_profile
    profile = get_profile()

    # 过滤非负责区县的点位
    filtered_points: list[dict] = []
    for p in points:
        county = p.get("county", "")
        if county:
            normalized = profile.normalize(county)
            if normalized and not profile.is_active(normalized):
                continue  # 非负责区县，忽略
        filtered_points.append(p)

    if len(filtered_points) < len(points):
        logger.info(
            "区县过滤：%d → %d 个点位（非负责区县已忽略）",
            len(points), len(filtered_points),
        )

    # ── v1.3.1：优先使用项目关联文件夹 ──
    match_map: dict[str, dict] = {}
    project_root: str | None = None
    try:
        from .database import Database
        from . import project_profile_repository as ppr
        conn = Database.open_db_connection(db_path) if db_path else None
        if conn:
            try:
                ppr.init_project_profiles_table(conn)
                project_root = ppr.get_project_folder(conn, project_id)
            finally:
                conn.close()

        from .scanner import (
            TEST_ROOT_PATH,
            scan_with_file_index,
        )
        from .file_index import FileIndex
        from .matcher import match_folder

        if project_root and Path(project_root).exists():
            # 直接扫描项目关联文件夹（不再扫整个 TEST_ROOT_PATH）
            file_index = FileIndex.build(project_root)
            matched_project = _make_project_node(project_name, project_root, file_index)
            logger.info("v1.3.1 使用项目文件夹：%s", project_root)
        else:
            # 回退：扫描 TEST_ROOT_PATH + 按名称匹配
            root = scan_directory or str(TEST_ROOT_PATH)
            projects = scan_with_file_index(root)
            matched_project = None
            for proj in projects:
                result = match_folder(project_name, proj.name)
                if result.is_match:
                    matched_project = proj
                    break

        if matched_project is not None and matched_project.file_index is not None:
            point_dict = [
                {"id": p["id"], "standard_point_name": p["standard_point_name"],
                 "county": p.get("county", "")}
                for p in filtered_points
            ]

            # ── v1.5：两阶段唯一归属模型 ──
            # 禁止调用 global_match_point（反向匹配会导致多归属污染）
            # 禁止调用 match_points_from_index（旧链路含 fuzzy 反向匹配）
            from .ownership import (
                assign_ownership,
                get_scanned_files_for_point,
                get_file_counts_for_point,
            )
            ownership = assign_ownership(matched_project.file_index, point_dict)

            # 构建 point_name → point_id 映射
            pname_to_pid: dict[str, int] = {}
            for p in point_dict:
                pname_to_pid[p["standard_point_name"]] = int(p["id"])

            for p in point_dict:
                pid = int(p["id"])
                pname = p["standard_point_name"]
                files = ownership.files_for_point(pid)
                cad_status, budget_status = ownership.status_for_point(pid)
                cad_count, budget_count = get_file_counts_for_point(ownership, pid, pname)
                scanned_files = get_scanned_files_for_point(ownership, pid)

                # 取第一个归属文件的父目录作为 folder_name
                folder_name = ""
                folder_path = ""
                if files:
                    folder_name = files[0].parent_dir
                    folder_path = files[0].parent_path

                # 匹配分数：有归属文件 → 1.0；否则 0
                match_score = 1.0 if files else 0.0

                match_map[pname] = {
                    "folder_name": folder_name,
                    "folder_path": folder_path,
                    "match_score": match_score,
                    "drawing_status": cad_status,
                    "budget_status": budget_status,
                    "scanned_files": scanned_files,
                    "cad_file_count": cad_count,
                    "budget_file_count": budget_count,
                    "is_multi_candidate": False,
                }

            logger.info(
                "v1.5 唯一归属扫描结果：项目=%s，%d 点位，已归属文件=%d，冲突=%d",
                project_name, len(match_map),
                ownership.assigned_count, len(ownership.conflict_files),
            )

    except Exception as exc:
        logger.warning("FileIndex 扫描失败，回退空匹配：%s", exc)

    # 构建 ScanResultItem 列表（使用过滤后的点位）
    items: list[ScanResultItem] = []
    for p in filtered_points:
        pname = p.get("standard_point_name", "")
        match_info = match_map.get(pname)
        item = ScanResultItem.from_point_dict(p, match_info)

        # ── v1.2.3：区县归一化 ──
        raw_county = p.get("county", "")
        if raw_county:
            normalized_county = profile.normalize(raw_county)
            if normalized_county:
                item.county = normalized_county

        # ── v1.2.2：应用历史确认 ──
        hist = history_map.get(pname)
        if hist is not None:
            item.confirmed = True
            item.match_method = hist.get("match_method", "history")
            if hist.get("actual_folder"):
                item.matched_folder = hist["actual_folder"]
                item.match_status = MatchStatus.MATCHED
                item.match_score = 1.0
                item.suggestion = f"已确认（{item.match_method}）"

        items.append(item)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    summary = ScanResultSummary.from_items(
        items=items,
        project_id=project_id,
        project_name=project_name,
        scan_directory=project_root or scan_directory or str(TEST_ROOT_PATH) if 'TEST_ROOT_PATH' in dir() else "",
        scan_duration_ms=elapsed_ms,
    )

    logger.info(
        "扫描结果汇总：%d 点位，已匹配=%d，部分=%d，未找到=%d，CAD缺失=%d，预算缺失=%d，耗时=%dms",
        summary.total_points, summary.matched_count, summary.partial_match_count,
        summary.not_found_count, summary.cad_missing_count, summary.budget_missing_count,
        elapsed_ms,
    )
    return summary


def _collect_files(folder_node, result: list[str], prefix: str = "") -> None:
    """递归收集文件夹下所有文件名（相对路径）。"""
    for f in folder_node.files:
        result.append(f"{prefix}{f.name}" if prefix else f.name)
    for sub in folder_node.subdirs:
        sub_prefix = f"{prefix}{sub.name}/" if prefix else f"{sub.name}/"
        _collect_files(sub, result, sub_prefix)


def _iter_files(folder_node):
    """递归遍历文件夹下所有文件节点。"""
    for f in folder_node.files:
        yield f
    for sub in folder_node.subdirs:
        yield from _iter_files(sub)


# ====================================================================
# v1.2.3：全局扫描结果缓存（项目列表统计统一数据源）
# ====================================================================

_project_summaries: dict[int, ScanResultSummary] = {}


def _cache_summary(project_id: int, summary: ScanResultSummary) -> None:
    """缓存项目扫描结果，供项目列表页读取。"""
    _project_summaries[project_id] = summary


def get_cached_summary(project_id: int) -> ScanResultSummary | None:
    """获取缓存的扫描结果（项目列表页统一数据源）。

    如果尚未扫描（无缓存），返回 None。
    调用方回退：显示 0。
    """
    return _project_summaries.get(project_id)


def clear_project_cache(project_id: int | None = None) -> None:
    """清除缓存（测试用）。"""
    if project_id is None:
        _project_summaries.clear()
    else:
        _project_summaries.pop(project_id, None)


def _make_project_node(project_name: str, project_path: str, file_index) -> object:
    """v1.3.1：从 FileIndex 构建 ProjectNode（直接扫描关联文件夹用）。"""
    from .scanner import ProjectNode
    proj = ProjectNode(name=project_name, path=project_path, file_index=file_index)
    return proj
