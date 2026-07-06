"""功能页面包。

汇聚所有右侧内容页面，供内容区域统一注册。
"""
from __future__ import annotations

from .access_page import AccessPage
from .ai_assistant_page import AIAssistantPage
from .base_page import BasePage
from .community_page import CommunityPage
from .enterprise_page import EnterprisePage
from .equipment_page import EquipmentPage
from .facility_page import FacilityPage
from .metro_page import MetroPage
from .pipeline_page import PipelinePage
from .project_all_page import ProjectAllEntryPage
from .project_detail_page import ProjectDetailPage
from .scan_center_page import ScanCenterPage
from .settings_page import SettingsPage

__all__ = [
    "BasePage",
    "ProjectAllEntryPage",
    "ProjectDetailPage",
    "ScanCenterPage",
    "CommunityPage",
    "EnterprisePage",
    "AccessPage",
    "EquipmentPage",
    "PipelinePage",
    "MetroPage",
    "FacilityPage",
    "AIAssistantPage",
    "SettingsPage",
]
