"""设备页面模块。

对应导航 "项目管理 / 设备"。继承分类展示页，仅展示设备类项目，
不含导入功能。
"""
from __future__ import annotations

from ....config import AppConfig
from .project_management_page import ProjectCategoryPage


class EquipmentPage(ProjectCategoryPage):
    """设备项目分类展示页。"""

    def __init__(self, config: AppConfig | None = None, parent=None) -> None:
        super().__init__(category="设备", config=config, parent=parent)
