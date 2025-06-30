#!/usr/bin/env python3
"""Quick test of V3 implementation"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.lib.blockchain_fetcher_v3 import fetch_wallet_trades_v3

WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"


def print_progress(msg):
    print(f"[PROGRESS] {msg}")


print("Starting V3 test...")
result = fetch_wallet_trades_v3(WALLET, print_progress)

print("\n=== RESULTS ===")
metrics = result["summary"]["metrics"]
print(f"Signatures fetched: {metrics['signatures_fetched']}")
print(f"Signatures parsed: {metrics['signatures_parsed']}")
print(f"Events swap rows: {metrics['events_swap_rows']}")
print(f"Fallback rows: {metrics['fallback_rows']}")
print(f"Total trades: {result['summary']['total_trades']}")

# Check if fallback parser is working
if metrics["fallback_rows"] > 0:
    print(f"\n✓ SUCCESS: Fallback parser is working! ({metrics['fallback_rows']} trades)")
else:
    print(f"\n✗ FAILURE: Fallback parser not working")
