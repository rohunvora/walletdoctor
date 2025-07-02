#!/usr/bin/env python3
"""Quick test of Railway API with smaller wallet"""

import requests
import json
import time

# Configuration
RAILWAY_URL = "https://web-production-2bb2f.up.railway.app"
API_KEY = "wd_12345678901234567890123456789012"
SMALL_WALLET = "CuieVDEDtLo7FypA9SbLM9saXFdb1dsshEkyErMqkRQq"  # Smaller test wallet

print("Testing Railway API...")
print(f"URL: {RAILWAY_URL}")

# Test with smaller wallet first
headers = {"X-Api-Key": API_KEY}
url = f"{RAILWAY_URL}/v4/positions/export-gpt/{SMALL_WALLET}"

print(f"\nTesting with smaller wallet: {SMALL_WALLET[:8]}...")
start = time.time()
response = requests.get(url, headers=headers, timeout=30)
duration = time.time() - start

print(f"Status: {response.status_code}")
print(f"Response time: {duration:.2f}s")

if response.status_code == 200:
    data = response.json()
    print(f"Schema version: {data.get('schema_version')}")
    print(f"Total positions: {data['summary']['total_positions']}")
    print("✅ API is working!")
    
    # Save response
    with open('railway_test_small.json', 'w') as f:
        json.dump(data, f, indent=2)
else:
    print(f"Error: {response.text}") 