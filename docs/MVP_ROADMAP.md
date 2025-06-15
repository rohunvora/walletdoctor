# WalletDoctor MVP Roadmap: Annotation-Driven Coaching

## Executive Summary

We're pivoting from a heavy analytics tool to a lightweight, annotation-driven trading coach that provides instant value and grows smarter with user input.

## The Pivot: Before vs After

### Before (Current State)
- **Heavy Gates**: Requires 30+ trades with 95% confidence
- **Batch Reports**: All-or-nothing insight dumps
- **One-Way Flow**: Data → Analysis → Report
- **Static Insights**: Same insights regardless of user evolution

### After (MVP State)
- **Instant Value**: Show win rate & avg P&L immediately
- **Interactive**: Users annotate trades for personalized insights
- **Continuous Learning**: Each annotation improves coaching
- **"You vs You"**: Compare new trades to personal patterns

## Implementation Phases

### ✅ Phase 1: Foundation (Completed)
**Files Created:**
- `scripts/db_migrations.py` - Annotation table schema
- `scripts/instant_stats.py` - Ungated baseline stats
- `scripts/trade_comparison.py` - Personal pattern matching

**What's New:**
- Database tables for annotations and coaching history
- Instant stats without statistical gates
- Trade comparison engine

### ✅ Phase 2: CLI Integration (Completed)
**Files Modified:**
- `scripts/coach.py` - Added new commands

**New Commands:**
```bash
# Instant baseline - no gates
python scripts/coach.py instant <wallet>

# Add annotation to trade
python scripts/coach.py annotate BONK "FOMO'd into the pump"

# Check new trades
python scripts/coach.py refresh

# See evolution over time
python scripts/coach.py evolution
```

### ✅ Phase 3: Web Interface (Completed)
**Files Created:**
- `web_app_v2.py` - Enhanced Flask app
- `templates_v2/index_v2.html` - Interactive UI

**Features:**
- Instant baseline display
- Interactive trade annotation
- Real-time pattern matching
- Persistent coaching journal

## Running the MVP

### 1. Setup Environment
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export HELIUS_KEY="your-key"
export CIELO_KEY="your-key"
```

### 2. Run Database Migrations
```bash
python scripts/db_migrations.py
```

### 3. Start Web Interface
```bash
python web_app_v2.py
# Open http://localhost:5002
```

### 4. CLI Usage
```bash
# Quick start
python scripts/coach.py instant <wallet>

# Add notes
python scripts/coach.py annotate BONK "Bought the top again"

# See your evolution
python scripts/coach.py evolution
```

## Key User Flows

### Flow 1: First-Time User
1. Enter wallet → See instant baseline (win rate, avg P&L)
2. View top 3 winners & losers
3. Add note to one trade
4. See comparison to similar past trades
5. Get personalized insight based on pattern

### Flow 2: Returning User
1. Click "Check New Trades"
2. See each new trade compared to personal average
3. Add annotations to explain decisions
4. Watch coaching evolve with their input

### Flow 3: Power User
1. Annotate consistently
2. Ask AI coach questions using annotation context
3. Track evolution over time
4. Export annotated journal for tax/analysis

## Technical Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Data Layer    │     │  Logic Layer     │     │ Presentation    │
├─────────────────┤     ├──────────────────┤     ├─────────────────┤
│ DuckDB          │────▶│ instant_stats.py │────▶│ CLI (coach.py)  │
│ - tx table      │     │ trade_comparison │     │ Web (Flask)     │
│ - pnl table     │     │ db_migrations    │     │ Templates       │
│ - annotations   │     │ analytics.py     │     └─────────────────┘
│ - snapshots     │     └──────────────────┘
└─────────────────┘
```

## Deployment Strategy

### Week 1: Soft Launch
- Deploy to staging environment
- Test with 5-10 friendly users
- Gather feedback on annotation UX
- Fix critical bugs

### Week 2: Beta Release
- Deploy enhanced web interface
- Add basic analytics tracking
- Monitor annotation quality
- Iterate on coaching prompts

### Week 3: Public Launch
- Announce on Twitter/Discord
- Create video walkthrough
- Launch "30-day challenge" campaign
- Track user retention metrics

## Success Metrics

### Engagement Metrics
- **Daily Active Users**: Target 100 in first month
- **Annotations per User**: Target 5+ per week
- **Return Rate**: 40% weekly active

### Quality Metrics
- **Annotation Length**: Average 20+ characters
- **Pattern Detection**: 80% users see patterns
- **Coaching Relevance**: 70% find insights helpful

### Growth Metrics
- **Viral Coefficient**: Users share annotated insights
- **Retention**: 30% still active after 30 days
- **Word of Mouth**: 50% users from referrals

## Risk Mitigation

### Risk 1: Annotation Fatigue
**Mitigation**: 
- Make it optional but valuable
- Show immediate benefit from each annotation
- Gamify with streaks/achievements

### Risk 2: Poor Quality Annotations
**Mitigation**:
- Provide prompting templates
- Show example annotations
- Filter out low-effort entries

### Risk 3: Scaling Issues
**Mitigation**:
- DuckDB handles 1000s of users easily
- Implement caching for common queries
- Move to PostgreSQL if needed

## Future Enhancements (Post-MVP)

### V2 Features
1. **Smart Prompts**: AI-suggested annotation questions
2. **Pattern Alerts**: Notify when repeating mistakes
3. **Social Features**: Anonymous pattern sharing
4. **Export Tools**: PDF reports, CSV exports

### V3 Features
1. **Multi-wallet**: Track multiple strategies
2. **Team Mode**: Share insights with trading group
3. **API Access**: Integrate with trading bots
4. **Mobile App**: Trade & annotate on the go

## Conclusion

This MVP transforms WalletDoctor from a passive analytics tool into an active coaching companion. By focusing on instant gratification, user participation, and personal pattern recognition, we create a sticky product that grows more valuable with use.

The annotation-driven approach solves the cold start problem while building a moat through personalized data that users themselves create.

**Next Step**: Run `python web_app_v2.py` and start annotating! 