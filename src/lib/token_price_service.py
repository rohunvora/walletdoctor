"""
Token Price Service for PRC-002: Per-Token Pricing

Provides individual token USD prices using CoinGecko API with intelligent caching.
Replaces the broken PRC-001 SOL spot pricing with accurate per-token values.

Features:
- CoinGecko API integration for Solana tokens
- 24-hour in-memory cache to minimize API calls
- Graceful degradation on API failures
- Proper decimal handling for accurate USD values
"""

import asyncio
import aiohttp
import logging
import time
from decimal import Decimal
from typing import Optional, Dict, Tuple, List, Any
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL_SECONDS = 86400  # 24 hours
MAX_BATCH_SIZE = 100  # CoinGecko limit

# Known token mappings (mint -> coingecko_id)
KNOWN_TOKENS = {
    "So11111111111111111111111111111111111111112": "solana",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "usd-coin",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "tether",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "bonk",
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs": "ether",
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "msol",
    "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj": "lido-staked-sol",
}


class TokenPriceService:
    """Fetches token prices from CoinGecko with caching"""
    
    def __init__(self, coingecko_api_key: Optional[str] = None):
        """
        Initialize the token price service
        
        Args:
            coingecko_api_key: Optional API key for higher rate limits
        """
        self.api_key = coingecko_api_key or os.getenv("COINGECKO_API_KEY")
        self.base_url = "https://api.coingecko.com/api/v3"
        
        # In-memory cache: token_mint -> (price_usd, timestamp)
        self._price_cache: Dict[str, Tuple[Decimal, float]] = {}
        
        # Track API calls for rate limiting
        self._api_calls = []
        self._rate_limit_window = 60  # 1 minute
        self._rate_limit_calls = 10 if not self.api_key else 500  # Free tier vs paid
        
        # Session for connection pooling
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()
            
    async def get_token_price_usd(
        self, 
        token_mint: str, 
        token_symbol: Optional[str] = None,
        force_refresh: bool = False
    ) -> Optional[Decimal]:
        """
        Get USD price for a token
        
        Args:
            token_mint: Solana token mint address
            token_symbol: Optional token symbol for fallback lookup
            force_refresh: Skip cache and fetch fresh price
            
        Returns:
            Token price in USD or None if unavailable
        """
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_price = self._get_cached_price(token_mint)
            if cached_price is not None:
                logger.debug(f"Cache hit for {token_mint[:8]}...: ${cached_price}")
                return cached_price
        
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("Rate limit reached, returning cached price if available")
            return self._get_cached_price(token_mint, ignore_ttl=True)
        
        # Try to fetch price
        price = await self._fetch_token_price(token_mint, token_symbol)
        
        if price is not None:
            # Cache the price
            self._cache_price(token_mint, price)
            logger.info(f"Fetched price for {token_mint[:8]}...: ${price}")
        else:
            # Try stale cache as last resort
            stale_price = self._get_cached_price(token_mint, ignore_ttl=True)
            if stale_price is not None:
                logger.warning(f"Using stale cached price for {token_mint[:8]}...: ${stale_price}")
                return stale_price
                
        return price
        
    async def get_batch_prices(
        self, 
        token_mints: List[str],
        token_symbols: Optional[Dict[str, str]] = None
    ) -> Dict[str, Optional[Decimal]]:
        """
        Get prices for multiple tokens efficiently
        
        Args:
            token_mints: List of token mint addresses
            token_symbols: Optional mapping of mint -> symbol
            
        Returns:
            Dict of token_mint -> price_usd (or None)
        """
        results = {}
        uncached_mints = []
        
        # Check cache first
        for mint in token_mints:
            cached_price = self._get_cached_price(mint)
            if cached_price is not None:
                results[mint] = cached_price
            else:
                uncached_mints.append(mint)
        
        # Batch fetch uncached tokens
        if uncached_mints:
            # CoinGecko supports up to 100 tokens per request
            for i in range(0, len(uncached_mints), MAX_BATCH_SIZE):
                batch = uncached_mints[i:i + MAX_BATCH_SIZE]
                batch_prices = await self._fetch_batch_prices(batch, token_symbols)
                results.update(batch_prices)
        
        return results
        
    async def _fetch_token_price(
        self, 
        token_mint: str, 
        token_symbol: Optional[str] = None
    ) -> Optional[Decimal]:
        """Fetch price for a single token"""
        # Check if we have a known CoinGecko ID
        coingecko_id = KNOWN_TOKENS.get(token_mint)
        
        if coingecko_id:
            # Direct lookup by ID
            return await self._fetch_by_id(coingecko_id)
        
        # Try by contract address
        price = await self._fetch_by_contract(token_mint)
        if price is not None:
            return price
            
        # Fallback to symbol search if available
        if token_symbol:
            return await self._fetch_by_symbol(token_symbol)
            
        return None
        
    async def _fetch_by_id(self, coingecko_id: str) -> Optional[Decimal]:
        """Fetch price by CoinGecko ID"""
        try:
            url = f"{self.base_url}/simple/price"
            params = {
                "ids": coingecko_id,
                "vs_currencies": "usd"
            }
            
            headers = {}
            if self.api_key:
                headers["x-cg-pro-api-key"] = self.api_key
            
            if not self._session:
                self._session = aiohttp.ClientSession()
                
            async with self._session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if coingecko_id in data and "usd" in data[coingecko_id]:
                        self._record_api_call()
                        return Decimal(str(data[coingecko_id]["usd"]))
                else:
                    logger.warning(f"CoinGecko API error {resp.status} for ID {coingecko_id}")
                    
        except Exception as e:
            logger.error(f"Error fetching price by ID {coingecko_id}: {e}")
            
        return None
        
    async def _fetch_by_contract(self, contract_address: str) -> Optional[Decimal]:
        """Fetch price by Solana contract address"""
        try:
            # CoinGecko uses 'solana' as the platform ID
            url = f"{self.base_url}/simple/token_price/solana"
            params = {
                "contract_addresses": contract_address,
                "vs_currencies": "usd"
            }
            
            headers = {}
            if self.api_key:
                headers["x-cg-pro-api-key"] = self.api_key
                
            if not self._session:
                self._session = aiohttp.ClientSession()
                
            async with self._session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if contract_address.lower() in data:
                        price_data = data[contract_address.lower()]
                        if "usd" in price_data:
                            self._record_api_call()
                            return Decimal(str(price_data["usd"]))
                else:
                    logger.debug(f"Contract {contract_address[:8]}... not found on CoinGecko")
                    
        except Exception as e:
            logger.error(f"Error fetching price by contract {contract_address}: {e}")
            
        return None
        
    async def _fetch_by_symbol(self, symbol: str) -> Optional[Decimal]:
        """Fetch price by token symbol (less reliable)"""
        try:
            # Search for the token
            url = f"{self.base_url}/search"
            params = {"query": symbol.lower()}
            
            headers = {}
            if self.api_key:
                headers["x-cg-pro-api-key"] = self.api_key
                
            if not self._session:
                self._session = aiohttp.ClientSession()
                
            async with self._session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    coins = data.get("coins", [])
                    
                    # Find exact symbol match
                    for coin in coins:
                        if coin.get("symbol", "").upper() == symbol.upper():
                            coin_id = coin.get("id")
                            if coin_id:
                                self._record_api_call()
                                # Fetch price by ID
                                return await self._fetch_by_id(coin_id)
                                
        except Exception as e:
            logger.error(f"Error searching for symbol {symbol}: {e}")
            
        return None
        
    async def _fetch_batch_prices(
        self, 
        token_mints: List[str],
        token_symbols: Optional[Dict[str, str]] = None
    ) -> Dict[str, Optional[Decimal]]:
        """Fetch prices for multiple tokens in one request"""
        results = {}
        
        # Separate known tokens and unknown contracts
        known_ids = []
        unknown_contracts = []
        
        for mint in token_mints:
            if mint in KNOWN_TOKENS:
                known_ids.append(KNOWN_TOKENS[mint])
                results[mint] = None  # Placeholder
            else:
                unknown_contracts.append(mint)
        
        # Fetch known tokens by ID (more reliable)
        if known_ids:
            try:
                url = f"{self.base_url}/simple/price"
                params = {
                    "ids": ",".join(known_ids),
                    "vs_currencies": "usd"
                }
                
                headers = {}
                if self.api_key:
                    headers["x-cg-pro-api-key"] = self.api_key
                    
                if not self._session:
                    self._session = aiohttp.ClientSession()
                    
                async with self._session.get(url, params=params, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._record_api_call()
                        
                        # Map back to mint addresses
                        for mint, coingecko_id in KNOWN_TOKENS.items():
                            if mint in token_mints and coingecko_id in data:
                                if "usd" in data[coingecko_id]:
                                    price = Decimal(str(data[coingecko_id]["usd"]))
                                    results[mint] = price
                                    self._cache_price(mint, price)
                                    
            except Exception as e:
                logger.error(f"Error fetching batch prices by ID: {e}")
        
        # Fetch unknown tokens by contract
        if unknown_contracts:
            try:
                url = f"{self.base_url}/simple/token_price/solana"
                params = {
                    "contract_addresses": ",".join(unknown_contracts),
                    "vs_currencies": "usd"
                }
                
                headers = {}
                if self.api_key:
                    headers["x-cg-pro-api-key"] = self.api_key
                    
                async with self._session.get(url, params=params, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._record_api_call()
                        
                        for contract in unknown_contracts:
                            if contract.lower() in data:
                                price_data = data[contract.lower()]
                                if "usd" in price_data:
                                    price = Decimal(str(price_data["usd"]))
                                    results[contract] = price
                                    self._cache_price(contract, price)
                            else:
                                results[contract] = None
                                
            except Exception as e:
                logger.error(f"Error fetching batch prices by contract: {e}")
        
        return results
        
    def _get_cached_price(self, token_mint: str, ignore_ttl: bool = False) -> Optional[Decimal]:
        """Get price from cache"""
        if token_mint in self._price_cache:
            price, timestamp = self._price_cache[token_mint]
            
            # Check if cache is still valid
            age = time.time() - timestamp
            if ignore_ttl or age < CACHE_TTL_SECONDS:
                return price
                
        return None
        
    def _cache_price(self, token_mint: str, price: Decimal) -> None:
        """Cache a token price"""
        self._price_cache[token_mint] = (price, time.time())
        logger.debug(f"Cached price for {token_mint[:8]}...: ${price}")
        
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        now = time.time()
        
        # Remove old API calls outside the window
        self._api_calls = [t for t in self._api_calls if now - t < self._rate_limit_window]
        
        # Check if we can make another call
        return len(self._api_calls) < self._rate_limit_calls
        
    def _record_api_call(self) -> None:
        """Record an API call for rate limiting"""
        self._api_calls.append(time.time())
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        now = time.time()
        total_cached = len(self._price_cache)
        fresh_cached = sum(
            1 for _, (_, timestamp) in self._price_cache.items()
            if now - timestamp < CACHE_TTL_SECONDS
        )
        
        return {
            "total_cached": total_cached,
            "fresh_cached": fresh_cached,
            "stale_cached": total_cached - fresh_cached,
            "api_calls_in_window": len(self._api_calls),
            "rate_limit": f"{len(self._api_calls)}/{self._rate_limit_calls}"
        }
        
    def clear_cache(self) -> None:
        """Clear the price cache"""
        self._price_cache.clear()
        logger.info("Price cache cleared") 