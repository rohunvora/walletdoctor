#!/bin/bash
# run_eval.sh - WalletDoctor v0.8.0-prices Evaluation Script

set -euo pipefail

# Configuration
BASE_URL="https://web-production-2bb2f.up.railway.app"
API_KEY="${API_KEY:-wd_test1234567890abcdef1234567890ab}"
SMALL_WALLET="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
MEDIUM_WALLET="3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🔍 WalletDoctor v0.8.0-prices Evaluation"
echo "======================================="
echo "Base URL: $BASE_URL"
echo "Schema: v0.8.0-prices"
echo ""

# Function to test endpoint and measure time
test_endpoint() {
    local wallet=$1
    local endpoint=$2
    local run_type=$3  # "cold" or "warm"
    
    echo -n "Testing $wallet ($run_type)... "
    
    local start_time=$(date +%s.%N)
    local response=$(curl -s -w "\n%{http_code}" \
        -H "X-Api-Key: $API_KEY" \
        "$BASE_URL$endpoint/$wallet")
    local end_time=$(date +%s.%N)
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')
    local elapsed=$(echo "$end_time - $start_time" | bc)
    
    if [[ "$http_code" != "200" ]]; then
        echo -e "${RED}FAILED${NC} (HTTP $http_code)"
        return 1
    fi
    
    echo -e "${GREEN}OK${NC} (${elapsed}s)"
    echo "$body" > "/tmp/eval_${wallet}_${run_type}.json"
    echo "$elapsed"
}

# Function to calculate non-null price percentage
calc_price_coverage() {
    local json_file=$1
    
    local total_positions=$(jq '.positions | length' "$json_file" 2>/dev/null || echo "0")
    if [[ "$total_positions" == "0" ]]; then
        echo "N/A"
        return
    fi
    
    local non_null_prices=$(jq '[.positions[] | select(.current_price_usd != null)] | length' "$json_file")
    local percentage=$(echo "scale=2; $non_null_prices * 100 / $total_positions" | bc)
    echo "${percentage}%"
}

# Initialize results
EVAL_RESULTS=()
EXIT_CODE=0

# Test 1: Small wallet positions (cold)
echo -e "\n${YELLOW}Test 1: Small Wallet Positions${NC}"
cold_time_small=$(test_endpoint "$SMALL_WALLET" "/v4/positions/export-gpt" "cold" || echo "ERROR")
sleep 2

# Test 2: Small wallet positions (warm)
warm_time_small=$(test_endpoint "$SMALL_WALLET" "/v4/positions/export-gpt" "warm" || echo "ERROR")

# Analyze small wallet results
if [[ -f "/tmp/eval_${SMALL_WALLET}_warm.json" ]]; then
    schema_version=$(jq -r '.schema_version' "/tmp/eval_${SMALL_WALLET}_warm.json")
    price_coverage=$(calc_price_coverage "/tmp/eval_${SMALL_WALLET}_warm.json")
    
    EVAL_RESULTS+=("$SMALL_WALLET,/v4/positions/export-gpt,$cold_time_small,$warm_time_small,$price_coverage,$schema_version,Small demo (18 pos)")
    
    # Validation checks
    if [[ "$schema_version" != "v0.8.0-prices" ]]; then
        echo -e "${RED}ERROR: Wrong schema version: $schema_version (expected v0.8.0-prices)${NC}"
        EXIT_CODE=1
    fi
    
    price_pct_numeric=$(echo "$price_coverage" | sed 's/%//')
    if (( $(echo "$price_pct_numeric < 90" | bc -l) )); then
        echo -e "${RED}ERROR: Price coverage $price_coverage < 90%${NC}"
        EXIT_CODE=1
    fi
fi

# Test 3: Medium wallet positions (cold)
echo -e "\n${YELLOW}Test 2: Medium Wallet Positions${NC}"
cold_time_medium=$(test_endpoint "$MEDIUM_WALLET" "/v4/positions/export-gpt" "cold" || echo "ERROR")
sleep 2

# Test 4: Medium wallet positions (warm)
warm_time_medium=$(test_endpoint "$MEDIUM_WALLET" "/v4/positions/export-gpt" "warm" || echo "ERROR")

# Analyze medium wallet results
if [[ -f "/tmp/eval_${MEDIUM_WALLET}_warm.json" ]]; then
    schema_version=$(jq -r '.schema_version' "/tmp/eval_${MEDIUM_WALLET}_warm.json")
    price_coverage=$(calc_price_coverage "/tmp/eval_${MEDIUM_WALLET}_warm.json")
    
    EVAL_RESULTS+=("$MEDIUM_WALLET,/v4/positions/export-gpt,$cold_time_medium,$warm_time_medium,$price_coverage,$schema_version,Medium demo (356 pos)")
    
    # Validation checks
    if [[ "$schema_version" != "v0.8.0-prices" ]]; then
        echo -e "${RED}ERROR: Wrong schema version: $schema_version${NC}"
        EXIT_CODE=1
    fi
    
    price_pct_numeric=$(echo "$price_coverage" | sed 's/%//')
    if (( $(echo "$price_pct_numeric < 90" | bc -l) )); then
        echo -e "${RED}ERROR: Price coverage $price_coverage < 90%${NC}"
        EXIT_CODE=1
    fi
fi

# Test trades endpoints (for completeness)
echo -e "\n${YELLOW}Test 3: Trade Endpoints${NC}"
trades_time_small=$(test_endpoint "$SMALL_WALLET" "/v4/trades/export-gpt" "cold" || echo "ERROR")
EVAL_RESULTS+=("$SMALL_WALLET,/v4/trades/export-gpt,$trades_time_small,N/A,N/A,N/A,Small trades (1106)")

trades_time_medium=$(test_endpoint "$MEDIUM_WALLET" "/v4/trades/export-gpt" "cold" || echo "ERROR")
EVAL_RESULTS+=("$MEDIUM_WALLET,/v4/trades/export-gpt,$trades_time_medium,N/A,N/A,N/A,Medium trades (6428)")

# Print evaluation matrix
echo -e "\n${YELLOW}📊 Evaluation Matrix${NC}"
echo "=================================="
echo "wallet,endpoint,cold_time_s,warm_time_s,non_null_price_pct,schema_version,notes"
for result in "${EVAL_RESULTS[@]}"; do
    echo "$result"
done

# Performance checks
echo -e "\n${YELLOW}🎯 Performance Validation${NC}"
echo "=================================="

# Check cold start times
if (( $(echo "$cold_time_small > 8" | bc -l) )); then
    echo -e "${RED}FAIL: Small wallet cold time ${cold_time_small}s > 8s${NC}"
    EXIT_CODE=1
elif (( $(echo "$cold_time_small > 6" | bc -l) )); then
    echo -e "${YELLOW}WARN: Small wallet cold time ${cold_time_small}s > 6s${NC}"
else
    echo -e "${GREEN}PASS: Small wallet cold time ${cold_time_small}s ≤ 6s${NC}"
fi

if (( $(echo "$cold_time_medium > 8" | bc -l) )); then
    echo -e "${RED}FAIL: Medium wallet cold time ${cold_time_medium}s > 8s${NC}"
    EXIT_CODE=1
elif (( $(echo "$cold_time_medium > 6" | bc -l) )); then
    echo -e "${YELLOW}WARN: Medium wallet cold time ${cold_time_medium}s > 6s${NC}"
else
    echo -e "${GREEN}PASS: Medium wallet cold time ${cold_time_medium}s ≤ 6s${NC}"
fi

# Check warm times
if (( $(echo "$warm_time_small > 5" | bc -l) )); then
    echo -e "${RED}FAIL: Small wallet warm time ${warm_time_small}s > 5s${NC}"
    EXIT_CODE=1
elif (( $(echo "$warm_time_small > 3" | bc -l) )); then
    echo -e "${YELLOW}WARN: Small wallet warm time ${warm_time_small}s > 3s${NC}"
else
    echo -e "${GREEN}PASS: Small wallet warm time ${warm_time_small}s ≤ 3s${NC}"
fi

if (( $(echo "$warm_time_medium > 5" | bc -l) )); then
    echo -e "${RED}FAIL: Medium wallet warm time ${warm_time_medium}s > 5s${NC}"
    EXIT_CODE=1
elif (( $(echo "$warm_time_medium > 3" | bc -l) )); then
    echo -e "${YELLOW}WARN: Medium wallet warm time ${warm_time_medium}s > 3s${NC}"
else
    echo -e "${GREEN}PASS: Medium wallet warm time ${warm_time_medium}s ≤ 3s${NC}"
fi

# Clean up temp files
rm -f /tmp/eval_*.json

# Final result
echo ""
if [[ "$EXIT_CODE" -eq 0 ]]; then
    echo -e "${GREEN}✅ All tests passed! v0.8.0-prices is working correctly.${NC}"
else
    echo -e "${RED}❌ Some tests failed. Check logs above.${NC}"
fi

exit $EXIT_CODE 