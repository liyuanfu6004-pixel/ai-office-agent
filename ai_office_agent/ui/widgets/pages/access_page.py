"""接入段页面模块。

对应导航 "项目管理 / 接入段"。继承分类展示页，仅展示接入段类项目，
不含导入功能。
"""
from __future__ import annotations

from ....config import AppConfig
from .project_management_page import ProjectCategoryPage


class AccessPage(ProjectCategoryPage):
    """接入段项目分类展示页。"""

    def __init__(self, config: AppConfig | None = None, parent=None) -> None:
        super().__init__(category="接入段", config=config, parent=parent)
