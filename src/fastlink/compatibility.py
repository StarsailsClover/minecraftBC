"""
FastLink Compatibility Checker

检查minecraftBC与FastLink之间的接口兼容性。
支持版本矩阵、特性检测和向后兼容保证。
"""

from __future__ import annotations
import asyncio
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Callable, Set

logger = logging.getLogger(__name__)


class InterfaceVersion:
    """
    minecraftBC与FastLink的接口版本
    
    使用语义化版本控制接口变更。
    """
    
    CURRENT = "1.0"
    HISTORY = [
        "1.0",  # 初始接口: P2P连接、节点发现
    ]
    
    @classmethod
    def is_compatible(cls, interface_version: str) -> bool:
        """检查接口版本是否兼容"""
        return interface_version in cls.HISTORY
    
    @classmethod
    def get_features(cls, interface_version: str) -> List[str]:
        """获取指定接口版本支持的特性"""
        features = {
            "1.0": [
                "p2p_connect",
                "p2p_listen",
                "node_discovery",
                "key_exchange",
                "message_send",
                "message_recv",
                "connection_stats",
            ],
        }
        return features.get(interface_version, [])


class FeatureFlag(Enum):
    """FastLink功能标记"""
    
    # P2P核心
    BIRTHDAY_PUNCH = "birthday_punch"
    ICE_SUPPORT = "ice_support"
    MULTI_PATH = "multi_path"
    
    # Server
    DHT_ROUTING = "dht_routing"
    SMART_RELAY = "smart_relay"
    REPUTATION_SYSTEM = "reputation_system"
    
    # Swift
    ANTI_DPI = "anti_dpi"
    TLS_FINGERPRINT = "tls_fingerprint"
    
    # Games
    FRAME_SYNC = "frame_sync"
    ROLLBACK = "rollback"
    JITTER_BUFFER = "jitter_buffer"
    
    # 通用
    ENCRYPTION = "encryption"
    AUTHENTICATION = "authentication"
    MULTI_ISP = "multi_isp"


@dataclass
class CompatibilityReport:
    """兼容性检查报告"""
    is_compatible: bool
    interface_version: str
    fastlink_version: str
    missing_features: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        status = "✅ COMPATIBLE" if self.is_compatible else "❌ INCOMPATIBLE"
        lines = [
            f"Compatibility Report ({status})",
            f"  minecraftBC interface: {self.interface_version}",
            f"  FastLink version: {self.fastlink_version}",
        ]
        
        if self.errors:
            lines.append("  Errors:")
            for err in self.errors:
                lines.append(f"    - {err}")
        
        if self.warnings:
            lines.append("  Warnings:")
            for warn in self.warnings:
                lines.append(f"    - {warn}")
        
        if self.missing_features:
            lines.append("  Missing Features:")
            for feat in self.missing_features:
                lines.append(f"    - {feat}")
        
        return '\n'.join(lines)


class CompatibilityChecker:
    """
    兼容性检查器
    
    检查minecraftBC与当前FastLink版本之间的兼容性。
    支持运行时检查和构建时检查。
    
    使用示例:
    ```python
    checker = CompatibilityChecker(fastlink_path)
    report = await checker.check_compatibility("1.0")
    if not report.is_compatible:
        print(report)
    ```
    """
    
    # 最小支持的FastLink版本
    MIN_FASTLINK_VERSION = "26.1-20260523"
    
    # 特性需求矩阵
    REQUIRED_FEATURES = {
        "1.0": {
            FeatureFlag.BIRTHDAY_PUNCH,
            FeatureFlag.ENCRYPTION,
            FeatureFlag.AUTHENTICATION,
        },
    }
    
    def __init__(self, 
                 fastlink_repo_path: Optional[Path] = None,
                 interface_version: str = InterfaceVersion.CURRENT):
        self.fastlink_repo_path = fastlink_repo_path or Path(__file__).parent.parent.parent / "FastLink"
        self.interface_version = interface_version
        self._feature_cache: Dict[str, bool] = {}
    
    async def check_compatibility(self, 
                                   fastlink_version: Optional[str] = None) -> CompatibilityReport:
        """
        执行兼容性检查
        
        Args:
            fastlink_version: 指定FastLink版本，None表示检测本地安装版本
        
        Returns:
            兼容性检查报告
        """
        errors = []
        warnings = []
        missing_features = []
        
        # 1. 检查FastLink是否存在
        if not self.fastlink_repo_path.exists():
            return CompatibilityReport(
                is_compatible=False,
                interface_version=self.interface_version,
                fastlink_version="not_found",
                errors=[f"FastLink repository not found at {self.fastlink_repo_path}"]
            )
        
        # 2. 获取FastLink版本
        version = fastlink_version or await self._detect_fastlink_version()
        if not version:
            errors.append("Could not detect FastLink version")
            return CompatibilityReport(
                is_compatible=False,
                interface_version=self.interface_version,
                fastlink_version="unknown",
                errors=errors
            )
        
        # 3. 检查最低版本要求
        min_version_check = self._check_min_version(version)
        if not min_version_check[0]:
            errors.append(min_version_check[1])
        
        # 4. 检查必需特性
        required = self.REQUIRED_FEATURES.get(self.interface_version, set())
        for feature in required:
            if not await self._check_feature_support(feature, version):
                missing_features.append(feature.value)
        
        # 5. 检查破坏性变更
        breaking = await self._check_breaking_changes(version)
        if breaking:
            warnings.append(f"Version {version} may contain breaking changes")
        
        # 生成报告
        is_compatible = len(errors) == 0 and len(missing_features) == 0
        
        return CompatibilityReport(
            is_compatible=is_compatible,
            interface_version=self.interface_version,
            fastlink_version=version,
            missing_features=missing_features,
            warnings=warnings,
            errors=errors
        )
    
    async def _detect_fastlink_version(self) -> Optional[str]:
        """检测本地FastLink版本"""
        try:
            # 从Cargo.toml读取
            cargo_toml = self.fastlink_repo_path / "Cargo.toml"
            if cargo_toml.exists():
                with open(cargo_toml, 'r') as f:
                    for line in f:
                        if line.startswith('version'):
                            return line.split('=')[1].strip().strip('"')
            
            # 从Git标签读取
            result = await asyncio.create_subprocess_exec(
                "git", "-C", str(self.fastlink_repo_path),
                "describe", "--tags", "--always",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            if result.returncode == 0:
                return stdout.decode().strip().lstrip('v')
            
        except Exception as e:
            logger.error(f"Version detection failed: {e}")
        
        return None
    
    def _check_min_version(self, version: str) -> Tuple[bool, str]:
        """检查最低版本要求"""
        # 简化版本比较
        current_parts = self._parse_version_parts(version)
        min_parts = self._parse_version_parts(self.MIN_FASTLINK_VERSION)
        
        for c, m in zip(current_parts, min_parts):
            if c < m:
                return False, f"FastLink version {version} is below minimum {self.MIN_FASTLINK_VERSION}"
            if c > m:
                break
        
        return True, ""
    
    def _parse_version_parts(self, version: str) -> Tuple[int, ...]:
        """解析版本号为数字元组"""
        version = version.lstrip('v')
        
        # FastLink格式: 26.1-20260523
        if '-' in version:
            parts = version.split('-')
            date = parts[-1]
            try:
                return (int(parts[0]), int(parts[1]), int(date[:8]))
            except (ValueError, IndexError):
                pass
        
        # 标准格式: X.Y.Z
        parts = []
        for p in version.split('.'):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        
        return tuple(parts)
    
    async def _check_feature_support(self, 
                                      feature: FeatureFlag, 
                                      version: str) -> bool:
        """检查特性是否在指定版本中支持"""
        cache_key = f"{feature.value}:{version}"
        
        if cache_key in self._feature_cache:
            return self._feature_cache[cache_key]
        
        # 特性支持矩阵
        FEATURE_MATRIX = {
            # FastLink 26.1+ 支持的特性
            "26.1-20260523": {
                FeatureFlag.BIRTHDAY_PUNCH: True,
                FeatureFlag.ENCRYPTION: True,
                FeatureFlag.AUTHENTICATION: True,
                FeatureFlag.DHT_ROUTING: True,
            },
            "26.2-20260525": {
                FeatureFlag.BIRTHDAY_PUNCH: True,
                FeatureFlag.ENCRYPTION: True,
                FeatureFlag.AUTHENTICATION: True,
                FeatureFlag.MULTI_PATH: True,
            },
            "26.3-20260528": {
                FeatureFlag.BIRTHDAY_PUNCH: True,
                FeatureFlag.ENCRYPTION: True,
                FeatureFlag.AUTHENTICATION: True,
                FeatureFlag.MULTI_PATH: True,
                FeatureFlag.ANTI_DPI: True,
            },
        }
        
        # 查找版本
        for v, features in FEATURE_MATRIX.items():
            if self._version_matches(version, v):
                supported = features.get(feature, False)
                self._feature_cache[cache_key] = supported
                return supported
        
        # 默认假设支持
        self._feature_cache[cache_key] = True
        return True
    
    def _version_matches(self, version: str, check_version: str) -> bool:
        """检查版本是否匹配或高于指定版本"""
        v1 = self._parse_version_parts(version)
        v2 = self._parse_version_parts(check_version)
        
        for a, b in zip(v1, v2):
            if a != b:
                return a > b
        
        return len(v1) >= len(v2)
    
    async def _check_breaking_changes(self, version: str) -> bool:
        """检查是否有破坏性变更"""
        # 从Git log检查
        try:
            result = await asyncio.create_subprocess_exec(
                "git", "-C", str(self.fastlink_repo_path),
                "log", f"v{version}..HEAD", "--oneline",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if result.returncode == 0:
                commits = stdout.decode().strip().split('\n')
                for commit in commits:
                    if 'BREAKING' in commit.upper() or '!' in commit:
                        return True
        except Exception:
            pass
        
        return False
    
    async def check_api_stability(self) -> Tuple[bool, List[str]]:
        """
        检查FastLink API稳定性
        
        Returns:
            (is_stable, warnings)
        """
        warnings = []
        
        # 检查是否有API文档
        docs_path = self.fastlink_repo_path / "docs"
        if not docs_path.exists():
            warnings.append("No API documentation found")
        
        # 检查版本标签稳定性
        tags = await self._get_git_tags()
        if len(tags) < 2:
            warnings.append("Less than 2 version tags - API may be unstable")
        
        # 检查是否有breaking changes历史
        breaking = await self._check_breaking_changes("HEAD")
        if breaking:
            warnings.append("Breaking changes detected in recent commits")
        
        return len(warnings) == 0, warnings
    
    async def _get_git_tags(self) -> List[str]:
        """获取Git标签"""
        try:
            result = await asyncio.create_subprocess_exec(
                "git", "-C", str(self.fastlink_repo_path),
                "tag", "-l",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if result.returncode == 0:
                return stdout.decode().strip().split('\n') if stdout else []
        except Exception:
            pass
        
        return []
