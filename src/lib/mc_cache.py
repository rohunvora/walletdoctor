#!/usr/bin/env python3
"""
Market Cap Cache - Redis-backed cache with in-memory LRU fallback
Stores historical market cap data for tokens with 30-day TTL
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import dataclass, asdict
from decimal import Decimal
import redis
from redis.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

# Setup logging
logger = logging.getLogger(__name__)

# Constants
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_DAYS = 30
CACHE_TTL_SECONDS = CACHE_TTL_DAYS * 24 * 60 * 60
LRU_MAX_SIZE = 1000  # In-memory fallback capacity
CACHE_KEY_PREFIX = "mc:v1:"  # Version prefix for cache keys

# Market cap confidence levels
CONFIDENCE_HIGH = "high"      # From on-chain AMM with good TVL
CONFIDENCE_EST = "est"        # From external APIs or current prices
CONFIDENCE_UNAVAILABLE = "unavailable"  # No data available


@dataclass
class MarketCapData:
    """Market cap data structure"""
    value: Optional[float]  # Market cap in USD
    confidence: str  # high/est/unavailable
    timestamp: int  # Unix timestamp when calculated
    source: Optional[str]  # Data source (e.g., "raydium", "birdeye")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "value": self.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "source": self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketCapData":
        """Create from dictionary"""
        return cls(
            value=data.get("value"),
            confidence=data.get("confidence", CONFIDENCE_UNAVAILABLE),
            timestamp=data.get("timestamp", 0),
            source=data.get("source")
        )


class InMemoryLRUCache:
    """Simple LRU cache for Redis fallback"""
    
    def __init__(self, max_size: int = LRU_MAX_SIZE):
        self.cache: OrderedDict[str, Tuple[str, float]] = OrderedDict()
        self.max_size = max_size
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        if key not in self.cache:
            return None
        
        # Check TTL
        value, expiry = self.cache[key]
        if time.time() > expiry:
            del self.cache[key]
            return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return value
    
    def set(self, key: str, value: str, ttl_seconds: int):
        """Set value in cache with TTL"""
        expiry = time.time() + ttl_seconds
        self.cache[key] = (value, expiry)
        self.cache.move_to_end(key)
        
        # Evict oldest if over capacity
        while len(self.cache) > self.max_size:
            self.cache.popitem(last=False)


class MarketCapCache:
    """Redis-backed market cap cache with in-memory fallback"""
    
    def __init__(self, redis_url: str = REDIS_URL, use_redis: bool = True):
        """Initialize cache with Redis connection pool"""
        self.use_redis = use_redis
        self.redis_client: Optional[redis.Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None
        self.lru_cache = InMemoryLRUCache()
        
        if self.use_redis:
            try:
                # Create connection pool
                self.connection_pool = redis.ConnectionPool.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                self.redis_client = redis.Redis(connection_pool=self.connection_pool)
                
                # Test connection
                self.redis_client.ping()
                logger.info("Redis connection established")
            except (RedisError, RedisConnectionError) as e:
                logger.warning(f"Redis connection failed, using in-memory cache: {e}")
                self.use_redis = False
                self.redis_client = None
    
    def _get_cache_key(self, mint: str, date: str) -> str:
        """Generate cache key for mint and date"""
        # date format: YYYY-MM-DD
        return f"{CACHE_KEY_PREFIX}{mint}:{date}"
    
    def get(self, mint: str, timestamp: int) -> Optional[MarketCapData]:
        """
        Get market cap data for a token at a specific timestamp
        
        Args:
            mint: Token mint address
            timestamp: Unix timestamp
            
        Returns:
            MarketCapData if found, None otherwise
        """
        # Convert timestamp to date for daily granularity
        date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        cache_key = self._get_cache_key(mint, date)
        
        # Try Redis first
        if self.use_redis and self.redis_client:
            try:
                data = self.redis_client.get(cache_key)
                if data:
                    return MarketCapData.from_dict(json.loads(data))
            except (RedisError, json.JSONDecodeError) as e:
                logger.error(f"Redis get error for {cache_key}: {e}")
        
        # Fallback to in-memory
        data = self.lru_cache.get(cache_key)
        if data:
            try:
                return MarketCapData.from_dict(json.loads(data))
            except json.JSONDecodeError:
                pass
        
        return None
    
    def set(self, mint: str, timestamp: int, mc_data: MarketCapData) -> bool:
        """
        Store market cap data with 30-day TTL
        
        Args:
            mint: Token mint address
            timestamp: Unix timestamp
            mc_data: Market cap data to store
            
        Returns:
            True if stored successfully
        """
        # Convert timestamp to date
        date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        cache_key = self._get_cache_key(mint, date)
        
        # Serialize data
        data_json = json.dumps(mc_data.to_dict())
        
        # Try Redis first
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.setex(
                    cache_key,
                    CACHE_TTL_SECONDS,
                    data_json
                )
                return True
            except RedisError as e:
                logger.error(f"Redis set error for {cache_key}: {e}")
        
        # Fallback to in-memory
        self.lru_cache.set(cache_key, data_json, CACHE_TTL_SECONDS)
        return True
    
    def batch_get(self, requests: list[Tuple[str, int]]) -> Dict[Tuple[str, int], Optional[MarketCapData]]:
        """
        Batch get multiple market cap entries
        
        Args:
            requests: List of (mint, timestamp) tuples
            
        Returns:
            Dictionary mapping (mint, timestamp) to MarketCapData
        """
        results = {}
        
        if self.use_redis and self.redis_client:
            # Build cache keys
            cache_keys = []
            key_to_request = {}
            
            for mint, timestamp in requests:
                date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                cache_key = self._get_cache_key(mint, date)
                cache_keys.append(cache_key)
                key_to_request[cache_key] = (mint, timestamp)
            
            try:
                # Batch get from Redis
                values = self.redis_client.mget(cache_keys)
                for cache_key, value in zip(cache_keys, values):
                    request = key_to_request[cache_key]
                    if value:
                        try:
                            results[request] = MarketCapData.from_dict(json.loads(value))
                        except json.JSONDecodeError:
                            results[request] = None
                    else:
                        results[request] = None
                
                return results
            except RedisError as e:
                logger.error(f"Redis batch get error: {e}")
        
        # Fallback to individual gets
        for mint, timestamp in requests:
            results[(mint, timestamp)] = self.get(mint, timestamp)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "backend": "redis" if self.use_redis else "in-memory",
            "lru_size": len(self.lru_cache.cache),
            "lru_max_size": self.lru_cache.max_size
        }
        
        if self.use_redis and self.redis_client:
            try:
                info = self.redis_client.info()
                stats.update({
                    "redis_connected": True,
                    "redis_used_memory": info.get("used_memory_human", "N/A"),
                    "redis_connected_clients": info.get("connected_clients", 0),
                    "redis_total_commands": info.get("total_commands_processed", 0)
                })
            except RedisError:
                stats["redis_connected"] = False
        
        return stats
    
    def close(self):
        """Close Redis connection"""
        if self.connection_pool:
            self.connection_pool.disconnect()
            logger.info("Redis connection pool closed")


# Global cache instance (created on first use)
_cache_instance: Optional[MarketCapCache] = None


def get_cache() -> MarketCapCache:
    """Get or create global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = MarketCapCache()
    return _cache_instance


# Example usage
if __name__ == "__main__":
    # Test the cache
    cache = MarketCapCache(use_redis=False)  # Use in-memory for testing
    
    # Test data
    test_mint = "So11111111111111111111111111111111111111112"
    test_timestamp = int(time.time())
    
    # Store market cap
    mc_data = MarketCapData(
        value=1234567.89,
        confidence=CONFIDENCE_HIGH,
        timestamp=test_timestamp,
        source="raydium"
    )
    
    success = cache.set(test_mint, test_timestamp, mc_data)
    print(f"Store success: {success}")
    
    # Retrieve market cap
    retrieved = cache.get(test_mint, test_timestamp)
    print(f"Retrieved: {retrieved}")
    
    # Test batch get
    requests = [
        (test_mint, test_timestamp),
        ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", test_timestamp),
    ]
    batch_results = cache.batch_get(requests)
    print(f"Batch results: {batch_results}")
    
    # Get stats
    print(f"Cache stats: {cache.get_stats()}")
    
    # Close
    cache.close() 