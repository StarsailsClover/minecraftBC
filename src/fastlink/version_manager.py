"""
FastLink Version Manager

管理FastLink依赖的版本信息、约束检查和版本锁定。
支持语义化版本比较和兼容性矩阵。
"""

from __future__ import annotations
import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Callable
import hashlib

logger = logging.getLogger(__name__)


class VersionType(Enum):
    """版本类型"""
    STABLE = "stable"
    BETA = "beta"
    ALPHA = "alpha"
    RC = "rc"
    NIGHTLY = "nightly"


@dataclass
class VersionInfo:
    """
    FastLink版本信息
    
    Attributes:
        version: 语义化版本 (如 "0.1.0" 或 "26.5-20260531")
        version_type: 版本类型
        release_date: 发布日期
        commit_hash: Git提交哈希
        changelog_url: 更新日志URL
        binary_hash: 预编译二进制哈希 (可选)
        min_rust_version: 最低Rust版本要求
        breaking_changes: 是否包含破坏性变更
        features: 支持的特性列表
    """
    version: str
    version_type: VersionType = VersionType.STABLE
    release_date: Optional[str] = None
    commit_hash: Optional[str] = None
    changelog_url: Optional[str] = None
    binary_hash: Optional[str] = None
    min_rust_version: str = "1.75"
    breaking_changes: bool = False
    features: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        return f"{self.version} ({self.version_type.value})"
    
    def is_compatible_with(self, other: 'VersionConstraint') -> bool:
        """检查是否满足版本约束"""
        if other.exact:
            return self.version == other.exact
        
        if other.min_version and self._compare_version(other.min_version) < 0:
            return False
        
        if other.max_version and self._compare_version(other.max_version) > 0:
            return False
        
        return True
    
    def _compare_version(self, other: str) -> int:
        """
        比较版本号
        
        Returns:
            -1: self < other
             0: self == other
             1: self > other
        """
        # 处理 FastLink 版本格式: YY.MM.DD 或 26.5-20260531
        self_parts = self._parse_version(self.version)
        other_parts = self._parse_version(other)
        
        for s, o in zip(self_parts, other_parts):
            if isinstance(s, int) and isinstance(o, int):
                if s != o:
                    return -1 if s < o else 1
            elif isinstance(s, str) and isinstance(o, str):
                if s != o:
                    return -1 if s < o else 1
        
        return 0
    
    def _parse_version(self, version: str) -> List:
        """解析版本号为可比较的列表"""
        # 移除前缀 'v'
        version = version.lstrip('v')
        
        # 处理 FastLink 格式: 26.5-20260531
        if '-' in version and len(version) > 8:
            parts = version.split('-')
            date_part = parts[-1]
            # 尝试解析日期部分
            try:
                if len(date_part) == 8:
                    return [int(date_part[:4]), int(date_part[4:6]), int(date_part[6:8])]
            except ValueError:
                pass
        
        # 标准语义化版本: X.Y.Z
        parts = []
        for part in version.split('.'):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(part)
        
        return parts


@dataclass
class VersionConstraint:
    """
    版本约束
    
    用于指定FastLink版本要求。
    """
    exact: Optional[str] = None
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    allow_prerelease: bool = False
    
    def is_satisfied_by(self, version: VersionInfo) -> bool:
        """检查版本是否满足约束"""
        if not self.allow_prerelease and version.version_type != VersionType.STABLE:
            return False
        
        if self.exact:
            return version.version == self.exact
        
        if self.min_version and version._compare_version(self.min_version) < 0:
            return False
        
        if self.max_version and version._compare_version(self.max_version) > 0:
            return False
        
        return True
    
    @classmethod
    def parse(cls, constraint_str: str) -> 'VersionConstraint':
        """
        解析版本约束字符串
        
        Examples:
            ">=26.1" -> min_version="26.1"
            "~26.1" -> min_version="26.1", max_version="27.0"
            "26.1" -> exact="26.1"
            ">=26.1 <27.0" -> min_version="26.1", max_version="27.0"
        """
        constraint = cls()
        
        if not constraint_str:
            return constraint
        
        # 精确版本
        if ',' not in constraint_str and not constraint_str.startswith(('>=', '<=', '~', '^')):
            constraint.exact = constraint_str
            return constraint
        
        # 范围约束
        for part in constraint_str.split(','):
            part = part.strip()
            if part.startswith('>='):
                constraint.min_version = part[2:]
            elif part.startswith('<='):
                constraint.max_version = part[2:]
            elif part.startswith('~'):
                constraint.min_version = part[1:]
                # ~26.1 表示 >=26.1 <27.0
                base = part[1:].split('.')
                if len(base) >= 2:
                    next_major = int(base[0]) + 1
                    constraint.max_version = f"{next_major}.0"
            elif part.startswith('^'):
                constraint.min_version = part[1:]
            elif part.startswith('>'):
                # 需要实现更高版本比较
                constraint.min_version = part[1:]
        
        return constraint


class FastLinkVersionManager:
    """
    FastLink版本管理器
    
    功能:
    - 版本信息查询
    - 版本约束检查
    - 自动更新检测
    - 版本回退管理
    
    使用示例:
    ```python
    manager = FastLinkVersionManager()
    await manager.initialize()
    
    # 检查当前版本
    current = manager.get_current_version()
    print(f"Current: {current}")
    
    # 检查更新
    update = await manager.check_for_updates()
    if update.available:
        print(f"New version: {update.latest}")
    ```
    """
    
    # 已知稳定版本
    STABLE_VERSIONS = [
        VersionInfo("26.1-20260523", VersionType.STABLE, "2026-05-23", breaking_changes=False),
        VersionInfo("26.2-20260525", VersionType.STABLE, "2026-05-25", breaking_changes=False),
        VersionInfo("26.3-20260528", VersionType.STABLE, "2026-05-28", breaking_changes=False),
        VersionInfo("26.4-20260530", VersionType.STABLE, "2026-05-30", breaking_changes=False),
    ]
    
    # 当前锁定版本 (生产环境使用)
    LOCKED_VERSION = "26.1-20260523"
    
    # 兼容性矩阵: minecraftBC接口版本 -> FastLink最低版本
    COMPATIBILITY_MATRIX = {
        "1.0": "26.1-20260523",
        "1.1": "26.2-20260525",
    }
    
    def __init__(self, 
                 repo_path: Optional[Path] = None,
                 cache_ttl: timedelta = timedelta(hours=1)):
        self.repo_path = repo_path or Path(__file__).parent.parent.parent / "FastLink"
        self.cache_ttl = cache_ttl
        
        self._version_cache: Dict[str, VersionInfo] = {}
        self._last_check: Optional[datetime] = None
        self._lock_file = self.repo_path.parent / "fastlink.lock"
        
        # 回调
        self._update_available_callbacks: List[Callable[[VersionInfo, VersionInfo], None]] = []
    
    async def initialize(self) -> bool:
        """
        初始化版本管理器
        
        Returns:
            初始化成功返回True
        """
        # 检查FastLink仓库是否存在
        if not self.repo_path.exists():
            logger.warning(f"FastLink repository not found at {self.repo_path}")
            return False
        
        # 加载锁定版本
        await self._load_lock_file()
        
        # 检查Git状态
        if not await self._is_git_repo():
            logger.warning("FastLink directory is not a git repository")
            return False
        
        return True
    
    async def _is_git_repo(self) -> bool:
        """检查是否为Git仓库"""
        try:
            result = await asyncio.create_subprocess_exec(
                "git", "-C", str(self.repo_path), "rev-parse", "--git-dir",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            return result.returncode == 0
        except Exception:
            return False
    
    async def _load_lock_file(self) -> None:
        """加载版本锁定文件"""
        if self._lock_file.exists():
            try:
                with open(self._lock_file, 'r') as f:
                    data = json.load(f)
                    self.LOCKED_VERSION = data.get('locked_version', self.LOCKED_VERSION)
            except Exception as e:
                logger.error(f"Failed to load lock file: {e}")
    
    async def _save_lock_file(self) -> None:
        """保存版本锁定文件"""
        try:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._lock_file, 'w') as f:
                json.dump({
                    'locked_version': self.LOCKED_VERSION,
                    'updated_at': datetime.now().isoformat(),
                    'reason': 'stable_release'
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save lock file: {e}")
    
    def get_current_version(self) -> Optional[VersionInfo]:
        """获取当前安装的FastLink版本"""
        # 尝试从Cargo.toml读取
        cargo_toml = self.repo_path / "Cargo.toml"
        if cargo_toml.exists():
            try:
                with open(cargo_toml, 'r') as f:
                    for line in f:
                        if line.startswith('version'):
                            version = line.split('=')[1].strip().strip('"')
                            return VersionInfo(version, VersionType.STABLE)
            except Exception as e:
                logger.error(f"Failed to read Cargo.toml: {e}")
        
        # 从锁定文件读取
        if self.LOCKED_VERSION:
            return VersionInfo(self.LOCKED_VERSION, VersionType.STABLE)
        
        return None
    
    async def check_for_updates(self, 
                                 check_beta: bool = False,
                                 check_nightly: bool = False) -> Optional[VersionInfo]:
        """
        检查FastLink更新
        
        Args:
            check_beta: 是否检查Beta版本
            check_nightly: 是否检查Nightly版本
        
        Returns:
            如果有更新返回新版本信息，否则返回None
        """
        # 检查缓存
        if self._last_check and datetime.now() - self._last_check < self.cache_ttl:
            return None
        
        logger.info("Checking for FastLink updates...")
        
        try:
            # 从远程仓库获取标签
            result = await asyncio.create_subprocess_exec(
                "git", "-C", str(self.repo_path), 
                "ls-remote", "--tags", "origin",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if result.returncode != 0:
                logger.warning("Failed to fetch remote tags")
                return None
            
            # 解析标签
            tags = self._parse_git_tags(stdout.decode())
            
            # 筛选版本
            candidates = []
            for tag in tags:
                vinfo = self._tag_to_version(tag)
                if vinfo:
                    if vinfo.version_type == VersionType.STABLE:
                        candidates.append(vinfo)
                    elif check_beta and vinfo.version_type in (VersionType.BETA, VersionType.RC):
                        candidates.append(vinfo)
                    elif check_nightly and vinfo.version_type == VersionType.NIGHTLY:
                        candidates.append(vinfo)
            
            # 排序并获取最新版本
            candidates.sort(key=lambda v: v._compare_version(VersionInfo("0.0.0").version), reverse=True)
            
            self._last_check = datetime.now()
            
            if candidates:
                latest = candidates[0]
                current = self.get_current_version()
                
                if current and latest._compare_version(current.version) > 0:
                    logger.info(f"New FastLink version available: {latest}")
                    return latest
            
            return None
            
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return None
    
    def _parse_git_tags(self, output: str) -> List[str]:
        """解析git ls-remote输出"""
        tags = []
        for line in output.strip().split('\n'):
            if line:
                # 格式: <hash>\trefs/tags/<tag>
                parts = line.split('\t')
                if len(parts) == 2:
                    tag = parts[1].replace('refs/tags/', '')
                    # 过滤掉非版本标签
                    if tag.startswith('v') or (tag[0].isdigit() and '.' in tag):
                        tags.append(tag)
        return tags
    
    def _tag_to_version(self, tag: str) -> Optional[VersionInfo]:
        """将Git标签转换为VersionInfo"""
        # 移除 'v' 前缀
        version = tag.lstrip('v')
        
        # 判断版本类型
        version_type = VersionType.STABLE
        if 'beta' in version.lower() or 'b' in version.lower():
            version_type = VersionType.BETA
        elif 'alpha' in version.lower() or 'a' in version.lower():
            version_type = VersionType.ALPHA
        elif 'rc' in version.lower():
            version_type = VersionType.RC
        elif 'nightly' in version.lower():
            version_type = VersionType.NIGHTLY
        
        return VersionInfo(
            version=version,
            version_type=version_type,
            features=["p2p", "server", "swift"]  # 默认特性
        )
    
    async def lock_version(self, version: str, reason: str = "stable_release") -> bool:
        """
        锁定FastLink版本
        
        锁定后不会自动更新到新版本。
        
        Args:
            version: 版本号
            reason: 锁定原因
        
        Returns:
            锁定成功返回True
        """
        try:
            self.LOCKED_VERSION = version
            await self._save_lock_file()
            logger.info(f"FastLink version locked to {version}: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to lock version: {e}")
            return False
    
    async def unlock_version(self) -> bool:
        """解除版本锁定"""
        try:
            self.LOCKED_VERSION = ""
            if self._lock_file.exists():
                self._lock_file.unlink()
            logger.info("FastLink version unlocked")
            return True
        except Exception as e:
            logger.error(f"Failed to unlock version: {e}")
            return False
    
    def get_compatible_versions(self, interface_version: str = "1.0") -> List[VersionInfo]:
        """
        获取与指定接口版本兼容的FastLink版本
        
        Args:
            interface_version: minecraftBC接口版本
        
        Returns:
            兼容的版本列表
        """
        min_version = self.COMPATIBILITY_MATRIX.get(interface_version, "26.1-20260523")
        constraint = VersionConstraint(min_version=min_version)
        
        compatible = []
        for version in self.STABLE_VERSIONS:
            if constraint.is_satisfied_by(version):
                compatible.append(version)
        
        return sorted(compatible, key=lambda v: v._compare_version("0.0.0"), reverse=True)
    
    def on_update_available(self, callback: Callable[[VersionInfo, VersionInfo], None]) -> None:
        """
        注册更新可用回调
        
        Args:
            callback: (current_version, new_version) -> None
        """
        self._update_available_callbacks.append(callback)
    
    async def run_version_check(self, callback_interval: int = 3600) -> None:
        """
        定期版本检查
        
        Args:
            callback_interval: 检查间隔(秒)
        """
        while True:
            try:
                update = await self.check_for_updates()
                if update:
                    current = self.get_current_version()
                    for cb in self._update_available_callbacks:
                        cb(current, update)
            except Exception as e:
                logger.error(f"Version check error: {e}")
            
            await asyncio.sleep(callback_interval)
