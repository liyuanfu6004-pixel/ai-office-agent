"""区县语义归一化模块 — v1.2.3 引入。

加载 config/region_profile_2026_km.json，提供：
- active_counties：项目负责区县白名单
- aliases：区县别名 → 标准名称映射
- normalize_county(raw) → 标准区县名称或 None
- is_active_county(name) → 是否在负责范围内
"""
from __future__ import annotations

import json
from pathlib import Path

from ..utils.logger import setup_logger

logger = setup_logger()

_PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "region_profile_2026_km.json"


class RegionProfile:
    """区县语义归一化配置。

    使用方式：
        profile = RegionProfile.load()
        normalized = profile.normalize("安宁")   # → "安宁市"
        if profile.is_active("安宁市"):
            ...
    """

    def __init__(self, active: list[str], aliases: dict[str, str]) -> None:
        self._active = set(active)
        self._aliases = aliases

    @classmethod
    def load(cls, path: str | None = None) -> RegionProfile:
        """从 JSON 文件加载区县配置。

        Args:
            path: JSON 文件路径，默认 config/region_profile_2026_km.json。
        """
        filepath = Path(path) if path else _PROFILE_PATH
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            active = data.get("active_counties", [])
            aliases = data.get("aliases", {})
            logger.info("区县配置已加载：%d 个负责区县，%d 个别名",
                        len(active), len(aliases))
            return cls(active=active, aliases=aliases)
        except FileNotFoundError:
            logger.warning("区县配置文件缺失：%s，使用空配置", filepath)
            return cls(active=[], aliases={})
        except json.JSONDecodeError as exc:
            logger.error("区县配置文件 JSON 解析失败：%s", exc)
            return cls(active=[], aliases={})

    @property
    def active_counties(self) -> list[str]:
        """负责区县列表（标准名称）。"""
        return sorted(self._active)

    def normalize(self, raw: str | None) -> str | None:
        """将任意区县名称归一化为标准名称。

        Args:
            raw: 原始区县名称（如"安宁"）。

        Returns:
            标准名称（如"安宁市"），如果无法映射则返回原始值。
        """
        if not raw or not isinstance(raw, str):
            return None
        s = raw.strip()
        # 精确匹配 alias
        if s in self._aliases:
            result = self._aliases[s]
            if result != s:
                logger.debug("区县归一化：%s → %s", s, result)
            return result
        return s

    def is_active(self, name: str | None) -> bool:
        """判断区县是否在项目负责范围内。

        Args:
            name: 原始或已归一化的区县名称。

        Returns:
            True 表示在负责范围内。
        """
        if not name:
            return False
        normalized = self.normalize(name)
        return (normalized or name) in self._active


# 全局单例（惰性加载）
_profile: RegionProfile | None = None


def get_profile() -> RegionProfile:
    """获取全局 RegionProfile 单例。"""
    global _profile
    if _profile is None:
        _profile = RegionProfile.load()
    return _profile


def reset_profile() -> None:
    """重置全局配置（测试用）。"""
    global _profile
    _profile = None
