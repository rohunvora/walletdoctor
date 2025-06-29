#!/usr/bin/env python
"""
WalletDoctor Analytics - Setup Configuration
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="walletdoctor-analytics",
    version="2.0.0",
    author="WalletDoctor Team",
    description="Pure analytics microservice for trading data analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/walletdoctor",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "Flask>=2.3.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "requests>=2.31.0",
        ],
        "production": [
            "gunicorn>=21.2.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "walletdoctor-api=wallet_analytics_api:main",
            "walletdoctor-analyze=wallet_analytics_service:main",
        ],
    },
) 