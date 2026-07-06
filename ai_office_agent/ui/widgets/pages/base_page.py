"""页面基类模块。

所有功能页面继承自 BasePage，统一页头布局（大标题 + 副标题），
并提供 content_layout 供子类填充具体内容；占位页面留空即可。
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class BasePage(QWidget):
    """页面基类。

    提供统一的页头：左上角大标题，下方灰色副标题；
    页头之下暴露 content_layout，供子类放置工具栏、表格等内容。
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """初始化页面。

        Args:
            title: 页面标题，显示于左上角。
            subtitle: 副标题，用于提示状态；为空则不显示。
            parent: 父控件。
        """
        super().__init__(parent)

        # 主纵向布局：页头 + 内容区
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(6)

        # 大标题
        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("PageTitle")
        layout.addWidget(self.title_label)

        # 副标题（可空）
        if subtitle:
            self.subtitle_label = QLabel(subtitle, self)
            self.subtitle_label.setObjectName("PageSubtitle")
            layout.addWidget(self.subtitle_label)

        # 内容区域布局：子类通过 self.content_layout 添加控件
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 12, 0, 0)
        self.content_layout.setSpacing(12)
        layout.addLayout(self.content_layout)
