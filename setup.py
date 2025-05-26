"""font-syncパッケージのセットアップスクリプト"""

from setuptools import setup, find_packages
from pathlib import Path

# READMEを読み込む
readme = Path("README.md")
long_description = readme.read_text() if readme.exists() else ""

setup(
    name="font-sync",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="macOS専用のCLIフォント同期ツール",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/font-sync",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: MacOS :: MacOS X",
    ],
    python_requires=">=3.8",
    install_requires=[
        "typer[all]>=0.9.0",
        "rich>=13.7.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "font-sync=src.main:app",
        ],
    },
) 