"""全量文件索引扫描引擎 — v1.2.3 引入。

**设计原则（颠覆旧架构）**：
- 不假设任何目录结构
- 不按图纸/区县文件夹查找
- 递归扫描整个项目目录，构建扁平 FileIndex
- 全局匹配：point_name → matcher → FileIndex 全量搜索
- 文件归属规则：只要文件名匹配点位，不管路径在哪，都归属该点位

**数据结构**：
    FileEntry:  单个文件的扁平索引条目
    DirEntry:   目录条目（用于重新匹配时的候选列表）
    FileIndex:  全量索引 + 全局匹配引擎
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .matcher import match_folder, match_strings
from .normalizer import for_matching
from ..utils.logger import setup_logger

logger = setup_logger()

# 图纸文件扩展名
_DWG_EXT = ".dwg"


@dataclass
class FileEntry:
    """单个文件的扁平索引条目（v1.2.3）。"""
    file_name: str          # 原始文件名（含扩展名）
    full_path: str          # 绝对路径
    extension: str          # 小写扩展名（含 . 前缀）
    normalized_name: str    # for_matching() 后的标准化名称（用于匹配）
    parent_dir: str         # 所在目录名称（用于归属推断）
    parent_path: str        # 所在目录绝对路径


@dataclass
class DirEntry:
    """目录条目（v1.2.3）。"""
    dir_name: str           # 目录原始名称
    dir_path: str           # 绝对路径
    normalized_name: str    # for_matching() 后的标准化名称
    file_count: int         # 目录内文件总数（含子目录）
    dwg_count: int          # 目录内 .dwg 文件数
    subdir_names: list[str] = field(default_factory=list)


@dataclass
class FileIndex:
    """全量文件索引（v1.2.3 扫描引擎核心）。

    包含：
    - 所有文件的扁平列表（FileEntry）
    - 所有目录的扁平列表（DirEntry）
    - 按 normalized_name 索引的快速查找映射

    使用方式：
        index = FileIndex.build(root_path)
        results = index.global_match_point("点位名称")
        files = index.find_files_for_point("点位名称")
    """

    root_path: str = ""
    files: list[FileEntry] = field(default_factory=list)
    dirs: list[DirEntry] = field(default_factory=list)
    # 快速索引：normalized_name → FileEntry 列表
    _file_index: dict[str, list[FileEntry]] = field(default_factory=dict)
    # 目录索引：normalized_name → DirEntry 列表
    _dir_index: dict[str, list[DirEntry]] = field(default_factory=dict)

    @classmethod
    def build(cls, root_path: str | Path) -> FileIndex:
        """递归扫描整个项目目录，构建 FileIndex。

        Args:
            root_path: 项目根目录路径。

        Returns:
            构建好的 FileIndex。
        """
        root = Path(root_path).resolve()
        index = cls(root_path=str(root))

        if not root.exists():
            logger.warning("FileIndex: 目录不存在 %s", root)
            return index

        # Step 1: 递归扫描所有文件和目录
        _scan_recursive(root, index)

        # Step 2: 构建快速查找索引
        _build_indices(index)

        logger.info(
            "FileIndex 构建完成：%s → %d 文件，%d 目录",
            root, len(index.files), len(index.dirs),
        )
        return index

    def global_match_point(
        self,
        point_name: str,
        remove_parens: bool = False,
    ) -> list[FileEntry]:
        """全局匹配：按点位名称搜索 FileIndex 中的匹配文件。

        不管路径在哪里，只要文件名匹配点位 → 都返回。

        v1.4.2 修复：目录匹配时严格过滤——
        仅当目录名与点位名**精确相等**时才把该目录下文件归入，
        避免 fuzzy 匹配导致的跨点位文件污染。

        Args:
            point_name: 标准点位名称（或任何用于匹配的名称）。
            remove_parens: 是否去括号匹配。

        Returns:
            匹配的 FileEntry 列表（按 match_score 降序）。
        """
        match_name = for_matching(point_name, remove_parens=remove_parens)
        if not match_name:
            return []

        results: list[tuple[float, FileEntry]] = []

        # 在文件索引中搜索（按文件名匹配）
        for norm_name, entries in self._file_index.items():
            result = match_strings(match_name, norm_name)
            if result.score >= 70:
                for entry in entries:
                    results.append((result.score, entry))

        # 目录匹配：目录名精确相等时，把该目录下直接文件归入该点位。
        # 同时兼容目录名用下划线/空格分隔的常见写法（Site_A ↔ Site A），
        # 但仍不启用 fuzzy，以避免跨点位污染。
        compact_match_name = match_name.replace(" ", "").replace("_", "")
        for de in self.dirs:
            compact_dir_name = de.normalized_name.replace(" ", "").replace("_", "")
            if de.normalized_name != match_name and compact_dir_name != compact_match_name:
                continue
            for fe in self.files:
                if fe.parent_path == de.dir_path:
                    results.append((100.0, fe))

        # 去重 + 按得分降序排列
        seen: set[str] = set()
        unique: list[FileEntry] = []
        for score, entry in sorted(results, key=lambda x: x[0], reverse=True):
            if entry.full_path not in seen:
                seen.add(entry.full_path)
                unique.append(entry)

        return unique

    def find_files_for_point(
        self,
        point_name: str,
        remove_parens: bool = False,
    ) -> list[FileEntry]:
        """为点位查找所有关联文件（dir match 或 file match）。"""
        return self.global_match_point(point_name, remove_parens=remove_parens)

    def get_candidate_dirs(self) -> list[str]:
        """返回所有候选目录名列表（用于重新匹配对话框）。"""
        return sorted(set(d.dir_name for d in self.dirs))

    def get_dwg_files(self) -> list[FileEntry]:
        """返回所有 .dwg 文件。"""
        return [f for f in self.files if f.extension == _DWG_EXT]

    def compute_drawing_status(self, point_name: str) -> str:
        """为点位计算图纸状态（基于 FileIndex 全量搜索）。"""
        files = self.global_match_point(point_name)
        for f in files:
            if f.extension == _DWG_EXT:
                return "有"
        return "无"

    def compute_budget_status(self, point_name: str) -> str:
        """为点位计算预算状态（基于 FileIndex 全量搜索）。

        规则：匹配到的目录内有任何非 .dwg 文件 → "有"。
        """
        files = self.global_match_point(point_name)
        for f in files:
            if f.extension != _DWG_EXT:
                return "有"
        return "无"


# ====================================================================
# 内部实现
# ====================================================================


def _scan_recursive(path: Path, index: FileIndex) -> None:
    """递归扫描 path 下的所有文件和目录，填入 index。

    遍历所有子目录，不假设任何结构。
    """
    try:
        entries = sorted(path.iterdir())
    except PermissionError:
        return
    except OSError:
        return

    dir_file_count = 0
    dir_dwg_count = 0
    dir_subdir_names: list[str] = []

    for entry in entries:
        try:
            if entry.is_dir():
                dir_subdir_names.append(entry.name)
                # 目录条目
                de = DirEntry(
                    dir_name=entry.name,
                    dir_path=str(entry),
                    normalized_name=for_matching(entry.name),
                    file_count=0,
                    dwg_count=0,
                )
                index.dirs.append(de)
                # 递归扫描子目录
                _scan_recursive(entry, index)

            elif entry.is_file():
                fe = FileEntry(
                    file_name=entry.name,
                    full_path=str(entry),
                    extension=entry.suffix.lower(),
                    normalized_name=for_matching(entry.stem),
                    parent_dir=entry.parent.name,
                    parent_path=str(entry.parent),
                )
                index.files.append(fe)
                dir_file_count += 1
                if fe.extension == _DWG_EXT:
                    dir_dwg_count += 1
        except OSError:
            continue

    # 更新当前目录的统计
    if path != Path(index.root_path):
        parent_name = for_matching(path.name)
        for de in index.dirs:
            if de.dir_path == str(path):
                de.file_count = dir_file_count
                de.dwg_count = dir_dwg_count
                de.subdir_names = dir_subdir_names
                break


def _build_indices(index: FileIndex) -> None:
    """构建快速查找映射。

    _file_index: normalized_name → [FileEntry, ...]
    _dir_index:  normalized_name → [DirEntry, ...]
    """
    for fe in index.files:
        key = fe.normalized_name
        if key not in index._file_index:
            index._file_index[key] = []
        index._file_index[key].append(fe)

    for de in index.dirs:
        key = de.normalized_name
        if key not in index._dir_index:
            index._dir_index[key] = []
        index._dir_index[key].append(de)
