#!/usr/bin/env python3
"""Mocked API tests that won't hang on network calls"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Set dummy env vars
os.environ["HELIUS_KEY"] = "test_key"
os.environ["BIRDEYE_API_KEY"] = "test_key"


def test_api_endpoints():
    """Test API endpoints with mocked blockchain fetcher"""
    with patch("src.api.wallet_analytics_api_v3.BlockchainFetcherV3Fast") as mock_fetcher:
        # Import after patching
        from src.api.wallet_analytics_api_v3 import app

        # Create test client
        app.config["TESTING"] = True
        client = app.test_client()

        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json["status"] == "healthy"
        print("✓ Health endpoint works")

        # Test home endpoint
        response = client.get("/")
        assert response.status_code == 200
        assert "service" in response.json
        print("✓ Home endpoint works")

        # Mock the fetcher response with complete structure
        mock_instance = AsyncMock()
        mock_instance.fetch_wallet_trades = AsyncMock(
            return_value={
                "wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
                "trades": [],
                "summary": {
                    "total_trades": 0,
                    "total_volume": 0.0,
                    "priced_trades": 0,
                    "total_pnl_usd": 0.0,
                    "win_rate": 0.0,
                    "execution_time": 0.5,
                    "metrics": {
                        "signatures_fetched": 100,
                        "signatures_parsed": 95,
                        "events_swap_rows": 20,
                        "fallback_rows": 75,
                        "dust_filtered": 5,
                        "dup_rows": 0,
                        "parser_errors": 0,
                        "unpriced_rows": 0,
                    },
                },
            }
        )
        mock_fetcher.return_value.__aenter__.return_value = mock_instance

        # Test analyze endpoint with mocked response
        response = client.post(
            "/analyze", json={"wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"}, content_type="application/json"
        )

        # Debug the response
        if response.status_code != 200:
            print(f"Analyze endpoint failed with status {response.status_code}")
            print(f"Response: {response.data}")

        assert response.status_code == 200
        data = response.json
        assert "wallet" in data
        assert "fetch_metrics" in data
        print("✓ Analyze endpoint works with mocked data")


def test_blockchain_fetcher_v3():
    """Test BlockchainFetcherV3 with mocked HTTP calls"""
    with patch("aiohttp.ClientSession") as mock_session:
        from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3

        # Mock the session
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=[])
        mock_resp.raise_for_status = Mock()

        mock_session_instance = AsyncMock()
        mock_session_instance.get = AsyncMock(return_value=mock_resp)
        mock_session_instance.post = AsyncMock(return_value=mock_resp)
        mock_session.return_value = mock_session_instance

        # Test initialization
        fetcher = BlockchainFetcherV3()
        assert fetcher is not None
        print("✓ BlockchainFetcherV3 initializes")


def test_rate_limiter():
    """Test rate limiter functionality"""
    from src.lib.blockchain_fetcher_v3 import RateLimiter

    limiter = RateLimiter(calls_per_second=10)

    # Should be able to acquire immediately
    async def test_acquire():
        await limiter.acquire()
        return True

    result = asyncio.run(test_acquire())
    assert result
    print("✓ RateLimiter works")


def test_price_cache():
    """Test price cache functionality"""
    from src.lib.blockchain_fetcher_v3 import PriceCache
    from datetime import datetime
    from decimal import Decimal

    cache = PriceCache()

    # Test set and get with proper types
    timestamp = datetime.fromtimestamp(1234567890)
    cache.set("test_mint", timestamp, Decimal("123.45"))
    price = cache.get("test_mint", timestamp)
    assert price == Decimal("123.45")
    print("✓ PriceCache works")


def test_metrics():
    """Test metrics tracking"""
    from src.lib.blockchain_fetcher_v3 import Metrics

    metrics = Metrics()
    metrics.signatures_fetched = 100
    metrics.signatures_parsed = 95

    assert metrics.signatures_fetched == 100
    assert metrics.signatures_parsed == 95
    print("✓ Metrics tracking works")


if __name__ == "__main__":
    print("Running mocked tests...")
    test_api_endpoints()
    test_blockchain_fetcher_v3()
    test_rate_limiter()
    test_price_cache()
    test_metrics()
    print("\n✅ All mocked tests passed!")
