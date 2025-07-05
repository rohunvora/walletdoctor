"""
Unit tests for WalletSummaryAggregator
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import json

from src.lib.wallet_summary_aggregator import WalletSummaryAggregator


class TestWalletSummaryAggregator:
    """Test suite for WalletSummaryAggregator"""
    
    @pytest.fixture
    def aggregator(self):
        """Create aggregator instance"""
        return WalletSummaryAggregator()
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trade data"""
        now = int(datetime.now().timestamp())
        day_ago = now - 86400
        week_ago = now - 604800
        month_ago = now - 2592000
        
        return [
            # Recent winning trade
            {
                'timestamp': now - 3600,
                'action': 'sell',
                'token_symbol': 'BONK',
                'token_mint': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
                'amount': 1000000,
                'price_usd': '0.000015',
                'value_usd': '15.00',
                'pnl_usd': '5.00',
                'dex': 'METEORA'
            },
            # Recent losing trade
            {
                'timestamp': now - 7200,
                'action': 'sell',
                'token_symbol': 'WIF',
                'token_mint': 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm',
                'amount': 100,
                'price_usd': '2.50',
                'value_usd': '250.00',
                'pnl_usd': '-50.00',
                'dex': 'PUMP_AMM'
            },
            # Buy trades
            {
                'timestamp': week_ago,
                'action': 'buy',
                'token_symbol': 'BONK',
                'amount': 2000000,
                'price_usd': '0.000010',
                'value_usd': '20.00',
                'pnl_usd': '0',
                'dex': 'METEORA'
            },
            {
                'timestamp': month_ago,
                'action': 'buy',
                'token_symbol': 'WIF',
                'amount': 200,
                'price_usd': '3.00',
                'value_usd': '600.00',
                'pnl_usd': '0',
                'dex': 'PUMP_AMM'
            },
            # Large loss trade (ZEX example)
            {
                'timestamp': month_ago + 86400,
                'action': 'sell',
                'token_symbol': 'ZEX',
                'token_mint': 'ZEXy1pqteRu3n13kdyh4LwPQknkFk3GzmMYMuNadWPo',
                'amount': 50000,
                'price_usd': '0.10',
                'value_usd': '5000.00',
                'pnl_usd': '-15387.00',  # Major loss like in user's example
                'dex': 'ORCA'
            }
        ]
    
    def test_empty_trades(self, aggregator):
        """Test with empty trade list"""
        result = aggregator.aggregate_wallet_summary([])
        
        assert result['wallet_summary']['total_trades'] == 0
        assert result['pnl_analysis']['total_realized_pnl_usd'] == "0.00"
        assert result['win_rate']['overall_win_rate'] == "0.00"
        assert result['trade_volume']['total_volume_usd'] == "0.00"
        assert len(result['token_breakdown']) == 0
    
    def test_basic_aggregation(self, aggregator, sample_trades):
        """Test basic aggregation functionality"""
        result = aggregator.aggregate_wallet_summary(sample_trades)
        
        # Check wallet summary
        assert result['wallet_summary']['total_trades'] == 5
        assert result['wallet_summary']['unique_tokens'] == 3  # BONK, WIF, ZEX
        assert result['wallet_summary']['unique_dexes'] == 3  # METEORA, PUMP_AMM, ORCA
        
        # Check P&L analysis
        pnl = result['pnl_analysis']
        assert pnl['total_realized_pnl_usd'] == "-15432.00"  # 5 - 50 - 15387
        assert pnl['total_gains_usd'] == "5.00"
        assert pnl['total_losses_usd'] == "-15437.00"
        assert pnl['largest_win_usd'] == "5.00"
        assert pnl['largest_loss_usd'] == "-15387.00"
        assert pnl['sell_trades_count'] == 3
        
        # Check win rate
        win_rate = result['win_rate']
        assert win_rate['winning_trades'] == 1
        assert win_rate['losing_trades'] == 2
        assert win_rate['overall_win_rate'] == "33.33"
        
        # Check volume stats
        volume = result['trade_volume']
        assert volume['total_volume_usd'] == "5885.00"
        assert volume['buy_count'] == 2
        assert volume['sell_count'] == 3
    
    def test_token_breakdown_sorting(self, aggregator, sample_trades):
        """Test that tokens are sorted by absolute P&L"""
        result = aggregator.aggregate_wallet_summary(sample_trades)
        
        tokens = result['token_breakdown']
        assert len(tokens) == 3
        
        # ZEX should be first (largest absolute P&L)
        assert tokens[0]['symbol'] == 'ZEX'
        assert tokens[0]['realized_pnl_usd'] == "-15387.00"
        
        # WIF should be second
        assert tokens[1]['symbol'] == 'WIF'
        assert tokens[1]['realized_pnl_usd'] == "-50.00"
        
        # BONK should be third
        assert tokens[2]['symbol'] == 'BONK'
        assert tokens[2]['realized_pnl_usd'] == "5.00"
    
    def test_window_calculations(self, aggregator, sample_trades):
        """Test recent window calculations"""
        result = aggregator.aggregate_wallet_summary(sample_trades, include_windows=True)
        
        windows = result['recent_windows']
        
        # 7-day window should include only recent trades
        assert windows['last_7_days']['trades'] == 2  # Only the two recent trades
        assert windows['last_7_days']['pnl_usd'] == "-45.00"  # 5 - 50
        
        # 30-day window should include more trades
        assert windows['last_30_days']['trades'] >= 3
    
    def test_size_trimming(self, aggregator):
        """Test that large payloads are trimmed"""
        # Create many trades with different tokens
        large_trades = []
        for i in range(100):
            large_trades.append({
                'timestamp': int(datetime.now().timestamp()) - i * 3600,
                'action': 'sell' if i % 2 else 'buy',
                'token_symbol': f'TOKEN{i}',
                'token_mint': f'mint{i}',
                'amount': 1000,
                'price_usd': '1.00',
                'value_usd': '1000.00',
                'pnl_usd': '10.00' if i % 2 else '0',
                'dex': 'TEST_DEX'
            })
        
        result = aggregator.aggregate_wallet_summary(large_trades, max_tokens=10)
        
        # Check that token breakdown is limited
        assert len(result['token_breakdown']) <= 10
        
        # Check size is under limit
        serialized = json.dumps(result)
        size_bytes = len(serialized.encode('utf-8'))
        assert size_bytes < 25 * 1024  # Under 25KB
        
        # Check meta indicates size
        assert 'meta' in result
        assert 'payload_size_bytes' in result['meta']
    
    def test_trading_patterns(self, aggregator, sample_trades):
        """Test trading pattern calculations"""
        # Add more trades at specific hours
        trades = sample_trades.copy()
        now = int(datetime.now().timestamp())
        
        # Add trades at hour 14 UTC
        for i in range(5):
            trades.append({
                'timestamp': now - i * 86400,  # Same hour, different days
                'action': 'buy',
                'token_symbol': 'TEST',
                'amount': 100,
                'price_usd': '1.00',
                'value_usd': '100.00',
                'pnl_usd': '0',
                'dex': 'METEORA'
            })
        
        result = aggregator.aggregate_wallet_summary(trades)
        patterns = result['trading_patterns']
        
        assert patterns['favorite_dex'] == 'METEORA'  # Most used DEX
        assert 'most_active_hour_utc' in patterns
        assert 'avg_trades_per_day' in patterns
    
    def test_profit_factor_calculation(self, aggregator):
        """Test profit factor edge cases"""
        # Only winning trades
        winning_trades = [{
            'timestamp': int(datetime.now().timestamp()),
            'action': 'sell',
            'token_symbol': 'WIN',
            'amount': 100,
            'price_usd': '1.00',
            'value_usd': '100.00',
            'pnl_usd': '50.00',
            'dex': 'TEST'
        }]
        
        result = aggregator.aggregate_wallet_summary(winning_trades)
        assert result['pnl_analysis']['profit_factor'] == "inf"  # No losses
        
        # Balanced trades
        balanced_trades = [
            {
                'timestamp': int(datetime.now().timestamp()),
                'action': 'sell',
                'token_symbol': 'TEST',
                'amount': 100,
                'price_usd': '1.00', 
                'value_usd': '100.00',
                'pnl_usd': '100.00',
                'dex': 'TEST'
            },
            {
                'timestamp': int(datetime.now().timestamp()) - 1,
                'action': 'sell',
                'token_symbol': 'TEST',
                'amount': 100,
                'price_usd': '1.00',
                'value_usd': '100.00',
                'pnl_usd': '-50.00',
                'dex': 'TEST'
            }
        ]
        
        result = aggregator.aggregate_wallet_summary(balanced_trades)
        assert result['pnl_analysis']['profit_factor'] == "2.00"  # 100/50
    
    def test_schema_completeness(self, aggregator, sample_trades):
        """Test that all expected fields are present"""
        result = aggregator.aggregate_wallet_summary(sample_trades)
        
        # Check top-level keys
        expected_keys = [
            'wallet_summary',
            'pnl_analysis', 
            'win_rate',
            'trade_volume',
            'token_breakdown',
            'recent_windows',
            'trading_patterns',
            'meta'
        ]
        
        for key in expected_keys:
            assert key in result
        
        # Check token breakdown fields
        if result['token_breakdown']:
            token = result['token_breakdown'][0]
            token_keys = [
                'symbol', 'trades', 'realized_pnl_usd',
                'win_rate', 'volume_usd', 'buy_count',
                'sell_count', 'avg_buy_price_usd', 'avg_sell_price_usd'
            ]
            for key in token_keys:
                assert key in token 