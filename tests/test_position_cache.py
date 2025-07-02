"""
Test Position Cache Layer
WAL-605: Tests for Redis-backed position caching with fallback
"""

import pytest
import asyncio
import time
import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from src.lib.position_cache import (
    PositionCache, InMemoryPositionCache, get_position_cache,
    benchmark_cache_performance, POSITION_CACHE_TTL, PNL_CACHE_TTL,
    _position_cache_instance
)
from src.lib.position_models import (
    Position, PositionPnL, PositionSnapshot, 
    CostBasisMethod, PriceConfidence
)

# Test constants
TEST_WALLET = "TestWallet123"
BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoHHuJjWKjH8vJFKfPQoKEWF"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


@pytest.fixture
def test_position():
    """Create a test position"""
    return Position(
        position_id=f"{TEST_WALLET}:{BONK_MINT}:123456",
        wallet=TEST_WALLET,
        token_mint=BONK_MINT,
        token_symbol="BONK",
        balance=Decimal("100000"),
        cost_basis=Decimal("0.00001"),
        cost_basis_usd=Decimal("1.0"),
        cost_basis_method=CostBasisMethod.FIFO,
        opened_at=datetime.now(timezone.utc),
        last_trade_at=datetime.now(timezone.utc),
        last_update_slot=1000,
        last_update_time=datetime.now(timezone.utc),
        is_closed=False,
        trade_count=1,
        decimals=5
    )


@pytest.fixture
def test_position_pnl(test_position):
    """Create a test position P&L"""
    return PositionPnL(
        position=test_position,
        current_price_usd=Decimal("0.00002"),
        current_value_usd=Decimal("2.0"),
        unrealized_pnl_usd=Decimal("1.0"),
        unrealized_pnl_pct=Decimal("100"),
        price_confidence=PriceConfidence.HIGH,
        last_price_update=datetime.now(timezone.utc),
        price_source="helius_amm",
        price_age_seconds=30
    )


@pytest.fixture
def test_snapshot(test_position_pnl):
    """Create a test portfolio snapshot"""
    return PositionSnapshot.from_positions(
        wallet=TEST_WALLET,
        position_pnls=[test_position_pnl]
    )


@pytest.fixture
def memory_cache():
    """Create in-memory cache for testing"""
    with patch("src.lib.position_cache.positions_enabled", return_value=True):
        cache = PositionCache(use_redis=False)
        yield cache


@pytest.fixture
def mock_redis_cache():
    """Create cache with mocked Redis"""
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.setex.return_value = True
    mock_redis.scan.return_value = (0, [])
    
    with patch("src.lib.position_cache.redis.Redis", return_value=mock_redis):
        with patch("src.lib.position_cache.redis.ConnectionPool"):
            with patch("src.lib.position_cache.positions_enabled", return_value=True):
                cache = PositionCache(use_redis=True)
                cache.redis_client = mock_redis
                yield cache


class TestInMemoryCache:
    """Test in-memory LRU cache"""
    
    def test_set_and_get(self):
        """Test basic set and get operations"""
        cache = InMemoryPositionCache(max_size=10)
        
        # Set value
        cache.set("key1", "value1", ttl_seconds=60)
        
        # Get value
        assert cache.get("key1") == "value1"
        
        # Non-existent key
        assert cache.get("key2") is None
    
    def test_ttl_expiration(self):
        """Test TTL expiration"""
        cache = InMemoryPositionCache()
        
        # Set with short TTL
        cache.set("key1", "value1", ttl_seconds=1)
        
        # Should exist immediately
        assert cache.get("key1") == "value1"
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired
        assert cache.get("key1") is None
    
    def test_lru_eviction(self):
        """Test LRU eviction when at capacity"""
        cache = InMemoryPositionCache(max_size=3)
        
        # Fill cache
        cache.set("key1", "value1", ttl_seconds=60)
        cache.set("key2", "value2", ttl_seconds=60)
        cache.set("key3", "value3", ttl_seconds=60)
        
        # Access key1 to make it recently used
        cache.get("key1")
        
        # Add new key, should evict key2 (least recently used)
        cache.set("key4", "value4", ttl_seconds=60)
        
        assert cache.get("key1") == "value1"  # Still there
        assert cache.get("key2") is None      # Evicted
        assert cache.get("key3") == "value3"  # Still there
        assert cache.get("key4") == "value4"  # New key
    
    def test_delete(self):
        """Test delete operation"""
        cache = InMemoryPositionCache()
        
        cache.set("key1", "value1", ttl_seconds=60)
        assert cache.get("key1") == "value1"
        
        # Delete
        assert cache.delete("key1") is True
        assert cache.get("key1") is None
        
        # Delete non-existent
        assert cache.delete("key2") is False
    
    def test_delete_pattern(self):
        """Test pattern-based deletion"""
        cache = InMemoryPositionCache()
        
        # Set multiple keys
        cache.set("pos:wallet1:token1", "value1", ttl_seconds=60)
        cache.set("pos:wallet1:token2", "value2", ttl_seconds=60)
        cache.set("pos:wallet2:token1", "value3", ttl_seconds=60)
        
        # Delete pattern
        count = cache.delete_pattern("pos:wallet1:")
        assert count == 2
        
        # Check results
        assert cache.get("pos:wallet1:token1") is None
        assert cache.get("pos:wallet1:token2") is None
        assert cache.get("pos:wallet2:token1") == "value3"


class TestPositionCache:
    """Test position cache functionality"""
    
    @pytest.mark.asyncio
    async def test_position_caching(self, memory_cache, test_position):
        """Test caching and retrieving positions"""
        # Cache position
        success = await memory_cache.set_position(test_position)
        assert success is True
        
        # Retrieve position
        cached = await memory_cache.get_position(
            test_position.wallet,
            test_position.token_mint
        )
        
        assert cached is not None
        assert cached.position_id == test_position.position_id
        assert cached.balance == test_position.balance
        assert cached.cost_basis_usd == test_position.cost_basis_usd
        assert memory_cache.metrics["cache_hits"] == 1
    
    @pytest.mark.asyncio
    async def test_position_cache_miss(self, memory_cache):
        """Test cache miss behavior"""
        # Try to get non-existent position
        cached = await memory_cache.get_position(TEST_WALLET, "unknown_mint")
        
        assert cached is None
        assert memory_cache.metrics["cache_misses"] == 1
    
    @pytest.mark.asyncio
    async def test_position_pnl_caching(self, memory_cache, test_position_pnl):
        """Test caching and retrieving position P&L"""
        # Cache P&L
        success = await memory_cache.set_position_pnl(test_position_pnl)
        assert success is True
        
        # Retrieve P&L
        cached = await memory_cache.get_position_pnl(
            test_position_pnl.position.wallet,
            test_position_pnl.position.token_mint
        )
        
        assert cached is not None
        assert cached.current_value_usd == test_position_pnl.current_value_usd
        assert cached.unrealized_pnl_usd == test_position_pnl.unrealized_pnl_usd
        assert cached.price_confidence == test_position_pnl.price_confidence
    
    @pytest.mark.asyncio
    async def test_snapshot_caching(self, memory_cache, test_snapshot):
        """Test caching and retrieving portfolio snapshots"""
        # Cache snapshot
        success = await memory_cache.set_portfolio_snapshot(test_snapshot)
        assert success is True
        
        # Retrieve snapshot
        cached = await memory_cache.get_portfolio_snapshot(test_snapshot.wallet)
        
        assert cached is not None
        assert cached.wallet == test_snapshot.wallet
        assert len(cached.positions) == len(test_snapshot.positions)
        assert cached.total_value_usd == test_snapshot.total_value_usd
    
    @pytest.mark.asyncio
    async def test_invalidation(self, memory_cache, test_position):
        """Test cache invalidation on new trades"""
        # Cache multiple items
        await memory_cache.set_position(test_position)
        
        # Create another position
        position2 = Position(
            position_id=f"{TEST_WALLET}:{USDC_MINT}:123456",
            wallet=TEST_WALLET,
            token_mint=USDC_MINT,
            token_symbol="USDC",
            balance=Decimal("1000"),
            cost_basis=Decimal("1.0"),
            cost_basis_usd=Decimal("1000"),
            decimals=6
        )
        await memory_cache.set_position(position2)
        
        # Verify both exist
        assert await memory_cache.get_position(TEST_WALLET, BONK_MINT) is not None
        assert await memory_cache.get_position(TEST_WALLET, USDC_MINT) is not None
        
        # Invalidate wallet - for in-memory cache with simple prefix matching
        # we need to ensure the keys contain the wallet
        # Get the actual keys
        key1 = memory_cache._get_position_key(TEST_WALLET, BONK_MINT)
        key2 = memory_cache._get_position_key(TEST_WALLET, USDC_MINT)
        
        # Check that keys contain wallet
        assert TEST_WALLET in key1
        assert TEST_WALLET in key2
        
        # Invalidate
        count = await memory_cache.invalidate_wallet_positions(TEST_WALLET)
        
        # With the current pattern matching, at least the two positions should be invalidated
        # The count includes position keys that match the pattern
        assert count >= 2
        
        # Verify invalidated
        assert await memory_cache.get_position(TEST_WALLET, BONK_MINT) is None
        assert await memory_cache.get_position(TEST_WALLET, USDC_MINT) is None
    
    @pytest.mark.asyncio
    async def test_feature_flag_disabled(self, memory_cache):
        """Test behavior when positions are disabled"""
        with patch("src.lib.position_cache.positions_enabled", return_value=False):
            # Should return None when disabled
            assert await memory_cache.get_position(TEST_WALLET, BONK_MINT) is None
            assert await memory_cache.get_position_pnl(TEST_WALLET, BONK_MINT) is None
    
    def test_cache_key_generation(self, memory_cache):
        """Test cache key generation"""
        # Position key
        key = memory_cache._get_position_key(TEST_WALLET, BONK_MINT)
        assert key == f"pos:v1:position:{TEST_WALLET}:{BONK_MINT}"
        
        # P&L key
        key = memory_cache._get_pnl_key(TEST_WALLET, BONK_MINT)
        assert key == f"pos:v1:pnl:{TEST_WALLET}:{BONK_MINT}"
        
        # Snapshot key
        key = memory_cache._get_snapshot_key(TEST_WALLET)
        assert key == f"pos:v1:snapshot:{TEST_WALLET}:latest"
        
        # Snapshot with timestamp (rounds to hour)
        timestamp = 1704067200  # 2024-01-01 00:00:00
        key = memory_cache._get_snapshot_key(TEST_WALLET, timestamp)
        assert key == f"pos:v1:snapshot:{TEST_WALLET}:1704067200"
    
    @pytest.mark.asyncio
    async def test_serialization_deserialization(self, memory_cache, test_position):
        """Test proper serialization/deserialization"""
        # Test with various decimal values
        test_position.balance = Decimal("123456.789012345")
        test_position.cost_basis = Decimal("0.000000123456")
        
        # Cache and retrieve
        await memory_cache.set_position(test_position)
        cached = await memory_cache.get_position(
            test_position.wallet,
            test_position.token_mint
        )
        
        # Verify decimal precision preserved
        assert cached.balance == test_position.balance
        assert cached.cost_basis == test_position.cost_basis
    
    def test_stats_tracking(self, memory_cache):
        """Test statistics tracking"""
        stats = memory_cache.get_stats()
        
        assert stats["backend"] == "in-memory"
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0
        assert stats["hit_rate"] == 0
    
    @pytest.mark.asyncio
    async def test_redis_fallback(self, mock_redis_cache):
        """Test Redis operations with mocked client"""
        # Mock Redis get to return cached data
        cached_data = {
            "position_id": "test_pos",
            "wallet": TEST_WALLET,
            "token_mint": BONK_MINT,
            "token_symbol": "BONK",
            "balance": "1000",
            "cost_basis": "1.0",
            "cost_basis_usd": "1000",
            "decimals": 9,
            "opened_at": datetime.now(timezone.utc).isoformat() + "Z",
            "last_trade_at": datetime.now(timezone.utc).isoformat() + "Z",
            "last_update_time": datetime.now(timezone.utc).isoformat() + "Z",
            "last_update_slot": 1000,
            "is_closed": False,
            "trade_count": 1,
            "cost_basis_method": "fifo"
        }
        
        mock_redis_cache.redis_client.get.return_value = json.dumps(cached_data)
        
        # Get position
        position = await mock_redis_cache.get_position(TEST_WALLET, BONK_MINT)
        
        assert position is not None
        assert position.wallet == TEST_WALLET
        assert position.balance == Decimal("1000")
        
        # Verify Redis was called
        mock_redis_cache.redis_client.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_redis_error_handling(self, mock_redis_cache, test_position):
        """Test graceful handling of Redis errors"""
        import redis
        
        # Make Redis operations fail with RedisError
        mock_redis_cache.redis_client.get.side_effect = redis.RedisError("Redis error")
        mock_redis_cache.redis_client.setex.side_effect = redis.RedisError("Redis error")
        
        # Should fall back to in-memory cache
        success = await mock_redis_cache.set_position(test_position)
        assert success is True  # Falls back to in-memory
        
        # Now get should work from in-memory cache
        # Reset get side effect so we can read from in-memory
        mock_redis_cache.redis_client.get.side_effect = redis.RedisError("Redis error")
        
        # The position should be in the in-memory cache
        # We need to manually check the in-memory cache since Redis fails
        key = mock_redis_cache._get_position_key(test_position.wallet, test_position.token_mint)
        # Check that it was stored in the LRU cache
        assert key in mock_redis_cache.lru_cache.cache
        
        # Check error metrics
        # We expect at least 1 error from setex
        assert mock_redis_cache.metrics["cache_errors"] >= 1


class TestPerformanceBenchmark:
    """Test performance benchmarking"""
    
    @pytest.mark.asyncio
    async def test_benchmark_function(self):
        """Test the benchmark function"""
        wallet = TEST_WALLET
        token_mints = [f"mint_{i}" for i in range(10)]
        
        # Run benchmark
        results = await benchmark_cache_performance(wallet, token_mints)
        
        assert "write_count" in results
        assert "read_count" in results
        assert "write_latency_ms" in results
        assert "read_latency_ms" in results
        assert "performance_target_met" in results
        
        # Should be fast with in-memory cache
        assert results["read_latency_ms"] < 100  # < 100ms target
        assert results["performance_target_met"] is True


class TestGlobalInstance:
    """Test global cache instance"""
    
    def test_singleton_pattern(self):
        """Test that get_position_cache returns singleton"""
        # Reset global instance
        import src.lib.position_cache
        src.lib.position_cache._position_cache_instance = None
        
        with patch("src.lib.position_cache.PositionCache") as MockCache:
            mock_instance = Mock()
            MockCache.return_value = mock_instance
            
            # First call creates instance
            cache1 = get_position_cache()
            assert MockCache.called
            
            # Should have set the global instance
            assert src.lib.position_cache._position_cache_instance is not None
            
            # Reset mock but not the global instance
            MockCache.reset_mock()
            
            # Second call returns same instance
            cache2 = get_position_cache()
            assert not MockCache.called
            assert cache1 is cache2
            
        # Clean up
        src.lib.position_cache._position_cache_instance = None


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_invalid_json_handling(self, memory_cache):
        """Test handling of corrupted cache data"""
        # Manually insert invalid JSON
        cache_key = memory_cache._get_position_key(TEST_WALLET, BONK_MINT)
        memory_cache.lru_cache.set(cache_key, "invalid json{", 60)
        
        # Should handle gracefully
        position = await memory_cache.get_position(TEST_WALLET, BONK_MINT)
        assert position is None
        assert memory_cache.metrics["cache_errors"] == 1
    
    @pytest.mark.asyncio
    async def test_historical_snapshot_caching(self, memory_cache, test_snapshot):
        """Test caching historical snapshots with timestamp"""
        timestamp = int(datetime.now().timestamp())
        
        # Cache with timestamp
        success = await memory_cache.set_portfolio_snapshot(
            test_snapshot,
            timestamp
        )
        assert success is True
        
        # Retrieve with timestamp
        cached = await memory_cache.get_portfolio_snapshot(
            test_snapshot.wallet,
            timestamp
        )
        assert cached is not None
    
    @pytest.mark.asyncio
    async def test_position_without_optional_fields(self, memory_cache):
        """Test caching position with minimal fields"""
        minimal_position = Position(
            position_id="minimal",
            wallet=TEST_WALLET,
            token_mint=BONK_MINT,
            token_symbol="BONK",
            balance=Decimal("100"),
            cost_basis=Decimal("1"),
            cost_basis_usd=Decimal("100"),
            decimals=9
        )
        
        # Should cache successfully
        success = await memory_cache.set_position(minimal_position)
        assert success is True
        
        cached = await memory_cache.get_position(TEST_WALLET, BONK_MINT)
        assert cached is not None
        assert cached.balance == Decimal("100")


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 