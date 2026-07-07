"""内容区域控件。

右侧内容区域，为白色圆角卡片风格。内部使用 QStackedWidget 承载所有
功能页面，根据导航发出的页面标识切换显示对应页面。

v0.6.0 架构：
- 「全部项目」页（all_projects）为唯一总入口，承载导入/新增；
- 7 个分类页（community...）为只读分类视图。
- 项目详情页（project_detail）为「全部项目」双击项目后的次级只读页。
- 扫描结果中心（scan_center）为独立导航项，承载扫描匹配分析。
- 总页面数 = 13（全部项目 + 7 分类 + 项目详情 + 扫描中心 + AI + 设置）。
"""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...config import AppConfig
from .pages import (
    AIAssistantPage,
    AccessPage,
    CommunityPage,
    EnterprisePage,
    EquipmentPage,
    FacilityPage,
    MetroPage,
    PipelinePage,
    ProjectAllEntryPage,
    ProjectDetailPage,
    ScanCenterPage,
    SettingsPage,
)


class ContentArea(QFrame):
    """右侧内容卡片区域。"""

    # 启动时默认显示的页面标识（全部项目）
    DEFAULT_PAGE = "all_projects"

    def __init__(
        self,
        config: AppConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")
        self._config = config or AppConfig()

        self._page_index: dict[str, int] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.page_stack = QStackedWidget(self)
        layout.addWidget(self.page_stack)

        self._register_pages()
        self.switch_to(self.DEFAULT_PAGE)
        self._apply_shadow()

    def _register_pages(self) -> None:
        """注册全部功能页面。"""
        cfg = self._config
        # 全部项目页：唯一总入口
        all_page = ProjectAllEntryPage(config=cfg)
        self.add_page("all_projects", all_page)

        # 7 个分类展示页（只读）
        category_pages = [
            CommunityPage(config=cfg),
            EnterprisePage(config=cfg),
            AccessPage(config=cfg),
            EquipmentPage(config=cfg),
            PipelinePage(config=cfg),
            MetroPage(config=cfg),
            FacilityPage(config=cfg),
        ]
        # 注入全部项目页，供导入/改类型后联动刷新
        all_page.set_category_pages(category_pages)
        # 全部项目页 + 7 个分类页双击 → 载入详情并切换（共用同一详情页）
        all_page.set_open_detail_handler(self.show_project_detail)
        for cp in category_pages:
            cp.set_open_detail_handler(self.show_project_detail)
        self.add_page("community", category_pages[0])
        self.add_page("enterprise", category_pages[1])
        self.add_page("access", category_pages[2])
        self.add_page("equipment", category_pages[3])
        self.add_page("pipeline", category_pages[4])
        self.add_page("metro", category_pages[5])
        self.add_page("facility", category_pages[6])

        # 占位顶级页
        self.add_page("ai_assistant", AIAssistantPage())
        self.add_page("settings", SettingsPage())

        # 扫描结果中心页面：独立导航项
        self._scan_center_page = ScanCenterPage(config=cfg)
        self.add_page("scan_center", self._scan_center_page)

        # 项目详情页：双击项目后的次级只读页（不属于导航树）
        self._detail_page = ProjectDetailPage(config=cfg)
        self.add_page("project_detail", self._detail_page)
        # 「返回」按钮 → 回到全部项目列表
        self._detail_page.back_btn.clicked.connect(
            lambda: self.switch_to("all_projects")
        )

    def add_page(self, key: str, page: QWidget) -> None:
        """将页面加入栈并记录索引。"""
        index = self.page_stack.addWidget(page)
        self._page_index[key] = index

    def switch_to(self, key: str) -> None:
        """切换到指定页面；未注册时忽略。

        切换到扫描中心时自动刷新项目列表，确保下拉框包含最新导入的项目。
        """
        index = self._page_index.get(key)
        if index is not None:
            self.page_stack.setCurrentIndex(index)
        if key == "scan_center":
            self._scan_center_page._refresh_project_combo()

    def show_project_detail(self, project_id: int) -> None:
        """载入项目详情并切换到详情页。

        由「全部项目」页双击项目行调用。若项目不存在则不切换。

        v1.4 修复：打开项目只加载 scan_result 缓存，不触发扫描。
        """
        if self._detail_page.load_project(project_id):
            self.switch_to("project_detail")
            # v1.4：预加载扫描结果中心缓存（不扫描）
            self._scan_center_page.load_project_cached(project_id)

    def _apply_shadow(self) -> None:
        """为卡片添加柔和投影。"""
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(20)
        effect.setXOffset(0)
        effect.setYOffset(2)
        effect.setColor(QColor(0, 0, 0, 25))
        self.setGraphicsEffect(effect)
