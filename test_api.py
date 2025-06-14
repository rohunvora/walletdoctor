import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scripts.data import fetch_cielo_pnl

# Test wallets
test_wallets = [
    ("DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm", "3718 trades wallet"),
    ("34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya", "83 trades wallet"),
]

for wallet, label in test_wallets:
    print(f"\nTesting {label}: {wallet}")
    print("=" * 60)
    
    # Test with instant mode limit (1000)
    result = fetch_cielo_pnl(wallet, max_items=1000)
    
    if 'data' in result and 'items' in result['data']:
        items = result['data']['items']
        print(f"Items returned: {len(items)}")
        if items:
            # Count total trades
            total_trades = sum(item.get('numSwaps', 0) for item in items)
            print(f"Total trades across all tokens: {total_trades}")
            print(f"First 3 tokens:")
            for i, item in enumerate(items[:3]):
                print(f"  {item.get('symbol', 'Unknown')}: {item.get('numSwaps', 0)} swaps")
    else:
        print(f"No data returned. Status: {result.get('status', 'unknown')}")
        if 'message' in result:
            print(f"Message: {result['message']}") 