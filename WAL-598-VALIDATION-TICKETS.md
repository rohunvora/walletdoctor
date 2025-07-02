# WAL-598 Series: GPT Action Validation Harness

## Overview
Create a headless validation harness to ensure GPT Actions can correctly process P6 position data and calculate unrealized P&L with acceptable accuracy.

---

## WAL-598a: Golden JSON Fixtures (2h)

**Objective**: Create test data representing various portfolio scenarios

**Acceptance Criteria:**
- [ ] Create `tests/fixtures/gpt_validation/` directory structure
- [ ] Generate at least 5 golden JSON fixtures:
  - `simple_portfolio.json` - 3 positions, all profitable
  - `complex_portfolio.json` - 20+ positions, mixed P&L
  - `edge_cases.json` - Airdrops, dust, high-decimal tokens
  - `stale_prices.json` - Various price confidence levels
  - `reopened_positions.json` - Same token closed and reopened
- [ ] Each fixture includes expected calculations:
  ```json
  {
    "input": { /* P6 export format */ },
    "expected": {
      "total_unrealized_pnl_usd": "325.40",
      "position_calculations": {
        "position_id": {
          "unrealized_pnl_usd": "6.00",
          "current_value_usd": "31.50"
        }
      }
    }
  }
  ```
- [ ] Document fixture generation process in README

**Dependencies**: None

---

## WAL-598b: ChatCompletion Test Runner (3h)

**Objective**: Implement GPT API calls to process position data

**Acceptance Criteria:**
- [ ] Create `tests/gpt_validation/test_runner.py`
- [ ] Implement ChatCompletion call with JSON mode:
  ```python
  async def test_gpt_calculations(fixture_path: str) -> Dict:
      system_prompt = load_prompt("calculate_unrealized_pnl.txt")
      user_data = load_fixture(fixture_path)["input"]
      
      response = await openai.ChatCompletion.create(
          model="gpt-4-turbo-preview",
          response_format={"type": "json_object"},
          messages=[
              {"role": "system", "content": system_prompt},
              {"role": "user", "content": json.dumps(user_data)}
          ]
      )
      return json.loads(response.choices[0].message.content)
  ```
- [ ] Handle API errors and retries
- [ ] Support both OpenAI and Azure OpenAI endpoints
- [ ] Add --dry-run mode that skips API calls
- [ ] Log all API calls and responses for debugging

**Dependencies**: WAL-598a (fixtures needed)

---

## WAL-598c: Diff Checker & CI Integration (3h)

**Objective**: Validate GPT outputs and integrate with CI

**Acceptance Criteria:**
- [ ] Create `tests/gpt_validation/validator.py` with:
  ```python
  def validate_calculation(expected: Dict, actual: Dict, tolerance: float = 0.005):
      """Compare with ±0.5% tolerance for monetary values"""
      # Check total unrealized P&L
      expected_total = Decimal(expected["total_unrealized_pnl_usd"])
      actual_total = Decimal(actual["total_unrealized_pnl_usd"])
      
      diff_pct = abs((actual_total - expected_total) / expected_total)
      assert diff_pct <= tolerance, f"Total P&L diff {diff_pct:.2%} exceeds {tolerance:.1%}"
      
      # Check each position...
  ```
- [ ] Generate detailed diff reports showing:
  - Pass/fail for each calculation
  - Percentage differences
  - Which positions exceeded tolerance
- [ ] Create GitHub Action workflow:
  ```yaml
  name: GPT Validation
  on:
    schedule:
      - cron: '0 2 * * *'  # Nightly at 2 AM UTC
    workflow_dispatch:  # Manual trigger
  ```
- [ ] Send Slack/email alerts on failures
- [ ] Generate HTML report with results

**Dependencies**: WAL-598b (test runner needed)

---

## WAL-598d: System Prompt Engineering (2h)

**Objective**: Create optimized prompts for accurate calculations

**Acceptance Criteria:**
- [ ] Create `tests/gpt_validation/prompts/calculate_unrealized_pnl.txt`
- [ ] Prompt must handle:
  - Decimal string parsing
  - Token decimal scaling (using decimals field)
  - Null/missing value handling
  - Stale price warnings
- [ ] Include few-shot examples in prompt
- [ ] Test prompt variations and document best performer
- [ ] Version prompts with changelog

**Dependencies**: WAL-598a (use fixtures for examples)

---

## Implementation Order
1. WAL-598a - Create fixtures (can start immediately)
2. WAL-598d - Engineer prompts (can start immediately) 
3. WAL-598b - Build test runner
4. WAL-598c - Add validation and CI

## Success Metrics
- All golden fixtures pass with < 0.5% deviation
- Nightly CI runs complete in < 5 minutes
- Zero false positives in 30-day period
- GPT costs < $1 per validation run 