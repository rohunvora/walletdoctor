import duckdb
import os
from datetime import datetime

# Check database contents
db = duckdb.connect("coach.db")

print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking database contents...")

# Check PnL table
pnl_count = db.execute("SELECT COUNT(*) FROM pnl").fetchone()[0]
print(f"PnL entries: {pnl_count}")

if pnl_count > 0:
    # Get some sample data
    print("\nFirst 5 PnL entries:")
    samples = db.execute("SELECT symbol, realizedPnl FROM pnl LIMIT 5").fetchall()
    for s in samples:
        print(f"  {s[0]}: ${s[1]:,.2f}")

# Check TX table
tx_count = db.execute("SELECT COUNT(*) FROM tx").fetchone()[0]
print(f"\nTX entries: {tx_count}")

# Test the wallet directly
print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Testing Cielo API directly...")
wallet = "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm"

import requests
CIELO_KEY = os.getenv("CIELO_KEY", "")
print(f"CIELO_KEY present: {bool(CIELO_KEY)}")

if CIELO_KEY:
    url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
    headers = {"x-api-key": CIELO_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'items' in data['data']:
                items = data['data']['items']
                print(f"Items returned: {len(items)}")
                if items:
                    print(f"First item: {items[0].get('symbol', 'No symbol')}")
            else:
                print(f"Response structure: {list(data.keys())}")
        else:
            print(f"Error response: {response.text[:200]}")
    except Exception as e:
        print(f"API Error: {e}")

db.close() 