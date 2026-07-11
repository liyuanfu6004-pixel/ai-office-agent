"""文件自动整理引擎 — v1.3 引入。

将混乱的项目目录按"图纸优先语义体系"整理为标准结构：

标准目录结构（不可变）：
    项目/
     ├── 点位A/
     │    ├── 图纸/
     │    ├── 预算/
     │    └── 其他文件/

分类优先级（强制）：图纸 > 预算 > 其他

图纸识别规则：
    1. 直接图纸文件类型：.dwg / .dxf / .bak
    2. PDF↔CAD 同名规则：PDF 文件名（去扩展名）匹配任意 CAD 文件 stem → 图纸
    3. CAD 语义体系：只要存在 DWG/DXF/BAK，同名 PDF 自动归入图纸

预算识别规则（仅当不满足图纸条件时）：
    - 文件类型：.xls/.xlsx/.et/.csv
    - 关键词：预算/概算/造价/报价/清单/cost/estimate

冲突规则：永远归类为【图纸】

安全规则（强制）：
    - 禁止删除文件
    - 禁止覆盖文件
    - 禁止未确认的重命名
    - Dry Run 默认模式
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .file_index import FileIndex, FileEntry
from .normalizer import for_matching
from ..utils.logger import setup_logger

logger = setup_logger()

# ====================================================================
# 文件类型定义
# ====================================================================

# 图纸文件扩展名（直接识别）
_DRAWING_EXTS: frozenset[str] = frozenset({".dwg", ".dxf", ".bak"})

# 预算文件扩展名
_BUDGET_EXTS: frozenset[str] = frozenset({".xls", ".xlsx", ".et", ".csv"})

# 预算关键词（文件名含任一关键词 → 预算，不限扩展名）
_BUDGET_KEYWORDS: tuple[str, ...] = (
    "预算", "概算", "造价", "报价",
    "cost", "estimate", "budget",
    # v1.5.2：业务补充关键词（来自实际工程文件命名）
    "CPMS结构数据", "嘉陵版", "安全事故防范", "安全生产费依据",
)


def _is_budget_like_file(file: FileEntry, point_name: str = "") -> bool:
    """判断预算类文件（含预算 PDF）。"""
    import re as _re
    match_name = for_matching(file.file_name)
    for kw in _BUDGET_KEYWORDS:
        if for_matching(kw) in match_name:
            return True
    if file.extension.lower() in _BUDGET_EXTS:
        stem_norm = for_matching(Path(file.file_name).stem)
        stem_no_digits = _re.sub(r"\d+", "", stem_norm).strip("-_ ")
        point_norm = for_matching(point_name)
        if stem_no_digits and len(stem_no_digits) >= 2:
            if stem_no_digits == point_norm:
                return True
            if point_norm.startswith(stem_no_digits + "-"):
                return True
    return False


# ====================================================================
# 分类结果
# ====================================================================


@dataclass
class ClassificationResult:
    """单个文件的分类结果。"""

    file: FileEntry          # 原始文件条目
    category: str            # "图纸" | "预算" | "其他"
    reason: str              # 分类依据
    target_dir: str          # 目标子目录名（图纸/预算/其他文件）
    target_path: str = ""    # 目标完整路径（Dry Run 时为空）


@dataclass
class OrganizePlan:
    """一次整理操作的完整计划。

    列出每个点位下的文件分类和移动计划。
    """

    project_path: str = ""
    points: dict[str, list[ClassificationResult]] = field(default_factory=dict)
    total_files: int = 0
    drawing_count: int = 0
    budget_count: int = 0
    other_count: int = 0
    # 冲突文件列表（目标位置已有同名文件）
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转为可序列化 dict（供 UI 预览）。"""
        result: dict[str, Any] = {
            "project_path": self.project_path,
            "total_files": self.total_files,
            "drawing_count": self.drawing_count,
            "budget_count": self.budget_count,
            "other_count": self.other_count,
            "conflicts": self.conflicts,
            "points": {},
        }
        for pname, items in self.points.items():
            result["points"][pname] = [
                {
                    "file_name": r.file.file_name,
                    "category": r.category,
                    "reason": r.reason,
                    "target_dir": r.target_dir,
                }
                for r in items
            ]
        return result


# ====================================================================
# CAD 索引
# ====================================================================


def build_cad_index(files: list[FileEntry]) -> dict[str, list[FileEntry]]:
    """构建 CAD 索引：{stem_name: [FileEntry, ...]}。

    stem_name = 文件名去扩展名的小写形式。
    包含 .dwg/.dxf/.bak 文件。
    """
    cad_index: dict[str, list[FileEntry]] = {}
    for f in files:
        if f.extension in _DRAWING_EXTS:
            stem = Path(f.file_name).stem.lower()
            if stem not in cad_index:
                cad_index[stem] = []
            cad_index[stem].append(f)
    logger.debug("CAD 索引：%d 个 stem，%d 个文件",
                 len(cad_index), sum(len(v) for v in cad_index.values()))
    return cad_index


# ====================================================================
# 分类引擎
# ====================================================================


def classify_file(
    file: FileEntry,
    cad_index: dict[str, list[FileEntry]],
    point_name: str,
    point_dir: str,
) -> ClassificationResult:
    """对单个文件进行分类（图纸 > 预算 > 其他资料）。

    v1.6 目录结构：
        项目根目录/设计文件/{点位名}/图纸/
        项目根目录/设计文件/{点位名}/预算/
        项目根目录/设计文件/{点位名}/其他资料/

    分类规则（优先级）：
    1. 图纸：直接图纸类型(.dwg/.dxf/.bak) 或 PDF 匹配 CAD stem
    2. 预算：文件名含预算关键词 或 表格类+stem去数字=点位名
    3. 其他资料：所有剩余文件

    Args:
        file: 文件条目。
        cad_index: CAD stem → FileEntry 映射。
        point_name: 点位名称。
        point_dir: 点位目录路径（= 项目根目录/设计文件/{点位名}）。

    Returns:
        ClassificationResult。
    """
    ext = file.extension.lower()
    stem = Path(file.file_name).stem.lower()

    # ── 图纸识别（最高优先级）──
    # 1) 直接图纸类型
    if ext in _DRAWING_EXTS:
        if not _drawing_belongs_to_point(file, point_name):
            return ClassificationResult(
                file=file, category="其他",
                reason=f"非本点位图纸 ({ext})",
                target_dir=Path(point_dir) / "其他资料",
            )
        return ClassificationResult(
            file=file, category="图纸",
            reason=f"图纸文件 ({ext})",
            target_dir=Path(point_dir) / "图纸",
        )

    # 2) PDF ↔ CAD 同名规则
    if ext == ".pdf" and stem in cad_index:
        cad_files = [c.file_name for c in cad_index[stem]]
        return ClassificationResult(
            file=file, category="图纸",
            reason=f"PDF 匹配 CAD: {', '.join(cad_files)}",
            target_dir=Path(point_dir) / "图纸",
        )

    # ── 预算识别（次级）──
    match_name = for_matching(file.file_name)
    for kw in _BUDGET_KEYWORDS:
        if for_matching(kw) in match_name:
            return ClassificationResult(
                file=file, category="预算",
                reason=f"预算关键词「{kw}」",
                target_dir=Path(point_dir) / "预算",
            )

    if ext in _BUDGET_EXTS:
        stem_norm = for_matching(stem)
        point_norm = for_matching(point_name)

        # 优先：stem 含完整点位名（兼容带时间戳后缀的预算文件）
        # 例：stem = "西山区海口街道...GJ001202606121607" 含 point_norm = "西山区海口街道...GJ001"
        if len(point_norm) >= 4 and point_norm in stem_norm:
            return ClassificationResult(
                file=file, category="预算",
                reason=f"表格文件 stem 含点位名",
                target_dir=Path(point_dir) / "预算",
            )

        # 备用：stem 去数字后匹配（兼容纯地点名+时间戳的简单命名）
        import re as _re
        stem_no_digits = _re.sub(r"\d+", "", stem_norm).strip("-_ ")
        if stem_no_digits and len(stem_no_digits) >= 2:
            if stem_no_digits == point_norm:
                return ClassificationResult(
                    file=file, category="预算",
                    reason=f"表格文件 stem 去数字=点位名（{stem_no_digits}）",
                    target_dir=Path(point_dir) / "预算",
                )
            if point_norm.startswith(stem_no_digits + "-"):
                return ClassificationResult(
                    file=file, category="预算",
                    reason=f"表格文件 stem 去数字为点位名前缀（{stem_no_digits}）",
                    target_dir=Path(point_dir) / "预算",
                )

    # ── 其他资料 ──
    return ClassificationResult(
        file=file, category="其他",
        reason="其他资料",
        target_dir=Path(point_dir) / "其他资料",
    )


# ====================================================================
# 整理计划生成器
# ====================================================================


def _generic_dir_names() -> frozenset[str]:
    return frozenset({
        "图纸", "设计图", "施工图", "预算", "其他资料", "其他文件", "其他", "资料",
        "设计文件",
        "other", "cad", "pdf", "dwg", "drawing", "drawings", "budget", "cost",
    })


def _drawing_belongs_to_point(file: FileEntry, point_name: str) -> bool:
    """判断图纸文件是否真正属于该点位（v1.5.3：仅 stem 匹配）。

    v1.5.3 修复：移除路径匹配规则，与 ownership._stem_match 保持一致。
    旧规则"路径包含点位名"导致误整理后的文件被错误归属。

    新规则（仅 stem）：
    1. 文件 stem 标准化后 == 点位名标准化后
    2. 文件 stem 标准化后以点位名标准化后开头（兼容带时间戳后缀的文件名）
    3. 点位名包含在 stem 中（兼容文件含编号前缀，如"01-昆明湖中坝...dwg"）
    """
    norm_point = for_matching(point_name)
    if not norm_point:
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


def build_organize_plan(
    point_files: dict[str, list[FileEntry]],
    project_path: str,
    point_counties: dict[str, str] | None = None,
) -> OrganizePlan:
    """为所有点位生成整理计划。

    v1.6 目录结构：
        项目根目录/设计文件/{区县}/{点位名}/图纸/
        项目根目录/设计文件/{区县}/{点位名}/预算/
        项目根目录/设计文件/{区县}/{点位名}/其他资料/
        区县未知时 → 项目根目录/设计文件/其他区县/{点位名}/

    Args:
        point_files: {point_name: [FileEntry, ...]}（来自 ownership 匹配结果）。
        project_path: 项目根目录路径。
        point_counties: {point_name: county} 区县映射（可选）。

    Returns:
        OrganizePlan 含所有分类和冲突。
    """
    plan = OrganizePlan(project_path=project_path)
    if point_counties is None:
        point_counties = {}
    # v1.6：所有整理目标在「设计文件」目录下
    # v1.6.2：如果用户选择的扫描目录本身就叫「设计文件」，直接在此目录下整理，
    # 避免出现 设计文件/设计文件/ 的嵌套路径。
    project_path_obj = Path(project_path).resolve()
    if project_path_obj.name == "设计文件":
        design_dir = project_path_obj
    else:
        design_dir = project_path_obj / "设计文件"

    for pname, files in point_files.items():
        # v1.6.1：点位名含 / → 直接删除（如 SL-DZCC/III-GJ001 → SL-DZCCIII-GJ001）
        county = point_counties.get(pname, "其他区县")
        safe_pname = pname.replace("/", "")
        point_dir = design_dir / county / safe_pname

        drawing_files = [
            f for f in files
            if f.extension in _DRAWING_EXTS and _drawing_belongs_to_point(f, pname)
        ]
        cad_index = build_cad_index(drawing_files)

        classifications: list[ClassificationResult] = []
        for f in files:
            result = classify_file(f, cad_index, pname, str(point_dir))
            result.target_path = str(result.target_dir / f.file_name)
            classifications.append(result)

        plan.points[pname] = classifications
        plan.total_files += len(classifications)

        for r in classifications:
            if r.category == "图纸":
                plan.drawing_count += 1
            elif r.category == "预算":
                plan.budget_count += 1
            else:
                plan.other_count += 1

        # 冲突检测：目标路径已存在同名文件
        seen_targets: set[str] = set()
        for r in classifications:
            dest = str(Path(r.target_path).resolve())
            if dest in seen_targets:
                plan.conflicts.append(
                    f"{pname}/{r.file.file_name} → {r.target_dir}"
                )
            seen_targets.add(dest)

    logger.info(
        "整理计划：%d 点位置，%d 文件（图纸=%d 预算=%d 其他=%d）冲突=%d",
        len(plan.points), plan.total_files,
        plan.drawing_count, plan.budget_count, plan.other_count,
        len(plan.conflicts),
    )
    return plan


# ====================================================================
# v1.5：基于唯一归属模型的整理计划入口
# ====================================================================


def build_organize_plan_from_ownership(
    file_index,
    points: list[dict],
    project_path: str,
) -> OrganizePlan:
    """v1.5：基于唯一归属模型生成整理计划。

    使用 ownership.assign_ownership 做唯一归属决策，
    禁止调用 file_index.global_match_point（反向匹配污染源）。

    Args:
        file_index: 项目的 FileIndex。
        points: 点位字典列表 [{id, standard_point_name, ...}]。
        project_path: 项目根目录路径。

    Returns:
        OrganizePlan 含所有分类和冲突。
    """
    from .ownership import assign_ownership

    ownership = assign_ownership(file_index, points)

    # 构建 point_id → {name, county} 映射
    pid_info: dict[int, dict] = {}
    for p in points:
        pid_info[int(p["id"])] = {
            "name": p.get("standard_point_name", ""),
            "county": p.get("county", ""),
        }

    # 转换为 build_organize_plan 所需的 {point_name: [FileEntry]} 格式
    point_files: dict[str, list[FileEntry]] = {}
    point_counties: dict[str, str] = {}
    for pid, files in ownership.point_files.items():
        info = pid_info.get(pid, {})
        pname = info.get("name", "")
        county = info.get("county", "")
        if pname:
            point_files[pname] = files
            if county:
                point_counties[pname] = county

    return build_organize_plan(point_files, project_path, point_counties)


def build_organize_plan_from_scan_session(
    point_files: dict[str | int, list[dict | FileEntry]],
    points: list[dict],
    project_path: str,
) -> OrganizePlan:
    """v1.5.3：基于当前 Scan Session 的唯一归属结果生成整理计划。

    本入口只消费已经保存的 ownership.point_files，不重新扫描、
    不重新调用 assign_ownership，避免文件整理预览/执行造成重复扫描。
    """
    pid_info: dict[int, dict] = {}
    for p in points:
        if p.get("id") is None:
            continue
        pid_info[int(p["id"])] = {
            "name": p.get("standard_point_name", ""),
            "county": p.get("county", ""),
        }

    converted: dict[str, list[FileEntry]] = {}
    point_counties: dict[str, str] = {}
    for raw_pid, raw_files in point_files.items():
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            continue
        info = pid_info.get(pid, {})
        pname = info.get("name", "")
        county = info.get("county", "")
        if not pname:
            continue
        if county:
            point_counties[pname] = county

        files: list[FileEntry] = []
        for raw_file in raw_files:
            if isinstance(raw_file, FileEntry):
                files.append(raw_file)
            elif isinstance(raw_file, dict):
                files.append(FileEntry(
                    file_name=raw_file.get("file_name", ""),
                    full_path=raw_file.get("full_path", ""),
                    extension=raw_file.get("extension", ""),
                    normalized_name=raw_file.get("normalized_name", ""),
                    parent_dir=raw_file.get("parent_dir", ""),
                    parent_path=raw_file.get("parent_path", ""),
                ))
        if files:
            converted[pname] = files

    return build_organize_plan(converted, project_path, point_counties)


# ====================================================================
# 执行器
# ====================================================================


def apply_organize_plan(plan: OrganizePlan) -> dict[str, Any]:
    """执行整理计划（Apply Mode）。

    实际移动文件到标准目录结构。
    安全规则：
    - 不删除文件
    - 不覆盖文件（冲突文件跳过）
    - 只创建子目录 + 移动文件

    Args:
        plan: OrganizePlan。

    Returns:
        {moved: int, skipped: int, errors: list[str]}。
    """
    moved = 0
    skipped = 0
    errors: list[str] = []

    for pname, items in plan.points.items():
        for r in items:
            src = Path(r.file.full_path)
            dest = Path(r.target_path)

            # 安全检查
            if not src.exists():
                errors.append(f"源文件不存在: {src}")
                skipped += 1
                continue
            if dest.exists():
                logger.warning("跳过冲突文件: %s → %s", src, dest)
                skipped += 1
                continue

            try:
                # 创建目标目录
                dest.parent.mkdir(parents=True, exist_ok=True)
                # 移动文件
                shutil.move(str(src), str(dest))
                moved += 1
                logger.debug("移动: %s → %s", src.name, r.target_dir)
            except OSError as exc:
                errors.append(f"移动失败 {src.name}: {exc}")
                skipped += 1

    logger.info(
        "整理完成：移动 %d，跳过 %d，错误 %d",
        moved, skipped, len(errors),
    )
    return {"moved": moved, "skipped": skipped, "errors": errors}


# ====================================================================
# v1.6：空文件夹清理
# ====================================================================


def cleanup_empty_dirs(root_path: str) -> int:
    """递归删除项目目录下的空文件夹（自底向上）。

    只删除完全为空（无文件无子目录）的文件夹。
    项目根目录本身不会被删除。

    Args:
        root_path: 项目根目录路径。

    Returns:
        删除的空文件夹数量。
    """
    deleted = 0
    root = Path(root_path)
    try:
        # 自底向上遍历，先删最深的空目录
        for dirpath, dirnames, filenames in os.walk(str(root), topdown=False):
            # 跳过根目录
            if Path(dirpath).resolve() == root.resolve():
                continue
            # 检查是否为空
            try:
                contents = os.listdir(dirpath)
                if not contents:
                    os.rmdir(dirpath)
                    deleted += 1
                    logger.debug("删除空文件夹：%s", dirpath)
            except OSError:
                pass
    except Exception as exc:
        logger.warning("空文件夹清理出错：%s", exc)
    logger.info("空文件夹清理完成：删除 %d 个", deleted)
    return deleted
