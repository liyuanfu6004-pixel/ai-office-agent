"""文件唯一归属模型（Single Ownership Model）— v1.5 引入。

**核心规则**：
1. 唯一归属：每个文件只能属于一个点位（强制）
2. 归属决策流程：file → candidate points → matcher score → 取最高分点位
3. 归属阈值：score < 0.75 → 不归属任何点位；score ≥ 0.75 → 才允许绑定

**图纸特殊规则（强制）**：
- DWG / DXF / BAK / PDF 必须 stem 精确匹配点位名
- 禁止 fuzzy match 进入图纸归属
- PDF 与 CAD 同名才可绑定（由 file_organizer 的 CAD 索引处理，本模块只做归属）

**两阶段模型**：
1. 候选生成（允许多点）：对每个文件，对每个点位打分
2. 唯一归属决策（只保留一个 owner）：取 Top1，且 score ≥ 0.75

**禁止行为**：
- 禁止一个文件归属多个点位
- 禁止扫描阶段直接写归属（归属决策必须走本模块）
- 禁止 fuzzy match 参与图纸归属

**输出目标**：
- 每个文件只有一个归属点位（或无归属）
- 点位详情文件不重叠
- 图纸/预算分类稳定一致
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .file_index import FileEntry, FileIndex
from .matcher import match_strings
from .normalizer import for_matching
from ..utils.logger import setup_logger

logger = setup_logger()


# ====================================================================
# 常量
# ====================================================================

# 归属阈值（0.0 ~ 1.0）。低于此值的文件不归属任何点位。
OWNERSHIP_THRESHOLD: float = 0.75

# Top1 与 Top2 得分差小于此值 → 冲突，不归属
CONFLICT_MARGIN: float = 0.05

# 图纸文件扩展名（必须 stem/路径精确匹配；预算 PDF 例外走预算识别）
DRAWING_EXTS: frozenset[str] = frozenset({".dwg", ".dxf", ".bak", ".pdf"})

# 泛分类目录名：只能作为文件类别线索，不能作为点位身份线索。
_GENERIC_DIR_NAMES: frozenset[str] = frozenset({
    "图纸", "设计图", "施工图", "预算", "其他文件", "其他", "资料",
    "other", "cad", "pdf", "dwg", "drawing", "drawings", "budget", "cost",
})


# ====================================================================
# 数据结构
# ====================================================================


@dataclass
class OwnershipDecision:
    """单个文件的归属决策结果。"""

    file: FileEntry
    best_point_id: int | None = None
    best_point_name: str = ""
    best_score: float = 0.0       # 0.0 ~ 1.0
    second_score: float = 0.0
    is_assigned: bool = False     # 是否已归属
    is_conflict: bool = False     # Top1 ≈ Top2 冲突
    is_drawing: bool = False      # 是否图纸类文件
    reason: str = ""              # 决策原因


@dataclass
class OwnershipResult:
    """整个项目的归属决策结果。"""

    # file_path → OwnershipDecision
    decisions: dict[str, OwnershipDecision] = field(default_factory=dict)
    # point_id → [FileEntry, ...]  只含已归属文件
    point_files: dict[int, list[FileEntry]] = field(default_factory=dict)
    # point_id → (cad_status, budget_status)
    point_status: dict[int, tuple[str, str]] = field(default_factory=dict)
    # 冲突文件路径列表
    conflict_files: list[str] = field(default_factory=list)
    # 未归属文件路径列表
    unassigned_files: list[str] = field(default_factory=list)
    # 未归属的预算文件路径列表（文件名含预算关键词但无法确定点位，需人工确认）
    unassigned_budget_files: list[str] = field(default_factory=list)

    @property
    def assigned_count(self) -> int:
        return sum(len(v) for v in self.point_files.values())

    def files_for_point(self, point_id: int) -> list[FileEntry]:
        """获取归属到某点位的所有文件。"""
        return self.point_files.get(point_id, [])

    def status_for_point(self, point_id: int) -> tuple[str, str]:
        """获取某点位的 (cad_status, budget_status)。"""
        return self.point_status.get(point_id, ("无", "无"))


# ====================================================================
# 阶段1：候选生成
# ====================================================================


def _is_generic_dir_name(name: str) -> bool:
    """判断路径片段是否只是泛分类目录名。"""
    norm = for_matching(name)
    return norm in {for_matching(x) for x in _GENERIC_DIR_NAMES}


def _path_segments(file: FileEntry) -> list[str]:
    """返回文件完整路径中的标准化非泛分类片段。"""
    segments: list[str] = []
    try:
        for seg in Path(file.full_path).parts:
            if not seg or seg in ("/", "\\"):
                continue
            norm = for_matching(Path(seg).stem if "." in seg else seg)
            if norm and not _is_generic_dir_name(seg):
                segments.append(norm)
    except Exception:
        pass
    return segments


def _is_budget_like_file(file: FileEntry, point_name: str = "") -> bool:
    """预算类文件判断；用于 PDF 预算文件跳过图纸严格规则。"""
    import re as _re
    budget_exts = {".xls", ".xlsx", ".et", ".csv"}
    budget_keywords = (
        "预算", "概算", "造价", "报价",
        "cost", "estimate", "budget",
        "CPMS结构数据", "嘉陵版", "安全事故防范", "安全生产费依据",
    )
    norm = for_matching(file.file_name)
    for kw in budget_keywords:
        if for_matching(kw) in norm:
            return True
    if point_name and file.extension in budget_exts:
        stem = for_matching(Path(file.file_name).stem)
        stem_no_digits = _re.sub(r"\d+", "", stem).strip("-_ ")
        point_norm = for_matching(point_name)
        if _stem_matches_point(stem_no_digits, point_norm):
            return True
    return False


def _stem_matches_point(stem_no_digits: str, point_norm: str, stem_raw: str = "") -> bool:
    """检查去数字后的 stem 是否匹配点位名（精确 / 前缀 / 包含）。

    v1.5.7：增加原始 stem 包含点位名的检查，解决去数字后失配问题。
    """
    if not stem_no_digits or len(stem_no_digits) < 2:
        return False
    if stem_no_digits == point_norm:
        return True
    # 点位名以 stem 开头（如文件"安宁-县街街道.xlsx"匹配点位"安宁-县街街道-扩容"）
    if point_norm.startswith(stem_no_digits + "-"):
        return True
    # v1.5.7：原始 stem 包含完整点位名（如"昆明湖中坝5号地块瑞园五GJ001预算"）
    if stem_raw and len(point_norm) >= 4 and point_norm in stem_raw:
        return True
    return False


def _is_drawing_file(file: FileEntry) -> bool:
    """判断是否图纸类文件。"""
    return file.extension in DRAWING_EXTS


def _stem_match(file: FileEntry, point_name: str) -> bool:
    """图纸类文件的严格归属证据（v1.5.3：仅 stem 匹配，禁止路径匹配）。

    v1.5.3 修复：移除"路径包含点位名"规则。
    旧规则导致两个严重问题：
    1. 文件被误整理到错误目录后，路径包含错误点位名 → 错误归属
    2. 文件 stem 匹配点位A，但路径包含点位B → 冲突 → 不归属任何点位

    新规则（仅 stem）：
    1. 文件 stem 标准化后 == 点位名标准化后
    2. 文件 stem 标准化后以点位名标准化后开头（兼容带时间戳后缀的文件名）
    3. 点位名包含在 stem 中（兼容文件含编号前缀，如"01-昆明湖中坝...dwg"）
    """
    norm_point = for_matching(point_name)
    if not norm_point or len(norm_point) < 2:
        return False

    norm_stem = for_matching(Path(file.file_name).stem)

    if norm_stem == norm_point:
        return True
    if norm_stem.startswith(norm_point):
        return True
    # v1.5.7：点位名包含在 stem 中（文件含编号前缀等）
    if norm_point in norm_stem:
        return True
    return False


def _score_file_to_point(
    file: FileEntry,
    point: dict,
    all_point_names_norm: set[str] | None = None,
) -> float:
    """阶段1：为单个文件对单个点位打分（0.0 ~ 1.0）。

    图纸类文件：必须 stem 精确匹配，否则得 0 分。
    非图纸类文件：分层评分。

    v1.5.6 分层评分（解决文件名含点位A但路径在点位B目录下的冲突）：
    - Tier 1: stem 含完整点位名 → 0.95（最强证据，立即返回）
    - Tier 2: 路径含完整点位名 → 0.85
    - Tier 3: 全名模糊匹配 → 封顶 0.88
    - Tier 4: 分段模糊匹配 → 封顶 0.75（防止「分纤箱扩容点位」等公共后缀误匹配）

    v1.5.7 反向排斥（解决其他点位文件被误归到目录所在点位）：
    - stem 含其他已知点位名 → return 0.0（文件属于另一个点位）
    - stem 含「分纤箱扩容」但当前点位名不含 → return 0.0
    """
    pname = point.get("standard_point_name", "")
    if not pname:
        return 0.0

    # 图纸类文件：强制严格证据；预算 PDF 作为预算资料参与普通归属。
    if _is_drawing_file(file) and not _is_budget_like_file(file, pname):
        if _stem_match(file, pname):
            return 1.0
        return 0.0

    norm_pname = for_matching(pname)
    if not norm_pname:
        return 0.0

    stem = for_matching(Path(file.file_name).stem)

    # ── Tier 1: stem 含完整点位名 → 最强证据（立即返回）──
    # 文件名直接包含点位名，比路径证据更可信。
    # 例如「盘龙-联盟街道-分纤箱扩容点位202606121558.xlsx」
    # 即使放在「安宁-太平新城街道」目录下，也应归属「盘龙-联盟街道」。
    if stem and len(norm_pname) >= 4 and norm_pname in stem:
        return 0.95

    # ── 反向排斥：stem 明确指向其他点位 → 不归属当前点位 ──
    # 场景：五华-丰宁街道的预算文件放在石林县宜奈一楼无线机房目录下，
    # stem 含「五华-丰宁街道-分纤箱扩容点位」但当前点位是「石林县宜奈...」，
    # 不应仅凭路径证据归属到石林县宜奈。
    if stem:
        # 检查 1：stem 含其他已知点位名
        if all_point_names_norm:
            for other_norm in all_point_names_norm:
                if (
                    other_norm != norm_pname
                    and len(other_norm) >= 4
                    and other_norm in stem
                ):
                    return 0.0  # 文件名明确指向另一个点位

        # 检查 2：stem 含「分纤箱扩容」但当前点位名不含
        # 「分纤箱扩容」是分纤箱类点位的特征后缀，如果文件名含此关键词
        # 但当前点位不是分纤箱类点位，说明文件属于其他点位。
        if "分纤箱扩容" in stem and "分纤箱扩容" not in norm_pname:
            return 0.0

    # ── 构建路径候选（不含 stem）──
    path_candidates: list[str] = []
    parent = for_matching(file.parent_dir)
    if parent and not _is_generic_dir_name(file.parent_dir):
        path_candidates.append(parent)
    path_candidates.extend(_path_segments(file))
    path_text = "-".join(_path_segments(file))
    if path_text:
        path_candidates.append(path_text)

    # 全候选 = 路径候选 + stem（用于模糊匹配，但不含 Tier1 的精确检查）
    all_candidates = list(path_candidates)
    if stem:
        all_candidates.append(stem)

    best = 0.0

    # ── Tier 2: 路径含完整点位名（需 stem 有一定关联）──
    # v1.5.7 修复：单纯路径证据不够，要求 stem 与点位名至少 60% 相似。
    # 否则像「五华-红云街道-分纤箱扩容点位.xlsx」放在「安宁-太平新城街道」目录下
    # 会被误归属到安宁点位。
    for cand in path_candidates:
        if not cand:
            continue
        if len(norm_pname) >= 4 and norm_pname in cand:
            if stem:
                stem_rel = match_strings(stem, pname).score
                if stem_rel >= 65:
                    best = max(best, 0.85)
                else:
                    # stem 不相关 → 路径证据不充分（降权至 < 阈值 0.75）
                    best = max(best, 0.65)
            else:
                best = max(best, 0.85)

    # ── Tier 3: 全名模糊匹配（封顶 0.88，确保低于 Tier1 的 0.95）──
    # 封顶 0.88 而非 0.90：避免浮点精度导致 0.95-0.90=0.0499...<0.05 误判冲突
    for cand in all_candidates:
        if not cand:
            continue
        r = match_strings(cand, pname)
        s = min(r.score / 100.0, 0.88)
        if s > best:
            best = s

    # ── Tier 4: 分段模糊匹配（封顶 0.75，防止公共后缀误匹配）──
    # 「分纤箱扩容点位」是所有点位的公共后缀，partial_ratio 会给 100 分，
    # 但这不代表文件属于该点位。封顶 0.75 确保分段匹配不会覆盖 Tier1/2/3。
    for cand in all_candidates:
        if not cand:
            continue
        for seg in norm_pname.split("-"):
            if len(seg) >= 2:
                r2 = match_strings(cand, seg)
                s2 = min(r2.score / 100.0, 0.75)
                if s2 > best:
                    best = s2

    return best


def _generate_candidates(
    files: list[FileEntry],
    points: list[dict],
) -> dict[str, list[tuple[float, dict]]]:
    """阶段1：为每个文件生成所有候选点位的得分。

    Returns:
        {file_path: [(score, point), ...]} 按得分降序。
    """
    # 预计算所有点位名的标准化集合，用于反向排斥检查
    all_point_names_norm: set[str] = set()
    for p in points:
        pname = p.get("standard_point_name", "")
        if pname:
            norm = for_matching(pname)
            if norm:
                all_point_names_norm.add(norm)

    candidates: dict[str, list[tuple[float, dict]]] = {}
    for file in files:
        scored: list[tuple[float, dict]] = []
        for p in points:
            score = _score_file_to_point(file, p, all_point_names_norm)
            if score > 0.0:
                scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        candidates[file.full_path] = scored
    return candidates


# ====================================================================
# 阶段2：唯一归属决策
# ====================================================================


def _decide_ownership(
    file: FileEntry,
    candidates: list[tuple[float, dict]],
) -> OwnershipDecision:
    """阶段2：对单个文件做唯一归属决策。

    规则：
    - 无候选 → 不归属
    - Top1 score < OWNERSHIP_THRESHOLD → 不归属
    - Top1 - Top2 < CONFLICT_MARGIN → 冲突，不归属
    - 否则归属 Top1
    """
    decision = OwnershipDecision(file=file, is_drawing=_is_drawing_file(file))

    if not candidates:
        decision.reason = "无候选点位"
        return decision

    top_score, top_point = candidates[0]
    second_score = candidates[1][0] if len(candidates) > 1 else 0.0

    decision.best_score = top_score
    decision.second_score = second_score

    if top_score < OWNERSHIP_THRESHOLD:
        decision.reason = f"Top1 得分 {top_score:.2f} < 阈值 {OWNERSHIP_THRESHOLD}"
        return decision

    if len(candidates) >= 2 and (top_score - second_score) < CONFLICT_MARGIN:
        decision.is_conflict = True
        decision.reason = (
            f"冲突：Top1={top_score:.2f} Top2={second_score:.2f} "
            f"差值 < {CONFLICT_MARGIN}"
        )
        return decision

    decision.best_point_id = int(top_point["id"])
    decision.best_point_name = top_point.get("standard_point_name", "")
    decision.is_assigned = True
    decision.reason = (
        f"归属：{decision.best_point_name}（score={top_score:.2f}）"
    )
    return decision


# ====================================================================
# 状态计算
# ====================================================================


def _is_budget_file(file: FileEntry, point_name: str) -> bool:
    """v1.5.2 判断文件是否为预算文件（与 file_organizer.classify_file 一致）。

    规则：
    1. 文件名含预算关键词（不限扩展名）→ 预算
    2. 表格类扩展名 + stem 去数字后 == 点位名 → 预算
    """
    import re as _re
    budget_exts = {".xls", ".xlsx", ".et", ".csv"}
    budget_keywords = (
        "预算", "概算", "造价", "报价",
        "cost", "estimate", "budget",
        "CPMS结构数据", "嘉陵版", "安全事故防范", "安全生产费依据",
    )

    norm = for_matching(file.file_name)
    for kw in budget_keywords:
        if for_matching(kw) in norm:
            return True

    if file.extension in budget_exts:
        stem = for_matching(Path(file.file_name).stem)
        stem_no_digits = _re.sub(r"\d+", "", stem).strip("-_ ")
        point_norm = for_matching(point_name)
        if _stem_matches_point(stem_no_digits, point_norm, stem):
            return True

    return False


def _compute_status(files: list[FileEntry], point_name: str = "") -> tuple[str, str]:
    """根据归属文件列表计算 (cad_status, budget_status)。

    v1.5.2 预算识别规则与 file_organizer.classify_file 保持一致。
    """
    has_cad = False
    has_budget = False

    for f in files:
        if f.extension == ".dwg":
            has_cad = True
            continue
        if _is_budget_file(f, point_name):
            has_budget = True

    return ("有" if has_cad else "无", "有" if has_budget else "无")


# ====================================================================
# 主入口
# ====================================================================


def assign_ownership(
    file_index: FileIndex,
    points: list[dict],
) -> OwnershipResult:
    """两阶段唯一归属模型主入口。

    Args:
        file_index: 项目的 FileIndex（含全量文件）。
        points: 点位字典列表 [{id, standard_point_name, county, ...}]。

    Returns:
        OwnershipResult 含每个文件的归属决策、每个点位的文件列表和状态。

    禁止行为：
    - 本函数不写数据库，只做决策
    - 本函数不调用 global_match_point（避免反向匹配污染）
    """
    result = OwnershipResult()

    if not points:
        logger.warning("归属决策：点位列表为空")
        return result

    # 阶段1：候选生成
    candidates = _generate_candidates(file_index.files, points)

    # 阶段2：唯一归属决策
    for file in file_index.files:
        decision = _decide_ownership(file, candidates.get(file.full_path, []))
        result.decisions[file.full_path] = decision

        if decision.is_assigned and decision.best_point_id is not None:
            pid = decision.best_point_id
            if pid not in result.point_files:
                result.point_files[pid] = []
            result.point_files[pid].append(file)
        elif decision.is_conflict:
            result.conflict_files.append(file.full_path)
        else:
            result.unassigned_files.append(file.full_path)

    # ── 识别未归属的预算文件（仅关键词匹配，不依赖点位名）──
    for file_path in result.unassigned_files:
        file = next((f for f in file_index.files if f.full_path == file_path), None)
        if file and _is_budget_like_file(file):  # point_name="" → 仅关键词匹配
            result.unassigned_budget_files.append(file_path)

    # 状态计算（基于唯一归属的文件列表，不使用 global_match_point）
    for p in points:
        pid = int(p["id"])
        pname = p.get("standard_point_name", "")
        files = result.point_files.get(pid, [])
        result.point_status[pid] = _compute_status(files, pname)

    logger.info(
        "唯一归属决策：%d 文件，已归属=%d，冲突=%d，未归属=%d（含未归属预算=%d），点位置=%d",
        len(result.decisions),
        result.assigned_count,
        len(result.conflict_files),
        len(result.unassigned_files),
        len(result.unassigned_budget_files),
        len(points),
    )
    return result


def get_scanned_files_for_point(
    result: OwnershipResult,
    point_id: int,
    limit: int = 50,
) -> list[str]:
    """获取某点位的扫描文件名列表（用于 UI 展示）。

    基于唯一归属结果，不调用 global_match_point。
    """
    files = result.files_for_point(point_id)
    return [f.file_name for f in files[:limit]]


def get_file_counts_for_point(
    result: OwnershipResult,
    point_id: int,
    point_name: str = "",
) -> tuple[int, int]:
    """获取某点位的 (cad_file_count, budget_file_count)。

    基于唯一归属结果。v1.5.2 预算计数规则与 classify_file 一致。
    """
    files = result.files_for_point(point_id)
    cad_count = sum(1 for f in files if f.extension == ".dwg")
    budget_count = 0
    for f in files:
        if f.extension == ".dwg":
            continue
        if _is_budget_file(f, point_name):
            budget_count += 1
    return (cad_count, budget_count)
