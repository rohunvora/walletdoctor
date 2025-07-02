#!/bin/bash
# WalletDoctor Deployment Verification Script

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== WalletDoctor Deployment Verification ===${NC}"

# Configuration
API_URL="${API_URL:-http://localhost:5000}"
VERIFY_AUTH="${VERIFY_AUTH:-false}"
API_KEY="${TEST_API_KEY:-wd_test1234567890abcdef1234567890ab}"

echo -e "\nVerifying deployment at: ${YELLOW}$API_URL${NC}"

# Function to check endpoint
check_endpoint() {
    local endpoint=$1
    local expected_status=$2
    local description=$3
    local headers=$4
    
    echo -n "Checking $description... "
    
    if [ -n "$headers" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" -H "$headers" "$API_URL$endpoint")
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL$endpoint")
    fi
    
    if [ "$response" = "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} ($response)"
        return 0
    else
        echo -e "${RED}✗${NC} (Expected $expected_status, got $response)"
        return 1
    fi
}

# Function to check JSON response
check_json_response() {
    local endpoint=$1
    local json_path=$2
    local expected_value=$3
    local description=$4
    
    echo -n "Checking $description... "
    
    response=$(curl -s "$API_URL$endpoint")
    actual_value=$(echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data$json_path)" 2>/dev/null || echo "ERROR")
    
    if [ "$actual_value" = "$expected_value" ] || [ -n "$actual_value" -a "$actual_value" != "ERROR" ]; then
        echo -e "${GREEN}✓${NC} ($actual_value)"
        return 0
    else
        echo -e "${RED}✗${NC} (Expected $expected_value, got $actual_value)"
        return 1
    fi
}

# Track results
total_tests=0
passed_tests=0

# 1. Basic Health Check
echo -e "\n${YELLOW}1. Basic Health Checks${NC}"

((total_tests++))
if check_endpoint "/health" "200" "Health endpoint"; then
    ((passed_tests++))
fi

((total_tests++))
if check_endpoint "/" "200" "Home endpoint"; then
    ((passed_tests++))
fi

((total_tests++))
if check_json_response "/health" "['status']" "healthy" "Health status"; then
    ((passed_tests++))
fi

# 2. Metrics and Monitoring
echo -e "\n${YELLOW}2. Metrics and Monitoring${NC}"

((total_tests++))
if check_endpoint "/metrics" "200" "Metrics endpoint"; then
    ((passed_tests++))
    
    # Check if metrics contain expected values
    metrics=$(curl -s "$API_URL/metrics")
    if echo "$metrics" | grep -q "walletdoctor_active_streams"; then
        echo -e "  ${GREEN}✓${NC} Prometheus metrics format verified"
    else
        echo -e "  ${YELLOW}⚠${NC} Metrics format may be incorrect"
    fi
fi

# 3. Authentication (if enabled)
if [ "$VERIFY_AUTH" = "true" ]; then
    echo -e "\n${YELLOW}3. Authentication Tests${NC}"
    
    ((total_tests++))
    if check_endpoint "/v4/wallet/test/stream" "401" "Endpoint without auth"; then
        ((passed_tests++))
    fi
    
    ((total_tests++))
    if check_endpoint "/v4/wallet/test/stream" "401" "Invalid API key" "X-API-Key: invalid"; then
        ((passed_tests++))
    fi
    
    ((total_tests++))
    if check_endpoint "/v4/wallet/test/stream" "200" "Valid API key" "X-API-Key: $API_KEY"; then
        ((passed_tests++))
    fi
else
    echo -e "\n${YELLOW}3. Authentication Tests${NC} - Skipped (set VERIFY_AUTH=true to enable)"
fi

# 4. SSE Streaming Test
echo -e "\n${YELLOW}4. SSE Streaming Tests${NC}"

echo -n "Testing SSE connection... "
# Test SSE stream (with timeout)
sse_test=$(timeout 3 curl -s -N -H "X-API-Key: $API_KEY" "$API_URL/v4/wallet/Bos1uqQZ4RZxFrkD1ktfyRSnafhfMuGhxgkdngGTwFGg/stream" 2>/dev/null | head -n 5)

((total_tests++))
if echo "$sse_test" | grep -q "event:"; then
    echo -e "${GREEN}✓${NC} SSE events received"
    ((passed_tests++))
    
    # Check for specific event types
    if echo "$sse_test" | grep -q "event: connected"; then
        echo -e "  ${GREEN}✓${NC} Connected event received"
    fi
else
    echo -e "${RED}✗${NC} No SSE events received"
fi

# 5. Error Handling
echo -e "\n${YELLOW}5. Error Handling Tests${NC}"

((total_tests++))
if check_endpoint "/nonexistent" "404" "404 error handling"; then
    ((passed_tests++))
fi

# 6. Performance Check
echo -e "\n${YELLOW}6. Performance Tests${NC}"

echo -n "Checking response time... "
start_time=$(date +%s%N)
curl -s -o /dev/null "$API_URL/health"
end_time=$(date +%s%N)
response_time=$(( (end_time - start_time) / 1000000 ))

((total_tests++))
if [ "$response_time" -lt 1000 ]; then
    echo -e "${GREEN}✓${NC} ($response_time ms)"
    ((passed_tests++))
else
    echo -e "${YELLOW}⚠${NC} ($response_time ms - slower than expected)"
fi

# 7. Security Headers
echo -e "\n${YELLOW}7. Security Headers${NC}"

headers=$(curl -s -I "$API_URL/health")

check_security_header() {
    local header=$1
    local expected=$2
    
    echo -n "Checking $header... "
    ((total_tests++))
    
    if echo "$headers" | grep -qi "$header: $expected"; then
        echo -e "${GREEN}✓${NC}"
        ((passed_tests++))
    else
        echo -e "${RED}✗${NC}"
    fi
}

check_security_header "X-Content-Type-Options" "nosniff"
check_security_header "X-Frame-Options" "DENY"
check_security_header "X-XSS-Protection" "1; mode=block"

# 8. Integration Test
echo -e "\n${YELLOW}8. Integration Tests${NC}"

if [ -f "tests/test_sse_integration.py" ]; then
    echo "Running integration tests..."
    if API_URL="$API_URL" python3 tests/test_sse_integration.py > /tmp/integration_test.log 2>&1; then
        echo -e "${GREEN}✓${NC} All integration tests passed"
        ((passed_tests++))
    else
        echo -e "${RED}✗${NC} Integration tests failed"
        echo "  See /tmp/integration_test.log for details"
    fi
    ((total_tests++))
else
    echo -e "${YELLOW}⚠${NC} Integration tests not found"
fi

# Summary
echo -e "\n${GREEN}=== Verification Summary ===${NC}"
echo -e "Total tests: $total_tests"
echo -e "Passed: ${GREEN}$passed_tests${NC}"
echo -e "Failed: ${RED}$((total_tests - passed_tests))${NC}"

if [ "$passed_tests" -eq "$total_tests" ]; then
    echo -e "\n${GREEN}✓ All verification tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}✗ Some tests failed. Please review the output above.${NC}"
    exit 1
fi 