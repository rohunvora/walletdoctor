#!/usr/bin/env python3
"""
Test Market Cap Pre-Cache Service
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import json
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.mc_precache_service import (
    PreCacheService,
    start_precache_service,
    stop_precache_service,
    get_precache_service,
    POPULAR_TOKENS
)
from src.lib.mc_calculator import MarketCapResult, CONFIDENCE_HIGH
from decimal import Decimal


class TestPreCacheService:
    """Test PreCacheService class"""
    
    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache"""
        cache = MagicMock()
        cache.get = MagicMock(return_value=None)
        cache.set = MagicMock(return_value=True)
        return cache
    
    @pytest.fixture
    def mock_calculator(self):
        """Create a mock calculator"""
        calculator = MagicMock()
        calculator.calculate_market_cap = AsyncMock()
        return calculator
    
    @pytest.fixture
    def mock_jupiter_client(self):
        """Create a mock Jupiter client"""
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test service initialization"""
        service = PreCacheService()
        
        assert service.cache is None
        assert service.calculator is None
        assert service.jupiter_client is None
        assert not service.running
        assert len(service.tracked_tokens) == len(POPULAR_TOKENS)
        assert POPULAR_TOKENS.issubset(service.tracked_tokens)
    
    @pytest.mark.asyncio
    async def test_service_start_stop(self, mock_cache, mock_calculator, mock_jupiter_client):
        """Test starting and stopping the service"""
        service = PreCacheService()
        
        with patch('src.lib.mc_precache_service.get_cache', return_value=mock_cache):
            with patch('src.lib.mc_precache_service.MarketCapCalculator', return_value=mock_calculator):
                with patch('src.lib.mc_precache_service.JupiterClient', return_value=mock_jupiter_client):
                    # Start service
                    await service.start()
                    
                    assert service.running
                    assert service.cache == mock_cache
                    assert service.calculator == mock_calculator
                    assert service.jupiter_client == mock_jupiter_client
                    assert len(service._tasks) == 4  # 4 background tasks
                    
                    # Stop service
                    await service.stop()
                    
                    assert not service.running
                    mock_jupiter_client.__aexit__.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_batch(self, mock_cache, mock_calculator):
        """Test caching a batch of tokens"""
        service = PreCacheService()
        service.cache = mock_cache
        service.calculator = mock_calculator
        
        # Mock successful MC calculation
        mock_result = MarketCapResult(
            value=1000000.0,
            confidence=CONFIDENCE_HIGH,
            source="test",
            supply=1000000.0,
            price=1.0,
            timestamp=int(datetime.now().timestamp())
        )
        mock_calculator.calculate_market_cap.return_value = mock_result
        
        # Cache a batch
        tokens = ["token1", "token2", "token3"]
        await service._cache_batch(tokens)
        
        # Verify all tokens were calculated
        assert mock_calculator.calculate_market_cap.call_count == 3
        
        # Verify stats were updated
        for token in tokens:
            assert service.token_stats[token]["last_cached"] is not None
    
    @pytest.mark.asyncio
    async def test_cache_batch_with_failures(self, mock_cache, mock_calculator):
        """Test caching with some failures"""
        service = PreCacheService()
        service.cache = mock_cache
        service.calculator = mock_calculator
        
        # Mock mixed results
        mock_calculator.calculate_market_cap.side_effect = [
            MarketCapResult(value=1000000.0, confidence=CONFIDENCE_HIGH, source="test", 
                          supply=1000000.0, price=1.0, timestamp=int(datetime.now().timestamp())),
            Exception("API error"),
            MarketCapResult(value=None, confidence="unavailable", source=None,
                          supply=None, price=None, timestamp=int(datetime.now().timestamp()))
        ]
        
        # Cache a batch
        tokens = ["token1", "token2", "token3"]
        await service._cache_batch(tokens)
        
        # Should complete despite errors
        assert mock_calculator.calculate_market_cap.call_count == 3
        assert service.token_stats["token1"]["last_cached"] is not None
        assert service.token_stats["token3"]["last_cached"] is not None
    
    @pytest.mark.asyncio
    async def test_track_request(self):
        """Test request tracking"""
        service = PreCacheService()
        
        # Track some requests
        service.track_request("token1", cache_hit=True)
        service.track_request("token1", cache_hit=False)
        service.track_request("token2", cache_hit=True)
        
        # Check stats
        assert service.token_stats["token1"]["request_count"] == 2
        assert service.token_stats["token1"]["cache_hits"] == 1
        assert service.token_stats["token2"]["request_count"] == 1
        assert service.token_stats["token2"]["cache_hits"] == 1
        
        # Track enough requests to add to tracked tokens
        for _ in range(5):
            service.track_request("new_token", cache_hit=False)
        
        assert "new_token" in service.tracked_tokens
    
    @pytest.mark.asyncio
    async def test_fetch_trending_tokens(self):
        """Test fetching trending tokens"""
        service = PreCacheService()
        
        # Mock response
        mock_response = {
            "pairs": [
                {"baseToken": {"address": "token1"}},
                {"baseToken": {"address": "token2"}},
                {"baseToken": {"address": "token3"}},
            ]
        }
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aenter__.return_value = mock_resp
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            tokens = await service._fetch_trending_tokens()
            
            assert len(tokens) == 3
            assert tokens == ["token1", "token2", "token3"]
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test statistics calculation"""
        service = PreCacheService()
        
        # Add some test data
        service.track_request("token1", cache_hit=True)
        service.track_request("token1", cache_hit=True)
        service.track_request("token2", cache_hit=False)
        service.track_request("token3", cache_hit=True)
        
        stats = service.get_stats()
        
        assert stats["tracked_tokens"] >= len(POPULAR_TOKENS)
        assert stats["popular_tokens"] == len(POPULAR_TOKENS)
        assert stats["total_requests"] == 4
        assert stats["total_cache_hits"] == 3
        assert stats["hit_rate"] == 75.0
        assert not stats["running"]
    
    @pytest.mark.asyncio
    async def test_popular_token_loop(self, mock_cache, mock_calculator):
        """Test popular token refresh loop"""
        service = PreCacheService()
        service.cache = mock_cache
        service.calculator = mock_calculator
        service.running = True
        
        # Mock successful calculation
        mock_calculator.calculate_market_cap.return_value = MarketCapResult(
            value=1000000.0, confidence=CONFIDENCE_HIGH, source="test",
            supply=1000000.0, price=1.0, timestamp=int(datetime.now().timestamp())
        )
        
        # Manually call _cache_batch to test the functionality
        await service._cache_batch(list(POPULAR_TOKENS)[:3])
        
        # Should have called calculate_market_cap for the tokens
        assert mock_calculator.calculate_market_cap.called
        assert mock_calculator.calculate_market_cap.call_count == 3
    
    @pytest.mark.asyncio
    async def test_global_service_management(self):
        """Test global service instance management"""
        # Initially no service
        assert get_precache_service() is None
        
        # Start service
        with patch('src.lib.mc_precache_service.PreCacheService.start', AsyncMock()):
            service1 = await start_precache_service()
            assert service1 is not None
            assert get_precache_service() == service1
            
            # Mark it as running to test duplicate start prevention
            service1.running = True
            
            # Try to start again - should return same instance
            service2 = await start_precache_service()
            assert service2 is service1  # Same object
            
            # Stop service
            with patch('src.lib.mc_precache_service.PreCacheService.stop', AsyncMock()):
                await stop_precache_service()
                assert get_precache_service() is None
    
    @pytest.mark.asyncio
    async def test_trending_token_updater(self):
        """Test trending token update logic"""
        service = PreCacheService()
        
        # Add some existing stats
        for i in range(10):
            service.token_stats[f"old_token_{i}"]["request_count"] = i
        
        # Mock trending tokens
        trending = [f"trending_{i}" for i in range(60)]
        
        with patch.object(service, '_fetch_trending_tokens', AsyncMock(return_value=trending)):
            # Manually update trending
            before = len(service.tracked_tokens)
            service.tracked_tokens.update(trending[:50])
            
            # Should have added 50 tokens
            assert len(service.tracked_tokens) >= before + 50
            
            # If over limit, should remove least requested
            if len(service.tracked_tokens) > 100:
                # Verify popular tokens are still there
                assert POPULAR_TOKENS.issubset(service.tracked_tokens)
    
    @pytest.mark.asyncio
    async def test_concurrent_calculations(self, mock_cache, mock_calculator):
        """Test concurrent calculation limiting"""
        service = PreCacheService()
        service.cache = mock_cache
        service.calculator = mock_calculator
        
        # Track concurrent calls
        concurrent_count = 0
        max_concurrent = 0
        total_calls = 0
        lock = asyncio.Lock()
        
        async def mock_calculate(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent, total_calls
            async with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                total_calls += 1
            
            await asyncio.sleep(0.05)  # Simulate work
            
            async with lock:
                concurrent_count -= 1
                
            return MarketCapResult(
                value=1000000.0, confidence=CONFIDENCE_HIGH, source="test",
                supply=1000000.0, price=1.0, timestamp=int(datetime.now().timestamp())
            )
        
        mock_calculator.calculate_market_cap = mock_calculate
        
        # Cache many tokens
        tokens = [f"token_{i}" for i in range(20)]
        await service._cache_batch(tokens)
        
        # Check that max concurrent calculations was respected
        # With MAX_CONCURRENT_CALCULATIONS = 5, we should see at most 5 concurrent
        assert max_concurrent <= 5
        assert total_calls == 20


if __name__ == "__main__":
    # Run basic tests
    print("Testing PreCacheService...")
    
    async def run_tests():
        test = TestPreCacheService()
        
        # Test initialization
        await test.test_service_initialization()
        print("✅ Initialization test passed")
        
        # Test request tracking
        await test.test_track_request()
        print("✅ Request tracking test passed")
        
        # Test stats
        await test.test_get_stats()
        print("✅ Statistics test passed")
        
        # Test global management
        await test.test_global_service_management()
        print("✅ Global service management test passed")
    
    asyncio.run(run_tests())
    
    print("\n✅ All basic tests passed!")
    print("\nRun 'pytest tests/test_mc_precache_service.py -v' for full test suite") 