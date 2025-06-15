# WalletDoctor Insight Engine 2.0

A refactored insight generation system that delivers "soul-piercing clarity" through deterministic analysis and focused narrative.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│ Raw Data        │ --> │ Features     │ --> │ Insights    │
│ (Pandas/DuckDB) │     │ (Pure Funcs) │     │ (Rules)     │
└─────────────────┘     └──────────────┘     └─────────────┘
                                                     |
                                                     v
                                              ┌─────────────┐
                                              │ LLM         │
                                              │ (Narrative) │
                                              └─────────────┘
```

## Key Components

### 1. Features (`features/behaviour.py`)
Pure functions that extract behavioral signals:
- `fee_burn()` - Total SOL burned in fees
- `premature_exits()` - % of winners sold too early  
- `revenge_trading_risk()` - % of losses after losses
- 20+ other behavioral metrics

### 2. Insights (`insights/`)
- `rules.yaml` - Declarative rules mapping metrics to insights
- `generator.py` - Ranks and renders top insights

### 3. LLM (`llm/prompt.py`)
Minimal LLM usage - only for narrative weaving, not analysis.

## Integration Example

```python
from walletdoctor.features import behaviour
from walletdoctor.insights import generate_full_report
from walletdoctor.llm import make_messages

# 1. Convert your data to Polars
trades_df = convert_to_polars(your_pandas_df)

# 2. Compute metrics
metrics = {
    'fee_burn': behaviour.fee_burn(trades_df),
    'win_rate': behaviour.win_rate(trades_df),
    # ... etc
}

# 3. Generate insights
report = generate_full_report(metrics)

# 4. Get narrative (if using LLM)
messages = make_messages(report['header'], report['insights'])
narrative = your_openai_client.chat.completions.create(...)
```

## Benefits

1. **Deterministic** - Metrics are pure functions, testable and reproducible
2. **Tunable** - Adjust thresholds and weights in YAML without code changes
3. **Focused** - Only surfaces insights that matter (threshold-based filtering)
4. **Maintainable** - Clear separation between logic, rules, and presentation

## Customization

### Adding New Metrics

1. Add function to `features/behaviour.py`:
```python
def new_metric(df: pl.DataFrame) -> float:
    """Description of what this measures."""
    # Your logic here
    return float_value
```

2. Add rule to `insights/rules.yaml`:
```yaml
new_metric:
  threshold: 42
  template: "Your insight: {value}"
  weight: 0.7
```

### Adjusting Sensitivity

Edit thresholds in `rules.yaml` to make insights more/less sensitive:
```yaml
fee_burn:
  threshold: 25  # Lower = more sensitive
```

## Migration Path

1. Install dependencies: `pip install polars pyyaml`
2. Copy `src/walletdoctor/` to your project
3. See `example_integration.py` for drop-in replacement
4. Gradually migrate from old system

## Output Example

```
┌─ Wallet Doctor — 12 Jun 2025 ─┐
| Net P&L: +342 SOL  (+18.4%)   |
| Win rate: 39% | Trades: 271    |
└───────────────────────────────┘

You burned **113 SOL** in fees. That's enough to erase four 
average winning trades. But the real leak isn't fees—it's 
impatience. **68%** of your winners were cut within 15 minutes. 
Those same trades would have added +9% P&L with just one hour 
of patience.

Every large loss followed the same pattern: revenge trading 
within 30 minutes of a stop-loss. The market doesn't care 
about your need to "get even."

Fix the fees first. Use limit orders. That's $100+ back in 
your pocket every week.
```

Clean. Focused. Actionable. 