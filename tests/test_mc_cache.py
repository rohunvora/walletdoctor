#!/usr/bin/env python3
"""
Test market cap cache functionality
"""

import pytest
import time
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.mc_cache import (
    MarketCapCache, MarketCapData, InMemoryLRUCache,
    CONFIDENCE_HIGH, CONFIDENCE_EST, CONFIDENCE_UNAVAILABLE,
    CACHE_TTL_SECONDS
)


class TestMarketCapData:
    """Test MarketCapData dataclass"""
    
    def test_to_dict(self):
        """Test converting to dictionary"""
        mc_data = MarketCapData(
            value=1000000.0,
            confidence=CONFIDENCE_HIGH,
            timestamp=1234567890,
            source="raydium"
        )
        
        data_dict = mc_data.to_dict()
        assert data_dict["value"] == 1000000.0
        assert data_dict["confidence"] == CONFIDENCE_HIGH
        assert data_dict["timestamp"] == 1234567890
        assert data_dict["source"] == "raydium"
    
    def test_from_dict(self):
        """Test creating from dictionary"""
        data = {
            "value": 500000.0,
            "confidence": CONFIDENCE_EST,
            "timestamp": 1234567890,
            "source": "birdeye"
        }
        
        mc_data = MarketCapData.from_dict(data)
        assert mc_data.value == 500000.0
        assert mc_data.confidence == CONFIDENCE_EST
        assert mc_data.timestamp == 1234567890
        assert mc_data.source == "birdeye"
    
    def test_from_dict_missing_fields(self):
        """Test creating from incomplete dictionary"""
        data = {"value": None}
        
        mc_data = MarketCapData.from_dict(data)
        assert mc_data.value is None
        assert mc_data.confidence == CONFIDENCE_UNAVAILABLE
        assert mc_data.timestamp == 0
        assert mc_data.source is None


class TestInMemoryLRUCache:
    """Test in-memory LRU cache"""
    
    def test_basic_get_set(self):
        """Test basic get/set operations"""
        cache = InMemoryLRUCache(max_size=2)
        
        # Set value
        cache.set("key1", "value1", ttl_seconds=10)
        
        # Get value
        assert cache.get("key1") == "value1"
        
        # Non-existent key
        assert cache.get("key2") is None
    
    def test_lru_eviction(self):
        """Test LRU eviction when max size reached"""
        cache = InMemoryLRUCache(max_size=2)
        
        # Fill cache
        cache.set("key1", "value1", ttl_seconds=10)
        cache.set("key2", "value2", ttl_seconds=10)
        
        # Access key1 to make it recently used
        cache.get("key1")
        
        # Add third item - should evict key2
        cache.set("key3", "value3", ttl_seconds=10)
        
        assert cache.get("key1") == "value1"  # Still there
        assert cache.get("key2") is None      # Evicted
        assert cache.get("key3") == "value3"  # New item
    
    def test_ttl_expiry(self):
        """Test TTL expiration"""
        cache = InMemoryLRUCache(max_size=10)
        
        # Set with very short TTL
        cache.set("key1", "value1", ttl_seconds=1)
        
        # Should exist immediately
        assert cache.get("key1") == "value1"
        
        # Wait for expiry
        time.sleep(1.5)
        
        # Should be expired
        assert cache.get("key1") is None


class TestMarketCapCache:
    """Test main MarketCapCache class"""
    
    def test_in_memory_mode(self):
        """Test cache in in-memory only mode"""
        cache = MarketCapCache(use_redis=False)
        
        # Test data
        mint = "So11111111111111111111111111111111111111112"
        timestamp = int(time.time())
        mc_data = MarketCapData(
            value=1500000.0,
            confidence=CONFIDENCE_HIGH,
            timestamp=timestamp,
            source="orca"
        )
        
        # Store and retrieve
        assert cache.set(mint, timestamp, mc_data) is True
        retrieved = cache.get(mint, timestamp)
        
        assert retrieved is not None
        assert retrieved.value == 1500000.0
        assert retrieved.confidence == CONFIDENCE_HIGH
        assert retrieved.source == "orca"
    
    def test_cache_key_generation(self):
        """Test cache key format"""
        cache = MarketCapCache(use_redis=False)
        
        # Test key generation
        key = cache._get_cache_key(
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "2024-01-15"
        )
        assert key == "mc:v1:EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v:2024-01-15"
    
    def test_date_granularity(self):
        """Test that cache uses daily granularity"""
        cache = MarketCapCache(use_redis=False)
        
        mint = "test_mint"
        base_timestamp = 1705334400  # 2024-01-15 16:00:00
        
        # Store at specific time
        mc_data = MarketCapData(
            value=1000000.0,
            confidence=CONFIDENCE_HIGH,
            timestamp=base_timestamp,
            source="test"
        )
        cache.set(mint, base_timestamp, mc_data)
        
        # Retrieve at different time same day
        different_time = base_timestamp + 3600  # 1 hour later
        retrieved = cache.get(mint, different_time)
        
        assert retrieved is not None
        assert retrieved.value == 1000000.0
        
        # Retrieve next day - should not find
        next_day = base_timestamp + 86400  # 24 hours later
        retrieved = cache.get(mint, next_day)
        assert retrieved is None
    
    def test_batch_get(self):
        """Test batch get functionality"""
        cache = MarketCapCache(use_redis=False)
        
        # Store multiple entries
        mint1 = "mint1"
        mint2 = "mint2"
        timestamp1 = int(time.time())
        timestamp2 = timestamp1 - 86400  # Yesterday
        
        mc_data1 = MarketCapData(value=1000000.0, confidence=CONFIDENCE_HIGH, timestamp=timestamp1, source="test1")
        mc_data2 = MarketCapData(value=2000000.0, confidence=CONFIDENCE_EST, timestamp=timestamp2, source="test2")
        
        cache.set(mint1, timestamp1, mc_data1)
        cache.set(mint2, timestamp2, mc_data2)
        
        # Batch get
        requests = [
            (mint1, timestamp1),
            (mint2, timestamp2),
            ("mint3", timestamp1),  # Non-existent
        ]
        
        results = cache.batch_get(requests)
        
        assert len(results) == 3
        result1 = results[(mint1, timestamp1)]
        result2 = results[(mint2, timestamp2)]
        assert result1 is not None and result1.value == 1000000.0
        assert result2 is not None and result2.value == 2000000.0
        assert results[("mint3", timestamp1)] is None
    
    @patch('src.lib.mc_cache.redis.Redis')
    @patch('src.lib.mc_cache.redis.ConnectionPool')
    def test_redis_mode(self, mock_pool, mock_redis):
        """Test cache with Redis (mocked)"""
        # Setup mocks
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        # Create cache with Redis
        cache = MarketCapCache(use_redis=True)
        
        # Test data
        mint = "test_mint"
        timestamp = int(time.time())
        mc_data = MarketCapData(
            value=3000000.0,
            confidence=CONFIDENCE_HIGH,
            timestamp=timestamp,
            source="redis_test"
        )
        
        # Mock Redis get to return None first, then our data
        date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        cache_key = f"mc:v1:{mint}:{date}"
        
        mock_redis_instance.get.return_value = None
        mock_redis_instance.setex.return_value = True
        
        # Store
        assert cache.set(mint, timestamp, mc_data) is True
        mock_redis_instance.setex.assert_called_once_with(
            cache_key,
            CACHE_TTL_SECONDS,
            json.dumps(mc_data.to_dict())
        )
        
        # Mock get to return data
        mock_redis_instance.get.return_value = json.dumps(mc_data.to_dict())
        
        # Retrieve
        retrieved = cache.get(mint, timestamp)
        assert retrieved is not None
        assert retrieved.value == 3000000.0
        
        mock_redis_instance.get.assert_called_with(cache_key)
    
    def test_get_stats(self):
        """Test cache statistics"""
        cache = MarketCapCache(use_redis=False)
        
        # Add some data
        cache.set("mint1", int(time.time()), MarketCapData(value=1000000.0, confidence=CONFIDENCE_HIGH, timestamp=0, source="test"))
        
        stats = cache.get_stats()
        assert stats["backend"] == "in-memory"
        assert stats["lru_size"] == 1
        assert stats["lru_max_size"] == 1000
    
    @patch('src.lib.mc_cache.redis.Redis')
    @patch('src.lib.mc_cache.redis.ConnectionPool') 
    def test_redis_fallback_on_error(self, mock_pool_class, mock_redis_class):
        """Test fallback to in-memory when Redis fails"""
        # Import RedisError to use the correct exception type
        from redis.exceptions import RedisError
        
        # Setup connection pool to work but Redis to fail on ping
        mock_pool = MagicMock()
        mock_pool_class.from_url.return_value = mock_pool
        
        mock_redis_instance = MagicMock()
        mock_redis_class.return_value = mock_redis_instance
        mock_redis_instance.ping.side_effect = RedisError("Redis connection failed")
        
        # Create cache - should fallback to in-memory
        cache = MarketCapCache(use_redis=True)
        
        # Should still work with in-memory
        mint = "test_mint"
        timestamp = int(time.time())
        mc_data = MarketCapData(value=1000000.0, confidence=CONFIDENCE_HIGH, timestamp=timestamp, source="test")
        
        assert cache.set(mint, timestamp, mc_data) is True
        retrieved = cache.get(mint, timestamp)
        assert retrieved is not None
        assert retrieved.value == 1000000.0
        
        # Stats should show in-memory
        stats = cache.get_stats()
        assert stats["backend"] == "in-memory"
    
    def test_fallback_to_memory_cache(self):
        """Test explicit fallback when Redis URL is invalid"""
        # Save original REDIS_URL
        original_redis_url = os.environ.get("REDIS_URL")
        
        try:
            # Set invalid Redis URL to force fallback
            os.environ["REDIS_URL"] = "redis://invalid:6379"
            
            # Create cache - should automatically use in-memory
            cache = MarketCapCache(use_redis=True)
            
            # Test data
            mint = "So11111111111111111111111111111111111111112"
            timestamp = int(time.time())
            mc_data = MarketCapData(
                value=15000000000.0,  # $15B SOL market cap
                confidence=CONFIDENCE_HIGH,
                timestamp=timestamp,
                source="helius_raydium"
            )
            
            # Should work seamlessly with in-memory fallback
            assert cache.set(mint, timestamp, mc_data) is True
            
            # Retrieve
            retrieved = cache.get(mint, timestamp)
            assert retrieved is not None
            assert retrieved.value == 15000000000.0
            assert retrieved.confidence == CONFIDENCE_HIGH
            assert retrieved.source == "helius_raydium"
            
            # Check stats confirm in-memory backend
            stats = cache.get_stats()
            assert stats["backend"] == "in-memory"
            assert stats["lru_size"] == 1
            
            # Test batch operations also work
            requests = [
                (mint, timestamp),
                ("unknown_mint", timestamp)
            ]
            batch_results = cache.batch_get(requests)
            assert len(batch_results) == 2
            assert batch_results[(mint, timestamp)] is not None
            assert batch_results[("unknown_mint", timestamp)] is None
            
            print("✅ Redis-down fallback test passed")
            
        finally:
            # Restore original REDIS_URL
            if original_redis_url is not None:
                os.environ["REDIS_URL"] = original_redis_url
            else:
                os.environ.pop("REDIS_URL", None)


if __name__ == "__main__":
    # Run basic tests
    print("Testing MarketCapData...")
    test_data = TestMarketCapData()
    test_data.test_to_dict()
    test_data.test_from_dict()
    test_data.test_from_dict_missing_fields()
    print("✅ MarketCapData tests passed")
    
    print("\nTesting InMemoryLRUCache...")
    test_lru = TestInMemoryLRUCache()
    test_lru.test_basic_get_set()
    test_lru.test_lru_eviction()
    test_lru.test_ttl_expiry()
    print("✅ InMemoryLRUCache tests passed")
    
    print("\nTesting MarketCapCache...")
    test_cache = TestMarketCapCache()
    test_cache.test_in_memory_mode()
    test_cache.test_cache_key_generation()
    test_cache.test_date_granularity()
    test_cache.test_batch_get()
    test_cache.test_get_stats()
    test_cache.test_redis_fallback_on_error()
    test_cache.test_fallback_to_memory_cache()
    print("✅ MarketCapCache tests passed")
    
    print("\n✅ All tests passed!") 