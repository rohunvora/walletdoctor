#!/usr/bin/env python3
"""
Test suite for enhanced position cache with eviction and refresh
WAL-607: Tests for cache eviction, staleness marking, and lazy refresh
"""

import asyncio
import time
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.lib.position_cache_v2 import PositionCacheV2, InMemoryLRUCache, get_position_cache_v2
from src.lib.position_models import Position, PositionPnL, PositionSnapshot, PriceConfidence
from src.lib.cost_basis_calculator import CostBasisMethod


@pytest.fixture
def mock_time():
    """Mock time for deterministic testing"""
    current_time = 1000.0  # Start at 1000 seconds
    
    def time_provider():
        nonlocal current_time
        return current_time
    
    def advance_time(seconds):
        nonlocal current_time
        current_time += seconds
    
    time_provider.advance = advance_time
    return time_provider


@pytest.fixture
def test_position():
    """Create a test position"""
    return Position(
        position_id="wallet1:token1:1000",
        wallet="wallet1",
        token_mint="token1",
        token_symbol="TEST",
        balance=Decimal("100"),
        cost_basis=Decimal("1.0"),
        cost_basis_usd=Decimal("100"),
        decimals=9,
        opened_at=datetime.utcnow(),
        last_trade_at=datetime.utcnow()
    )


@pytest.fixture
def test_position_pnl(test_position):
    """Create a test position with P&L"""
    return PositionPnL(
        position=test_position,
        current_price_usd=Decimal("1.5"),
        current_value_usd=Decimal("150"),
        unrealized_pnl_usd=Decimal("50"),
        unrealized_pnl_pct=Decimal("50"),
        price_confidence=PriceConfidence.HIGH,
        last_price_update=datetime.utcnow(),
        price_source="test",
        price_age_seconds=60
    )


@pytest.fixture
def test_snapshot(test_position_pnl):
    """Create a test portfolio snapshot"""
    return PositionSnapshot(
        wallet="wallet1",
        timestamp=datetime.utcnow(),
        positions=[test_position_pnl],
        total_value_usd=Decimal("150"),
        total_unrealized_pnl_usd=Decimal("50"),
        total_unrealized_pnl_pct=Decimal("50")
    )


class TestInMemoryLRUCache:
    """Test LRU cache implementation"""
    
    def test_basic_get_set(self, mock_time):
        """Test basic get/set operations"""
        cache = InMemoryLRUCache(max_size=10)
        
        # Set value
        cache.set("key1", "value1", 300, now=mock_time())
        
        # Get value - should be fresh
        result = cache.get("key1", now=mock_time())
        assert result is not None
        value, is_stale = result
        assert value == "value1"
        assert is_stale is False
    
    def test_staleness_detection(self, mock_time):
        """Test staleness detection based on age"""
        cache = InMemoryLRUCache(max_size=10)
        
        # Set value
        cache.set("key1", "value1", 1800, now=mock_time())  # 30 min TTL
        
        # Check fresh
        result = cache.get("key1", now=mock_time())
        assert result is not None
        value, is_stale = result
        assert is_stale is False
        
        # Advance time past staleness threshold (15 min)
        mock_time.advance(901)  # 15 min + 1 sec
        
        # Check stale
        result = cache.get("key1", now=mock_time())
        assert result is not None
        value, is_stale = result
        assert value == "value1"
        assert is_stale is True
    
    def test_expiry(self, mock_time):
        """Test TTL expiry"""
        cache = InMemoryLRUCache(max_size=10)
        
        # Set value with 5 min TTL
        cache.set("key1", "value1", 300, now=mock_time())
        
        # Advance time past TTL
        mock_time.advance(301)
        
        # Should be expired
        result = cache.get("key1", now=mock_time())
        assert result is None
    
    def test_lru_eviction(self, mock_time):
        """Test LRU eviction when max size reached"""
        cache = InMemoryLRUCache(max_size=3)
        
        # Fill cache
        cache.set("key1", "value1", 300, now=mock_time())
        cache.set("key2", "value2", 300, now=mock_time())
        cache.set("key3", "value3", 300, now=mock_time())
        
        assert len(cache.cache) == 3
        assert cache.evictions == 0
        
        # Add one more - should evict key1 (oldest)
        cache.set("key4", "value4", 300, now=mock_time())
        
        assert len(cache.cache) == 3
        assert cache.evictions == 1
        assert cache.get("key1", now=mock_time()) is None
        assert cache.get("key2", now=mock_time()) is not None
    
    def test_lru_ordering(self, mock_time):
        """Test LRU ordering on access"""
        cache = InMemoryLRUCache(max_size=3)
        
        # Fill cache
        cache.set("key1", "value1", 300, now=mock_time())
        cache.set("key2", "value2", 300, now=mock_time())
        cache.set("key3", "value3", 300, now=mock_time())
        
        # Access key1 - moves to end
        cache.get("key1", now=mock_time())
        
        # Add key4 - should evict key2 (now oldest)
        cache.set("key4", "value4", 300, now=mock_time())
        
        assert cache.get("key1", now=mock_time()) is not None
        assert cache.get("key2", now=mock_time()) is None
        assert cache.get("key3", now=mock_time()) is not None
        assert cache.get("key4", now=mock_time()) is not None
    
    def test_delete_pattern(self, mock_time):
        """Test pattern-based deletion"""
        cache = InMemoryLRUCache(max_size=10)
        
        # Add various keys
        cache.set("pos:v1:position:wallet1:token1", "data1", 300, now=mock_time())
        cache.set("pos:v1:position:wallet1:token2", "data2", 300, now=mock_time())
        cache.set("pos:v1:position:wallet2:token1", "data3", 300, now=mock_time())
        cache.set("pos:v1:snapshot:wallet1", "data4", 300, now=mock_time())
        
        # Delete wallet1 pattern
        count = cache.delete_pattern("pos:v1:*:wallet1*")
        assert count == 3  # Should delete 3 wallet1 entries
        
        # Only wallet2 should remain
        assert cache.get("pos:v1:position:wallet2:token1", now=mock_time()) is not None
        assert cache.get("pos:v1:position:wallet1:token1", now=mock_time()) is None


@pytest.mark.asyncio
class TestPositionCacheV2:
    """Test enhanced position cache with staleness and refresh"""
    
    async def test_feature_flag_disabled(self, mock_time):
        """Test cache behavior when disabled"""
        with patch.dict(os.environ, {"POSITION_CACHE_ENABLED": "false"}):
            cache = PositionCacheV2(use_redis=False, now_provider=mock_time)
            
            assert cache.enabled is False
            
            # All operations should return None/0
            result = await cache.get_position("wallet1", "token1")
            assert result is None
            
            test_position = Position(
                position_id="test",
                wallet="wallet1",
                token_mint="token1",
                token_symbol="TEST",
                balance=Decimal("100"),
                cost_basis=Decimal("1"),
                cost_basis_usd=Decimal("100"),
                decimals=9
            )
            
            success = await cache.set_position(test_position)
            assert success is False
    
    async def test_position_get_set_with_staleness(self, mock_time, test_position):
        """Test position caching with staleness detection"""
        cache = PositionCacheV2(use_redis=False, now_provider=mock_time)
        
        # Set position
        success = await cache.set_position(test_position)
        assert success is True
        
        # Get fresh position
        result = await cache.get_position("wallet1", "token1", trigger_refresh=False)
        assert result is not None
        position, is_stale = result
        assert position.token_mint == "token1"
        assert is_stale is False
        
        # Advance time to make it stale
        mock_time.advance(901)  # 15 min + 1 sec
        
        # Get stale position
        result = await cache.get_position("wallet1", "token1", trigger_refresh=False)
        assert result is not None
        position, is_stale = result
        assert position.token_mint == "token1"
        assert is_stale is True
        
        # Check metrics
        metrics = cache.get_metrics()
        assert metrics["position_cache_hits"] == 2
        assert metrics["position_cache_stale_serves"] == 1
    
    async def test_refresh_trigger(self, mock_time, test_position):
        """Test background refresh triggering"""
        cache = PositionCacheV2(use_redis=False, now_provider=mock_time)
        
        # Set position
        await cache.set_position(test_position)
        
        # Advance time to make stale
        mock_time.advance(901)
        
        # Get with refresh trigger
        result = await cache.get_position("wallet1", "token1", trigger_refresh=True)
        assert result is not None
        _, is_stale = result
        assert is_stale is True
        
        # Check refresh was triggered
        assert len(cache.refresh_tasks) == 1
        assert "wallet1:token1" in cache.refresh_tasks
        
        # Wait for refresh task to complete
        await asyncio.sleep(0.1)
        
        # Task should be cleaned up
        assert len(cache.refresh_tasks) == 0
        
        # Check metrics
        metrics = cache.get_metrics()
        assert metrics["position_cache_refresh_triggers"] == 1
    
    async def test_portfolio_snapshot_staleness(self, mock_time, test_snapshot):
        """Test portfolio snapshot with staleness"""
        cache = PositionCacheV2(use_redis=False, now_provider=mock_time)
        
        # Set snapshot
        success = await cache.set_portfolio_snapshot(test_snapshot)
        assert success is True
        
        # Get fresh snapshot
        result = await cache.get_portfolio_snapshot("wallet1", trigger_refresh=False)
        assert result is not None
        snapshot, is_stale = result
        assert snapshot.wallet == "wallet1"
        assert is_stale is False
        
        # Advance time
        mock_time.advance(901)
        
        # Get stale snapshot
        result = await cache.get_portfolio_snapshot("wallet1", trigger_refresh=True)
        assert result is not None
        snapshot, is_stale = result
        assert is_stale is True
        
        # Check refresh was triggered
        assert "wallet1" in cache.refresh_tasks
    
    async def test_wallet_invalidation(self, mock_time):
        """Test invalidating all wallet data"""
        cache = PositionCacheV2(use_redis=False, now_provider=mock_time)
        
        # Add multiple entries for wallet
        positions = [
            Position(
                position_id=f"wallet1:token{i}:1000",
                wallet="wallet1",
                token_mint=f"token{i}",
                token_symbol=f"TEST{i}",
                balance=Decimal("100"),
                cost_basis=Decimal("1"),
                cost_basis_usd=Decimal("100"),
                decimals=9
            )
            for i in range(3)
        ]
        
        for pos in positions:
            await cache.set_position(pos)
        
        # Also add a snapshot
        snapshot = PositionSnapshot(
            wallet="wallet1",
            timestamp=datetime.utcnow(),
            positions=[],
            total_value_usd=Decimal("0"),
            total_unrealized_pnl_usd=Decimal("0"),
            total_unrealized_pnl_pct=Decimal("0")
        )
        await cache.set_portfolio_snapshot(snapshot)
        
        # Verify all cached
        for i in range(3):
            result = await cache.get_position("wallet1", f"token{i}")
            assert result is not None
        
        # Invalidate wallet
        count = await cache.invalidate_wallet("wallet1")
        assert count >= 4  # 3 positions + 1 snapshot
        
        # Verify all cleared
        for i in range(3):
            result = await cache.get_position("wallet1", f"token{i}")
            assert result is None
    
    async def test_metrics_tracking(self, mock_time, test_position):
        """Test comprehensive metrics tracking"""
        cache = PositionCacheV2(use_redis=False, now_provider=mock_time)
        
        # Generate some activity
        await cache.set_position(test_position)
        await cache.get_position("wallet1", "token1")  # Hit
        await cache.get_position("wallet1", "token2")  # Miss
        
        # Make stale and trigger refresh
        mock_time.advance(901)
        await cache.get_position("wallet1", "token1", trigger_refresh=True)  # Stale hit
        
        # Get metrics
        metrics = cache.get_metrics()
        assert metrics["position_cache_hits"] == 2
        assert metrics["position_cache_misses"] == 1
        assert metrics["position_cache_stale_serves"] == 1
        assert metrics["position_cache_refresh_triggers"] == 1
        
        # Fill cache to trigger evictions
        cache.lru_cache.max_size = 3
        for i in range(5):
            pos = Position(
                position_id=f"wallet{i}:token:1000",
                wallet=f"wallet{i}",
                token_mint="token",
                token_symbol="TEST",
                balance=Decimal("100"),
                cost_basis=Decimal("1"),
                cost_basis_usd=Decimal("100"),
                decimals=9
            )
            await cache.set_position(pos)
        
        # Check evictions
        metrics = cache.get_metrics()
        assert metrics["position_cache_evictions"] >= 2
    
    async def test_cache_stats(self, mock_time):
        """Test detailed cache statistics"""
        with patch.dict(os.environ, {
            "POSITION_CACHE_TTL_SEC": "600",
            "POSITION_CACHE_MAX": "1500"
        }):
            cache = PositionCacheV2(use_redis=False, now_provider=mock_time)
            
            # Generate some activity
            for i in range(5):
                pos = Position(
                    position_id=f"wallet1:token{i}:1000",
                    wallet="wallet1",
                    token_mint=f"token{i}",
                    token_symbol=f"TEST{i}",
                    balance=Decimal("100"),
                    cost_basis=Decimal("1"),
                    cost_basis_usd=Decimal("100"),
                    decimals=9
                )
                await cache.set_position(pos)
            
            # Get some hits and misses
            await cache.get_position("wallet1", "token0")  # Hit
            await cache.get_position("wallet1", "token1")  # Hit
            await cache.get_position("wallet1", "token99")  # Miss
            
            stats = cache.get_stats()
            
            # Check structure
            assert stats["enabled"] is True
            assert stats["backend"] == "in-memory"
            assert stats["hit_rate_pct"] == pytest.approx(66.67, 0.1)
            assert stats["total_requests"] == 3
            assert stats["lru_size"] == 5
            assert stats["lru_max_size"] == 1500
            assert stats["config"]["ttl_seconds"] == 600
            assert stats["config"]["max_wallets"] == 1500
            
            # Check metrics included
            assert "position_cache_hits" in stats
            assert "position_cache_misses" in stats
    
    async def test_global_instance(self):
        """Test global cache instance creation"""
        cache1 = get_position_cache_v2()
        cache2 = get_position_cache_v2()
        
        # Should be same instance
        assert cache1 is cache2
        
        # Should be enabled by default
        assert cache1.enabled is True


@pytest.mark.asyncio
class TestCacheIntegration:
    """Integration tests with real Redis-like scenarios"""
    
    async def test_concurrent_access(self, mock_time, test_position):
        """Test concurrent access patterns"""
        cache = PositionCacheV2(use_redis=False, now_provider=mock_time)
        
        # Simulate concurrent writes
        tasks = []
        for i in range(10):
            pos = Position(
                position_id=f"wallet1:token{i}:1000",
                wallet="wallet1",
                token_mint=f"token{i}",
                token_symbol=f"TEST{i}",
                balance=Decimal(str(i * 100)),
                cost_basis=Decimal("1"),
                cost_basis_usd=Decimal(str(i * 100)),
                decimals=9
            )
            tasks.append(cache.set_position(pos))
        
        results = await asyncio.gather(*tasks)
        assert all(results)
        
        # Simulate concurrent reads
        tasks = []
        for i in range(10):
            tasks.append(cache.get_position("wallet1", f"token{i}"))
        
        results = await asyncio.gather(*tasks)
        assert all(r is not None for r in results)
    
    async def test_performance_benchmark(self, mock_time):
        """Test cache performance meets requirements"""
        cache = PositionCacheV2(use_redis=False, now_provider=mock_time)
        
        # Prepare test data
        positions = []
        for i in range(50):  # 50 positions
            pos = Position(
                position_id=f"wallet1:token{i}:1000",
                wallet="wallet1",
                token_mint=f"token{i}",
                token_symbol=f"TEST{i}",
                balance=Decimal("100"),
                cost_basis=Decimal("1"),
                cost_basis_usd=Decimal("100"),
                decimals=9
            )
            positions.append(pos)
        
        # Benchmark writes
        start = time.time()
        for pos in positions:
            await cache.set_position(pos)
        write_time = time.time() - start
        
        # Benchmark reads
        start = time.time()
        for i in range(50):
            await cache.get_position("wallet1", f"token{i}")
        read_time = time.time() - start
        
        # Check performance
        # P95 should be < 120ms for /v4/positions
        # This tests just the cache layer
        avg_read_ms = (read_time / 50) * 1000
        assert avg_read_ms < 10  # Cache reads should be < 10ms average
        
        print(f"Cache performance: {avg_read_ms:.2f}ms avg read, {write_time*1000:.2f}ms total write")


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 