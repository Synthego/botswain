# AWS Bedrock SDK Migration Design

**Date:** 2026-03-09
**Author:** Claude Code
**Status:** Approved
**Target:** Botswain v1.1

## Executive Summary

Migrate Botswain's LLM integration from subprocess-based Claude CLI to AWS Bedrock SDK using the official Anthropic Python SDK. This eliminates process nesting issues, improves reliability, and adds comprehensive token usage monitoring.

## Problem Statement

**Current Issues:**
- Claude CLI subprocess calls fail when running inside Claude Code ("nesting" error)
- No token usage tracking or cost visibility
- Fragile error handling with stdout/stderr parsing
- No production-grade retry/timeout logic

**Impact:**
- Cannot use Botswain CLI inside Claude Code development environment
- No visibility into token costs or usage patterns
- Unreliable error messages for users
- Difficult to optimize for cost

## Goals

1. **Primary:** Replace Claude CLI with AWS Bedrock SDK
2. **Secondary:** Add comprehensive token usage monitoring
3. **Tertiary:** Maintain backwards compatibility with CLI provider

**Non-Goals:**
- Adding LangChain (deferred for later)
- Multi-model support beyond Claude
- Streaming responses (future enhancement)

## Architecture

### Current State
```
User Question → ClaudeCLIProvider → subprocess.run(['claude']) → Parse stdout → Intent
```

### Proposed State
```
User Question → BedrockProvider → AnthropicBedrock.messages.create() → Intent
                                   ↓
                                   Token Usage → QueryLog
```

### Component Overview

**Unchanged:**
- `BaseEntity` abstraction
- `QueryExecutor` logic
- `EntityRegistry` pattern
- API views and serializers

**New:**
- `BedrockProvider` class
- Token tracking fields in `QueryLog`
- Token usage management commands
- Cost calculation utilities

**Modified:**
- `LLMProviderFactory` default changes from `claude_cli` to `bedrock`
- `requirements.txt` adds `anthropic[bedrock]`

## Design Details

### 1. BedrockProvider Implementation

**File:** `core/llm/bedrock.py`

```python
from anthropic import AnthropicBedrock
from .provider import LLMProvider
import json

class BedrockProvider(LLMProvider):
    """AWS Bedrock implementation using Anthropic SDK"""

    def __init__(
        self,
        model: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        max_intent_tokens: int = 500,
        max_response_tokens: int = 1000,
        timeout: float = 30.0
    ):
        self.client = AnthropicBedrock(
            timeout=timeout,
            max_retries=2
        )
        self.model = model
        self.max_intent_tokens = max_intent_tokens
        self.max_response_tokens = max_response_tokens

    def parse_intent(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse natural language into structured intent"""
        prompt = self._build_intent_prompt(question, context)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_intent_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract response and token usage
        response_text = message.content[0].text
        cleaned = self._strip_markdown_json(response_text)

        try:
            intent = json.loads(cleaned)
            # Attach token usage for logging
            intent['_tokens'] = {
                'input': message.usage.input_tokens,
                'output': message.usage.output_tokens,
                'total': message.usage.input_tokens + message.usage.output_tokens
            }
            return intent
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON from LLM: {cleaned[:200]}")

    def format_response(self, query_results: Any, original_question: str) -> str:
        """Format query results into natural language"""
        prompt = self._build_response_prompt(query_results, original_question)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_response_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        return message.content[0].text
```

**Key Features:**
- Uses inference profile ID: `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (not direct model ID)
- Configurable token limits per operation (intent parsing vs response formatting)
- Built-in retry logic (2 retries with exponential backoff)
- 30-second timeout protection

### 2. Model Selection and Access

**Verified Working Models (us-west-2):**
- ✅ `us.anthropic.claude-sonnet-4-5-20250929-v1:0` - Sonnet 4.5 (default)
- ✅ `us.anthropic.claude-3-5-haiku-20241022-v1:0` - Haiku 3.5 (cost optimization)

**Critical Discovery:**
- Must use **inference profile IDs** with `us.` prefix
- Direct model IDs (e.g., `anthropic.claude-3-5-sonnet-20240620-v1:0`) fail with "Access denied"
- Newer models require inference profiles for invocation

**Configuration:**
```python
# settings/base.py
BOTSWAIN_BEDROCK_MODEL = os.getenv(
    'BOTSWAIN_BEDROCK_MODEL',
    'us.anthropic.claude-sonnet-4-5-20250929-v1:0'
)
```

### 3. Token Limits and Cost Control

**Limits by Operation:**

| Operation | Max Tokens | Rationale |
|-----------|------------|-----------|
| User input | 1000 chars | ~750 tokens, prevents abuse |
| Intent parsing | 500 | Intent is tiny JSON (~200 tokens typical) |
| Response formatting | 1000 | Concise natural language (~750 words max) |
| Query results | 1000 rows | Already enforced by SafetyValidator |

**Cost Projection (Sonnet 4.5):**
- Input: $3/MTok, Output: $15/MTok
- Typical query: ~1500 input + ~500 output tokens = $0.012
- 10,000 queries/month: ~$120/month
- 100,000 queries/month: ~$1,200/month

**Safety Mechanisms:**
```python
# In QueryRequestSerializer
question = serializers.CharField(
    required=True,
    max_length=1000,
    error_messages={'max_length': 'Question too long (max 1000 characters)'}
)
```

### 4. Token Usage Monitoring

**Database Schema Changes:**

```python
# Add to QueryLog model
class QueryLog(models.Model):
    # ... existing fields ...

    # Token usage tracking
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    total_tokens = models.IntegerField(null=True, blank=True)
    estimated_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=['executed_at', 'total_tokens']),  # For usage reports
        ]
```

**Token Capture in API View:**

```python
# In QueryAPIView
intent = llm_provider.parse_intent(question, context)

# Extract tokens from intent (BedrockProvider attaches them)
tokens = intent.pop('_tokens', None)

# ... execute query ...

# Log with token data
logger.log(
    user=user,
    intent=intent,
    response=response_data,
    input_tokens=tokens['input'] if tokens else None,
    output_tokens=tokens['output'] if tokens else None,
    total_tokens=tokens['total'] if tokens else None,
    estimated_cost_usd=calculate_cost(tokens) if tokens else None
)
```

**Cost Calculation:**

```python
# utils/cost.py
def calculate_bedrock_cost(input_tokens: int, output_tokens: int, model: str) -> Decimal:
    """Calculate estimated cost in USD"""
    # Sonnet 4.5 pricing (as of 2026-03)
    PRICING = {
        'us.anthropic.claude-sonnet-4-5-20250929-v1:0': {
            'input_per_mtok': Decimal('3.00'),
            'output_per_mtok': Decimal('15.00'),
        },
        'us.anthropic.claude-3-5-haiku-20241022-v1:0': {
            'input_per_mtok': Decimal('0.25'),
            'output_per_mtok': Decimal('1.25'),
        },
    }

    rates = PRICING.get(model, PRICING['us.anthropic.claude-sonnet-4-5-20250929-v1:0'])
    input_cost = (Decimal(input_tokens) / 1_000_000) * rates['input_per_mtok']
    output_cost = (Decimal(output_tokens) / 1_000_000) * rates['output_per_mtok']
    return input_cost + output_cost
```

**Management Commands:**

```bash
# Token usage report
python manage.py token_usage_report --days 7

# Output:
# Token Usage Report (Last 7 days)
# ====================================
# Total Queries: 1,247
# Total Tokens: 1,834,521 (Input: 1,123,401 | Output: 711,120)
# Avg Tokens/Query: 1,471
# Estimated Cost: $47.23
#
# Daily Breakdown:
# 2026-03-09: 234 queries, 345,231 tokens, $8.92
# 2026-03-08: 189 queries, 278,901 tokens, $7.21
# ...
#
# Top 5 Most Expensive Queries:
# 1. "Show all instruments with status..." - 4,521 tokens ($0.12)
# 2. "List every synthesizer and their..." - 3,892 tokens ($0.10)

# Optimization analysis
python manage.py analyze_token_usage

# Output:
# Token Usage Analysis
# ====================
#
# Model: us.anthropic.claude-sonnet-4-5-20250929-v1:0
# Period: Last 30 days
#
# Optimization Opportunities:
# 1. 45% of queries use <200 tokens → Could use Haiku (10x cheaper)
#    Potential savings: ~$150/month
#
# 2. 12% of queries exceed 2000 tokens → May need limit reduction
#    Queries: ["Show all instruments...", "List every..."]
#
# 3. Entity "instrument" averages 1,800 tokens
#    Consider: Caching common queries, reducing result verbosity
```

**API Endpoint:**

```python
# GET /api/stats/tokens
{
  "today": {
    "queries": 124,
    "input_tokens": 87234,
    "output_tokens": 45107,
    "total_tokens": 132341,
    "cost_usd": 4.23
  },
  "this_week": {
    "queries": 1247,
    "input_tokens": 1123401,
    "output_tokens": 711120,
    "total_tokens": 1834521,
    "cost_usd": 47.23
  },
  "this_month": {
    "queries": 5234,
    "input_tokens": 4234123,
    "output_tokens": 3000000,
    "total_tokens": 7234123,
    "cost_usd": 189.45
  }
}
```

### 5. Error Handling and Resilience

**Error Types:**

1. **Authentication Errors:**
```python
from botocore.exceptions import ClientError

try:
    message = self.client.messages.create(...)
except ClientError as e:
    if e.response['Error']['Code'] == 'UnauthorizedException':
        raise ValueError(
            "AWS credentials invalid or expired. "
            "Run: aws sso login --profile admin"
        )
```

2. **Model Access Errors:**
```python
except ClientError as e:
    if 'AccessDeniedException' in str(e):
        raise ValueError(
            f"Model {self.model} not accessible. "
            f"Use inference profile IDs with 'us.' prefix. "
            f"Working models: us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )
```

3. **Rate Limiting:**
```python
# Handled automatically by SDK with exponential backoff
# Default: 2 retries, max 10s wait
# Can configure:
client = AnthropicBedrock(max_retries=3)
```

4. **Timeout Protection:**
```python
client = AnthropicBedrock(timeout=30.0)  # 30 second timeout
```

5. **Invalid LLM Responses:**
```python
try:
    intent = json.loads(cleaned_output)
    # Validate required fields
    required_fields = ['entity', 'intent_type']
    missing = [f for f in required_fields if f not in intent]
    if missing:
        raise ValueError(f"LLM response missing fields: {missing}")
except json.JSONDecodeError:
    raise ValueError(f"LLM returned invalid JSON: {cleaned_output[:200]}")
```

**Logging Strategy:**
```python
import logging
logger = logging.getLogger('botswain.llm')

# Log all LLM calls
logger.info(
    "LLM call",
    extra={
        'model': self.model,
        'operation': 'parse_intent',
        'input_tokens': usage.input_tokens,
        'output_tokens': usage.output_tokens,
        'latency_ms': int(latency * 1000),
        'request_id': message.id  # For Bedrock support tickets
    }
)
```

### 6. Testing Strategy

**Unit Tests:**

```python
# tests/test_bedrock_provider.py
def test_bedrock_provider_parse_intent(mocker):
    """Test intent parsing with mocked Bedrock client"""
    mock_client = mocker.Mock()
    mock_response = mocker.Mock(
        content=[mocker.Mock(text='{"entity": "synthesizer", "intent_type": "query"}')],
        usage=mocker.Mock(input_tokens=100, output_tokens=50),
        id='req_123'
    )
    mock_client.messages.create.return_value = mock_response

    provider = BedrockProvider()
    provider.client = mock_client

    intent = provider.parse_intent("How many synthesizers?", {'entities': {}})

    assert intent['entity'] == 'synthesizer'
    assert intent['_tokens']['total'] == 150
    mock_client.messages.create.assert_called_once()

def test_token_limits_enforced():
    """Verify token limits are passed to API"""
    provider = BedrockProvider(max_intent_tokens=500)
    # Verify max_tokens=500 in API call

def test_invalid_json_handling():
    """Test error handling for malformed LLM output"""
    # Mock LLM returning non-JSON
    # Verify ValueError with helpful message

def test_authentication_error():
    """Test AWS credential failure handling"""
    # Mock ClientError with UnauthorizedException
    # Verify helpful error message with fix instructions
```

**Integration Tests:**

```python
@pytest.mark.skipif(not os.getenv('TEST_REAL_BEDROCK'), reason="Requires AWS credentials")
def test_real_bedrock_integration():
    """Integration test with real AWS Bedrock"""
    provider = BedrockProvider()
    intent = provider.parse_intent(
        "How many synthesizers are online?",
        {'entities': {'synthesizer': 'RNA synthesis instruments'}}
    )

    assert 'entity' in intent
    assert intent['_tokens']['total'] > 0
    assert intent['_tokens']['input'] > 0
    assert intent['_tokens']['output'] > 0

def test_token_logging_to_database():
    """Verify tokens are logged to QueryLog"""
    # Make API request
    response = client.post('/api/query', {'question': 'test'})

    # Verify QueryLog entry
    log = QueryLog.objects.latest('executed_at')
    assert log.input_tokens > 0
    assert log.output_tokens > 0
    assert log.total_tokens == log.input_tokens + log.output_tokens
    assert log.estimated_cost_usd is not None
```

**Backwards Compatibility:**

```python
def test_factory_defaults_to_bedrock():
    """Verify factory creates BedrockProvider by default"""
    provider = LLMProviderFactory.create()
    assert isinstance(provider, BedrockProvider)

def test_factory_supports_cli_fallback():
    """Verify CLI provider still available"""
    provider = LLMProviderFactory.create('claude_cli')
    assert isinstance(provider, ClaudeCLIProvider)
```

**Test Coverage Goals:**
- Core provider logic: 90%+
- Error handling: 100%
- Token tracking: 100%
- Integration: 80%+

### 7. Migration and Deployment

**Phase 1: Implementation**
1. Add `anthropic[bedrock]==0.21.0` to requirements.txt
2. Create `core/llm/bedrock.py` with BedrockProvider
3. Add token fields to QueryLog model (nullable, no downtime)
4. Create migration: `0002_querylog_add_token_tracking.py`
5. Update `LLMProviderFactory` to default to `bedrock`
6. Add cost calculation utilities
7. Create management commands: `token_usage_report`, `analyze_token_usage`
8. All tests passing

**Phase 2: Local Testing**
1. Test with local BARB database
2. Test with production replica (VPN)
3. Verify token logging works
4. Compare Bedrock vs CLI response quality
5. Verify error messages helpful

**Phase 3: Deployment**
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run migrations (safe - adds nullable fields)
python manage.py migrate

# 3. Deploy code (Bedrock now default)
# No service restart needed if using gunicorn with reload

# 4. Verify
python manage.py check_bedrock_access  # New management command
```

**Phase 4: Monitoring (1 week)**
```bash
# Daily checks
python manage.py token_usage_report --days 1

# Weekly analysis
python manage.py analyze_token_usage

# Watch for:
# - Error rate spike
# - Cost exceeding budget
# - Token usage patterns
```

**Phase 5: Optimization (ongoing)**
- Identify queries suitable for Haiku (45% cost savings potential)
- Add caching for common queries
- Refine token limits based on actual usage

**Rollback Plan:**

If issues arise:
```bash
# Option 1: Environment variable (no code change)
export BOTSWAIN_LLM_PROVIDER=claude_cli

# Option 2: Settings override
# In settings/local.py or production:
BOTSWAIN_LLM_PROVIDER = 'claude_cli'

# Option 3: Factory override in code
provider = LLMProviderFactory.create('claude_cli')
```

**Configuration Files:**

```python
# .env.example
BOTSWAIN_LLM_PROVIDER=bedrock
BOTSWAIN_BEDROCK_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BOTSWAIN_MAX_INPUT_CHARS=1000
BOTSWAIN_MAX_INTENT_TOKENS=500
BOTSWAIN_MAX_RESPONSE_TOKENS=1000
BOTSWAIN_DAILY_BUDGET_USD=50.00
AWS_REGION=us-west-2
```

## Dependencies

**New:**
- `anthropic[bedrock]>=0.21.0` - Official Anthropic SDK with Bedrock support

**Existing (unchanged):**
- `boto3` - Already present for AWS access
- `Django>=4.2.9`
- `djangorestframework>=3.14.0`

## Success Metrics

**Technical:**
- ✅ Zero nesting errors (can use Botswain in Claude Code)
- ✅ <3s average response time
- ✅ <1% error rate
- ✅ 100% token tracking coverage

**Cost:**
- 🎯 <$200/month for 10k queries (well under budget)
- 🎯 Token usage visibility within 1 day of deployment
- 🎯 Cost optimization opportunities identified within 1 week

**Quality:**
- ✅ Response quality equivalent or better than CLI
- ✅ Helpful error messages with actionable fixes
- ✅ Audit logs include token data for all queries

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| AWS Bedrock outage | High | Low | Keep ClaudeCLIProvider as fallback |
| Cost overrun | Medium | Low | Token limits, daily budget alerts, monitoring dashboard |
| Model access revoked | High | Very Low | Document model access requirements, alert on auth failures |
| Response quality degradation | Medium | Low | A/B testing during rollout, rollback plan ready |
| Token logging breaks | Low | Low | Nullable fields, graceful degradation if logging fails |

## Future Enhancements

**Not in this design (deferred):**
- Streaming responses for long queries
- Multi-model support (GPT-4, etc.)
- Response caching layer
- LangChain integration for complex workflows
- Fine-tuned models for Synthego domain

## Alternatives Considered

1. **Keep Claude CLI**
   - ❌ Nesting issues persist
   - ❌ No token visibility
   - ❌ Fragile subprocess error handling

2. **Use Anthropic API directly** (not Bedrock)
   - ✅ Same quality and features
   - ❌ Separate billing (not on AWS bill)
   - ❌ Different credential management
   - ❌ Doesn't match AWS infrastructure pattern

3. **Full LangChain adoption**
   - ❌ Overkill for current use case
   - ❌ Heavy dependency, frequent breaking changes
   - ⏸️ Deferred to later when needed

## References

- AWS Bedrock Models: `/home/danajanezic/.claude/projects/-home-danajanezic-code/memory/aws-bedrock-models.md`
- Anthropic SDK Docs: https://docs.anthropic.com/en/api/client-sdks
- Bedrock Pricing: https://aws.amazon.com/bedrock/pricing/
- BARB Production Access: `/home/danajanezic/code/.worktrees/botswain-implementation/botswain/BARB_PROD_ACCESS.md`

## Approval

- [x] Architecture approved
- [x] Components approved
- [x] Data flow approved
- [x] Model access verified
- [x] Token monitoring strategy approved
- [x] Error handling approved
- [x] Testing strategy approved
- [x] Migration plan approved

**Ready for implementation.**
