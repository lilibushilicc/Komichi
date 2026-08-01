"""Komichi CLI 打包配置"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="komichi-cli",
    version="0.2.0",
    description="Komichi CLI - 基于 Cloudflare Serverless 的漫画追更管理系统命令行工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Komichi",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "komichi-crawler>=1.1",
        "click>=8.0.0",
        "httpx>=0.24.0",
        "rich>=13.0.0",
        "parsel>=1.8.0",
        "curl-cffi>=0.7.0",
    ],
    entry_points={
        "console_scripts": [
            "komichi-cli=komichi_cli.main:cli",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
)
