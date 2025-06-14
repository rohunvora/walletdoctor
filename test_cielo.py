import os
import requests
from datetime import datetime

wallet = "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm"
known_good_wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"  # 83 trades wallet

print(f"Testing problematic wallet: {wallet}")
print(f"Testing known good wallet: {known_good_wallet}")

# Test with different case variations
wallets_to_test = [
    (wallet, "Problematic wallet"),
    (known_good_wallet, "Known good wallet"),
]

CIELO_KEY = os.getenv("CIELO_KEY", "")
print(f"CIELO_KEY present: {bool(CIELO_KEY)} (length: {len(CIELO_KEY)})")

if not CIELO_KEY:
    print("No CIELO_KEY found in environment")
    exit(1)

headers = {"x-api-key": CIELO_KEY}

for test_wallet, label in wallets_to_test:
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Testing {label}: {test_wallet}")
    url = f"https://feed-api.cielo.finance/api/v1/{test_wallet}/pnl/tokens"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'items' in data['data']:
                items = data['data']['items']
                print(f"Items returned: {len(items)}")
                if items:
                    print(f"First token: {items[0].get('symbol', 'No symbol')}")
                    print(f"Total trades across all tokens: {sum(item.get('numSwaps', 0) for item in items)}")
                    # Show first few tokens
                    print(f"First 5 tokens:")
                    for i, item in enumerate(items[:5]):
                        print(f"  {i+1}. {item.get('symbol', 'Unknown')}: {item.get('numSwaps', 0)} swaps, P&L: ${item.get('realizedPnl', 0):,.2f}")
                else:
                    print("Empty items array!")
            else:
                print(f"Unexpected response structure: {list(data.keys())}")
                if 'data' in data:
                    print(f"Data keys: {list(data['data'].keys())}")
        else:
            print(f"Error: {response.text[:200]}")
    except Exception as e:
        print(f"Exception: {e}")

# Check if the problematic wallet has pagination info
print(f"\n{'='*60}")
print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking first page details for problematic wallet...")
url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
try:
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if 'data' in data:
            print(f"Data keys: {list(data['data'].keys())}")
            if 'paging' in data['data']:
                print(f"Paging info: {data['data']['paging']}")
except Exception as e:
    print(f"Exception: {e}")

# Also try the stats endpoint
print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Testing stats endpoint...")
stats_url = f"https://feed-api.cielo.finance/api/v1/{wallet}/stats"
try:
    response = requests.get(stats_url, headers=headers, timeout=10)
    print(f"Stats endpoint status: {response.status_code}")
    if response.status_code == 200:
        print(f"Stats response: {response.json()}")
except Exception as e:
    print(f"Stats exception: {e}") 