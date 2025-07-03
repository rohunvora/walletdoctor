#!/bin/bash

# Local test for GPT-006 CI workflow functionality
# Validates all components work before deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 GPT-006 CI Workflow Local Test${NC}"
echo "=================================="
echo "Testing all components of .github/workflows/gpt-integration.yml"
echo ""

# Configuration from CI workflow
API_URL="https://web-production-2bb2f.up.railway.app"
TEST_WALLET="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
API_KEY="${API_KEY:-wd_12345678901234567890123456789012}"

# Test counters
TESTS_PASSED=0
TOTAL_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "${YELLOW}Testing: $test_name${NC}"
    ((TOTAL_TESTS++))
    
    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASS: $test_name${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL: $test_name${NC}"
    fi
    echo ""
}

# Test 1: Schema Validation (from schema-validation job)
test_schema_validation() {
    echo "  Running schema validation..."
    
    # Test schema validation script
    if ! python3 scripts/validate_openapi_schema.py schemas/trades_export_v0.7.0_openapi.json 0.7.0 >/dev/null 2>&1; then
        echo "  ❌ Schema validation script failed"
        return 1
    fi
    
    # Check all required schema files
    for file in ExportResponse Trade TokenFlow ErrorResponse RetryErrorResponse trades_export_combined; do
        if [ ! -f "schemas/${file}_v0.7.0.json" ]; then
            echo "  ❌ Missing schema file: schemas/${file}_v0.7.0.json"
            return 1
        fi
    done
    
    echo "  ✅ All schema validations passed"
    return 0
}

# Test 2: Cold Performance Test
test_cold_performance() {
    echo "  Testing cold performance against $API_URL..."
    
    local start_ms=$(python3 -c "import time; print(int(time.time() * 1000))")
    
    local http_code=$(curl -s -o /tmp/ci_test_response.json -w "%{http_code}" \
        -H "X-Api-Key: $API_KEY" \
        -H "Accept: application/json" \
        --max-time 30 \
        "$API_URL/v4/trades/export-gpt/$TEST_WALLET" 2>/dev/null)
    
    local end_ms=$(python3 -c "import time; print(int(time.time() * 1000))")
    local duration_ms=$((end_ms - start_ms))
    local duration_sec=$(echo "scale=2; $duration_ms / 1000" | bc)
    
    echo "  Response time: ${duration_sec}s (${duration_ms}ms)"
    echo "  HTTP status: $http_code"
    
    # Check HTTP status
    if [ "$http_code" != "200" ]; then
        echo "  ❌ Expected HTTP 200, got $http_code"
        if [ -f /tmp/ci_test_response.json ]; then
            echo "  Response: $(cat /tmp/ci_test_response.json)"
        fi
        return 1
    fi
    
    # Check response structure
    if ! jq -e '.wallet, .signatures, .trades' /tmp/ci_test_response.json >/dev/null 2>&1; then
        echo "  ❌ Response missing required fields (wallet, signatures, trades)"
        return 1
    fi
    
    local trade_count=$(jq '.trades | length' /tmp/ci_test_response.json)
    echo "  ✅ Found $trade_count trades"
    
    # Performance check (using CI thresholds)
    if [ $duration_ms -gt 8000 ]; then
        echo "  ❌ Cold performance ${duration_sec}s > 8s fail threshold"
        return 1
    elif [ $duration_ms -gt 6000 ]; then
        echo "  ⚠️  Cold performance ${duration_sec}s > 6s warning threshold"
        echo "      (This would show as warning in CI, not fail)"
    fi
    
    return 0
}

# Test 3: Warm Performance Test
test_warm_performance() {
    echo "  Testing warm performance (second request)..."
    sleep 2  # Brief pause like CI
    
    local start_ms=$(python3 -c "import time; print(int(time.time() * 1000))")
    
    local http_code=$(curl -s -o /tmp/ci_test_response2.json -w "%{http_code}" \
        -H "X-Api-Key: $API_KEY" \
        -H "Accept: application/json" \
        --max-time 10 \
        "$API_URL/v4/trades/export-gpt/$TEST_WALLET" 2>/dev/null)
    
    local end_ms=$(python3 -c "import time; print(int(time.time() * 1000))")
    local duration_ms=$((end_ms - start_ms))
    local duration_sec=$(echo "scale=2; $duration_ms / 1000" | bc)
    
    echo "  Response time: ${duration_sec}s (${duration_ms}ms)"
    
    # Performance check (adjusted for Railway single worker reality)
    if [ $duration_ms -gt 5000 ]; then
        echo "  ❌ Warm performance ${duration_sec}s > 5s fail threshold"
        return 1
    elif [ $duration_ms -gt 3000 ]; then
        echo "  ⚠️  Warm performance ${duration_sec}s > 3s warning threshold"
        echo "      (This would show as warning in CI, not fail)"
    fi
    
    return 0
}

# Test 4: Auth Error Handling
test_auth_error() {
    echo "  Testing auth error handling (401 expected for missing API key)..."
    
    local http_code=$(curl -s -o /tmp/ci_test_auth_error.json -w "%{http_code}" \
        --max-time 5 \
        "$API_URL/v4/trades/export-gpt/$TEST_WALLET" 2>/dev/null)
    
    if [ "$http_code" = "401" ]; then
        echo "  ✅ Correctly returned 401 for missing API key"
        if [ -f /tmp/ci_test_auth_error.json ]; then
            local error_msg=$(jq -r '.error' /tmp/ci_test_auth_error.json 2>/dev/null || echo "N/A")
            echo "  Error message: $error_msg"
        fi
        return 0
    elif [ "$http_code" = "403" ]; then
        echo "  ✅ Returned 403 for missing API key (also acceptable)"
        return 0
    else
        echo "  ❌ Expected 401 or 403, got $http_code"
        if [ -f /tmp/ci_test_auth_error.json ]; then
            echo "  Response: $(cat /tmp/ci_test_auth_error.json)"
        fi
        return 1
    fi
}

# Test 5: GitHub Actions Workflow Syntax
test_workflow_syntax() {
    echo "  Checking workflow file syntax..."
    
    if [ ! -f ".github/workflows/gpt-integration.yml" ]; then
        echo "  ❌ Workflow file missing: .github/workflows/gpt-integration.yml"
        return 1
    fi
    
    # Basic YAML syntax check
    if ! python3 -c "
import yaml
import sys
try:
    with open('.github/workflows/gpt-integration.yml', 'r') as f:
        yaml.safe_load(f)
    print('  ✅ Valid YAML syntax')
except Exception as e:
    print(f'  ❌ YAML syntax error: {e}')
    sys.exit(1)
" 2>/dev/null; then
        echo "  ❌ YAML syntax check failed"
        return 1
    fi
    
    # Check required sections exist
    if ! grep -q "name: GPT Integration Tests" .github/workflows/gpt-integration.yml; then
        echo "  ❌ Missing workflow name"
        return 1
    fi
    
    if ! grep -q "cron:" .github/workflows/gpt-integration.yml; then
        echo "  ❌ Missing schedule trigger"
        return 1
    fi
    
    if ! grep -q "No Slack webhook configured" .github/workflows/gpt-integration.yml; then
        echo "  ❌ Missing optional Slack notification handling"
        return 1
    fi
    
    echo "  ✅ Workflow structure validated"
    return 0
}

# Run all tests
echo -e "${BLUE}Phase 1: Schema and Workflow Validation${NC}"
echo "========================================"
run_test "Schema Validation" "test_schema_validation"
run_test "Workflow Syntax" "test_workflow_syntax"

echo -e "${BLUE}Phase 2: API Endpoint Testing${NC}"
echo "============================="
run_test "Cold Performance" "test_cold_performance"
run_test "Warm Performance" "test_warm_performance"
run_test "Auth Error Handling" "test_auth_error"

# Cleanup
rm -f /tmp/ci_test_*.json

# Final results
echo -e "${BLUE}📊 Test Results${NC}"
echo "==============="
echo "Tests passed: $TESTS_PASSED/$TOTAL_TESTS"

if [ $TESTS_PASSED -eq $TOTAL_TESTS ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED${NC}"
    echo ""
    echo -e "${GREEN}✅ GPT-006 CI workflow is ready for production${NC}"
    echo ""
    echo "The workflow will:"
    echo "  • Run daily at 9 AM UTC"
    echo "  • Test trades export endpoint"
    echo "  • Validate performance thresholds"
    echo "  • Send Slack alerts on failures"
    echo "  • Validate schemas against GPT-002"
    echo ""
    echo "Next steps:"
    echo "  1. Ensure SLACK_WEBHOOK_URL secret is set in GitHub"
    echo "  2. Monitor first scheduled run tomorrow"
    echo "  3. Adjust performance thresholds if needed"
    exit 0
else
    echo -e "${RED}❌ Some tests failed - CI workflow needs fixes${NC}"
    echo ""
    echo "Please address the failed tests before marking GPT-006 complete."
    exit 1
fi 