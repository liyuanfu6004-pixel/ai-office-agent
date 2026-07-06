"""社区页面模块。

对应导航 "项目管理 / 社区"。继承分类展示页，仅展示社区类项目，
纯只读（导入口与编辑能力归「全部项目」页）。
"""
from __future__ import annotations

from ....config import AppConfig
from .project_management_page import ProjectCategoryPage


class CommunityPage(ProjectCategoryPage):
    """社区项目分类展示页。"""

    def __init__(self, config: AppConfig | None = None, parent=None) -> None:
        super().__init__(category="社区", config=config, parent=parent)
