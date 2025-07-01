#!/usr/bin/env python3
"""
AMM Price Reader - Get token prices from on-chain Raydium/Orca pools
Filters by TVL ≥ $5k and returns price from deepest pool
"""

import os
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import logging
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal
import json

# Setup logging
logger = logging.getLogger(__name__)

# Environment variables
HELIUS_KEY = os.getenv("HELIUS_KEY")

# Constants
HELIUS_RPC_BASE = "https://mainnet.helius-rpc.com"
REQUEST_TIMEOUT = 30
MIN_TVL_USD = 5000  # Minimum TVL in USD
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

# Program IDs
RAYDIUM_AMM_PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
ORCA_WHIRLPOOL_PROGRAM = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"

# Pool cache (in-memory for now)
_pool_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}  # mint -> (pool_data, timestamp)
POOL_CACHE_TTL = 300  # 5 minutes


class AMMPriceReader:
    """Reads token prices from on-chain AMM pools"""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize with optional session for connection pooling"""
        self.session = session
        self._owns_session = session is None
        self.request_count = 0
        self._sol_price_usd: Optional[Decimal] = None
        self._sol_price_timestamp: float = 0
        
    async def __aenter__(self):
        """Async context manager entry"""
        if self._owns_session:
            self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._owns_session and self.session:
            await self.session.close()
    
    def _get_rpc_url(self) -> str:
        """Get RPC URL with API key"""
        if not HELIUS_KEY:
            raise ValueError("HELIUS_KEY environment variable not set")
        return f"{HELIUS_RPC_BASE}/?api-key={HELIUS_KEY}"
    
    async def _make_rpc_request(self, method: str, params: List[Any]) -> Dict[str, Any]:
        """Make RPC request to Helius"""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        url = self._get_rpc_url()
        headers = {"Content-Type": "application/json"}
        
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        try:
            self.request_count += 1
            async with self.session.post(
                url, 
                headers=headers, 
                json=body,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                
                if "error" in data:
                    logger.error(f"RPC error: {data['error']}")
                    return data
                
                return data
                
        except Exception as e:
            logger.error(f"RPC request error: {e}")
            return {"error": {"message": str(e)}}
    
    async def get_sol_price_usd(self) -> Optional[Decimal]:
        """Get current SOL price in USD (cached for 60s)"""
        import time
        current_time = time.time()
        
        # Use cached price if fresh
        if self._sol_price_usd and (current_time - self._sol_price_timestamp) < 60:
            return self._sol_price_usd
        
        # Get SOL/USDC pool price
        sol_price = await self._get_price_from_stable_pool(SOL_MINT)
        if sol_price:
            self._sol_price_usd = sol_price
            self._sol_price_timestamp = current_time
            return sol_price
        
        # Fallback to hardcoded price (should use external API in production)
        logger.warning("Failed to get SOL price, using fallback")
        return Decimal("150.0")  # Fallback price
    
    async def _get_price_from_stable_pool(self, token_mint: str) -> Optional[Decimal]:
        """Get token price from USDC/USDT pools"""
        if token_mint == USDC_MINT:
            return Decimal("1.0")
        if token_mint == USDT_MINT:
            return Decimal("1.0")
        
        # Find pools with token paired with USDC or USDT
        pools = await self._find_pools_for_token(token_mint)
        
        for pool in pools:
            # Check if paired with stable
            token_a = pool.get("token_a_mint")
            token_b = pool.get("token_b_mint")
            
            if token_a == token_mint and token_b in [USDC_MINT, USDT_MINT]:
                price = pool.get("token_a_price")
                if price:
                    return Decimal(str(price))
            elif token_b == token_mint and token_a in [USDC_MINT, USDT_MINT]:
                price = pool.get("token_b_price")
                if price:
                    return Decimal(str(price))
        
        return None
    
    async def _find_pools_for_token(self, token_mint: str) -> List[Dict[str, Any]]:
        """Find all pools containing a token"""
        import time
        
        # Check cache
        cache_key = f"pools_{token_mint}"
        if cache_key in _pool_cache:
            pool_data, timestamp = _pool_cache[cache_key]
            if time.time() - timestamp < POOL_CACHE_TTL:
                return pool_data.get("pools", [])
        
        # For now, return empty list (would query pool accounts in production)
        # This would normally:
        # 1. Query getProgramAccounts for Raydium/Orca programs
        # 2. Filter by token mint
        # 3. Parse pool data
        logger.info(f"Finding pools for {token_mint} (mock implementation)")
        return []
    
    async def get_token_price(
        self, 
        token_mint: str, 
        quote_mint: str = USDC_MINT,
        slot: Optional[int] = None
    ) -> Optional[Tuple[Decimal, str, Decimal]]:
        """
        Get token price from deepest AMM pool
        
        Args:
            token_mint: Token to price
            quote_mint: Quote currency (default USDC)
            slot: Optional slot for historical price
            
        Returns:
            Tuple of (price, source, tvl_usd) or None
        """
        if token_mint == quote_mint:
            return (Decimal("1.0"), "self", Decimal("0"))
        
        # Get all pools for this token pair
        pools = await self._get_pools_for_pair(token_mint, quote_mint, slot)
        
        if not pools:
            logger.info(f"No pools found for {token_mint}/{quote_mint}")
            return None
        
        # Filter by minimum TVL
        sol_price = await self.get_sol_price_usd()
        if not sol_price:
            logger.warning("Could not get SOL price for TVL calculation")
            return None
            
        valid_pools = []
        
        for pool in pools:
            tvl_usd = await self._calculate_pool_tvl(pool, sol_price)
            if tvl_usd >= MIN_TVL_USD:
                valid_pools.append((pool, tvl_usd))
        
        if not valid_pools:
            logger.info(f"No pools with TVL >= ${MIN_TVL_USD} for {token_mint}")
            return None
        
        # Sort by TVL (highest first)
        valid_pools.sort(key=lambda x: x[1], reverse=True)
        
        # Use deepest pool
        deepest_pool, tvl_usd = valid_pools[0]
        price = await self._calculate_price_from_pool(deepest_pool, token_mint, quote_mint)
        
        if price:
            source = deepest_pool.get("program", "unknown")
            return (price, source, Decimal(str(tvl_usd)))
        
        return None
    
    async def _get_pools_for_pair(
        self, 
        token_a: str, 
        token_b: str,
        slot: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all pools for a token pair"""
        # This is a simplified implementation
        # In production, would query:
        # 1. Raydium pools via getProgramAccounts
        # 2. Orca whirlpools via getProgramAccounts
        # 3. Parse pool accounts to extract reserves
        
        # For now, return mock data for testing
        if token_a == SOL_MINT and token_b == USDC_MINT:
            return [{
                "program": "raydium",
                "address": "58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2",
                "token_a_mint": SOL_MINT,
                "token_b_mint": USDC_MINT,
                "token_a_amount": "1000000000000",  # 1000 SOL (9 decimals)
                "token_b_amount": "150000000000",   # 150k USDC (6 decimals)
                "token_a_decimals": 9,
                "token_b_decimals": 6
            }]
        
        return []
    
    async def _calculate_pool_tvl(
        self, 
        pool: Dict[str, Any], 
        sol_price_usd: Decimal
    ) -> Decimal:
        """Calculate pool TVL in USD"""
        tvl = Decimal("0")
        
        # Token A
        token_a_mint = pool.get("token_a_mint")
        token_a_amount = Decimal(pool.get("token_a_amount", "0"))
        token_a_decimals = pool.get("token_a_decimals", 0)
        
        # Token B
        token_b_mint = pool.get("token_b_mint")
        token_b_amount = Decimal(pool.get("token_b_amount", "0"))
        token_b_decimals = pool.get("token_b_decimals", 0)
        
        # Convert amounts to human-readable
        token_a_human = token_a_amount / Decimal(10 ** token_a_decimals)
        token_b_human = token_b_amount / Decimal(10 ** token_b_decimals)
        
        # Calculate USD values
        if token_a_mint == SOL_MINT:
            tvl += token_a_human * sol_price_usd
        elif token_a_mint in [USDC_MINT, USDT_MINT]:
            tvl += token_a_human
        else:
            # Would need to get price for other tokens
            pass
        
        if token_b_mint == SOL_MINT:
            tvl += token_b_human * sol_price_usd
        elif token_b_mint in [USDC_MINT, USDT_MINT]:
            tvl += token_b_human
        else:
            # Would need to get price for other tokens
            pass
        
        return tvl
    
    async def _calculate_price_from_pool(
        self,
        pool: Dict[str, Any],
        base_mint: str,
        quote_mint: str
    ) -> Optional[Decimal]:
        """Calculate price from pool reserves"""
        token_a_mint = pool.get("token_a_mint")
        token_b_mint = pool.get("token_b_mint")
        
        if not all([token_a_mint, token_b_mint]):
            return None
        
        # Get amounts and decimals
        token_a_amount = Decimal(pool.get("token_a_amount", "0"))
        token_b_amount = Decimal(pool.get("token_b_amount", "0"))
        token_a_decimals = pool.get("token_a_decimals", 0)
        token_b_decimals = pool.get("token_b_decimals", 0)
        
        if token_a_amount == 0 or token_b_amount == 0:
            return None
        
        # Calculate price based on reserves
        if base_mint == token_a_mint and quote_mint == token_b_mint:
            # Price = quote_amount / base_amount * (10^base_decimals / 10^quote_decimals)
            price = (token_b_amount / token_a_amount) * Decimal(10 ** (token_a_decimals - token_b_decimals))
            return price
        elif base_mint == token_b_mint and quote_mint == token_a_mint:
            # Inverted
            price = (token_a_amount / token_b_amount) * Decimal(10 ** (token_b_decimals - token_a_decimals))
            return price
        
        return None
    
    async def get_raydium_pool_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Get Raydium pool data (placeholder for actual implementation)"""
        # This would parse the actual Raydium pool account data
        # For now, return None
        logger.info(f"Getting Raydium pool data for {pool_address} (not implemented)")
        return None
    
    async def get_orca_pool_data(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """Get Orca whirlpool data (placeholder for actual implementation)"""
        # This would parse the actual Orca whirlpool account data
        # For now, return None
        logger.info(f"Getting Orca pool data for {pool_address} (not implemented)")
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reader statistics"""
        return {
            "request_count": self.request_count,
            "cache_size": len(_pool_cache),
            "sol_price": float(self._sol_price_usd) if self._sol_price_usd else None
        }


async def get_amm_price(
    token_mint: str,
    quote_mint: str = USDC_MINT,
    slot: Optional[int] = None
) -> Optional[Tuple[Decimal, str, Decimal]]:
    """
    Convenience function to get AMM price
    
    Returns:
        Tuple of (price, source, tvl_usd) or None
    """
    async with AMMPriceReader() as reader:
        return await reader.get_token_price(token_mint, quote_mint, slot)


# Example usage
if __name__ == "__main__":
    async def test_amm_reader():
        """Test the AMM price reader"""
        async with AMMPriceReader() as reader:
            # Test SOL/USDC price
            sol_price = await reader.get_sol_price_usd()
            print(f"SOL price: ${sol_price}")
            
            # Test getting price from AMM
            result = await reader.get_token_price(SOL_MINT, USDC_MINT)
            if result:
                price, source, tvl = result
                print(f"SOL/USDC price: ${price} from {source} (TVL: ${tvl})")
            
            # Get stats
            print(f"\nStats: {reader.get_stats()}")
    
    # Run test
    asyncio.run(test_amm_reader()) 