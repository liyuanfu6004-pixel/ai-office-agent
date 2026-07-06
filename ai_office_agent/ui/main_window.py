"""主窗口模块。

主窗口采用左右分栏：左侧树形导航，右侧内容卡片。
导航发出的页面切换请求转交给内容区域处理。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig
from .widgets.content_area import ContentArea
from .widgets.nav_tree import NavTree


class MainWindow(QMainWindow):
    """应用程序主窗口。"""

    def __init__(self, config: AppConfig) -> None:
        """初始化主窗口。

        Args:
            config: 应用配置对象，用于读取窗口尺寸等参数。
        """
        super().__init__()
        self._config = config

        self.setWindowTitle(config.ui.title)
        self.resize(config.ui.width, config.ui.height)

        self._setup_ui()
        self.statusBar().showMessage("已就绪")

    def _setup_ui(self) -> None:
        """构建主界面布局。"""
        # 可拖拽的左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # 左侧：树形导航
        self.nav_tree = NavTree(splitter)

        # 右侧：灰色留白容器 + 白色内容卡片（卡片带圆角与阴影）
        content_wrapper = QWidget(splitter)
        content_wrapper.setObjectName("ContentWrapper")
        wrapper_layout = QVBoxLayout(content_wrapper)
        wrapper_layout.setContentsMargins(16, 16, 16, 16)
        # 将配置传入内容区域，供项目管理页面访问数据库
        self.content_area = ContentArea(config=self._config, parent=content_wrapper)
        wrapper_layout.addWidget(self.content_area)

        # 初始宽度与拉伸策略：导航不变宽，内容自适应
        content_width = max(self._config.ui.width - self._config.ui.nav_width, 400)
        splitter.setSizes([self._config.ui.nav_width, content_width])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        # 连接：导航切换 -> 内容区域
        self.nav_tree.page_requested.connect(self.content_area.switch_to)
