#!/usr/bin/env python3
"""
Test Market Cap API endpoints
"""

import pytest
import asyncio
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.api.market_cap_api import app, decimal_to_float
from src.lib.mc_calculator import MarketCapResult, CONFIDENCE_HIGH, CONFIDENCE_EST


class TestMarketCapAPI:
    """Test Market Cap API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        return app.test_client()
    
    @pytest.fixture
    def mock_market_cap_result(self):
        """Create mock MarketCapResult"""
        return MarketCapResult(
            value=1000000.0,
            confidence=CONFIDENCE_HIGH,
            source="helius_raydium",
            supply=1000000.0,
            price=1.0,
            timestamp=1234567890
        )
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get('/health')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['service'] == 'market_cap_api'
        assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_get_market_cap(self, client, mock_market_cap_result):
        """Test single token market cap endpoint"""
        token_mint = "So11111111111111111111111111111111111111112"
        
        with patch('src.api.market_cap_api.calculate_market_cap', 
                  AsyncMock(return_value=mock_market_cap_result)):
            with patch('src.api.market_cap_api.get_precache_service', return_value=None):
                response = client.get(f'/v1/market-cap/{token_mint}')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert data['token_mint'] == token_mint
                assert data['market_cap'] == 1000000.0
                assert data['confidence'] == CONFIDENCE_HIGH
                assert data['source'] == "helius_raydium"
                assert data['supply'] == 1000000.0
                assert data['price'] == 1.0
                assert data['timestamp'] == 1234567890
                assert data['cached'] is False
    
    @pytest.mark.asyncio
    async def test_get_market_cap_with_params(self, client, mock_market_cap_result):
        """Test market cap endpoint with query parameters"""
        token_mint = "So11111111111111111111111111111111111111112"
        
        with patch('src.api.market_cap_api.calculate_market_cap', 
                  AsyncMock(return_value=mock_market_cap_result)) as mock_calc:
            with patch('src.api.market_cap_api.get_precache_service', return_value=None):
                response = client.get(
                    f'/v1/market-cap/{token_mint}?slot=12345&timestamp=9876543210&use_cache=false'
                )
                assert response.status_code == 200
                
                # Verify parameters were passed correctly
                mock_calc.assert_called_once_with(
                    token_mint=token_mint,
                    slot=12345,
                    timestamp=9876543210,
                    use_cache=False
                )
    
    @pytest.mark.asyncio
    async def test_get_market_cap_with_cache_tracking(self, client, mock_market_cap_result):
        """Test cache hit tracking"""
        token_mint = "So11111111111111111111111111111111111111112"
        
        # Mock pre-cache service
        mock_precache = MagicMock()
        mock_precache.track_request = MagicMock()
        
        # Mock cache with data
        mock_cache = MagicMock()
        mock_cache.get.return_value = MagicMock(value=1000000.0)
        
        with patch('src.api.market_cap_api.calculate_market_cap', 
                  AsyncMock(return_value=mock_market_cap_result)):
            with patch('src.api.market_cap_api.get_precache_service', return_value=mock_precache):
                with patch('src.api.market_cap_api.get_cache', return_value=mock_cache):
                    response = client.get(f'/v1/market-cap/{token_mint}?timestamp=1234567890')
                    assert response.status_code == 200
                    
                    # Should track cache hit
                    mock_precache.track_request.assert_called_with(token_mint, cache_hit=True)
    
    @pytest.mark.asyncio
    async def test_get_market_cap_error(self, client):
        """Test error handling in market cap endpoint"""
        token_mint = "invalid_token"
        
        with patch('src.api.market_cap_api.calculate_market_cap', 
                  AsyncMock(side_effect=Exception("Test error"))):
            response = client.get(f'/v1/market-cap/{token_mint}')
            assert response.status_code == 500
            
            data = json.loads(response.data)
            assert 'error' in data
            assert data['token_mint'] == token_mint
    
    @pytest.mark.asyncio
    async def test_batch_market_caps(self, client, mock_market_cap_result):
        """Test batch market cap endpoint"""
        request_data = {
            "tokens": [
                "So11111111111111111111111111111111111111112",
                {"mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "slot": 12345},
                {"mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "timestamp": 9876543210}
            ]
        }
        
        with patch('src.api.market_cap_api.calculate_market_cap', 
                  AsyncMock(return_value=mock_market_cap_result)):
            with patch('src.api.market_cap_api.get_precache_service', return_value=None):
                response = client.post(
                    '/v1/market-cap/batch',
                    data=json.dumps(request_data),
                    content_type='application/json'
                )
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert 'results' in data
                assert data['count'] == 3
                assert len(data['results']) == 3
                
                # Check first result
                result = data['results'][0]
                assert result['token_mint'] == "So11111111111111111111111111111111111111112"
                assert result['market_cap'] == 1000000.0
    
    @pytest.mark.asyncio
    async def test_batch_market_caps_error(self, client):
        """Test batch endpoint error handling"""
        # Test missing tokens
        response = client.post(
            '/v1/market-cap/batch',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400
        
        # Test too many tokens
        request_data = {
            "tokens": [f"token_{i}" for i in range(51)]
        }
        response = client.post(
            '/v1/market-cap/batch',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert "Maximum 50 tokens" in data['error']
    
    def test_get_stats(self, client):
        """Test stats endpoint"""
        mock_cache = MagicMock()
        mock_cache.get_stats.return_value = {"total_keys": 100, "memory_usage": 1024}
        
        mock_precache = MagicMock()
        mock_precache.get_stats.return_value = {
            "tracked_tokens": 50,
            "hit_rate": 85.5
        }
        
        with patch('src.api.market_cap_api.get_cache', return_value=mock_cache):
            with patch('src.api.market_cap_api.get_precache_service', return_value=mock_precache):
                response = client.get('/v1/market-cap/stats')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert data['cache']['total_keys'] == 100
                assert data['precache_service']['tracked_tokens'] == 50
    
    @pytest.mark.asyncio
    async def test_get_popular_tokens(self, client, mock_market_cap_result):
        """Test popular tokens endpoint"""
        # Create different MC values
        results = [
            MarketCapResult(value=5000000.0, confidence=CONFIDENCE_HIGH, source="test",
                          supply=1000000.0, price=5.0, timestamp=1234567890),
            MarketCapResult(value=3000000.0, confidence=CONFIDENCE_HIGH, source="test",
                          supply=1000000.0, price=3.0, timestamp=1234567890),
            MarketCapResult(value=8000000.0, confidence=CONFIDENCE_HIGH, source="test",
                          supply=1000000.0, price=8.0, timestamp=1234567890),
        ]
        
        with patch('src.api.market_cap_api.calculate_market_cap', 
                  AsyncMock(side_effect=results)):
            response = client.get('/v1/market-cap/popular?limit=3')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert data['count'] == 3
            assert len(data['tokens']) == 3
            
            # Should be sorted by market cap (highest first)
            assert data['tokens'][0]['market_cap'] == 8000000.0
            assert data['tokens'][1]['market_cap'] == 5000000.0
            assert data['tokens'][2]['market_cap'] == 3000000.0
    
    @pytest.mark.asyncio
    async def test_get_trending_tokens(self, client, mock_market_cap_result):
        """Test trending tokens endpoint"""
        # Mock pre-cache service with token stats
        mock_precache = MagicMock()
        mock_precache.token_stats = {
            "token1": {"request_count": 100, "cache_hits": 80},
            "token2": {"request_count": 50, "cache_hits": 40},
            "token3": {"request_count": 200, "cache_hits": 150},
        }
        
        with patch('src.api.market_cap_api.calculate_market_cap', 
                  AsyncMock(return_value=mock_market_cap_result)):
            with patch('src.api.market_cap_api.get_precache_service', return_value=mock_precache):
                response = client.get('/v1/market-cap/trending?limit=2')
                assert response.status_code == 200
                
                data = json.loads(response.data)
                assert data['count'] == 2
                assert len(data['tokens']) == 2
                
                # Should be sorted by request count
                assert data['tokens'][0]['token_mint'] == "token3"
                assert data['tokens'][0]['request_count'] == 200
                assert data['tokens'][1]['token_mint'] == "token1"
                assert data['tokens'][1]['request_count'] == 100
    
    @pytest.mark.asyncio
    async def test_get_trending_tokens_no_service(self, client):
        """Test trending endpoint when pre-cache service is not available"""
        with patch('src.api.market_cap_api.get_precache_service', return_value=None):
            response = client.get('/v1/market-cap/trending')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert 'error' in data
            assert data['count'] == 0
    
    def test_decimal_to_float(self):
        """Test decimal to float conversion"""
        assert decimal_to_float(Decimal("123.456")) == 123.456
        assert decimal_to_float(123) == 123
        assert decimal_to_float("test") == "test"
        assert decimal_to_float(None) is None
    
    def test_404_handler(self, client):
        """Test 404 error handler"""
        response = client.get('/v1/market-cap/invalid/endpoint')
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert data['error'] == "Endpoint not found"


if __name__ == "__main__":
    # Run basic tests
    print("Testing Market Cap API...")
    
    test = TestMarketCapAPI()
    app.config['TESTING'] = True
    client = app.test_client()
    
    # Test health
    test.test_health_endpoint(client)
    print("✅ Health endpoint test passed")
    
    # Test decimal conversion
    test.test_decimal_to_float()
    print("✅ Decimal conversion test passed")
    
    # Test 404
    test.test_404_handler(client)
    print("✅ 404 handler test passed")
    
    print("\n✅ All basic tests passed!")
    print("\nRun 'pytest tests/test_market_cap_api.py -v' for full test suite") 