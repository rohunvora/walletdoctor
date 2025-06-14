# WalletDoctor Technical Design Document
## Data Processing Pipeline (Steps 4-6)

### Table of Contents
1. [Overview](#overview)
2. [Step 4: Data Transformation](#step-4-data-transformation)
3. [Step 5: Analytics & Pattern Detection](#step-5-analytics--pattern-detection)
4. [Step 6: Output Generation](#step-6-output-generation)
5. [Potential Improvements](#potential-improvements)

---

## Executive Summary: Key Algorithms in Plain English

### What Makes WalletDoctor Different

WalletDoctor uses **statistical proof** rather than guesswork to identify trading problems. Here's how:

#### 1. **Position Size Analysis**
- **Question**: "At what dollar amount do you start losing money?"
- **Method**: Group all trades by size ($100-500, $500-1K, etc.) and calculate P&L for each group
- **Discovery**: Most traders have a "sweet spot" where they're profitable and a "danger zone" where they consistently lose
- **Example**: User wins 42% at $100-500 but only 18% at $1K-5K positions

#### 2. **FOMO Detection Algorithm**
- **Question**: "Do quick trades perform worse than patient ones?"
- **Method**: Compare trades held <10 minutes vs >1 hour using bootstrap statistical testing
- **Validation**: Run 1000 random samples to ensure the pattern is real, not luck
- **Example**: Quick trades average -$35 loss, patient trades average +$120 profit (97% confidence)

#### 3. **Behavioral Pattern Recognition**
- **Question**: "Do you hold losers longer than winners?"
- **Method**: Calculate average hold time for profitable vs unprofitable trades
- **Red Flag**: If losers are held 2x+ longer than winners = loss aversion pattern
- **Impact**: Shows exact dollar cost of this behavior

#### 4. **Harsh Truth Generation**
- **Philosophy**: Vague advice doesn't change behavior; specific, painful truths do
- **Format**: Every insight includes:
  - The exact mistake (with numbers)
  - How much it costs (in dollars)
  - One specific fix (actionable)
  - Real examples from user's trades

### The Statistical Foundation

The system only reports patterns when:
- **Sample size** ≥ 30 trades (statistical significance)
- **Confidence** ≥ 95% (via bootstrap testing)
- **Dollar impact** ≥ $500 (meaningful loss)
- **Relative difference** ≥ 20% (substantial pattern)

This prevents false positives and ensures every insight is both **statistically valid** and **financially meaningful**.

---

## Overview

This document details the technical implementation of WalletDoctor's core data processing pipeline, which transforms raw blockchain data into actionable trading insights. The system processes wallet transaction data through three main stages:

1. **Data Transformation**: Converting raw API responses into structured DataFrames
2. **Analytics & Pattern Detection**: Running multiple analysis algorithms to identify trading patterns
3. **Output Generation**: Formatting insights into human-readable, actionable reports

### Key Design Principles
- **Statistical Rigor**: Only report patterns with >95% confidence
- **Dollar Impact**: Focus on patterns that matter financially (>$500 impact)
- **Actionable Insights**: Every finding includes a specific fix
- **Harsh Truth**: Direct language that motivates behavior change

---

## Step 4: Data Transformation

### 4.1 Input Data Sources

#### Helius API (Transaction History)
```json
{
  "signature": "5xKtCja8wH3...",
  "timestamp": 1699564800,
  "type": "SWAP",
  "fee": 5000,
  "tokenTransfers": [{
    "mint": "DezXAY8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "tokenAmount": 1000000,
    "fromUserAccount": "8xKt9H2...",
    "toUserAccount": "7yLm3K1..."
  }],
  "nativeTransfers": [{
    "amount": 50000000,
    "fromUserAccount": "8xKt9H2...",
    "toUserAccount": "9zMn4J2..."
  }]
}
```

#### Cielo Finance API (P&L Data)
```json
{
  "token_address": "DezXAY8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
  "token_symbol": "BONK",
  "total_pnl_usd": -450.25,
  "unrealized_pnl_usd": 0,
  "holding_time_seconds": 3600,
  "num_swaps": 8,
  "average_buy_price": 0.00012,
  "average_sell_price": 0.00008,
  "total_buy_amount": 10000000,
  "total_sell_amount": 10000000
}
```

### 4.2 Transformation Process

#### Helius Transformation (`normalize_helius_transactions()`)

```python
def normalize_helius_transactions(transactions: List[Dict]) -> pd.DataFrame:
    flattened = []
    for tx in transactions:
        base_info = {
            'signature': tx.get('signature'),
            'timestamp': tx.get('timestamp'),  # Unix timestamp
            'fee': tx.get('fee'),
            'type': tx.get('type'),
            'source': tx.get('source'),
            'slot': tx.get('slot'),
        }
        
        # Flatten nested transfers into individual rows
        for transfer in tx.get('tokenTransfers', []):
            record = base_info.copy()
            record.update({
                'token_mint': transfer.get('mint'),
                'token_amount': transfer.get('tokenAmount'),
                'from_address': transfer.get('fromUserAccount'),
                'to_address': transfer.get('toUserAccount'),
                'transfer_type': 'token_transfer'
            })
            flattened.append(record)
```

**Key Transformations:**
1. **Denormalization**: Each token transfer becomes its own row
2. **Timestamp Conversion**: Unix → datetime object
3. **Type Labeling**: Adds `transfer_type` for filtering
4. **Null Handling**: Missing fields filled with None

#### Cielo Transformation (`normalize_cielo_pnl()`)

```python
def normalize_cielo_pnl(pnl_data: Dict) -> pd.DataFrame:
    normalized_tokens = []
    for token in pnl_data['tokens']:
        # Calculate derived fields
        entry_size = token.get('total_buy_amount', 0) * token.get('average_buy_price', 0)
        
        normalized_token = {
            'mint': token.get('token_address'),
            'symbol': token.get('token_symbol'),
            'realizedPnl': token.get('total_pnl_usd', 0),
            'unrealizedPnl': token.get('unrealized_pnl_usd', 0),
            'totalPnl': token.get('total_pnl_usd', 0) + token.get('unrealized_pnl_usd', 0),
            'entry_size_usd': entry_size,  # Calculated field
            'avgBuyPrice': token.get('average_buy_price', 0),
            'avgSellPrice': token.get('average_sell_price', 0),
            'quantity': token.get('holding_amount', 0),
            'totalBought': token.get('total_buy_amount', 0),
            'totalSold': token.get('total_sell_amount', 0),
            'holdTimeSeconds': token.get('holding_time_seconds', 0),
            'numSwaps': token.get('num_swaps', 0)
        }
```

**Key Calculations:**
- `entry_size_usd = totalBought × avgBuyPrice` (for position sizing analysis)
- `totalPnl = realizedPnl + unrealizedPnl` (combined P&L)

### 4.3 Database Schema

#### DuckDB Tables

```sql
-- Transaction table (tx)
CREATE TABLE tx (
    signature VARCHAR,
    timestamp TIMESTAMP,
    fee BIGINT,
    type VARCHAR,
    source VARCHAR,
    slot BIGINT,
    token_mint VARCHAR,
    token_amount DOUBLE,
    native_amount BIGINT,
    from_address VARCHAR,
    to_address VARCHAR,
    transfer_type VARCHAR
);

-- P&L table (pnl)
CREATE TABLE pnl (
    mint VARCHAR,
    symbol VARCHAR,
    realizedPnl DOUBLE,
    unrealizedPnl DOUBLE,
    totalPnl DOUBLE,
    avgBuyPrice DOUBLE,
    avgSellPrice DOUBLE,
    quantity DOUBLE,
    totalBought DOUBLE,
    totalSold DOUBLE,
    holdTimeSeconds BIGINT,
    numSwaps INTEGER,
    entry_size_usd DOUBLE  -- Calculated field
);
```

---

## Step 5: Analytics & Pattern Detection

### 5.1 Analytics Architecture

The system runs multiple analysis engines in parallel:

```
┌─────────────────────┐
│   Loaded Data       │
│  (pnl_df, tx_df)    │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌───────────┐ ┌──────────────┐
│Basic Stats│ │Pattern Engine│
└─────┬─────┘ └──────┬───────┘
      │              │
      ▼              ▼
┌──────────┐ ┌───────────────┐
│Metrics   │ │Harsh Insights │
│Calculator│ │Generator      │
└──────────┘ └───────────────┘
```

### 5.2 Basic Statistics Engine

#### Algorithm: `calculate_accurate_stats()`

```python
def calculate_accurate_stats(pnl_df: pd.DataFrame) -> Dict[str, Any]:
    # Core metrics
    total_tokens = len(pnl_df)
    winning_tokens = len(pnl_df[pnl_df['realizedPnl'] > 0])
    losing_tokens = total_tokens - winning_tokens
    
    # Win rate calculation
    win_rate = (winning_tokens / total_tokens * 100) if total_tokens > 0 else 0
    
    # Hold time analysis (only for sold positions)
    sold_tokens = pnl_df[pnl_df['holdTimeSeconds'] > 0]
    median_hold_minutes = sold_tokens['holdTimeSeconds'].median() / 60
    
    return {
        'total_tokens_traded': total_tokens,
        'win_rate_pct': win_rate,
        'winning_tokens': winning_tokens,
        'losing_tokens': losing_tokens,
        'total_realized_pnl': pnl_df['realizedPnl'].sum(),
        'total_unrealized_pnl': pnl_df['unrealizedPnl'].sum(),
        'median_hold_minutes': median_hold_minutes
    }
```

### 5.3 Position Size Analysis

#### Algorithm: `_analyze_position_sizes()`

```python
def _analyze_position_sizes(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
    # Define size buckets
    bins = [0, 100, 500, 1000, 5000, 10000, 50000, float('inf')]
    labels = ['<$100', '$100-500', '$500-1K', '$1K-5K', '$5K-10K', '$10K-50K', '>$50K']
    
    # Categorize trades
    pnl_df['size_bucket'] = pd.cut(pnl_df['entry_size_usd'], bins=bins, labels=labels)
    
    # Analyze each bucket
    bucket_stats = pnl_df.groupby('size_bucket').agg({
        'realizedPnl': ['sum', 'mean', 'count']
    })
    
    # Calculate win rates per bucket
    bucket_win_rates = pnl_df.groupby('size_bucket').apply(
        lambda x: (x['realizedPnl'] > 0).sum() / len(x) * 100
    )
    
    # Identify best/worst buckets by total P&L
    total_by_bucket = bucket_stats[('realizedPnl', 'sum')]
    best_bucket = total_by_bucket.idxmax()
    worst_bucket = total_by_bucket.idxmin()
```

**Key Insights Generated:**
- Optimal position size range
- Win rate by position size
- Cost of wrong sizing
- Specific examples of failed large trades

### 5.4 Behavioral Pattern Detection

#### FOMO Detection Algorithm

```python
def _detect_fomo_pattern(self, pnl_df: pd.DataFrame) -> Optional[Dict]:
    # Define behavioral groups
    quick_trades = pnl_df[pnl_df['holdTimeSeconds'] < 600]   # <10 minutes
    patient_trades = pnl_df[pnl_df['holdTimeSeconds'] > 3600] # >1 hour
    
    # Minimum sample size check
    if len(quick_trades) < 30 or len(patient_trades) < 30:
        return None
    
    # Statistical validation using bootstrap
    confidence = self._bootstrap_confidence_test(
        quick_trades['realizedPnl'].values,
        patient_trades['realizedPnl'].values,
        test_type='patient_better'
    )
    
    # Calculate opportunity cost
    avg_quick = quick_trades['realizedPnl'].mean()
    avg_patient = patient_trades['realizedPnl'].mean()
    potential_improvement = (avg_patient - avg_quick) * len(quick_trades)
    
    # Report only if statistically significant
    if confidence > 0.95 and potential_improvement > 500:
        return {
            "pattern": "FOMO Trading Detected",
            "confidence": f"{confidence*100:.0f}%",
            "impact": f"${potential_improvement:,.0f} potential gain",
            "evidence": {...}
        }
```

#### Bootstrap Confidence Test

```python
def _bootstrap_confidence_test(self, sample1, sample2, test_type='greater', n_iterations=1000):
    """Statistical validation using bootstrap resampling"""
    better_count = 0
    
    for _ in range(n_iterations):
        # Resample with replacement
        resample1 = np.random.choice(sample1, size=30, replace=True)
        resample2 = np.random.choice(sample2, size=30, replace=True)
        
        if test_type == 'patient_better':
            if resample2.mean() > resample1.mean():
                better_count += 1
    
    return better_count / n_iterations
```

### 5.5 Pattern Detection Thresholds

```python
PATTERN_REQUIREMENTS = {
    "min_sample_size": 30,      # Statistical significance
    "confidence_level": 0.95,   # 95% confidence required
    "min_dollar_impact": 500,   # Must matter financially
    "min_relative_diff": 0.2    # 20% relative difference
}
```

### 5.6 Harsh Truth Generation

#### Position Sizing Sweet Spot

```python
def generate_position_size_insight(bucket_analysis):
    # Extract key facts
    best_range = bucket_analysis['best_bucket']
    worst_range = bucket_analysis['worst_bucket']
    cost = abs(bucket_analysis['negative_buckets_total'])
    
    # Get specific examples
    examples = get_worst_trades_in_bucket(worst_range, limit=3)
    
    return {
        "title": "💰 YOUR POSITION SIZE SWEET SPOT",
        "facts": [
            f"Best size range: {best_range} (Total P&L: ${best_pnl:,.0f})",
            f"Worst size range: {worst_range} (Total P&L: ${worst_pnl:,.0f})",
            f"{best_range} win rate: {best_wr:.0f}%",
            f"{worst_range} win rate: {worst_wr:.0f}%"
        ],
        "cost": f"Wrong position sizing cost: ${cost:,.0f}",
        "fix": f"Stick to {best_range} positions. Your {worst_range} trades are ego, not edge.",
        "examples": format_trade_examples(examples)
    }
```

---

## Step 6: Output Generation

### 6.1 Output Structure

The final output follows a strict format for consistency:

```
[EMOJI] [SECTION TITLE]
═══════════════════════
[DATA TABLE or FACTS LIST]

[EMOJI] [INSIGHT TITLE]
═══════════════════════
• Fact 1 with numbers
• Fact 2 with percentages
• Fact 3 with comparisons

💸 COST: [Dollar impact]
✅ THE FIX: [Specific action]

📝 Examples:
- [Real trade example 1]
- [Real trade example 2]
```

### 6.2 Formatting Functions

#### Main Formatter

```python
def format_insights_for_web(insights: List[Dict[str, Any]]) -> str:
    output = []
    
    for insight in insights:
        # Severity determines emoji
        severity_emoji = {
            "critical": "🚨",
            "high": "⚠️", 
            "medium": "📊"
        }
        
        # Build section
        output.append(f"\n{severity_emoji[insight['severity']]} {insight['title']}")
        output.append("=" * 60)
        
        # Add facts
        for fact in insight['facts']:
            output.append(f"   • {fact}")
        
        # Add cost and fix
        output.append(f"\n   💸 COST: {insight['cost']}")
        output.append(f"   ✅ THE FIX: {insight['fix']}")
        
        # Add examples if present
        if insight.get('examples'):
            output.append("\n   📝 Examples:")
            for example in insight['examples']:
                output.append(f"      - {example}")
    
    return "\n".join(output)
```

### 6.3 Performance Summary Table

```python
def format_performance_table(stats):
    table = Table(title="Performance Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Tokens Traded", str(stats['total_tokens_traded']))
    table.add_row("Token Win Rate", f"{stats['win_rate_pct']:.2f}%")
    table.add_row("Winning Tokens", str(stats['winning_tokens']))
    table.add_row("Losing Tokens", str(stats['losing_tokens']))
    table.add_row("Realized PnL", f"${stats['total_realized_pnl']:,.2f}")
    table.add_row("Median Hold Time", f"{stats['median_hold_minutes']:.1f} minutes")
    
    return table
```

---

## Potential Improvements

### 1. Advanced Statistical Methods

**Current**: Simple bootstrap confidence testing
**Potential**: 
- Implement proper hypothesis testing (t-tests, Mann-Whitney U)
- Add time series analysis for performance trends
- Use machine learning for pattern clustering

### 2. Real-time Price Integration

**Current**: No market price comparison
**Potential**:
- Calculate actual slippage vs market prices
- Identify front-running patterns
- Compare execution quality across DEXes

### 3. Enhanced Pattern Detection

**Current**: Rule-based pattern detection
**Potential**:
- ML-based anomaly detection
- Sequence analysis for trading patterns
- Cross-wallet pattern comparison

### 4. Risk Metrics

**Current**: Basic P&L and win rate
**Potential**:
- Sharpe ratio calculation
- Maximum drawdown analysis
- Value at Risk (VaR)
- Risk-adjusted returns

### 5. Optimization Suggestions

**Current**: Static recommendations
**Potential**:
- Dynamic position sizing calculator
- Optimal hold time predictor
- Entry/exit signal generation

### 6. Data Pipeline Improvements

**Current**: Batch processing on demand
**Potential**:
- Real-time streaming pipeline
- Incremental updates
- Data caching layer
- Parallel processing for multiple wallets

### 7. Enhanced Behavioral Analysis

**Current**: Basic FOMO and loss aversion
**Potential**:
- Revenge trading detection
- Correlation with market events
- Social sentiment analysis
- Trader psychology profiling

### 8. Output Customization

**Current**: One-size-fits-all harsh truths
**Potential**:
- Adjustable tone/severity
- Focus area selection
- Progress tracking over time
- Gamification elements

---

## Technical Considerations

### Performance
- Current processing time: 10-30 seconds per wallet
- Bottlenecks: API calls, bootstrap iterations
- Memory usage: ~100MB for typical wallet

### Scalability
- Database can handle millions of records
- API rate limits may constrain bulk analysis
- Consider caching layer for repeated queries

### Accuracy
- Statistical confidence thresholds prevent false positives
- Minimum sample sizes ensure reliability
- Dollar impact thresholds focus on meaningful patterns

### Maintainability
- Modular design allows easy addition of new patterns
- Clear separation between data, analytics, and presentation
- Comprehensive logging for debugging

---

## Conclusion

WalletDoctor's analytics pipeline transforms raw blockchain data into actionable trading insights through:

1. **Robust data transformation** that handles messy real-world data
2. **Statistically validated pattern detection** that avoids false positives
3. **Harsh but actionable output** that motivates behavior change

The system's strength lies in its focus on statistical rigor and dollar impact, ensuring that every insight is both accurate and meaningful. Future improvements could enhance the sophistication of pattern detection and provide more personalized recommendations. 