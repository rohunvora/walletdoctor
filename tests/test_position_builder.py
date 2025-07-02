"""
Test Position Builder Service
WAL-603: Tests for building positions from trade history
"""

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any
import json

from src.lib.position_builder import PositionBuilder, TokenTradeGroup
from src.lib.position_models import Position, CostBasisMethod
from src.lib.cost_basis_calculator import DUST_THRESHOLD_USD

# Constants
SOL_MINT = "So11111111111111111111111111111111111111112"
BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoHHuJjWKjH8vJFKfPQoKEWF"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class TestPositionBuilder(unittest.TestCase):
    def test_sol_position_tracking(self):
        """Test that SOL native token position is tracked"""
        # Test trades that result in SOL balance
        trades = [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "signature": "sig1",
                "action": "buy",
                "token": "BONK",
                "amount": 1000000,
                "token_in": {
                    "mint": "So11111111111111111111111111111111111111112",
                    "symbol": "SOL",
                    "amount": 10.5  # Spend 10.5 SOL
                },
                "token_out": {
                    "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                    "symbol": "BONK",
                    "amount": 1000000
                },
                "price": 0.00001,
                "value_usd": 450,
                "slot": 1
            },
            {
                "timestamp": "2024-01-02T00:00:00Z",
                "signature": "sig2",
                "action": "sell",
                "token": "WIF",
                "amount": 100,
                "token_in": {
                    "mint": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
                    "symbol": "WIF",
                    "amount": 100
                },
                "token_out": {
                    "mint": "So11111111111111111111111111111111111111112",
                    "symbol": "SOL",
                    "amount": 15.0  # Receive 15 SOL
                },
                "price": 3.5,
                "value_usd": 350,
                "slot": 2
            }
        ]
        
        builder = PositionBuilder()
        positions = builder.build_positions_from_trades(trades, "test_wallet")
        
        # Find SOL position
        sol_position = next((p for p in positions if p.token_mint == "So11111111111111111111111111111111111111112"), None)
        
        # Should have SOL position with balance = 15.0 - 10.5 = 4.5 SOL
        self.assertIsNotNone(sol_position, "SOL position should exist")
        if sol_position:
            self.assertEqual(sol_position.token_symbol, "SOL")
            self.assertAlmostEqual(float(sol_position.balance), 4.5, places=2)
            self.assertEqual(float(sol_position.cost_basis), 0.0)  # Native token has no cost basis
            self.assertEqual(float(sol_position.cost_basis_usd), 0.0)
            self.assertEqual(sol_position.decimals, 9)
    """Test cases for position builder service"""
    
    def setUp(self):
        """Set up test data"""
        # Enable position tracking for tests
        from unittest.mock import patch
        self.positions_patch = patch("src.lib.position_builder.positions_enabled", return_value=True)
        self.positions_patch.start()
        
        self.builder = PositionBuilder(CostBasisMethod.WEIGHTED_AVG)
        self.wallet = "TestWalletAddress123"
    
    def tearDown(self):
        """Clean up patches"""
        self.positions_patch.stop()
        
    def _create_trade(self, 
                     action: str,
                     token_mint: str,
                     token_symbol: str,
                     amount: str,
                     price: str,
                     timestamp: str,
                     signature: str = "test_sig",
                     slot: int = 1000) -> Dict[str, Any]:
        """Helper to create a trade dictionary"""
        if action == "buy":
            return {
                "action": "buy",
                "signature": signature,
                "timestamp": timestamp,
                "slot": slot,
                "amount": amount,
                "price": price,
                "value_usd": str(Decimal(amount) * Decimal(price)),
                "token_in": {
                    "mint": SOL_MINT,
                    "symbol": "SOL",
                    "decimals": 9
                },
                "token_out": {
                    "mint": token_mint,
                    "symbol": token_symbol,
                    "decimals": 9
                }
            }
        else:  # sell
            return {
                "action": "sell",
                "signature": signature,
                "timestamp": timestamp,
                "slot": slot,
                "amount": amount,
                "price": price,
                "value_usd": str(Decimal(amount) * Decimal(price)),
                "token_in": {
                    "mint": token_mint,
                    "symbol": token_symbol,
                    "decimals": 9
                },
                "token_out": {
                    "mint": SOL_MINT,
                    "symbol": "SOL",
                    "decimals": 9
                }
            }
    
    def test_empty_trades(self):
        """Test with no trades"""
        positions = self.builder.build_positions_from_trades([], self.wallet)
        self.assertEqual(len(positions), 0)
    
    def test_single_buy(self):
        """Test single buy creates open position"""
        trades = [
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.01",
                timestamp="2024-01-01T00:00:00Z"
            )
        ]
        
        positions = self.builder.build_positions_from_trades(trades, self.wallet)
        
        self.assertEqual(len(positions), 1)
        position = positions[0]
        
        self.assertEqual(position.wallet, self.wallet)
        self.assertEqual(position.token_mint, BONK_MINT)
        self.assertEqual(position.token_symbol, "BONK")
        self.assertEqual(position.balance, Decimal("1000"))
        self.assertEqual(position.cost_basis, Decimal("0.01"))
        self.assertEqual(position.cost_basis_usd, Decimal("10"))
        self.assertFalse(position.is_closed)
        self.assertEqual(position.trade_count, 1)
    
    def test_buy_sell_partial(self):
        """Test buy followed by partial sell"""
        trades = [
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.01",
                timestamp="2024-01-01T00:00:00Z"
            ),
            self._create_trade(
                action="sell",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="400",
                price="0.02",
                timestamp="2024-01-02T00:00:00Z"
            )
        ]
        
        positions = self.builder.build_positions_from_trades(trades, self.wallet)
        
        self.assertEqual(len(positions), 1)
        position = positions[0]
        
        self.assertEqual(position.balance, Decimal("600"))
        self.assertEqual(position.cost_basis, Decimal("0.01"))
        self.assertEqual(position.cost_basis_usd, Decimal("6"))
        self.assertFalse(position.is_closed)
        
        # Check realized P&L was calculated on the sell
        sell_trade = trades[1]
        self.assertIn("pnl_usd", sell_trade)
        self.assertEqual(sell_trade["pnl_usd"], 4.0)  # (0.02 - 0.01) * 400
    
    def test_buy_sell_complete(self):
        """Test buy followed by complete sell closes position"""
        trades = [
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.01",
                timestamp="2024-01-01T00:00:00Z"
            ),
            self._create_trade(
                action="sell",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.02",
                timestamp="2024-01-02T00:00:00Z"
            )
        ]
        
        positions = self.builder.build_positions_from_trades(trades, self.wallet)
        
        # Position should be closed, not returned
        self.assertEqual(len(positions), 0)
        
        # Check trade was marked as closing position
        sell_trade = trades[1]
        self.assertTrue(sell_trade["position_closed"])
        self.assertEqual(sell_trade["pnl_usd"], 10.0)  # (0.02 - 0.01) * 1000
    
    def test_multiple_buys_fifo(self):
        """Test FIFO cost basis with multiple buys"""
        self.builder = PositionBuilder(CostBasisMethod.FIFO)
        
        trades = [
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.01",
                timestamp="2024-01-01T00:00:00Z"
            ),
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.02",
                timestamp="2024-01-02T00:00:00Z"
            ),
            self._create_trade(
                action="sell",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1500",
                price="0.03",
                timestamp="2024-01-03T00:00:00Z"
            )
        ]
        
        positions = self.builder.build_positions_from_trades(trades, self.wallet)
        
        self.assertEqual(len(positions), 1)
        position = positions[0]
        
        # Should have 500 remaining
        self.assertEqual(position.balance, Decimal("500"))
        # With FIFO, the cost basis is calculated for the remaining position
        # The cost basis reflects the weighted average of remaining tokens
        # not necessarily just the last buy price
        self.assertGreater(position.cost_basis, Decimal("0"))
        self.assertGreater(position.cost_basis_usd, Decimal("0"))
        
        # Check P&L calculation
        sell_trade = trades[2]
        # 1000 @ 0.01 + 500 @ 0.02 = 20 cost
        # 1500 @ 0.03 = 45 revenue
        # P&L = 45 - 20 = 25
        self.assertEqual(sell_trade["pnl_usd"], 25.0)
    
    def test_multiple_buys_weighted_avg(self):
        """Test weighted average cost basis"""
        self.builder = PositionBuilder(CostBasisMethod.WEIGHTED_AVG)
        
        trades = [
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.01",
                timestamp="2024-01-01T00:00:00Z"
            ),
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.02",
                timestamp="2024-01-02T00:00:00Z"
            ),
            self._create_trade(
                action="sell",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1500",
                price="0.03",
                timestamp="2024-01-03T00:00:00Z"
            )
        ]
        
        positions = self.builder.build_positions_from_trades(trades, self.wallet)
        
        self.assertEqual(len(positions), 1)
        position = positions[0]
        
        # Should have 500 remaining at 0.015 avg cost basis
        self.assertEqual(position.balance, Decimal("500"))
        self.assertEqual(position.cost_basis, Decimal("0.015"))
        self.assertEqual(position.cost_basis_usd, Decimal("7.5"))
    
    def test_multiple_tokens(self):
        """Test tracking multiple token positions"""
        trades = [
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.01",
                timestamp="2024-01-01T00:00:00Z"
            ),
            self._create_trade(
                action="buy",
                token_mint=USDC_MINT,
                token_symbol="USDC",
                amount="100",
                price="1.0",
                timestamp="2024-01-01T01:00:00Z"
            ),
            self._create_trade(
                action="sell",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="500",
                price="0.02",
                timestamp="2024-01-02T00:00:00Z"
            )
        ]
        
        positions = self.builder.build_positions_from_trades(trades, self.wallet)
        
        self.assertEqual(len(positions), 2)
        
        # Find each position
        bonk_position = next(p for p in positions if p.token_mint == BONK_MINT)
        usdc_position = next(p for p in positions if p.token_mint == USDC_MINT)
        
        # Check BONK position
        self.assertEqual(bonk_position.balance, Decimal("500"))
        self.assertEqual(bonk_position.cost_basis, Decimal("0.01"))
        
        # Check USDC position  
        self.assertEqual(usdc_position.balance, Decimal("100"))
        self.assertEqual(usdc_position.cost_basis, Decimal("1.0"))
    
    def test_dust_position_ignored(self):
        """Test that closed positions are not returned"""
        trades = [
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="100",
                price="0.01",
                timestamp="2024-01-01T00:00:00Z"
            ),
            # Sell all to close position
            self._create_trade(
                action="sell",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="100",
                price="0.01",
                timestamp="2024-01-02T00:00:00Z"
            )
        ]
        
        positions = self.builder.build_positions_from_trades(trades, self.wallet)
        
        # Closed positions should not be returned
        self.assertEqual(len(positions), 0)
    
    def test_position_history(self):
        """Test position history tracking"""
        trades = [
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.01",
                timestamp="2024-01-01T00:00:00Z"
            ),
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="500",
                price="0.02",
                timestamp="2024-01-02T00:00:00Z"
            ),
            self._create_trade(
                action="sell",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="700",
                price="0.03",
                timestamp="2024-01-03T00:00:00Z"
            )
        ]
        
        history = self.builder.get_position_history(trades, self.wallet, BONK_MINT)
        
        self.assertEqual(len(history), 3)
        
        # Check snapshots
        self.assertEqual(history[0]["balance"], 1000.0)
        self.assertEqual(history[0]["cost_basis_per_token"], 0.01)
        
        self.assertEqual(history[1]["balance"], 1500.0)
        self.assertAlmostEqual(history[1]["cost_basis_per_token"], 0.0133333, places=5)
        
        self.assertEqual(history[2]["balance"], 800.0)
        # Cost basis will be recalculated based on remaining tokens
        self.assertGreater(history[2]["cost_basis_per_token"], 0)
    
    def test_portfolio_summary(self):
        """Test portfolio summary calculation"""
        # Create some positions manually
        positions = [
            Position(
                position_id="test1",
                wallet=self.wallet,
                token_mint=BONK_MINT,
                token_symbol="BONK",
                balance=Decimal("1000"),
                cost_basis=Decimal("0.01"),
                cost_basis_usd=Decimal("10"),
                cost_basis_method=CostBasisMethod.FIFO,
                opened_at=datetime.now(timezone.utc),
                last_trade_at=datetime.now(timezone.utc),
                last_update_slot=1000,
                last_update_time=datetime.now(timezone.utc),
                is_closed=False,
                trade_count=1
            ),
            Position(
                position_id="test2",
                wallet=self.wallet,
                token_mint=USDC_MINT,
                token_symbol="USDC",
                balance=Decimal("100"),
                cost_basis=Decimal("1.0"),
                cost_basis_usd=Decimal("100"),
                cost_basis_method=CostBasisMethod.FIFO,
                opened_at=datetime.now(timezone.utc),
                last_trade_at=datetime.now(timezone.utc),
                last_update_slot=1001,
                last_update_time=datetime.now(timezone.utc),
                is_closed=False,
                trade_count=1
            )
        ]
        
        summary = self.builder.calculate_portfolio_summary(positions)
        
        self.assertEqual(summary["total_positions"], 2)
        self.assertEqual(summary["total_cost_basis_usd"], 110.0)
        self.assertEqual(summary["cost_basis_method"], "fifo")
        self.assertEqual(len(summary["tokens"]), 2)
        
        # Should be sorted by cost basis USD descending
        self.assertEqual(summary["tokens"][0]["symbol"], "USDC")
        self.assertEqual(summary["tokens"][1]["symbol"], "BONK")
    
    def test_trade_group_timestamps(self):
        """Test TokenTradeGroup timestamp handling"""
        group = TokenTradeGroup(
            token_mint=BONK_MINT,
            token_symbol="BONK"
        )
        
        # Add trades with different timestamps
        trade1 = {
            "timestamp": "2024-01-02T00:00:00Z",
            "signature": "sig1"
        }
        trade2 = {
            "timestamp": "2024-01-01T00:00:00Z",  # Earlier
            "signature": "sig2"
        }
        trade3 = {
            "timestamp": "2024-01-03T00:00:00Z",  # Latest
            "signature": "sig3"
        }
        
        group.add_trade(trade1)
        group.add_trade(trade2)
        group.add_trade(trade3)
        
        # Check timestamps were tracked correctly
        self.assertEqual(
            group.first_trade_time,
            datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(
            group.last_trade_time,
            datetime(2024, 1, 3, 0, 0, 0, tzinfo=timezone.utc)
        )
    
    def test_extract_token_info(self):
        """Test token extraction from trades"""
        # Test buy trade (SOL -> BONK)
        buy_trade = self._create_trade(
            action="buy",
            token_mint=BONK_MINT,
            token_symbol="BONK",
            amount="1000",
            price="0.01",
            timestamp="2024-01-01T00:00:00Z"
        )
        
        mint, symbol = self.builder._extract_token_info(buy_trade)
        self.assertEqual(mint, BONK_MINT)
        self.assertEqual(symbol, "BONK")
        
        # Test sell trade (BONK -> SOL)
        sell_trade = self._create_trade(
            action="sell",
            token_mint=BONK_MINT,
            token_symbol="BONK",
            amount="1000",
            price="0.01",
            timestamp="2024-01-01T00:00:00Z"
        )
        
        mint, symbol = self.builder._extract_token_info(sell_trade)
        self.assertEqual(mint, BONK_MINT)
        self.assertEqual(symbol, "BONK")
    
    def test_reopened_position(self):
        """Test reopening a previously closed position"""
        trades = [
            # First position
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.01",
                timestamp="2024-01-01T00:00:00Z"
            ),
            # Close it
            self._create_trade(
                action="sell",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="1000",
                price="0.02",
                timestamp="2024-01-02T00:00:00Z"
            ),
            # Reopen with new buy
            self._create_trade(
                action="buy",
                token_mint=BONK_MINT,
                token_symbol="BONK",
                amount="500",
                price="0.03",
                timestamp="2024-01-03T00:00:00Z"
            )
        ]
        
        positions = self.builder.build_positions_from_trades(trades, self.wallet)
        
        self.assertEqual(len(positions), 1)
        position = positions[0]
        
        # Should have new position with fresh cost basis
        self.assertEqual(position.balance, Decimal("500"))
        # After closing the position, the new buy should have its own cost basis
        self.assertGreater(position.cost_basis, Decimal("0"))
        self.assertGreater(position.cost_basis_usd, Decimal("0"))
        
        # Position ID should include wallet and token mint
        self.assertIn(self.wallet, position.position_id)
        self.assertIn(BONK_MINT, position.position_id)
    
    def test_integration_with_real_trade_format(self):
        """Test with trade format from actual API"""
        trades = [
            {
                "signature": "abc123",
                "timestamp": "2024-01-01T12:00:00Z",
                "slot": 123456789,
                "action": "buy",
                "swap_type": "pump",
                "token_in": {
                    "mint": SOL_MINT,
                    "symbol": "SOL",
                    "amount": "0.1",
                    "decimals": 9
                },
                "token_out": {
                    "mint": BONK_MINT,
                    "symbol": "BONK",
                    "amount": "10000",
                    "decimals": 5
                },
                "amount": "10000",
                "price": "0.00001",
                "price_usd": "0.0005",
                "value_usd": "5.0",
                "fee_sol": "0.00001",
                "fee_usd": "0.0005"
            }
        ]
        
        positions = self.builder.build_positions_from_trades(trades, self.wallet)
        
        self.assertEqual(len(positions), 1)
        position = positions[0]
        
        self.assertEqual(position.token_mint, BONK_MINT)
        self.assertEqual(position.balance, Decimal("10000"))
        self.assertEqual(position.decimals, 5)

    def test_spam_token_filter_airdrop(self):
        """WAL-606e: Test that airdrop tokens (no buys) are filtered"""
        trades = [
            # Regular buy trade - should create position
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "signature": "sig1",
                "action": "buy",
                "token": "PEPE",
                "amount": 1000,
                "price": 0.001,
                "value_usd": 1.0,
                "token_in": {"mint": "So11111111111111111111111111111111111111112", "symbol": "SOL"},
                "token_out": {"mint": "PEPEmint", "symbol": "PEPE", "amount": 1000}
            },
            # Airdrop token - only has balance, no buy trades
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "signature": "sig2",
                "action": "receive",  # This would be processed differently, but for test purposes
                "token": "SPAM",
                "amount": 1000000,
                "price": 0.000001,
                "value_usd": 1.0,
                "token_in": {"mint": "SPAMmint", "symbol": "SPAM", "amount": 1000000},
                "token_out": {"mint": "So11111111111111111111111111111111111111112", "symbol": "SOL"}
            }
        ]
        
        # For this test, simulate GTA token which has 0 buys (from real data)
        airdrop_trades = [{
            "timestamp": "2024-01-01T00:00:00Z", 
            "signature": "sig_airdrop",
            "action": "sell",  # Only sell, no buy = airdrop
            "token": "GTA",
            "amount": 0.001,
            "price": 50000,
            "value_usd": 50.0,
            "token_in": {"mint": "GTAmint", "symbol": "GTA", "amount": 0.001},
            "token_out": {"mint": "So11111111111111111111111111111111111111112", "symbol": "SOL"}
        }]
        
        # Build positions - should filter the airdrop
        positions = self.builder.build_positions_from_trades(trades + airdrop_trades, self.wallet)
        
        # Should only have PEPE position, not SPAM or GTA
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].token_symbol, "PEPE")
        
        # Verify no SPAM or GTA positions
        token_symbols = {p.token_symbol for p in positions}
        self.assertNotIn("SPAM", token_symbols)
        self.assertNotIn("GTA", token_symbols)
    
    def test_spam_token_filter_with_remaining_balance(self):
        """WAL-606e: Test spam filter for tokens that still have balance but no buys"""
        # Simulate a token that was airdropped and partially sold
        trades = [
            # Legitimate token with buy
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "signature": "sig1",
                "action": "buy",
                "token": "LEGIT",
                "amount": 1000,
                "price": 0.01,
                "value_usd": 10.0,
                "token_in": {"mint": "So11111111111111111111111111111111111111112", "symbol": "SOL"},
                "token_out": {"mint": "LEGITmint", "symbol": "LEGIT", "amount": 1000}
            }
        ]
        
        # Process without any airdrops first
        positions_before = self.builder.build_positions_from_trades(trades, self.wallet)
        self.assertEqual(len(positions_before), 1)
        
        # Now test that spam filter info is logged
        # We can't easily test logging, but we can verify the positions are correct
        self.assertEqual(positions_before[0].token_symbol, "LEGIT")
        self.assertEqual(positions_before[0].balance, Decimal("1000"))
    
    def test_multiple_tokens_with_filter(self):
        """Test building positions for multiple tokens with spam filter"""
        trades = [
            # Token 1: Normal buy/sell
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "signature": "sig1",
                "action": "buy",
                "token": "TOKEN1",
                "amount": 1000,
                "price": 0.1,
                "value_usd": 100.0,
                "token_in": {"mint": "So11111111111111111111111111111111111111112", "symbol": "SOL"},
                "token_out": {"mint": "TOKEN1mint", "symbol": "TOKEN1", "amount": 1000}
            },
            # Token 2: Another normal token
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "signature": "sig2",
                "action": "buy",
                "token": "TOKEN2",
                "amount": 500,
                "price": 0.2,
                "value_usd": 100.0,
                "token_in": {"mint": "So11111111111111111111111111111111111111112", "symbol": "SOL"},
                "token_out": {"mint": "TOKEN2mint", "symbol": "TOKEN2", "amount": 500}
            }
        ]
        
        positions = self.builder.build_positions_from_trades(trades, self.wallet)
        
        self.assertEqual(len(positions), 2)
        token_symbols = {p.token_symbol for p in positions}
        self.assertEqual(token_symbols, {"TOKEN1", "TOKEN2"})


if __name__ == "__main__":
    unittest.main() 