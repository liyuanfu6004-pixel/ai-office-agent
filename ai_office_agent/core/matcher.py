"""统一字符串匹配引擎 — v1.1.1 引入。

所有模糊匹配统一走本模块。业务代码禁止直接调用 RapidFuzz。

流程：
    原始字符串 A / B
        ↓ normalizer.for_comparison() 或 for_filesystem()
    标准化后字符串
        ↓ RapidFuzz（多策略综合评分）
    匹配结果（MatchResult）

配置（预留，以后放入 Settings）：
- 最低完全匹配分：95
- 最低包含匹配分：85
- 最低模糊匹配分：70
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from rapidfuzz import fuzz

from .normalizer import for_matching


# ====================================================================
# 阈值配置（预留，以后放入 Settings）
# ====================================================================

class MatchThresholds:
    """匹配阈值配置。预留从 Settings 加载的接口。"""

    # 完全一致或高度相似
    exact: int = 95
    # 包含关系
    contains: int = 85
    # 模糊匹配最低分
    fuzzy: int = 70

    def __repr__(self) -> str:
        return f"Thresholds(exact={self.exact}, contains={self.contains}, fuzzy={self.fuzzy})"


# 全局默认阈值（单例模式，以后从 Settings 替换）
_thresholds = MatchThresholds()


def get_thresholds() -> MatchThresholds:
    """获取当前阈值配置。"""
    return _thresholds


def configure_thresholds(exact: int | None = None, contains: int | None = None, fuzzy: int | None = None) -> None:
    """运行时调整阈值（供 Settings 加载时调用）。"""
    if exact is not None:
        _thresholds.exact = exact
    if contains is not None:
        _thresholds.contains = contains
    if fuzzy is not None:
        _thresholds.fuzzy = fuzzy


# ====================================================================
# 匹配结果
# ====================================================================


class MatchKind(Enum):
    """匹配类型。"""
    EXACT = auto()         # 标准化后完全一致
    CONTAINS = auto()      # 一方包含另一方
    FUZZY = auto()         # 模糊匹配（高相似度）
    WEAK = auto()          # 弱匹配（低于阈值）
    NONE = auto()          # 无匹配


@dataclass
class MatchResult:
    """统一匹配结果。

    不使用简单的 True/False，而是返回得分、类型和原因。
    """

    # 标准化后的字符串
    query_normalized: str = ""
    target_normalized: str = ""

    # 原始字符串
    query_raw: str = ""
    target_raw: str = ""

    # 匹配得分（0~100），使用 WRatio 综合评分
    score: float = 0.0

    # 匹配类型
    kind: MatchKind = MatchKind.NONE

    # 可读原因
    reason: str = ""

    # 附加信息（可选的上下文数据）
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_match(self) -> bool:
        """是否判定为匹配（完全/包含/模糊）。"""
        return self.kind in (MatchKind.EXACT, MatchKind.CONTAINS, MatchKind.FUZZY)

    @property
    def is_strong(self) -> bool:
        """强匹配（完全一致或包含关系）。"""
        return self.kind in (MatchKind.EXACT, MatchKind.CONTAINS)


# ====================================================================
# 匹配函数（统一入口）
# ====================================================================


def match_strings(
    a: str | None,
    b: str | None,
    *,
    use_filesystem_norm: bool = False,
) -> MatchResult:
    """通用字符串匹配——底层引擎（v1.2.3：统一使用 for_matching）。

    Args:
        a: 字符串 A。
        b: 字符串 B。
        use_filesystem_norm: （已废弃，保留兼容）始终使用 for_matching。

    Returns:
        MatchResult 含得分/类型/原因。
    """
    if a is None:
        a = ""
    if b is None:
        b = ""

    a_raw = str(a).strip()
    b_raw = str(b).strip()

    a_norm = for_matching(a_raw)
    b_norm = for_matching(b_raw)

    result = MatchResult(
        query_raw=a_raw,
        target_raw=b_raw,
        query_normalized=a_norm,
        target_normalized=b_norm,
    )

    # 快速路径：标准化后完全一致
    if a_norm == b_norm:
        result.score = 100.0
        result.kind = MatchKind.EXACT
        result.reason = "标准化后完全一致"
        return result

    # 快速路径：任一方为空
    if not a_norm or not b_norm:
        result.score = 0.0
        result.kind = MatchKind.NONE
        result.reason = "一方为空字符串"
        return result

    # 包含关系：partial_ratio 高且 ratio 适中
    partial = fuzz.partial_ratio(a_norm, b_norm)
    if partial >= _thresholds.exact:
        # partial 极高 → 一方完全包含另一方
        result.score = float(partial)
        result.kind = MatchKind.CONTAINS
        result.reason = "一方完全包含另一方"
        return result

    # 综合评分：WRatio
    w_ratio = fuzz.WRatio(a_norm, b_norm)

    if w_ratio >= _thresholds.exact:
        result.score = w_ratio
        result.kind = MatchKind.EXACT
        result.reason = f"高度相似（WRatio={w_ratio:.0f}）"
    elif w_ratio >= _thresholds.contains:
        result.score = w_ratio
        result.kind = MatchKind.CONTAINS
        result.reason = f"包含关系（WRatio={w_ratio:.0f}，partial={partial:.0f}）"
    elif w_ratio >= _thresholds.fuzzy:
        result.score = w_ratio
        result.kind = MatchKind.FUZZY
        result.reason = f"模糊匹配（WRatio={w_ratio:.0f}）"
    else:
        result.score = w_ratio
        result.kind = MatchKind.WEAK
        result.reason = f"低于阈值（WRatio={w_ratio:.0f} < {_thresholds.fuzzy}）"

    return result


# ====================================================================
# 场景化匹配函数（按业务场景命名）
# ====================================================================


def match_sheet(
    sheet_name: str | None,
    keyword: str | None,
) -> MatchResult:
    """匹配 Sheet 名称与规模表关键词。

    用于 Sheet 自动识别：判断一个 Sheet 是否可能是规模表。
    使用通用标准化（不去文件系统特殊字符）。

    Args:
        sheet_name: Excel Sheet 名称。
        keyword: 规模表关键词（如 "点位"、"明细"）。

    Returns:
        MatchResult。
    """
    return match_strings(sheet_name, keyword)


def match_field(
    header: str | None,
    keyword: str | None,
) -> MatchResult:
    """匹配表头字段名与关键词。

    用于字段智能识别：判断表头列是否匹配业务字段关键词。
    使用通用标准化。

    Args:
        header: Excel 表头名。
        keyword: 业务字段关键词（如 "点位名称"、"区县"）。

    Returns:
        MatchResult。
    """
    return match_strings(header, keyword)


def match_point_name(
    excel_name: str | None,
    standard_name: str | None,
) -> MatchResult:
    """匹配 Excel 原始点位名称与标准点位名称。

    用于点位字典匹配。
    使用文件系统标准化（去特殊字符）。

    Args:
        excel_name: Excel 原始点位名称。
        standard_name: 标准点位名称（point_dictionary.standard_point_name）。

    Returns:
        MatchResult。
    """
    return match_strings(excel_name, standard_name, use_filesystem_norm=True)


def match_folder(
    folder_name: str | None,
    target_name: str | None,
) -> MatchResult:
    """匹配文件夹名。

    用于沙盒扫描中的文件夹名称匹配（项目文件夹、点位文件夹）。
    使用文件系统标准化。

    Args:
        folder_name: 实际文件夹名。
        target_name: 目标名称（项目名、标准点位名）。

    Returns:
        MatchResult。
    """
    return match_strings(folder_name, target_name, use_filesystem_norm=True)


def match_filename(
    file_name: str | None,
    target_name: str | None,
) -> MatchResult:
    """匹配文件名。

    用于文件扫描匹配。
    使用文件系统标准化。

    Args:
        file_name: 实际文件名。
        target_name: 目标名称。

    Returns:
        MatchResult。
    """
    return match_strings(file_name, target_name, use_filesystem_norm=True)


# ====================================================================
# 批量匹配
# ====================================================================


def best_match(
    query: str | None,
    candidates: list[str],
    *,
    use_filesystem_norm: bool = False,
) -> MatchResult:
    """在候选列表中找出最佳匹配。

    Args:
        query: 查询字符串。
        candidates: 候选列表。
        use_filesystem_norm: 是否文件系统标准化。

    Returns:
        最佳匹配的 MatchResult。如果所有候选都低于 fuzzy 阈值，
        返回 kind=NONE 的结果，meta 中附所有候选的得分列表。
    """
    if not candidates:
        return MatchResult(
            query_raw=query or "",
            kind=MatchKind.NONE,
            reason="候选列表为空",
        )

    best: MatchResult | None = None
    all_results: list[dict] = []

    for c in candidates:
        r = match_strings(query, c, use_filesystem_norm=use_filesystem_norm)
        all_results.append({"target": c, "score": r.score, "kind": r.kind.name})
        if best is None or r.score > best.score:
            best = r

    if best is None:
        return MatchResult(
            query_raw=query or "",
            kind=MatchKind.NONE,
            reason="无候选",
        )

    best.meta["all_candidates"] = all_results
    return best


def any_match(
    query: str | None,
    candidates: list[str],
    *,
    threshold: int | None = None,
    use_filesystem_norm: bool = False,
) -> MatchResult | None:
    """在候选列表中返回第一个匹配（得分 ≥ threshold）的结果。

    Args:
        query: 查询字符串。
        candidates: 候选列表。
        threshold: 最低得分阈值，默认使用 _thresholds.fuzzy。
        use_filesystem_norm: 是否文件系统标准化。

    Returns:
        第一个达标的 MatchResult，或 None。
    """
    if threshold is None:
        threshold = _thresholds.fuzzy

    for c in candidates:
        r = match_strings(query, c, use_filesystem_norm=use_filesystem_norm)
        if r.score >= threshold:
            return r

    return None


# ====================================================================
# 快速判断（便利函数，返回 bool）
# ====================================================================


def is_match(
    a: str | None,
    b: str | None,
    *,
    use_filesystem_norm: bool = False,
) -> bool:
    """快速判断两字符串是否匹配。"""
    return match_strings(a, b, use_filesystem_norm=use_filesystem_norm).is_match


def is_strong_match(
    a: str | None,
    b: str | None,
    *,
    use_filesystem_norm: bool = False,
) -> bool:
    """快速判断两字符串是否强匹配（完全一致或包含关系）。"""
    return match_strings(a, b, use_filesystem_norm=use_filesystem_norm).is_strong


# ====================================================================
# v1.3.1：文件唯一归属匹配（file → all points → single winner）
# ====================================================================


@dataclass
class FilePointMatch:
    """文件对多个点位的匹配结果（Top1 Winner）。"""

    file_path: str
    file_name: str
    best_point_id: int | None = None     # 最佳匹配 point_id
    best_point_name: str = ""            # 最佳匹配 point_name
    best_score: float = 0.0              # 最佳得分（0-100）
    second_score: float = 0.0            # 次佳得分
    is_conflict: bool = False             # top1 ≈ top2
    is_assigned: bool = False             # 是否已归属某个点位


def match_file_to_points(
    file_name: str,
    file_path: str,
    points: list[dict],
    parent_dir_name: str = "",
) -> FilePointMatch:
    """文件 → 所有点位 → 单一归属（Top1 Winner 规则）。

    v1.3.3 修复：真实工程目录结构为 项目/{点位名}/{图纸|预算|其他文件}/{文件名}
    匹配策略：
    1) 「点位名在文件路径上的任意目录段」严格正向匹配——命中即归属
       该点位（点位名本身就是路径某一段，最可信）
    2) 否则走模糊 Top1 + 冲突检测（点位名拆段 vs 候选名）

    Args:
        file_name: 文件名。
        file_path: 文件路径。
        points: 点位列表 [{id, standard_point_name}]。
        parent_dir_name: 文件直接父目录名。
    """
    if not file_path or not points:
        return FilePointMatch(file_path=file_path, file_name=file_name,
                              best_point_id=None)

    from .normalizer import for_matching
    from pathlib import Path as _P

    # ── 策略1：只看目录段（去掉文件名）严格匹配 ──
    # 文件名可能含其他点位名（如"安宁-连然街道-...打印.pdf"放在另一点位目录下）
    # 只看目录段可避免文件名引起误判冲突
    try:
        all_parts = list(_P(file_path).parts)
        dir_parts = all_parts[:-1]           # 去掉最后一段（文件名）
        dir_norm = {for_matching(seg) for seg in dir_parts if seg}
    except Exception:
        dir_norm = set()
    dir_norm.discard("")

    # 点位名标准化去重：同名多个点位只算一个候选
    direct_hits: dict[str, dict] = {}
    for p in points:
        pname = p.get("standard_point_name", "")
        if not pname:
            continue
        pnorm = for_matching(pname)
        if pnorm and pnorm in dir_norm and pnorm not in direct_hits:
            direct_hits[pnorm] = p

    if len(direct_hits) == 1:
        # 目录路径只有一个点位名（去重后）→ 唯一归属，最可信
        p = next(iter(direct_hits.values()))
        return FilePointMatch(
            file_path=file_path, file_name=file_name,
            best_point_id=int(p["id"]),
            best_point_name=p["standard_point_name"],
            best_score=100.0, second_score=0.0,
            is_assigned=True,
        )
    if len(direct_hits) >= 2:
        # 目录路径含多个不同点位名 → 真冲突，不归属
        return FilePointMatch(
            file_path=file_path, file_name=file_name, best_point_id=None,
            best_score=100.0, second_score=100.0,
            is_conflict=True,
        )

    # ── 策略2：模糊 Top1 ──
    candidates: set[str] = set()
    if file_name:
        candidates.add(for_matching(file_name))
    if parent_dir_name:
        candidates.add(for_matching(parent_dir_name))
    try:
        for seg in _P(file_path).parts[-3:]:
            if seg:
                candidates.add(for_matching(seg))
    except Exception:
        pass
    candidates.discard("")

    if not candidates:
        return FilePointMatch(file_path=file_path, file_name=file_name,
                              best_point_id=None)

    scored: list[tuple[float, dict]] = []
    for p in points:
        pname = p.get("standard_point_name", "")
        if not pname:
            continue
        pname_norm = for_matching(pname)
        pname_segs = [s for s in pname_norm.split("-") if len(s) >= 2]
        best_for_point = 0.0
        for cand in candidates:
            r = match_strings(cand, pname)
            if r.score > best_for_point:
                best_for_point = r.score
            for seg in pname_segs:
                if seg:
                    r2 = match_strings(cand, seg)
                    if r2.score > best_for_point:
                        best_for_point = r2.score
        if best_for_point >= 60:
            scored.append((best_for_point, p))

    if not scored:
        return FilePointMatch(file_path=file_path, file_name=file_name,
                              best_point_id=None)

    scored.sort(key=lambda x: x[0], reverse=True)
    top_score, top_point = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    is_conflict = (top_score - second_score) < 5.0 if len(scored) >= 2 else False

    if is_conflict:
        return FilePointMatch(
            file_path=file_path, file_name=file_name, best_point_id=None,
            best_score=top_score, second_score=second_score,
            is_conflict=True,
        )

    return FilePointMatch(
        file_path=file_path, file_name=file_name,
        best_point_id=int(top_point["id"]),
        best_point_name=top_point["standard_point_name"],
        best_score=top_score, second_score=second_score,
        is_assigned=True,
    )
