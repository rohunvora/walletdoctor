#!/usr/bin/env python3
"""
Tests for GPT Export API Endpoint (WAL-611)
"""

import pytest
import json
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.api.wallet_analytics_api_v4_gpt import app, format_gpt_schema_v1_1
from src.lib.position_models import (
    Position, PositionPnL, PositionSnapshot, 
    CostBasisMethod, PriceConfidence
)


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def valid_api_key():
    """Valid API key for testing"""
    return "wd_" + "a" * 32  # 35 chars total


@pytest.fixture
def sample_position():
    """Create sample position for testing"""
    return Position(
        position_id="3JoVBi:DezXAZ:1706438400",
        wallet="3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
        token_mint="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        token_symbol="BONK",
        balance=Decimal("1000000.123456"),
        decimals=5,
        cost_basis=Decimal("0.0000255"),
        cost_basis_usd=Decimal("25.50"),
        cost_basis_method=CostBasisMethod.FIFO,
        opened_at=datetime(2024, 1, 27, 15, 30, tzinfo=timezone.utc),
        last_trade_at=datetime(2024, 1, 28, 9, 15, tzinfo=timezone.utc),
        last_update_slot=250000000,
        last_update_time=datetime.now(timezone.utc),
        is_closed=False,
        trade_count=2
    )


@pytest.fixture
def sample_position_pnl(sample_position):
    """Create sample PositionPnL"""
    return PositionPnL(
        position=sample_position,
        current_price_usd=Decimal("0.0000315"),
        current_value_usd=Decimal("31.50"),
        unrealized_pnl_usd=Decimal("6.00"),
        unrealized_pnl_pct=Decimal("23.53"),
        price_confidence=PriceConfidence.HIGH,
        last_price_update=datetime.now(timezone.utc),
        price_source="market_cap_service",
        price_age_seconds=45
    )


@pytest.fixture
def sample_snapshot(sample_position_pnl):
    """Create sample portfolio snapshot"""
    return PositionSnapshot(
        wallet="3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
        positions=[sample_position_pnl],
        total_value_usd=Decimal("31.50"),
        total_unrealized_pnl_usd=Decimal("6.00"),
        total_unrealized_pnl_pct=Decimal("23.53")
    )


class TestGPTExportAPI:
    """Test GPT export endpoint"""
    
    def test_no_auth(self, client):
        """Test endpoint requires authentication"""
        response = client.get("/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert "error" in data
        assert "API key required" in data["error"]
    
    def test_invalid_api_key_format(self, client):
        """Test invalid API key format rejection"""
        # Too short
        response = client.get(
            "/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
            headers={"X-Api-Key": "wd_short"}
        )
        assert response.status_code == 401
        
        # Wrong prefix
        response = client.get(
            "/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
            headers={"X-Api-Key": "wrong_" + "a" * 29}
        )
        assert response.status_code == 401
    
    def test_invalid_wallet_address(self, client, valid_api_key):
        """Test invalid wallet address handling"""
        response = client.get(
            "/v4/positions/export-gpt/invalid",
            headers={"X-Api-Key": valid_api_key}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Invalid wallet address" in data["error"]
    
    def test_unsupported_schema_version(self, client, valid_api_key):
        """Test unsupported schema version"""
        response = client.get(
            "/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2?schema_version=2.0",
            headers={"X-Api-Key": valid_api_key}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Unsupported schema version" in data["error"]
    
    @patch('src.api.wallet_analytics_api_v4_gpt.get_position_cache_v2')
    @patch('src.api.wallet_analytics_api_v4_gpt.positions_enabled', return_value=True)
    def test_valid_wallet_fresh_data(self, mock_positions_enabled, mock_get_cache, client, valid_api_key, sample_snapshot):
        """Test valid wallet with fresh cached data"""
        # Mock cache to return fresh data
        mock_cache = AsyncMock()
        mock_cache.get_portfolio_snapshot.return_value = (sample_snapshot, False)  # Not stale
        mock_get_cache.return_value = mock_cache
        
        response = client.get(
            "/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
            headers={"X-Api-Key": valid_api_key}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check schema version
        assert data["schema_version"] == "1.1"
        assert data["wallet"] == "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
        
        # Check positions
        assert len(data["positions"]) == 1
        position = data["positions"][0]
        assert position["token_symbol"] == "BONK"
        assert position["balance"] == "1000000.123456"
        assert position["decimals"] == 5
        assert position["unrealized_pnl_usd"] == "6.00"
        assert position["price_confidence"] == "high"
        
        # Check summary
        assert data["summary"]["total_positions"] == 1
        assert data["summary"]["total_unrealized_pnl_usd"] == "6.00"
        
        # Check price sources
        assert "price_sources" in data
        assert "primary" in data["price_sources"]
        
        # Should not have staleness flags
        assert "stale" not in data
        assert "age_seconds" not in data
        
        # Check performance header
        assert "X-Response-Time-Ms" in response.headers
        assert "X-Cache-Status" in response.headers
        assert response.headers["X-Cache-Status"] == "MISS"  # Fresh data
    
    @patch('src.api.wallet_analytics_api_v4_gpt.get_position_cache_v2')
    @patch('src.api.wallet_analytics_api_v4_gpt.positions_enabled', return_value=True)
    def test_valid_wallet_stale_data(self, mock_positions_enabled, mock_get_cache, client, valid_api_key, sample_snapshot):
        """Test valid wallet with stale cached data"""
        # Make snapshot older
        sample_snapshot.timestamp = datetime.now(timezone.utc) - timedelta(minutes=20)
        
        # Mock cache to return stale data
        mock_cache = AsyncMock()
        mock_cache.get_portfolio_snapshot.return_value = (sample_snapshot, True)  # Stale
        mock_get_cache.return_value = mock_cache
        
        response = client.get(
            "/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
            headers={"X-Api-Key": valid_api_key}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should have staleness flags
        assert data["stale"] == True
        assert data["age_seconds"] > 0
        assert data["age_seconds"] >= 1200  # At least 20 minutes
        
        # Check cache hit header
        assert response.headers["X-Cache-Status"] == "HIT"
    
    @patch('src.api.wallet_analytics_api_v4_gpt.get_position_cache_v2')
    @patch('src.api.wallet_analytics_api_v4_gpt.positions_enabled', return_value=True)
    def test_wallet_not_found(self, mock_positions_enabled, mock_get_cache, client, valid_api_key):
        """Test wallet with no data"""
        # Mock cache to return None
        mock_cache = AsyncMock()
        mock_cache.get_portfolio_snapshot.return_value = None
        mock_get_cache.return_value = mock_cache
        
        # Mock fetcher to return no trades
        with patch('src.api.wallet_analytics_api_v4_gpt.BlockchainFetcherV3Fast') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher.fetch_wallet_trades.return_value = {"trades": []}
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher
            
            response = client.get(
                "/v4/positions/export-gpt/unknown_wallet_address_with_no_trades",
                headers={"X-Api-Key": valid_api_key}
            )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "Wallet not found" in data["error"]
    
    @patch('src.api.wallet_analytics_api_v4_gpt.positions_enabled', return_value=False)
    def test_positions_disabled(self, mock_positions_enabled, client, valid_api_key):
        """Test when positions feature is disabled"""
        response = client.get(
            "/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
            headers={"X-Api-Key": valid_api_key}
        )
        
        assert response.status_code == 501
        data = json.loads(response.data)
        assert "Feature disabled" in data["error"]
    
    def test_schema_formatting(self, sample_position):
        """Test GPT schema v1.1 formatting"""
        # Test with high confidence price
        position_pnl_high = PositionPnL(
            position=sample_position,
            current_price_usd=Decimal("0.0000315"),
            current_value_usd=Decimal("31.50"),
            unrealized_pnl_usd=Decimal("6.00"),
            unrealized_pnl_pct=Decimal("23.53"),
            price_confidence=PriceConfidence.HIGH,
            last_price_update=datetime.now(timezone.utc),
            price_source="market_cap_service",
            price_age_seconds=45
        )
        snapshot = PositionSnapshot(
            wallet="3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
            positions=[position_pnl_high],
            total_value_usd=Decimal("31.50"),
            total_unrealized_pnl_usd=Decimal("6.00"),
            total_unrealized_pnl_pct=Decimal("23.53")
        )
        
        result = format_gpt_schema_v1_1(snapshot, base_url="https://walletdoctor.app")
        
        assert result["schema_version"] == "1.1"
        assert result["wallet"] == snapshot.wallet
        assert len(result["positions"]) == 1
        
        position = result["positions"][0]
        assert position["price_confidence"] == "high"
        assert result["summary"]["stale_price_count"] == 0
        
        # Verify price sources
        assert result["price_sources"]["primary"] == "https://walletdoctor.app/v4/prices"
        
        # Test with stale price
        position_pnl_stale = PositionPnL(
            position=sample_position,
            current_price_usd=Decimal("0.0000315"),
            current_value_usd=Decimal("31.50"),
            unrealized_pnl_usd=Decimal("6.00"),
            unrealized_pnl_pct=Decimal("23.53"),
            price_confidence=PriceConfidence.UNAVAILABLE,
            last_price_update=datetime.now(timezone.utc),
            price_source="market_cap_service",
            price_age_seconds=45
        )
        snapshot_stale = PositionSnapshot(
            wallet="3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
            positions=[position_pnl_stale],
            total_value_usd=Decimal("31.50"),
            total_unrealized_pnl_usd=Decimal("6.00"),
            total_unrealized_pnl_pct=Decimal("23.53")
        )
        result = format_gpt_schema_v1_1(snapshot_stale, base_url="https://walletdoctor.app")
        assert result["positions"][0]["price_confidence"] == "stale"
        assert result["summary"]["stale_price_count"] == 1
        
        # Test with estimated price
        position_pnl_est = PositionPnL(
            position=sample_position,
            current_price_usd=Decimal("0.0000315"),
            current_value_usd=Decimal("31.50"),
            unrealized_pnl_usd=Decimal("6.00"),
            unrealized_pnl_pct=Decimal("23.53"),
            price_confidence=PriceConfidence.ESTIMATED,
            last_price_update=datetime.now(timezone.utc),
            price_source="market_cap_service",
            price_age_seconds=45
        )
        snapshot_est = PositionSnapshot(
            wallet="3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
            positions=[position_pnl_est],
            total_value_usd=Decimal("31.50"),
            total_unrealized_pnl_usd=Decimal("6.00"),
            total_unrealized_pnl_pct=Decimal("23.53")
        )
        result = format_gpt_schema_v1_1(snapshot_est, base_url="https://walletdoctor.app")
        assert result["positions"][0]["price_confidence"] == "est"
        assert result["summary"]["stale_price_count"] == 0  # est is not counted as stale
    
    @patch('src.api.wallet_analytics_api_v4_gpt.positions_enabled', return_value=True)
    def test_performance_requirements(self, mock_positions_enabled, client, valid_api_key):
        """Test performance headers are included"""
        with patch('src.api.wallet_analytics_api_v4_gpt.get_position_cache_v2') as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get_portfolio_snapshot.return_value = None
            mock_get_cache.return_value = mock_cache
            
            with patch('src.api.wallet_analytics_api_v4_gpt.BlockchainFetcherV3Fast') as mock_fetcher_class:
                mock_fetcher = AsyncMock()
                mock_fetcher.fetch_wallet_trades.return_value = {"trades": []}
                mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher
                
                response = client.get(
                    "/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
                    headers={"X-Api-Key": valid_api_key}
                )
        
        # Should get 404 for wallet not found
        assert response.status_code == 404
        
        # Check performance header exists even on error
        assert "X-Response-Time-Ms" in response.headers
        response_time = float(response.headers["X-Response-Time-Ms"])
        
        # Should be fast for this simple test
        assert response_time < 1500  # Under 1.5s requirement
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert data["service"] == "WalletDoctor GPT Export API"
        assert data["version"] == "1.1"
    
    def test_home_endpoint(self, client):
        """Test home endpoint provides API info"""
        response = client.get("/")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["service"] == "WalletDoctor GPT Export API"
        assert "/v4/positions/export-gpt/{wallet}" in data["endpoints"]
        assert data["authentication"]["required"] == True
        assert data["authentication"]["header"] == "X-Api-Key"
        assert "1.1" in data["schema_versions"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 