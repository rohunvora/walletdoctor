#!/usr/bin/env python3
"""
Quick test to verify GPT validation harness (WAL-613)
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.gpt_validation.validator import GPTExportValidator, validate_gpt_export


def test_gpt_validator_works():
    """Basic test to ensure the validator is functional"""
    # Create a minimal valid response
    response = {
        "schema_version": "1.1",
        "wallet": "34zYDgjy9Uyj9NZnDVKBB45urkbBV4h5LzxWjXJg9VCya",
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
            "primary_hint": "POST {mints: [string], timestamps: [number]} returns {mint: price_usd} in JSON",
            "fallback": "https://api.coingecko.com/api/v3/simple/price",
            "fallback_hint": "GET ?ids={coingecko_id}&vs_currencies=usd returns {id: {usd: price}} in JSON"
        }
    }
    
    # Validate
    is_valid, errors, warnings = validate_gpt_export(response)
    
    assert is_valid, f"Validation failed: {errors}"
    assert len(errors) == 0
    print("✅ GPT validator is working correctly")


def test_gpt_validator_catches_errors():
    """Test that validator catches schema errors"""
    # Invalid response (missing required fields)
    response = {
        "schema_version": "1.1",
        "wallet": "34zYDgjy9Uyj9NZnDVKBB45urkbBV4h5LzxWjXJg9VCya",
        # Missing timestamp, positions, summary, price_sources
    }
    
    # Validate
    is_valid, errors, warnings = validate_gpt_export(response)
    
    assert not is_valid
    assert len(errors) > 0
    assert any("timestamp" in error for error in errors)
    print("✅ GPT validator correctly catches errors")


if __name__ == "__main__":
    test_gpt_validator_works()
    test_gpt_validator_catches_errors()
    print("\n✅ All GPT validation harness tests passed!") 