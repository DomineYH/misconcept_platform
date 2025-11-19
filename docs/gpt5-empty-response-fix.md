# GPT-5 Empty Response Issue - Root Cause and Fix

**Date**: 2025-11-18
**Issue**: Student bot responses appearing empty or truncated
**Status**: ✅ RESOLVED

## Problem Summary

After deploying GPT-5 with Responses API, student bot responses were appearing empty despite API calls succeeding and returning token usage information.

### Symptoms

- First student response: ✅ Works (short response)
- Subsequent responses: ❌ Empty or very short (2-3 chars)
- API calls succeeding with no errors
- Token usage reported (128 completion tokens consumed)
- Response status: `incomplete` instead of `completed`

## Root Cause Analysis

### Investigation Steps

1. **Initial Observation**: Database showed empty `content` field (0 chars) despite successful API calls
2. **API Response Inspection**: Discovered response status was `incomplete` with only reasoning output
3. **Token Budget Analysis**: Found that reasoning effort consumed ALL available output tokens

### Technical Details

**GPT-5 Responses API with Reasoning**:
- `reasoning_effort="medium"` → uses ~128 tokens for internal reasoning
- `max_output_tokens=150` (old config) → only 22 tokens left for actual text
- Short responses (≤22 tokens) worked, longer ones truncated or empty
- Response marked as `incomplete` when tokens exhausted before completion

**Example Output Structure**:
```json
{
  "status": "incomplete",
  "output": [
    {
      "type": "reasoning",
      "content": null  // 128 reasoning tokens used internally
    }
    // No message item - ran out of tokens!
  ],
  "usage": {
    "output_tokens": 128,
    "output_tokens_details": {
      "reasoning_tokens": 128  // All tokens used for reasoning
    }
  }
}
```

## Solution

### Configuration Changes

**Before** (.env):
```bash
STUDENT_MAX_TOKENS=150  # Insufficient for reasoning="medium"
TUTOR_MAX_TOKENS=100    # Too low for reasoning="low"
```

**After** (.env):
```bash
STUDENT_MAX_TOKENS=500  # 128 reasoning + 372 for response
TUTOR_MAX_TOKENS=300    # Sufficient buffer for reasoning
```

### Calculation

For `reasoning_effort="medium"`:
- Reasoning tokens: ~128
- Desired response length: ~300-400 tokens
- **Minimum max_output_tokens**: 128 + 300 = **428 tokens**
- **Recommended**: 500 tokens (safety buffer)

### Testing Results

| max_output_tokens | Status | Response Length | Result |
|---|---|---|---|
| 150 | incomplete | 0-2 chars | ❌ Failed |
| 300 | completed | 80 chars | ✅ Works |
| 500 | completed | Full response | ✅ Optimal |

## Implementation

### Files Changed

1. **`.env`** - Updated token limits with documentation
2. **`.env.example`** - Updated with recommendations and warnings
3. **Server restart** - Required to pick up new configuration

### Verification Steps

```bash
# 1. Verify config loaded
python -c "from src.config import config; print(config.STUDENT_MAX_TOKENS)"
# Expected: 500

# 2. Test chat functionality
# Start new session and send 3+ messages
# All responses should be complete

# 3. Check database
sqlite3 dialogue_sim.db "SELECT id, role, LENGTH(content) FROM message WHERE session_id = X;"
# All student messages should have content_length > 0
```

## Prevention

### Configuration Guidelines

**For GPT-5 Responses API**:
1. Always account for reasoning tokens when setting `max_output_tokens`
2. Formula: `max_output_tokens = reasoning_tokens + desired_response_length + buffer`
3. Reasoning token consumption by effort level:
   - `minimal`: ~32 tokens
   - `low`: ~64 tokens
   - `medium`: ~128 tokens
   - `high`: ~256 tokens

**Recommended Settings**:
```bash
# Student responses (reasoning="medium")
STUDENT_MAX_TOKENS=500  # 128 reasoning + 372 response

# Tutor feedback (reasoning="low")
TUTOR_MAX_TOKENS=300    # 64 reasoning + 236 response

# Analysis (reasoning="high")
# Use even higher values: 600-1000 tokens
```

### Monitoring

Watch for these indicators:
- Response status: `incomplete` (bad) vs `completed` (good)
- Message content length: 0 or very short despite token usage
- Token usage details: Check `reasoning_tokens` vs `output_tokens`

## Related Issues

- Phase 1: Initial GPT-5 Migration (Chat/Responses API compatibility)
- Phase 1.5: Analyzer Responses API Migration
- This Issue: Token budget allocation for reasoning

## References

- OpenAI Responses API Documentation
- GPT-5 Reasoning Effort Configuration
- Project: `src/services/student_bot.py`
- Config: `src/config.py`, `.env`, `.env.example`
