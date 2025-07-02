#!/usr/bin/env python3
"""
GPT Export Validation Test Runner (WAL-613)

Tests the GPT export endpoint using fixtures and validates responses.
"""

import pytest
import json
import os
import time
import requests
from typing import Dict, Any, List, Optional
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .validator import GPTExportValidator, validate_gpt_export

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestGPTExportValidation:
    """Test suite for GPT export validation"""
    
    # Test fixtures directory
    FIXTURES_DIR = Path(__file__).parent / "fixtures"
    
    # Small wallet address
    SMALL_WALLET = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # API configuration
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8081")
    API_KEY = os.getenv("API_KEY", "wd_" + "a" * 32)  # Default test key
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.validator = GPTExportValidator()
        self.start_time = time.time()
    
    def teardown_method(self):
        """Cleanup after each test"""
        duration = time.time() - self.start_time
        print(f"\nTest duration: {duration:.2f}s")
    
    def load_fixture(self, filename: str) -> Dict[str, Any]:
        """Load a test fixture"""
        path = self.FIXTURES_DIR / filename
        with open(path) as f:
            return json.load(f)
    
    def mock_api_response(self, fixture_data: Dict[str, Any], use_mock: bool = False) -> Dict[str, Any]:
        """
        Create a mock API response based on fixture data.
        Used ONLY when --use-mock flag is explicitly provided.
        
        Args:
            fixture_data: Test fixture data
            use_mock: Whether mocking is explicitly enabled
            
        Raises:
            RuntimeError: If mocking is not enabled
        """
        if not use_mock:
            raise RuntimeError(
                "Mock data requested but --use-mock flag not provided. "
                "Use --use-mock to enable mock mode, or ensure API is available."
            )
        
        response = fixture_data["expected_response"].copy()
        # Update timestamp to current time
        response["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return response
    
    @pytest.mark.parametrize("fixture_file", [
        "small_wallet_normal.json",
        "small_wallet_stale_prices.json",
        "small_wallet_empty.json",
        "small_wallet_estimated_prices.json"
    ])
    def test_schema_validation(self, fixture_file: str, request):
        """Test schema validation for various scenarios"""
        fixture = self.load_fixture(fixture_file)
        
        # Check if we're using mock mode
        use_mock = request.config.getoption("--use-mock", default=False)
        
        if use_mock:
            # Use mock data from fixture
            response = self.mock_api_response(fixture, use_mock=True)
        else:
            # Use the expected response directly for schema validation
            # This test doesn't require network access
            response = fixture["expected_response"]
        
        # Validate schema
        is_valid, errors, warnings = validate_gpt_export(response, fixture.get("tolerance", 0.005))
        
        # Check results
        if not is_valid:
            pytest.fail(f"Schema validation failed for {fixture_file}:\n" + "\n".join(errors))
        
        # Log warnings if any
        if warnings:
            print(f"\nWarnings for {fixture_file}:")
            for warning in warnings:
                print(f"  - {warning}")
    
    def test_normal_response_validation(self):
        """Test validation of normal response"""
        fixture = self.load_fixture("small_wallet_normal.json")
        # Use expected response directly - no mocking needed for schema tests
        response = fixture["expected_response"].copy()
        response["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Validate
        is_valid, errors, warnings = self.validator.validate(response)
        
        assert is_valid, f"Validation failed: {errors}"
        assert len(response["positions"]) == 2
        assert response["summary"]["total_positions"] == 2
        assert response["summary"]["stale_price_count"] == 0
    
    def test_stale_price_detection(self):
        """Test detection of stale prices"""
        fixture = self.load_fixture("small_wallet_stale_prices.json")
        response = fixture["expected_response"].copy()
        response["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Validate
        is_valid, errors, warnings = self.validator.validate(response)
        
        assert is_valid, f"Validation failed: {errors}"
        assert response["stale"] == True
        assert response["age_seconds"] >= 0
        assert response["summary"]["stale_price_count"] == 1
        
        # Check specific position has stale price
        stale_position = next(p for p in response["positions"] if p["token_symbol"] == "BONK")
        assert stale_position["price_confidence"] == "stale"
    
    def test_empty_portfolio_validation(self):
        """Test validation of empty portfolio"""
        fixture = self.load_fixture("small_wallet_empty.json")
        response = fixture["expected_response"].copy()
        response["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Validate
        is_valid, errors, warnings = self.validator.validate(response)
        
        assert is_valid, f"Validation failed: {errors}"
        assert len(response["positions"]) == 0
        assert response["summary"]["total_positions"] == 0
        assert response["summary"]["total_value_usd"] == "0.00"
    
    def test_estimated_price_handling(self):
        """Test handling of estimated prices"""
        fixture = self.load_fixture("small_wallet_estimated_prices.json")
        response = fixture["expected_response"].copy()
        response["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Validate
        is_valid, errors, warnings = self.validator.validate(response)
        
        assert is_valid, f"Validation failed: {errors}"
        
        # Check estimated price position
        est_position = next(p for p in response["positions"] if p["token_symbol"] == "NEWTOK")
        assert est_position["price_confidence"] == "est"
        
        # Estimated prices should not count as stale
        assert response["summary"]["stale_price_count"] == 0
    
    def test_totals_calculation(self):
        """Test that summary totals match position calculations"""
        fixture = self.load_fixture("small_wallet_normal.json")
        response = fixture["expected_response"].copy()
        response["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Calculate expected totals from positions
        positions = response["positions"]
        expected_value = sum(float(p["current_value_usd"]) for p in positions)
        expected_pnl = sum(float(p["unrealized_pnl_usd"]) for p in positions)
        
        # Compare with summary
        summary_value = float(response["summary"]["total_value_usd"])
        summary_pnl = float(response["summary"]["total_unrealized_pnl_usd"])
        
        # Check within tolerance (0.5%)
        tolerance = 0.005
        assert abs(summary_value - expected_value) <= expected_value * tolerance
        assert abs(summary_pnl - expected_pnl) <= abs(expected_pnl) * tolerance
    
    def test_required_fields_presence(self):
        """Test all required fields are present"""
        fixture = self.load_fixture("small_wallet_normal.json")
        response = fixture["expected_response"].copy()
        response["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Check top-level fields
        required_top = {"schema_version", "wallet", "timestamp", "positions", "summary", "price_sources"}
        assert required_top.issubset(set(response.keys()))
        
        # Check position fields
        if response["positions"]:
            position = response["positions"][0]
            required_pos = {
                "position_id", "token_symbol", "token_mint", "balance",
                "decimals", "cost_basis_usd", "current_price_usd",
                "current_value_usd", "unrealized_pnl_usd", "unrealized_pnl_pct",
                "price_confidence", "price_age_seconds", "opened_at", "last_trade_at"
            }
            assert required_pos.issubset(set(position.keys()))
    
    def test_invalid_schema_version(self):
        """Test rejection of invalid schema version"""
        response = {
            "schema_version": "2.0",  # Invalid version
            "wallet": self.SMALL_WALLET,
            "timestamp": "2024-01-28T12:00:00Z",
            "positions": [],
            "summary": {
                "total_positions": 0,
                "total_value_usd": "0.00",
                "total_unrealized_pnl_usd": "0.00",
                "total_unrealized_pnl_pct": "0.00",
                "stale_price_count": 0
            },
            "price_sources": {
                "primary": "https://walletdoctor.app/v4/prices",
                "primary_hint": "POST",
                "fallback": "https://api.coingecko.com/api/v3/simple/price",
                "fallback_hint": "GET"
            }
        }
        
        is_valid, errors, warnings = self.validator.validate(response)
        assert not is_valid
        assert any("schema version" in error.lower() for error in errors)
    
    def test_missing_required_fields(self):
        """Test detection of missing required fields"""
        # Missing positions field
        response = {
            "schema_version": "1.1",
            "wallet": self.SMALL_WALLET,
            "timestamp": "2024-01-28T12:00:00Z",
            # "positions": [],  # Missing!
            "summary": {
                "total_positions": 0,
                "total_value_usd": "0.00",
                "total_unrealized_pnl_usd": "0.00",
                "total_unrealized_pnl_pct": "0.00",
                "stale_price_count": 0
            },
            "price_sources": {}
        }
        
        is_valid, errors, warnings = self.validator.validate(response)
        assert not is_valid
        assert any("positions" in error for error in errors)
    
    @pytest.mark.requires_network
    @pytest.mark.integration
    @pytest.mark.skipif(
        os.getenv("SKIP_INTEGRATION_TESTS", "true").lower() == "true",
        reason="Integration tests disabled"
    )
    def test_live_api_small_wallet(self, request):
        """Test against live API with small wallet"""
        use_mock = request.config.getoption("--use-mock", default=False)
        
        if use_mock:
            # Use mock data instead of calling API
            fixture = self.load_fixture("small_wallet_normal.json")
            data = self.mock_api_response(fixture, use_mock=True)
            response_time = 50  # Fake response time
        else:
            # Make real API request
            headers = {"X-Api-Key": self.API_KEY}
            url = f"{self.API_BASE_URL}/v4/positions/export-gpt/{self.SMALL_WALLET}"
            
            try:
                logger.info(f"Making API request to {url}")
                # 10s hard timeout for fail-fast
                response = requests.get(url, headers=headers, timeout=10)
                
                # Log the HTTP status
                logger.info(f"HTTP Status: {response.status_code}")
                
                if response.status_code != 200:
                    logger.error(f"API request failed: {response.status_code} - {response.text}")
                    pytest.fail(f"API returned {response.status_code}: {response.text}")
                
                response.raise_for_status()
                data = response.json()
                
                # Get response time from header
                response_time = float(response.headers.get("X-Response-Time-Ms", 0))
                
            except requests.exceptions.Timeout as e:
                logger.error(f"API request timed out after 10s - ABORTED")
                pytest.fail(f"API request exceeded 10s timeout in strict mode")
            except requests.exceptions.RequestException as e:
                logger.error(f"API request failed: {e}")
                # No automatic fallback to mock - fail in strict mode
                pytest.fail(f"API request failed in strict mode: {e}")
        
        # Validate response
        is_valid, errors, warnings = self.validator.validate(data)
        
        assert is_valid, f"Live API validation failed: {errors}"
        
        # Check performance
        assert response_time < 1500, f"Response too slow: {response_time}ms"
    
    @pytest.mark.skipif(
        "--large" not in sys.argv,
        reason="Large wallet tests disabled by default"
    )
    def test_medium_wallet(self):
        """Test medium wallet (disabled by default)"""
        # TODO: Implement when Railway performance is resolved
        pytest.skip("Medium wallet tests not implemented yet")
    
    @pytest.mark.skipif(
        "--large" not in sys.argv,
        reason="Large wallet tests disabled by default"
    )
    def test_large_wallet(self):
        """Test large wallet (disabled by default)"""
        # TODO: Implement when Railway performance is resolved
        pytest.skip("Large wallet tests not implemented yet")


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--use-mock",
        action="store_true",
        default=False,
        help="Use mock data instead of making real API calls"
    )
    parser.addoption(
        "--large",
        action="store_true",
        default=False,
        help="Enable large wallet tests"
    )


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "requires_network: mark test as requiring network access"
    )


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"]) 