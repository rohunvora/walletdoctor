#!/usr/bin/env python3
"""
Test Birdeye client functionality
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
import time
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.birdeye_client import (
    BirdeyeClient,
    get_birdeye_price,
    get_market_cap_from_birdeye,
    SOL_MINT,
    USDC_MINT
)


class TestBirdeyeClient:
    """Test BirdeyeClient class"""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock aiohttp session"""
        session = MagicMock()
        session.get = AsyncMock()
        return session
    
    @pytest.fixture
    def mock_response(self):
        """Create a mock response"""
        response = MagicMock()
        response.status = 200
        response.headers = {}
        response.json = AsyncMock()
        response.raise_for_status = MagicMock()
        return response
    
    @pytest.mark.asyncio
    async def test_get_token_price_success(self, mock_session, mock_response):
        """Test successful token price fetch"""
        # Setup mock response
        mock_response.json.return_value = {
            "data": {
                "value": 150.50,
                "liquidity": 1000000,
                "v24hUSD": 5000000,
                "priceChange24h": 5.2,
                "updateUnixTime": 1700000000
            }
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = BirdeyeClient(mock_session)
        result = await client.get_token_price(SOL_MINT)
        
        assert result is not None
        price, metadata = result
        assert price == Decimal("150.50")
        assert metadata["liquidity"] == 1000000
        assert metadata["volume24h"] == 5000000
        assert metadata["priceChange24h"] == 5.2
        assert metadata["source"] == "birdeye_current"
    
    @pytest.mark.asyncio
    async def test_get_token_price_not_found(self, mock_session, mock_response):
        """Test token price not found (404)"""
        mock_response.status = 404
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = BirdeyeClient(mock_session)
        result = await client.get_token_price("invalid_token")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_historical_price_success(self, mock_session, mock_response):
        """Test successful historical price fetch"""
        timestamp = int(time.time()) - 86400  # 24 hours ago
        
        # Setup mock response
        mock_response.json.return_value = {
            "data": {
                "items": [
                    {"unixTime": timestamp - 1800, "value": 149.0},
                    {"unixTime": timestamp, "value": 150.0},  # Exact match
                    {"unixTime": timestamp + 1800, "value": 151.0}
                ]
            }
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = BirdeyeClient(mock_session)
        result = await client.get_historical_price(SOL_MINT, timestamp)
        
        assert result is not None
        price, metadata = result
        assert price == Decimal("150.0")
        assert metadata["timestamp"] == timestamp
        assert metadata["timeDiff"] == 0  # Exact match
        assert metadata["source"] == "birdeye_historical"
    
    @pytest.mark.asyncio
    async def test_get_historical_price_closest_match(self, mock_session, mock_response):
        """Test historical price with closest match"""
        timestamp = int(time.time()) - 86400
        
        # Setup mock response with no exact match
        mock_response.json.return_value = {
            "data": {
                "items": [
                    {"unixTime": timestamp - 3600, "value": 149.0},
                    {"unixTime": timestamp + 600, "value": 150.5},  # Closest
                ]
            }
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = BirdeyeClient(mock_session)
        result = await client.get_historical_price(SOL_MINT, timestamp)
        
        assert result is not None
        price, metadata = result
        assert price == Decimal("150.5")
        assert metadata["timestamp"] == timestamp + 600
        assert metadata["timeDiff"] == 600
    
    @pytest.mark.asyncio
    async def test_get_token_market_data_success(self, mock_session, mock_response):
        """Test successful market data fetch"""
        # Setup mock response
        mock_response.json.return_value = {
            "data": {
                "price": 150.50,
                "mc": 86000000000,  # 86B market cap
                "fdv": 90000000000,
                "liquidity": 10000000,
                "v24hUSD": 5000000000,
                "priceChange24h": 5.2,
                "holder": 1500000,
                "decimals": 9,
                "supply": 574207458,
                "lastTradeUnixTime": 1700000000
            }
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = BirdeyeClient(mock_session)
        result = await client.get_token_market_data(SOL_MINT)
        
        assert result is not None
        assert result["price"] == 150.50
        assert result["marketCap"] == 86000000000
        assert result["fdv"] == 90000000000
        assert result["liquidity"] == 10000000
        assert result["volume24h"] == 5000000000
        assert result["holder"] == 1500000
        assert result["decimals"] == 9
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, mock_session, mock_response):
        """Test rate limiting behavior"""
        # First response is rate limited
        rate_limited_response = MagicMock()
        rate_limited_response.status = 429
        rate_limited_response.headers = {"Retry-After": "1"}
        
        # Second response is successful
        mock_response.json.return_value = {"data": {"value": 150.0}}
        
        # Configure mock to return rate limited first, then success
        mock_session.get.return_value.__aenter__.side_effect = [
            rate_limited_response,
            mock_response
        ]
        
        client = BirdeyeClient(mock_session)
        
        start_time = time.time()
        result = await client.get_token_price(SOL_MINT)
        elapsed = time.time() - start_time
        
        assert result is not None
        assert elapsed >= 1.0  # Should have waited at least 1 second
    
    @pytest.mark.asyncio
    async def test_api_error_response(self, mock_session, mock_response):
        """Test API error in response"""
        mock_response.json.return_value = {
            "success": False,
            "message": "Invalid API key"
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = BirdeyeClient(mock_session)
        result = await client.get_token_price(SOL_MINT)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_batch_get_prices(self, mock_session, mock_response):
        """Test batch price fetching"""
        tokens = ["token1", "token2", "token3"]
        
        # Mock different responses for each token
        responses = [
            {"data": {"value": 1.0}},
            {"data": {"value": 2.0}},
            {"data": {"value": 3.0}}
        ]
        
        call_count = 0
        async def mock_json():
            nonlocal call_count
            result = responses[call_count % len(responses)]
            call_count += 1
            return result
        
        mock_response.json = mock_json
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = BirdeyeClient(mock_session)
        results = await client.batch_get_prices(tokens)
        
        assert len(results) == 3
        assert results["token1"][0] == Decimal("1.0")
        assert results["token2"][0] == Decimal("2.0")
        assert results["token3"][0] == Decimal("3.0")
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test context manager functionality"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session
            
            async with BirdeyeClient() as client:
                assert client.session is mock_session
                assert client._owns_session is True
            
            # Verify session was closed
            mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_birdeye_price_convenience(self):
        """Test convenience function for getting price"""
        with patch('src.lib.birdeye_client.BirdeyeClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_token_price.return_value = (Decimal("150.0"), {"test": "data"})
            mock_client_class.return_value = mock_client
            
            result = await get_birdeye_price(SOL_MINT, USDC_MINT)
            
            assert result is not None
            price, source, metadata = result
            assert price == Decimal("150.0")
            assert source == "birdeye_current"
            assert metadata == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_get_birdeye_price_historical(self):
        """Test convenience function for historical price"""
        timestamp = int(time.time()) - 86400
        
        with patch('src.lib.birdeye_client.BirdeyeClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_historical_price.return_value = (Decimal("145.0"), {"historical": True})
            mock_client_class.return_value = mock_client
            
            result = await get_birdeye_price(SOL_MINT, USDC_MINT, timestamp)
            
            assert result is not None
            price, source, metadata = result
            assert price == Decimal("145.0")
            assert source == "birdeye_historical"
            assert metadata == {"historical": True}
    
    @pytest.mark.asyncio
    async def test_get_market_cap_from_birdeye(self):
        """Test convenience function for market cap"""
        with patch('src.lib.birdeye_client.BirdeyeClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_token_market_data.return_value = {
                "marketCap": 86000000000,
                "price": 150.0
            }
            mock_client_class.return_value = mock_client
            
            result = await get_market_cap_from_birdeye(SOL_MINT)
            
            assert result is not None
            market_cap, source = result
            assert market_cap == 86000000000
            assert source == "birdeye_mc"
    
    def test_client_stats(self):
        """Test client statistics"""
        client = BirdeyeClient()
        client.request_count = 5
        
        stats = client.get_stats()
        assert stats["request_count"] == 5
        assert "api_key_set" in stats
        assert stats["base_url"] == "https://public-api.birdeye.so"


if __name__ == "__main__":
    # Run basic tests
    print("Testing BirdeyeClient...")
    
    async def run_tests():
        test = TestBirdeyeClient()
        
        # Create mocks manually
        mock_session = MagicMock()
        mock_session.get = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.json = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        
        # Test successful price fetch
        await test.test_get_token_price_success(mock_session, mock_response)
        print("✅ Token price fetch test passed")
        
        # Test historical price
        await test.test_get_historical_price_success(mock_session, mock_response)
        print("✅ Historical price test passed")
        
        # Test market data
        await test.test_get_token_market_data_success(mock_session, mock_response)
        print("✅ Market data test passed")
    
    asyncio.run(run_tests())
    
    print("\n✅ All basic tests passed!")
    print("\nRun 'pytest tests/test_birdeye_client.py -v' for full test suite") 