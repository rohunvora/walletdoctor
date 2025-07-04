# WalletDoctor Tickets System

## Overview

This directory contains all active development tickets. Each ticket is a standalone markdown file that defines scope, acceptance criteria, and measurable outcomes.

## Ticket Board

### Active Tickets
| ID | Title | Scope / Done-When | Priority | Owner |
|---|---|---|---|---|
| [CCH-001](./CCH-001.md) | Add Redis warm-cache | Warm <0.5s, cache hit ratio metric in `/diagnostics` | P3 | |
| [PAG-001](./PAG-001.md) | Large-wallet pagination | 250k+ sig wallets succeed ≤30s | P3 | |
| [OPS-001](./OPS-001.md) | Hard branch-freeze rule | GH protection + `BRANCH_FREEZE.md` merged | P2 | DevOps |

### Completed ✅
| ID | Title | Completed | Notes |
|---|---|---|---|
| [PRC-001](./PRC-001.md) | **SOL spot pricing for positions** | **2025-01-15** | **✅ Production validated: 18+356 positions priced with schema v0.8.0-prices** |
| [POS-001](./POS-001.md) | Fix position-builder filter bug | 2024-01-15 | Demo wallet returns ≥1 position ✅ |
| [POS-002](./POS-002.md) | Production endpoint investigation | 2024-01-15 | 18 positions in production ✅ |

**PRC-001 Verification Proof**:
```bash
# ✅ PRODUCTION VALIDATION
curl -H "X-Api-Key: wd_test1234567890abcdef1234567890ab" \
  "https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"

# Response shows:
# ✅ "schema_version": "v0.8.0-prices" 
# ✅ "current_price_usd": "152.64" (SOL spot price)
# ✅ "price_source": "sol_spot_price" 
# ✅ 18 positions all priced consistently
# ✅ Response time: <3s (target <5s)
# ✅ Feature flag: PRICE_SOL_SPOT_ONLY=true active

# Git tag: v0.8.0-prices (commit 68a81df)
# Performance: >99% success rate, 30s cache, <200ms fetch
# ChatGPT ready: Meaningful dollar value discussions enabled
```

### GPT Integration ([Epic: GPT-000](./GPT-000-INTEGRATION-EPIC.md))
| ID | Title | Scope / Done-When | Priority | Owner |
|---|---|---|---|---|
| [GPT-001](./GPT-001.md) | Public Postman / cURL cookbook | `docs/gpt_examples.md` shows 3 copy-paste calls returning 200 | P1 | |
| [GPT-002](./GPT-002.md) | Schema JSONSchema export | `schemas/trades_export_v0.7.0.json` auto-generated; validated by ajv | P1 | |
| [GPT-003](./GPT-003.md) | TypeScript client helper | Lightweight npm package with auth handling; published to GitHub Packages | P2 | |
| [GPT-004](./GPT-004.md) | Prompt templates & few-shot examples | `prompts/base_trades.md` contains 5+ examples; reviewed by GPT PM | P2 | |
| [GPT-005](./GPT-005.md) | Streaming support spike | PoC SSE endpoint returning first 100 trades in <1s | P3 | |
| [GPT-006](./GPT-006.md) | CI integration tests | GitHub Action hits Railway daily; fails if HTTP ≥400; alerts in #alerts | P1 | |

## Process

### New Work
1. **Create ticket**: `tickets/XYZ-###.md` using the template below
2. **Update board**: Add row to table above
3. **Get agreement**: Discuss scope and priority before starting

### Development
1. **PR title**: Must reference ticket ID: `POS-001: Fix position filtering in PositionSnapshot`
2. **Link ticket**: Include `Closes tickets/POS-001.md` in PR description
3. **Review**: Code owner reviews both code and ticket completion

### Completion
1. **Merge PR**: Automatically closes ticket
2. **Update CHANGELOG**: Auto-generate entry from ticket title
3. **Archive**: Move ticket to `tickets/completed/`

## Ticket Template

```markdown
# XYZ-001: [One-line title]

**Priority**: P1/P2/P3  
**Owner**: @username  
**Created**: YYYY-MM-DD  

## Goal
One-sentence value statement describing why this work matters.

## Acceptance Criteria
- [ ] Measurable criterion 1
- [ ] Measurable criterion 2  
- [ ] Performance target (if applicable)

## Out of Scope
- Thing we explicitly won't do
- Feature that might seem related but isn't

## Testing
- [ ] Unit tests for new functionality
- [ ] Integration test with specific wallet
- [ ] Performance validation

## Definition of Done
Clear, binary statement of completion.
```

## Anti-Patterns to Avoid

❌ **Vague scope**: "Improve performance"  
✅ **Specific target**: "Cold response <8s for test wallet"  

❌ **Feature creep**: Adding "just one more thing"  
✅ **Strict scope**: If it's not in acceptance criteria, it's out of scope  

❌ **Moving goalposts**: Changing criteria mid-ticket  
✅ **New ticket**: Create separate ticket for new requirements 