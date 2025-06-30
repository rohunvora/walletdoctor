#!/usr/bin/env python3
"""Basic import tests to verify code structure without network calls"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Test that all modules can be imported"""
    # Test lib imports
    from src.lib import blockchain_fetcher_v3
    from src.lib import blockchain_fetcher_v3_fast

    # Test API imports
    from src.api import wallet_analytics_api_v3

    # Check key classes exist
    assert hasattr(blockchain_fetcher_v3, "BlockchainFetcherV3")
    assert hasattr(blockchain_fetcher_v3_fast, "BlockchainFetcherV3Fast")
    assert hasattr(wallet_analytics_api_v3, "app")

    print("✓ All imports successful")


def test_env_vars():
    """Test that environment variables are handled properly"""
    # Save original values
    import os

    original_helius = os.environ.get("HELIUS_KEY")
    original_birdeye = os.environ.get("BIRDEYE_API_KEY")

    # Test missing env vars
    os.environ.pop("HELIUS_KEY", None)
    os.environ.pop("BIRDEYE_API_KEY", None)

    # Should fail gracefully
    from src.lib import blockchain_fetcher_v3

    assert blockchain_fetcher_v3.HELIUS_KEY is None
    assert blockchain_fetcher_v3.BIRDEYE_API_KEY is None

    # Restore
    if original_helius:
        os.environ["HELIUS_KEY"] = original_helius
    if original_birdeye:
        os.environ["BIRDEYE_API_KEY"] = original_birdeye

    print("✓ Environment variable handling works")


if __name__ == "__main__":
    test_imports()
    test_env_vars()
    print("\n✅ Basic tests passed!")
