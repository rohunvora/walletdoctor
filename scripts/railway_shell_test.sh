#!/bin/bash
# Script to test blockchain fetcher directly on Railway shell

echo "=== Railway Shell Blockchain Fetcher Test ==="
echo "Time: $(date)"
echo "Environment:"
echo "  HELIUS_KEY present: ${HELIUS_KEY:+true}"
echo "  BIRDEYE_API_KEY present: ${BIRDEYE_API_KEY:+true}"
echo "  HELIUS_PARALLEL_REQUESTS: ${HELIUS_PARALLEL_REQUESTS:-not set}"
echo ""

# Test 1: Basic connectivity
echo "Test 1: Basic Helius connectivity"
time curl -s -X GET "https://api.helius.xyz/v0/addresses/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya/transactions?api-key=$HELIUS_KEY&limit=1" > /dev/null
echo ""

# Test 2: Run blockchain fetcher for small wallet
echo "Test 2: Blockchain fetcher for small wallet"
time python3 -c "
import os
import sys
sys.path.insert(0, '.')
os.environ['HELIUS_KEY'] = '$HELIUS_KEY'
os.environ['BIRDEYE_API_KEY'] = '$BIRDEYE_API_KEY'
from src.lib.blockchain_fetcher_v3_fast import fetch_wallet_trades_fast
result = fetch_wallet_trades_fast('34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya', print)
print(f'\\nTotal trades: {result["summary"]["total_trades"]}')
"

echo ""
echo "=== Test Complete ===" 