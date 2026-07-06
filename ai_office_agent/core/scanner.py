"""文件系统沙盒扫描器（v1.2.3 重构：FileIndex + RegionProfile + match_name）。

**安全约束（硬编码，不可绕过）**：
- 仅扫描 TEST_ROOT_PATH = D:\\AI-Office-Agent-Test\\
- 禁止访问任何其他路径
- 只读操作：不创建、不修改、不删除任何文件或文件夹

**v1.2.3 重构**：
- 底层引擎替换为 FileIndex（全量递归扫描 + 扁平索引）
- 全局匹配：point_name → matcher → FileIndex 全量搜索
- 区县过滤：RegionProfile 归一化 + active_counties 白名单
- 所有匹配统一使用 for_matching() 输出 match_name
- 旧 API（scan_project_root / match_project_sites 等）保留兼容

v1.1.1 升级：
- 删除自定义 normalize_for_match、_match_keyword 函数
- 统一走 core.normalizer（for_filesystem）+ core.matcher（match_folder/match_filename）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .file_index import FileIndex, FileEntry, DirEntry
from .matcher import match_folder, match_strings
from .normalizer import for_comparison, for_filesystem, for_matching
from .region_profile import get_profile
from ..utils.logger import setup_logger

logger = setup_logger()

# ====================================================================
# 安全边界 —— 硬编码沙盒根目录
# ====================================================================

TEST_ROOT_PATH = Path(r"D:\AI-Office-Agent-Test")

_DWG_EXT = ".dwg"

# ====================================================================
# 图纸根目录关键词（保留向后兼容）
# ====================================================================

_DRAWING_ROOT_KEYWORDS = (
    "图纸", "设计图", "CAD", "cad",
    "施工图", "Drawing", "drawing",
    "图", "dwg", "DWG",
)

# 项目整体资料关键词识别
_PROJECT_DOC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "规模表": ("规模表", "规模", "统计表"),
    "材料表": ("材料表", "材料", "物料"),
    "照片": ("照片", "photo", "图片", "现场照片"),
    "勘察报告": ("勘察报告", "勘察", "勘测", "survey"),
    "流程文件": ("流程", "审批", "process", "workflow"),
    "批复": ("批复", "批准", "核准", "approval"),
    "其它资料": ("其它", "其他", "其它资料", "其他资料", "other", "其它文件", "其他文件"),
}

# ====================================================================
# 数据结构（保留向后兼容）
# ====================================================================


@dataclass
class FileNode:
    """叶子节点：单个文件。"""
    name: str
    path: str
    extension: str


@dataclass
class FolderNode:
    """文件夹节点：可含子文件夹与文件。"""
    name: str
    path: str
    subdirs: list[FolderNode] = field(default_factory=list)
    files: list[FileNode] = field(default_factory=list)


@dataclass
class ProjectDocGroup:
    """项目整体资料分类。"""
    category: str
    folder: FolderNode | None = None
    matched_by: str = "keyword"


@dataclass
class DrawingRoot:
    """图纸根目录。"""
    folder: FolderNode
    name: str
    candidate_count: int = 1


@dataclass
class SiteNode:
    """点位节点。"""
    name: str
    path: str
    folder: FolderNode
    drawing_dir: FolderNode | None = None
    budget_dir: FolderNode | None = None


@dataclass
class ProjectNode:
    """项目根节点。"""
    name: str
    path: str
    docs: list[ProjectDocGroup] = field(default_factory=list)
    root_files: list[FileNode] = field(default_factory=list)
    drawing_root: DrawingRoot | None = None
    drawing_candidates: list[DrawingRoot] = field(default_factory=list)
    sites: list[SiteNode] = field(default_factory=list)
    other_folders: list[FolderNode] = field(default_factory=list)
    # v1.2.3：补充 FileIndex 引用
    file_index: FileIndex | None = None


@dataclass
class MatchResult:
    """点位文件夹与标准点位字典的匹配结果。"""
    folder_name: str
    folder_path: str
    point_id: int | None = None
    point_name: str | None = None
    match_score: float = 0.0
    drawing_status: str = "无"
    budget_status: str = "无"

    @property
    def is_matched(self) -> bool:
        return self.point_id is not None and self.match_score > 0.0


@dataclass
class ProjectScanResult:
    """单个项目的完整扫描结果。"""
    project_name: str
    project_path: str
    docs: list[ProjectDocGroup]
    drawing_root: DrawingRoot | None
    sites: list[SiteNode]
    matches: list[MatchResult]
    unmatched_folders: list[str]


# ====================================================================
# 路径安全校验
# ====================================================================


def _validate_path(path: Path) -> None:
    """确保路径在 TEST_ROOT_PATH 内。"""
    try:
        path.resolve().relative_to(TEST_ROOT_PATH.resolve())
    except ValueError:
        raise ValueError(
            f"安全违规：路径不在沙盒目录内: {path}\n"
            f"  沙盒根目录: {TEST_ROOT_PATH}"
        )


def _safe_resolve(path: str | Path) -> Path:
    p = Path(path).resolve()
    _validate_path(p)
    return p


# ====================================================================
# 扫描引擎
# ====================================================================


def _scan_dir(path: Path) -> FolderNode:
    """递归扫描文件夹。"""
    _validate_path(path)
    node = FolderNode(name=path.name, path=str(path))
    if not path.is_dir():
        return node
    for entry in sorted(path.iterdir()):
        if entry.is_dir():
            node.subdirs.append(_scan_dir(entry))
        else:
            node.files.append(FileNode(
                name=entry.name, path=str(entry), extension=entry.suffix.lower(),
            ))
    return node


def _match_keyword(name: str, keywords: tuple[str, ...]) -> bool:
    """判断文件夹名是否命中任一关键词。

    v1.1.1 升级：走 matcher.match_folder（RapidFuzz 引擎）。
    """
    for kw in keywords:
        result = match_folder(name, kw)
        if result.is_match:
            return True
    return False


def scan_project_root(root_path: str | None = None) -> list[ProjectNode]:
    """扫描沙盒项目根目录。

    三步走：
    1. 识别项目整体资料（关键词匹配）
    2. 识别图纸根目录（关键词 + 候选）
    3. 在图纸根目录下寻找点位

    Args:
        root_path: 默认 TEST_ROOT_PATH。
    """
    root = _safe_resolve(root_path or TEST_ROOT_PATH)
    logger.info("沙盒扫描开始：%s", root)

    projects: list[ProjectNode] = []
    if not root.exists():
        logger.warning("沙盒目录不存在：%s", root)
        return projects

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        projects.append(_scan_project(entry))

    logger.info("沙盒扫描完成：%d 个项目", len(projects))
    return projects


def _scan_project(proj_path: Path) -> ProjectNode:
    """扫描单个项目目录——三步架构。

    第一步：遍历顶层，分类为「资料/图纸候选/其它」
    第二步：确定图纸根目录
    第三步：在图纸根目录下提取点位
    """
    _validate_path(proj_path)
    proj = ProjectNode(name=proj_path.name, path=str(proj_path))

    # 完整扫描顶层文件夹
    top_dirs: list[FolderNode] = []
    for entry in sorted(proj_path.iterdir()):
        if entry.is_dir():
            top_dirs.append(_scan_dir(entry))
        else:
            proj.root_files.append(FileNode(
                name=entry.name, path=str(entry), extension=entry.suffix.lower(),
            ))

    # ── 第一步：识别项目整体资料 ──
    for d in list(top_dirs):
        matched = False
        for cat, keywords in _PROJECT_DOC_KEYWORDS.items():
            if _match_keyword(d.name, keywords):
                proj.docs.append(ProjectDocGroup(category=cat, folder=d))
                matched = True
                break
        if matched:
            top_dirs.remove(d)

    # ── 第二步：识别图纸根目录候选 ──
    drawing_candidates: list[FolderNode] = []
    for d in list(top_dirs):
        if _match_keyword(d.name, _DRAWING_ROOT_KEYWORDS):
            drawing_candidates.append(d)
            top_dirs.remove(d)

    # 如果关键词未命中，检查目录内是否大量含 .dwg（兜底识别）
    for d in list(top_dirs):
        if _folder_contains_dwg_deep(d):
            drawing_candidates.append(d)
            top_dirs.remove(d)

    # 记录候选
    for dc in drawing_candidates:
        proj.drawing_candidates.append(DrawingRoot(
            folder=dc,
            name=dc.name,
            candidate_count=len(drawing_candidates),
        ))

    # 确定图纸根目录（未配记忆时取第一个候选，UI 层后续可覆盖）
    if proj.drawing_candidates:
        proj.drawing_root = proj.drawing_candidates[0]

    # 剩余顶层文件夹
    proj.other_folders = top_dirs

    # ── 第三步：在图纸根目录下提取点位 ──
    if proj.drawing_root is not None:
        proj.sites = _extract_sites(proj.drawing_root.folder)

    logger.info(
        "项目 %s：资料=%d 图纸候选=%d 点位=%d 其它=%d",
        proj.name, len(proj.docs),
        len(proj.drawing_candidates), len(proj.sites),
        len(proj.other_folders),
    )
    return proj


def _folder_contains_dwg_deep(folder: FolderNode) -> bool:
    """判断文件夹树内是否包含 .dwg 文件（兜底识别图纸目录）。"""
    for f in folder.files:
        if f.extension == _DWG_EXT:
            return True
    for sub in folder.subdirs:
        if _folder_contains_dwg_deep(sub):
            return True
    return False


def _extract_sites(drawing_root: FolderNode) -> list[SiteNode]:
    """在图纸根目录下提取点位文件夹列表。

    图纸根目录的直接子目录即为点位文件夹。
    每个点位下识别：图纸 / 预算 / 其它。
    """
    sites: list[SiteNode] = []
    for sub in drawing_root.subdirs:
        # 跳过明显非点位的文件夹（如根级"_备份"等）
        name_lower = sub.name.lower()
        if name_lower.startswith("_") or name_lower in ("backup", "备份", "temp", "tmp"):
            continue

        site = _build_site_node(sub)
        sites.append(site)
    return sites


def _build_site_node(folder: FolderNode) -> SiteNode:
    """从点位文件夹构建 SiteNode，识别图纸/预算子目录。

    v1.1.1 升级：走 matcher.match_folder。
    """
    site = SiteNode(name=folder.name, path=folder.path, folder=folder)

    drawing_keywords = ("图纸", "drawing", "dwg", "cad", "图")
    budget_keywords = ("预算", "budget", "造价", "cost")

    for sub in folder.subdirs:
        if _match_keyword(sub.name, drawing_keywords):
            site.drawing_dir = sub
        elif _match_keyword(sub.name, budget_keywords):
            site.budget_dir = sub

    return site


# ====================================================================
# 图纸/预算文件判定
# ====================================================================


def has_dwg_files(folder: FolderNode) -> bool:
    """文件夹（含子目录）内是否有 *.dwg。"""
    for f in folder.files:
        if f.extension == _DWG_EXT:
            return True
    for sub in folder.subdirs:
        if has_dwg_files(sub):
            return True
    return False


def has_any_files(folder: FolderNode) -> bool:
    """文件夹是否有文件。"""
    if folder.files:
        return True
    for sub in folder.subdirs:
        if sub.files:
            return True
    return False


# ====================================================================
# 状态计算
# ====================================================================


def compute_drawing_status(site: SiteNode) -> str:
    """图纸状态：点位下图纸子文件夹存在 *.dwg →「有」；否则 →「无」。"""
    if site.drawing_dir is not None and has_dwg_files(site.drawing_dir):
        return "有"
    # 兜底：点位内任意位置有 .dwg 也算有
    if has_dwg_files(site.folder):
        return "有"
    return "无"


def compute_budget_status(site: SiteNode) -> str:
    """预算状态：点位下预算子文件夹存在且有文件 →「有」；否则 →「无」。"""
    if site.budget_dir is not None and has_any_files(site.budget_dir):
        return "有"
    return "无"


def compute_all_statuses_for_sites(sites: list[SiteNode]) -> list[dict]:
    """批量计算所有点位的图纸/预算状态。"""
    results = []
    for s in sites:
        results.append({
            "name": s.name,
            "drawing_status": compute_drawing_status(s),
            "budget_status": compute_budget_status(s),
        })
    return results


# ====================================================================
# 匹配系统
# ====================================================================
def match_single_folder(
    folder_name: str,
    folder_path: str,
    point_list: list[dict],
) -> MatchResult:
    """将单个文件夹名与点位字典匹配（v1.2.3：使用 for_matching）。

    v1.1.1 升级：走 matcher.match_folder（RapidFuzz 引擎）。
    v1.2.3 升级：都使用 for_matching 生成 match_name 后匹配。
    """
    if not folder_name:
        return MatchResult(folder_name=folder_name, folder_path=folder_path)

    best_score = 0.0
    best_point: dict | None = None

    for p in point_list:
        result = match_folder(
            for_matching(folder_name),
            for_matching(p["standard_point_name"]),
        )
        if result.score > best_score:
            best_score = result.score
            best_point = p
        if result.kind.name == "EXACT":
            break

    if best_point is not None and best_score >= 70.0:
        return MatchResult(
            folder_name=folder_name, folder_path=folder_path,
            point_id=int(best_point["id"]),
            point_name=best_point["standard_point_name"],
            match_score=round(best_score / 100.0, 2),
        )
    return MatchResult(folder_name=folder_name, folder_path=folder_path)


def match_project_sites(
    project: ProjectNode,
    point_list: list[dict],
) -> tuple[list[MatchResult], list[str]]:
    """为项目的所有点位建立匹配（并填入真实状态）。"""
    matches: list[MatchResult] = []
    unmatched: list[str] = []

    for site in project.sites:
        result = match_single_folder(site.name, site.path, point_list)
        # 填入真实状态
        result.drawing_status = compute_drawing_status(site)
        result.budget_status = compute_budget_status(site)
        if result.is_matched:
            matches.append(result)
        else:
            unmatched.append(site.name)
            matches.append(result)

    logger.info(
        "项目 %s 匹配：%d 个点位，%d 成功，%d 未匹配",
        project.name, len(project.sites),
        sum(1 for m in matches if m.is_matched), len(unmatched),
    )
    return matches, unmatched


# ====================================================================
# 便捷入口
# ====================================================================


def run_full_scan(
    point_dict_by_project: dict[int, list[dict]] | None = None,
    root_path: str | None = None,
) -> list[ProjectScanResult]:
    """完整沙盒扫描链路。"""
    projects = scan_project_root(root_path)
    results: list[ProjectScanResult] = []

    for proj in projects:
        points: list[dict] = []
        if point_dict_by_project is not None:
            for pid, plist in point_dict_by_project.items():
                points.extend(plist)

        matches, unmatched = match_project_sites(proj, points)

        results.append(ProjectScanResult(
            project_name=proj.name,
            project_path=proj.path,
            docs=proj.docs,
            drawing_root=proj.drawing_root,
            sites=proj.sites,
            matches=matches,
            unmatched_folders=unmatched,
        ))

    logger.info("完整扫描完成：%d 个项目", len(results))
    return results


# ====================================================================
# v1.2.3 新扫描引擎（FileIndex + RegionProfile + match_name）
# ====================================================================


def scan_with_file_index(root_path: str | None = None) -> list[ProjectNode]:
    """v1.2.3 新扫描：FileIndex + 区县过滤 + 全局匹配。

    新流程：
    1. 递归扫描所有文件 → FileIndex
    2. 区县过滤（Region Profile.active_counties）
    3. 构建 ProjectNode（含 FileIndex 引用）
    4. 不依赖目录结构假设
    """
    root = _safe_resolve(root_path or TEST_ROOT_PATH)
    logger.info("v1.2.3 FileIndex 扫描开始：%s", root)

    projects: list[ProjectNode] = []
    if not root.exists():
        logger.warning("沙盒目录不存在：%s", root)
        return projects

    profile = get_profile()

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue

        # 构建 FileIndex
        file_index = FileIndex.build(entry)

        # 区县过滤：检查区县在白名单内
        proj_name = entry.name
        county_name = _extract_county_from_name(proj_name, profile)
        if county_name is not None and not profile.is_active(county_name):
            logger.info("跳过非负责区县项目：%s（区县=%s）", proj_name, county_name)
            continue

        proj = ProjectNode(
            name=proj_name,
            path=str(entry),
            file_index=file_index,
        )

        # 提取点位列表（从 FileIndex 目录中识别）
        proj.sites = _extract_sites_from_index(file_index, entry)
        # 简易资料识别
        proj.docs = _classify_docs_from_index(file_index)

        projects.append(proj)

        logger.info(
            "v1.2.3 项目 %s：索引 %d 文件 + %d 目录，点位=%d",
            proj.name, len(file_index.files), len(file_index.dirs), len(proj.sites),
        )

    logger.info("v1.2.3 FileIndex 扫描完成：%d 个项目", len(projects))
    return projects


def match_points_from_index(
    project: ProjectNode,
    point_list: list[dict],
) -> tuple[list[MatchResult], list[str], list[str]]:
    """v1.5 唯一归属匹配：基于 ownership 模型。

    核心升级（v1.5）：
    - 内部调用 ownership.assign_ownership 做两阶段唯一归属决策
    - 禁止调用 file_index.global_match_point（反向匹配污染源）
    - 禁止调用 matcher.match_file_to_points（旧 fuzzy 链路）
    - 图纸类文件强制 stem 精确匹配
    - 阈值 0.75，冲突 margin 0.05

    保留原返回签名 (matches, unmatched_names, conflict_file_paths) 以兼容。

    Args:
        project: 含 FileIndex 的 ProjectNode。
        point_list: 点位字典列表 [{id, standard_point_name, county, ...}]。

    Returns:
        (matches, unmatched_names, conflict_file_paths)。
    """
    if project.file_index is None:
        logger.warning("项目 %s 无 FileIndex，回退旧匹配", project.name)
        return match_project_sites(project, point_list)

    from .ownership import assign_ownership
    from .normalizer import for_matching as _fm

    profile = get_profile()

    # 区县过滤
    active_points: list[dict] = []
    for p in point_list:
        county = p.get("county", "")
        if county:
            normalized = profile.normalize(county)
            if normalized and not profile.is_active(normalized):
                continue
        active_points.append(p)

    if not active_points:
        return [], [], []

    # ── v1.5：两阶段唯一归属模型 ──
    ownership = assign_ownership(project.file_index, active_points)

    # 构建 MatchResult
    matches: list[MatchResult] = []
    unmatched: list[str] = []

    for p in active_points:
        pname = p.get("standard_point_name", "")
        pid = int(p["id"])
        files = ownership.files_for_point(pid)
        cad_status, budget_status = ownership.status_for_point(pid)

        if files:
            # 取第一个归属文件的父目录作为 folder_name
            folder_name = files[0].parent_dir
            folder_path = files[0].parent_path
            matches.append(MatchResult(
                folder_name=folder_name,
                folder_path=folder_path,
                point_id=pid,
                point_name=pname,
                match_score=1.0,
                drawing_status=cad_status,
                budget_status=budget_status,
            ))
        else:
            unmatched.append(pname)
            matches.append(MatchResult(
                folder_name=pname, folder_path="",
                point_id=pid, point_name=pname,
                drawing_status="无", budget_status="无",
            ))

    logger.info(
        "v1.5 唯一归属匹配：项目=%s，%d 文件已归属，%d 冲突，%d 点位置",
        project.name, ownership.assigned_count,
        len(ownership.conflict_files), len(active_points),
    )
    return matches, unmatched, ownership.conflict_files


def _extract_county_from_name(project_name: str, profile) -> str | None:
    """从项目名称中提取区县名。"""
    for county in profile.active_counties:
        if county in project_name:
            return county
    return None


def _extract_sites_from_index(file_index: FileIndex, root_path: Path) -> list[SiteNode]:
    """从 FileIndex 提取点位列表。

    策略：所有第一层子目录 → 作为候选点位。
    """
    sites: list[SiteNode] = []
    seen: set[str] = set()

    for de in file_index.dirs:
        # 取直接子目录作为点位
        try:
            rel = Path(de.dir_path).relative_to(root_path)
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) >= 2:
            site_name = parts[1]  # project/site_name/...
        else:
            site_name = parts[0]

        if site_name in seen:
            continue
        seen.add(site_name)

        # 跳过明显非点位
        name_lower = site_name.lower()
        if name_lower.startswith("_") or name_lower in ("backup", "备份", "temp", "tmp"):
            continue

        folder = FolderNode(name=site_name, path=de.dir_path)
        site = SiteNode(name=site_name, path=de.dir_path, folder=folder)
        sites.append(site)

    return sites


def _classify_docs_from_index(file_index: FileIndex) -> list[ProjectDocGroup]:
    """从 FileIndex 分类项目整体资料。"""
    docs: list[ProjectDocGroup] = []
    for cat, keywords in _PROJECT_DOC_KEYWORDS.items():
        for de in file_index.dirs:
            if _match_keyword(de.dir_name, keywords):
                folder = FolderNode(name=de.dir_name, path=de.dir_path)
                docs.append(ProjectDocGroup(category=cat, folder=folder))
                break
    return docs
