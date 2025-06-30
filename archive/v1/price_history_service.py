#!/usr/bin/env python3
"""
Price History Service - Fetches and stores price data using Birdeye API
"""

import aiohttp
import asyncio
import logging
import duckdb
import os
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PriceSnapshot:
    """Data class for price snapshots"""
    token_address: str
    timestamp: datetime
    price_sol: float
    price_usd: float
    market_cap: float
    volume_24h: float
    liquidity_usd: float


class PriceHistoryService:
    """Service for fetching and storing price history data"""
    
    def __init__(self, birdeye_api_key: Optional[str] = None, db_path: str = "pocket_coach.db"):
        self.birdeye_key = birdeye_api_key or os.getenv('BIRDEYE_API_KEY')
        self.birdeye_api = "https://public-api.birdeye.so"
        self.db_path = db_path
        self.db_mutex = asyncio.Lock()  # Mutex for DuckDB concurrency
        
        # DexScreener fallback
        self.dexscreener_api = "https://api.dexscreener.com/latest/dex"
        
        # Cache for API responses (1 minute TTL)
        self.price_cache = {}
        self.cache_ttl = 60  # seconds
        
    async def fetch_and_store_price_data(self, token_address: str, 
                                       token_symbol: Optional[str] = None) -> Optional[PriceSnapshot]:
        """
        Implement Birdeye 3-call pattern:
        1. Get current price
        2. Get price changes (24h, 7d)
        3. Get historical data (last hour)
        
        Falls back to DexScreener for new tokens
        """
        try:
            # Check cache first
            cache_key = f"{token_address}:{int(datetime.now().timestamp() / 60)}"
            if cache_key in self.price_cache:
                logger.debug(f"Cache hit for {token_symbol or token_address}")
                return self.price_cache[cache_key]
            
            # Try Birdeye first
            snapshot = await self._fetch_from_birdeye(token_address)
            
            # Fallback to DexScreener if Birdeye fails
            if not snapshot:
                logger.info(f"Birdeye failed for {token_symbol}, trying DexScreener")
                snapshot = await self._fetch_from_dexscreener(token_address)
            
            if snapshot:
                # Store in database
                await self._store_snapshot(snapshot)
                
                # Cache the result
                self.price_cache[cache_key] = snapshot
                
                # Clean old cache entries
                self._clean_cache()
                
                return snapshot
            
            logger.warning(f"Failed to fetch price data for {token_symbol or token_address}")
            return None
            
        except Exception as e:
            logger.error(f"Error in fetch_and_store_price_data: {e}")
            return None
    
    async def _fetch_from_birdeye(self, token_address: str) -> Optional[PriceSnapshot]:
        """Implement Birdeye 3-call pattern"""
        headers = {
            "X-API-KEY": self.birdeye_key,
            "accept": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # Call 1: Get current price
                price_data = await self._birdeye_get_price(session, headers, token_address)
                if not price_data:
                    return None
                
                # Call 2: Get market data (v3 endpoint for better data)
                market_data = await self._birdeye_get_market_data(session, headers, token_address)
                
                # Call 3: Get token overview (includes basic market info)
                overview_data = await self._birdeye_get_overview(session, headers, token_address)
                
                # Combine all data
                return await self._combine_birdeye_data(token_address, price_data, market_data, overview_data)
                
        except Exception as e:
            logger.error(f"Birdeye API error: {e}")
            return None
    
    async def _birdeye_get_price(self, session: aiohttp.ClientSession, 
                                headers: Dict, token_address: str) -> Optional[Dict]:
        """Get current price from Birdeye"""
        url = f"{self.birdeye_api}/defi/price"
        params = {"address": token_address}
        
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('data', {})
            else:
                logger.error(f"Birdeye price API error: {response.status}")
                return None
    
    async def _birdeye_get_market_data(self, session: aiohttp.ClientSession,
                                       headers: Dict, token_address: str) -> Optional[Dict]:
        """Get market data from Birdeye v3 API"""
        url = f"{self.birdeye_api}/defi/v3/token/market-data"
        params = {
            "address": token_address,
            "chain": "solana"  # Specify chain for better results
        }
        
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('data', {})
            else:
                logger.debug(f"Birdeye market data API error: {response.status}")
                return None
    
    async def _birdeye_get_overview(self, session: aiohttp.ClientSession,
                                   headers: Dict, token_address: str) -> Optional[Dict]:
        """Get token overview including market cap, volume, liquidity"""
        url = f"{self.birdeye_api}/defi/token_overview"
        params = {
            "address": token_address,
            "chain": "solana"  # Specify chain for better results
        }
        
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('data', {})
            else:
                logger.debug(f"Birdeye overview API error: {response.status}")
                return None
    
    async def _combine_birdeye_data(self, token_address: str, price_data: Dict,
                             market_data: Optional[Dict], overview_data: Optional[Dict]) -> PriceSnapshot:
        """Combine data from multiple Birdeye calls"""
        
        # Get current SOL price for conversion
        sol_price_usd = await self.get_sol_price()
        
        # Extract price in USD from price endpoint
        price_usd = price_data.get('value', 0)
        
        # Calculate price in SOL
        price_sol = price_usd / sol_price_usd if sol_price_usd > 0 else 0
        
        # Extract market data - prefer v3 market data over overview
        market_cap = 0
        volume_24h = 0
        liquidity_usd = 0
        
        # First try v3 market data (more accurate)
        if market_data:
            market_cap = market_data.get('market_cap', 0) or market_data.get('marketCap', 0) or 0
            volume_24h = market_data.get('volume_24h', 0) or market_data.get('volume24h', 0) or 0
            liquidity_usd = market_data.get('liquidity', 0) or 0
        
        # Fallback to overview data if market data missing
        if overview_data and market_cap == 0:
            market_cap = overview_data.get('marketCap', 0) or overview_data.get('mc', 0) or 0
            volume_24h = overview_data.get('v24hUSD', 0) or 0
            liquidity_usd = overview_data.get('liquidity', 0) or 0
        
        return PriceSnapshot(
            token_address=token_address,
            timestamp=datetime.now(),
            price_sol=price_sol,
            price_usd=price_usd,
            market_cap=market_cap,
            volume_24h=volume_24h,
            liquidity_usd=liquidity_usd
        )
    
    async def _fetch_from_dexscreener(self, token_address: str) -> Optional[PriceSnapshot]:
        """Fallback to DexScreener for new tokens"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.dexscreener_api}/tokens/{token_address}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get('pairs', [])
                        
                        if not pairs:
                            logger.debug(f"No pairs found for token {token_address}")
                            return None
                        
                        # Get the most liquid pair
                        try:
                            pair = max(pairs, key=lambda p: p.get('liquidity', {}).get('usd', 0))
                        except (ValueError, KeyError) as e:
                            logger.error(f"Error getting most liquid pair: {e}")
                            return None
                        
                        return PriceSnapshot(
                            token_address=token_address,
                            timestamp=datetime.now(),
                            price_sol=float(pair.get('priceNative', 0)),
                            price_usd=float(pair.get('priceUsd', 0)),
                            market_cap=float(pair.get('fdv', 0)),  # Fully diluted valuation
                            volume_24h=float(pair.get('volume', {}).get('h24', 0)),
                            liquidity_usd=float(pair.get('liquidity', {}).get('usd', 0))
                        )
                    else:
                        logger.debug(f"DexScreener API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"DexScreener error: {e}")
            return None
    
    async def _store_snapshot(self, snapshot: PriceSnapshot):
        """Store price snapshot in database with mutex for thread safety"""
        async with self.db_mutex:
            db = duckdb.connect(self.db_path)
            try:
                db.execute("""
                    INSERT INTO price_snapshots 
                    (token_address, timestamp, price_sol, price_usd, 
                     market_cap, volume_24h, liquidity_usd)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    snapshot.token_address,
                    snapshot.timestamp,
                    snapshot.price_sol,
                    snapshot.price_usd,
                    snapshot.market_cap,
                    snapshot.volume_24h,
                    snapshot.liquidity_usd
                ])
                db.commit()
                logger.debug(f"Stored price snapshot for {snapshot.token_address}")
            except Exception as e:
                logger.error(f"Error storing price snapshot: {e}")
            finally:
                db.close()
    
    async def fetch_historical_prices(self, token_address: str, 
                                    hours: int = 1) -> List[PriceSnapshot]:
        """Fetch historical price data for the last N hours"""
        start_time = datetime.now() - timedelta(hours=hours)
        
        async with self.db_mutex:
            db = duckdb.connect(self.db_path)
            try:
                results = db.execute("""
                    SELECT token_address, timestamp, price_sol, price_usd,
                           market_cap, volume_24h, liquidity_usd
                    FROM price_snapshots
                    WHERE token_address = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                """, [token_address, start_time]).fetchall()
                
                return [
                    PriceSnapshot(
                        token_address=row[0],
                        timestamp=row[1],
                        price_sol=row[2],
                        price_usd=row[3],
                        market_cap=row[4],
                        volume_24h=row[5],
                        liquidity_usd=row[6]
                    )
                    for row in results
                ]
            finally:
                db.close()
    
    async def get_price_at_timestamp(self, token_address: str, 
                                   timestamp: datetime) -> Optional[PriceSnapshot]:
        """Get the closest price to a specific timestamp"""
        # Allow 5 minute window
        time_window = timedelta(minutes=5)
        
        async with self.db_mutex:
            db = duckdb.connect(self.db_path)
            try:
                result = db.execute("""
                    SELECT token_address, timestamp, price_sol, price_usd,
                           market_cap, volume_24h, liquidity_usd
                    FROM price_snapshots
                    WHERE token_address = ? 
                    AND timestamp BETWEEN ? AND ?
                    ORDER BY ABS(EXTRACT(EPOCH FROM (timestamp - ?))) ASC
                    LIMIT 1
                """, [
                    token_address,
                    timestamp - time_window,
                    timestamp + time_window,
                    timestamp
                ]).fetchone()
                
                if result:
                    return PriceSnapshot(
                        token_address=result[0],
                        timestamp=result[1],
                        price_sol=result[2],
                        price_usd=result[3],
                        market_cap=result[4],
                        volume_24h=result[5],
                        liquidity_usd=result[6]
                    )
                return None
            finally:
                db.close()
    
    def _clean_cache(self):
        """Remove old cache entries"""
        current_minute = int(datetime.now().timestamp() / 60)
        old_keys = []
        
        for key in self.price_cache.keys():
            # Skip non-timestamp keys like "sol_price"
            if ':' in key:
                try:
                    key_minute = int(key.split(':')[1])
                    if key_minute < current_minute - 1:
                        old_keys.append(key)
                except (IndexError, ValueError):
                    pass
        
        for key in old_keys:
            del self.price_cache[key]
    
    async def get_sol_price(self) -> float:
        """Get current SOL price for conversions"""
        cache_key = "sol_price"
        
        # Check cache
        if cache_key in self.price_cache:
            return self.price_cache[cache_key].price_usd
        
        try:
            # Fetch SOL price using Birdeye
            headers = {
                "X-API-KEY": self.birdeye_key,
                "accept": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.birdeye_api}/defi/price"
                params = {
                    "address": "So11111111111111111111111111111111111111112",  # Wrapped SOL
                    "chain": "solana"
                }
                
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        sol_price = data.get('data', {}).get('value', 150.0)
                        
                        # Cache as a simple PriceSnapshot
                        self.price_cache[cache_key] = PriceSnapshot(
                            token_address="SOL",
                            timestamp=datetime.now(),
                            price_sol=1.0,
                            price_usd=sol_price,
                            market_cap=0,
                            volume_24h=0,
                            liquidity_usd=0
                        )
                        
                        return sol_price
                    else:
                        logger.warning("Failed to fetch SOL price, using default")
                        return 150.0
                        
        except Exception as e:
            logger.error(f"Error fetching SOL price: {e}")
            return 150.0  # Fallback price


# Testing
async def test_price_history():
    """Test the price history service"""
    service = PriceHistoryService()
    
    # Test token (BONK)
    test_token = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    
    print("Fetching price data...")
    snapshot = await service.fetch_and_store_price_data(test_token, "BONK")
    
    if snapshot:
        print(f"Token: {test_token}")
        print(f"Price USD: ${snapshot.price_usd:.8f}")
        print(f"Price SOL: {snapshot.price_sol:.8f}")
        print(f"Market Cap: ${snapshot.market_cap:,.0f}")
        print(f"Volume 24h: ${snapshot.volume_24h:,.0f}")
        print(f"Liquidity: ${snapshot.liquidity_usd:,.0f}")
    else:
        print("Failed to fetch price data")
    
    # Test historical fetch
    print("\nFetching historical prices...")
    history = await service.fetch_historical_prices(test_token, hours=24)
    print(f"Found {len(history)} historical price points")

if __name__ == "__main__":
    asyncio.run(test_price_history()) 