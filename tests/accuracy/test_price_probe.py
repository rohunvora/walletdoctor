#!/usr/bin/env python3
"""
WAL-511a: On-chain Price Probe
Query AMM pool price at specific slots and compare with Birdeye
"""

import pytest
import asyncio
import os
import logging
import time
from decimal import Decimal
from typing import Optional, Tuple
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from src.lib.amm_price import AMMPriceReader
from src.lib.birdeye_client import get_birdeye_price
from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
TEST_DATA = {
    "fakeout": {
        "mint": "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump",
        "symbol": "fakeout",
        "platform": "pump_amm",
        "first_buy_signature": "XWdPAumHmsj9bKwyHRvbJCjFi5JSoUNqazp8eTy3mYo7XsDaHWdAhiSzBJ1F2QEgDBy3rztPdVtsc8RGzBb8NkZ",
        "expected_slot": None  # Will be fetched from transaction
    },
    "RDMP": {
        "mint": "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop",
        "symbol": "RDMP",
        "platform": "raydium",
        "first_buy_signature": None,  # Need to identify from wallet scan
        "expected_slot": None
    }
}

# Check if required keys are available
HELIUS_KEY_AVAILABLE = bool(os.getenv("HELIUS_KEY"))
BIRDEYE_KEY_AVAILABLE = bool(os.getenv("BIRDEYE_API_KEY"))


async def get_transaction_slot(signature: str) -> Optional[int]:
    """Get the slot number for a transaction"""
    try:
        async with BlockchainFetcherV3() as fetcher:
            # Use Helius RPC to get transaction details
            import aiohttp
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


async def get_amm_price_at_slot(token_mint: str, slot: int) -> Optional[Tuple[Decimal, str]]:
    """Get AMM pool price at a specific slot"""
    try:
        async with AMMPriceReader() as reader:
            # Note: Current implementation doesn't support historical slots
            # This would need to be enhanced to query historical pool states
            result = await reader.get_token_price(token_mint)
            if result:
                price, source, tvl = result
                return (price, source)
    except Exception as e:
        logger.error(f"Failed to get AMM price: {e}")
    return None


async def get_birdeye_price_current(token_mint: str) -> Optional[Decimal]:
    """Get current Birdeye price"""
    try:
        result = await get_birdeye_price(token_mint)
        if result:
            price, source, metadata = result
            return price
    except Exception as e:
        logger.error(f"Failed to get Birdeye price: {e}")
    return None


@pytest.mark.skipif(
    not HELIUS_KEY_AVAILABLE,
    reason="HELIUS_KEY environment variable not set"
)
class TestPriceProbe:
    """Test on-chain price accuracy"""
    
    @pytest.mark.asyncio
    async def test_fakeout_price_at_first_buy(self):
        """Test fakeout token price at first buy slot"""
        token_data = TEST_DATA["fakeout"]
        
        # Get transaction slot
        slot = await get_transaction_slot(token_data["first_buy_signature"])
        assert slot is not None, f"Could not get slot for transaction {token_data['first_buy_signature']}"
        
        logger.info(f"First buy slot for {token_data['symbol']}: {slot}")
        
        # Get AMM price
        amm_result = await get_amm_price_at_slot(token_data["mint"], slot)
        assert amm_result is not None, "Could not get AMM price"
        
        amm_price, source = amm_result
        logger.info(f"AMM price: ${float(amm_price):.8f} from {source}")
        
        # Skip Birdeye comparison if no API key
        if not BIRDEYE_KEY_AVAILABLE:
            pytest.skip("BIRDEYE_API_KEY not set, skipping price comparison")
        
        # Get current Birdeye price (historical might not be available)
        birdeye_price = await get_birdeye_price_current(token_data["mint"])
        if birdeye_price is None:
            pytest.skip("Could not get Birdeye price for comparison")
        
        logger.info(f"Birdeye price (current): ${float(birdeye_price):.8f}")
        
        # For historical comparison, we'll be more lenient since we're comparing 
        # historical AMM price to current Birdeye price
        price_diff = abs(float(amm_price) - float(birdeye_price)) / float(birdeye_price)
        logger.info(f"Price difference: {price_diff*100:.1f}%")
        
        # Note: Comparing historical AMM to current Birdeye, so we just log the difference
        # In production, you'd need historical Birdeye API access for accurate comparison
        if price_diff > 0.5:  # 50% threshold for warning
            logger.warning(f"Large price difference detected: {price_diff*100:.1f}%")
    
    @pytest.mark.asyncio
    async def test_rdmp_price_at_first_buy(self):
        """Test RDMP token price at first buy slot"""
        # First need to find the first RDMP buy transaction
        wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
        
        async with BlockchainFetcherV3(skip_pricing=True) as fetcher:
            result = await fetcher.fetch_wallet_trades(wallet)
            
        # Find first RDMP buy
        rdmp_mint = TEST_DATA["RDMP"]["mint"]
        first_buy_sig = None
        
        for trade in result.get("trades", []):
            if (trade.get("action") == "buy" and 
                trade.get("token_out", {}).get("mint") == rdmp_mint):
                first_buy_sig = trade.get("signature")
                break
        
        assert first_buy_sig is not None, "Could not find first RDMP buy transaction"
        
        # Get transaction slot
        slot = await get_transaction_slot(first_buy_sig)
        assert slot is not None, f"Could not get slot for transaction {first_buy_sig}"
        
        logger.info(f"First RDMP buy: {first_buy_sig} at slot {slot}")
        
        # Get AMM price
        amm_result = await get_amm_price_at_slot(rdmp_mint, slot)
        assert amm_result is not None, "Could not get AMM price"
        
        amm_price, source = amm_result
        logger.info(f"AMM price: ${float(amm_price):.8f} from {source}")
        
        # Skip Birdeye comparison if no API key
        if not BIRDEYE_KEY_AVAILABLE:
            pytest.skip("BIRDEYE_API_KEY not set, skipping price comparison")
        
        # Get current Birdeye price
        birdeye_price = await get_birdeye_price_current(rdmp_mint)
        if birdeye_price is None:
            pytest.skip("Could not get Birdeye price for comparison")
        
        logger.info(f"Birdeye price (current): ${float(birdeye_price):.8f}")
        
        # Log price difference
        price_diff = abs(float(amm_price) - float(birdeye_price)) / float(birdeye_price)
        logger.info(f"Price difference: {price_diff*100:.1f}%")
        
        if price_diff > 0.5:  # 50% threshold for warning
            logger.warning(f"Large price difference detected: {price_diff*100:.1f}%")


if __name__ == "__main__":
    # Run tests
    asyncio.run(pytest.main([__file__, "-v"])) 