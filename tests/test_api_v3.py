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
    response = requests.post(
        "http://localhost:8080/analyze",
        json={"wallet": wallet}
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("\nFetch Metrics:")
        for key, value in data['fetch_metrics'].items():
            print(f"  {key}: {value}")
        print("\nAnalytics:")
        for key, value in data['analytics'].items():
            if key != 'tokens_traded':
                print(f"  {key}: {value}")
        print(f"\nSample trades: {len(data.get('sample_trades', []))} trades shown")
    else:
        print(response.text)
except Exception as e:
    print(f"Error: {e}") 