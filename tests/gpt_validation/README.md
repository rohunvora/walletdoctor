# GPT Action Validation Harness

This harness validates that GPT-4 can accurately process WalletDoctor P6 position data and calculate unrealized P&L within acceptable tolerances.

## Quick Start

```bash
# Install dependencies
pip install openai python-dotenv pytest

# Run all validation tests in STRICT mode (default)
python -m tests.gpt_validation.test_runner

# Run with mock data (for offline development)
python -m tests.gpt_validation.test_runner --use-mock

# Run only tests that don't require network
pytest -m "not requires_network" tests/gpt_validation/

# Run specific fixture
python -m tests.gpt_validation.test_runner --fixture simple_portfolio.json
```

## Strict Mode (Default)

**As of WAL-613, strict mode is the default behavior:**

- Tests run against real API endpoints
- Network failures cause tests to fail with non-zero exit status
- HTTP status codes and errors are logged
- Mock data is NEVER used unless explicitly requested

This ensures CI catches real issues like:
- Missing or invalid API keys
- Rate limiting
- Service outages
- Configuration errors

## Mock Mode (Opt-in)

To use mock data for offline development:

```bash
# Enable mock mode explicitly
pytest tests/gpt_validation/test_runner.py --use-mock

# Or set environment variable
USE_MOCK=true pytest tests/gpt_validation/
```

**Important:** Mock mode should only be used for local development when working offline.

## Configuration

Create `.env` file with:
```
OPENAI_API_KEY=sk-...
# API endpoint configuration
API_BASE_URL=https://walletdoctor.app
API_KEY=wd_...

# Optional: Skip integration tests
SKIP_INTEGRATION_TESTS=false
```

## Directory Structure

```
tests/gpt_validation/
├── README.md                   # This file
├── __init__.py
├── test_runner.py             # Main test execution
├── validator.py               # Output validation logic
├── helius_mock.py             # Optional mock for unit tests
├── pytest.ini                 # Pytest configuration
├── fixtures/                  # Test data
│   ├── small_wallet_normal.json
│   ├── small_wallet_stale_prices.json
│   ├── small_wallet_empty.json
│   └── small_wallet_estimated_prices.json
└── prompts/                   # GPT system prompts (if needed)
    └── calculate_unrealized_pnl.txt
```

## Fixture Format

Each fixture contains input data and expected outputs:

```json
{
  "description": "Simple 3-position portfolio",
  "input": {
    "schema_version": "1.1",
    "wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
    "positions": [...],
    "price_sources": {...}
  },
  "expected": {
    "total_unrealized_pnl_usd": "325.40",
    "total_value_usd": "1250.75",
    "position_calculations": {
      "3JoVBi:DezXAZ:1706438400": {
        "unrealized_pnl_usd": "6.00",
        "unrealized_pnl_pct": "23.53",
        "current_value_usd": "31.50"
      }
    }
  },
  "tolerance": 0.005  // Optional: Override default ±0.5%
}
```

## Running Tests

### Local Development

```bash
# Run with real API (strict mode)
pytest tests/gpt_validation/test_runner.py -v

# Run offline with mocks
pytest tests/gpt_validation/test_runner.py --use-mock

# Skip network tests
pytest -m "not requires_network" tests/gpt_validation/

# Generate HTML report
pytest tests/gpt_validation/test_runner.py --html=report.html
```

### CI Integration

Tests run in strict mode by default:

```yaml
# .github/workflows/gpt-validation.yml
name: GPT Validation
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - name: Run GPT validation tests (strict mode)
        run: pytest tests/gpt_validation/test_runner.py
        env:
          API_KEY: ${{ secrets.WD_API_KEY }}
          API_BASE_URL: https://walletdoctor.app
      - uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: test-logs
          path: |
            *.log
            pytest.log
```

## Validation Logic

The validator checks:

1. **Total unrealized P&L** - Must be within ±0.5% of expected
2. **Per-position calculations** - Each position's P&L within tolerance
3. **Edge cases handled** - Nulls, decimals, stale prices
4. **Calculation consistency** - Sum of positions equals total

### Tolerance Levels

- Monetary values: ±0.5% (default)
- Percentages: ±1% absolute
- Counts/integers: Exact match

## Adding New Fixtures

1. Create JSON file in `fixtures/` directory
2. Include realistic test scenario
3. Calculate expected values manually
4. Document any special cases in description
5. Run validator to ensure it passes

## Troubleshooting

### Common Issues

**API Rate Limits**
- Check logs for HTTP 429 status
- Reduce test frequency or add delays
- Contact support for higher limits

**Network Failures in CI**
- Tests will fail with clear error messages
- Check CI logs for HTTP status and traceback
- Ensure API_KEY is set in CI secrets

**Calculation Differences**
- Check decimal precision in prompts
- Verify token decimals are correct
- Look for rounding differences

### Debug Mode

```bash
# Full debug output
python -m tests.gpt_validation.test_runner --debug

# Save API calls for analysis
python -m tests.gpt_validation.test_runner --save-api-calls calls.jsonl

# Test with increased timeout
pytest tests/gpt_validation/ --timeout=120
```

## Performance Benchmarks

Target metrics:
- Validation time: < 30s per fixture
- API cost: < $0.20 per fixture
- Accuracy: 100% pass rate with ±0.5% tolerance
- Reliability: < 1% false positive rate

## Contributing

1. New fixtures should cover unique scenarios
2. Always test in strict mode before committing
3. Document any tolerance adjustments with rationale
4. Keep fixtures under 50 positions for performance
5. Never commit with --use-mock in CI configuration 