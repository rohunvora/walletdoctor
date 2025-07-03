# GPT-000: GPT Integration Epic

**Priority**: EPIC  
**Owner**: TBD  
**Created**: 2025-01-02  
**Target**: Q1 2025  

## Goal
Ship first-class trading-insight prompting in ChatGPT with <1-sec median latency and clear, documented examples.

## Success Metrics
- [ ] End-to-end prompt → answer demo screencast for test wallet
- [ ] GPT integration tests green in CI (see GPT-006)
- [ ] GPT team successfully using endpoint in production
- [ ] Median response time <1 second for cached requests

## Child Tickets
| Ticket | Title | Status |
|--------|-------|--------|
| [GPT-001](./GPT-001.md) | Public Postman / cURL cookbook | New |
| [GPT-002](./GPT-002.md) | Schema JSONSchema export | New |
| [GPT-003](./GPT-003.md) | TypeScript client helper | New |
| [GPT-004](./GPT-004.md) | Prompt templates & few-shot examples | New |
| [GPT-005](./GPT-005.md) | Streaming support spike | New |
| [GPT-006](./GPT-006.md) | CI integration tests | New |

## Architecture Decisions
- Trades-only endpoint (no positions) for initial integration
- API key authentication required
- JSON response format optimized for LLM consumption
- No pagination for v1 (handle in GPT prompts)

## Out of Scope
- Position calculations (separate backend work)
- Real-time WebSocket updates
- Historical price accuracy improvements
- Multi-wallet batch requests

## Milestones
1. **Week 1**: GPT-001 & GPT-002 complete (unblock GPT team)
2. **Week 2**: GPT-003 & GPT-006 complete (developer experience)
3. **Week 3**: GPT-004 complete (prompt optimization)
4. **Week 4**: GPT-005 spike results (streaming decision)

## Definition of Done
GPT team has successfully integrated trades endpoint with production ChatGPT, CI tests are green, and documentation enables external developers to build similar integrations. 