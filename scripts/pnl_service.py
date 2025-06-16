#!/usr/bin/env python3
"""
Fast-Path P&L Service using Cielo Finance and Birdeye APIs
"""

import aiohttp
import asyncio
import time
import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class CieloClient:
    """Client for Cielo Finance API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://feed-api.cielo.finance/api/v1"
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
    
    async def get_wallet_pnl(self, wallet_address: str) -> Optional[Dict]:
        """Get overall P&L stats for a wallet"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/{wallet_address}/pnl/total-stats"
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Cielo API error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching wallet P&L: {e}")
            return None
    
    async def get_token_pnl(self, wallet_address: str) -> Optional[List[Dict]]:
        """Get P&L breakdown by token"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/{wallet_address}/pnl/tokens"
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Cielo API returns: {"status": "ok", "data": {"items": [...]}}
                        if data.get('status') == 'ok':
                            items = data.get('data', {}).get('items', [])
                            return items
                        return []
                    else:
                        logger.error(f"Cielo API error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching token P&L: {e}")
            return None


class BirdeyeClient:
    """Client for Birdeye API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://public-api.birdeye.so"
        self.headers = {
            "X-API-Key": api_key,
            "accept": "application/json"
        }
    
    async def get_token_price(self, token_address: str) -> Optional[float]:
        """Get current token price in USD"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/defi/price"
                params = {"address": token_address}
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('data', {}).get('value', 0)
                    else:
                        logger.error(f"Birdeye API error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching token price: {e}")
            return None
    
    async def get_historical_price(self, token_address: str, timestamp: int) -> Optional[float]:
        """Get historical token price at specific timestamp"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/defi/history_price"
                params = {
                    "address": token_address,
                    "time": timestamp
                }
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('data', {}).get('value', 0)
                    else:
                        logger.error(f"Birdeye historical price error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching historical price: {e}")
            return None


class PnLCache:
    """Simple in-memory cache with TTL"""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[Dict]:
        """Get cached value if not expired"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                logger.debug(f"Cache hit for {key}")
                return data
            else:
                # Expired, remove it
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Dict):
        """Store value with current timestamp"""
        self.cache[key] = (value, time.time())
        logger.debug(f"Cached {key}")
    
    def invalidate(self, pattern: str = None):
        """Invalidate cache entries matching pattern"""
        if pattern:
            keys_to_delete = [k for k in self.cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self.cache[key]
        else:
            self.cache.clear()


class FastPnLService:
    """Main service combining Cielo, Birdeye, and caching"""
    
    def __init__(self, cielo_api_key: str, birdeye_api_key: str):
        self.cielo = CieloClient(cielo_api_key)
        self.birdeye = BirdeyeClient(birdeye_api_key)
        self.cache = PnLCache(ttl_seconds=300)  # 5 min cache
        self.sol_mint = "So11111111111111111111111111111111111111112"
    
    async def get_token_pnl_data(self, wallet_address: str, token_address: str) -> Optional[Dict]:
        """Get comprehensive P&L data for a specific token"""
        cache_key = f"{wallet_address}:{token_address}"
        
        # Check cache first
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # Fetch from Cielo
        tokens_data = await self.cielo.get_token_pnl(wallet_address)
        if not tokens_data:
            return None
        
        # Find the specific token
        token_data = None
        for token in tokens_data:
            # Cielo uses 'token_address' field
            if token.get('token_address', '').lower() == token_address.lower():
                token_data = token
                break
        
        if not token_data:
            return None
        
        # Enhance with current price from Birdeye
        current_price = await self.birdeye.get_token_price(token_address)
        
        # Extract fields from Cielo response
        num_swaps = token_data.get('num_swaps', 0)
        total_buy_usd = token_data.get('total_buy_usd', 0)
        total_sell_usd = token_data.get('total_sell_usd', 0)
        total_pnl_usd = token_data.get('total_pnl_usd', 0)
        unrealized_pnl_usd = token_data.get('unrealized_pnl_usd', 0)
        roi_percentage = token_data.get('roi_percentage', 0)
        
        # For display purposes, we want to show what the user has actually realized from closed positions
        # Cielo provides realized_pnl_usd directly in their response
        realized_pnl_usd = token_data.get('realized_pnl_usd', 0)
        
        # If realized P&L isn't provided, calculate it as total - unrealized
        if 'realized_pnl_usd' not in token_data:
            realized_pnl_usd = total_pnl_usd - unrealized_pnl_usd
        
        # Estimate SOL amounts (will need SOL price)
        sol_price = await self.get_sol_price()
        realized_pnl_sol = realized_pnl_usd / sol_price if sol_price > 0 else 0
        unrealized_pnl_sol = unrealized_pnl_usd / sol_price if sol_price > 0 else 0
        total_pnl_sol = total_pnl_usd / sol_price if sol_price > 0 else 0
        
        # Calculate win rate from ROI
        # If ROI is positive with realized P&L, assume decent win rate
        win_rate = 0
        if realized_pnl_usd > 0 and num_swaps > 0:
            # Rough estimate: positive P&L suggests > 50% win rate
            win_rate = 0.6 if roi_percentage > 50 else 0.4
        
        # Check if has open position
        has_open_position = unrealized_pnl_usd != 0
        
        result = {
            'token_address': token_address,
            'token_symbol': token_data.get('token_symbol', 'Unknown'),
            'token_name': token_data.get('token_name', ''),
            'realized_pnl_sol': realized_pnl_sol,
            'realized_pnl_usd': realized_pnl_usd,
            'unrealized_pnl_sol': unrealized_pnl_sol,
            'unrealized_pnl_usd': unrealized_pnl_usd,
            'total_pnl_sol': total_pnl_sol,
            'total_pnl_usd': total_pnl_usd,
            'buy_txns': num_swaps,  # Cielo doesn't separate buy/sell counts
            'sell_txns': num_swaps,
            'total_trades': num_swaps,
            'avg_buy_price': token_data.get('average_buy_price', 0),
            'avg_sell_price': token_data.get('average_sell_price', 0),
            'current_price': current_price or token_data.get('token_price', 0),
            'current_balance': token_data.get('holding_amount', 0),
            'win_rate': win_rate,
            'has_open_position': has_open_position,
            'roi_percentage': roi_percentage,
            'holding_time_seconds': token_data.get('holding_time_seconds', 0)
        }
        
        # Cache the result
        self.cache.set(cache_key, result)
        
        return result
    
    async def get_sol_price(self) -> float:
        """Get current SOL price in USD"""
        cache_key = "sol_price"
        cached = self.cache.get(cache_key)
        if cached:
            return cached.get('price', 0)
        
        price = await self.birdeye.get_token_price(self.sol_mint)
        if price:
            self.cache.set(cache_key, {'price': price})
            return price
        
        # Fallback price if API fails
        return 95.0  # Reasonable fallback
    
    async def format_pnl_display(self, sol_amount: float, usd_amount: float) -> str:
        """Format P&L in preferred display format (SOL primary)"""
        # Option A: "-1.5 SOL (-$142)"
        sol_str = f"{sol_amount:+.2f} SOL" if abs(sol_amount) >= 0.01 else "0 SOL"
        usd_str = f"${abs(usd_amount):,.0f}" if abs(usd_amount) >= 1 else f"${abs(usd_amount):.2f}"
        
        if usd_amount >= 0:
            return f"{sol_str} (+{usd_str})"
        else:
            return f"{sol_str} (-{usd_str})"
    
    def invalidate_wallet_cache(self, wallet_address: str):
        """Invalidate all cache entries for a wallet (after new trade)"""
        self.cache.invalidate(pattern=wallet_address)


# Example usage
async def test_pnl_service():
    """Test the P&L service with real data"""
    service = FastPnLService(
        cielo_api_key="7c855165-3874-4237-9416-450d2373ea72",
        birdeye_api_key="4e5e878a6137491bbc280c10587a0cce"
    )
    
    # Test wallets
    test_wallets = [
        "34zYDgjy8oinZ5v8gyrcQktzUmSfFLJztTSq5xLUVCya",
        "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
        "3URnnJKdG8eTjrKo7G8rN5GjzweYwSZSxwyJm5Ut5UmL"
    ]
    
    # Example token (you'll need to get actual token addresses from transactions)
    test_token = "CGkRYvHnV6guL8DMadWG57qe6qUm6m3zDyGpMrcvpump"  # CRUISE
    
    for wallet in test_wallets:
        print(f"\nTesting wallet: {wallet[:8]}...")
        pnl_data = await service.get_token_pnl_data(wallet, test_token)
        
        if pnl_data:
            print(f"Token: {pnl_data['token_symbol']}")
            print(f"Realized P&L: {await service.format_pnl_display(pnl_data['realized_pnl_sol'], pnl_data['realized_pnl_usd'])}")
            print(f"Unrealized P&L: {await service.format_pnl_display(pnl_data['unrealized_pnl_sol'], pnl_data['unrealized_pnl_usd'])}")
            print(f"Trades: {pnl_data['buy_txns']} buys, {pnl_data['sell_txns']} sells")
            print(f"Has open position: {pnl_data['has_open_position']}")
        else:
            print("No P&L data found")

if __name__ == "__main__":
    asyncio.run(test_pnl_service()) 