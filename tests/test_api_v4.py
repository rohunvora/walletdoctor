"""
Test V4 API Endpoints
WAL-606: Tests for enhanced API with position tracking
"""

import pytest
import json
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List

# Import the app
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.api.wallet_analytics_api_v4 import app, calculate_positions, calculate_unrealized_pnl
from src.lib.position_models import Position, PositionPnL, PositionSnapshot, PriceConfidence


# Test wallet and data
TEST_WALLET = "TestWallet123456789012345678901234567890"
BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoHHuJjWKjH8vJFKfPQoKEWF"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_MINT = "So11111111111111111111111111111111111111112"


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_trades():
    """Mock trade data"""
    return [
        {
            "signature": "sig1",
            "slot": 1000,
            "timestamp": "2024-01-01T00:00:00Z",
            "action": "buy",
            "token": "BONK",
            "amount": 1000000,
            "token_in": {
                "mint": SOL_MINT,
                "symbol": "SOL",
                "amount": 1.0
            },
            "token_out": {
                "mint": BONK_MINT,
                "symbol": "BONK",
                "amount": 1000000
            },
            "price": 0.00001,
            "value_usd": 10.0,
            "pnl_usd": 0,
            "priced": True
        },
        {
            "signature": "sig2",
            "slot": 2000,
            "timestamp": "2024-01-02T00:00:00Z",
            "action": "sell",
            "token": "BONK",
            "amount": 500000,
            "token_in": {
                "mint": BONK_MINT,
                "symbol": "BONK",
                "amount": 500000
            },
            "token_out": {
                "mint": SOL_MINT,
                "symbol": "SOL",
                "amount": 0.75
            },
            "price": 0.000015,
            "value_usd": 7.5,
            "pnl_usd": 2.5,
            "priced": True
        }
    ]


@pytest.fixture
def mock_positions():
    """Mock position data"""
    return [
        Position(
            position_id=f"{TEST_WALLET}:{BONK_MINT}:123456",
            wallet=TEST_WALLET,
            token_mint=BONK_MINT,
            token_symbol="BONK",
            balance=Decimal("500000"),
            cost_basis=Decimal("0.00001"),
            cost_basis_usd=Decimal("5.0"),
            opened_at=datetime.now(timezone.utc),
            last_trade_at=datetime.now(timezone.utc),
            trade_count=2,
            decimals=5
        )
    ]


class TestV4AnalyzeEndpoint:
    """Test /v4/analyze endpoint"""
    
    @patch('src.api.wallet_analytics_api_v4.BlockchainFetcherV3')
    @patch('src.api.wallet_analytics_api_v4.positions_enabled')
    def test_analyze_without_positions(self, mock_positions_enabled, mock_fetcher_class, client, mock_trades):
        """Test analyze endpoint with positions disabled"""
        # Setup mocks
        mock_positions_enabled.return_value = False
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_wallet_trades = AsyncMock(return_value={
            "trades": mock_trades,
            "summary": {"total_trades": 2}
        })
        mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher
        
        # Make request
        response = client.post('/v4/analyze', 
            json={"wallet": TEST_WALLET},
            content_type='application/json'
        )
        
        # Verify response
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "trades" in data
        assert len(data["trades"]) == 2
        assert "positions" not in data  # No positions when disabled
        assert "X-Progress-Token" in response.headers
        
        # Verify totals
        assert "totals" in data
        assert data["totals"]["total_trades"] == 2
        assert data["totals"]["realized_pnl_usd"] == 2.5
    
    @patch('src.api.wallet_analytics_api_v4.BlockchainFetcherV3')
    @patch('src.api.wallet_analytics_api_v4.positions_enabled')
    @patch('src.api.wallet_analytics_api_v4.should_calculate_unrealized_pnl')
    @patch('src.api.wallet_analytics_api_v4.get_position_cache')
    @patch('src.api.wallet_analytics_api_v4.PositionBuilder')
    @patch('src.api.wallet_analytics_api_v4.UnrealizedPnLCalculator')
    def test_analyze_with_positions(self, mock_pnl_calc_class, mock_builder_class, 
                                   mock_cache_func, mock_unrealized_enabled,
                                   mock_positions_enabled, mock_fetcher_class, 
                                   client, mock_trades, mock_positions):
        """Test analyze endpoint with positions enabled"""
        # Setup mocks
        mock_positions_enabled.return_value = True
        mock_unrealized_enabled.return_value = True
        
        # Mock fetcher
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_wallet_trades = AsyncMock(return_value={
            "trades": mock_trades,
            "summary": {"total_trades": 2}
        })
        mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher
        
        # Mock cache (no cached data)
        mock_cache = AsyncMock()
        mock_cache.get_portfolio_snapshot = AsyncMock(return_value=None)
        mock_cache.set_portfolio_snapshot = AsyncMock()
        mock_cache.invalidate_wallet_positions = AsyncMock()
        mock_cache_func.return_value = mock_cache
        
        # Mock position builder
        mock_builder = Mock()
        mock_builder.build_positions_from_trades = Mock(return_value=mock_positions)
        mock_builder_class.return_value = mock_builder
        
        # Mock P&L calculator
        mock_pnl_calc = AsyncMock()
        position_pnl = PositionPnL(
            position=mock_positions[0],
            current_price_usd=Decimal("0.00002"),
            current_value_usd=Decimal("10.0"),
            unrealized_pnl_usd=Decimal("5.0"),
            unrealized_pnl_pct=Decimal("100"),
            price_confidence=PriceConfidence.HIGH,
            last_price_update=datetime.now(timezone.utc)
        )
        mock_pnl_calc.create_position_pnl_list = AsyncMock(return_value=[position_pnl])
        mock_pnl_calc_class.return_value = mock_pnl_calc
        
        # Make request
        response = client.post('/v4/analyze', 
            json={"wallet": TEST_WALLET, "include_positions": True},
            content_type='application/json'
        )
        
        # Verify response
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check positions were calculated
        assert "positions" in data
        assert len(data["positions"]) == 1
        assert data["positions"][0]["token_symbol"] == "BONK"
        assert data["positions"][0]["unrealized_pnl_usd"] == "5.0"
        
        # Check position summary
        assert "position_summary" in data
        assert data["position_summary"]["total_positions"] == 1
        assert data["position_summary"]["total_unrealized_pnl_usd"] == "5.0"
        
        # Check combined totals
        assert "totals" in data
        assert data["totals"]["realized_pnl_usd"] == 2.5
        assert data["totals"]["unrealized_pnl_usd"] == 5.0
        assert data["totals"]["total_pnl_usd"] == 7.5
    
    def test_analyze_missing_wallet(self, client):
        """Test analyze with missing wallet address"""
        response = client.post('/v4/analyze', 
            json={},
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "Missing wallet address" in data["error"]
    
    def test_analyze_invalid_wallet(self, client):
        """Test analyze with invalid wallet address"""
        response = client.post('/v4/analyze', 
            json={"wallet": "short"},
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "Invalid wallet address" in data["error"]


class TestPositionsEndpoint:
    """Test /v4/positions/{wallet} endpoint"""
    
    @patch('src.api.wallet_analytics_api_v4.positions_enabled')
    def test_positions_disabled(self, mock_enabled, client):
        """Test positions endpoint when feature is disabled"""
        mock_enabled.return_value = False
        
        response = client.get(f'/v4/positions/{TEST_WALLET}')
        
        assert response.status_code == 501
        data = json.loads(response.data)
        assert "error" in data
        assert "not enabled" in data["error"]
    
    @patch('src.api.wallet_analytics_api_v4.positions_enabled')
    @patch('src.api.wallet_analytics_api_v4.should_calculate_unrealized_pnl')
    @patch('src.api.wallet_analytics_api_v4.get_position_cache')
    def test_positions_from_cache(self, mock_cache_func, mock_unrealized_enabled,
                                 mock_enabled, client, mock_positions):
        """Test getting positions from cache"""
        mock_enabled.return_value = True
        mock_unrealized_enabled.return_value = True
        
        # Create cached snapshot
        position_pnl = PositionPnL(
            position=mock_positions[0],
            current_price_usd=Decimal("0.00002"),
            current_value_usd=Decimal("10.0"),
            unrealized_pnl_usd=Decimal("5.0"),
            unrealized_pnl_pct=Decimal("100"),
            price_confidence=PriceConfidence.HIGH,
            last_price_update=datetime.now(timezone.utc)
        )
        cached_snapshot = PositionSnapshot.from_positions(TEST_WALLET, [position_pnl])
        
        # Mock cache
        mock_cache = AsyncMock()
        mock_cache.get_portfolio_snapshot = AsyncMock(return_value=cached_snapshot)
        mock_cache_func.return_value = mock_cache
        
        # Make request
        response = client.get(f'/v4/positions/{TEST_WALLET}')
        
        # Verify response
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["wallet"] == TEST_WALLET
        assert data["cached"] is True
        assert len(data["positions"]) == 1
        assert "summary" in data
    
    @patch('src.api.wallet_analytics_api_v4.positions_enabled')
    @patch('src.api.wallet_analytics_api_v4.should_calculate_unrealized_pnl')
    @patch('src.api.wallet_analytics_api_v4.get_position_cache')
    @patch('src.api.wallet_analytics_api_v4.BlockchainFetcherV3')
    @patch('src.api.wallet_analytics_api_v4.PositionBuilder')
    @patch('src.api.wallet_analytics_api_v4.UnrealizedPnLCalculator')
    def test_positions_fresh_fetch(self, mock_pnl_calc_class, mock_builder_class,
                                  mock_fetcher_class, mock_cache_func, 
                                  mock_unrealized_enabled, mock_enabled,
                                  client, mock_trades, mock_positions):
        """Test fetching fresh positions"""
        mock_enabled.return_value = True
        mock_unrealized_enabled.return_value = True
        
        # Mock cache (no cached data)
        mock_cache = AsyncMock()
        mock_cache.get_portfolio_snapshot = AsyncMock(return_value=None)
        mock_cache.set_portfolio_snapshot = AsyncMock()
        mock_cache.invalidate_wallet_positions = AsyncMock()
        mock_cache_func.return_value = mock_cache
        
        # Mock fetcher
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_wallet_trades = AsyncMock(return_value={
            "trades": mock_trades
        })
        mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher
        
        # Mock position builder
        mock_builder = Mock()
        mock_builder.build_positions_from_trades = Mock(return_value=mock_positions)
        mock_builder_class.return_value = mock_builder
        
        # Mock P&L calculator
        position_pnl = PositionPnL(
            position=mock_positions[0],
            current_price_usd=Decimal("0.00002"),
            current_value_usd=Decimal("10.0"),
            unrealized_pnl_usd=Decimal("5.0"),
            unrealized_pnl_pct=Decimal("100"),
            price_confidence=PriceConfidence.HIGH,
            last_price_update=datetime.now(timezone.utc)
        )
        mock_pnl_calc = AsyncMock()
        mock_pnl_calc.create_position_pnl_list = AsyncMock(return_value=[position_pnl])
        mock_pnl_calc_class.return_value = mock_pnl_calc
        
        # Make request with refresh
        response = client.get(f'/v4/positions/{TEST_WALLET}?refresh=true')
        
        # Verify response
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["wallet"] == TEST_WALLET
        assert data["cached"] is False
        assert len(data["positions"]) == 1
        
        # Verify cache was updated
        mock_cache.set_portfolio_snapshot.assert_called_once()
        mock_cache.invalidate_wallet_positions.assert_called_once_with(TEST_WALLET)
    
    @patch('src.api.wallet_analytics_api_v4.positions_enabled')
    def test_positions_invalid_wallet(self, mock_enabled, client):
        """Test positions with invalid wallet"""
        mock_enabled.return_value = True  # Enable positions to test validation
        response = client.get('/v4/positions/short')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data


class TestProgressEndpoint:
    """Test /v4/progress/{token} endpoint"""
    
    @patch('src.api.wallet_analytics_api_v4.get_progress_tracker')
    def test_progress_found(self, mock_tracker_func, client):
        """Test getting progress for valid token"""
        # Mock progress data
        progress_data = {
            "token": "test-token-123",
            "status": "calculating_positions",
            "pages": 45,
            "total": 72,
            "trades": 3500,
            "age_seconds": 15
        }
        
        mock_tracker = Mock()
        mock_tracker.get_progress = Mock(return_value=progress_data)
        mock_tracker_func.return_value = mock_tracker
        
        response = client.get('/v4/progress/test-token-123')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "calculating_positions"
        assert data["trades"] == 3500
    
    @patch('src.api.wallet_analytics_api_v4.get_progress_tracker')
    def test_progress_not_found(self, mock_tracker_func, client):
        """Test getting progress for invalid token"""
        mock_tracker = Mock()
        mock_tracker.get_progress = Mock(return_value=None)
        mock_tracker_func.return_value = mock_tracker
        
        response = client.get('/v4/progress/invalid-token')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data


class TestHealthEndpoint:
    """Test /health endpoint"""
    
    @patch('src.api.wallet_analytics_api_v4.positions_enabled')
    @patch('src.api.wallet_analytics_api_v4.should_calculate_unrealized_pnl')
    @patch('src.api.wallet_analytics_api_v4.get_cost_basis_method')
    @patch('src.api.wallet_analytics_api_v4.get_position_cache')
    def test_health_check(self, mock_cache_func, mock_method, mock_pnl, mock_positions, client):
        """Test health check endpoint"""
        mock_positions.return_value = True
        mock_pnl.return_value = True
        mock_method.return_value = "fifo"
        
        # Mock cache stats
        mock_cache = Mock()
        mock_cache.get_stats = Mock(return_value={
            "cache_hits": 100,
            "cache_misses": 20,
            "hit_rate": 83.3
        })
        mock_cache_func.return_value = mock_cache
        
        response = client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert data["version"] == "4.0"
        assert data["features"]["positions_enabled"] is True
        assert data["features"]["unrealized_pnl_enabled"] is True
        assert data["features"]["cost_basis_method"] == "fifo"
        assert "cache_stats" in data


class TestUtilityFunctions:
    """Test utility functions"""
    
    @pytest.mark.asyncio
    async def test_calculate_positions(self, mock_trades):
        """Test calculate_positions function"""
        with patch('src.api.wallet_analytics_api_v4.PositionBuilder') as mock_builder_class:
            mock_builder = Mock()
            mock_positions = [Mock(spec=Position)]
            mock_builder.build_positions_from_trades = Mock(return_value=mock_positions)
            mock_builder_class.return_value = mock_builder
            
            positions = await calculate_positions(TEST_WALLET, mock_trades)
            
            assert positions == mock_positions
            mock_builder.build_positions_from_trades.assert_called_once_with(
                mock_trades, TEST_WALLET
            )
    
    @pytest.mark.asyncio
    async def test_calculate_unrealized_pnl(self, mock_positions):
        """Test calculate_unrealized_pnl function"""
        with patch('src.api.wallet_analytics_api_v4.UnrealizedPnLCalculator') as mock_calc_class:
            mock_calc = AsyncMock()
            mock_pnls = [Mock(spec=PositionPnL)]
            mock_calc.create_position_pnl_list = AsyncMock(return_value=mock_pnls)
            mock_calc_class.return_value = mock_calc
            
            pnls = await calculate_unrealized_pnl(mock_positions)
            
            assert pnls == mock_pnls
            mock_calc.create_position_pnl_list.assert_called_once_with(mock_positions)


class TestHomeEndpoint:
    """Test home endpoint"""
    
    @patch('src.api.wallet_analytics_api_v4.positions_enabled')
    @patch('src.api.wallet_analytics_api_v4.should_calculate_unrealized_pnl')
    @patch('src.api.wallet_analytics_api_v4.get_cost_basis_method')
    def test_home_info(self, mock_method, mock_pnl, mock_positions, client):
        """Test home endpoint returns API info"""
        mock_positions.return_value = True
        mock_pnl.return_value = False
        mock_method.return_value = "weighted_avg"
        
        response = client.get('/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["service"] == "WalletDoctor API V4"
        assert data["version"] == "4.0"
        assert "/v4/analyze" in data["endpoints"]
        assert "/v4/positions/{wallet}" in data["endpoints"]
        assert data["position_features"]["enabled"] is True
        assert data["position_features"]["unrealized_pnl"] is False
        assert data["position_features"]["cost_basis_method"] == "weighted_avg"


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 