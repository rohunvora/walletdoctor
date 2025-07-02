# WAL-613: Strict Mode Implementation Summary

## Overview

Implemented strict mode as the default behavior for the GPT export validation harness. Tests now fail with non-zero exit status when real API calls fail, ensuring CI catches actual issues instead of silently using mock data.

## Key Changes

### 1. Default Behavior: Strict Mode ✅

**Before**: Tests would silently fall back to mock data on API failures
**After**: Tests fail immediately with clear error messages and non-zero exit status

```python
# Old behavior (removed)
except requests.exceptions.RequestException as e:
    pytest.skip(f"API not available: {e}")

# New behavior (strict mode)
except requests.exceptions.RequestException as e:
    logger.error(f"API request failed: {e}")
    if use_mock:
        pytest.skip(f"API not available and mock mode enabled: {e}")
    else:
        # In strict mode, fail the test
        pytest.fail(f"API request failed in strict mode: {e}")
```

### 2. Mock Mode: Opt-in Only

Mock mode is now explicitly opt-in via `--use-mock` flag:

```bash
# Default (strict mode) - will fail if API unavailable
pytest tests/gpt_validation/test_runner.py

# Mock mode - for offline development only
pytest tests/gpt_validation/test_runner.py --use-mock
```

### 3. Enhanced Error Logging

- HTTP status codes are logged
- Full error tracebacks are captured
- Network timeouts are clearly reported
- Rate limiting (429) is detected

```python
# Log the HTTP status
logger.info(f"HTTP Status: {response.status_code}")

if response.status_code != 200:
    logger.error(f"API request failed: {response.status_code} - {response.text}")
    pytest.fail(f"API returned {response.status_code}: {response.text}")
```

### 4. Network Test Marking

Tests requiring network access are now properly marked:

```python
@pytest.mark.requires_network
@pytest.mark.integration
def test_live_api_small_wallet(self, request):
    """Test against live API with small wallet"""
```

For offline development:
```bash
# Skip network tests
pytest -m "not requires_network" tests/gpt_validation/
```

### 5. CI Configuration

CI runs in strict mode by default - no changes needed to existing workflows:

```yaml
- name: Run GPT validation tests (strict mode)
  run: pytest tests/gpt_validation/test_runner.py
  env:
    API_KEY: ${{ secrets.WD_API_KEY }}
    API_BASE_URL: https://walletdoctor.app
```

## Files Modified

1. **tests/gpt_validation/test_runner.py**
   - Added `--use-mock` option (default=False)
   - Updated `mock_api_response()` to require explicit opt-in
   - Enhanced `test_live_api_small_wallet()` with proper error handling
   - Added logging configuration
   - Added `pytest_addoption()` for custom CLI options

2. **tests/gpt_validation/pytest.ini**
   - Created pytest configuration
   - Defined markers: `integration`, `requires_network`
   - Set strict marker enforcement
   - Enabled logging

3. **tests/gpt_validation/README.md**
   - Documented strict mode as default
   - Added mock mode usage instructions
   - Updated CI configuration examples
   - Added troubleshooting for network failures

4. **scripts/test_railway_performance.py**
   - Created performance testing script
   - Captures detailed timing breakdown
   - Validates against 30s target for cold cache
   - Generates JSON report

## Test Results

✅ All schema validation tests pass without requiring network
✅ Mock mode properly throws error when not explicitly enabled
✅ Network tests properly marked and can be skipped for offline work

## Benefits

1. **CI Reliability**: Real failures are caught immediately
2. **Clear Debugging**: HTTP status and errors are logged
3. **Explicit Behavior**: No hidden fallbacks to mock data
4. **Developer Friendly**: Can still work offline with `--use-mock`

## Next Steps

1. Deploy to Railway and run performance tests
2. If performance > 30s, implement suggested optimizations:
   - Increase Gunicorn workers to 2
   - Set HELIUS_PARALLEL_REQUESTS=5
   - Verify environment variables have no quotes
3. Update documentation once performance targets are met

## Usage Examples

```bash
# CI/Production (strict mode)
pytest tests/gpt_validation/test_runner.py

# Local development with real API
pytest tests/gpt_validation/test_runner.py -v

# Offline development
pytest tests/gpt_validation/test_runner.py --use-mock

# Skip network tests
pytest -m "not requires_network" tests/gpt_validation/

# Test Railway performance
python3 scripts/test_railway_performance.py
``` 