"""
Pytest configuration for GPT validation tests
"""

import pytest


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--use-mock",
        action="store_true",
        default=False,
        help="Use mock data instead of making real API calls"
    )
    parser.addoption(
        "--large",
        action="store_true", 
        default=False,
        help="Enable large wallet tests"
    ) 