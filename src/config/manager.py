"""
Configuration Manager

处理配置文件的加载、保存和验证。
"""

from __future__ import annotations
import os
import json
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import asdict

from .settings import MinecraftBCSettings

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    配置管理器
    
    管理minecraftBC的配置文件。
    支持JSON和YAML格式。
    
    默认配置路径:
    - Windows: %APPDATA%/minecraftBC/config.yaml
    - Linux/macOS: ~/.config/minecraftBC/config.yaml
    """
    
    DEFAULT_CONFIG_NAME = "config.yaml"
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认使用系统配置目录
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self._get_default_config_path()
        
        self._settings: Optional[MinecraftBCSettings] = None
    
    def _get_default_config_path(self) -> Path:
        """获取默认配置文件路径"""
        if os.name == 'nt':  # Windows
            app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
            config_dir = Path(app_data) / "minecraftBC"
        else:  # Linux/macOS
            config_dir = Path.home() / ".config" / "minecraftBC"
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / self.DEFAULT_CONFIG_NAME
    
    def load(self) -> MinecraftBCSettings:
        """
        加载配置
        
        Returns:
            设置对象
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    if self.config_path.suffix == '.yaml' or self.config_path.suffix == '.yml':
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)
                
                self._settings = MinecraftBCSettings.from_dict(data)
                logger.info(f"Loaded config from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load config: {e}, using defaults")
                self._settings = MinecraftBCSettings()
        else:
            logger.info(f"Config file not found, using defaults")
            self._settings = MinecraftBCSettings()
        
        return self._settings
    
    def save(self) -> bool:
        """
        保存配置
        
        Returns:
            保存成功返回True
        """
        if self._settings is None:
            logger.error("No settings to save")
            return False
        
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = self._settings.to_dict()
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.suffix == '.yaml' or self.config_path.suffix == '.yml':
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved config to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def get_settings(self) -> MinecraftBCSettings:
        """获取当前设置"""
        if self._settings is None:
            return self.load()
        return self._settings
    
    def update_settings(self, settings: MinecraftBCSettings) -> None:
        """更新设置"""
        self._settings = settings
    
    @staticmethod
    def create_default_config(path: str) -> bool:
        """
        创建默认配置文件
        
        Args:
            path: 配置文件路径
        
        Returns:
            创建成功返回True
        """
        try:
            config_path = Path(path)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            settings = MinecraftBCSettings()
            data = settings.to_dict()
            
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix == '.yaml' or config_path.suffix == '.yml':
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created default config at {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create default config: {e}")
            return False
