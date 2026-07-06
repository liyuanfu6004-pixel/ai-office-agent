"""集客页面模块。

对应导航 "项目管理 / 集客"。继承分类展示页，仅展示集客类项目，
不含导入功能。
"""
from __future__ import annotations

from ....config import AppConfig
from .project_management_page import ProjectCategoryPage


class EnterprisePage(ProjectCategoryPage):
    """集客项目分类展示页。"""

    def __init__(self, config: AppConfig | None = None, parent=None) -> None:
        super().__init__(category="集客", config=config, parent=parent)
