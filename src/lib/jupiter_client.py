#!/usr/bin/env python3
"""
Jupiter Client - Aggregated DEX pricing across Solana
Provides best swap rates by aggregating multiple DEXs
"""

import os
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import logging
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal
from datetime import datetime
import time
import json

# Setup logging
logger = logging.getLogger(__name__)

# Constants
JUPITER_PRICE_API = "https://price.jup.ag/v4"
JUPITER_QUOTE_API = "https://quote-api.jup.ag/v6"
MAX_RETRIES = 3
RETRY_DELAYS = [0.5, 1, 2]
REQUEST_TIMEOUT = 20
RATE_LIMIT_DELAY = 0.1  # Jupiter is generous with rate limits

# Special addresses
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_MINT = "So11111111111111111111111111111111111111112"
WSOL_MINT = "So11111111111111111111111111111111111111112"

# Common token decimals
TOKEN_DECIMALS = {
    SOL_MINT: 9,
    USDC_MINT: 6,
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": 6,  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": 6,  # USDT
}


class JupiterClient:
    """Client for Jupiter aggregator APIs"""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize with optional session"""
        self.session = session
        self._owns_session = session is None
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
    
    async def _rate_limit(self):
        """Enforce gentle rate limiting"""
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()
    
    async def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make API request with retry logic"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        await self._rate_limit()
        
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
                        logger.info(f"Resource not found: {url}")
                        return None
                    
                    if resp.status == 429:
                        # Rate limited
                        retry_after = int(resp.headers.get("Retry-After", delay))
                        logger.warning(f"Jupiter rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
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
        logger.error(f"All Jupiter retries failed: {last_error}")
        return None
    
    async def get_token_price(
        self,
        token_mint: str,
        vs_token: str = USDC_MINT
    ) -> Optional[Tuple[Decimal, Dict[str, Any]]]:
        """
        Get token price from Jupiter Price API
        
        Args:
            token_mint: Token mint address
            vs_token: Quote token mint (default USDC)
            
        Returns:
            Tuple of (price, metadata) or None
        """
        try:
            # Jupiter Price API v4 endpoint
            url = f"{JUPITER_PRICE_API}/price"
            params = {
                "ids": token_mint,
                "vsToken": vs_token
            }
            
            data = await self._make_request(url, params)
            if not data or "data" not in data:
                return None
            
            price_data = data["data"].get(token_mint)
            if not price_data:
                return None
            
            # Extract price
            price = price_data.get("price")
            if price is None:
                return None
            
            # Build metadata
            metadata = {
                "id": price_data.get("id"),
                "vsToken": vs_token,
                "vsTokenSymbol": price_data.get("vsTokenSymbol", "USDC"),
                "confidence": price_data.get("confidence"),
                "depth": price_data.get("depth", {}),
                "source": "jupiter_price_v4"
            }
            
            return (Decimal(str(price)), metadata)
            
        except Exception as e:
            logger.error(f"Error fetching Jupiter price for {token_mint}: {e}")
            return None
    
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,  # 0.5% default slippage
    ) -> Optional[Dict[str, Any]]:
        """
        Get swap quote from Jupiter
        
        Args:
            input_mint: Input token mint
            output_mint: Output token mint
            amount: Amount in smallest units
            slippage_bps: Slippage in basis points
            
        Returns:
            Quote data or None
        """
        try:
            url = f"{JUPITER_QUOTE_API}/quote"
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": str(slippage_bps),
                "onlyDirectRoutes": "false",
                "asLegacyTransaction": "false"
            }
            
            data = await self._make_request(url, params)
            return data
            
        except Exception as e:
            logger.error(f"Error getting Jupiter quote: {e}")
            return None
    
    async def get_token_price_via_quote(
        self,
        token_mint: str,
        vs_token: str = USDC_MINT,
        amount_usd: float = 100.0  # $100 worth for price discovery
    ) -> Optional[Tuple[Decimal, Dict[str, Any]]]:
        """
        Get token price via swap quote (more accurate for illiquid tokens)
        
        Args:
            token_mint: Token mint to price
            vs_token: Quote token (default USDC)
            amount_usd: USD amount for quote
            
        Returns:
            Tuple of (price, metadata) or None
        """
        try:
            # Convert USD amount to token units (assuming vs_token is USDC-like with 6 decimals)
            vs_decimals = TOKEN_DECIMALS.get(vs_token, 6)
            amount_units = int(amount_usd * (10 ** vs_decimals))
            
            # Get quote for buying the token
            quote = await self.get_quote(
                input_mint=vs_token,
                output_mint=token_mint,
                amount=amount_units
            )
            
            if not quote:
                return None
            
            # Extract amounts
            in_amount = int(quote.get("inAmount", 0))
            out_amount = int(quote.get("outAmount", 0))
            
            if in_amount == 0 or out_amount == 0:
                return None
            
            # Get decimals
            token_decimals = TOKEN_DECIMALS.get(token_mint, 9)  # Default to 9
            
            # Calculate price
            # Price = input_amount / output_amount (adjusted for decimals)
            in_value = Decimal(in_amount) / Decimal(10 ** vs_decimals)
            out_value = Decimal(out_amount) / Decimal(10 ** token_decimals)
            
            if out_value == 0:
                return None
            
            price = in_value / out_value
            
            # Build metadata
            metadata = {
                "inputMint": vs_token,
                "outputMint": token_mint,
                "inAmount": in_amount,
                "outAmount": out_amount,
                "priceImpactPct": quote.get("priceImpactPct", 0),
                "routes": len(quote.get("routePlan", [])),
                "source": "jupiter_quote_v6"
            }
            
            return (price, metadata)
            
        except Exception as e:
            logger.error(f"Error getting price via quote: {e}")
            return None
    
    async def get_token_list(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get Jupiter's verified token list
        
        Returns:
            List of token data or None
        """
        try:
            url = "https://token.jup.ag/all"
            data = await self._make_request(url)
            # Ensure we return a list
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "tokens" in data:
                return data["tokens"]
            else:
                logger.warning(f"Unexpected token list format: {type(data)}")
                return None
            
        except Exception as e:
            logger.error(f"Error fetching token list: {e}")
            return None
    
    async def batch_get_prices(
        self,
        token_mints: List[str],
        vs_token: str = USDC_MINT
    ) -> Dict[str, Optional[Tuple[Decimal, Dict[str, Any]]]]:
        """
        Get prices for multiple tokens (Jupiter supports batch)
        
        Args:
            token_mints: List of token mint addresses
            vs_token: Quote token mint
            
        Returns:
            Dict mapping token_mint to (price, metadata) or None
        """
        try:
            # Jupiter Price API supports batch requests
            url = f"{JUPITER_PRICE_API}/price"
            params = {
                "ids": ",".join(token_mints),
                "vsToken": vs_token
            }
            
            data = await self._make_request(url, params)
            if not data or "data" not in data:
                return {mint: None for mint in token_mints}
            
            results = {}
            price_data = data["data"]
            
            for token_mint in token_mints:
                token_data = price_data.get(token_mint)
                if token_data and "price" in token_data:
                    price = token_data["price"]
                    metadata = {
                        "id": token_data.get("id"),
                        "vsToken": vs_token,
                        "vsTokenSymbol": token_data.get("vsTokenSymbol", "USDC"),
                        "confidence": token_data.get("confidence"),
                        "source": "jupiter_price_v4"
                    }
                    results[token_mint] = (Decimal(str(price)), metadata)
                else:
                    results[token_mint] = None
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch price fetch: {e}")
            return {mint: None for mint in token_mints}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            "request_count": self.request_count,
            "price_api": JUPITER_PRICE_API,
            "quote_api": JUPITER_QUOTE_API
        }


# Convenience functions
async def get_jupiter_price(
    token_mint: str,
    vs_token: str = USDC_MINT,
    use_quote: bool = False
) -> Optional[Tuple[Decimal, str, Dict[str, Any]]]:
    """
    Get token price from Jupiter
    
    Args:
        token_mint: Token mint address
        vs_token: Quote token mint
        use_quote: Use quote API instead of price API
        
    Returns:
        Tuple of (price, source, metadata) or None
    """
    async with JupiterClient() as client:
        if use_quote:
            result = await client.get_token_price_via_quote(token_mint, vs_token)
            source = "jupiter_quote"
        else:
            result = await client.get_token_price(token_mint, vs_token)
            source = "jupiter_price"
            
        if result:
            price, metadata = result
            return (price, source, metadata)
    
    return None


# Example usage
if __name__ == "__main__":
    async def test_jupiter():
        """Test Jupiter client"""
        async with JupiterClient() as client:
            # Test price API
            print("Testing Jupiter Price API...")
            result = await client.get_token_price(SOL_MINT)
            if result:
                price, metadata = result
                print(f"SOL price: ${price:.2f}")
                print(f"Metadata: {metadata}")
            else:
                print("No price data available")
            
            # Test batch prices
            print("\nTesting batch prices...")
            tokens = [SOL_MINT, "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"]  # SOL and BONK
            batch_results = await client.batch_get_prices(tokens)
            for token, result in batch_results.items():
                if result:
                    price, _ = result
                    print(f"{token[:8]}...: ${price:.6f}")
            
            # Test quote API
            print("\nTesting quote-based pricing...")
            quote_result = await client.get_token_price_via_quote(SOL_MINT)
            if quote_result:
                price, metadata = quote_result
                print(f"SOL price via quote: ${price:.2f}")
                print(f"Price impact: {metadata.get('priceImpactPct', 0):.4f}%")
            
            # Get stats
            print(f"\nClient stats: {client.get_stats()}")
    
    # Run test
    asyncio.run(test_jupiter()) 