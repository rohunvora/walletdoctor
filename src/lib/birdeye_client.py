#!/usr/bin/env python3
"""
Birdeye Client - Fallback price source for market cap calculations
Provides historical and current prices when on-chain data is unavailable
"""

import os
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import logging
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import time
import json

# Setup logging
logger = logging.getLogger(__name__)

# Environment variables
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")

# Constants
BIRDEYE_BASE_URL = "https://public-api.birdeye.so"
BIRDEYE_V2_BASE = "https://api.birdeye.so/v2"
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 5]
REQUEST_TIMEOUT = 30
RATE_LIMIT_DELAY = 0.5  # 2 requests per second max

# Special addresses
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_MINT = "So11111111111111111111111111111111111111112"
WSOL_MINT = "So11111111111111111111111111111111111111112"


class BirdeyeClient:
    """Client for Birdeye price API"""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize with optional session"""
        self.session = session
        self._owns_session = session is None
        self.api_key = BIRDEYE_API_KEY
        self._last_request_time = 0
        self.request_count = 0
        
    async def __aenter__(self):
        """Async context manager entry"""
        if self._owns_session:
            self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._owns_session and self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with API key"""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
        return headers
    
    async def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()
    
    async def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        use_v2: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Make API request with retry logic"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        # Select base URL
        base_url = BIRDEYE_V2_BASE if use_v2 else BIRDEYE_BASE_URL
        url = f"{base_url}{endpoint}"
        
        # Apply rate limiting
        await self._rate_limit()
        
        last_error = None
        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                self.request_count += 1
                
                async with self.session.get(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=ClientTimeout(total=REQUEST_TIMEOUT)
                ) as resp:
                    if resp.status == 429:
                        # Rate limited
                        retry_after = int(resp.headers.get("Retry-After", delay))
                        logger.warning(f"Birdeye rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    if resp.status == 404:
                        # Token not found
                        logger.info(f"Token not found in Birdeye: {params}")
                        return None
                    
                    resp.raise_for_status()
                    data = await resp.json()
                    
                    # Check for API errors in response
                    if data.get("success") is False:
                        error_msg = data.get("message", "Unknown error")
                        logger.error(f"Birdeye API error: {error_msg}")
                        return None
                    
                    return data
                    
            except asyncio.TimeoutError:
                last_error = f"Request timeout after {REQUEST_TIMEOUT}s"
                logger.warning(f"Timeout on attempt {attempt + 1}: {last_error}")
            except aiohttp.ClientError as e:
                last_error = str(e)
                logger.warning(f"Client error on attempt {attempt + 1}: {last_error}")
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error on attempt {attempt + 1}: {last_error}")
            
            # Wait before retry (except on last attempt)
            if attempt < len(RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)
        
        # All retries failed
        logger.error(f"All Birdeye retries failed: {last_error}")
        return None
    
    async def get_token_price(
        self,
        token_mint: str,
        quote_mint: str = USDC_MINT
    ) -> Optional[Tuple[Decimal, Dict[str, Any]]]:
        """
        Get current token price from Birdeye
        
        Args:
            token_mint: Token mint address
            quote_mint: Quote token mint (default USDC)
            
        Returns:
            Tuple of (price, metadata) or None if not available
        """
        try:
            # Use defi/price endpoint
            endpoint = "/defi/price"
            params = {
                "address": token_mint,
                "check_liquidity": "true"
            }
            
            data = await self._make_request(endpoint, params)
            if not data or "data" not in data:
                return None
            
            price_data = data["data"]
            price = price_data.get("value")
            
            if price is None:
                return None
            
            # Extract metadata
            metadata = {
                "liquidity": price_data.get("liquidity", 0),
                "volume24h": price_data.get("v24hUSD", 0),
                "priceChange24h": price_data.get("priceChange24h", 0),
                "updateTime": price_data.get("updateUnixTime", int(time.time())),
                "source": "birdeye_current"
            }
            
            return (Decimal(str(price)), metadata)
            
        except Exception as e:
            logger.error(f"Error fetching Birdeye price for {token_mint}: {e}")
            return None
    
    async def get_historical_price(
        self,
        token_mint: str,
        timestamp: int,
        quote_mint: str = USDC_MINT
    ) -> Optional[Tuple[Decimal, Dict[str, Any]]]:
        """
        Get historical token price from Birdeye
        
        Args:
            token_mint: Token mint address
            timestamp: Unix timestamp for historical price
            quote_mint: Quote token mint (default USDC)
            
        Returns:
            Tuple of (price, metadata) or None if not available
        """
        try:
            # Use history/price endpoint
            endpoint = "/defi/history_price"
            
            # Birdeye expects timestamps in seconds
            params = {
                "address": token_mint,
                "address_type": "token",
                "type": "1H",  # 1 hour intervals
                "time_from": timestamp - 3600,  # 1 hour before
                "time_to": timestamp + 3600     # 1 hour after
            }
            
            data = await self._make_request(endpoint, params)
            if not data or "data" not in data or "items" not in data["data"]:
                return None
            
            items = data["data"]["items"]
            if not items:
                return None
            
            # Find closest price to requested timestamp
            closest_item = None
            min_diff = float('inf')
            
            for item in items:
                item_time = item.get("unixTime", 0)
                diff = abs(item_time - timestamp)
                if diff < min_diff:
                    min_diff = diff
                    closest_item = item
            
            if not closest_item or "value" not in closest_item:
                return None
            
            # Extract price and metadata
            price = closest_item["value"]
            metadata = {
                "timestamp": closest_item.get("unixTime", timestamp),
                "timeDiff": min_diff,
                "source": "birdeye_historical"
            }
            
            return (Decimal(str(price)), metadata)
            
        except Exception as e:
            logger.error(f"Error fetching historical price for {token_mint}: {e}")
            return None
    
    async def get_token_market_data(
        self,
        token_mint: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive market data for a token
        
        Args:
            token_mint: Token mint address
            
        Returns:
            Market data dict or None
        """
        try:
            endpoint = "/defi/token_overview"
            params = {"address": token_mint}
            
            data = await self._make_request(endpoint, params)
            if not data or "data" not in data:
                return None
            
            market_data = data["data"]
            
            # Extract relevant fields
            return {
                "price": market_data.get("price", 0),
                "marketCap": market_data.get("mc", 0),
                "fdv": market_data.get("fdv", 0),
                "liquidity": market_data.get("liquidity", 0),
                "volume24h": market_data.get("v24hUSD", 0),
                "priceChange24h": market_data.get("priceChange24h", 0),
                "holder": market_data.get("holder", 0),
                "decimals": market_data.get("decimals", 0),
                "supply": market_data.get("supply", 0),
                "lastTradeTime": market_data.get("lastTradeUnixTime", 0)
            }
            
        except Exception as e:
            logger.error(f"Error fetching market data for {token_mint}: {e}")
            return None
    
    async def batch_get_prices(
        self,
        token_mints: List[str],
        quote_mint: str = USDC_MINT
    ) -> Dict[str, Optional[Tuple[Decimal, Dict[str, Any]]]]:
        """
        Get prices for multiple tokens
        
        Args:
            token_mints: List of token mint addresses
            quote_mint: Quote token mint
            
        Returns:
            Dict mapping token_mint to (price, metadata) or None
        """
        results = {}
        
        # Process tokens one by one due to rate limits
        for token_mint in token_mints:
            try:
                price_data = await self.get_token_price(token_mint, quote_mint)
                results[token_mint] = price_data
            except Exception as e:
                logger.error(f"Error in batch price fetch for {token_mint}: {e}")
                results[token_mint] = None
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            "request_count": self.request_count,
            "api_key_set": bool(self.api_key),
            "base_url": BIRDEYE_BASE_URL
        }


# Convenience functions
async def get_birdeye_price(
    token_mint: str,
    quote_mint: str = USDC_MINT,
    timestamp: Optional[int] = None
) -> Optional[Tuple[Decimal, str, Dict[str, Any]]]:
    """
    Get token price from Birdeye with confidence indicator
    
    Args:
        token_mint: Token mint address
        quote_mint: Quote token mint
        timestamp: Optional timestamp for historical price
        
    Returns:
        Tuple of (price, source, metadata) or None
    """
    async with BirdeyeClient() as client:
        if timestamp:
            # Historical price
            result = await client.get_historical_price(token_mint, timestamp, quote_mint)
            if result:
                price, metadata = result
                return (price, "birdeye_historical", metadata)
        else:
            # Current price
            result = await client.get_token_price(token_mint, quote_mint)
            if result:
                price, metadata = result
                return (price, "birdeye_current", metadata)
    
    return None


async def get_market_cap_from_birdeye(token_mint: str) -> Optional[Tuple[float, str]]:
    """
    Get market cap directly from Birdeye
    
    Args:
        token_mint: Token mint address
        
    Returns:
        Tuple of (market_cap, source) or None
    """
    async with BirdeyeClient() as client:
        market_data = await client.get_token_market_data(token_mint)
        if market_data and market_data.get("marketCap"):
            return (market_data["marketCap"], "birdeye_mc")
    
    return None


# Example usage
if __name__ == "__main__":
    async def test_birdeye():
        """Test Birdeye client"""
        async with BirdeyeClient() as client:
            # Test current price (SOL)
            print("Testing current SOL price...")
            result = await client.get_token_price(SOL_MINT)
            if result:
                price, metadata = result
                print(f"SOL price: ${price:.2f}")
                print(f"Metadata: {metadata}")
            else:
                print("No price data available")
            
            # Test historical price
            print("\nTesting historical price...")
            timestamp = int(time.time()) - 86400  # 24 hours ago
            result = await client.get_historical_price(SOL_MINT, timestamp)
            if result:
                price, metadata = result
                print(f"SOL price 24h ago: ${price:.2f}")
                print(f"Metadata: {metadata}")
            
            # Test market data
            print("\nTesting market data...")
            market_data = await client.get_token_market_data(SOL_MINT)
            if market_data:
                print(f"Market cap: ${market_data.get('marketCap', 0):,.0f}")
                print(f"24h volume: ${market_data.get('volume24h', 0):,.0f}")
                print(f"Liquidity: ${market_data.get('liquidity', 0):,.0f}")
            
            # Get stats
            print(f"\nClient stats: {client.get_stats()}")
    
    # Run test
    asyncio.run(test_birdeye()) 