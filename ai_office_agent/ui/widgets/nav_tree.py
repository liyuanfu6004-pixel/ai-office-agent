"""树形导航控件。

严格按需求结构构建左侧导航：

    📁 项目管理
        ├── 全部项目   ← 唯一总入口（导入/新增/总览）
        ├── 社区
        ├── 集客
        ├── 接入段
        ├── 设备
        ├── 管道
        ├── 城域网
        └── 机房配套
    🔍 扫描结果中心   ← v1.2 引入（扫描匹配分析）
    🤖 AI助手
    ⚙ 设置

v0.6.0：「全部项目」为所有项目的唯一总入口，所有导入数据先进入全部项目；
7 个分类页只是全部项目的分类视图（只读）。点击叶子节点发出 page_requested
信号；分组节点不切换（切换由"全部项目"叶子承担）。默认选中"全部项目"。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QWidget,
)


def _bold_font() -> QFont:
    """返回加粗字体，用于分组/顶级节点视觉区分。"""
    font = QFont()
    font.setBold(True)
    return font


class NavTree(QTreeWidget):
    """左侧树形导航。"""

    # 点击叶子节点时发出，参数为对应页面标识
    page_requested = Signal(str)

    # 启动时默认选中的页面标识（全部项目）
    DEFAULT_PAGE = "all_projects"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavTree")
        self.setHeaderHidden(True)
        self.setMinimumWidth(200)
        self.setIndentation(18)

        self._build_items()
        self.expandAll()

        self.itemClicked.connect(self._on_item_clicked)
        self.select_default()

    def _build_items(self) -> None:
        """构建导航树结构。"""
        # 分组：项目管理（仅作容器，不携带页面标识）
        project_group = QTreeWidgetItem(self, ["📁  项目管理"])
        project_group.setFont(0, _bold_font())
        project_group.setData(0, Qt.ItemDataRole.UserRole, None)  # 不切换

        # 全部项目：唯一总入口
        all_item = QTreeWidgetItem(project_group, ["全部项目"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, "all_projects")

        # 7 个分类展示页：名称 -> 页面标识
        project_children = [
            ("社区", "community"),
            ("集客", "enterprise"),
            ("接入段", "access"),
            ("设备", "equipment"),
            ("管道", "pipeline"),
            ("城域网", "metro"),
            ("机房配套", "facility"),
        ]
        for name, key in project_children:
            child = QTreeWidgetItem(project_group, [name])
            child.setData(0, Qt.ItemDataRole.UserRole, key)

        # 扫描结果中心
        scan_item = QTreeWidgetItem(self, ["🔍  扫描结果中心"])
        scan_item.setFont(0, _bold_font())
        scan_item.setData(0, Qt.ItemDataRole.UserRole, "scan_center")

        # 顶级占位项：AI助手
        ai_item = QTreeWidgetItem(self, ["🤖  AI助手"])
        ai_item.setFont(0, _bold_font())
        ai_item.setData(0, Qt.ItemDataRole.UserRole, "ai_assistant")

        # 顶级占位项：设置
        settings_item = QTreeWidgetItem(self, ["⚙  设置"])
        settings_item.setFont(0, _bold_font())
        settings_item.setData(0, Qt.ItemDataRole.UserRole, "settings")

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """点击节点：若附带页面标识则发出切换请求，否则忽略。"""
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if key:
            self.page_requested.emit(key)

    def select_default(self) -> None:
        """默认选中全部项目，仅高亮不触发信号。"""
        item = self._find_item_by_key(self.DEFAULT_PAGE)
        if item is not None:
            self.setCurrentItem(item)

    def _find_item_by_key(self, key: str) -> QTreeWidgetItem | None:
        """遍历查找携带指定页面标识的节点。"""
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.ItemDataRole.UserRole) == key:
                return item
            iterator += 1
        return None
