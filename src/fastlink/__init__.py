"""
FastLink Integration Module

提供FastLink依赖管理、版本检查和自动更新功能。
作为Python与FastLink Rust库之间的桥接层。
"""

from .version_manager import FastLinkVersionManager, VersionInfo, VersionConstraint
from .compatibility import CompatibilityChecker, InterfaceVersion
from .auto_updater import AutoUpdater, UpdateConfig
from .bridge import FastLinkBridge, BridgeConfig

__all__ = [
    'FastLinkVersionManager',
    'VersionInfo',
    'VersionConstraint',
    'CompatibilityChecker',
    'InterfaceVersion',
    'AutoUpdater',
    'UpdateConfig',
    'FastLinkBridge',
    'BridgeConfig',
]
