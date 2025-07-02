#!/usr/bin/env python3
"""
Test market cap accuracy on real trades
"""

import pytest
import asyncio
import json
import os
from decimal import Decimal
from unittest.mock import patch, MagicMock
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3
from src.lib.mc_calculator import calculate_market_cap
from src.api.wallet_analytics_api_v3 import _enrich_trades_with_market_cap

# Check if HELIUS_KEY is available
HELIUS_KEY_AVAILABLE = bool(os.getenv("HELIUS_KEY"))

# Load expected values
with open(os.path.join(os.path.dirname(__file__), "fixtures", "real_trades.json")) as f:
    EXPECTED_DATA = json.load(f)

@pytest.mark.skipif(
    not HELIUS_KEY_AVAILABLE,
    reason="HELIUS_KEY environment variable not set"
)
class TestRealTradeAccuracy:
    """Test market cap accuracy on real trades"""
    
    async def get_wallet_trades(self):
        """Fetch trades for the test wallet"""
        wallet = EXPECTED_DATA["wallet"]
        
        async with BlockchainFetcherV3(skip_pricing=True) as fetcher:
            result = await fetcher.fetch_wallet_trades(wallet)
        
        # Enrich with market cap data
        trades = await _enrich_trades_with_market_cap(result.get("trades", []))
        return trades
    
    def find_matching_trade(self, trades, expected):
        """Find a trade matching the expected criteria"""
        matching_trades = []
        
        for trade in trades:
            # Check token mint
            token_in_mint = trade.get("token_in", {}).get("mint", "")
            token_out_mint = trade.get("token_out", {}).get("mint", "")
            
            if expected["action"] == "buy":
                if token_out_mint == expected["mint"]:
                    sol_amount = trade.get("token_in", {}).get("amount", 0)
                    if abs(sol_amount - expected["sol_delta"]) < 0.1:
                        matching_trades.append(trade)
            else:  # sell
                if token_in_mint == expected["mint"]:
                    sol_amount = -trade.get("token_out", {}).get("amount", 0)
                    if abs(sol_amount - expected["sol_delta"]) < 0.1:
                        matching_trades.append(trade)
        
        # Return the nth matching trade (based on trade_number)
        if len(matching_trades) >= expected["trade_number"]:
            return matching_trades[expected["trade_number"] - 1]
        
        return None
    
    @pytest.mark.asyncio
    async def test_trade_market_caps(self):
        """Test that market caps are accurate for each expected trade"""
        # Get trades once
        wallet_trades = await self.get_wallet_trades()
        errors = []
        
        for expected in EXPECTED_DATA["expected_trades"]:
            trade = self.find_matching_trade(wallet_trades, expected)
            
            if not trade:
                errors.append(f"Could not find trade: {expected['symbol']} #{expected['trade_number']}")
                continue
            
            # Get market cap data from the appropriate token
            if expected["action"] == "buy":
                mc_data = trade.get("token_out", {}).get("market_cap", {})
            else:
                mc_data = trade.get("token_in", {}).get("market_cap", {})
            
            if not mc_data:
                errors.append(f"No market cap data for {expected['symbol']} #{expected['trade_number']}")
                continue
            
            # Check confidence level
            if mc_data.get("confidence") != expected["expected_confidence"]:
                errors.append(
                    f"{expected['symbol']} #{expected['trade_number']}: "
                    f"confidence is '{mc_data.get('confidence')}', expected '{expected['expected_confidence']}'"
                )
            
            # Check market cap value (within tolerance)
            mc_value = mc_data.get("market_cap", 0)
            expected_mc = expected["expected_mc"]
            tolerance = expected["tolerance"]
            
            if mc_value == 0:
                errors.append(f"{expected['symbol']} #{expected['trade_number']}: market cap is 0")
                continue
            
            # Calculate percentage difference
            diff_pct = abs(mc_value - expected_mc) / expected_mc
            
            if diff_pct > tolerance:
                errors.append(
                    f"{expected['symbol']} #{expected['trade_number']}: "
                    f"MC ${mc_value:,.0f} is {diff_pct*100:.1f}% off from expected ${expected_mc:,.0f}"
                )
        
        if errors:
            pytest.fail("\n".join(errors))
    
    @pytest.mark.asyncio
    async def test_token_pnl(self):
        """Test that PNL calculations are accurate"""
        # Get trades once
        wallet_trades = await self.get_wallet_trades()
        
        # Group trades by token
        token_trades = {}
        for trade in wallet_trades:
            token_in_mint = trade.get("token_in", {}).get("mint", "")
            token_out_mint = trade.get("token_out", {}).get("mint", "")
            
            # Find which token is not SOL
            for mint in [token_in_mint, token_out_mint]:
                if mint and "11111111" not in mint:  # Not SOL
                    if mint not in token_trades:
                        token_trades[mint] = []
                    token_trades[mint].append(trade)
        
        errors = []
        
        for mint, expected_pnl in EXPECTED_DATA["expected_pnl"].items():
            if mint not in token_trades:
                errors.append(f"No trades found for {expected_pnl['symbol']}")
                continue
            
            # Calculate net SOL for this token
            net_sol = 0
            for trade in token_trades[mint]:
                if trade.get("action") == "buy":
                    # SOL spent (negative)
                    net_sol -= trade.get("token_in", {}).get("amount", 0)
                else:  # sell
                    # SOL received (positive)
                    net_sol += trade.get("token_out", {}).get("amount", 0)
            
            # Check PNL accuracy
            expected_val = expected_pnl["pnl_sol"]
            tolerance = expected_pnl["tolerance"]
            
            if abs(net_sol - expected_val) > tolerance:
                errors.append(
                    f"{expected_pnl['symbol']}: "
                    f"PNL {net_sol:.2f} SOL differs from expected {expected_val:.2f} SOL"
                )
        
        if errors:
            pytest.fail("\n".join(errors))
    
    @pytest.mark.asyncio
    async def test_pump_price_source(self):
        """Test that pump.fun tokens use AMM price, not Jupiter quotes"""
        # Test fakeout token specifically
        fakeout_mint = "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump"
        
        result = await calculate_market_cap(fakeout_mint)
        
        assert result is not None, "Failed to calculate market cap for fakeout"
        assert result.source != "helius_jupiter_quote", f"Pump token using Jupiter quote instead of AMM: {result.source}"
        # Since our implementation uses mock data, we expect high confidence
        assert result.confidence == "high", f"Expected high confidence, got {result.confidence}" 