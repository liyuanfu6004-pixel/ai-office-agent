"""设置页面模块。

对应导航顶级项 "设置"，当前为占位，暂不开发。
"""
from __future__ import annotations

from .base_page import BasePage


class SettingsPage(BasePage):
    """设置页面（占位，待开发）。"""

    def __init__(self, parent=None) -> None:
        super().__init__(title="设置", subtitle="待开发", parent=parent)
