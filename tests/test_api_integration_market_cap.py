#!/usr/bin/env python3
"""
Test WAL-510: Integration of market cap functionality with main analytics API
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import sys
import os
from decimal import Decimal

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.api.wallet_analytics_api_v3 import app
from src.lib.mc_calculator import MarketCapResult


class TestMarketCapIntegration:
    """Test market cap integration with main API"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def mock_trades(self):
        """Mock trade data"""
        return [
            {
                "timestamp": "2024-01-01T00:00:00",
                "signature": "sig1",
                "action": "buy",
                "token": "BONK",
                "amount": 1000000,
                "token_in": {
                    "mint": "So11111111111111111111111111111111111111112",
                    "symbol": "SOL",
                    "amount": 1.5
                },
                "token_out": {
                    "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                    "symbol": "BONK",
                    "amount": 1000000
                },
                "price": 0.00001,
                "value_usd": 10.0,
                "pnl_usd": 0,
                "fees_usd": 0.1,
                "priced": True,
                "dex": "Jupiter",
                "tx_type": "swap"
            }
        ]
    
    @pytest.fixture
    def mock_market_cap_result(self):
        """Mock market cap result"""
        return MarketCapResult(
            value=86131118728.8,
            confidence="high",
            source="helius_amm",
            supply=144372745251.0,
            price=0.596789,
            timestamp=1704067200  # 2024-01-01
        )
    
    @patch('src.api.wallet_analytics_api_v3.BlockchainFetcherV3')
    @patch('src.api.wallet_analytics_api_v3.calculate_market_cap')
    @patch('src.api.wallet_analytics_api_v3.get_precache_service')
    def test_v4_analyze_with_market_cap_enrichment(
        self, mock_get_service, mock_calculate_mc, mock_fetcher_class, client, mock_trades, mock_market_cap_result
    ):
        """Test /v4/analyze endpoint with market cap enrichment"""
        # Setup mocks
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_wallet_trades.return_value = {
            "wallet": "test_wallet",
            "trades": mock_trades,
            "fetch_metrics": {"total_trades": 1}
        }
        mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher
        
        # Mock market cap calculation
        async def mock_calc(*args, **kwargs):
            return mock_market_cap_result
        mock_calculate_mc.side_effect = mock_calc
        
        # Mock pre-cache service
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        
        # Make request with market cap enrichment
        response = client.post('/v4/analyze', json={
            "wallet": "test_wallet_address_12345678901234567890",
            "enrich_market_cap": True
        })
        
        assert response.status_code == 200
        data = response.json
        
        # Check response structure
        assert "trades" in data
        assert len(data["trades"]) == 1
        
        # Check market cap data was added
        trade = data["trades"][0]
        assert "token_in" in trade
        assert "market_cap" in trade["token_in"]
        assert trade["token_in"]["market_cap"]["market_cap"] == 86131118728.8
        assert trade["token_in"]["market_cap"]["confidence"] == "high"
        assert trade["token_in"]["market_cap"]["source"] == "helius_amm"
        
        # Check progress token header
        assert "X-Progress-Token" in response.headers
        
        # Verify pre-cache service tracking was called
        assert mock_service.track_request.called
    
    @patch('src.api.wallet_analytics_api_v3.BlockchainFetcherV3')
    def test_v4_analyze_without_market_cap_enrichment(self, mock_fetcher_class, client, mock_trades):
        """Test /v4/analyze endpoint without market cap enrichment"""
        # Setup mocks
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_wallet_trades.return_value = {
            "wallet": "test_wallet",
            "trades": mock_trades,
            "fetch_metrics": {"total_trades": 1}
        }
        mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher
        
        # Make request without market cap enrichment
        response = client.post('/v4/analyze', json={
            "wallet": "test_wallet_address_12345678901234567890",
            "enrich_market_cap": False
        })
        
        assert response.status_code == 200
        data = response.json
        
        # Check trades don't have market cap data
        trade = data["trades"][0]
        assert "market_cap" not in trade.get("token_in", {})
        assert "market_cap" not in trade.get("token_out", {})
    
    @patch('src.api.wallet_analytics_api_v3.calculate_market_cap')
    def test_single_market_cap_endpoint(self, mock_calculate_mc, client, mock_market_cap_result):
        """Test /v4/market-cap/{mint} endpoint"""
        # Mock market cap calculation
        async def mock_calc(*args, **kwargs):
            return mock_market_cap_result
        mock_calculate_mc.side_effect = mock_calc
        
        # Use asyncio to run the async endpoint
        with app.app_context():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def test():
                # Import the actual function
                from src.api.wallet_analytics_api_v3 import get_market_cap
                
                # Create mock request
                with app.test_request_context('/v4/market-cap/So11111111111111111111111111111111111111112'):
                    result = await get_market_cap("So11111111111111111111111111111111111111112")
                    return result
            
            response = loop.run_until_complete(test())
            data = response.json
            
            assert data["token_mint"] == "So11111111111111111111111111111111111111112"
            assert data["market_cap"] == 86131118728.8
            assert data["confidence"] == "high"
            assert data["source"] == "helius_amm"
    
    @patch('src.api.wallet_analytics_api_v3.calculate_market_cap')
    def test_batch_market_cap_endpoint(self, mock_calculate_mc, client, mock_market_cap_result):
        """Test /v4/market-cap/batch endpoint"""
        # Mock market cap calculation
        async def mock_calc(*args, **kwargs):
            return mock_market_cap_result
        mock_calculate_mc.side_effect = mock_calc
        
        # Use asyncio to run the async endpoint
        with app.app_context():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def test():
                # Import the actual function
                from src.api.wallet_analytics_api_v3 import get_batch_market_caps
                
                # Create mock request
                with app.test_request_context(
                    '/v4/market-cap/batch',
                    method='POST',
                    json={
                        "tokens": [
                            "So11111111111111111111111111111111111111112",
                            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                        ]
                    }
                ):
                    from flask import request
                    app.preprocess_request()
                    result = await get_batch_market_caps()
                    return result
            
            response = loop.run_until_complete(test())
            data = response.json
            
            assert "results" in data
            assert len(data["results"]) == 2
            
            # Check first result
            result = data["results"][0]
            assert result["token_mint"] == "So11111111111111111111111111111111111111112"
            assert result["market_cap"] == 86131118728.8
    
    @patch('src.api.wallet_analytics_api_v3.get_precache_service')
    def test_health_check_with_market_cap_stats(self, mock_get_service, client):
        """Test /health endpoint includes market cap service stats"""
        # Mock pre-cache service
        mock_service = Mock()
        mock_service.get_stats.return_value = {
            "tracked_tokens": 50,
            "popular_tokens": 11,
            "total_requests": 1000,
            "total_cache_hits": 900,
            "hit_rate": 90.0,
            "running": True
        }
        mock_get_service.return_value = mock_service
        
        response = client.get('/health')
        assert response.status_code == 200
        
        data = response.json
        assert "market_cap_service" in data
        assert data["market_cap_service"]["tracked_tokens"] == 50
        assert data["market_cap_service"]["hit_rate"] == 90.0
    
    def test_home_endpoint_shows_market_cap_features(self, client):
        """Test / endpoint shows market cap features"""
        response = client.get('/')
        assert response.status_code == 200
        
        data = response.json
        
        # Check endpoints
        endpoints = data["endpoints"]
        assert "/v4/market-cap/{mint}" in endpoints
        assert "/v4/market-cap/batch" in endpoints
        assert "enrich_market_cap" in endpoints["/v4/analyze"]
        
        # Check features
        features = data["features"]
        assert any("market cap" in f.lower() for f in features)
        assert any("pre-cache" in f.lower() for f in features)


if __name__ == "__main__":
    # Run specific test
    pytest.main([__file__, "-v", "-k", "test_v4_analyze_with_market_cap_enrichment"]) 