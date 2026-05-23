"""
minecraftBC Setup
Minecraft 桥接连接器安装脚本
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip() 
        for line in requirements_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="minecraftBC",
    version="0.1.0",
    description="Minecraft Bridge Connector - P2P联机与跨游戏互联",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="minecraftBC Team",
    author_email="",
    url="https://github.com/yourusername/minecraftBC",
    
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    
    include_package_data=True,
    package_data={
        "": ["*.json", "*.yaml", "*.yml"],
    },
    
    install_requires=requirements,
    
    extras_require={
        "gui": ["PyQt6>=6.5.0"],
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "mypy>=1.5.0",
        ],
    },
    
    entry_points={
        "console_scripts": [
            "minecraftBC=minecraftBC.main:main",
            "mcbc=minecraftBC.main:main",
        ],
    },
    
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Games/Entertainment",
        "Topic :: Internet",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    
    python_requires=">=3.9",
    
    keywords=[
        "minecraft",
        "p2p",
        "multiplayer",
        "fastlink",
        "mnmcp",
        "cross-game",
        "miniworld",
        "nat-traversal",
    ],
    
    project_urls={
        "Bug Reports": "https://github.com/yourusername/minecraftBC/issues",
        "Source": "https://github.com/yourusername/minecraftBC",
    },
)
