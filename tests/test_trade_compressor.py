"""
Unit tests for TradeCompressor (v0.7.2-compact)
"""

import pytest
import json
from datetime import datetime
from decimal import Decimal

from src.lib.trade_compressor import TradeCompressor


class TestTradeCompressor:
    """Test suite for trade compression functionality"""
    
    @pytest.fixture
    def compressor(self):
        """Create a fresh compressor instance"""
        return TradeCompressor()
    
    @pytest.fixture
    def sample_trade(self):
        """Sample enriched trade"""
        return {
            "timestamp": "2025-01-15T10:00:00",
            "signature": "5s53x9ETa3YhzV6NTVGC3ezHWKqASdakKq3UXdLXKbWRWrFqXZeCv",
            "action": "buy",
            "token": "BONK",
            "amount": 1000000.0,
            "token_in": {
                "mint": "So11111111111111111111111111111111111111112",
                "symbol": "SOL",
                "amount": 10.0
            },
            "token_out": {
                "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                "symbol": "BONK",
                "amount": 1000000.0
            },
            "price_sol": "0.00001",
            "price_usd": "0.0015",
            "value_usd": "1500.00",
            "pnl_usd": "0",
            "fees_usd": 0.25,
            "priced": True,
            "dex": "JUPITER",
            "tx_type": "swap"
        }
    
    def test_compress_single_trade(self, compressor, sample_trade):
        """Test compressing a single trade"""
        result = compressor.compress_trades([sample_trade], "test_wallet")
        
        assert result["wallet"] == "test_wallet"
        assert result["schema_version"] == "v0.7.2-compact"
        assert result["field_map"] == ["ts", "act", "tok", "amt", "p_sol", "p_usd", "val", "pnl"]
        assert len(result["trades"]) == 1
        
        # Check compressed trade
        compressed = result["trades"][0]
        assert len(compressed) == 8  # 8 fields
        assert isinstance(compressed[0], int)  # Should be a Unix timestamp
        assert compressed[0] > 1700000000  # Reasonable timestamp
        assert compressed[1] == 1  # buy = 1
        assert compressed[2] == "BONK"
        assert compressed[3] == 1000000.0
        assert compressed[4] == "0.00001"
        assert compressed[5] == "0.0015"
        assert compressed[6] == "1500"  # Decimal cleaned up
        assert compressed[7] == "0"
    
    def test_compress_sell_trade(self, compressor):
        """Test sell trade compression"""
        sell_trade = {
            "timestamp": "2025-01-15T11:00:00",
            "action": "sell",
            "token": "BONK",
            "amount": 500000.0,
            "price_sol": "0.000012",
            "price_usd": "0.0018",
            "value_usd": "900.00",
            "pnl_usd": "150.25"
        }
        
        result = compressor.compress_trades([sell_trade], "test_wallet")
        compressed = result["trades"][0]
        
        assert compressed[1] == 0  # sell = 0
        assert compressed[7] == "150.25"  # P&L preserved
    
    def test_decimal_formatting(self, compressor):
        """Test decimal value formatting"""
        trades = [
            {
                "timestamp": "2025-01-15T10:00:00",
                "action": "buy",
                "token": "TEST",
                "amount": 1000,
                "price_sol": "0.0000001234567890",  # Very small number
                "price_usd": "0.00001500000",      # Trailing zeros
                "value_usd": "15.0",               # Single decimal
                "pnl_usd": "0.0"                   # Zero with decimal
            }
        ]
        
        result = compressor.compress_trades(trades, "test_wallet")
        compressed = result["trades"][0]
        
        assert compressed[4] == "0.00000012"  # Limited to 8 decimals
        assert compressed[5] == "0.000015"    # Trailing zeros removed
        assert compressed[6] == "15"          # Decimal point removed
        assert compressed[7] == "0"           # Clean zero
    
    def test_missing_fields(self, compressor):
        """Test handling of missing enriched fields"""
        trade = {
            "timestamp": "2025-01-15T10:00:00",
            "action": "buy",
            "token": "TEST",
            "amount": 1000,
            # No price fields
        }
        
        result = compressor.compress_trades([trade], "test_wallet")
        compressed = result["trades"][0]
        
        # Missing fields should be empty strings
        assert compressed[4] == ""  # price_sol
        assert compressed[5] == ""  # price_usd
        assert compressed[6] == ""  # value_usd
        assert compressed[7] == ""  # pnl_usd
    
    def test_size_reduction(self, compressor, sample_trade):
        """Test actual size reduction"""
        # Create 100 trades
        trades = [sample_trade.copy() for _ in range(100)]
        
        # Original format size
        original_json = json.dumps({"trades": trades})
        original_size = len(original_json)
        
        # Compressed format
        compressed_result = compressor.compress_trades(trades, "test_wallet")
        compressed_json = json.dumps(compressed_result)
        compressed_size = len(compressed_json)
        
        # Check size reduction
        compression_ratio = original_size / compressed_size
        assert compression_ratio > 3.5  # Should achieve at least 3.5x compression
        
        # Check it's under target size for 1000 trades
        size_per_trade = compressed_size / 100
        estimated_1k_size = size_per_trade * 1000
        assert estimated_1k_size < 200_000  # Under 200KB for 1000 trades
    
    def test_constants_section(self, compressor):
        """Test constants section is included"""
        result = compressor.compress_trades([], "test_wallet")
        
        assert "constants" in result
        assert result["constants"]["actions"] == ["sell", "buy"]
        assert result["constants"]["sol_mint"] == "So11111111111111111111111111111111111111112"
    
    def test_summary_counts(self, compressor):
        """Test summary counts are accurate"""
        trades = [
            {"timestamp": "2025-01-15T10:00:00", "action": "buy", "token": "A", "amount": 100},
            {"timestamp": "2025-01-15T11:00:00", "action": "sell", "token": "B", "amount": 200},
            {"timestamp": "invalid", "action": "buy", "token": "C", "amount": 300},  # Will fail
        ]
        
        result = compressor.compress_trades(trades, "test_wallet")
        
        assert result["summary"]["total"] == 3
        assert result["summary"]["included"] == 2  # One failed to compress
        assert len(result["trades"]) == 2
    
    def test_schema_version_parameter(self, compressor):
        """Test custom schema version"""
        result = compressor.compress_trades([], "test_wallet", schema_version="v0.7.2-test")
        assert result["schema_version"] == "v0.7.2-test"
    
    def test_token_symbol_fallback(self, compressor):
        """Test token symbol extraction from token_out"""
        trade = {
            "timestamp": "2025-01-15T10:00:00",
            "action": "buy",
            "amount": 1000,
            # No direct token field
            "token_out": {
                "symbol": "FALLBACK",
                "mint": "test_mint"
            }
        }
        
        result = compressor.compress_trades([trade], "test_wallet")
        compressed = result["trades"][0]
        
        assert compressed[2] == "FALLBACK"  # Used token_out.symbol 