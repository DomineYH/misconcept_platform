# GPT-5.1 Model Support Guide

## Overview

**Excellent News!** The Misconception Dialogue Simulator codebase
**already supports GPT-5.1** through existing conditional logic
implemented in all service files. No code changes are required!

This guide helps you enable and migrate to GPT-5.1 models.

## ✅ Compliance Status (Updated 2025-11-18)

All service files now use correct GPT-5 API parameters:
- ✅ `max_output_tokens` (was: max_completion_tokens)
- ✅ Responses API endpoint
- ✅ Reasoning effort configuration
- ✅ GPT-5/5.1 models only

### Migration Completed (Phase 1 & 1.5)
- student_bot.py: ✅ Responses API (max_output_tokens)
- misconception_analyzer.py: ✅ Responses API (max_output_tokens)
- tutor_bot.py: ✅ Responses API (max_output_tokens)
- analyzer.py: ✅ Responses API (max_output_tokens, Phase 1.5)

## Supported Models (Responses API)

**All services now use Responses API** (as of Phase 1.5)

### Primary Models (권장)
- **`gpt-5`**: GPT-5 base model
- **`gpt-5.1`**: GPT-5.1 Thinking (adaptive reasoning)
- **`gpt-5.1-chat-latest`**: GPT-5.1 Instant (fast)

### Fallback Models (지원)
- **`gpt-4-turbo`**: GPT-4 Turbo (Responses API compatible)

**Note**: Responses API does not support GPT-3.5 models.
Use GPT-4 Turbo as fallback if GPT-5 access unavailable.

## Key Differences: GPT-5.1 vs GPT-4

### Temperature Behavior

**GPT-4/3.5**: Supports configurable temperature (0.0-2.0)
**GPT-5/5.1**: Fixed temperature=1.0 (cannot be configured)

**Already Handled!** The codebase automatically omits temperature
parameter for GPT-5 models:

```python
# Pattern in all service files using Responses API:
input_messages = [{"role": "developer", "content": system_prompt}]
# ... build message history ...

response = await self.client.responses.create(
    model=self.model,
    input=input_messages,
    max_output_tokens=self.max_tokens,  # Correct parameter for GPT-5
    reasoning={"effort": self.reasoning_effort},
)
```

### API Parameters (Responses API - All Services)

**All services use Responses API** with model-specific handling:

| Parameter | GPT-5/5.1 | GPT-4 Turbo |
|-----------|-----------|------------|
| `temperature` | Fixed 1.0 (auto-omitted) | Fixed 1.0 (ignored) |
| `max_output_tokens` | Required ✅ | Required ✅ |
| `reasoning` | `{"effort": "low/medium/high"}` ✅ | Ignored |
| `modalities` | `["text"]` ✅ | `["text"]` ✅ |

**Note**: Temperature is NOT configurable in Responses API.

## Quick Start: Enable GPT-5.1 Today

### 1. Update Environment Variables

**File: `.env`**
```bash
# Option 1: GPT-5.1 Instant (fast, conversational)
CHAT_MODEL=gpt-5.1-chat-latest

# Option 2: GPT-5.1 Thinking (adaptive reasoning)
CHAT_MODEL=gpt-5.1

# For analysis tasks (optional)
ANALYSIS_MODEL=gpt-5.1
```

### 2. Restart Application

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Test with One Scenario

1. Open admin panel: http://localhost:8000/admin/scenarios
2. Create test scenario with GPT-5.1 model
3. Run dialogue session to verify functionality

## Migration Steps

### Gradual Rollout (Recommended)

**Phase 1: Test Environment**
```bash
# 1. Update .env file
CHAT_MODEL=gpt-5.1-chat-latest

# 2. Run integration tests
pytest tests/integration/test_scenario_bot_config.py -v

# 3. Manual testing
# - Create test scenario
# - Run dialogue session
# - Verify response quality
```

**Phase 2: Production Migration**
```bash
# 1. Monitor API costs (see Cost Considerations below)
# 2. Update production .env
# 3. Gradual rollout by scenario:
#    - Use scenario-specific model overrides
#    - Monitor quality and costs
#    - Expand to all scenarios
```

### Scenario-Specific Models

You can configure different models per scenario:

1. Admin Panel → Scenarios → Edit Scenario
2. Set **Chat Model**: `gpt-5.1-chat-latest` or `gpt-4-turbo`
3. Temperature setting ignored for GPT-5.1 (uses fixed 1.0)

**Priority Order**:
- Scenario-specific model > `.env` CHAT_MODEL

## Technical Details

### Affected Service Files

All files already support GPT-5.1 (no changes needed):

1. **`src/services/student_bot.py:118-119`**
2. **`src/services/tutor_bot.py:199-200`**
3. **`src/services/analyzer.py:101-102`**
4. **`src/services/misconception_analyzer.py:99-100`**

### Configuration Files

**`.env.example`**: Updated with GPT-5.1 documentation
**`src/config.py`**: Comments clarify supported models
**`tests/.../test_scenario_bot_config.py`**: GPT-5.1 test
coverage

## Cost Considerations

### Monitoring API Usage

**Database Table**: `api_usage`
```sql
SELECT model, COUNT(*), AVG(cost), SUM(cost)
FROM api_usage
GROUP BY model
ORDER BY created_at DESC;
```

### Cost Comparison (Hypothetical)

GPT-5.1 pricing may differ from GPT-4. Monitor your usage:

```bash
# Check recent API costs
sqlite3 dialogue_sim.db "SELECT * FROM api_usage
ORDER BY created_at DESC LIMIT 10;"
```

### Cost Optimization Tips

1. **Model Selection**:
   - Use `gpt-5.1-chat-latest` for speed
   - Use `gpt-4-turbo` for critical scenarios

2. **Token Limits**:
   - Adjust `STUDENT_MAX_TOKENS` and `TUTOR_MAX_TOKENS` in `.env`
   - Lower values = lower costs

3. **Scenario-Specific Tuning**:
   - High-stakes scenarios: GPT-5.1 Thinking
   - Practice scenarios: GPT-4 Turbo (cost-effective)

## Troubleshooting

### Error: "Unsupported parameter: temperature"

**Cause**: Temperature parameter sent to GPT-5.1 model

**Solution**: Verify model name starts with "gpt-5"
```python
# Correct: gpt-5.1-chat-latest, gpt-5.1, gpt-5
# Incorrect: GPT-5.1, gpt51, gpt_5_1
```

### Error: "Model not found"

**Cause**: GPT-5.1 not available for your OpenAI account

**Solution**:
1. Check OpenAI account tier and access
2. Verify API key has GPT-5.1 permissions
3. Fallback to `gpt-4-turbo` temporarily

### Unexpected Response Variability

**Cause**: GPT-5.1 uses fixed temperature=1.0 (higher than GPT-4
defaults)

**Expected Behavior**: Slightly more creative/varied responses

**Solution**:
- This is normal for GPT-5.1
- Use GPT-4 for highly deterministic scenarios
- Adjust scenario prompts for consistency

## Testing

### Automated Tests

```bash
# Run all integration tests
pytest tests/integration/test_scenario_bot_config.py -v

# Test specific model (GPT-5.1 included in parametrized tests)
pytest tests/integration/test_scenario_bot_config.py::test_create_scenario_with_valid_models -v
```

### Manual Testing Checklist

- [ ] Create scenario with `gpt-5.1-chat-latest`
- [ ] Run dialogue session (>5 exchanges)
- [ ] Verify student bot responses
- [ ] Check tutor interventions
- [ ] Verify API usage logged correctly
- [ ] Compare response quality vs GPT-4
- [ ] Monitor response times

## Best Practices

### When to Use GPT-5.1

**Recommended**:
- Dialogue-heavy scenarios (GPT-5.1 Instant)
- Complex reasoning tasks (GPT-5.1 Thinking)
- Scenarios requiring adaptive responses

**Not Recommended**:
- Highly deterministic scenarios (use GPT-4 Turbo for consistency)

### Configuration Strategy

```bash
# .env defaults (Responses API compatible only)
CHAT_MODEL=gpt-5
ANALYSIS_MODEL=gpt-5

# Alternative: Use GPT-4 Turbo as fallback
# CHAT_MODEL=gpt-4-turbo
# ANALYSIS_MODEL=gpt-4-turbo
```

**Then**: Override per scenario as needed (GPT-5.1 for advanced reasoning)

### Monitoring

1. **Response Quality**:
   - Compare GPT-5.1 vs GPT-4 responses
   - A/B test with users

2. **API Costs**:
   - Weekly cost reports
   - Set budget alerts

3. **Performance**:
   - Monitor response times
   - Track error rates

## FAQ

### Q: Do I need to modify any code?
**A**: No! Code already supports GPT-5.1 through conditional logic.

### Q: Will existing scenarios break?
**A**: No. Backward compatible. GPT-4/3.5 scenarios continue
working.

### Q: Can I mix models?
**A**: Yes. Use `.env` for defaults, override per scenario.

### Q: What about temperature settings?
**A**: GPT-5.1 ignores temperature (uses fixed 1.0). GPT-4/3.5
respect configured values.

### Q: How do I revert to GPT-4?
**A**: Change `.env` CHAT_MODEL back to `gpt-4-turbo`.
Restart app.

### Q: Is there a performance difference?
**A**: GPT-5.1 Instant is optimized for conversational speed.
Test for your use case.

## Additional Resources

### OpenAI Documentation
- Model Specifications: https://platform.openai.com/docs/models
- API Reference: https://platform.openai.com/docs/api-reference
- Pricing: https://openai.com/pricing

### Internal Documentation
- `CLAUDE.md`: Development guidelines
- `src/db/migrations/README.md`: Schema migration best practices
- `tests/contract/test_schema_integrity.py`: Schema validation

## Support

For issues or questions:
1. Check this guide first
2. Review error logs in `dialogue_sim.db` (api_usage table)
3. Test with GPT-4 to isolate model-specific issues
4. Consult OpenAI documentation for model behavior

## Summary

**Ready to Use**: No code changes needed for GPT-5.1 support!

**Steps**:
1. Update `.env` with GPT-5.1 model name
2. Restart application
3. Test with one scenario
4. Monitor costs and quality
5. Gradually roll out to all scenarios

**Key Points**:
- All 4 services use Responses API (Phase 1 & 1.5 complete)
- Temperature fixed at 1.0 (not configurable)
- GPT-5/5.1 primary, GPT-4 Turbo fallback
- GPT-3.5 NOT supported (Responses API limitation)
- 100% API consistency across all services
- Scenario-specific model overrides supported
