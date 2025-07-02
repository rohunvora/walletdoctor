# WAL-613: Strict Mode for GPT Export Validation

## Summary

This PR implements strict mode as the default behavior for the GPT export validation harness, ensuring that CI catches real API failures instead of silently falling back to mock data.

## What Changed

### 🔒 Strict Mode by Default
- Tests now fail with non-zero exit status when API calls fail
- Mock data requires explicit `--use-mock` flag
- HTTP status codes and errors are logged for debugging

### 📊 Enhanced Error Reporting
```python
# Before: Silent skip
pytest.skip(f"API not available: {e}")

# After: Explicit failure in strict mode
logger.error(f"API request failed: {e}")
pytest.fail(f"API request failed in strict mode: {e}")
```

### 🏷️ Network Test Marking
- Added `@pytest.mark.requires_network` for tests needing API access
- Developers can work offline: `pytest -m "not requires_network"`

### 🚀 Performance Testing
- Added `scripts/test_railway_performance.py` for deployment validation
- Captures detailed timing breakdown
- Validates against 30s target

## Files Changed

1. `tests/gpt_validation/test_runner.py` - Strict mode implementation
2. `tests/gpt_validation/pytest.ini` - Test configuration
3. `tests/gpt_validation/README.md` - Updated documentation
4. `scripts/test_railway_performance.py` - Performance testing tool
5. `railway-performance-optimizations.md` - Deployment optimization guide

## Testing

✅ All tests pass without network (12 passed, 2 skipped)
✅ Mock mode properly requires explicit flag
✅ Error logging captures HTTP status and traceback

## Usage

```bash
# Default (strict mode) - for CI
pytest tests/gpt_validation/test_runner.py

# Offline development
pytest tests/gpt_validation/test_runner.py --use-mock

# Skip network tests
pytest -m "not requires_network" tests/gpt_validation/
```

## Next Steps

1. Deploy to Railway with optimizations
2. Run performance tests
3. If > 30s, implement background processing

## Benefits

- **CI Reliability**: Real outages are caught immediately
- **Clear Debugging**: HTTP status and errors in logs
- **No Hidden Behavior**: Explicit mock mode only
- **Developer Friendly**: Offline mode still available

## Breaking Changes

None - existing CI workflows continue to work, now with better error detection. 