#!/usr/bin/env python3
"""
Price Service - Fetch token and SOL prices at transaction time
"""

import logging
import os
import aiohttp
import asyncio
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

class PriceService:
    def __init__(self):
        self.jupiter_api = "https://price.jup.ag/v4"
        self.helius_api = f"https://api.helius.xyz/v0"
        self.helius_key = os.getenv('HELIUS_KEY')
        self.cache: Dict[str, Dict] = {}  # Simple in-memory cache
        self.sol_mint = "So11111111111111111111111111111111111111112"
        
    async def get_sol_price_at_time(self, timestamp: int) -> Optional[float]:
        """Get SOL/USD price at a specific timestamp"""
        try:
            # For now, use current price as historical price data is complex
            # In production, you'd use a service like CoinGecko historical API
            sol_price = await self.get_current_sol_price()
            return sol_price
            
        except Exception as e:
            logger.error(f"Error getting SOL price at time: {e}")
            return None
    
    async def get_current_sol_price(self) -> Optional[float]:
        """Get current SOL/USD price from Jupiter"""
        try:
            # Check cache first (1 minute cache)
            cache_key = "SOL_USD"
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if time.time() - cached['timestamp'] < 60:
                    return cached['price']
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.jupiter_api}/price?ids=SOL"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        sol_price = data['data']['SOL']['price']
                        
                        # Cache the result
                        self.cache[cache_key] = {
                            'price': sol_price,
                            'timestamp': time.time()
                        }
                        
                        return float(sol_price)
                    else:
                        logger.error(f"Failed to get SOL price: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error fetching SOL price: {e}")
            return None
    
    async def get_token_price(self, token_mint: str) -> Optional[float]:
        """Get current token price in USD"""
        try:
            # Check cache first
            cache_key = f"token_{token_mint}"
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if time.time() - cached['timestamp'] < 300:  # 5 minute cache
                    return cached['price']
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.jupiter_api}/price?ids={token_mint}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if token_mint in data.get('data', {}):
                            price = data['data'][token_mint]['price']
                            
                            # Cache the result
                            self.cache[cache_key] = {
                                'price': price,
                                'timestamp': time.time()
                            }
                            
                            return float(price)
                    
            return None
                    
        except Exception as e:
            logger.error(f"Error fetching token price for {token_mint}: {e}")
            return None
    
    async def calculate_usd_values(self, sol_amount: float, token_amount: float, 
                                 token_mint: str, timestamp: int, is_buy: bool) -> Dict[str, Optional[float]]:
        """Calculate USD values for a swap transaction"""
        try:
            # Get SOL price at transaction time
            sol_price = await self.get_sol_price_at_time(timestamp)
            if not sol_price:
                logger.warning("Could not get SOL price")
                return {'sol_usd': None, 'token_usd': None, 'price_per_token': None}
            
            # Calculate SOL USD value
            sol_usd = sol_amount * sol_price if sol_amount > 0 else None
            
            # For token USD value, we'll use SOL value as reference
            # This is more accurate than fetching current token price
            token_usd = sol_usd  # In a swap, both sides have equal value
            
            # Calculate price per token
            price_per_token = None
            if token_amount > 0 and sol_usd:
                price_per_token = sol_usd / token_amount
            
            return {
                'sol_usd': sol_usd,
                'token_usd': token_usd,
                'price_per_token': price_per_token,
                'sol_price': sol_price
            }
            
        except Exception as e:
            logger.error(f"Error calculating USD values: {e}")
            return {'sol_usd': None, 'token_usd': None, 'price_per_token': None}

# Test function
async def test_price_service():
    """Test the price service"""
    service = PriceService()
    
    # Test SOL price
    sol_price = await service.get_current_sol_price()
    print(f"Current SOL price: ${sol_price}")
    
    # Test token price (BONK)
    bonk_mint = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    bonk_price = await service.get_token_price(bonk_mint)
    print(f"BONK price: ${bonk_price}")
    
    # Test USD calculation
    usd_values = await service.calculate_usd_values(
        sol_amount=0.837,
        token_amount=1675078.954,
        token_mint=bonk_mint,
        timestamp=int(time.time()),
        is_buy=False
    )
    print(f"USD values: {usd_values}")

if __name__ == "__main__":
    asyncio.run(test_price_service()) 