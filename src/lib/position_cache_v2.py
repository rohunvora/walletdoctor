"""
Position Cache Layer V2 - Enhanced with Eviction & Refresh
WAL-607: Smart cache eviction, lazy refresh, and staleness marking

Provides configurable TTL, LRU eviction, async refresh on stale data,
and Prometheus-ready metrics for monitoring cache performance.
"""

import os
import json
import time
import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple, Set
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import asdict
from decimal import Decimal

try:
    import redis
    from redis.connection import ConnectionPool
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    RedisError = Exception
    RedisConnectionError = Exception

from src.lib.position_models import Position, PositionPnL, PositionSnapshot
from src.config.feature_flags import positions_enabled

logger = logging.getLogger(__name__)

# Constants from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_KEY_PREFIX = "pos:v1:"  # Version prefix for cache keys
PNL_CACHE_TTL = 60  # 1 minute for price-dependent data
SNAPSHOT_CACHE_TTL = 1800  # 30 minutes for historical snapshots


def get_position_cache_ttl():
    """Get position cache TTL from environment"""
    return int(os.getenv("POSITION_CACHE_TTL_SEC", "900"))


def get_position_cache_max():
    """Get position cache max size from environment"""
    return int(os.getenv("POSITION_CACHE_MAX", "2000"))


def is_position_cache_enabled():
    """Check if position cache is enabled"""
    return os.getenv("POSITION_CACHE_ENABLED", "true").lower() == "true"


class InMemoryLRUCache:
    """LRU cache with eviction tracking and staleness support"""
    
    def __init__(self, max_size: Optional[int] = None):
        self.cache: OrderedDict[str, Tuple[str, float, float]] = OrderedDict()  # value, expiry, created_at
        self.max_size = max_size or get_position_cache_max()
        self.evictions = 0
    
    def get(self, key: str, now: Optional[float] = None) -> Optional[Tuple[str, bool]]:
        """Get value with staleness flag"""
        if key not in self.cache:
            return None
        
        current_time = now or time.time()
        value, expiry, created_at = self.cache[key]
        
        # Check if expired
        if current_time > expiry:
            del self.cache[key]
            return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        
        # Check staleness
        age = current_time - created_at
        is_stale = age > get_position_cache_ttl()
        
        return (value, is_stale)
    
    def set(self, key: str, value: str, ttl_seconds: int, now: Optional[float] = None):
        """Set value with TTL"""
        current_time = now or time.time()
        expiry = current_time + ttl_seconds
        self.cache[key] = (value, expiry, current_time)
        self.cache.move_to_end(key)
        
        # Evict oldest if over capacity
        while len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
            self.evictions += 1
    
    def delete(self, key: str) -> bool:
        """Delete a key"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern"""
        count = 0
        keys_to_delete = []
        
        # Handle wildcard patterns
        if "*" in pattern:
            parts = pattern.split(":")
            if len(parts) >= 4 and parts[2] == "*":
                wallet = parts[3].rstrip("*")
                # Find all keys containing this wallet
                for k in list(self.cache.keys()):  # Make a copy to avoid modification during iteration
                    if f":{wallet}:" in k or k.endswith(f":{wallet}"):
                        keys_to_delete.append(k)
            else:
                # Prefix match
                prefix = pattern.split("*")[0]
                keys_to_delete = [k for k in self.cache.keys() if k.startswith(prefix)]
        else:
            # Simple prefix match
            keys_to_delete = [k for k in self.cache.keys() if k.startswith(pattern)]
        
        for key in keys_to_delete:
            if self.delete(key):
                count += 1
        return count


class PositionCacheV2:
    """Enhanced position cache with eviction, refresh, and staleness support"""
    
    def __init__(
        self, 
        redis_url: str = REDIS_URL,
        use_redis: bool = True,
        now_provider: Optional[callable] = None  # For testing
    ):
        """Initialize enhanced cache"""
        self.enabled = is_position_cache_enabled()
        
        if not self.enabled:
            logger.info("Position cache is disabled by feature flag")
            
        self.use_redis = use_redis and self.enabled and REDIS_AVAILABLE
        self.redis_client = None
        self.connection_pool = None
        self.lru_cache = InMemoryLRUCache()
        self.now_provider = now_provider or time.time
        
        # Metrics
        self.metrics = {
            "position_cache_hits": 0,
            "position_cache_misses": 0,
            "position_cache_evictions": 0,
            "position_cache_refresh_errors": 0,
            "position_cache_redis_errors": 0,
            "position_cache_stale_serves": 0,
            "position_cache_refresh_triggers": 0
        }
        
        # Track refresh tasks
        self.refresh_tasks: Dict[str, asyncio.Task] = {}
        
        if self.use_redis:
            try:
                self.connection_pool = redis.ConnectionPool.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                self.redis_client = redis.Redis(connection_pool=self.connection_pool)
                self.redis_client.ping()
                logger.info("Position cache V2 Redis connection established")
            except (RedisError, RedisConnectionError) as e:
                logger.warning(f"Redis connection failed, using in-memory cache: {e}")
                self.use_redis = False
                self.redis_client = None
                self.metrics["position_cache_redis_errors"] += 1
    
    def _get_cache_key(self, cache_type: str, wallet: str, token_mint: Optional[str] = None) -> str:
        """Generate cache key"""
        if token_mint:
            return f"{CACHE_KEY_PREFIX}{cache_type}:{wallet}:{token_mint}"
        return f"{CACHE_KEY_PREFIX}{cache_type}:{wallet}"
    
    async def get_position(
        self, 
        wallet: str, 
        token_mint: str,
        trigger_refresh: bool = True
    ) -> Optional[Tuple[Position, bool]]:
        """
        Get position from cache with staleness flag
        
        Returns:
            Tuple of (Position, is_stale) or None
        """
        if not self.enabled:
            return None
            
        cache_key = self._get_cache_key("position", wallet, token_mint)
        result = self._get_from_cache(cache_key)
        
        if result:
            value, is_stale = result
            try:
                position_dict = json.loads(value)
                position = self._deserialize_position(position_dict)
                
                self.metrics["position_cache_hits"] += 1
                
                if is_stale:
                    self.metrics["position_cache_stale_serves"] += 1
                    
                    # Trigger async refresh if needed
                    if trigger_refresh:
                        refresh_key = f"{wallet}:{token_mint}"
                        if refresh_key not in self.refresh_tasks:
                            self.metrics["position_cache_refresh_triggers"] += 1
                            task = asyncio.create_task(
                                self._refresh_position(wallet, token_mint)
                            )
                            self.refresh_tasks[refresh_key] = task
                
                return (position, is_stale)
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to deserialize position: {e}")
                self.metrics["position_cache_refresh_errors"] += 1
        else:
            self.metrics["position_cache_misses"] += 1
        
        return None
    
    async def set_position(self, position: Position) -> bool:
        """Cache a position"""
        if not self.enabled:
            return False
            
        cache_key = self._get_cache_key("position", position.wallet, position.token_mint)
        position_json = json.dumps(position.to_dict())
        
        return self._set_in_cache(cache_key, position_json, get_position_cache_ttl())
    
    async def get_portfolio_snapshot(
        self, 
        wallet: str,
        trigger_refresh: bool = True
    ) -> Optional[Tuple[PositionSnapshot, bool]]:
        """Get portfolio snapshot with staleness flag"""
        if not self.enabled:
            return None
            
        cache_key = self._get_cache_key("snapshot", wallet)
        result = self._get_from_cache(cache_key)
        
        if result:
            value, is_stale = result
            try:
                snapshot_dict = json.loads(value)
                snapshot = self._deserialize_snapshot(snapshot_dict)
                
                self.metrics["position_cache_hits"] += 1
                
                if is_stale:
                    self.metrics["position_cache_stale_serves"] += 1
                    
                    # Mark positions as stale in response
                    for pos_pnl in snapshot.positions:
                        if hasattr(pos_pnl, '_stale'):
                            pos_pnl._stale = True
                    
                    # Trigger refresh
                    if trigger_refresh and wallet not in self.refresh_tasks:
                        self.metrics["position_cache_refresh_triggers"] += 1
                        task = asyncio.create_task(
                            self._refresh_portfolio(wallet)
                        )
                        self.refresh_tasks[wallet] = task
                
                return (snapshot, is_stale)
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to deserialize snapshot: {e}")
                self.metrics["position_cache_refresh_errors"] += 1
        else:
            self.metrics["position_cache_misses"] += 1
        
        return None
    
    async def set_portfolio_snapshot(self, snapshot: PositionSnapshot) -> bool:
        """Cache portfolio snapshot"""
        if not self.enabled:
            return False
            
        cache_key = self._get_cache_key("snapshot", snapshot.wallet)
        snapshot_json = json.dumps(snapshot.to_dict())
        
        return self._set_in_cache(cache_key, snapshot_json, SNAPSHOT_CACHE_TTL)
    
    async def invalidate_wallet(self, wallet: str) -> int:
        """Invalidate all cached data for a wallet"""
        if not self.enabled:
            return 0
            
        pattern = f"{CACHE_KEY_PREFIX}*:{wallet}*"
        
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
                self.metrics["position_cache_redis_errors"] += 1
        
        # Fallback to in-memory
        count = self.lru_cache.delete_pattern(pattern)
        logger.info(f"Invalidated {count} in-memory cache entries for wallet {wallet}")
        return count
    
    def _get_from_cache(self, key: str) -> Optional[Tuple[str, bool]]:
        """Get value with staleness flag from cache"""
        now = self.now_provider()
        
        if self.use_redis and self.redis_client:
            try:
                # Get value with TTL check
                pipeline = self.redis_client.pipeline()
                pipeline.get(key)
                pipeline.ttl(key)
                value, ttl = pipeline.execute()
                
                if value:
                    # Check if stale based on remaining TTL
                    is_stale = ttl < (get_position_cache_ttl() / 2)  # Less than half TTL remaining
                    return (value, is_stale)
                return None
            except RedisError as e:
                logger.error(f"Redis get error for {key}: {e}")
                self.metrics["position_cache_redis_errors"] += 1
        
        # Fallback to in-memory
        result = self.lru_cache.get(key, now=now)
        if result:
            self.metrics["position_cache_evictions"] = self.lru_cache.evictions
        return result
    
    def _set_in_cache(self, key: str, value: str, ttl: int) -> bool:
        """Set value in cache"""
        now = self.now_provider()
        
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.setex(key, ttl, value)
                return True
            except RedisError as e:
                logger.error(f"Redis set error for {key}: {e}")
                self.metrics["position_cache_redis_errors"] += 1
        
        # Fallback to in-memory
        self.lru_cache.set(key, value, ttl, now=now)
        self.metrics["position_cache_evictions"] = self.lru_cache.evictions
        return True
    
    async def _refresh_position(self, wallet: str, token_mint: str):
        """Background refresh of position data"""
        try:
            # This would call the actual position calculation service
            # For now, just log that refresh was triggered
            logger.info(f"Refreshing position for {wallet}:{token_mint}")
            
            # Clean up task reference
            refresh_key = f"{wallet}:{token_mint}"
            if refresh_key in self.refresh_tasks:
                del self.refresh_tasks[refresh_key]
                
        except Exception as e:
            logger.error(f"Error refreshing position: {e}")
            self.metrics["position_cache_refresh_errors"] += 1
    
    async def _refresh_portfolio(self, wallet: str):
        """Background refresh of portfolio data"""
        try:
            # This would call the actual portfolio calculation service
            logger.info(f"Refreshing portfolio for {wallet}")
            
            # Clean up task reference
            if wallet in self.refresh_tasks:
                del self.refresh_tasks[wallet]
                
        except Exception as e:
            logger.error(f"Error refreshing portfolio: {e}")
            self.metrics["position_cache_refresh_errors"] += 1
    
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
        
        # Import here to avoid circular import
        from src.lib.cost_basis_calculator import CostBasisMethod
        
        # Convert cost basis method
        if data.get("cost_basis_method"):
            data["cost_basis_method"] = CostBasisMethod(data["cost_basis_method"])
        
        return Position(**data)
    
    def _deserialize_snapshot(self, data: Dict[str, Any]) -> PositionSnapshot:
        """Deserialize portfolio snapshot from dict"""
        # Parse timestamp
        if data.get("timestamp"):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"].rstrip("Z"))
        
        # Import here to avoid circular import
        from src.lib.position_models import PriceConfidence
        
        # Deserialize positions
        positions = []
        for pos_data in data.get("positions", []):
            # Deserialize position first
            if "position" in pos_data:
                position = self._deserialize_position(pos_data["position"])
            else:
                # Reconstruct from flat data
                position = Position(
                    position_id=pos_data.get("position_id", ""),
                    wallet=pos_data.get("wallet", ""),
                    token_mint=pos_data.get("token_mint", ""),
                    token_symbol=pos_data.get("token_symbol", ""),
                    balance=Decimal(pos_data.get("balance", "0")),
                    cost_basis=Decimal(pos_data.get("cost_basis", "0")),
                    cost_basis_usd=Decimal(pos_data.get("cost_basis_usd", "0")),
                    decimals=pos_data.get("decimals", 9)
                )
            
            # Create PositionPnL
            position_pnl = PositionPnL(
                position=position,
                current_price_usd=Decimal(pos_data.get("current_price_usd", "0")),
                current_value_usd=Decimal(pos_data.get("current_value_usd", "0")),
                unrealized_pnl_usd=Decimal(pos_data.get("unrealized_pnl_usd", "0")),
                unrealized_pnl_pct=Decimal(pos_data.get("unrealized_pnl_pct", "0")),
                price_confidence=PriceConfidence(pos_data.get("price_confidence", "unavailable")),
                last_price_update=datetime.fromisoformat(
                    pos_data.get("last_price_update", datetime.now().isoformat()).rstrip("Z")
                ),
                price_source=pos_data.get("price_source", "unknown"),
                price_age_seconds=pos_data.get("price_age_seconds", 0)
            )
            positions.append(position_pnl)
        
        # Handle summary format
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
            total_value_usd=Decimal(data.get("total_value_usd", "0")),
            total_unrealized_pnl_usd=Decimal(data.get("total_unrealized_pnl_usd", "0")),
            total_unrealized_pnl_pct=Decimal(data.get("total_unrealized_pnl_pct", "0"))
        )
    
    def get_metrics(self) -> Dict[str, int]:
        """Get Prometheus-ready metrics"""
        # Update eviction count from LRU
        self.metrics["position_cache_evictions"] = self.lru_cache.evictions
        return self.metrics.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detailed cache statistics"""
        total_requests = (
            self.metrics["position_cache_hits"] + 
            self.metrics["position_cache_misses"]
        )
        hit_rate = (
            (self.metrics["position_cache_hits"] / total_requests * 100)
            if total_requests > 0 else 0
        )
        
        stats = {
            "enabled": self.enabled,
            "backend": "redis" if self.use_redis else "in-memory",
            "hit_rate_pct": hit_rate,
            "total_requests": total_requests,
            "lru_size": len(self.lru_cache.cache),
            "lru_max_size": self.lru_cache.max_size,
            "active_refresh_tasks": len(self.refresh_tasks),
            "config": {
                "ttl_seconds": get_position_cache_ttl(),
                "max_wallets": get_position_cache_max()
            }
        }
        
        # Add all metrics
        stats.update(self.metrics)
        
        if self.use_redis and self.redis_client:
            try:
                info = self.redis_client.info()
                stats.update({
                    "redis_connected": True,
                    "redis_used_memory": info.get("used_memory_human", "N/A"),
                    "redis_connected_clients": info.get("connected_clients", 0)
                })
            except RedisError:
                stats["redis_connected"] = False
        
        return stats
    
    def close(self):
        """Close Redis connection and cancel refresh tasks"""
        # Cancel all refresh tasks
        for task in self.refresh_tasks.values():
            task.cancel()
        self.refresh_tasks.clear()
        
        # Close Redis connection
        if self.connection_pool:
            self.connection_pool.disconnect()
            logger.info("Position cache V2 Redis connection pool closed")


# Global instance
_cache_v2_instance: Optional[PositionCacheV2] = None


def get_position_cache_v2() -> PositionCacheV2:
    """Get or create global cache instance"""
    global _cache_v2_instance
    if _cache_v2_instance is None:
        _cache_v2_instance = PositionCacheV2()
    return _cache_v2_instance 