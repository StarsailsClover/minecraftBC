"""
FastLink Auto Updater

自动检查和安装FastLink更新。
支持版本锁定、回退和自动更新策略。
"""

from __future__ import annotations
import asyncio
import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Callable, Tuple
from dataclasses import asdict

logger = logging.getLogger(__name__)


class UpdateStrategy(Enum):
    """更新策略"""
    AUTO = "auto"           # 自动安装稳定版更新
    LOCKED = "locked"       # 仅使用锁定版本
    STABLE_ONLY = "stable"  # 仅安装稳定版


@dataclass
class UpdateConfig:
    """更新配置"""
    strategy: UpdateStrategy = UpdateStrategy.STABLE_ONLY
    
    # 检查间隔
    check_interval_hours: int = 24
    
    # 是否自动安装
    auto_install: bool = False
    
    # 通知设置
    notify_on_update: bool = True
    
    # 回滚设置
    auto_rollback_on_failure: bool = True
    
    # 允许的更新类型
    allow_major_updates: bool = False
    allow_minor_updates: bool = True
    allow_patch_updates: bool = True
    
    def is_allowed(self, version: str) -> bool:
        """检查版本是否允许自动更新"""
        if self.strategy == UpdateStrategy.LOCKED:
            return False
        
        parts = version.split('.')
        if len(parts) >= 2:
            major = int(parts[0])
            minor = int(parts[1])
            
            if not self.allow_major_updates and major > 0:
                return False
            if not self.allow_minor_updates and minor > 0:
                return False
        
        return True


class FastLinkUpdater:
    """
    FastLink自动更新器
    
    功能:
    - 定期检查更新
    - 自动或手动安装更新
    - 版本回滚
    - 更新历史记录
    
    使用示例:
    ```python
    updater = FastLinkUpdater(config=UpdateConfig(auto_install=True))
    await updater.initialize()
    
    # 手动检查更新
    update = await updater.check_and_install()
    ```
    """
    
    def __init__(self, 
                 repo_path: Optional[Path] = None,
                 config: Optional[UpdateConfig] = None):
        self.repo_path = repo_path or Path(__file__).parent.parent.parent / "FastLink"
        self.config = config or UpdateConfig()
        
        self._history_file = self.repo_path.parent / "fastlink_update_history.json"
        self._update_history: List[Dict] = []
        self._last_check: Optional[datetime] = None
        
        # 回调
        self._on_update_available: List[Callable] = []
        self._on_update_complete: List[Callable] = []
        self._on_update_failed: List[Callable] = []
    
    async def initialize(self) -> bool:
        """初始化更新器"""
        await self._load_history()
        return self.repo_path.exists()
    
    async def check_and_install(self, 
                                 strategy: Optional[UpdateStrategy] = None
                                 ) -> Tuple[bool, Optional[str]]:
        """
        检查并安装更新
        
        Args:
            strategy: 覆盖默认策略
        
        Returns:
            (success, installed_version_or_none)
        """
        use_strategy = strategy or self.config.strategy
        
        # 锁定模式下不检查更新
        if use_strategy == UpdateStrategy.LOCKED:
            return False, None
        
        # 检查更新
        from .version_manager import FastLinkVersionManager
        manager = FastLinkVersionManager(self.repo_path)
        
        latest = await manager.check_for_updates()
        if not latest:
            return False, None
        
        current = manager.get_current_version()
        if not current or latest._compare_version(current.version) <= 0:
            return False, None
        
        logger.info(f"Update available: {current.version} -> {latest.version}")
        
        # 通知
        for cb in self._on_update_available:
            cb(current, latest)
        
        # 安装更新
        if use_strategy == UpdateStrategy.AUTO or self.config.auto_install:
            if self.config.is_allowed(latest.version):
                return await self._install_update(latest)
        
        return False, latest.version
    
    async def _install_update(self, version_info) -> Tuple[bool, Optional[str]]:
        """安装指定版本"""
        try:
            logger.info(f"Installing FastLink {version_info.version}...")
            
            # 切换到指定版本
            tag = f"v{version_info.version}" if not version_info.version.startswith('v') else version_info.version
            
            result = await asyncio.create_subprocess_exec(
                "git", "-C", str(self.repo_path),
                "checkout", tag,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error = stderr.decode()
                logger.error(f"Git checkout failed: {error}")
                return False, None
            
            # 构建
            build_success = await self._build_fastlink()
            if not build_success:
                # 回滚
                await self._rollback()
                return False, None
            
            # 记录历史
            self._record_update(version_info.version, "success")
            
            # 通知
            for cb in self._on_update_complete:
                cb(version_info)
            
            logger.info(f"FastLink updated to {version_info.version}")
            return True, version_info.version
            
        except Exception as e:
            logger.error(f"Update failed: {e}")
            self._record_update(version_info.version, f"failed: {e}")
            
            for cb in self._on_update_failed:
                cb(version_info, str(e))
            
            return False, None
    
    async def _build_fastlink(self) -> bool:
        """构建FastLink"""
        try:
            # 检查Rust是否安装
            result = await asyncio.create_subprocess_exec(
                "cargo", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            
            if result.returncode != 0:
                logger.error("Rust/cargo not found, cannot build FastLink")
                return False
            
            # 构建
            logger.info("Building FastLink...")
            result = await asyncio.create_subprocess_exec(
                "cargo", "build", "--release",
                cwd=str(self.repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 不等待完成，允许超时
            try:
                stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=300)
                if result.returncode == 0:
                    logger.info("FastLink build successful")
                    return True
                else:
                    logger.error(f"Build failed: {stderr.decode()}")
                    return False
            except asyncio.TimeoutError:
                logger.error("Build timeout")
                return False
                
        except Exception as e:
            logger.error(f"Build error: {e}")
            return False
    
    async def _rollback(self) -> bool:
        """回滚到上一个版本"""
        try:
            logger.info("Rolling back FastLink...")
            
            # 读取历史记录
            if len(self._update_history) >= 2:
                prev_version = self._update_history[-2]['version']
                
                result = await asyncio.create_subprocess_exec(
                    "git", "-C", str(self.repo_path),
                    "checkout", f"v{prev_version}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    logger.info(f"Rolled back to {prev_version}")
                    self._record_update(prev_version, "rollback")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def _record_update(self, version: str, status: str) -> None:
        """记录更新历史"""
        self._update_history.append({
            'version': version,
            'status': status,
            'timestamp': datetime.now().isoformat()
        })
        
        # 只保留最近20条
        if len(self._update_history) > 20:
            self._update_history = self._update_history[-20:]
        
        self._save_history()
    
    async def _load_history(self) -> None:
        """加载更新历史"""
        if self._history_file.exists():
            try:
                with open(self._history_file, 'r') as f:
                    self._update_history = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load update history: {e}")
    
    def _save_history(self) -> None:
        """保存更新历史"""
        try:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._history_file, 'w') as f:
                json.dump(self._update_history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save update history: {e}")
    
    def get_update_history(self) -> List[Dict]:
        """获取更新历史"""
        return self._update_history.copy()
    
    def on_update_available(self, callback: Callable) -> None:
        """注册更新可用回调"""
        self._on_update_available.append(callback)
    
    def on_update_complete(self, callback: Callable) -> None:
        """注册更新完成回调"""
        self._on_update_complete.append(callback)
    
    def on_update_failed(self, callback: Callable) -> None:
        """注册更新失败回调"""
        self._on_update_failed.append(callback)
    
    async def run_background_check(self, interval_hours: Optional[int] = None) -> None:
        """
        后台定期检查更新
        
        Args:
            interval_hours: 检查间隔(小时)
        """
        interval = interval_hours or self.config.check_interval_hours
        
        while True:
            try:
                await self.check_and_install()
            except Exception as e:
                logger.error(f"Background check error: {e}")
            
            await asyncio.sleep(interval * 3600)
