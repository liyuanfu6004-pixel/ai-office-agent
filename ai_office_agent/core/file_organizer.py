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

# 预算关键词
_BUDGET_KEYWORDS: tuple[str, ...] = (
    "预算", "概算", "造价", "报价", "清单",
    "cost", "estimate", "budget",
)


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
    """对单个文件进行分类（图纸 > 预算 > 其他）。

    分类规则（优先级）：
    1. 图纸：直接图纸类型(.dwg/.dxf/.bak) 或 PDF 匹配 CAD stem
    2. 预算：预算类型(.xls/.xlsx/.et/.csv) 且文件名包含关键词
    3. 其他：所有剩余文件

    Args:
        file: 文件条目。
        cad_index: CAD stem → FileEntry 映射。
        point_name: 点位名称（用于日志）。
        point_dir: 点位目录路径。

    Returns:
        ClassificationResult。
    """
    ext = file.extension.lower()
    stem = Path(file.file_name).stem.lower()

    # ── 图纸识别（最高优先级）──
    # v1.4.2 修复：直接图纸文件类型必须通过归属校验。
    # global_match_point 的 fuzzy 匹配会把其他点位的 .dwg/.dxf/.bak
    # 混入当前点位的文件列表。这些文件虽然扩展名是图纸类型，
    # 但文件名/路径与当前点位名不匹配，不能归入当前点位的图纸。
    # 1) 直接图纸类型
    if ext in _DRAWING_EXTS:
        if not _drawing_belongs_to_point(file, point_name):
            return ClassificationResult(
                file=file, category="其他",
                reason=f"非本点位图纸 ({ext})",
                target_dir=Path(point_dir) / point_name / "其他文件",
            )
        return ClassificationResult(
            file=file, category="图纸",
            reason=f"图纸文件 ({ext})",
            target_dir=Path(point_dir) / point_name / "图纸",
        )

    # 2) PDF ↔ CAD 同名规则
    if ext == ".pdf" and stem in cad_index:
        cad_files = [c.file_name for c in cad_index[stem]]
        return ClassificationResult(
            file=file, category="图纸",
            reason=f"PDF 匹配 CAD: {', '.join(cad_files)}",
            target_dir=Path(point_dir) / point_name / "图纸",
        )

    # ── 预算识别（次级）──
    if ext in _BUDGET_EXTS:
        # 关键词匹配
        match_name = for_matching(file.file_name)
        for kw in _BUDGET_KEYWORDS:
            if for_matching(kw) in match_name:
                return ClassificationResult(
                    file=file, category="预算",
                    reason=f"预算关键词「{kw}」",
                    target_dir=Path(point_dir) / point_name / "预算",
                )

    # ── 其他 ──
    return ClassificationResult(
        file=file, category="其他",
        reason="其他文件",
        target_dir=Path(point_dir) / point_name / "其他文件",
    )


# ====================================================================
# 整理计划生成器
# ====================================================================


def _drawing_belongs_to_point(file: FileEntry, point_name: str) -> bool:
    """判断图纸文件是否真正属于该点位（v1.4.2）。

    问题背景：file_index.global_match_point 使用 fuzzy 匹配（score>=70），
    相似点位名（如「盘龙-金辰街道」和「盘龙-联盟街道」）会互相包含对方的
    图纸文件，导致一个点位下出现其他点位的图纸。

    图纸归属强规则（满足任一即可）：
    1. 文件完整路径（含目录）中包含点位名
    2. 文件名 stem 以点位名开头（兼容「点位名202606121601.bak」这种带日期的命名）
    3. 文件所在目录名包含点位名
    """
    norm_point = for_matching(point_name)
    if not norm_point:
        return False

    norm_path = for_matching(file.full_path)
    norm_stem = for_matching(Path(file.file_name).stem)
    norm_parent = for_matching(file.parent_dir)

    if norm_point in norm_path:
        return True
    if norm_stem.startswith(norm_point):
        return True
    if norm_point in norm_parent:
        return True

    return False


def build_organize_plan(
    point_files: dict[str, list[FileEntry]],
    project_path: str,
) -> OrganizePlan:
    """为所有点位生成整理计划。

    Args:
        point_files: {point_name: [FileEntry, ...]}（来自 FileIndex 匹配结果）。
        project_path: 项目根目录路径。

    Returns:
        OrganizePlan 含所有分类和冲突。
    """
    plan = OrganizePlan(project_path=project_path)
    project_dir = Path(project_path)

    for pname, files in point_files.items():
        # v1.4.2 修复：图纸文件必须严格属于该点位。
        # global_match_point 的 fuzzy 匹配会导致相似点位名互相污染；
        # 在生成整理计划时，只把真正属于本点位的图纸文件纳入 CAD 索引。
        drawing_files = [
            f for f in files
            if f.extension in _DRAWING_EXTS and _drawing_belongs_to_point(f, pname)
        ]
        cad_index = build_cad_index(drawing_files)

        classifications: list[ClassificationResult] = []
        for f in files:
            result = classify_file(f, cad_index, pname, str(project_dir))
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
    """为所有点位生成整理计划。

    Args:
        point_files: {point_name: [FileEntry, ...]}（来自 FileIndex 匹配结果）。
        project_path: 项目根目录路径。

    Returns:
        OrganizePlan 含所有分类和冲突。
    """
    plan = OrganizePlan(project_path=project_path)
    project_dir = Path(project_path)

    for pname, files in point_files.items():
        # v1.4.2 修复：图纸文件必须严格属于该点位。
        # global_match_point 的 fuzzy 匹配会导致相似点位名互相污染；
        # 在生成整理计划时，只把真正属于本点位的图纸文件纳入 CAD 索引。
        drawing_files = [
            f for f in files
            if f.extension in _DRAWING_EXTS and _drawing_belongs_to_point(f, pname)
        ]
        cad_index = build_cad_index(drawing_files)

        classifications: list[ClassificationResult] = []
        for f in files:
            result = classify_file(f, cad_index, pname, str(project_dir))
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
