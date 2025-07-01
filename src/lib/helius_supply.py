#!/usr/bin/env python3
"""
Helius Supply Fetcher - Get token supply at specific slots via RPC
"""

import os
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import logging
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal
import time
import json

# Setup logging
logger = logging.getLogger(__name__)

# Environment variables
HELIUS_KEY = os.getenv("HELIUS_KEY")

# Constants
HELIUS_RPC_BASE = "https://mainnet.helius-rpc.com"
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 5]  # Exponential backoff
REQUEST_TIMEOUT = 30
BATCH_SIZE = 100  # Max batch size for RPC calls

# Special mints
SOL_MINT = "So11111111111111111111111111111111111111112"
SOL_DECIMALS = 9
SOL_SUPPLY = Decimal("574207458.192302894")  # SOL has a fixed supply


class HeliusSupplyFetcher:
    """Fetches token supply from Helius RPC"""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize with optional session for connection pooling"""
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
    
    def _get_rpc_url(self) -> str:
        """Get RPC URL with API key"""
        if not HELIUS_KEY:
            raise ValueError("HELIUS_KEY environment variable not set")
        return f"{HELIUS_RPC_BASE}/?api-key={HELIUS_KEY}"
    
    async def _make_rpc_request(self, method: str, params: List[Any], request_id: int = 1) -> Dict[str, Any]:
        """Make a single RPC request with retry logic"""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        url = self._get_rpc_url()
        headers = {"Content-Type": "application/json"}
        
        body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        last_error = None
        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                self.request_count += 1
                async with self.session.post(
                    url, 
                    headers=headers, 
                    json=body,
                    timeout=ClientTimeout(total=REQUEST_TIMEOUT)
                ) as resp:
                    if resp.status == 429:
                        # Rate limited
                        retry_after = int(resp.headers.get("Retry-After", delay))
                        logger.warning(f"Rate limited on attempt {attempt + 1}, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    resp.raise_for_status()
                    data = await resp.json()
                    
                    # Check for RPC errors
                    if "error" in data:
                        error_msg = data["error"].get("message", "Unknown RPC error")
                        logger.error(f"RPC error: {error_msg}")
                        return data
                    
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
        logger.error(f"All retries failed for {method}: {last_error}")
        return {"error": {"message": f"All retries failed: {last_error}"}}
    
    async def get_token_supply(self, mint: str, slot: Optional[int] = None) -> Optional[Decimal]:
        """
        Get token supply at a specific slot
        
        Args:
            mint: Token mint address
            slot: Optional slot number (defaults to latest)
            
        Returns:
            Token supply as Decimal, or None if error
        """
        # Special case for SOL
        if mint == SOL_MINT:
            return SOL_SUPPLY
        
        # Build params
        params = [mint]
        if slot is not None:
            # Add commitment config with specific slot
            params.append({"commitment": "confirmed", "minContextSlot": slot})
        
        # Make RPC request
        response = await self._make_rpc_request("getTokenSupply", params)
        
        if "error" in response:
            logger.error(f"Failed to get supply for {mint}: {response['error']}")
            return None
        
        # Parse result
        try:
            result = response.get("result", {})
            value = result.get("value", {})
            
            # Get UI amount (human-readable with decimals applied)
            ui_amount_str = value.get("uiAmountString")
            if ui_amount_str:
                return Decimal(ui_amount_str)
            
            # Fallback to raw amount and decimals
            amount = value.get("amount")
            decimals = value.get("decimals", 0)
            
            if amount is None:
                logger.error(f"No amount in response for {mint}")
                return None
            
            # Convert to decimal
            supply = Decimal(amount) / Decimal(10 ** decimals)
            return supply
            
        except Exception as e:
            logger.error(f"Error parsing supply response for {mint}: {e}")
            return None
    
    async def get_token_supply_batch(self, requests: List[Tuple[str, Optional[int]]]) -> Dict[Tuple[str, Optional[int]], Optional[Decimal]]:
        """
        Get token supplies for multiple tokens in batch
        
        Args:
            requests: List of (mint, slot) tuples
            
        Returns:
            Dictionary mapping (mint, slot) to supply
        """
        results = {}
        
        # Process in batches to avoid overwhelming the RPC
        for i in range(0, len(requests), BATCH_SIZE):
            batch = requests[i:i + BATCH_SIZE]
            
            # Create tasks for parallel execution
            tasks = []
            for mint, slot in batch:
                task = self.get_token_supply(mint, slot)
                tasks.append(task)
            
            # Execute batch
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Map results
            for (mint, slot), result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Exception getting supply for {mint}: {result}")
                    results[(mint, slot)] = None
                else:
                    results[(mint, slot)] = result
            
            # Small delay between batches to avoid rate limiting
            if i + BATCH_SIZE < len(requests):
                await asyncio.sleep(0.1)
        
        return results
    
    async def get_token_metadata(self, mint: str) -> Optional[Dict[str, Any]]:
        """
        Get token metadata including decimals
        
        Args:
            mint: Token mint address
            
        Returns:
            Token metadata dict or None
        """
        # Use getAccountInfo to get mint data
        response = await self._make_rpc_request("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        
        if "error" in response:
            return None
        
        try:
            result = response.get("result", {})
            value = result.get("value", {})
            data = value.get("data", {})
            
            if isinstance(data, dict) and "parsed" in data:
                parsed = data["parsed"]
                info = parsed.get("info", {})
                
                return {
                    "decimals": info.get("decimals", 0),
                    "supply": info.get("supply"),
                    "mintAuthority": info.get("mintAuthority"),
                    "freezeAuthority": info.get("freezeAuthority"),
                    "isInitialized": info.get("isInitialized", False)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing metadata for {mint}: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get fetcher statistics"""
        return {
            "request_count": self.request_count,
            "rpc_endpoint": HELIUS_RPC_BASE
        }


async def get_token_supply_at_slot(mint: str, slot: Optional[int] = None) -> Optional[Decimal]:
    """
    Convenience function to get token supply at a specific slot
    
    Args:
        mint: Token mint address
        slot: Optional slot number
        
    Returns:
        Token supply as Decimal, or None if error
    """
    async with HeliusSupplyFetcher() as fetcher:
        return await fetcher.get_token_supply(mint, slot)


# Example usage
if __name__ == "__main__":
    async def test_supply_fetcher():
        """Test the supply fetcher"""
        async with HeliusSupplyFetcher() as fetcher:
            # Test SOL (special case)
            sol_supply = await fetcher.get_token_supply(SOL_MINT)
            print(f"SOL supply: {sol_supply}")
            
            # Test USDC
            usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
            usdc_supply = await fetcher.get_token_supply(usdc_mint)
            print(f"USDC supply: {usdc_supply}")
            
            # Test with specific slot
            usdc_supply_at_slot = await fetcher.get_token_supply(usdc_mint, 250000000)
            print(f"USDC supply at slot 250000000: {usdc_supply_at_slot}")
            
            # Test batch
            requests = [
                (SOL_MINT, None),
                (usdc_mint, None),
                ("So11111111111111111111111111111111111111112", 250000000),
            ]
            batch_results = await fetcher.get_token_supply_batch(requests)
            print(f"\nBatch results:")
            for (mint, slot), supply in batch_results.items():
                print(f"  {mint[:8]}... at slot {slot}: {supply}")
            
            # Test metadata
            metadata = await fetcher.get_token_metadata(usdc_mint)
            print(f"\nUSDC metadata: {metadata}")
            
            # Get stats
            print(f"\nStats: {fetcher.get_stats()}")
    
    # Run test
    asyncio.run(test_supply_fetcher()) 