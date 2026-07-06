"""统一字符串标准化模块 — v1.1.1 引入，v1.2.3 扩展双层标准化。

所有字符串比较前必须先经本模块标准化。标准化仅用于比较，
**禁止修改原始数据**。数据库仍保存原始名称。

v1.2.3 双层标准化：
    standard_name   → 原始名称，不变
    match_name      → for_matching() 输出，用于全系统匹配
    filesystem_name → for_filesystem_path() 输出，用于未来文件夹生成

标准化规则（按顺序执行）：
1.  Unicode 统一（NFKC）
2.  去首尾空白（含中文全角空格）
3.  合并连续空白
4.  中文全角空格 → 半角空格
5.  中文括号 ↔ 英文括号统一
6.  中文标点 → 英文标点统一（用于比较）
7.  大小写统一（小写）
8.  删除匹配时不允许的字符：/ \\ : * ? " < > |
9.  可选去括号内容（match_name）
"""
from __future__ import annotations

import re
import unicodedata

# ====================================================================
# 特殊字符清理
# ====================================================================

# 文件系统不允许的字符
_FILESYSTEM_FORBIDDEN = re.compile(r'[/\\:*?"<>|]')

# 空白合并
_MULTI_SPACE = re.compile(r"\s+")

# 括号内容匹配（用于可选去除）
_PAREN_CONTENT = re.compile(r"\([^)]*\)|（[^）]*）")


def for_comparison(raw: str | None) -> str:
    """将任意字符串标准化为可用于比较的形式（保留向后兼容）。

    此函数是"比较标准化"的主入口。所有模糊匹配在比较前都应调用此函数。
    v1.2.3：推荐使用 for_matching() 替代。

    Args:
        raw: 原始字符串（可含中文、特殊字符、全角符号等）。

    Returns:
        标准化后的字符串（小写、NFKC、标点统一）。

    Examples:
        >>> for_comparison("A/B社区")
        "a/b社区"
        >>> for_comparison("人民路机房（最终）")
        "人民路机房 (最终)"
    """
    if raw is None:
        return ""

    if not isinstance(raw, str):
        raise TypeError(f"normalizer 仅接受 str 或 None，收到 {type(raw).__name__}")

    s = raw

    # 1. Unicode 统一（NFKC）
    s = unicodedata.normalize("NFKC", s)

    # 2. 中文全角空格 → 半角空格
    s = s.replace("　", " ")

    # 3. 中文括号 → 英文括号
    s = _normalize_brackets(s)

    # 4. 常用中文标点 → 英文标点（仅用于比较）
    s = _normalize_punctuation(s)

    # 5. 去首尾空白
    s = s.strip()

    # 6. 合并连续空白
    s = _MULTI_SPACE.sub(" ", s)

    # 7. 统一小写
    s = s.lower()

    return s


def for_filesystem(raw: str | None) -> str:
    """用于文件名/文件夹名匹配的标准化（保留向后兼容）。

    v1.2.3：推荐使用 for_matching() 替代。

    在 for_comparison 基础上额外删除文件系统不允许的字符。
    """
    s = for_comparison(raw)
    s = _FILESYSTEM_FORBIDDEN.sub("", s)
    s = _MULTI_SPACE.sub(" ", s).strip()
    return s


def for_matching(raw: str | None, remove_parens: bool = False) -> str:
    """v1.2.3 主匹配标准化 —— 生成 match_name。

    规则：
    1. NFKC 统一
    2. 全角空格 → 半角
    3. 中文括号 → 英文括号
    4. 中文标点 → 英文
    5. **删除文件系统非法字符 / \\ : * ? " < > |**
    6. 去首尾空白 + 合并空白
    7. 英文 lowercase
    8. 可选：去除括号内容

    全系统 matcher 统一使用此函数输出作为匹配基准。
    禁止任何模块使用原始字符串直接匹配。

    Args:
        raw: 原始名称（standard_point_name / 文件夹名 / 文件名）。
        remove_parens: 是否去除括号内容（用于激进匹配）。

    Returns:
        match_name —— 供 matcher 使用的标准化字符串。
    """
    s = for_comparison(raw)
    # 删除文件系统非法字符
    s = _FILESYSTEM_FORBIDDEN.sub("", s)
    s = _MULTI_SPACE.sub(" ", s).strip()
    # 可选去括号
    if remove_parens:
        s = _PAREN_CONTENT.sub("", s)
        s = _MULTI_SPACE.sub(" ", s).strip()
    return s


def for_filesystem_path(raw: str | None) -> str:
    """v1.2.3 新标准化 —— 生成 filesystem_name（用于未来文件夹生成）。

    与 for_matching 的区别：保留更多可读性。

    规则：
    1. / → -  （路径分隔符替换为连字符）
    2. 删除其他非法字符：\\ : * ? " < > |
    3. 保留中文
    4. 避免非法字符
    5. 保持可读性

    Args:
        raw: 原始名称。

    Returns:
        filesystem_name —— 可用于文件夹命名的安全名称。
    """
    if raw is None:
        return ""
    s = raw
    # / → -
    s = s.replace("/", "-")
    # 删除其他非法字符
    s = re.sub(r'[\\:*?"<>|]', "", s)
    # 去首尾空白和点号（Windows 文件夹限制）
    s = s.strip().rstrip(".")
    # 合并空格
    s = _MULTI_SPACE.sub(" ", s)
    return s if s else "unnamed"


def for_display(raw: str | None) -> str:
    """用于显示比较的标准化（保留可读性，仅做轻量清理）。"""
    if raw is None:
        return ""
    s = raw
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("　", " ")
    s = s.strip()
    s = _MULTI_SPACE.sub(" ", s)
    return s


# ====================================================================
# 内部辅助
# ====================================================================

# 中文括号 ↔ 英文括号映射
_BRACKET_MAP: dict[str, str] = {
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "｛": "{",
    "｝": "}",
    "《": "<",
    "》": ">",
}

# 中文标点 → 英文标点（仅用于比较，不影响原始数据）
_PUNCTUATION_MAP: dict[str, str] = {
    "，": ",",
    "。": ".",
    "！": "!",
    "？": "?",
    "：": ":",
    "；": ";",
    "＂": '"',
    "＇": "'",
    "～": "~",
    "＠": "@",
    "＃": "#",
    "＄": "$",
    "％": "%",
    "＾": "^",
    "＆": "&",
    "＊": "*",
}


def _normalize_brackets(s: str) -> str:
    """中文括号 → 英文括号。"""
    for cn, en in _BRACKET_MAP.items():
        s = s.replace(cn, en)
    return s


def _normalize_punctuation(s: str) -> str:
    """中文标点 → 英文标点。"""
    for cn, en in _PUNCTUATION_MAP.items():
        s = s.replace(cn, en)
    return s
