"""项目类别定义与 Excel 类型分流。

单一事实源：7 个业务类别 + 别名→类别映射。导入总体项目表时，若 Excel
"项目类型列"有值，经 `resolve_category` 归入对应业务类别写入
projects.project_type；无值或无法识别时 project_type 为 NULL，
该项目只显示在"全部项目"页，用户可后续手动指定类别。

类别与导航/页面键一一对应，严禁散落硬编码。
"""
from __future__ import annotations

# 7 个业务类别名（与左侧导航 7 个分类页一致，顺序固定）
CATEGORIES: list[str] = [
    "社区",
    "集客",
    "接入段",
    "设备",
    "管道",
    "城域网",
    "机房配套",
]

# 类别名 -> 内容区域页面键
CATEGORY_TO_PAGE_KEY: dict[str, str] = {
    "社区": "community",
    "集客": "enterprise",
    "接入段": "access",
    "设备": "equipment",
    "管道": "pipeline",
    "城域网": "metro",
    "机房配套": "facility",
}
# 页面键 -> 类别名
PAGE_KEY_TO_CATEGORY: dict[str, str] = {v: k for k, v in CATEGORY_TO_PAGE_KEY.items()}

# Excel 原始类型文本 -> 类别名 的别名映射。
# 顺序即匹配优先级；同一类别多别名任一命中即归入。
# 匹配规则：先精确相等，再子串包含（均去空白）。
_ALIASES: list[tuple[str, tuple[str, ...]]] = [
    ("社区", ("社区", "数字家庭")),
    ("集客", ("集客", "专线")),
    ("接入段", ("接入段",)),
    ("设备", ("设备",)),
    ("管道", ("管道",)),
    ("城域网", ("城域网", "优化", "输线路工程")),
    ("机房配套", ("机房配套", "配套")),
]


def normalize(raw: str | None) -> str:
    """去首尾空白。"""
    return (raw or "").strip()


def resolve_category(raw_type: str | None) -> str | None:
    """把 Excel 原始类型文本归入 7 类之一；无法识别返回 None。

    先精确匹配，再子串包含匹配（v1.1.1 升级：走 matcher.match_field）。
    避免短别名误吞长文本。
    """
    from .matcher import match_field

    s = normalize(raw_type)
    if not s:
        return None
    # 精确匹配优先
    for cat, aliases in _ALIASES:
        for a in aliases:
            if s == a:
                return cat
    # 子串包含匹配（v1.1.1：走 matcher）
    for cat, aliases in _ALIASES:
        for a in aliases:
            if a and match_field(s, a).is_match:
                return cat
    return None


def is_valid_category(category: str | None) -> bool:
    """判断是否为合法业务类别名。"""
    return category in CATEGORIES
