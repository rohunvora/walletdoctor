# GPT Action Validation Harness

This harness validates that GPT-4 can accurately process WalletDoctor P6 position data and calculate unrealized P&L within acceptable tolerances.

## Quick Start

```bash
# Install dependencies
pip install openai python-dotenv pytest

# Run all validation tests
python -m tests.gpt_validation.test_runner

# Run specific fixture
python -m tests.gpt_validation.test_runner --fixture simple_portfolio.json

# Dry run (no API calls)
python -m tests.gpt_validation.test_runner --dry-run
```

## Configuration

Create `.env` file with:
```
OPENAI_API_KEY=sk-...
# Or for Azure OpenAI:
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_KEY=...
AZURE_OPENAI_VERSION=2024-02-15-preview
```

## Directory Structure

```
tests/gpt_validation/
├── README.md                   # This file
├── __init__.py
├── test_runner.py             # Main test execution
├── validator.py               # Output validation logic
├── fixtures/                  # Test data
│   ├── simple_portfolio.json
│   ├── complex_portfolio.json
│   ├── edge_cases.json
│   ├── stale_prices.json
│   └── reopened_positions.json
└── prompts/                   # GPT system prompts
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
# Run with verbose output
python -m tests.gpt_validation.test_runner -v

# Generate HTML report
python -m tests.gpt_validation.test_runner --report output.html

# Test specific GPT model
python -m tests.gpt_validation.test_runner --model gpt-4-0125-preview
```

### CI Integration

Tests run nightly via GitHub Actions:

```yaml
# .github/workflows/gpt-validation.yml
name: GPT Validation
on:
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m tests.gpt_validation.test_runner
      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: validation-report
          path: validation-report.html
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
- Add delays between tests: `--delay 2`
- Use cheaper model for development: `--model gpt-3.5-turbo`

**Calculation Differences**
- Check decimal precision in prompts
- Verify token decimals are correct
- Look for rounding differences

**Prompt Issues**
- Test prompts in playground first
- Use `--debug` to see full API calls
- Check few-shot examples match schema version

### Debug Mode

```bash
# Full debug output
python -m tests.gpt_validation.test_runner --debug

# Save API calls for analysis
python -m tests.gpt_validation.test_runner --save-api-calls calls.jsonl
```

## Performance Benchmarks

Target metrics:
- Validation time: < 30s per fixture
- API cost: < $0.20 per fixture
- Accuracy: 100% pass rate with ±0.5% tolerance
- Reliability: < 1% false positive rate

## Contributing

1. New fixtures should cover unique scenarios
2. Update prompts carefully - test all fixtures after changes
3. Document any tolerance adjustments with rationale
4. Keep fixtures under 50 positions for performance 