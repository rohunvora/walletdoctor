# GPT Integration Final Plan

## Executive Summary
Complete plan for GPT integration with all gap resolutions and concrete implementation steps.

## Final To-Do List

### ✅ GPT-001: Public Postman / cURL Cookbook (COMPLETE)
**Status**: Ready to ship  
**Files**: `docs/gpt_examples.md`

**Deliverables**:
- ✅ Small wallet success example (200 OK)
- ✅ Auth error example (403 Forbidden) 
- ✅ Server error with retry example (5xx)
- ✅ Exponential backoff script
- ✅ Examples <3KB for clean pasting
- ✅ Performance expectations documented

### 📋 GPT-002: JSONSchema 
**Status**: Ready for Week 1  
**Approach**: Use openapi-generator-cli (1-liner)

**Implementation**:
```bash
npm install -g @openapitools/openapi-generator-cli
openapi-generator-cli generate -i src/api/openapi.yaml -g openapi -o schemas/
```

**CI Integration**: Schema validation in GPT-006 workflow

### 📋 GPT-003: TypeScript Helper
**Decision**: Monorepo approach (`/clients/ts/`)  
**Status**: Ready for Week 1

**Structure**:
```
clients/
├── ts/
│   ├── src/
│   ├── package.json (private: true)
│   └── README.md
├── python/  # Future
└── rust/    # Future
```

### 📋 GPT-004: Prompt Templates
**Status**: Ready for Week 1  
**Requirement**: Include chain-of-thought example with token cost

**Example Structure**:
- Basic analysis prompt
- Deep analysis with CoT
- Token cost breakdown
- "Example output" disclaimer

### 📋 GPT-005: SSE Streaming Spike
**Status**: Time-boxed to 6 hours  
**Exit Criteria**: 
- ✅ If >90% events arrive <25s → proceed
- ❌ If not → punt to WebSocket (PAG-002)

**Test Script**: `scripts/test_sse_railway.sh`

### ✅ GPT-006: CI Workflow (READY FOR PR)
**Status**: Complete, ready to open PR  
**Files**: `.github/workflows/gpt-integration.yml`

**Features**:
- ✅ Performance warning bands (cold >6s, warm >0.3s)
- ✅ Single concurrent job (prevents DOS)
- ✅ Parameterized for forking
- ✅ Schema validation step
- ✅ Slack notifications

**PR Script**: `scripts/create_gpt_ci_pr.sh`

## Gap Resolutions Summary

1. **Schema Freeze** ✅ → v0.7.0 locked, versioning doc created
2. **Performance Environment** ✅ → Single concurrent CI job  
3. **SSE Exit Criteria** ✅ → 90% <25s or punt to WebSocket
4. **Package Decision** ✅ → Monorepo `/clients/ts/`
5. **Acceptance Metrics** ✅ → Cold ≤8s, warm ≤0.5s, warning bands
6. **Error Coverage** ✅ → Added 5xx retry examples

## Week 1 Execution Plan

### Day 1-2: Foundation
- [x] Ship GPT-001 docs
- [ ] Open PR for GPT-006 CI workflow
- [ ] Generate initial schema (GPT-002)

### Day 3-4: Development  
- [ ] Build TypeScript client structure (GPT-003)
- [ ] Create prompt templates (GPT-004)
- [ ] Run SSE spike test (GPT-005)

### Day 5: Integration
- [ ] Wire schema validation into CI
- [ ] Document SSE spike results
- [ ] Prepare Week 2 plan

## Success Metrics
- GPT team successfully runs all examples
- CI passes with performance targets
- Schema stays in sync with API
- Clear go/no-go on SSE streaming

## Next Steps After GPT-001 Merge
1. Start POS-001 work in feature branch
2. Monitor first scheduled CI run
3. Gather GPT team feedback on examples 