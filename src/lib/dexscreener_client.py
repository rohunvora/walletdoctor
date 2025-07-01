#!/usr/bin/env python3
"""
DexScreener Client - Additional fallback price source for market cap calculations
Provides real-time DEX prices when Birdeye is unavailable
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

# Constants
DEXSCREENER_BASE_URL = "https://api.dexscreener.com/latest"
MAX_RETRIES = 3
RETRY_DELAYS = [0.5, 1, 2]  # Shorter delays as DexScreener is usually fast
REQUEST_TIMEOUT = 15  # Shorter timeout
NO_RATE_LIMIT = True  # DexScreener has no documented rate limits

# Special addresses
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_MINT = "So11111111111111111111111111111111111111112"
WSOL_MINT = "So11111111111111111111111111111111111111112"

# Chain identifier for Solana
SOLANA_CHAIN = "solana"


class DexScreenerClient:
    """Client for DexScreener API - no authentication required"""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize with optional session"""
        self.session = session
        self._owns_session = session is None
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
    
    async def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make API request with retry logic"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        url = f"{DEXSCREENER_BASE_URL}{endpoint}"
        
        last_error = None
        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                self.request_count += 1
                
                async with self.session.get(
                    url,
                    params=params,
                    timeout=ClientTimeout(total=REQUEST_TIMEOUT)
                ) as resp:
                    if resp.status == 404:
                        # Token/pair not found
                        logger.info(f"Token not found in DexScreener: {endpoint}")
                        return None
                    
                    resp.raise_for_status()
                    data = await resp.json()
                    
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
        logger.error(f"All DexScreener retries failed: {last_error}")
        return None
    
    async def get_token_pairs(
        self,
        token_mint: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get all pairs for a token
        
        Args:
            token_mint: Token mint address
            
        Returns:
            List of pair data or None
        """
        try:
            # DexScreener uses token address endpoint
            endpoint = f"/dex/tokens/{token_mint}"
            
            data = await self._make_request(endpoint)
            if not data:
                return None
            
            # Extract pairs
            pairs = data.get("pairs", [])
            
            # Filter for Solana pairs only
            solana_pairs = [p for p in pairs if p.get("chainId") == SOLANA_CHAIN]
            
            return solana_pairs if solana_pairs else None
            
        except Exception as e:
            logger.error(f"Error fetching token pairs for {token_mint}: {e}")
            return None
    
    async def get_pair_by_address(
        self,
        pair_address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific pair data
        
        Args:
            pair_address: Pair contract address
            
        Returns:
            Pair data or None
        """
        try:
            endpoint = f"/dex/pairs/{SOLANA_CHAIN}/{pair_address}"
            
            data = await self._make_request(endpoint)
            if not data:
                return None
            
            # Get the pair
            pair = data.get("pair")
            return pair
            
        except Exception as e:
            logger.error(f"Error fetching pair {pair_address}: {e}")
            return None
    
    async def get_token_price(
        self,
        token_mint: str,
        quote_mint: str = USDC_MINT
    ) -> Optional[Tuple[Decimal, Dict[str, Any]]]:
        """
        Get token price from DexScreener
        
        Args:
            token_mint: Token mint address
            quote_mint: Quote token mint (default USDC)
            
        Returns:
            Tuple of (price, metadata) or None
        """
        try:
            # Get all pairs for the token
            pairs = await self.get_token_pairs(token_mint)
            if not pairs:
                logger.info(f"No pairs found for {token_mint[:8]}...")
                return None
            
            # Find best pair (highest liquidity with quote token)
            best_pair = None
            highest_liquidity = 0
            
            for pair in pairs:
                # Check if this pair has our quote token
                base_token = pair.get("baseToken", {})
                quote_token = pair.get("quoteToken", {})
                
                # Determine if token is base or quote
                is_base = base_token.get("address", "").lower() == token_mint.lower()
                is_quote_match = False
                
                if is_base:
                    is_quote_match = quote_token.get("address", "").lower() == quote_mint.lower()
                else:
                    is_quote_match = base_token.get("address", "").lower() == quote_mint.lower()
                
                # Skip if not matching quote token
                if not is_quote_match:
                    continue
                
                # Check liquidity
                liquidity_usd = pair.get("liquidity", {}).get("usd", 0)
                if liquidity_usd > highest_liquidity:
                    highest_liquidity = liquidity_usd
                    best_pair = pair
            
            if not best_pair:
                # No pair with desired quote token, use highest liquidity pair
                best_pair = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0))
            
            # Extract price
            price_usd = best_pair.get("priceUsd")
            if not price_usd:
                return None
            
            # Build metadata
            metadata = {
                "pairAddress": best_pair.get("pairAddress"),
                "dexId": best_pair.get("dexId"),
                "liquidity": best_pair.get("liquidity", {}).get("usd", 0),
                "volume24h": best_pair.get("volume", {}).get("h24", 0),
                "priceChange24h": best_pair.get("priceChange", {}).get("h24", 0),
                "txCount24h": best_pair.get("txns", {}).get("h24", {}).get("buys", 0) + 
                            best_pair.get("txns", {}).get("h24", {}).get("sells", 0),
                "fdv": best_pair.get("fdv", 0),
                "marketCap": best_pair.get("marketCap", 0),
                "source": "dexscreener"
            }
            
            return (Decimal(str(price_usd)), metadata)
            
        except Exception as e:
            logger.error(f"Error getting DexScreener price for {token_mint}: {e}")
            return None
    
    async def get_market_cap(
        self,
        token_mint: str
    ) -> Optional[Tuple[float, str]]:
        """
        Get market cap from DexScreener
        
        Args:
            token_mint: Token mint address
            
        Returns:
            Tuple of (market_cap, source) or None
        """
        try:
            # Get token pairs
            pairs = await self.get_token_pairs(token_mint)
            if not pairs:
                return None
            
            # Get highest liquidity pair
            best_pair = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0))
            
            # Check for market cap
            market_cap = best_pair.get("marketCap")
            if market_cap and market_cap > 0:
                return (float(market_cap), "dexscreener_mc")
            
            # Try FDV as fallback
            fdv = best_pair.get("fdv")
            if fdv and fdv > 0:
                return (float(fdv), "dexscreener_fdv")
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting market cap for {token_mint}: {e}")
            return None
    
    async def search_tokens(
        self,
        query: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Search for tokens by name or symbol
        
        Args:
            query: Search query
            
        Returns:
            List of matching tokens or None
        """
        try:
            endpoint = "/dex/search"
            params = {"q": query}
            
            data = await self._make_request(endpoint, params)
            if not data:
                return None
            
            # Extract pairs and filter for Solana
            pairs = data.get("pairs", [])
            solana_pairs = [p for p in pairs if p.get("chainId") == SOLANA_CHAIN]
            
            return solana_pairs if solana_pairs else None
            
        except Exception as e:
            logger.error(f"Error searching tokens: {e}")
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
        
        # DexScreener has no rate limits, so we can parallelize
        tasks = []
        for token_mint in token_mints:
            task = self.get_token_price(token_mint, quote_mint)
            tasks.append((token_mint, task))
        
        # Execute all tasks in parallel
        for token_mint, task in tasks:
            try:
                result = await task
                results[token_mint] = result
            except Exception as e:
                logger.error(f"Error in batch price fetch for {token_mint}: {e}")
                results[token_mint] = None
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            "request_count": self.request_count,
            "base_url": DEXSCREENER_BASE_URL,
            "rate_limited": not NO_RATE_LIMIT
        }


# Convenience functions
async def get_dexscreener_price(
    token_mint: str,
    quote_mint: str = USDC_MINT
) -> Optional[Tuple[Decimal, str, Dict[str, Any]]]:
    """
    Get token price from DexScreener
    
    Args:
        token_mint: Token mint address
        quote_mint: Quote token mint
        
    Returns:
        Tuple of (price, source, metadata) or None
    """
    async with DexScreenerClient() as client:
        result = await client.get_token_price(token_mint, quote_mint)
        if result:
            price, metadata = result
            return (price, "dexscreener", metadata)
    
    return None


async def get_market_cap_from_dexscreener(token_mint: str) -> Optional[Tuple[float, str]]:
    """
    Get market cap from DexScreener
    
    Args:
        token_mint: Token mint address
        
    Returns:
        Tuple of (market_cap, source) or None
    """
    async with DexScreenerClient() as client:
        return await client.get_market_cap(token_mint)


# Example usage
if __name__ == "__main__":
    async def test_dexscreener():
        """Test DexScreener client"""
        async with DexScreenerClient() as client:
            # Test token price (using a well-known token)
            print("Testing SOL price...")
            result = await client.get_token_price(SOL_MINT)
            if result:
                price, metadata = result
                print(f"SOL price: ${price:.2f}")
                print(f"Liquidity: ${metadata.get('liquidity', 0):,.0f}")
                print(f"24h Volume: ${metadata.get('volume24h', 0):,.0f}")
                print(f"Market Cap: ${metadata.get('marketCap', 0):,.0f}")
            else:
                print("No price data available")
            
            # Test market cap
            print("\nTesting market cap...")
            mc_result = await client.get_market_cap(SOL_MINT)
            if mc_result:
                market_cap, source = mc_result
                print(f"Market Cap: ${market_cap:,.0f} (source: {source})")
            
            # Test search
            print("\nSearching for 'bonk'...")
            search_results = await client.search_tokens("bonk")
            if search_results:
                print(f"Found {len(search_results)} results")
                for i, pair in enumerate(search_results[:3]):
                    base = pair.get("baseToken", {})
                    print(f"  {i+1}. {base.get('symbol')} - {base.get('name')}")
            
            # Get stats
            print(f"\nClient stats: {client.get_stats()}")
    
    # Run test
    asyncio.run(test_dexscreener()) 