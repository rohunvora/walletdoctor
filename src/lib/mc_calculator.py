#!/usr/bin/env python3
"""
Market Cap Calculator - Orchestrates supply and price data to calculate MC with confidence
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass

# Setup logging
logger = logging.getLogger(__name__)

# Import our modules
from .helius_supply import get_token_supply_at_slot
from .amm_price import get_amm_price
from .mc_cache import MarketCapCache, MarketCapData, get_cache
from .birdeye_client import get_birdeye_price, get_market_cap_from_birdeye
from .dexscreener_client import get_dexscreener_price, get_market_cap_from_dexscreener
from .jupiter_client import get_jupiter_price

# Constants
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_MINT = "So11111111111111111111111111111111111111112"

# Confidence levels
CONFIDENCE_HIGH = "high"      # Primary sources (Helius + AMM)
CONFIDENCE_EST = "est"        # Fallback sources (Birdeye, DexScreener)
CONFIDENCE_UNAVAILABLE = "unavailable"  # No data available


@dataclass
class MarketCapResult:
    """Result from market cap calculation"""
    value: Optional[float]  # Market cap in USD
    confidence: str         # high, est, or unavailable
    source: Optional[str]   # Data source used
    supply: Optional[float] # Token supply (for debugging)
    price: Optional[float]  # Token price (for debugging)
    timestamp: int         # Unix timestamp


class MarketCapCalculator:
    """Calculates market cap by orchestrating supply and price data"""
    
    def __init__(self, cache: Optional[MarketCapCache] = None):
        """Initialize with optional cache"""
        self.cache = cache
        self._cache_enabled = cache is not None
        
    async def calculate_market_cap(
        self,
        token_mint: str,
        slot: Optional[int] = None,
        timestamp: Optional[int] = None
    ) -> MarketCapResult:
        """
        Calculate market cap for a token at a specific slot/time
        
        Args:
            token_mint: Token mint address
            slot: Optional slot number for historical calculation
            timestamp: Optional unix timestamp for cache lookup
            
        Returns:
            MarketCapResult with value and confidence
        """
        logger.info(f"Calculating MC for {token_mint[:8]}... at slot {slot}")
        
        # Check cache first if available
        if self._cache_enabled and timestamp:
            cached = await self._check_cache(token_mint, timestamp)
            if cached:
                return cached
        
        # Try primary sources (Helius + AMM)
        result = await self._try_primary_sources(token_mint, slot)
        if result:
            # Cache the result
            if self._cache_enabled and timestamp:
                await self._cache_result(token_mint, timestamp, result)
            return result
        
        # Try fallback sources
        result = await self._try_fallback_sources(token_mint, slot, timestamp)
        if result:
            # Cache the result
            if self._cache_enabled and timestamp:
                await self._cache_result(token_mint, timestamp, result)
            return result
        
        # No data available
        return MarketCapResult(
            value=None,
            confidence=CONFIDENCE_UNAVAILABLE,
            source=None,
            supply=None,
            price=None,
            timestamp=timestamp or int(datetime.now().timestamp())
        )
    
    async def _check_cache(
        self,
        token_mint: str,
        timestamp: int
    ) -> Optional[MarketCapResult]:
        """Check cache for existing market cap data"""
        if not self.cache:
            return None
            
        try:
            cached_data = self.cache.get(token_mint, timestamp)
            if cached_data:
                logger.info(f"Cache hit for {token_mint[:8]}... MC: ${cached_data.value:,.2f}")
                return MarketCapResult(
                    value=cached_data.value,
                    confidence=cached_data.confidence,
                    source=f"cache_{cached_data.source}" if cached_data.source else "cache",
                    supply=None,
                    price=None,
                    timestamp=cached_data.timestamp
                )
        except Exception as e:
            logger.error(f"Cache lookup error: {e}")
            
        return None
    
    async def _try_primary_sources(
        self,
        token_mint: str,
        slot: Optional[int]
    ) -> Optional[MarketCapResult]:
        """Try primary sources: Helius supply + AMM price"""
        try:
            # Get token supply from Helius
            supply = await get_token_supply_at_slot(token_mint, slot)
            if not supply:
                logger.warning(f"No supply data from Helius for {token_mint[:8]}...")
                return None
            
            # Get price from AMM pools
            price_result = await get_amm_price(token_mint, USDC_MINT, slot)
            if not price_result:
                logger.warning(f"No AMM price for {token_mint[:8]}...")
                return None
            
            price, source, tvl = price_result
            
            # Calculate market cap
            market_cap = float(supply) * float(price)
            
            logger.info(
                f"Primary MC calculation: {token_mint[:8]}... "
                f"supply={supply:,.0f} * price=${price:.6f} = ${market_cap:,.2f}"
            )
            
            return MarketCapResult(
                value=market_cap,
                confidence=CONFIDENCE_HIGH,
                source=f"helius_{source}",
                supply=float(supply),
                price=float(price),
                timestamp=int(datetime.now().timestamp())
            )
            
        except Exception as e:
            logger.error(f"Primary source error: {e}")
            return None
    
    async def _try_fallback_sources(
        self,
        token_mint: str,
        slot: Optional[int],
        timestamp: Optional[int] = None
    ) -> Optional[MarketCapResult]:
        """Try fallback sources: Birdeye, Jupiter, then DexScreener"""
        logger.info(f"Trying fallback sources for {token_mint[:8]}...")
        
        # Try Birdeye first
        result = await self._try_birdeye_fallback(token_mint, slot, timestamp)
        if result:
            return result
        
        # Try Jupiter as second fallback
        result = await self._try_jupiter_fallback(token_mint, slot, timestamp)
        if result:
            return result
        
        # Try DexScreener as last resort
        result = await self._try_dexscreener_fallback(token_mint, slot, timestamp)
        if result:
            return result
        
        logger.warning(f"All fallback sources failed for {token_mint[:8]}...")
        return None
    
    async def _try_birdeye_fallback(
        self,
        token_mint: str,
        slot: Optional[int],
        timestamp: Optional[int] = None
    ) -> Optional[MarketCapResult]:
        """Try Birdeye as fallback source"""
        try:
            # First, try to get market cap directly from Birdeye
            mc_result = await get_market_cap_from_birdeye(token_mint)
            if mc_result:
                market_cap, source = mc_result
                logger.info(f"Got MC directly from Birdeye: ${market_cap:,.2f}")
                
                return MarketCapResult(
                    value=market_cap,
                    confidence=CONFIDENCE_EST,
                    source=source,
                    supply=None,  # Not available from direct MC
                    price=None,   # Not available from direct MC
                    timestamp=timestamp or int(datetime.now().timestamp())
                )
            
            # If no direct MC, try to calculate from Birdeye price + Helius supply
            # Get supply (might work even if AMM price didn't)
            supply = await get_token_supply_at_slot(token_mint, slot)
            if not supply:
                logger.warning(f"No supply for Birdeye fallback MC calculation")
                return None
            
            # Get Birdeye price
            price_data = await get_birdeye_price(token_mint, USDC_MINT, timestamp)
            if not price_data:
                logger.warning(f"No Birdeye price for {token_mint[:8]}...")
                return None
            
            price, source, metadata = price_data
            
            # Calculate market cap
            market_cap = float(supply) * float(price)
            
            logger.info(
                f"Birdeye fallback MC: {token_mint[:8]}... "
                f"supply={supply:,.0f} * price=${price:.6f} = ${market_cap:,.2f}"
            )
            
            return MarketCapResult(
                value=market_cap,
                confidence=CONFIDENCE_EST,
                source=f"helius_{source}",
                supply=float(supply),
                price=float(price),
                timestamp=timestamp or int(datetime.now().timestamp())
            )
            
        except Exception as e:
            logger.error(f"Birdeye fallback error: {e}")
            return None
    
    async def _try_jupiter_fallback(
        self,
        token_mint: str,
        slot: Optional[int],
        timestamp: Optional[int] = None
    ) -> Optional[MarketCapResult]:
        """Try Jupiter as fallback source"""
        try:
            # Get supply from Helius
            supply = await get_token_supply_at_slot(token_mint, slot)
            if not supply:
                logger.warning(f"No supply for Jupiter fallback MC calculation")
                return None
            
            # Get Jupiter price (try quote API for better accuracy on illiquid tokens)
            price_data = await get_jupiter_price(token_mint, USDC_MINT, use_quote=True)
            if not price_data:
                # Fallback to regular price API
                price_data = await get_jupiter_price(token_mint, USDC_MINT, use_quote=False)
                if not price_data:
                    logger.warning(f"No Jupiter price for {token_mint[:8]}...")
                    return None
            
            price, source, metadata = price_data
            
            # Calculate market cap
            market_cap = float(supply) * float(price)
            
            logger.info(
                f"Jupiter fallback MC: {token_mint[:8]}... "
                f"supply={supply:,.0f} * price=${price:.6f} = ${market_cap:,.2f}"
            )
            
            return MarketCapResult(
                value=market_cap,
                confidence=CONFIDENCE_EST,
                source=f"helius_{source}",
                supply=float(supply),
                price=float(price),
                timestamp=timestamp or int(datetime.now().timestamp())
            )
            
        except Exception as e:
            logger.error(f"Jupiter fallback error: {e}")
            return None
    
    async def _try_dexscreener_fallback(
        self,
        token_mint: str,
        slot: Optional[int],
        timestamp: Optional[int] = None
    ) -> Optional[MarketCapResult]:
        """Try DexScreener as final fallback source"""
        try:
            # First, try to get market cap directly from DexScreener
            mc_result = await get_market_cap_from_dexscreener(token_mint)
            if mc_result:
                market_cap, source = mc_result
                logger.info(f"Got MC directly from DexScreener: ${market_cap:,.2f}")
                
                return MarketCapResult(
                    value=market_cap,
                    confidence=CONFIDENCE_EST,
                    source=source,
                    supply=None,  # Not available from direct MC
                    price=None,   # Not available from direct MC
                    timestamp=timestamp or int(datetime.now().timestamp())
                )
            
            # If no direct MC, try to calculate from DexScreener price + Helius supply
            # Get supply (might work even if other sources didn't)
            supply = await get_token_supply_at_slot(token_mint, slot)
            if not supply:
                logger.warning(f"No supply for DexScreener fallback MC calculation")
                return None
            
            # Get DexScreener price
            price_data = await get_dexscreener_price(token_mint, USDC_MINT)
            if not price_data:
                logger.warning(f"No DexScreener price for {token_mint[:8]}...")
                return None
            
            price, source, metadata = price_data
            
            # Calculate market cap
            market_cap = float(supply) * float(price)
            
            logger.info(
                f"DexScreener fallback MC: {token_mint[:8]}... "
                f"supply={supply:,.0f} * price=${price:.6f} = ${market_cap:,.2f}"
            )
            
            return MarketCapResult(
                value=market_cap,
                confidence=CONFIDENCE_EST,
                source=f"helius_{source}",
                supply=float(supply),
                price=float(price),
                timestamp=timestamp or int(datetime.now().timestamp())
            )
            
        except Exception as e:
            logger.error(f"DexScreener fallback error: {e}")
            return None
    
    async def _cache_result(
        self,
        token_mint: str,
        timestamp: int,
        result: MarketCapResult
    ) -> None:
        """Cache the market cap result"""
        if not self.cache or not result.value:
            return
            
        try:
            mc_data = MarketCapData(
                value=result.value,
                confidence=result.confidence,
                timestamp=timestamp,
                source=result.source
            )
            
            self.cache.set(token_mint, timestamp, mc_data)
            logger.debug(f"Cached MC for {token_mint[:8]}... at {timestamp}")
            
        except Exception as e:
            logger.error(f"Failed to cache MC: {e}")
    
    async def get_batch_market_caps(
        self,
        requests: list[Tuple[str, Optional[int], Optional[int]]]
    ) -> Dict[str, MarketCapResult]:
        """
        Get market caps for multiple tokens in batch
        
        Args:
            requests: List of (token_mint, slot, timestamp) tuples
            
        Returns:
            Dict mapping token_mint to MarketCapResult
        """
        tasks = []
        for token_mint, slot, timestamp in requests:
            task = self.calculate_market_cap(token_mint, slot, timestamp)
            tasks.append((token_mint, task))
        
        results = {}
        for token_mint, task in tasks:
            try:
                result = await task
                results[token_mint] = result
            except Exception as e:
                logger.error(f"Batch MC error for {token_mint}: {e}")
                results[token_mint] = MarketCapResult(
                    value=None,
                    confidence=CONFIDENCE_UNAVAILABLE,
                    source=None,
                    supply=None,
                    price=None,
                    timestamp=int(datetime.now().timestamp())
                )
        
        return results


# Convenience function
async def calculate_market_cap(
    token_mint: str,
    slot: Optional[int] = None,
    timestamp: Optional[int] = None,
    use_cache: bool = True
) -> MarketCapResult:
    """
    Calculate market cap for a token
    
    Args:
        token_mint: Token mint address
        slot: Optional slot for historical calculation
        timestamp: Optional timestamp for cache
        use_cache: Whether to use cache (default True)
        
    Returns:
        MarketCapResult with value and confidence
    """
    cache = None
    if use_cache:
        try:
            cache = get_cache()
        except:
            logger.warning("Cache not available, proceeding without cache")
    
    calculator = MarketCapCalculator(cache)
    return await calculator.calculate_market_cap(token_mint, slot, timestamp)


# Example usage
if __name__ == "__main__":
    async def test_calculator():
        """Test the MC calculator"""
        # Test with SOL (should work with mock data)
        result = await calculate_market_cap(SOL_MINT, use_cache=False)
        
        if result.value:
            print(f"SOL Market Cap: ${result.value:,.2f}")
            print(f"Confidence: {result.confidence}")
            print(f"Source: {result.source}")
            print(f"Supply: {result.supply:,.0f}")
            print(f"Price: ${result.price:.4f}")
        else:
            print(f"No market cap available: {result.confidence}")
    
    asyncio.run(test_calculator()) 