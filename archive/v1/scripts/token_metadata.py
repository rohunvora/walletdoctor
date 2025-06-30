#!/usr/bin/env python3
"""
Token Metadata Service - Fetch token symbols, names, and metadata
"""

import logging
import os
import aiohttp
import asyncio
import base64
import json
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)

@dataclass
class TokenMetadata:
    symbol: str
    name: str
    decimals: int
    mint: str
    
class TokenMetadataService:
    def __init__(self):
        self.helius_key = os.getenv('HELIUS_KEY')
        self.helius_api = f"https://api.helius.xyz/v0"
        self.birdeye_key = os.getenv('BIRDEYE_API_KEY')
        self.birdeye_api = "https://public-api.birdeye.so"
        self.cache: Dict[str, TokenMetadata] = {}
        
        # Known tokens cache
        self.known_tokens = {
            "So11111111111111111111111111111111111111112": TokenMetadata("SOL", "Solana", 9, "So11111111111111111111111111111111111111112"),
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": TokenMetadata("BONK", "Bonk", 5, "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),
        }
        
    async def get_token_metadata(self, mint: str) -> Optional[TokenMetadata]:
        """Get token metadata including symbol and name"""
        try:
            # Check known tokens first
            if mint in self.known_tokens:
                return self.known_tokens[mint]
                
            # Check cache
            if mint in self.cache:
                return self.cache[mint]
            
            # Try Helius first
            metadata = await self._fetch_from_helius(mint)
            if metadata:
                self.cache[mint] = metadata
                return metadata
            
            # Fallback to Birdeye
            metadata = await self._fetch_from_birdeye(mint)
            if metadata:
                self.cache[mint] = metadata
                return metadata
            
            # If all else fails, return truncated mint
            return TokenMetadata(
                symbol=f"{mint[:4]}...{mint[-4:]}",
                name=f"Unknown Token",
                decimals=9,
                mint=mint
            )
            
        except Exception as e:
            logger.error(f"Error getting token metadata for {mint}: {e}")
            return None
    
    async def _fetch_from_helius(self, mint: str) -> Optional[TokenMetadata]:
        """Fetch token metadata from Helius"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.helius_api}/token-metadata?api-key={self.helius_key}"
                payload = {"mintAccounts": [mint]}
                
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            token_data = data[0]
                            
                            # Extract on-chain metadata
                            on_chain = token_data.get('onChainMetadata', {})
                            metadata = on_chain.get('metadata', {})
                            
                            # The actual data is nested under metadata.data
                            metadata_data = metadata.get('data', {})
                            symbol = metadata_data.get('symbol', '')
                            name = metadata_data.get('name', '')
                            
                            # Get decimals from onChainAccountInfo
                            account_info = token_data.get('onChainAccountInfo', {})
                            parsed_data = account_info.get('accountInfo', {}).get('data', {}).get('parsed', {})
                            decimals = parsed_data.get('info', {}).get('decimals', 9)
                            
                            if symbol:
                                return TokenMetadata(
                                    symbol=symbol.strip(),
                                    name=name.strip() if name else symbol.strip(),
                                    decimals=decimals,
                                    mint=mint
                                )
                                
        except Exception as e:
            logger.debug(f"Error fetching from Helius: {e}")
            
        return None
    
    async def _fetch_from_birdeye(self, mint: str) -> Optional[TokenMetadata]:
        """Fetch token metadata from Birdeye"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.birdeye_api}/defi/token_overview"
                headers = {"X-API-KEY": self.birdeye_key}
                params = {"address": mint}
                
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success') and data.get('data'):
                            token_data = data['data']
                            
                            return TokenMetadata(
                                symbol=token_data.get('symbol', '').strip(),
                                name=token_data.get('name', '').strip(),
                                decimals=token_data.get('decimals', 9),
                                mint=mint
                            )
                            
        except Exception as e:
            logger.debug(f"Error fetching from Birdeye: {e}")
            
        return None
    
    async def get_market_cap(self, mint: str) -> Optional[float]:
        """Get token market cap from multiple sources"""
        try:
            # Try Birdeye first (paid service, more comprehensive data)
            if self.birdeye_key:
                mc = await self._get_market_cap_from_birdeye(mint)
                if mc:
                    return mc
            
            # Fallback to DexScreener if Birdeye fails
            mc = await self._get_market_cap_from_dexscreener(mint)
            if mc:
                return mc
                
            return None
            
        except Exception as e:
            logger.error(f"Error fetching market cap: {e}")
            return None
    
    async def _get_market_cap_from_dexscreener(self, mint: str) -> Optional[float]:
        """Get market cap from DexScreener API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # DexScreener returns array of pairs for the token
                        if data.get('pairs') and len(data['pairs']) > 0:
                            # Get the pair with highest liquidity
                            best_pair = max(data['pairs'], key=lambda p: float(p.get('liquidity', {}).get('usd', 0)))
                            mc = best_pair.get('marketCap')
                            if mc:
                                return float(mc)
                                
        except Exception as e:
            logger.debug(f"Error fetching market cap from DexScreener: {e}")
            
        return None
    
    async def _get_market_cap_from_birdeye(self, mint: str) -> Optional[float]:
        """Get market cap from Birdeye (fallback)"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.birdeye_api}/defi/token_overview"
                headers = {"X-API-KEY": self.birdeye_key}
                params = {"address": mint}
                
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success') != False and data.get('data'):
                            # Try multiple possible field names
                            token_data = data['data']
                            mc = (token_data.get('marketCap') or 
                                  token_data.get('mc') or 
                                  token_data.get('market_cap') or 0)
                            return float(mc) if mc else None
                            
        except Exception as e:
            logger.debug(f"Error fetching market cap from Birdeye: {e}")
            
        return None
    
    async def get_additional_token_info(self, mint: str) -> Optional[dict]:
        """Get additional token info from Birdeye (holder count, etc.)"""
        try:
            if not self.birdeye_key:
                return None
                
            async with aiohttp.ClientSession() as session:
                url = f"{self.birdeye_api}/defi/token_overview"
                headers = {"X-API-KEY": self.birdeye_key}
                params = {"address": mint}
                
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success') != False and data.get('data'):
                            token_data = data['data']
                            return {
                                'holder_count': token_data.get('numberHolders', 0),
                                'total_supply': token_data.get('supply', 0),
                                'volume_24h': token_data.get('v24hUSD', 0),
                                'price_change_24h': token_data.get('priceChange24h', 0),
                                'liquidity': token_data.get('liquidity', 0)
                            }
                            
        except Exception as e:
            logger.debug(f"Error fetching additional token info: {e}")
            
        return None
    
    def format_market_cap(self, mc: Optional[float]) -> str:
        """Format market cap for display"""
        if not mc:
            return ""
            
        if mc >= 1_000_000_000:
            return f"${mc/1_000_000_000:.1f}B"
        elif mc >= 1_000_000:
            return f"${mc/1_000_000:.1f}M"
        elif mc >= 1_000:
            return f"${mc/1_000:.0f}K"
        else:
            return f"${mc:.0f}"

# Test function
async def test_metadata_service():
    """Test the metadata service"""
    service = TokenMetadataService()
    
    # Test known token
    sol_meta = await service.get_token_metadata("So11111111111111111111111111111111111111112")
    print(f"SOL metadata: {sol_meta}")
    
    # Test with a real token
    test_mint = "6Nijf9VXcybuKUV2kP8WZ2CLKND6UjeFiDPBff3Zpump"
    metadata = await service.get_token_metadata(test_mint)
    print(f"Token metadata: {metadata}")
    
    # Test market cap
    mc = await service.get_market_cap(test_mint)
    print(f"Market cap: {service.format_market_cap(mc)}")

if __name__ == "__main__":
    asyncio.run(test_metadata_service()) 