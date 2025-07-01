#!/usr/bin/env python3
"""
Market Cap Pre-Cache Service - Proactively caches market cap data for popular tokens
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
import json
from collections import defaultdict
import aiohttp

# Setup logging
logger = logging.getLogger(__name__)

# Import our modules
from .mc_calculator import MarketCapCalculator, calculate_market_cap
from .mc_cache import get_cache
from .jupiter_client import JupiterClient

# Constants
CACHE_REFRESH_INTERVAL = 300  # 5 minutes
POPULAR_TOKEN_REFRESH = 60    # 1 minute for popular tokens
BATCH_SIZE = 20               # Process tokens in batches
MAX_CONCURRENT_CALCULATIONS = 5  # Limit concurrent MC calculations

# Popular tokens to always keep fresh
POPULAR_TOKENS = {
    "So11111111111111111111111111111111111111112",  # SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",  # WETH
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",   # mSOL
    "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",  # stSOL
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",   # JUP
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",  # WIF
    "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",   # RENDER
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",  # PYTH
}

# Dynamic token tracking
TRENDING_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens/solana"
MAX_TRACKED_TOKENS = 100  # Maximum tokens to track


class PreCacheService:
    """Service for pre-caching market cap data"""
    
    def __init__(self):
        """Initialize the pre-cache service"""
        self.cache = None
        self.calculator = None
        self.jupiter_client = None
        self.tracked_tokens: Set[str] = set(POPULAR_TOKENS)
        self.token_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "request_count": 0,
            "last_requested": None,
            "last_cached": None,
            "cache_hits": 0
        })
        self.running = False
        self._tasks: List[asyncio.Task] = []
        
    async def start(self):
        """Start the pre-cache service"""
        logger.info("Starting Market Cap Pre-Cache Service...")
        
        # Initialize components
        try:
            self.cache = get_cache()
            self.calculator = MarketCapCalculator(self.cache)
            self.jupiter_client = JupiterClient()
            await self.jupiter_client.__aenter__()
        except Exception as e:
            logger.error(f"Failed to initialize pre-cache service: {e}")
            raise
        
        self.running = True
        
        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._popular_token_loop()),
            asyncio.create_task(self._general_cache_loop()),
            asyncio.create_task(self._trending_token_updater()),
            asyncio.create_task(self._stats_reporter())
        ]
        
        logger.info(f"Pre-cache service started with {len(self.tracked_tokens)} tokens")
        
    async def stop(self):
        """Stop the pre-cache service"""
        logger.info("Stopping Market Cap Pre-Cache Service...")
        self.running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Cleanup
        if self.jupiter_client:
            await self.jupiter_client.__aexit__(None, None, None)
        
        logger.info("Pre-cache service stopped")
    
    async def _popular_token_loop(self):
        """Continuously refresh popular tokens"""
        while self.running:
            try:
                logger.debug("Refreshing popular tokens...")
                
                # Process popular tokens in small batches
                tokens = list(POPULAR_TOKENS)
                for i in range(0, len(tokens), 5):
                    batch = tokens[i:i+5]
                    await self._cache_batch(batch, priority="high")
                    await asyncio.sleep(1)  # Small delay between batches
                
                await asyncio.sleep(POPULAR_TOKEN_REFRESH)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in popular token loop: {e}")
                await asyncio.sleep(10)
    
    async def _general_cache_loop(self):
        """Refresh all tracked tokens periodically"""
        await asyncio.sleep(30)  # Initial delay
        
        while self.running:
            try:
                logger.info(f"Refreshing {len(self.tracked_tokens)} tracked tokens...")
                
                # Get all non-popular tokens
                other_tokens = list(self.tracked_tokens - POPULAR_TOKENS)
                
                # Sort by request frequency
                other_tokens.sort(
                    key=lambda t: self.token_stats[t]["request_count"], 
                    reverse=True
                )
                
                # Process in batches
                for i in range(0, len(other_tokens), BATCH_SIZE):
                    batch = other_tokens[i:i+BATCH_SIZE]
                    await self._cache_batch(batch, priority="normal")
                    await asyncio.sleep(5)  # Delay between batches
                
                await asyncio.sleep(CACHE_REFRESH_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in general cache loop: {e}")
                await asyncio.sleep(30)
    
    async def _cache_batch(self, tokens: List[str], priority: str = "normal"):
        """Cache a batch of tokens"""
        if not tokens:
            return
        
        # Create tasks with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALCULATIONS)
        
        async def cache_token(token: str):
            async with semaphore:
                try:
                    # Get current timestamp
                    timestamp = int(datetime.now().timestamp())
                    
                    # Calculate and cache
                    result = await self.calculator.calculate_market_cap(
                        token_mint=token,
                        timestamp=timestamp
                    )
                    
                    # Update stats
                    self.token_stats[token]["last_cached"] = timestamp
                    
                    if result.value:
                        logger.debug(
                            f"Cached {token[:8]}... MC: ${result.value:,.2f} "
                            f"({result.confidence}) via {result.source}"
                        )
                    else:
                        logger.debug(f"No MC data for {token[:8]}...")
                        
                except Exception as e:
                    logger.error(f"Error caching {token[:8]}...: {e}")
        
        # Process all tokens in parallel
        tasks = [cache_token(token) for token in tokens]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _trending_token_updater(self):
        """Update list of trending tokens periodically"""
        while self.running:
            try:
                await asyncio.sleep(600)  # Check every 10 minutes
                
                logger.info("Updating trending tokens...")
                trending = await self._fetch_trending_tokens()
                
                if trending:
                    # Add trending tokens to tracked set
                    before = len(self.tracked_tokens)
                    self.tracked_tokens.update(trending[:50])  # Top 50 trending
                    
                    # Limit total tracked tokens
                    if len(self.tracked_tokens) > MAX_TRACKED_TOKENS:
                        # Remove least requested tokens
                        tokens_by_requests = sorted(
                            self.tracked_tokens - POPULAR_TOKENS,
                            key=lambda t: self.token_stats[t]["request_count"]
                        )
                        
                        # Remove least popular
                        to_remove = len(self.tracked_tokens) - MAX_TRACKED_TOKENS
                        for token in tokens_by_requests[:to_remove]:
                            self.tracked_tokens.remove(token)
                    
                    added = len(self.tracked_tokens) - before
                    logger.info(f"Added {added} trending tokens, tracking {len(self.tracked_tokens)} total")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating trending tokens: {e}")
    
    async def _fetch_trending_tokens(self) -> List[str]:
        """Fetch trending tokens from DexScreener"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(TRENDING_TOKENS_URL, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Extract token addresses
                        tokens = []
                        for pair in data.get("pairs", [])[:100]:
                            base_token = pair.get("baseToken", {})
                            if base_token.get("address"):
                                tokens.append(base_token["address"])
                        
                        return tokens
        except Exception as e:
            logger.error(f"Failed to fetch trending tokens: {e}")
        
        return []
    
    async def _stats_reporter(self):
        """Report statistics periodically"""
        while self.running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Calculate stats
                total_cached = sum(
                    1 for token in self.tracked_tokens
                    if self.token_stats[token]["last_cached"]
                )
                
                total_requests = sum(
                    stats["request_count"] 
                    for stats in self.token_stats.values()
                )
                
                total_hits = sum(
                    stats["cache_hits"]
                    for stats in self.token_stats.values()
                )
                
                hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
                
                logger.info(
                    f"Pre-cache stats: {total_cached}/{len(self.tracked_tokens)} cached, "
                    f"{total_requests} requests, {hit_rate:.1f}% hit rate"
                )
                
                # Log top requested tokens
                top_tokens = sorted(
                    self.token_stats.items(),
                    key=lambda x: x[1]["request_count"],
                    reverse=True
                )[:10]
                
                if top_tokens:
                    logger.info("Top requested tokens:")
                    for token, stats in top_tokens:
                        logger.info(
                            f"  {token[:8]}...: {stats['request_count']} requests, "
                            f"{stats['cache_hits']} hits"
                        )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stats reporter: {e}")
    
    def track_request(self, token_mint: str, cache_hit: bool = False):
        """Track a token request for statistics"""
        self.token_stats[token_mint]["request_count"] += 1
        self.token_stats[token_mint]["last_requested"] = datetime.now()
        
        if cache_hit:
            self.token_stats[token_mint]["cache_hits"] += 1
        
        # Add to tracked tokens if frequently requested
        if (self.token_stats[token_mint]["request_count"] >= 5 and 
            token_mint not in self.tracked_tokens):
            self.tracked_tokens.add(token_mint)
            logger.info(f"Added frequently requested token {token_mint[:8]}... to tracking")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        total_requests = sum(stats["request_count"] for stats in self.token_stats.values())
        total_hits = sum(stats["cache_hits"] for stats in self.token_stats.values())
        
        return {
            "tracked_tokens": len(self.tracked_tokens),
            "popular_tokens": len(POPULAR_TOKENS),
            "total_requests": total_requests,
            "total_cache_hits": total_hits,
            "hit_rate": (total_hits / total_requests * 100) if total_requests > 0 else 0,
            "running": self.running
        }


# Global service instance
_service_instance: Optional[PreCacheService] = None


async def start_precache_service() -> PreCacheService:
    """Start the global pre-cache service"""
    global _service_instance
    
    if _service_instance and _service_instance.running:
        logger.warning("Pre-cache service already running")
        return _service_instance
    
    _service_instance = PreCacheService()
    await _service_instance.start()
    
    return _service_instance


async def stop_precache_service():
    """Stop the global pre-cache service"""
    global _service_instance
    
    if _service_instance:
        await _service_instance.stop()
        _service_instance = None


def get_precache_service() -> Optional[PreCacheService]:
    """Get the global pre-cache service instance"""
    return _service_instance


# Example usage
if __name__ == "__main__":
    async def test_service():
        """Test the pre-cache service"""
        # Start service
        service = await start_precache_service()
        
        print("Pre-cache service started!")
        print(f"Tracking {len(service.tracked_tokens)} tokens")
        
        # Let it run for a bit
        await asyncio.sleep(10)
        
        # Get stats
        stats = service.get_stats()
        print(f"\nService stats: {json.dumps(stats, indent=2)}")
        
        # Simulate some requests
        service.track_request("So11111111111111111111111111111111111111112", cache_hit=True)
        service.track_request("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", cache_hit=True)
        service.track_request("random_token_123", cache_hit=False)
        
        # Wait a bit more
        await asyncio.sleep(5)
        
        # Stop service
        await stop_precache_service()
        print("\nPre-cache service stopped!")
    
    asyncio.run(test_service()) 