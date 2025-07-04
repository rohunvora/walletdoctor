"""
Unit tests for TradeAnalyticsAggregator (v0.8.0-summary)
"""

import pytest
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.lib.trade_analytics_aggregator import TradeAnalyticsAggregator


class TestTradeAnalyticsAggregator:
    """Test suite for trade analytics aggregation"""
    
    @pytest.fixture
    def aggregator(self):
        """Create a fresh aggregator instance"""
        return TradeAnalyticsAggregator()
    
    @pytest.fixture
    def sample_trades(self):
        """Sample enriched trades with P&L data"""
        now = datetime.now(timezone.utc)
        
        trades = [
            # Historical winning trade
            {
                "timestamp": (now - timedelta(days=60)).isoformat(),
                "action": "buy",
                "token": "BONK",
                "amount": 1000000,
                "value_usd": "1000",
                "token_in": {"symbol": "So111111", "amount": 10},
                "token_out": {"symbol": "BONK", "amount": 1000000}
            },
            {
                "timestamp": (now - timedelta(days=50)).isoformat(),
                "action": "sell",
                "token": "BONK",
                "amount": 1000000,
                "value_usd": "1500",
                "pnl_usd": "500"  # Win
            },
            
            # Recent losing trade
            {
                "timestamp": (now - timedelta(days=5)).isoformat(),
                "action": "buy",
                "token": "WIF",
                "amount": 100,
                "value_usd": "200",
                "token_in": {"symbol": "So111111", "amount": 2},
                "token_out": {"symbol": "WIF", "amount": 100}
            },
            {
                "timestamp": (now - timedelta(days=3)).isoformat(),
                "action": "sell",
                "token": "WIF",
                "amount": 100,
                "value_usd": "150",
                "pnl_usd": "-50"  # Loss
            },
            
            # Very recent trade (within 7d)
            {
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "action": "buy",
                "token": "PEPE",
                "amount": 500000,
                "value_usd": "100",
                "token_in": {"symbol": "So111111", "amount": 1},
                "token_out": {"symbol": "PEPE", "amount": 500000}
            }
        ]
        
        return trades
    
    @pytest.mark.asyncio
    async def test_aggregate_analytics_basic(self, aggregator, sample_trades):
        """Test basic analytics aggregation"""
        result = await aggregator.aggregate_analytics(sample_trades, "test_wallet")
        
        # Check structure
        assert result["wallet"] == "test_wallet"
        assert result["schema_version"] == "v0.8.0-summary"
        assert "generated_at" in result
        assert "time_window" in result
        assert "pnl" in result
        assert "volume" in result
        assert "top_tokens" in result
        assert "recent_windows" in result
    
    @pytest.mark.asyncio
    async def test_pnl_metrics(self, aggregator, sample_trades):
        """Test P&L calculations"""
        result = await aggregator.aggregate_analytics(sample_trades, "test_wallet")
        pnl = result["pnl"]
        
        # Should have 1 win (500) and 1 loss (-50)
        assert pnl["realized_usd"] == "450"
        assert pnl["wins"] == 1
        assert pnl["losses"] == 1
        assert pnl["win_rate"] == 0.5
        assert pnl["max_single_win_usd"] == "500"
        assert pnl["max_single_loss_usd"] == "-50"
    
    @pytest.mark.asyncio
    async def test_volume_metrics(self, aggregator, sample_trades):
        """Test volume calculations"""
        result = await aggregator.aggregate_analytics(sample_trades, "test_wallet")
        volume = result["volume"]
        
        assert volume["total_trades"] == 5
        assert volume["total_sol_volume"] == "13"  # 10 + 2 + 1
        assert float(volume["avg_trade_value_usd"]) > 0
        assert volume["trades_per_day"] > 0
    
    @pytest.mark.asyncio
    async def test_token_metrics(self, aggregator, sample_trades):
        """Test token-level metrics"""
        result = await aggregator.aggregate_analytics(sample_trades, "test_wallet")
        tokens = result["top_tokens"]
        
        # Should have 3 tokens
        assert len(tokens) == 3
        
        # Find BONK
        bonk = next(t for t in tokens if t["symbol"] == "BONK")
        assert bonk["trades"] == 2
        assert bonk["realized_pnl_usd"] == "500"
        
        # Find WIF
        wif = next(t for t in tokens if t["symbol"] == "WIF")
        assert wif["trades"] == 2
        assert wif["realized_pnl_usd"] == "-50"
    
    @pytest.mark.asyncio
    async def test_time_windows(self, aggregator, sample_trades):
        """Test time window calculations"""
        result = await aggregator.aggregate_analytics(sample_trades, "test_wallet")
        time_window = result["time_window"]
        
        assert time_window["start"] is not None
        assert time_window["end"] is not None
        assert time_window["days"] > 0
    
    @pytest.mark.asyncio
    async def test_recent_windows(self, aggregator, sample_trades):
        """Test recent window metrics (30d, 7d)"""
        result = await aggregator.aggregate_analytics(sample_trades, "test_wallet")
        recent = result["recent_windows"]
        
        # Last 30d should include recent trades (depends on test run date)
        # Since we're using relative dates, all recent trades should be in 30d window
        assert recent["last_30d"]["trades"] >= 2  # At least WIF sell and PEPE buy
        assert recent["last_30d"]["pnl_usd"] == "-50"  # Only WIF sold
        assert recent["last_30d"]["win_rate"] == 0  # 0 wins, 1 loss
        
        # Last 7d should include most recent trades
        assert recent["last_7d"]["trades"] >= 1  # At least PEPE buy
        # P&L depends on what's within 7d window
    
    @pytest.mark.asyncio
    async def test_empty_trades(self, aggregator):
        """Test handling of empty trade list"""
        result = await aggregator.aggregate_analytics([], "test_wallet")
        
        assert result["pnl"]["realized_usd"] == "0"
        assert result["pnl"]["wins"] == 0
        assert result["pnl"]["losses"] == 0
        assert result["volume"]["total_trades"] == 0
        assert len(result["top_tokens"]) == 0
    
    @pytest.mark.asyncio
    async def test_response_size(self, aggregator, sample_trades):
        """Test that response stays under 50KB"""
        # Create more trades to test size
        many_trades = []
        for i in range(100):
            trade = sample_trades[0].copy()
            trade["token"] = f"TOKEN{i}"
            many_trades.append(trade)
        
        result = await aggregator.aggregate_analytics(many_trades, "test_wallet")
        
        # Check size
        result_json = json.dumps(result)
        size_kb = len(result_json) / 1024
        
        assert size_kb < 50  # Must be under 50KB
        assert len(result["top_tokens"]) == 10  # Only top 10 tokens
    
    @pytest.mark.asyncio
    async def test_decimal_formatting(self, aggregator):
        """Test decimal formatting edge cases"""
        trades = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "sell",
                "token": "TEST",
                "amount": 100,
                "value_usd": "123.456789",
                "pnl_usd": "12.00"  # Should remove trailing zeros
            }
        ]
        
        result = await aggregator.aggregate_analytics(trades, "test_wallet")
        
        assert result["pnl"]["realized_usd"] == "12"  # .00 removed
        assert "." in result["volume"]["avg_trade_value_usd"]  # Has decimals
    
    @pytest.mark.asyncio
    async def test_performance_stats(self, aggregator, sample_trades):
        """Test that performance stats are tracked"""
        await aggregator.aggregate_analytics(sample_trades, "test_wallet")
        
        assert aggregator.stats["trades_processed"] == len(sample_trades)
        assert aggregator.stats["computation_time_ms"] >= 0  # May be 0 for small datasets
    
    @pytest.mark.asyncio
    async def test_malformed_trades(self, aggregator):
        """Test handling of malformed trade data"""
        bad_trades = [
            {"timestamp": "invalid", "action": "buy"},  # Bad timestamp
            {"action": "sell", "pnl_usd": "not_a_number"},  # Bad P&L
            {"timestamp": datetime.now(timezone.utc).isoformat()},  # Missing fields
        ]
        
        # Should not crash
        result = await aggregator.aggregate_analytics(bad_trades, "test_wallet")
        assert result["schema_version"] == "v0.8.0-summary" 