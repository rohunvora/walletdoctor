# GPT-005: SSE Streaming Spike Guide

## Overview

GPT-005 validates whether Server-Sent Events (SSE) streaming is viable through Railway's proxy infrastructure for real-time wallet analysis. This spike is time-boxed to 6 hours with clear exit criteria.

## Exit Criteria

✅ **PROCEED**: If >90% of events arrive within 25 seconds  
❌ **PUNT**: If performance is below threshold → punt to WebSocket (PAG-002)

## Test Suite

### 1. Bash Test Script (`scripts/test_sse_railway.sh`)

**Fast, lightweight testing for quick validation:**

```bash
# Basic usage
./scripts/test_sse_railway.sh

# With custom settings
RAILWAY_URL="https://your-app.railway.app" \
API_KEY="wd_your_key" \
./scripts/test_sse_railway.sh
```

**Features:**
- Railway proxy connection validation
- SSE buffering detection  
- Event timing analysis
- Concurrent stream testing
- JSON result output

### 2. Python Test Client (`scripts/test_sse_python.py`)

**Precise timing analysis and detailed reporting:**

```bash
# Basic usage
python scripts/test_sse_python.py

# With custom parameters
python scripts/test_sse_python.py \
  --url "https://your-app.railway.app" \
  --api-key "wd_your_key" \
  --timeout 25 \
  --success-rate 90 \
  --output "tmp/sse_results.json"
```

**Features:**
- Microsecond-precision timing
- Detailed event analysis
- Concurrent connection testing
- Comprehensive JSON reports
- Error classification

## Test Scenarios

### Phase 1: Railway Proxy Validation
- Connection speed testing
- SSE buffering detection
- HTTP status validation

### Phase 2: Performance Testing
1. **Small Wallet Test** (< 1000 trades)
   - Fast completion for baseline performance
   - Expected: Complete in <5 seconds

2. **Medium Wallet Test** (1000-5000 trades)
   - Stress test for sustained streaming
   - Expected: Complete in 10-20 seconds

3. **Concurrent Streams Test**
   - 3 simultaneous connections
   - Tests Railway proxy limits
   - Expected: 2/3 streams succeed

### Phase 3: Analysis
- Event timing distribution
- Success rate calculation
- Failure pattern analysis

## Railway-Specific Considerations

### 30-Second Timeout Limit
Railway enforces a 30-second timeout for HTTP requests:
- **Risk**: Long-running analyses may timeout
- **Mitigation**: 25-second threshold provides safety margin
- **Alternative**: WebSocket connections don't have this limit

### Proxy Buffering
Railway may buffer SSE responses:
- **Detection**: Measure first-event latency
- **Impact**: Delays in real-time feedback
- **Threshold**: >2s delay indicates problematic buffering

### Connection Pooling
Railway load balances across multiple instances:
- **Impact**: Concurrent connections may hit different instances
- **Testing**: Multiple parallel streams validate behavior

## Expected Results

### Success Scenario (Proceed with SSE)
```json
{
  "exit_criteria_met": true,
  "overall_success_rate": 95.0,
  "recommendation": "PROCEED with SSE",
  "summary": {
    "avg_first_event_time": 0.8,
    "concurrent_success": "3/3",
    "railway_buffering": false
  }
}
```

### Failure Scenario (Punt to WebSocket)
```json
{
  "exit_criteria_met": false,
  "overall_success_rate": 75.0,
  "recommendation": "PUNT to WebSocket (PAG-002)",
  "issues": [
    "Railway buffering detected (3.2s delay)",
    "25% timeout rate on medium wallets",
    "Concurrent streams failing 2/3"
  ]
}
```

## Integration Examples

### Using Test Results in CI

```bash
# Run in CI pipeline
if ./scripts/test_sse_railway.sh; then
  echo "SSE viable - proceeding with implementation"
  # Enable SSE features
else
  echo "SSE not viable - falling back to WebSocket"
  # Disable SSE, enable WebSocket plan
fi
```

### Monitoring in Production

```python
# Based on test patterns
import asyncio
from scripts.test_sse_python import SSEPerformanceTester

async def monitor_sse_performance():
    tester = SSEPerformanceTester(
        railway_url="https://walletdoctor-production.up.railway.app",
        api_key=os.getenv("MONITORING_API_KEY"),
        timeout_threshold=25.0,
        success_threshold=85.0  # Lower threshold for monitoring
    )
    
    result = await tester.test_sse_stream(
        "small_test_wallet", 
        "production_health_check"
    )
    
    if not result.passed:
        # Alert: SSE performance degraded
        send_alert(f"SSE performance: {result.success_rate}%")
```

## Troubleshooting

### Common Issues

**No events received:**
```
Error: Connection timeout
Solution: Check API key, Railway deployment status
```

**High latency:**
```
Issue: First event >5s delay
Cause: Railway cold start or buffering
Action: Warm-up request or consider WebSocket
```

**Concurrent failures:**
```
Issue: Multiple streams timing out
Cause: Railway resource limits
Action: Rate limiting or connection pooling
```

### Debug Mode

```bash
# Enable verbose logging
DEBUG=1 ./scripts/test_sse_railway.sh

# Save raw event logs
python scripts/test_sse_python.py --output tmp/debug_sse.json
# Check tmp/sse_test_*.log files for raw data
```

## Decision Matrix

| Metric | SSE Proceed | SSE Punt | Notes |
|--------|-------------|----------|-------|
| Success Rate | ≥90% | <90% | Core requirement |
| First Event | <2s | >3s | User experience |
| Concurrent Streams | 2/3+ pass | <2/3 pass | Scalability |
| Railway Buffering | <2s delay | >3s delay | Real-time feel |
| Total Duration | <6hr spike | - | Time constraint |

## Next Steps

### If SSE Proceeds
1. Implement production SSE endpoints
2. Add monitoring and alerting
3. Create GPT integration examples
4. Document rate limiting strategy

### If SSE Punted (PAG-002)
1. Design WebSocket architecture
2. Implement connection management
3. Handle reconnection logic
4. Plan progressive data loading

## Files Created

- `scripts/test_sse_railway.sh` - Bash test suite
- `scripts/test_sse_python.py` - Python detailed analysis
- `docs/gpt_action/GPT-005_SSE_SPIKE_GUIDE.md` - This guide
- `tickets/GPT-005.md` - Implementation ticket

## Test Artifacts

Results stored in `tmp/` directory:
- `sse_railway_test_*.json` - Bash test results
- `sse_python_test.json` - Python test results  
- `sse_test_*.log` - Raw event logs
- Performance metrics and timing data 