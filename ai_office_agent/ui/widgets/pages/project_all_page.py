"""全部项目页面模块。

对应导航 "项目管理 / 全部项目"。是全系统**唯一**的 Excel 导入口与
「新增项目」入口，展示全部项目，project_type 列支持下拉修改归属类别。
"""
from __future__ import annotations

from ....config import AppConfig
from .project_management_page import ProjectAllPage


class ProjectAllEntryPage(ProjectAllPage):
    """全部项目页（全局唯一总入口）。"""

    def __init__(self, config: AppConfig | None = None, parent=None) -> None:
        super().__init__(config=config, parent=parent)
