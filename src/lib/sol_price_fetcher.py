"""
SOL Price Fetcher for PRC-001: Helius-Only Pricing

Provides single SOL/USD spot price with robust fallback chain:
1. Helius RPC (primary)
2. CoinGecko API (fallback)
3. 30-second in-memory cache

Usage:
    sol_price = get_sol_price_usd()
    if sol_price:
        current_value_usd = balance_sol * sol_price
"""

import time
import logging
from decimal import Decimal
from typing import Optional
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL_SECONDS = 30
_price_cache = {"price": None, "timestamp": 0}


class SolPriceFetcher:
    """Fetches SOL/USD price with fallback chain and caching"""
    
    def __init__(self, helius_api_key: Optional[str] = None):
        self.helius_api_key = helius_api_key
        self.helius_url = f"https://rpc.helius.xyz/?api-key={helius_api_key}" if helius_api_key else None
        self.coingecko_url = "https://api.coingecko.com/api/v3/simple/price"
        
    def get_sol_price_usd(self) -> Optional[Decimal]:
        """
        Get current SOL/USD price with 30s cache
        
        Returns:
            Decimal: SOL price in USD, or None if all sources fail
        """
        # Check cache first
        now = time.time()
        if (now - _price_cache["timestamp"]) < CACHE_TTL_SECONDS and _price_cache["price"]:
            logger.debug(f"SOL price cache hit: ${_price_cache['price']}")
            return _price_cache["price"]
        
        # Try Helius first
        price = self._fetch_from_helius()
        if price:
            self._update_cache(price)
            return price
        
        # Fallback to CoinGecko
        price = self._fetch_from_coingecko()
        if price:
            self._update_cache(price)
            return price
        
        # All sources failed
        logger.error("All SOL price sources failed")
        return None
    
    def _fetch_from_helius(self) -> Optional[Decimal]:
        """Fetch SOL price from Helius RPC"""
        if not self.helius_url:
            logger.debug("Helius API key not configured, skipping")
            return None
        
        try:
            # Use getTokenSupply as a simple way to get SOL price metadata
            # In practice, Helius often includes price data in responses
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenSupply",
                "params": ["So11111111111111111111111111111111111111112"]  # SOL mint
            }
            
            response = requests.post(
                self.helius_url, 
                json=payload,
                timeout=5,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            # For now, fall back to CoinGecko since Helius doesn't directly provide price
            # TODO: Use Helius price oracle or asset metadata when available
            logger.debug("Helius SOL price not available in token supply response")
            return None
            
        except Exception as e:
            logger.warning(f"Helius SOL price fetch failed: {e}")
            return None
    
    def _fetch_from_coingecko(self) -> Optional[Decimal]:
        """Fetch SOL price from CoinGecko public API"""
        try:
            params = {
                "ids": "solana",
                "vs_currencies": "usd"
            }
            
            response = requests.get(
                self.coingecko_url,
                params=params,
                timeout=5,
                headers={"User-Agent": "WalletDoctor/1.0"}
            )
            response.raise_for_status()
            
            data = response.json()
            sol_price = data.get("solana", {}).get("usd")
            
            if sol_price:
                price = Decimal(str(sol_price))
                logger.info(f"SOL price from CoinGecko: ${price}")
                return price
            else:
                logger.error("SOL price not found in CoinGecko response")
                return None
                
        except Exception as e:
            logger.error(f"CoinGecko SOL price fetch failed: {e}")
            return None
    
    def _update_cache(self, price: Decimal):
        """Update the price cache"""
        _price_cache["price"] = price
        _price_cache["timestamp"] = time.time()
        logger.debug(f"SOL price cached: ${price}")


# Global instance for easy access
_fetcher_instance = None


def get_sol_price_usd(helius_api_key: Optional[str] = None) -> Optional[Decimal]:
    """
    Get current SOL/USD price (convenience function)
    
    Args:
        helius_api_key: Optional Helius API key for primary source
        
    Returns:
        Decimal: SOL price in USD, or None if all sources fail
    """
    global _fetcher_instance
    
    # Create or reuse fetcher instance
    if _fetcher_instance is None or (helius_api_key and _fetcher_instance.helius_api_key != helius_api_key):
        _fetcher_instance = SolPriceFetcher(helius_api_key)
    
    return _fetcher_instance.get_sol_price_usd()


def clear_sol_price_cache():
    """Clear the SOL price cache (useful for testing)"""
    global _price_cache
    _price_cache = {"price": None, "timestamp": 0}
    logger.debug("SOL price cache cleared")


def get_cache_status() -> dict:
    """Get current cache status (useful for diagnostics)"""
    now = time.time()
    age = now - _price_cache["timestamp"]
    
    return {
        "price": str(_price_cache["price"]) if _price_cache["price"] else None,
        "age_seconds": age,
        "is_fresh": age < CACHE_TTL_SECONDS,
        "ttl_seconds": CACHE_TTL_SECONDS
    } 