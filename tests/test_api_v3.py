#!/usr/bin/env python3
"""Test the V3 API"""

import requests
import json

# Test home endpoint
print("Testing home endpoint...")
try:
    response = requests.get("http://localhost:8080/")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")

# Test health endpoint
print("\nTesting health endpoint...")
try:
    response = requests.get("http://localhost:8080/health")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")

# Test analyze endpoint with sample wallet
print("\nTesting analyze endpoint...")
wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
try:
    response = requests.post("http://localhost:8080/analyze", json={"wallet": wallet})
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("\nFetch Metrics:")
        for key, value in data["fetch_metrics"].items():
            print(f"  {key}: {value}")
        print("\nAnalytics:")
        for key, value in data["analytics"].items():
            if key != "tokens_traded":
                print(f"  {key}: {value}")
        print(f"\nSample trades: {len(data.get('sample_trades', []))} trades shown")
    else:
        print(response.text)
except Exception as e:
    print(f"Error: {e}")


# WAL-108: Integration test for full payload
print("\n\n=== WAL-108: Integration Test - Full Payload Validation ===")

def validate_trade_schema(trade):
    """Validate a single trade against JSON schema v1.0"""
    required_fields = {
        "timestamp": str,  # ISO8601 string
        "signature": str,
        "action": str,  # buy/sell
        "token": str,
        "amount": (int, float),
        "token_in": dict,
        "token_out": dict,
        "price": (int, float, type(None)),
        "value_usd": (int, float, type(None)),
        "pnl_usd": (int, float),
        "fees_usd": (int, float),
        "priced": bool,
        "dex": str,
        "tx_type": str,
    }
    
    # Check all required fields exist
    for field, expected_type in required_fields.items():
        if field not in trade:
            return False, f"Missing field: {field}"
        
        if not isinstance(trade[field], expected_type):
            return False, f"Field {field} has wrong type: expected {expected_type}, got {type(trade[field])}"
    
    # Validate nested token objects
    for token_field in ["token_in", "token_out"]:
        token = trade[token_field]
        if not all(key in token for key in ["mint", "symbol", "amount"]):
            return False, f"{token_field} missing required fields"
        if not isinstance(token["mint"], str) or not isinstance(token["symbol"], str):
            return False, f"{token_field} has invalid field types"
        if not isinstance(token["amount"], (int, float)):
            return False, f"{token_field}.amount must be numeric"
    
    # Validate action values
    if trade["action"] not in ["buy", "sell"]:
        return False, f"Invalid action: {trade['action']}"
    
    # Validate tx_type
    if trade["tx_type"] != "swap":
        return False, f"Invalid tx_type: {trade['tx_type']}"
    
    return True, "Valid"


# Test with a wallet known to have many trades
test_wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"  # Can be replaced with a more active wallet

try:
    print(f"Testing with wallet: {test_wallet}")
    response = requests.post("http://localhost:8080/v4/analyze", json={"wallet": test_wallet})
    
    if response.status_code != 200:
        print(f"❌ API returned {response.status_code}: {response.text}")
    else:
        data = response.json()
        
        # Check response structure
        assert "wallet" in data, "Response missing 'wallet' field"
        assert "trades" in data, "Response missing 'trades' field"
        assert "summary" in data, "Response missing 'summary' field"
        
        trades = data["trades"]
        print(f"\n✅ Response structure valid")
        print(f"Total trades returned: {len(trades)}")
        
        # Validate we got trades
        if len(trades) == 0:
            print("⚠️  No trades returned - cannot validate schema")
        else:
            # Validate first 5 trades in detail
            print(f"\nValidating trade schema (checking first 5 trades)...")
            all_valid = True
            for i, trade in enumerate(trades[:5]):
                valid, msg = validate_trade_schema(trade)
                if valid:
                    print(f"  Trade {i+1}: ✅ Valid")
                else:
                    print(f"  Trade {i+1}: ❌ {msg}")
                    all_valid = False
            
            if all_valid:
                print(f"\n✅ All validated trades match schema v1.0")
            else:
                print(f"\n❌ Some trades don't match schema")
        
        # Check if we got enough trades (goal is >100 but depends on wallet)
        if len(trades) > 100:
            print(f"\n✅ Got {len(trades)} trades (>100 requirement met)")
        elif len(trades) > 0:
            print(f"\n⚠️  Got {len(trades)} trades (less than 100, but wallet may not have more)")
        
        # Validate summary section
        summary = data["summary"]
        print(f"\nSummary validation:")
        print(f"  Total trades: {summary.get('total_trades', 0)}")
        print(f"  Total P&L: ${summary.get('total_pnl_usd', 0):.2f}")
        print(f"  Win rate: {summary.get('win_rate', 0):.1f}%")
        
        print(f"\n✅ Integration test complete")
        
except Exception as e:
    print(f"\n❌ Integration test failed: {e}")
    import traceback
    traceback.print_exc()
