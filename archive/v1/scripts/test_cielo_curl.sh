#!/bin/bash
# Test Cielo API endpoints with curl

WALLET="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
BASE_URL="https://feed-api.cielo.finance/api/v1"

# Check if API key is provided
if [ -z "$1" ]; then
    echo "Usage: ./test_cielo_curl.sh YOUR_API_KEY"
    echo "Get your API key from: https://developer.cielo.finance"
    exit 1
fi

API_KEY=$1

echo "Testing Cielo Finance API Endpoints"
echo "Wallet: $WALLET"
echo "=================================="

# Function to test endpoint
test_endpoint() {
    local name=$1
    local endpoint=$2
    
    echo -e "\n### Testing: $name"
    echo "URL: $BASE_URL/$WALLET/$endpoint"
    
    # Try with x-api-key header first
    echo -e "\nWith x-api-key header:"
    curl -s -X GET "$BASE_URL/$WALLET/$endpoint" \
        -H "accept: application/json" \
        -H "x-api-key: $API_KEY" | jq '.' 2>/dev/null || echo "Failed to parse JSON"
    
    # If that fails, try Bearer token
    echo -e "\nWith Authorization Bearer header:"
    curl -s -X GET "$BASE_URL/$WALLET/$endpoint" \
        -H "accept: application/json" \
        -H "Authorization: Bearer $API_KEY" | jq '.' 2>/dev/null || echo "Failed to parse JSON"
}

# Test all endpoints
echo -e "\n=== ENDPOINT TESTS ==="

test_endpoint "Trading Stats" "trading-stats"
test_endpoint "Token PNL" "pnl/tokens"
test_endpoint "Total PNL Stats" "pnl/total-stats"
test_endpoint "Wallet Portfolio" "portfolio"

echo -e "\n=== ANALYSIS ==="
echo "Check the responses above to see:"
echo "1. Which auth method works (x-api-key vs Bearer)"
echo "2. What data each endpoint provides"
echo "3. Whether we get token-level details or just aggregates"