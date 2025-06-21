# Context-Aware AI Layer Implementation Plan

## Problem Statement

The current bot uses rigid if/else rules that can't understand context, leading to:
- Misclassification of user intent ("cut position" while in profit tagged as "stop loss")
- Tone-deaf responses (asking about "profits" when user is down -49%)
- Repetitive patterns despite state management
- Inability to understand nuanced trading scenarios

## Solution: Context-Aware AI Layer

### Core Concept
Replace template-based responses with an AI layer that understands:
1. **Trading Context** - What's actually happening (profit vs loss, size, timing)
2. **Conversation History** - What was discussed and when
3. **User Intent** - What the trader means, not just what they say
4. **Personal Patterns** - Individual trading style and vocabulary

### Architecture

```
Trade Event → Context Pack → AI Analysis → Response Generation → User
                  ↓              ↓
            State Manager    Pattern DB
```

### Context Pack Structure
```python
{
    "trade": {
        "action": "SELL",
        "token": "ROOMCON",
        "pnl": "+37%",
        "size_ratio": 1.2,
        "hold_time": "4h"
    },
    "conversation": {
        "last_question": "ROOMCON again?",
        "last_answer": "following the whale",
        "unanswered_questions": [],
        "time_since_last": "2h"
    },
    "patterns": {
        "token_history": "3 trades, -$2k total",
        "typical_hold": "30min",
        "win_rate": "23%"
    },
    "user_message": "cut the position"
}
```

## Implementation Phases

### Phase 1: Intent Classification (Thin Slice)
**Goal**: Correctly classify user messages based on context

**Scope**:
- Focus only on user responses to bot questions
- Binary classification initially (profit-taking vs stop-loss)
- Use GPT-4 with structured prompts

**Example**:
```
User says: "cut the position"
If P&L > 0: → "profit_taking"
If P&L < 0: → "stop_loss"
```

**Success Metric**: 95% accuracy on intent classification

### Phase 2: Dynamic Question Generation
**Goal**: Generate contextually appropriate questions

**Scope**:
- Replace template selection with AI generation
- Maintain conversational tone
- Include relevant context naturally

**Example**:
```
Instead of: "Taking some {token} profits?"
Generate: "Nice 37% on ROOMCON - still following that whale or taking the win?"
```

### Phase 3: Memory Integration
**Goal**: Reference past conversations naturally

**Scope**:
- Pull relevant history from state manager
- Weave into questions seamlessly
- Avoid repetitive callbacks

**Example**:
```
"Last week you said BONK was a 'quick flip' - looks like you're holding longer this time. Strategy change?"
```

### Phase 4: Learning & Adaptation
**Goal**: Improve responses based on user feedback

**Scope**:
- Track which questions get answered
- Learn user's vocabulary and style
- Adjust tone based on engagement

## Technical Implementation

### 1. Create AI Service
```python
class ContextAwareAI:
    def __init__(self, openai_client):
        self.client = openai_client
        
    async def classify_intent(self, context_pack):
        # Structured prompt for classification
        
    async def generate_question(self, context_pack):
        # Dynamic question generation
        
    async def should_respond(self, context_pack):
        # Decide if response needed
```

### 2. Integrate with Existing Flow
```python
# In nudge_engine.py
if ai_enabled:
    context_pack = build_context_pack(trade, state, patterns)
    question = await ai.generate_question(context_pack)
else:
    question = select_template(pattern)  # Current approach
```

### 3. Prompt Engineering
```
You are a trading coach having a conversation with a trader.

Context:
- They just sold ROOMCON at +37% profit
- 2 hours ago they said they were "following a whale"
- This is their 3rd ROOMCON trade (previous: -$800, -$1200)

They just said: "cut the position"

Generate a brief, conversational response that:
1. Acknowledges their profit
2. References their whale-following strategy
3. Keeps it under 20 words
```

## Success Metrics

1. **Intent Accuracy**: >95% correct classification
2. **Response Relevance**: >90% user rating
3. **Engagement Rate**: >70% questions answered
4. **Duplicate Rate**: <5% repetitive questions
5. **Latency**: <2s additional delay

## Risk Mitigation

1. **Fallback System**: Keep template system as backup
2. **Gradual Rollout**: Test with small user group first
3. **Cost Control**: Cache AI responses, batch where possible
4. **Privacy**: Never send wallet addresses to AI
5. **Monitoring**: Track AI performance metrics

## Development Timeline

- **Week 1**: Intent classification prototype
- **Week 2**: Integration with existing bot
- **Week 3**: Testing and refinement
- **Week 4**: Gradual rollout to users

## Key Decisions

1. **Start Small**: Just intent classification first
2. **Use Existing Infrastructure**: Build on state manager
3. **Maintain Tone**: Keep conversational, not robotic
4. **Measure Everything**: Data-driven improvements
5. **User Control**: Allow AI features to be toggled

## Next Steps

1. Set up OpenAI integration
2. Create context pack builder
3. Write intent classification prompts
4. Build test harness with real examples
5. Integrate with one pattern type first 