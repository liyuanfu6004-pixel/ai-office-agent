"""管道页面模块。

对应导航 "项目管理 / 管道"。继承分类展示页，仅展示管道类项目，
不含导入功能。
"""
from __future__ import annotations

from ....config import AppConfig
from .project_management_page import ProjectCategoryPage


class PipelinePage(ProjectCategoryPage):
    """管道项目分类展示页。"""

    def __init__(self, config: AppConfig | None = None, parent=None) -> None:
        super().__init__(category="管道", config=config, parent=parent)
