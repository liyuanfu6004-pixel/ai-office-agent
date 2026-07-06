"""城域网页面模块。

对应导航 "项目管理 / 城域网"。继承分类展示页，仅展示城域网类项目，
不含导入功能。
"""
from __future__ import annotations

from ....config import AppConfig
from .project_management_page import ProjectCategoryPage


class MetroPage(ProjectCategoryPage):
    """城域网项目分类展示页。"""

    def __init__(self, config: AppConfig | None = None, parent=None) -> None:
        super().__init__(category="城域网", config=config, parent=parent)
