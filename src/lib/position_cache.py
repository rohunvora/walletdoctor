"""
Position Cache Layer
WAL-605: Redis-backed cache for positions with TTL and invalidation

Provides fast position retrieval with fallback to calculation,
cache invalidation on new trades, and performance monitoring.
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, List, Tuple, Set
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import asdict
from decimal import Decimal
import redis
from redis.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from src.lib.position_models import Position, PositionPnL, PositionSnapshot
from src.lib.position_builder import PositionBuilder
from src.lib.unrealized_pnl_calculator import UnrealizedPnLCalculator
from src.lib.cost_basis_calculator import CostBasisMethod
from src.config.feature_flags import positions_enabled, get_cost_basis_method

logger = logging.getLogger(__name__)

# Constants
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
POSITION_CACHE_TTL = 300  # 5 minutes as specified
PNL_CACHE_TTL = 60  # 1 minute for price-dependent data
SNAPSHOT_CACHE_TTL = 1800  # 30 minutes for historical snapshots
LRU_MAX_SIZE = 500  # In-memory fallback capacity
CACHE_KEY_PREFIX = "pos:v1:"  # Version prefix for cache keys


class InMemoryPositionCache:
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
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern (simple prefix match)"""
        count = 0
        keys_to_delete = []
        
        # Special handling for wallet invalidation patterns
        if "*" in pattern:
            # Extract wallet from pattern like "pos:v1:*:wallet*"
            parts = pattern.split(":")
            if len(parts) >= 4 and parts[2] == "*":
                wallet = parts[3].rstrip("*")
                # Find all keys containing this wallet
                for k in self.cache.keys():
                    if f":{wallet}:" in k:
                        keys_to_delete.append(k)
            else:
                # Fallback to prefix match
                prefix = pattern.split("*")[0]
                keys_to_delete = [k for k in self.cache.keys() if k.startswith(prefix)]
        else:
            # Simple prefix match
            keys_to_delete = [k for k in self.cache.keys() if k.startswith(pattern)]
        
        for key in keys_to_delete:
            if self.delete(key):
                count += 1
        return count


class PositionCache:
    """Redis-backed position cache with in-memory fallback"""
    
    def __init__(
        self, 
        redis_url: str = REDIS_URL, 
        use_redis: bool = True,
        position_builder: Optional[PositionBuilder] = None,
        pnl_calculator: Optional[UnrealizedPnLCalculator] = None
    ):
        """
        Initialize cache with Redis connection pool
        
        Args:
            redis_url: Redis connection URL
            use_redis: Whether to use Redis (False for testing)
            position_builder: Optional position builder instance
            pnl_calculator: Optional P&L calculator instance
        """
        self.use_redis = use_redis
        self.redis_client: Optional[redis.Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None
        self.lru_cache = InMemoryPositionCache()
        
        # Services for fallback calculation
        self.position_builder = position_builder or PositionBuilder(
            CostBasisMethod(get_cost_basis_method())
        )
        self.pnl_calculator = pnl_calculator or UnrealizedPnLCalculator()
        
        # Performance metrics
        self.metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_errors": 0,
            "fallback_calculations": 0
        }
        
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
                logger.info("Position cache Redis connection established")
            except (RedisError, RedisConnectionError) as e:
                logger.warning(f"Redis connection failed, using in-memory cache: {e}")
                self.use_redis = False
                self.redis_client = None
    
    def _get_position_key(self, wallet: str, token_mint: str) -> str:
        """Generate cache key for position"""
        return f"{CACHE_KEY_PREFIX}position:{wallet}:{token_mint}"
    
    def _get_pnl_key(self, wallet: str, token_mint: str) -> str:
        """Generate cache key for position P&L"""
        return f"{CACHE_KEY_PREFIX}pnl:{wallet}:{token_mint}"
    
    def _get_snapshot_key(self, wallet: str, timestamp: Optional[int] = None) -> str:
        """Generate cache key for portfolio snapshot"""
        if timestamp:
            # Round to nearest hour for better cache hits
            hour_ts = (timestamp // 3600) * 3600
            return f"{CACHE_KEY_PREFIX}snapshot:{wallet}:{hour_ts}"
        return f"{CACHE_KEY_PREFIX}snapshot:{wallet}:latest"
    
    def _get_invalidation_pattern(self, wallet: str) -> str:
        """Get pattern for invalidating all wallet positions"""
        # Need to match the actual key format: pos:v1:TYPE:WALLET:MINT
        return f"{CACHE_KEY_PREFIX}*:{wallet}*"
    
    async def get_position(self, wallet: str, token_mint: str) -> Optional[Position]:
        """
        Get position from cache or calculate if missing
        
        Args:
            wallet: Wallet address
            token_mint: Token mint address
            
        Returns:
            Position object or None
        """
        if not positions_enabled():
            return None
        
        cache_key = self._get_position_key(wallet, token_mint)
        
        # Try cache first
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            try:
                self.metrics["cache_hits"] += 1
                position_dict = json.loads(cached_data)
                return self._deserialize_position(position_dict)
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to deserialize position: {e}")
                self.metrics["cache_errors"] += 1
        else:
            self.metrics["cache_misses"] += 1
        
        # Fallback: return None (caller should calculate)
        # This avoids circular dependency where cache calculates positions
        return None
    
    async def set_position(self, position: Position) -> bool:
        """
        Cache a position
        
        Args:
            position: Position to cache
            
        Returns:
            True if cached successfully
        """
        cache_key = self._get_position_key(position.wallet, position.token_mint)
        position_json = json.dumps(position.to_dict())
        
        return self._set_in_cache(cache_key, position_json, POSITION_CACHE_TTL)
    
    async def get_position_pnl(
        self, 
        wallet: str, 
        token_mint: str
    ) -> Optional[PositionPnL]:
        """
        Get position P&L from cache
        
        Args:
            wallet: Wallet address
            token_mint: Token mint address
            
        Returns:
            PositionPnL object or None
        """
        if not positions_enabled():
            return None
        
        cache_key = self._get_pnl_key(wallet, token_mint)
        
        # Try cache first
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            try:
                self.metrics["cache_hits"] += 1
                pnl_dict = json.loads(cached_data)
                return self._deserialize_position_pnl(pnl_dict)
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to deserialize position P&L: {e}")
                self.metrics["cache_errors"] += 1
        else:
            self.metrics["cache_misses"] += 1
        
        return None
    
    async def set_position_pnl(self, position_pnl: PositionPnL) -> bool:
        """
        Cache position P&L (shorter TTL due to price volatility)
        
        Args:
            position_pnl: PositionPnL to cache
            
        Returns:
            True if cached successfully
        """
        cache_key = self._get_pnl_key(
            position_pnl.position.wallet,
            position_pnl.position.token_mint
        )
        pnl_json = json.dumps(position_pnl.to_dict())
        
        return self._set_in_cache(cache_key, pnl_json, PNL_CACHE_TTL)
    
    async def get_portfolio_snapshot(
        self, 
        wallet: str,
        timestamp: Optional[int] = None
    ) -> Optional[PositionSnapshot]:
        """
        Get portfolio snapshot from cache
        
        Args:
            wallet: Wallet address
            timestamp: Optional timestamp for historical snapshot
            
        Returns:
            PositionSnapshot object or None
        """
        cache_key = self._get_snapshot_key(wallet, timestamp)
        
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            try:
                self.metrics["cache_hits"] += 1
                snapshot_dict = json.loads(cached_data)
                return self._deserialize_snapshot(snapshot_dict)
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to deserialize snapshot: {e}")
                self.metrics["cache_errors"] += 1
        else:
            self.metrics["cache_misses"] += 1
        
        return None
    
    async def set_portfolio_snapshot(
        self, 
        snapshot: PositionSnapshot,
        timestamp: Optional[int] = None
    ) -> bool:
        """
        Cache portfolio snapshot
        
        Args:
            snapshot: PositionSnapshot to cache
            timestamp: Optional timestamp for historical caching
            
        Returns:
            True if cached successfully
        """
        cache_key = self._get_snapshot_key(snapshot.wallet, timestamp)
        snapshot_json = json.dumps(snapshot.to_dict())
        
        return self._set_in_cache(cache_key, snapshot_json, SNAPSHOT_CACHE_TTL)
    
    async def invalidate_wallet_positions(self, wallet: str) -> int:
        """
        Invalidate all cached positions for a wallet (on new trades)
        
        Args:
            wallet: Wallet address
            
        Returns:
            Number of keys invalidated
        """
        pattern = self._get_invalidation_pattern(wallet)
        
        if self.use_redis and self.redis_client:
            try:
                # Use SCAN to find and delete matching keys
                count = 0
                cursor = 0
                while True:
                    cursor, keys = self.redis_client.scan(
                        cursor, 
                        match=pattern, 
                        count=100
                    )
                    if keys:
                        count += self.redis_client.delete(*keys)
                    if cursor == 0:
                        break
                
                logger.info(f"Invalidated {count} cache entries for wallet {wallet}")
                return count
            except RedisError as e:
                logger.error(f"Redis invalidation error: {e}")
                self.metrics["cache_errors"] += 1
        
        # Fallback to in-memory
        count = self.lru_cache.delete_pattern(pattern)
        logger.info(f"Invalidated {count} in-memory cache entries for wallet {wallet}")
        return count
    
    def _get_from_cache(self, key: str) -> Optional[str]:
        """Get value from cache (Redis or in-memory)"""
        if self.use_redis and self.redis_client:
            try:
                return self.redis_client.get(key)
            except RedisError as e:
                logger.error(f"Redis get error for {key}: {e}")
                self.metrics["cache_errors"] += 1
        
        # Fallback to in-memory
        return self.lru_cache.get(key)
    
    def _set_in_cache(self, key: str, value: str, ttl: int) -> bool:
        """Set value in cache with TTL"""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.setex(key, ttl, value)
                return True
            except RedisError as e:
                logger.error(f"Redis set error for {key}: {e}")
                self.metrics["cache_errors"] += 1
        
        # Fallback to in-memory
        self.lru_cache.set(key, value, ttl)
        return True
    
    def _deserialize_position(self, data: Dict[str, Any]) -> Position:
        """Deserialize position from dict"""
        # Convert string timestamps to datetime
        for field in ["opened_at", "last_trade_at", "last_update_time", "closed_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field].rstrip("Z"))
        
        # Convert string decimals
        for field in ["balance", "cost_basis", "cost_basis_usd"]:
            if data.get(field):
                data[field] = Decimal(data[field])
        
        # Convert cost basis method
        if data.get("cost_basis_method"):
            data["cost_basis_method"] = CostBasisMethod(data["cost_basis_method"])
        
        return Position(**data)
    
    def _deserialize_position_pnl(self, data: Dict[str, Any]) -> PositionPnL:
        """Deserialize position P&L from dict"""
        # First deserialize the nested position
        if "position" in data:
            position_data = data.pop("position")
            position = self._deserialize_position(position_data)
        else:
            # Try to reconstruct from flat data
            position = Position(
                position_id=data.get("position_id", ""),
                wallet=data.get("wallet", ""),
                token_mint=data.get("token_mint", ""),
                token_symbol=data.get("token_symbol", ""),
                balance=Decimal(data.get("balance", "0")),
                cost_basis=Decimal(data.get("cost_basis", "0")),
                cost_basis_usd=Decimal(data.get("cost_basis_usd", "0")),
                decimals=data.get("decimals", 9)
            )
        
        # Parse timestamp
        if data.get("last_price_update"):
            data["last_price_update"] = datetime.fromisoformat(
                data["last_price_update"].rstrip("Z")
            )
        
        # Import PriceConfidence here to avoid circular import
        from src.lib.position_models import PriceConfidence
        
        # Convert confidence string to enum
        if data.get("price_confidence"):
            data["price_confidence"] = PriceConfidence(data["price_confidence"])
        
        # Convert string decimals
        for field in ["current_price_usd", "current_value_usd", "unrealized_pnl_usd", "unrealized_pnl_pct"]:
            if data.get(field):
                data[field] = Decimal(data[field])
        
        return PositionPnL(
            position=position,
            current_price_usd=data.get("current_price_usd", Decimal("0")),
            current_value_usd=data.get("current_value_usd", Decimal("0")),
            unrealized_pnl_usd=data.get("unrealized_pnl_usd", Decimal("0")),
            unrealized_pnl_pct=data.get("unrealized_pnl_pct", Decimal("0")),
            price_confidence=data.get("price_confidence", PriceConfidence.UNAVAILABLE),
            last_price_update=data.get("last_price_update", datetime.now()),
            price_source=data.get("price_source", "unknown"),
            price_age_seconds=data.get("price_age_seconds", 0)
        )
    
    def _deserialize_snapshot(self, data: Dict[str, Any]) -> PositionSnapshot:
        """Deserialize portfolio snapshot from dict"""
        # Parse timestamp
        if data.get("timestamp"):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"].rstrip("Z"))
        
        # Deserialize positions
        positions = []
        for pos_data in data.get("positions", []):
            positions.append(self._deserialize_position_pnl(pos_data))
        
        # Convert string decimals
        for field in ["total_value_usd", "total_unrealized_pnl_usd", "total_unrealized_pnl_pct"]:
            if field in data and "summary" not in data:
                data[field] = Decimal(data[field])
        
        # Handle summary format from to_dict()
        if "summary" in data:
            summary = data["summary"]
            return PositionSnapshot(
                wallet=data["wallet"],
                timestamp=data["timestamp"],
                positions=positions,
                total_value_usd=Decimal(summary.get("total_value_usd", "0")),
                total_unrealized_pnl_usd=Decimal(summary.get("total_unrealized_pnl_usd", "0")),
                total_unrealized_pnl_pct=Decimal(summary.get("total_unrealized_pnl_pct", "0").rstrip("%"))
            )
        
        return PositionSnapshot(
            wallet=data["wallet"],
            timestamp=data["timestamp"],
            positions=positions,
            total_value_usd=data.get("total_value_usd", Decimal("0")),
            total_unrealized_pnl_usd=data.get("total_unrealized_pnl_usd", Decimal("0")),
            total_unrealized_pnl_pct=data.get("total_unrealized_pnl_pct", Decimal("0"))
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = (
            self.metrics["cache_hits"] + 
            self.metrics["cache_misses"]
        )
        hit_rate = (
            (self.metrics["cache_hits"] / total_requests * 100)
            if total_requests > 0 else 0
        )
        
        stats = {
            "backend": "redis" if self.use_redis else "in-memory",
            "cache_hits": self.metrics["cache_hits"],
            "cache_misses": self.metrics["cache_misses"],
            "cache_errors": self.metrics["cache_errors"],
            "hit_rate": hit_rate,
            "total_requests": total_requests,
            "fallback_calculations": self.metrics["fallback_calculations"],
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
            logger.info("Position cache Redis connection pool closed")


# Global cache instance (created on first use)
_position_cache_instance: Optional[PositionCache] = None


def get_position_cache() -> PositionCache:
    """Get or create global position cache instance"""
    global _position_cache_instance
    if _position_cache_instance is None:
        _position_cache_instance = PositionCache()
    return _position_cache_instance


# Performance benchmark function
async def benchmark_cache_performance(wallet: str, token_mints: List[str]) -> Dict[str, Any]:
    """
    Benchmark cache performance
    
    Args:
        wallet: Wallet address
        token_mints: List of token mints to test
        
    Returns:
        Performance metrics
    """
    cache = get_position_cache()
    
    # Test data
    test_position = Position(
        position_id=f"{wallet}:test:123456",
        wallet=wallet,
        token_mint=token_mints[0] if token_mints else "test_mint",
        token_symbol="TEST",
        balance=Decimal("1000"),
        cost_basis=Decimal("1.0"),
        cost_basis_usd=Decimal("1000"),
        decimals=9
    )
    
    # Benchmark writes
    start_time = time.time()
    write_count = 0
    
    for mint in token_mints:
        test_position.token_mint = mint
        if await cache.set_position(test_position):
            write_count += 1
    
    write_time = time.time() - start_time
    write_latency = (write_time / len(token_mints) * 1000) if token_mints else 0
    
    # Benchmark reads
    start_time = time.time()
    read_count = 0
    
    for mint in token_mints:
        if await cache.get_position(wallet, mint):
            read_count += 1
    
    read_time = time.time() - start_time
    read_latency = (read_time / len(token_mints) * 1000) if token_mints else 0
    
    # Get cache stats
    stats = cache.get_stats()
    
    return {
        "write_count": write_count,
        "write_time_ms": write_time * 1000,
        "write_latency_ms": write_latency,
        "read_count": read_count,
        "read_time_ms": read_time * 1000,
        "read_latency_ms": read_latency,
        "cache_stats": stats,
        "performance_target_met": read_latency < 100  # < 100ms target
    } 