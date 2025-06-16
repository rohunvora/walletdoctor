# Product Requirements Document: Trading Report Card

**Product Name**: TradeBro Trading Report Card  
**Version**: 1.0  
**Date**: December 2024  
**Status**: Approved for Development  

---

## 1. Executive Summary

TradeBro Trading Report Card transforms complex trading data into a simple, shareable letter grade. Like Spotify Wrapped for traders, it provides instant understanding of performance through beautiful visualizations optimized for social sharing.

**Key Value Proposition**: "See your trading grade in 5 seconds. Share it in 1 click."

---

## 2. Problem Statement

### Current Pain Points:
- Traders don't know how they compare to others
- Complex analytics dashboards overwhelm users
- No simple way to understand overall performance
- Trading apps lack shareable, viral moments
- Existing tools try to be coaches, not mirrors

### User Need:
"I want to quickly understand if I'm a good trader and share my wins (or commiserate about losses) with others."

---

## 3. Solution Overview

A single-page web app that:
1. Takes a Solana wallet address
2. Calculates trading performance percentile
3. Assigns a letter grade (A+ to F)
4. Identifies one superpower and one weakness
5. Displays results in a beautiful, shareable format

---

## 4. Target Users

### Primary User: Active Solana Trader
- Age: 18-35
- Trades 10+ times per month
- Active on Twitter/Discord
- Likes to share wins
- Seeks validation/comparison

### Secondary User: Casual Trader
- Trades occasionally
- Curious about performance
- Might become more active with feedback

---

## 5. Core Features

### 5.1 Grade Calculation
- **Input**: Wallet address
- **Process**: Compare to database of 100+ wallets
- **Output**: Letter grade based on percentile
  - A+: Top 10%
  - A: Top 20%
  - B+: Top 30%
  - B: Top 40%
  - C+: Top 50%
  - C: Top 60%
  - D: Top 80%
  - F: Bottom 20%

### 5.2 Performance Insights
Each report card includes:
- **Percentile Rank**: "Better than X% of traders"
- **Superpower**: User's strongest trait
- **Kryptonite**: User's biggest weakness
- **Best Trade**: Highest profit with details
- **Worst Trade**: Biggest loss with details

### 5.2 Performance Insights with Creative Labels
Each report card includes:
- **Percentile Rank**: "Better than X% of traders"
- **Notable Trades**: 3-5 trades with creative, memorable labels
  - Winners: "THE BONK SNIPER" (+$4,231, 2.3hr) - "Took profits like a pro"
  - Losers: "THE ZEX DISASTER" (-$15,387, 47hr) - "Married a pump, divorced broke"
- **Trading DNA**: Personalized trading style summary
- **Superpower/Kryptonite**: Expressed through specific trade examples

#### Creative Label System
Each significant trade gets:
1. **Emoji**: Visual indicator (💎, 🩸, 🎰, ⚡)
2. **Title**: "THE [TOKEN] [DESCRIPTOR]" format
3. **Stats**: P&L and hold time
4. **Subtitle**: Witty one-liner that captures what happened

Examples:
- 💎 THE BONK SNIPER - "Perfect timing for once"
- 🩸 THE SAMO FUNERAL - "Rode it all the way down"
- 🎰 THE WIF CASINO - "19 swaps of pure chaos"
- ⚡ THE SOL QUICKIE - "Sometimes lucky > good"

### 5.3 Visual Design
- Mobile-first responsive design
- Clean, modern aesthetic
- Large, prominent letter grade
- Optimized for screenshots
- Subtle animations on load

### 5.4 Sharing Features
- Pre-formatted share buttons for Twitter
- Open Graph meta tags for rich previews
- Download as image option
- Unique URL for each report card

---

## 6. User Flow

```
1. Land on homepage → "Enter your wallet address"
2. Submit wallet → Loading state (3-5 seconds)
3. Grade reveal → Animated letter grade appears
4. Full report → Scroll to see details
5. Share → Click to post on Twitter/download
```

---

## 7. Technical Requirements

### 7.1 Data Sources
- **Cielo API**: P&L data, win rates, trade details
- **Helius API**: Transaction data (optional enhancement)
- **Internal DB**: Percentile comparison data

### 7.2 Key Calculations
```python
# Pseudocode for grade calculation
def calculate_grade(wallet_stats):
    score = weighted_average(
        win_rate * 0.3,
        avg_pnl * 0.3,
        total_pnl * 0.2,
        consistency * 0.2
    )
    percentile = get_percentile(score, all_wallets)
    return percentile_to_grade(percentile)
```

### 7.3 Performance Requirements
- Page load: < 1 second
- Grade calculation: < 5 seconds
- Mobile-optimized: 100% responsive
- Share generation: Instant

### 7.4 Tech Stack
- Frontend: React/Next.js (or simple HTML/JS)
- Backend: Python FastAPI
- Database: DuckDB for analytics
- Hosting: Railway/Vercel
- CDN: Cloudflare for images

---

## 8. UI/UX Requirements

### 8.1 Visual Hierarchy
1. Letter grade (largest element)
2. Percentile rank
3. Superpower/Kryptonite
4. Trade details
5. Share buttons

### 8.2 Color Scheme
- A grades: Green gradient
- B grades: Blue gradient
- C grades: Yellow gradient
- D/F grades: Red gradient
- Dark mode support

### 8.3 Animations
- Grade reveal: Fade in with slight scale
- Stats: Slide in from sides
- Share button: Pulse on hover

---

## 9. Copy Guidelines

### 9.1 Tone
- Honest but not mean
- Celebratory for good grades
- Encouraging for bad grades
- Always shareable

### 9.2 Examples
**Good Grade**:
```
"Your Grade: A-
Better than 85% of traders 🎉

Your Superpower: Diamond Hands 💎
You hold winners 2.5x longer than average

Your Kryptonite: Overconfidence 📈
Sometimes you hold TOO long"
```

**Bad Grade**:
```
"Your Grade: D+
Better than 25% of traders 📚

Your Superpower: Risk Taker 🎲
You're not afraid to make moves

Your Kryptonite: FOMO Central 🚀
You chase 3x more pumps than profitable traders"
```

---

## 10. Success Metrics

### 10.1 Launch Metrics (Week 1)
- 1,000+ report cards generated
- 20%+ share rate
- <5% error rate

### 10.2 Growth Metrics (Month 1)
- 10,000+ unique wallets analyzed
- 25%+ return visitor rate
- 50+ organic social shares daily

### 10.3 Long-term Success
- Becomes the standard way to share trading performance
- "What's your TradeBro grade?" enters trader vocabulary
- Natural viral growth without paid marketing

---

## 11. MVP Scope (3 Days)

### Day 1: Backend
- [ ] Build percentile ranking system
- [ ] Create grade calculation algorithm
- [ ] Set up basic API endpoints
- [ ] Prepare comparison dataset

### Day 2: Frontend
- [ ] Design report card UI
- [ ] Implement grade reveal animation
- [ ] Add share functionality
- [ ] Optimize for mobile

### Day 3: Polish
- [ ] Test with 50+ real wallets
- [ ] Refine grade algorithm
- [ ] Perfect copy and messaging
- [ ] Deploy to production

---

## 12. Future Enhancements (Post-MVP)

1. **Grade History**: Track improvement over time
2. **Leaderboards**: Top traders by grade
3. **Badges**: Special achievements
4. **Compare**: Side-by-side wallet comparison
5. **Tips**: One actionable tip based on weakness

---

## 13. Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Unfair grades | High | Test extensively, gather feedback |
| API limits | Medium | Cache results, use pagination |
| Low share rate | High | A/B test copy and design |
| Data incomplete | Low | Percentiles handle missing data |

---

## 14. Launch Strategy

1. **Soft Launch**: Test with 10 friendly traders
2. **Adjust**: Refine based on feedback
3. **Twitter Launch**: Share compelling examples
4. **Community Seeding**: Post in trading Discords
5. **Influencer Outreach**: Get CT influencers to share grades

---

## 15. Example Report Cards

### High Performer
![A+ Grade Example]
- Grade: A+
- "Better than 94% of traders"
- Superpower: "Sniper Entries"
- Kryptonite: "Rare Misses Hit Hard"

### Average Performer
![C+ Grade Example]
- Grade: C+
- "Better than 55% of traders"
- Superpower: "Consistent Grinder"
- Kryptonite: "Small Wins, Big Losses"

### Learning Trader
![D Grade Example]
- Grade: D
- "Better than 22% of traders"
- Superpower: "Fearless Explorer"
- Kryptonite: "Every Pump Looks Good"

---

## 16. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| Dec 2024 | No coaching/advice | Keep scope simple |
| Dec 2024 | Letter grades only | Universal understanding |
| Dec 2024 | One page only | Reduce complexity |
| Dec 2024 | No user accounts | Reduce friction |

---

## 17. Approval

**Product Owner**: [Name]  
**Technical Lead**: [Name]  
**Design Lead**: [Name]  
**Approved Date**: [Date]

---

*This PRD is a living document and will be updated as we learn from user feedback.* 