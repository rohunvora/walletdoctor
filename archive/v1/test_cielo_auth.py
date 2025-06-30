#!/usr/bin/env python3
"""Test different Cielo auth methods"""

import os
import requests

api_key = os.getenv('CIELO_KEY')
wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"

print(f"Testing Cielo auth with key: {api_key[:10]}...")

# Test 1: x-api-key header
print("\n1. Testing with x-api-key header:")
response = requests.get(
    f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats",
    headers={"x-api-key": api_key}
)
print(f"   Status: {response.status_code}")
if response.status_code != 200:
    print(f"   Response: {response.text[:100]}")

# Test 2: Authorization Bearer
print("\n2. Testing with Authorization Bearer:")
response = requests.get(
    f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats",
    headers={"Authorization": f"Bearer {api_key}"}
)
print(f"   Status: {response.status_code}")
if response.status_code != 200:
    print(f"   Response: {response.text[:100]}")

# Test 3: API-Key header
print("\n3. Testing with API-Key header:")
response = requests.get(
    f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats",
    headers={"API-Key": api_key}
)
print(f"   Status: {response.status_code}")
if response.status_code != 200:
    print(f"   Response: {response.text[:100]}")

# Test 4: Query parameter
print("\n4. Testing with api_key query param:")
response = requests.get(
    f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats?api_key={api_key}"
)
print(f"   Status: {response.status_code}")
if response.status_code != 200:
    print(f"   Response: {response.text[:100]}")

print("\nNote: Cielo might require a different API key format or authentication method")