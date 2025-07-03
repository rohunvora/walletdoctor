#!/bin/bash

# Test SSE streaming performance through Railway proxy
# GPT-005: Validate if >90% events arrive <25s (exit criteria)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RAILWAY_URL="${RAILWAY_URL:-https://walletdoctor-production.up.railway.app}"
TEST_WALLET="${TEST_WALLET:-8kGfFmGfFi8tBvbX6yy8Z4pvFUgbGCnBCbqKnUhcKh5h}"  # Known small wallet
API_KEY="${API_KEY:-wd_test_key_1234567890123456789012345}"
OUTPUT_FILE="tmp/sse_railway_test_$(date +%s).json"
TIMEOUT_THRESHOLD=25  # seconds for event arrival
SUCCESS_THRESHOLD=90  # percentage of events that must arrive on time

echo -e "${BLUE}🚀 GPT-005: SSE Railway Streaming Test${NC}"
echo "======================================="
echo "Railway URL: $RAILWAY_URL"
echo "Test Wallet: $TEST_WALLET"
echo "Timeout Threshold: ${TIMEOUT_THRESHOLD}s"
echo "Success Threshold: ${SUCCESS_THRESHOLD}%"
echo ""

# Ensure tmp directory exists
mkdir -p tmp

# Test function to analyze SSE stream
test_sse_streaming() {
    local wallet=$1
    local test_name=$2
    
    echo -e "${YELLOW}Testing: $test_name${NC}"
    
    # Start timestamp
    local start_time=$(date +%s.%N)
    local event_count=0
    local on_time_events=0
    local total_events=0
    local first_event_time=""
    local last_event_time=""
    local connection_established=false
    
    # Create temporary file for this test
    local temp_file="tmp/sse_test_${test_name}_$(date +%s).log"
    
    # Start SSE connection with timeout
    timeout 60 curl -s -N \
        -H "Accept: text/event-stream" \
        -H "X-API-Key: $API_KEY" \
        -H "Cache-Control: no-cache" \
        "$RAILWAY_URL/v4/wallet/$wallet/stream" \
        2>/dev/null | while IFS= read -r line; do
            
            local current_time=$(date +%s.%N)
            
            # Log raw data
            echo "$current_time|$line" >> "$temp_file"
            
            # Parse SSE events
            if [[ "$line" =~ ^event:\ (.+)$ ]]; then
                local event_type="${BASH_REMATCH[1]}"
                
                # Read next line for data
                IFS= read -r data_line
                echo "$current_time|$data_line" >> "$temp_file"
                
                if [[ "$data_line" =~ ^data:\ (.+)$ ]]; then
                    local event_data="${BASH_REMATCH[1]}"
                    
                    # Track events
                    ((total_events++))
                    
                    # Check timing
                    local elapsed=$(echo "$current_time - $start_time" | bc -l)
                    
                    # First event timing
                    if [[ -z "$first_event_time" ]]; then
                        first_event_time=$elapsed
                        connection_established=true
                    fi
                    
                    # Count on-time events
                    if (( $(echo "$elapsed <= $TIMEOUT_THRESHOLD" | bc -l) )); then
                        ((on_time_events++))
                    fi
                    
                    last_event_time=$elapsed
                    
                    echo "  Event #$total_events: $event_type at ${elapsed}s"
                    
                    # Stop conditions
                    if [[ "$event_type" == "complete" ]] || [[ "$event_type" == "error" ]]; then
                        break
                    fi
                    
                    # Safety stop after 100 events
                    if [[ $total_events -ge 100 ]]; then
                        echo "  Stopping after 100 events for safety"
                        break
                    fi
                fi
            fi
        done
    
    # Analyze results
    if [[ $total_events -gt 0 ]]; then
        local success_rate=$(echo "scale=2; $on_time_events * 100 / $total_events" | bc -l)
        
        echo "  📊 Results:"
        echo "    Total events: $total_events"
        echo "    On-time events: $on_time_events"
        echo "    Success rate: ${success_rate}%"
        echo "    First event: ${first_event_time}s"
        echo "    Last event: ${last_event_time}s"
        
        # Write detailed results to JSON
        cat > "${temp_file}.json" << EOF
{
  "test_name": "$test_name",
  "wallet": "$wallet",
  "railway_url": "$RAILWAY_URL",
  "start_time": "$start_time",
  "total_events": $total_events,
  "on_time_events": $on_time_events,
  "success_rate": $success_rate,
  "first_event_time": $first_event_time,
  "last_event_time": $last_event_time,
  "timeout_threshold": $TIMEOUT_THRESHOLD,
  "success_threshold": $SUCCESS_THRESHOLD,
  "passed": $(if (( $(echo "$success_rate >= $SUCCESS_THRESHOLD" | bc -l) )); then echo "true"; else echo "false"; fi),
  "connection_established": $connection_established
}
EOF
        
        # Check if test passed
        if (( $(echo "$success_rate >= $SUCCESS_THRESHOLD" | bc -l) )); then
            echo -e "    ${GREEN}✅ PASS: Success rate ${success_rate}% >= ${SUCCESS_THRESHOLD}%${NC}"
            return 0
        else
            echo -e "    ${RED}❌ FAIL: Success rate ${success_rate}% < ${SUCCESS_THRESHOLD}%${NC}"
            return 1
        fi
    else
        echo -e "    ${RED}❌ FAIL: No events received${NC}"
        cat > "${temp_file}.json" << EOF
{
  "test_name": "$test_name",
  "wallet": "$wallet",
  "railway_url": "$RAILWAY_URL",
  "error": "No events received",
  "connection_established": false,
  "passed": false
}
EOF
        return 1
    fi
}

# Test Railway proxy behavior
test_railway_proxy() {
    echo -e "${YELLOW}Testing Railway proxy behavior...${NC}"
    
    # Test connection establishment time
    echo "  Testing connection time..."
    local connect_start=$(date +%s.%N)
    
    local http_status=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "X-API-Key: $API_KEY" \
        "$RAILWAY_URL/health")
    
    local connect_time=$(echo "$(date +%s.%N) - $connect_start" | bc -l)
    
    echo "    HTTP Status: $http_status"
    echo "    Connection time: ${connect_time}s"
    
    if [[ "$http_status" == "200" ]]; then
        echo -e "    ${GREEN}✅ Railway proxy accessible${NC}"
    else
        echo -e "    ${RED}❌ Railway proxy issue (HTTP $http_status)${NC}"
        return 1
    fi
    
    # Test if Railway buffers SSE
    echo "  Testing Railway SSE buffering..."
    local buffer_test_start=$(date +%s.%N)
    
    # Get first SSE event timing
    local first_chunk_time=$(timeout 10 curl -s -N \
        -H "Accept: text/event-stream" \
        -H "X-API-Key: $API_KEY" \
        "$RAILWAY_URL/v4/wallet/$TEST_WALLET/stream" \
        2>/dev/null | head -n 1 | while read -r line; do
            echo "$(date +%s.%N)"
            break
        done)
    
    if [[ -n "$first_chunk_time" ]]; then
        local buffer_delay=$(echo "$first_chunk_time - $buffer_test_start" | bc -l)
        echo "    First chunk delay: ${buffer_delay}s"
        
        if (( $(echo "$buffer_delay <= 2.0" | bc -l) )); then
            echo -e "    ${GREEN}✅ Railway not significantly buffering SSE${NC}"
        else
            echo -e "    ${YELLOW}⚠️ Railway may be buffering (${buffer_delay}s delay)${NC}"
        fi
    else
        echo -e "    ${RED}❌ No SSE data received${NC}"
        return 1
    fi
}

# Main test execution
main() {
    echo -e "${BLUE}Phase 1: Railway Proxy Validation${NC}"
    echo "=================================="
    
    if ! test_railway_proxy; then
        echo -e "${RED}❌ Railway proxy tests failed - SSE likely not viable${NC}"
        echo ""
        echo -e "${YELLOW}📋 RECOMMENDATION: Punt to WebSocket (PAG-002)${NC}"
        exit 1
    fi
    
    echo ""
    echo -e "${BLUE}Phase 2: SSE Performance Tests${NC}"
    echo "==============================="
    
    local tests_passed=0
    local total_tests=0
    
    # Test 1: Small wallet (fast)
    ((total_tests++))
    if test_sse_streaming "$TEST_WALLET" "small_wallet"; then
        ((tests_passed++))
    fi
    
    echo ""
    
    # Test 2: Medium wallet (more stress)
    ((total_tests++))
    if test_sse_streaming "34zYDgjy5Bd3EhwXGgN9EacjhGJMTBrKFoJg8vJx3C5n" "medium_wallet"; then
        ((tests_passed++))
    fi
    
    echo ""
    
    # Test 3: Connection under load (multiple concurrent)
    echo -e "${YELLOW}Testing: concurrent_streams${NC}"
    local concurrent_results=()
    
    for i in {1..3}; do
        {
            if test_sse_streaming "$TEST_WALLET" "concurrent_$i"; then
                echo "1" > "tmp/concurrent_$i.result"
            else
                echo "0" > "tmp/concurrent_$i.result"
            fi
        } &
    done
    
    wait  # Wait for all background tests
    
    local concurrent_passed=0
    for i in {1..3}; do
        if [[ -f "tmp/concurrent_$i.result" ]]; then
            concurrent_passed=$((concurrent_passed + $(cat "tmp/concurrent_$i.result")))
            rm -f "tmp/concurrent_$i.result"
        fi
    done
    
    ((total_tests++))
    if [[ $concurrent_passed -ge 2 ]]; then
        echo -e "  ${GREEN}✅ PASS: $concurrent_passed/3 concurrent streams succeeded${NC}"
        ((tests_passed++))
    else
        echo -e "  ${RED}❌ FAIL: Only $concurrent_passed/3 concurrent streams succeeded${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}📊 Final Results${NC}"
    echo "================="
    echo "Tests passed: $tests_passed/$total_tests"
    
    local overall_success_rate=$(echo "scale=2; $tests_passed * 100 / $total_tests" | bc -l)
    echo "Overall success rate: ${overall_success_rate}%"
    
    # Generate final report
    cat > "$OUTPUT_FILE" << EOF
{
  "test_timestamp": "$(date -Iseconds)",
  "railway_url": "$RAILWAY_URL",
  "test_wallet": "$TEST_WALLET",
  "timeout_threshold": $TIMEOUT_THRESHOLD,
  "success_threshold": $SUCCESS_THRESHOLD,
  "tests_passed": $tests_passed,
  "total_tests": $total_tests,
  "overall_success_rate": $overall_success_rate,
  "exit_criteria_met": $(if (( $(echo "$overall_success_rate >= 90" | bc -l) )); then echo "true"; else echo "false"; fi),
  "recommendation": "$(if (( $(echo "$overall_success_rate >= 90" | bc -l) )); then echo "PROCEED with SSE"; else echo "PUNT to WebSocket (PAG-002)"; fi)"
}
EOF
    
    echo "Detailed results: $OUTPUT_FILE"
    echo ""
    
    # Final recommendation
    if (( $(echo "$overall_success_rate >= 90" | bc -l) )); then
        echo -e "${GREEN}🎉 SUCCESS: SSE streaming viable through Railway${NC}"
        echo -e "${GREEN}✅ RECOMMENDATION: Proceed with SSE implementation${NC}"
        echo ""
        echo "  • >90% events arriving <25s ✅"
        echo "  • Railway proxy compatible ✅"
        echo "  • Concurrent connections working ✅"
        exit 0
    else
        echo -e "${RED}❌ FAILURE: SSE streaming not reliable through Railway${NC}"
        echo -e "${YELLOW}📋 RECOMMENDATION: Punt to WebSocket (PAG-002)${NC}"
        echo ""
        echo "  • Performance below 90% threshold"
        echo "  • Railway 30s timeout risk"
        echo "  • Consider alternative: WebSocket + streaming"
        exit 1
    fi
}

# Run tests
main "$@" 