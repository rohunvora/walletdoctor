"""
Unit tests for TradeEnricher (TRD-002)
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

from src.lib.trade_enricher import TradeEnricher, SOL_MINT


class TestTradeEnricher:
    """Test suite for trade enrichment functionality"""
    
    @pytest.fixture
    def enricher(self):
        """Create a fresh enricher instance"""
        return TradeEnricher()
    
    @pytest.fixture
    def buy_trade(self):
        """Sample buy trade (SOL -> Token)"""
        return {
            "timestamp": "2025-01-15T10:00:00",
            "signature": "buy_sig_1",
            "action": "buy",
            "token": "PUMP",
            "amount": 1000.0,
            "token_in": {
                "mint": SOL_MINT,
                "symbol": "SOL",
                "amount": 10.0
            },
            "token_out": {
                "mint": "PUMPmintaddress",
                "symbol": "PUMP", 
                "amount": 1000.0
            },
            "price": None,
            "value_usd": None,
            "pnl_usd": 0.0,
            "fees_usd": 0.0,
            "priced": False,
            "dex": "JUPITER",
            "tx_type": "swap"
        }
    
    @pytest.fixture
    def sell_trade(self):
        """Sample sell trade (Token -> SOL)"""
        return {
            "timestamp": "2025-01-15T11:00:00",
            "signature": "sell_sig_1",
            "action": "sell",
            "token": "PUMP",
            "amount": 500.0,
            "token_in": {
                "mint": "PUMPmintaddress",
                "symbol": "PUMP",
                "amount": 500.0
            },
            "token_out": {
                "mint": SOL_MINT,
                "symbol": "SOL",
                "amount": 6.0
            },
            "price": None,
            "value_usd": None,
            "pnl_usd": 0.0,
            "fees_usd": 0.0,
            "priced": False,
            "dex": "JUPITER",
            "tx_type": "swap"
        }
    
    @pytest.mark.asyncio
    @patch('src.lib.trade_enricher.get_sol_price_usd')
    async def test_enrich_buy_trade(self, mock_sol_price, enricher, buy_trade):
        """Test enriching a buy trade with pricing"""
        # Mock SOL price at $150
        mock_sol_price.return_value = Decimal("150.00")
        
        # Enrich single trade
        enriched = await enricher.enrich_trades([buy_trade])
        
        assert len(enriched) == 1
        trade = enriched[0]
        
        # Check calculated fields
        assert Decimal(trade["price_sol"]) == Decimal("0.01")  # 10 SOL / 1000 PUMP
        assert Decimal(trade["price_usd"]) == Decimal("1.5")   # 0.01 * 150
        assert Decimal(trade["value_usd"]) == Decimal("1500")  # 10 SOL * 150
        assert Decimal(trade["pnl_usd"]) == Decimal("0")      # No P&L on buys
        
        # Check stats
        assert enricher.enrichment_stats["trades_priced"] == 1
        assert enricher.enrichment_stats["trades_with_pnl"] == 0
    
    @pytest.mark.asyncio
    @patch('src.lib.trade_enricher.get_sol_price_usd')
    async def test_enrich_sell_trade_with_profit(self, mock_sol_price, enricher, buy_trade, sell_trade):
        """Test enriching a sell trade with positive P&L"""
        # Mock SOL price at $150
        mock_sol_price.return_value = Decimal("150.00")
        
        # Process buy first to establish cost basis
        await enricher.enrich_trades([buy_trade])
        
        # Then process sell
        enriched = await enricher.enrich_trades([sell_trade])
        trade = enriched[0]
        
        # Check calculated fields
        assert Decimal(trade["price_sol"]) == Decimal("0.012")   # 6 SOL / 500 PUMP
        assert Decimal(trade["price_usd"]) == Decimal("1.8")     # 0.012 * 150
        assert Decimal(trade["value_usd"]) == Decimal("900")     # 6 SOL * 150
        
        # P&L calculation:
        # Bought 1000 @ $1.5, selling 500 @ $1.8
        # Cost basis: 500 * $1.5 = $750
        # Proceeds: 500 * $1.8 = $900
        # P&L: $900 - $750 = $150
        assert Decimal(trade["pnl_usd"]) == Decimal("150")
        
        # Check stats
        assert enricher.enrichment_stats["trades_with_pnl"] == 1
    
    @pytest.mark.asyncio
    @patch('src.lib.trade_enricher.get_sol_price_usd')
    async def test_enrich_sell_trade_with_loss(self, mock_sol_price, enricher):
        """Test enriching a sell trade with negative P&L"""
        # Mock SOL price at $150
        mock_sol_price.return_value = Decimal("150.00")
        
        # Buy high
        buy_trade = {
            "timestamp": "2025-01-15T10:00:00",
            "action": "buy",
            "token_in": {"mint": SOL_MINT, "amount": 10.0},
            "token_out": {"mint": "TOKEN", "amount": 1000.0}
        }
        
        # Sell low
        sell_trade = {
            "timestamp": "2025-01-15T11:00:00",
            "action": "sell",
            "token_in": {"mint": "TOKEN", "amount": 1000.0},
            "token_out": {"mint": SOL_MINT, "amount": 8.0}
        }
        
        # Process both trades
        all_trades = await enricher.enrich_trades([buy_trade, sell_trade])
        sell = all_trades[1]
        
        # P&L calculation:
        # Bought 1000 @ $1.5 (10 SOL * 150 / 1000) = $1500 cost
        # Sold 1000 @ $1.2 (8 SOL * 150 / 1000) = $1200 proceeds
        # P&L: $1200 - $1500 = -$300
        assert Decimal(sell["pnl_usd"]) == Decimal("-300")
    
    @pytest.mark.asyncio
    @patch('src.lib.trade_enricher.get_sol_price_usd')
    async def test_fifo_partial_sell(self, mock_sol_price, enricher):
        """Test FIFO logic with partial sells"""
        mock_sol_price.return_value = Decimal("150.00")
        
        # Two buys at different prices
        buy1 = {
            "timestamp": "2025-01-15T10:00:00",
            "action": "buy",
            "token_in": {"mint": SOL_MINT, "amount": 10.0},
            "token_out": {"mint": "TOKEN", "amount": 1000.0}
        }
        
        buy2 = {
            "timestamp": "2025-01-15T11:00:00",
            "action": "buy",
            "token_in": {"mint": SOL_MINT, "amount": 20.0},
            "token_out": {"mint": "TOKEN", "amount": 1000.0}
        }
        
        # Sell part of holdings
        sell = {
            "timestamp": "2025-01-15T12:00:00",
            "action": "sell",
            "token_in": {"mint": "TOKEN", "amount": 1500.0},
            "token_out": {"mint": SOL_MINT, "amount": 22.5}
        }
        
        await enricher.enrich_trades([buy1, buy2])
        enriched = await enricher.enrich_trades([sell])
        
        # FIFO P&L:
        # First 1000 @ $1.5 = $1500 cost
        # Next 500 @ $3.0 = $1500 cost
        # Total cost: $3000
        # Proceeds: 22.5 SOL * 150 = $3375
        # P&L: $3375 - $3000 = $375
        assert Decimal(enriched[0]["pnl_usd"]) == Decimal("375")
    
    @pytest.mark.asyncio
    @patch('src.lib.trade_enricher.get_sol_price_usd')
    async def test_missing_sol_price(self, mock_sol_price, enricher, buy_trade):
        """Test handling when SOL price is unavailable"""
        mock_sol_price.return_value = None
        
        enriched = await enricher.enrich_trades([buy_trade])
        trade = enriched[0]
        
        # All price fields should be null
        assert trade["price_sol"] is None
        assert trade["price_usd"] is None
        assert trade["value_usd"] is None
        assert trade["pnl_usd"] is None
        
        # Check stats
        assert enricher.enrichment_stats["null_sol_prices"] == 1
        assert enricher.enrichment_stats["trades_priced"] == 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, enricher):
        """Test graceful error handling"""
        # Invalid trade with missing fields
        invalid_trade = {"signature": "bad_trade"}
        
        enriched = await enricher.enrich_trades([invalid_trade])
        
        assert len(enriched) == 1
        trade = enriched[0]
        
        # Should have null enrichment fields
        assert trade["price_sol"] is None
        assert trade["price_usd"] is None
        assert trade["value_usd"] is None
        assert trade["pnl_usd"] is None
        
        # Check error was counted
        assert enricher.enrichment_stats["errors"] == 1
    
    @pytest.mark.asyncio
    @patch('src.lib.trade_enricher.get_sol_price_usd')
    async def test_token_to_token_swap(self, mock_sol_price, enricher):
        """Test token-to-token swaps are skipped"""
        mock_sol_price.return_value = Decimal("150.00")
        
        # Token to token swap (no SOL involved)
        swap = {
            "timestamp": "2025-01-15T10:00:00",
            "action": "buy",
            "token_in": {"mint": "USDC", "amount": 100.0},
            "token_out": {"mint": "PUMP", "amount": 50.0}
        }
        
        enriched = await enricher.enrich_trades([swap])
        trade = enriched[0]
        
        # Should not be priced
        assert trade["price_sol"] is None
        assert trade["price_usd"] is None
        assert trade["value_usd"] is None
        assert trade["pnl_usd"] is None
        
        assert enricher.enrichment_stats["trades_priced"] == 0 