#!/usr/bin/env python3
"""
Debug script to inspect AMM price calculation at specific slots
"""

import asyncio
import os
import sys
from decimal import Decimal
import base58
import struct
from typing import Optional, Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.amm_price import AMMPriceReader
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pump.fun program ID
PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

# Test cases
TEST_CASES = [
    {
        "name": "fakeout first buy",
        "mint": "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump",
        "slot": 187872345,  # Example slot - will need to fetch actual
        "signature": "XWdPAumHmsj9bKwyHRvbJCjFi5JSoUNqazp8eTy3mYo7XsDaHWdAhiSzBJ1F2QEgDBy3rztPdVtsc8RGzBb8NkZ"
    },
    {
        "name": "RDMP first buy", 
        "mint": "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop",
        "slot": 186931122,  # Example slot - will need to fetch actual
        "signature": None  # Will find from wallet scan
    }
]


async def get_transaction_slot(signature: str) -> Optional[int]:
    """Get the slot number for a transaction"""
    try:
        url = f"https://mainnet.helius-rpc.com/?api-key={os.getenv('HELIUS_KEY')}"
        
        async with aiohttp.ClientSession() as session:
            body = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [signature, {"maxSupportedTransactionVersion": 0}]
            }
            
            async with session.post(url, json=body) as resp:
                data = await resp.json()
                if "result" in data and data["result"]:
                    return data["result"]["slot"]
    except Exception as e:
        logger.error(f"Failed to get transaction slot: {e}")
    return None


async def find_pump_pool_address(mint: str) -> str:
    """Derive pump.fun pool address from mint"""
    from solders.pubkey import Pubkey
    
    mint_pubkey = Pubkey.from_string(mint)
    program_pubkey = Pubkey.from_string(PUMP_PROGRAM)
    
    # Find program address with seed ["pool", mint]
    seeds = [b"pool", bytes(mint_pubkey)]
    pool_address, _ = Pubkey.find_program_address(seeds, program_pubkey)
    
    return str(pool_address)


async def get_account_info_at_slot(address: str, slot: int) -> Optional[dict]:
    """Get account info at specific slot"""
    try:
        url = f"https://mainnet.helius-rpc.com/?api-key={os.getenv('HELIUS_KEY')}"
        
        async with aiohttp.ClientSession() as session:
            # First try getAccountInfo with minContextSlot
            body = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [
                    address,
                    {
                        "encoding": "base64",
                        "commitment": "confirmed",
                        "minContextSlot": slot
                    }
                ]
            }
            
            async with session.post(url, json=body) as resp:
                data = await resp.json()
                if "result" in data and data["result"] and data["result"]["value"]:
                    return data["result"]["value"]
                    
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
    return None


async def decode_pump_pool_data(data: str) -> dict:
    """Decode pump.fun pool account data"""
    try:
        # Decode base64
        raw_data = base58.b58decode(data)
        
        # Pump pool layout (simplified)
        # Skip discriminator (8 bytes)
        offset = 8
        
        # Read fields (this is approximate - actual layout may differ)
        virtual_sol_reserves = int.from_bytes(raw_data[offset:offset+8], 'little')
        offset += 8
        
        virtual_token_reserves = int.from_bytes(raw_data[offset:offset+8], 'little')
        offset += 8
        
        real_sol_reserves = int.from_bytes(raw_data[offset:offset+8], 'little')
        offset += 8
        
        real_token_reserves = int.from_bytes(raw_data[offset:offset+8], 'little')
        
        return {
            "virtual_sol_reserves": virtual_sol_reserves / 1e9,  # Convert lamports to SOL
            "virtual_token_reserves": virtual_token_reserves / 1e6,  # Assuming 6 decimals
            "real_sol_reserves": real_sol_reserves / 1e9,
            "real_token_reserves": real_token_reserves / 1e6,
        }
    except Exception as e:
        logger.error(f"Failed to decode pump pool: {e}")
        return {}


async def get_birdeye_price(mint: str) -> Optional[float]:
    """Get current Birdeye price"""
    try:
        from src.lib.birdeye_client import get_birdeye_price as birdeye_get_price
        result = await birdeye_get_price(mint)
        if result:
            price, _, _ = result
            return float(price)
    except Exception as e:
        logger.error(f"Failed to get Birdeye price: {e}")
    return None


async def debug_price_at_slot(mint: str, slot: int, name: str):
    """Debug price calculation at specific slot"""
    print(f"\n{name}")
    print(f"  mint: {mint}")
    print(f"  slot: {slot}")
    
    # Try to get price from AMM reader
    async with AMMPriceReader() as reader:
        # Get current price (since we don't have historical slot support yet)
        result = await reader.get_token_price(mint)
        
        if result:
            price, source, tvl = result
            print(f"  AMM price: ${float(price):.8f}")
            print(f"  source: {source}")
            print(f"  TVL: ${tvl:,.0f}")
        else:
            print("  AMM price: Not found")
    
    # Check if it's a pump token
    if mint.endswith("pump"):
        pool_address = await find_pump_pool_address(mint)
        print(f"  pump pool: {pool_address}")
        
        # Try to get pool data at slot
        pool_data = await get_account_info_at_slot(pool_address, slot)
        if pool_data and pool_data.get("data"):
            decoded = await decode_pump_pool_data(pool_data["data"][0])
            if decoded:
                print(f"  reserves:")
                print(f"    virtual SOL: {decoded.get('virtual_sol_reserves', 0):.2f}")
                print(f"    virtual tokens: {decoded.get('virtual_token_reserves', 0):,.0f}")
                print(f"    real SOL: {decoded.get('real_sol_reserves', 0):.2f}")
                print(f"    real tokens: {decoded.get('real_token_reserves', 0):,.0f}")
                
                # Calculate price from reserves
                if decoded.get('virtual_token_reserves', 0) > 0:
                    derived_price = decoded['virtual_sol_reserves'] / decoded['virtual_token_reserves']
                    print(f"  derived price: ${derived_price:.8f}")
    
    # Get Birdeye price for comparison
    birdeye_price = await get_birdeye_price(mint)
    if birdeye_price:
        print(f"  birdeye (current): ${birdeye_price:.8f}")
        
        if result and birdeye_price > 0:
            diff = (float(price) - birdeye_price) / birdeye_price * 100
            print(f"  difference: {diff:+.1f}%")


async def find_rdmp_first_buy():
    """Find RDMP first buy transaction"""
    from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3
    
    wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    rdmp_mint = "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop"
    
    async with BlockchainFetcherV3(skip_pricing=True) as fetcher:
        result = await fetcher.fetch_wallet_trades(wallet)
        
    for trade in result.get("trades", []):
        if (trade.get("action") == "buy" and 
            trade.get("token_out", {}).get("mint") == rdmp_mint):
            return trade.get("signature")
    
    return None


async def main():
    """Run debug for all test cases"""
    
    # Update RDMP signature if needed
    if not TEST_CASES[1]["signature"]:
        rdmp_sig = await find_rdmp_first_buy()
        if rdmp_sig:
            TEST_CASES[1]["signature"] = rdmp_sig
            print(f"Found RDMP first buy: {rdmp_sig}")
    
    # Get actual slots from transactions
    for test_case in TEST_CASES:
        if test_case["signature"]:
            actual_slot = await get_transaction_slot(test_case["signature"])
            if actual_slot:
                test_case["slot"] = actual_slot
    
    # Debug each case
    for test_case in TEST_CASES:
        await debug_price_at_slot(
            test_case["mint"],
            test_case["slot"],
            test_case["name"]
        )


if __name__ == "__main__":
    if not os.getenv("HELIUS_KEY"):
        print("Error: HELIUS_KEY environment variable not set")
        sys.exit(1)
    
    asyncio.run(main()) 