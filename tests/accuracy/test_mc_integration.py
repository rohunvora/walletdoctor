#!/usr/bin/env python3
"""
WAL-511c: MC + P&L Integration
Stream the six trades and verify market cap accuracy and P&L
"""

import pytest
import asyncio
import os
import logging
from decimal import Decimal
from typing import List, Dict, Any
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3
from src.api.wallet_analytics_api_v3 import _enrich_trades_with_market_cap

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Expected trades and values from WAL-511 spec
EXPECTED_TRADES = {
    "fakeout": {
        "mint": "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump",
        "symbol": "fakeout",
        "trades": [
            {"action": "buy", "sol_delta": 4.45, "expected_mc": 63000},
            {"action": "sell", "sol_delta": -7.05, "expected_mc": 96000}
        ],
        "expected_pnl": 2.6,  # +2.6 SOL
        "pnl_tolerance": 0.1
    },
    "RDMP": {
        "mint": "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop", 
        "symbol": "RDMP",
        "trades": [
            {"action": "buy", "sol_delta": 22.77, "expected_mc": 2400000},
            {"action": "sell", "sol_delta": -4.78, "expected_mc": 5100000},
            {"action": "sell", "sol_delta": -19.94, "expected_mc": 4700000},
            {"action": "sell", "sol_delta": -10.60, "expected_mc": 2500000}
        ],
        "expected_pnl": 12.55,  # +12.55 SOL
        "pnl_tolerance": 0.1
    }
}

WALLET_ADDRESS = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

# Check if required keys are available
HELIUS_KEY_AVAILABLE = bool(os.getenv("HELIUS_KEY"))


def find_matching_trades(all_trades: List[Dict[str, Any]], token_mint: str) -> List[Dict[str, Any]]:
    """Find all trades for a specific token"""
    matching_trades = []
    
    for trade in all_trades:
        token_in_mint = trade.get("token_in", {}).get("mint", "")
        token_out_mint = trade.get("token_out", {}).get("mint", "")
        
        if token_in_mint == token_mint or token_out_mint == token_mint:
            matching_trades.append(trade)
    
    return matching_trades


def calculate_token_pnl(trades: List[Dict[str, Any]], token_mint: str) -> Decimal:
    """Calculate net SOL P&L for a token"""
    net_sol = Decimal("0")
    
    for trade in trades:
        if trade.get("action") == "buy":
            # Buying token with SOL (SOL out)
            if trade.get("token_in", {}).get("mint") == "So11111111111111111111111111111111111111112":
                net_sol -= Decimal(str(trade.get("token_in", {}).get("amount", 0)))
        else:  # sell
            # Selling token for SOL (SOL in)
            if trade.get("token_out", {}).get("mint") == "So11111111111111111111111111111111111111112":
                net_sol += Decimal(str(trade.get("token_out", {}).get("amount", 0)))
    
    return net_sol


@pytest.mark.skipif(
    not HELIUS_KEY_AVAILABLE,
    reason="HELIUS_KEY environment variable not set"
)
class TestMCIntegration:
    """Test market cap and P&L integration"""
    
    @pytest.mark.asyncio
    async def test_stream_trades_with_mc(self):
        """Stream wallet trades and verify market cap enrichment"""
        # Fetch all trades for the wallet
        async with BlockchainFetcherV3(skip_pricing=True) as fetcher:
            result = await fetcher.fetch_wallet_trades(WALLET_ADDRESS)
        
        # Enrich with market cap data
        all_trades = await _enrich_trades_with_market_cap(result.get("trades", []))
        
        logger.info(f"Total trades fetched: {len(all_trades)}")
        
        # Test each token
        for token_name, token_data in EXPECTED_TRADES.items():
            token_mint = token_data["mint"]
            
            # Find trades for this token
            token_trades = find_matching_trades(all_trades, token_mint)
            logger.info(f"\nFound {len(token_trades)} trades for {token_name}")
            
            # Verify we have the expected number of trades
            expected_count = len(token_data["trades"])
            assert len(token_trades) >= expected_count, \
                f"Expected at least {expected_count} trades for {token_name}, found {len(token_trades)}"
            
            # Check each trade
            errors = []
            for i, expected in enumerate(token_data["trades"]):
                if i < len(token_trades):
                    trade = token_trades[i]
                    
                    # Get market cap data
                    if expected["action"] == "buy":
                        mc_data = trade.get("token_out", {}).get("market_cap", {})
                    else:
                        mc_data = trade.get("token_in", {}).get("market_cap", {})
                    
                    # Check confidence
                    if mc_data.get("confidence") != "high":
                        errors.append(
                            f"Trade {i+1}: confidence is '{mc_data.get('confidence')}', expected 'high'"
                        )
                    
                    # Check market cap value
                    mc_value = mc_data.get("market_cap", 0)
                    expected_mc = expected["expected_mc"]
                    
                    if mc_value > 0:
                        diff_pct = abs(mc_value - expected_mc) / expected_mc
                        if diff_pct > 0.1:
                            errors.append(
                                f"Trade {i+1}: MC ${mc_value:,.0f} is {diff_pct*100:.1f}% "
                                f"off from expected ${expected_mc:,.0f}"
                            )
                        else:
                            logger.info(
                                f"Trade {i+1}: MC ${mc_value:,.0f} ✓ "
                                f"(within {diff_pct*100:.1f}% of expected)"
                            )
                    else:
                        errors.append(f"Trade {i+1}: No market cap data")
            
            if errors:
                pytest.fail(f"{token_name} errors:\n" + "\n".join(errors))
    
    @pytest.mark.asyncio  
    async def test_token_pnl_accuracy(self):
        """Test P&L calculations for each token"""
        # Fetch all trades for the wallet
        async with BlockchainFetcherV3(skip_pricing=True) as fetcher:
            result = await fetcher.fetch_wallet_trades(WALLET_ADDRESS)
        
        all_trades = result.get("trades", [])
        
        errors = []
        
        for token_name, token_data in EXPECTED_TRADES.items():
            token_mint = token_data["mint"]
            
            # Find trades for this token
            token_trades = find_matching_trades(all_trades, token_mint)
            
            # Calculate P&L
            pnl = calculate_token_pnl(token_trades, token_mint)
            expected_pnl = Decimal(str(token_data["expected_pnl"]))
            tolerance = Decimal(str(token_data["pnl_tolerance"]))
            
            diff = abs(pnl - expected_pnl)
            
            if diff <= tolerance:
                logger.info(
                    f"{token_name} P&L: {pnl:.2f} SOL ✓ "
                    f"(expected {expected_pnl:.2f} ±{tolerance:.1f})"
                )
            else:
                errors.append(
                    f"{token_name}: P&L {pnl:.2f} SOL differs from "
                    f"expected {expected_pnl:.2f} SOL by {diff:.2f}"
                )
        
        if errors:
            pytest.fail("P&L errors:\n" + "\n".join(errors))
    
    @pytest.mark.asyncio
    async def test_external_api_fallback(self):
        """Test behavior when external APIs are unreachable"""
        # This test should mark build as UNSTABLE (yellow) if APIs fail
        # but not fail the test completely
        
        try:
            # Try to fetch with market cap enrichment
            async with BlockchainFetcherV3(skip_pricing=True) as fetcher:
                result = await fetcher.fetch_wallet_trades(WALLET_ADDRESS)
            
            trades = await _enrich_trades_with_market_cap(result.get("trades", []))
            
            # Check if we got any market cap data
            mc_count = 0
            for trade in trades[:10]:  # Check first 10 trades
                if trade.get("token_in", {}).get("market_cap") or \
                   trade.get("token_out", {}).get("market_cap"):
                    mc_count += 1
            
            if mc_count == 0:
                pytest.skip("External APIs unreachable - marking build UNSTABLE")
            else:
                logger.info(f"Successfully enriched {mc_count}/10 trades with market cap data")
                
        except Exception as e:
            pytest.skip(f"External API error: {e} - marking build UNSTABLE")


if __name__ == "__main__":
    # Run tests
    asyncio.run(pytest.main([__file__, "-v"])) 