# AWS Bedrock SDK Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace subprocess-based Claude CLI with AWS Bedrock SDK, add token usage monitoring

**Architecture:** Create BedrockProvider using Anthropic SDK with inference profile IDs, extend QueryLog for token tracking, add management commands for cost analysis

**Tech Stack:** anthropic[bedrock], boto3, Django 4.2.9, pytest

---

## Task 1: Add Dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Add Anthropic Bedrock SDK**

Update `requirements.txt`:
```txt
Django==4.2.9
djangorestframework==3.14.0
psycopg2-binary==2.9.9
django-redis==5.4.0
celery==5.3.4
redis==5.0.1
python-dotenv==1.0.0
requests==2.31.0
anthropic[bedrock]==0.21.0

# Testing
pytest==7.4.3
pytest-django==4.7.0
pytest-mock==3.12.0
pytest-cov==4.1.0
factory-boy==3.3.0
```

**Step 2: Install dependencies**

Run: `venv/bin/pip install -r requirements.txt`
Expected: "Successfully installed anthropic-0.21.0 ..."

**Step 3: Verify installation**

Run: `venv/bin/python -c "from anthropic import AnthropicBedrock; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add anthropic[bedrock] SDK for Bedrock integration"
```

---

## Task 2: Create BedrockProvider with TDD

**Files:**
- Create: `core/llm/bedrock.py`
- Create: `tests/test_bedrock_provider.py`

**Step 1: Write failing test for parse_intent**

Create `tests/test_bedrock_provider.py`:
```python
import json
import pytest
from unittest.mock import Mock
from core.llm.bedrock import BedrockProvider


def test_bedrock_provider_parse_intent(mocker):
    """Test intent parsing extracts JSON and tokens"""
    # Mock the Bedrock client
    mock_client = mocker.Mock()
    mock_message = mocker.Mock()
    mock_message.content = [mocker.Mock(text='{"entity": "synthesizer", "intent_type": "query"}')]
    mock_message.usage = mocker.Mock(input_tokens=100, output_tokens=50)
    mock_message.id = 'req_123'
    mock_client.messages.create.return_value = mock_message

    provider = BedrockProvider()
    provider.client = mock_client

    intent = provider.parse_intent(
        "How many synthesizers?",
        {'entities': {'synthesizer': 'RNA instruments'}}
    )

    assert intent['entity'] == 'synthesizer'
    assert intent['intent_type'] == 'query'
    assert intent['_tokens']['input'] == 100
    assert intent['_tokens']['output'] == 50
    assert intent['_tokens']['total'] == 150


def test_bedrock_provider_format_response(mocker):
    """Test response formatting"""
    mock_client = mocker.Mock()
    mock_message = mocker.Mock()
    mock_message.content = [mocker.Mock(text='Found 5 synthesizers online')]
    mock_client.messages.create.return_value = mock_message

    provider = BedrockProvider()
    provider.client = mock_client

    result = provider.format_response(
        {'count': 5, 'results': []},
        'How many synthesizers?'
    )

    assert result == 'Found 5 synthesizers online'


def test_bedrock_provider_strips_markdown_json(mocker):
    """Test markdown code block stripping"""
    mock_client = mocker.Mock()
    mock_message = mocker.Mock()
    # LLM returns JSON wrapped in markdown
    mock_message.content = [mocker.Mock(text='```json\n{"entity": "instrument"}\n```')]
    mock_message.usage = mocker.Mock(input_tokens=50, output_tokens=25)
    mock_client.messages.create.return_value = mock_message

    provider = BedrockProvider()
    provider.client = mock_client

    intent = provider.parse_intent("test", {})

    assert intent['entity'] == 'instrument'
```

**Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_bedrock_provider.py -v`
Expected: ModuleNotFoundError: No module named 'core.llm.bedrock'

**Step 3: Create BedrockProvider implementation**

Create `core/llm/bedrock.py`:
```python
import json
import re
from typing import Dict, Any
from anthropic import AnthropicBedrock
from .provider import LLMProvider


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
        """Parse natural language into structured intent using Bedrock"""
        prompt = self._build_intent_prompt(question, context)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_intent_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract response text
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
            raise ValueError(f"Invalid JSON from Claude: {cleaned[:200]}")

    def format_response(self, query_results: Any, original_question: str) -> str:
        """Format query results into natural language using Bedrock"""
        prompt = self._build_response_prompt(query_results, original_question)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_response_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        return message.content[0].text

    def _build_intent_prompt(self, question: str, context: Dict[str, Any]) -> str:
        """Build prompt for intent parsing"""
        entities_desc = "\n".join([
            f"- {name}: {desc}"
            for name, desc in context.get('entities', {}).items()
        ])

        return f"""You are a factory query assistant. Parse this question into structured JSON.

Available entities:
{entities_desc}

Question: {question}

Return ONLY valid JSON with this structure:
{{
  "entity": "entity_name",
  "intent_type": "query|count|aggregate",
  "attributes": ["attr1", "attr2"],
  "filters": {{"key": "value"}},
  "sort": {{"field": "name", "direction": "asc"}},
  "limit": 10
}}
"""

    def _build_response_prompt(self, query_results: Any, original_question: str) -> str:
        """Build prompt for response formatting"""
        results_json = json.dumps(query_results, indent=2, default=str)

        return f"""You are a factory query assistant. Format these query results as a natural language response.

Original question: {original_question}

Query results:
{results_json}

Provide a concise, helpful natural language response."""

    def _strip_markdown_json(self, text: str) -> str:
        """Strip markdown code blocks from JSON response"""
        text = text.strip()

        # Pattern to match markdown code blocks
        pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
        match = re.search(pattern, text, re.DOTALL)

        if match:
            return match.group(1).strip()

        return text
```

**Step 4: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_bedrock_provider.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add core/llm/bedrock.py tests/test_bedrock_provider.py
git commit -m "feat: add BedrockProvider using Anthropic SDK

- Uses inference profile ID: us.anthropic.claude-sonnet-4-5-20250929-v1:0
- Configurable token limits per operation
- Extracts token usage from responses
- Strips markdown code blocks from JSON
- TDD: 3 passing tests
"
```

---

## Task 3: Add Token Tracking to QueryLog Model

**Files:**
- Modify: `core/models.py`
- Create: `core/migrations/0002_querylog_add_token_tracking.py`
- Create: `tests/test_token_tracking.py`

**Step 1: Write failing test for token fields**

Create `tests/test_token_tracking.py`:
```python
import pytest
from decimal import Decimal
from core.models import QueryLog
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_query_log_stores_token_usage():
    """Test QueryLog can store token usage data"""
    user = User.objects.create(username='testuser')

    log = QueryLog.objects.create(
        user=user,
        username='testuser',
        question='How many synthesizers?',
        intent={'entity': 'synthesizer'},
        entity='synthesizer',
        execution_time_ms=45,
        input_tokens=123,
        output_tokens=456,
        total_tokens=579,
        estimated_cost_usd=Decimal('0.012345')
    )

    assert log.input_tokens == 123
    assert log.output_tokens == 456
    assert log.total_tokens == 579
    assert log.estimated_cost_usd == Decimal('0.012345')


@pytest.mark.django_db
def test_query_log_token_fields_nullable():
    """Test token fields are optional (for CLI provider)"""
    user = User.objects.create(username='testuser')

    log = QueryLog.objects.create(
        user=user,
        username='testuser',
        question='test',
        intent={},
        entity='test',
        execution_time_ms=10
    )

    assert log.input_tokens is None
    assert log.output_tokens is None
    assert log.total_tokens is None
    assert log.estimated_cost_usd is None
```

**Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_token_tracking.py -v`
Expected: FAIL with "QueryLog() got unexpected keyword argument 'input_tokens'"

**Step 3: Add token fields to QueryLog model**

Modify `core/models.py`:
```python
from django.db import models
from django.contrib.auth.models import User


class QueryLog(models.Model):
    """Audit log of all queries"""

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField(max_length=255)
    question = models.TextField()
    intent = models.JSONField()
    entity = models.CharField(max_length=100, db_index=True)
    executed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    execution_time_ms = models.IntegerField()
    success = models.BooleanField(default=True, db_index=True)
    interface = models.CharField(max_length=20, default='api')
    cache_hit = models.BooleanField(default=False)

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
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['executed_at', 'entity']),
            models.Index(fields=['executed_at', 'total_tokens']),
        ]

    def __str__(self):
        return f"{self.username} - {self.entity} - {self.executed_at}"
```

**Step 4: Create migration**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.local venv/bin/python manage.py makemigrations core`
Expected: "Migrations for 'core': core/migrations/0002_querylog_add_token_tracking.py"

**Step 5: Run migration**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/python manage.py migrate`
Expected: "Applying core.0002_querylog_add_token_tracking... OK"

**Step 6: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_token_tracking.py -v`
Expected: 2 passed

**Step 7: Commit**

```bash
git add core/models.py core/migrations/0002_querylog_add_token_tracking.py tests/test_token_tracking.py
git commit -m "feat: add token tracking fields to QueryLog model

- Add input_tokens, output_tokens, total_tokens fields
- Add estimated_cost_usd field
- All fields nullable for backwards compatibility
- Add index on (executed_at, total_tokens) for reporting
"
```

---

## Task 4: Create Cost Calculation Utility

**Files:**
- Create: `core/utils/cost.py`
- Create: `tests/test_cost_calculation.py`

**Step 1: Write failing test for cost calculation**

Create `tests/test_cost_calculation.py`:
```python
import pytest
from decimal import Decimal
from core.utils.cost import calculate_bedrock_cost


def test_calculate_cost_sonnet_45():
    """Test cost calculation for Sonnet 4.5"""
    cost = calculate_bedrock_cost(
        input_tokens=1000,
        output_tokens=500,
        model='us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    )

    # Input: 1000/1M * $3 = $0.003
    # Output: 500/1M * $15 = $0.0075
    # Total: $0.0105
    assert cost == Decimal('0.0105')


def test_calculate_cost_haiku_35():
    """Test cost calculation for Haiku 3.5"""
    cost = calculate_bedrock_cost(
        input_tokens=1000,
        output_tokens=500,
        model='us.anthropic.claude-3-5-haiku-20241022-v1:0'
    )

    # Input: 1000/1M * $0.25 = $0.00025
    # Output: 500/1M * $1.25 = $0.000625
    # Total: $0.000875
    assert cost == Decimal('0.000875')


def test_calculate_cost_unknown_model_uses_default():
    """Test unknown model uses Sonnet pricing as default"""
    cost = calculate_bedrock_cost(
        input_tokens=1000,
        output_tokens=500,
        model='unknown-model'
    )

    # Should default to Sonnet 4.5 pricing
    assert cost == Decimal('0.0105')


def test_calculate_cost_zero_tokens():
    """Test zero tokens returns zero cost"""
    cost = calculate_bedrock_cost(
        input_tokens=0,
        output_tokens=0,
        model='us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    )

    assert cost == Decimal('0')
```

**Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_cost_calculation.py -v`
Expected: ModuleNotFoundError: No module named 'core.utils'

**Step 3: Create cost calculation utility**

Create `core/utils/__init__.py` (empty file)

Create `core/utils/cost.py`:
```python
from decimal import Decimal


def calculate_bedrock_cost(input_tokens: int, output_tokens: int, model: str) -> Decimal:
    """
    Calculate estimated cost in USD for Bedrock API call.

    Pricing as of 2026-03 (per million tokens):
    - Sonnet 4.5: $3 input, $15 output
    - Haiku 3.5: $0.25 input, $1.25 output
    """
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

    # Default to Sonnet pricing if model unknown
    rates = PRICING.get(
        model,
        PRICING['us.anthropic.claude-sonnet-4-5-20250929-v1:0']
    )

    input_cost = (Decimal(input_tokens) / Decimal('1000000')) * rates['input_per_mtok']
    output_cost = (Decimal(output_tokens) / Decimal('1000000')) * rates['output_per_mtok']

    return input_cost + output_cost
```

**Step 4: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_cost_calculation.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add core/utils/__init__.py core/utils/cost.py tests/test_cost_calculation.py
git commit -m "feat: add Bedrock cost calculation utility

- Calculate USD cost from token usage
- Support Sonnet 4.5 and Haiku 3.5 pricing
- Default to Sonnet pricing for unknown models
- TDD: 4 passing tests
"
```

---

## Task 5: Update AuditLogger to Capture Tokens

**Files:**
- Modify: `core/audit.py`
- Modify: `tests/test_audit_logger.py`

**Step 1: Write failing test for token logging**

Modify `tests/test_audit_logger.py`, add test:
```python
from decimal import Decimal
from core.utils.cost import calculate_bedrock_cost


@pytest.mark.django_db
def test_audit_logger_logs_tokens():
    """Test AuditLogger captures token usage"""
    logger = AuditLogger()

    intent = {
        'entity': 'synthesizer',
        '_tokens': {
            'input': 123,
            'output': 456,
            'total': 579
        }
    }

    response = {
        'success': True,
        'count': 5
    }

    log_entry = logger.log(
        user='testuser',
        intent=intent,
        response=response,
        execution_time=0.045,
        question='How many synthesizers?',
        interface='api'
    )

    assert log_entry.input_tokens == 123
    assert log_entry.output_tokens == 456
    assert log_entry.total_tokens == 579
    assert log_entry.estimated_cost_usd is not None
    assert log_entry.estimated_cost_usd > 0
```

**Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_audit_logger.py::test_audit_logger_logs_tokens -v`
Expected: FAIL (attributes not set)

**Step 3: Update AuditLogger to extract and log tokens**

Modify `core/audit.py`:
```python
from .models import QueryLog
from .utils.cost import calculate_bedrock_cost
from django.conf import settings


class AuditLogger:
    """Logs all queries for audit and monitoring"""

    def log(
        self,
        user: str,
        intent: dict,
        response: dict,
        execution_time: float,
        question: str = None,
        interface: str = 'api',
        cache_hit: bool = False
    ) -> QueryLog:
        """
        Log a query execution.

        Args:
            user: Username who made the query
            intent: Parsed intent dict
            response: Query response dict
            execution_time: Execution time in seconds
            question: Original user question
            interface: Interface used (api, cli, etc)
            cache_hit: Whether result was cached

        Returns:
            QueryLog instance
        """
        # Extract tokens from intent (BedrockProvider attaches them)
        tokens = intent.pop('_tokens', None)

        # Calculate cost if tokens available
        estimated_cost = None
        if tokens:
            model = getattr(settings, 'BOTSWAIN_BEDROCK_MODEL', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
            estimated_cost = calculate_bedrock_cost(
                input_tokens=tokens['input'],
                output_tokens=tokens['output'],
                model=model
            )

        log_entry = QueryLog.objects.create(
            username=user,
            question=question or intent.get('question', ''),
            intent=intent,
            entity=intent.get('entity', ''),
            execution_time_ms=int(execution_time * 1000),
            success=response.get('success', True),
            interface=interface,
            cache_hit=cache_hit,
            input_tokens=tokens['input'] if tokens else None,
            output_tokens=tokens['output'] if tokens else None,
            total_tokens=tokens['total'] if tokens else None,
            estimated_cost_usd=estimated_cost
        )

        return log_entry
```

**Step 4: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_audit_logger.py::test_audit_logger_logs_tokens -v`
Expected: PASS

**Step 5: Run all audit tests**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_audit_logger.py -v`
Expected: All passing

**Step 6: Commit**

```bash
git add core/audit.py tests/test_audit_logger.py
git commit -m "feat: update AuditLogger to capture token usage

- Extract _tokens from intent
- Calculate cost using cost utility
- Log input/output/total tokens
- Log estimated cost in USD
- Graceful handling when tokens not present (CLI provider)
"
```

---

## Task 6: Update LLMProviderFactory Default to Bedrock

**Files:**
- Modify: `core/llm/factory.py`
- Modify: `tests/test_llm_factory.py`

**Step 1: Write test for Bedrock as default**

Modify `tests/test_llm_factory.py`, add test:
```python
def test_factory_defaults_to_bedrock():
    """Test factory creates BedrockProvider by default"""
    from core.llm.bedrock import BedrockProvider

    provider = LLMProviderFactory.create()

    assert isinstance(provider, BedrockProvider)


def test_factory_supports_cli_override():
    """Test CLI provider still available via explicit selection"""
    provider = LLMProviderFactory.create('claude_cli')

    assert isinstance(provider, ClaudeCLIProvider)
```

**Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_llm_factory.py::test_factory_defaults_to_bedrock -v`
Expected: FAIL (AssertionError: not BedrockProvider)

**Step 3: Update factory to default to Bedrock**

Modify `core/llm/factory.py`:
```python
from typing import Dict, Type
from .provider import LLMProvider
from .claude_cli import ClaudeCLIProvider
from .bedrock import BedrockProvider


class LLMProviderFactory:
    """Factory for creating LLM provider instances"""

    _providers: Dict[str, Type[LLMProvider]] = {
        'bedrock': BedrockProvider,      # NEW - now default
        'claude_cli': ClaudeCLIProvider,  # Keep for compatibility
    }

    @classmethod
    def create(cls, provider_name: str = 'bedrock', **kwargs) -> LLMProvider:
        """
        Create an LLM provider instance.

        Args:
            provider_name: Provider to use ('bedrock' or 'claude_cli')
            **kwargs: Provider-specific arguments

        Returns:
            LLMProvider instance

        Raises:
            ValueError: If provider_name is unknown
        """
        provider_class = cls._providers.get(provider_name)
        if not provider_class:
            available = ', '.join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available providers: {available}"
            )
        return provider_class(**kwargs)

    @classmethod
    def list_providers(cls):
        """Return list of available provider names"""
        return list(cls._providers.keys())
```

**Step 4: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_llm_factory.py -v`
Expected: All passing

**Step 5: Commit**

```bash
git add core/llm/factory.py tests/test_llm_factory.py
git commit -m "feat: change LLMProviderFactory default to Bedrock

- Bedrock now default provider
- CLI provider still available via explicit selection
- Update factory docstring
- TDD: all factory tests passing
"
```

---

## Task 7: Update API View to Use Bedrock

**Files:**
- Modify: `api/views.py`
- Create: `tests/test_api_bedrock_integration.py`

**Step 1: Write integration test**

Create `tests/test_api_bedrock_integration.py`:
```python
import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from core.models import QueryLog


@pytest.mark.django_db
def test_api_logs_tokens_from_bedrock(mocker):
    """Test API captures token usage from BedrockProvider"""
    # Mock BedrockProvider to return tokens
    mock_provider = mocker.patch('api.views.LLMProviderFactory.create')
    mock_instance = mocker.Mock()

    # parse_intent returns intent with _tokens
    mock_instance.parse_intent.return_value = {
        'entity': 'synthesizer',
        'intent_type': 'query',
        'filters': {},
        '_tokens': {
            'input': 234,
            'output': 123,
            'total': 357
        }
    }

    mock_instance.format_response.return_value = 'Found 5 synthesizers'
    mock_provider.return_value = mock_instance

    client = APIClient()
    response = client.post('/api/query', {
        'question': 'How many synthesizers?',
        'format': 'natural'
    }, format='json')

    assert response.status_code == 200

    # Verify tokens were logged
    log = QueryLog.objects.latest('executed_at')
    assert log.input_tokens == 234
    assert log.output_tokens == 123
    assert log.total_tokens == 357
    assert log.estimated_cost_usd is not None
    assert log.estimated_cost_usd > Decimal('0')
```

**Step 2: Run test to verify current state**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_api_bedrock_integration.py -v`
Expected: Should pass (API view already uses factory, just need to verify)

**Step 3: Verify API view handles tokens correctly**

Check `api/views.py` - should already handle tokens via AuditLogger.
No code changes needed if test passes.

**Step 4: If test fails, update API view**

If test fails, modify `api/views.py` to ensure tokens flow through:
```python
# Existing code already correct - factory creates Bedrock by default
# AuditLogger extracts _tokens from intent
# No changes needed
```

**Step 5: Commit**

```bash
git add tests/test_api_bedrock_integration.py
git commit -m "test: add integration test for API token logging

- Verify API captures tokens from BedrockProvider
- Verify tokens logged to QueryLog
- Verify cost calculated
"
```

---

## Task 8: Add Token Usage Management Commands

**Files:**
- Create: `core/management/__init__.py`
- Create: `core/management/commands/__init__.py`
- Create: `core/management/commands/token_usage_report.py`
- Create: `tests/test_management_commands.py`

**Step 1: Write test for token_usage_report command**

Create `tests/test_management_commands.py`:
```python
import pytest
from decimal import Decimal
from io import StringIO
from django.core.management import call_command
from django.contrib.auth.models import User
from core.models import QueryLog
from datetime import datetime, timedelta


@pytest.mark.django_db
def test_token_usage_report_command():
    """Test token usage report shows statistics"""
    user = User.objects.create(username='testuser')

    # Create some query logs with token data
    for i in range(3):
        QueryLog.objects.create(
            user=user,
            username='testuser',
            question=f'Query {i}',
            intent={'entity': 'synthesizer'},
            entity='synthesizer',
            execution_time_ms=45,
            input_tokens=100 * (i + 1),
            output_tokens=50 * (i + 1),
            total_tokens=150 * (i + 1),
            estimated_cost_usd=Decimal('0.001') * (i + 1)
        )

    out = StringIO()
    call_command('token_usage_report', '--days', '7', stdout=out)
    output = out.getvalue()

    assert 'Total Queries: 3' in output
    assert 'Total Tokens: 900' in output  # 150 + 300 + 450
    assert 'Avg Tokens/Query: 300' in output
    assert 'Estimated Cost:' in output


@pytest.mark.django_db
def test_token_usage_report_no_data():
    """Test report handles no query data gracefully"""
    out = StringIO()
    call_command('token_usage_report', '--days', '7', stdout=out)
    output = out.getvalue()

    assert 'Total Queries: 0' in output
```

**Step 2: Run test to verify it fails**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_management_commands.py -v`
Expected: CommandError: Unknown command: 'token_usage_report'

**Step 3: Create management command structure**

Create empty files:
```bash
touch core/management/__init__.py
touch core/management/commands/__init__.py
```

Create `core/management/commands/token_usage_report.py`:
```python
from django.core.management.base import BaseCommand
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from datetime import timedelta
from core.models import QueryLog


class Command(BaseCommand):
    help = 'Generate token usage report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to include in report'
        )

    def handle(self, *args, **options):
        days = options['days']
        since = timezone.now() - timedelta(days=days)

        # Query logs with token data
        logs = QueryLog.objects.filter(
            executed_at__gte=since,
            total_tokens__isnull=False
        )

        # Aggregate statistics
        stats = logs.aggregate(
            total_queries=Count('id'),
            total_tokens=Sum('total_tokens'),
            total_input=Sum('input_tokens'),
            total_output=Sum('output_tokens'),
            total_cost=Sum('estimated_cost_usd'),
            avg_tokens=Avg('total_tokens')
        )

        # Display report
        self.stdout.write(self.style.SUCCESS(
            f'\nToken Usage Report (Last {days} days)'
        ))
        self.stdout.write('=' * 60)
        self.stdout.write(f"Total Queries: {stats['total_queries'] or 0}")

        if stats['total_tokens']:
            self.stdout.write(
                f"Total Tokens: {stats['total_tokens']:,} "
                f"(Input: {stats['total_input']:,} | "
                f"Output: {stats['total_output']:,})"
            )
            self.stdout.write(
                f"Avg Tokens/Query: {int(stats['avg_tokens'] or 0):,}"
            )
            self.stdout.write(
                f"Estimated Cost: ${stats['total_cost'] or 0:.2f}"
            )

            # Top expensive queries
            top_queries = logs.order_by('-total_tokens')[:5]
            if top_queries.exists():
                self.stdout.write('\n' + '=' * 60)
                self.stdout.write('Top 5 Most Expensive Queries:')
                for i, log in enumerate(top_queries, 1):
                    self.stdout.write(
                        f"{i}. \"{log.question[:50]}...\" - "
                        f"{log.total_tokens:,} tokens "
                        f"(${log.estimated_cost_usd:.4f})"
                    )
        else:
            self.stdout.write('No token usage data available.')

        self.stdout.write('')
```

**Step 4: Run test to verify it passes**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/test_management_commands.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add core/management/ tests/test_management_commands.py
git commit -m "feat: add token_usage_report management command

- Show total queries, tokens, cost for date range
- Show average tokens per query
- List top 5 most expensive queries
- Handle empty data gracefully
- TDD: 2 passing tests
"
```

---

## Task 9: Add Settings and Configuration

**Files:**
- Modify: `botswain/settings/base.py`
- Create: `.env.example`

**Step 1: Add Bedrock settings to base.py**

Modify `botswain/settings/base.py`, add at bottom:
```python
# AWS Bedrock / LLM Configuration
BOTSWAIN_LLM_PROVIDER = os.getenv('BOTSWAIN_LLM_PROVIDER', 'bedrock')
BOTSWAIN_BEDROCK_MODEL = os.getenv(
    'BOTSWAIN_BEDROCK_MODEL',
    'us.anthropic.claude-sonnet-4-5-20250929-v1:0'
)
BOTSWAIN_MAX_INPUT_CHARS = int(os.getenv('BOTSWAIN_MAX_INPUT_CHARS', '1000'))
BOTSWAIN_MAX_INTENT_TOKENS = int(os.getenv('BOTSWAIN_MAX_INTENT_TOKENS', '500'))
BOTSWAIN_MAX_RESPONSE_TOKENS = int(os.getenv('BOTSWAIN_MAX_RESPONSE_TOKENS', '1000'))
BOTSWAIN_DAILY_BUDGET_USD = float(os.getenv('BOTSWAIN_DAILY_BUDGET_USD', '50.00'))

# AWS Region
AWS_DEFAULT_REGION = os.getenv('AWS_REGION', 'us-west-2')
```

**Step 2: Create .env.example**

Create `.env.example`:
```bash
# Botswain LLM Configuration

# LLM Provider ('bedrock' or 'claude_cli')
BOTSWAIN_LLM_PROVIDER=bedrock

# AWS Bedrock Model (must use inference profile ID with 'us.' prefix)
BOTSWAIN_BEDROCK_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Token Limits
BOTSWAIN_MAX_INPUT_CHARS=1000
BOTSWAIN_MAX_INTENT_TOKENS=500
BOTSWAIN_MAX_RESPONSE_TOKENS=1000

# Cost Control
BOTSWAIN_DAILY_BUDGET_USD=50.00

# AWS Configuration
AWS_REGION=us-west-2
# AWS_PROFILE=admin  # If using AWS profiles
```

**Step 3: Verify settings load**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.local venv/bin/python -c "from django.conf import settings; print(settings.BOTSWAIN_BEDROCK_MODEL)"`
Expected: "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

**Step 4: Commit**

```bash
git add botswain/settings/base.py .env.example
git commit -m "feat: add Bedrock configuration settings

- Add BOTSWAIN_LLM_PROVIDER setting
- Add BOTSWAIN_BEDROCK_MODEL with default
- Add token limit settings
- Add daily budget setting
- Create .env.example with documentation
"
```

---

## Task 10: Update README with Bedrock Information

**Files:**
- Modify: `README.md`

**Step 1: Add Bedrock section to README**

Modify `README.md`, add after "Architecture" section:
```markdown
## LLM Provider

Botswain uses **AWS Bedrock** with the Anthropic SDK by default.

**Default Model:** Claude Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)

**Configuration:**
```bash
# .env or environment variables
BOTSWAIN_LLM_PROVIDER=bedrock
BOTSWAIN_BEDROCK_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

**Token Limits:**
- User input: 1000 characters (~750 tokens)
- Intent parsing: 500 tokens max
- Response formatting: 1000 tokens max

**Cost Monitoring:**
```bash
# View token usage report
python manage.py token_usage_report --days 7

# Shows:
# - Total queries and tokens
# - Average tokens per query
# - Estimated costs
# - Top expensive queries
```

**Alternative Provider:**
To use Claude CLI instead (local development only):
```bash
export BOTSWAIN_LLM_PROVIDER=claude_cli
```

**Requirements:**
- AWS credentials configured (via `aws sso login` or IAM role)
- Access to Bedrock service in us-west-2
- Model access granted for Claude Sonnet 4.5

**See also:** `docs/plans/2026-03-09-bedrock-sdk-migration-design.md` for detailed architecture
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add Bedrock LLM provider documentation to README

- Document default model and configuration
- Document token limits and cost monitoring
- Document alternative CLI provider
- Add requirements section
"
```

---

## Task 11: Integration Testing with Real Bedrock

**Files:**
- Create: `tests/integration/test_real_bedrock.py`

**Step 1: Create integration test**

Create `tests/integration/test_real_bedrock.py`:
```python
import pytest
import os
from core.llm.bedrock import BedrockProvider


@pytest.mark.skipif(
    not os.getenv('TEST_REAL_BEDROCK'),
    reason="Requires AWS credentials and TEST_REAL_BEDROCK=1"
)
def test_real_bedrock_parse_intent():
    """Integration test with real AWS Bedrock API"""
    provider = BedrockProvider()

    intent = provider.parse_intent(
        "How many synthesizers are online?",
        {
            'entities': {
                'synthesizer': 'RNA/DNA synthesis instruments',
                'instrument': 'Factory equipment'
            }
        }
    )

    # Verify response structure
    assert 'entity' in intent
    assert intent['entity'] in ['synthesizer', 'instrument']
    assert 'intent_type' in intent

    # Verify token tracking
    assert '_tokens' in intent
    assert intent['_tokens']['input'] > 0
    assert intent['_tokens']['output'] > 0
    assert intent['_tokens']['total'] > 0

    print(f"\nReal Bedrock Response:")
    print(f"Entity: {intent['entity']}")
    print(f"Intent Type: {intent['intent_type']}")
    print(f"Tokens: {intent['_tokens']}")


@pytest.mark.skipif(
    not os.getenv('TEST_REAL_BEDROCK'),
    reason="Requires AWS credentials and TEST_REAL_BEDROCK=1"
)
def test_real_bedrock_format_response():
    """Test response formatting with real API"""
    provider = BedrockProvider()

    response = provider.format_response(
        {
            'success': True,
            'entity': 'synthesizer',
            'count': 5,
            'results': [
                {'barcode': 'SYN-001', 'status': 'online'},
                {'barcode': 'SYN-002', 'status': 'online'},
            ]
        },
        'How many synthesizers are online?'
    )

    # Verify it's a natural language response
    assert isinstance(response, str)
    assert len(response) > 0
    assert '5' in response or 'five' in response.lower()

    print(f"\nFormatted Response:")
    print(response)
```

**Step 2: Test locally with real AWS**

Run: `TEST_REAL_BEDROCK=1 DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest tests/integration/test_real_bedrock.py -v -s`
Expected: 2 passed (if AWS credentials configured)

**Step 3: Commit**

```bash
git add tests/integration/test_real_bedrock.py
git commit -m "test: add integration tests for real Bedrock API

- Test parse_intent with real API
- Test format_response with real API
- Verify token tracking works end-to-end
- Gated by TEST_REAL_BEDROCK env var
"
```

---

## Task 12: Run Full Test Suite

**Step 1: Run all tests**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest -v`
Expected: All tests passing

**Step 2: Run test coverage**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.test venv/bin/pytest --cov=core --cov=api --cov-report=term`
Expected: >85% coverage

**Step 3: Verify Bedrock works with production replica**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.barb_prod_replica venv/bin/python manage.py runserver 8002`

In another terminal:
Run: `curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" -d '{"question":"How many instruments?"}' | python -m json.tool`

Expected: Success response with token usage

**Step 4: Check token logging**

Run: `DJANGO_SETTINGS_MODULE=botswain.settings.barb_prod_replica venv/bin/python manage.py token_usage_report --days 1`
Expected: Shows token usage from test query

---

## Task 13: Update Makefile with Token Commands

**Files:**
- Modify: `Makefile`

**Step 1: Add token usage commands**

Modify `Makefile`, add in "##@ BARB Integration" section:
```makefile
token-report: ## Show token usage report
	@echo "$(GREEN)Token Usage Report...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py token_usage_report --days 7

token-report-today: ## Show today's token usage
	@echo "$(GREEN)Today's Token Usage...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py token_usage_report --days 1

token-report-month: ## Show this month's token usage
	@echo "$(GREEN)Monthly Token Usage...$(NC)"
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS) $(VENV_BIN)/python manage.py token_usage_report --days 30
```

**Step 2: Test commands**

Run: `make token-report`
Expected: Displays token usage report

**Step 3: Commit**

```bash
git add Makefile
git commit -m "feat: add token usage commands to Makefile

- make token-report: 7-day report
- make token-report-today: today only
- make token-report-month: 30-day report
"
```

---

## Task 14: Final Documentation and Cleanup

**Files:**
- Create: `docs/BEDROCK_SETUP.md`

**Step 1: Create Bedrock setup guide**

Create `docs/BEDROCK_SETUP.md`:
```markdown
# AWS Bedrock Setup Guide

## Prerequisites

1. **AWS Credentials**
   ```bash
   aws sso login --profile admin
   ```

2. **Verify Bedrock Access**
   ```bash
   aws bedrock list-foundation-models --region us-west-2 --by-provider anthropic
   ```

## Model Access

Botswain uses **inference profile IDs** (not direct model IDs).

**Working Models:**
- `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (default)
- `us.anthropic.claude-3-5-haiku-20241022-v1:0` (cost optimization)

**Important:** Must use `us.` prefix. Direct model IDs fail with "Access denied".

## Configuration

1. **Environment Variables**
   ```bash
   export BOTSWAIN_BEDROCK_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
   export AWS_REGION=us-west-2
   ```

2. **Or .env File**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

## Testing Bedrock Access

```bash
# Quick test
python -c "from anthropic import AnthropicBedrock; client = AnthropicBedrock(); print('OK')"

# Full integration test
TEST_REAL_BEDROCK=1 pytest tests/integration/test_real_bedrock.py -v
```

## Cost Management

**View Usage:**
```bash
python manage.py token_usage_report --days 7
```

**Set Budget Alert:**
```bash
export BOTSWAIN_DAILY_BUDGET_USD=50.00
```

## Troubleshooting

**Error: "Access denied"**
- Using direct model ID instead of inference profile
- Solution: Use `us.anthropic.claude-sonnet-4-5-20250929-v1:0`

**Error: "UnauthorizedException"**
- AWS credentials expired
- Solution: `aws sso login --profile admin`

**Error: "Model not found"**
- Model not available in region
- Solution: Check available models with `aws bedrock list-inference-profiles`

## Rollback to CLI

If Bedrock has issues:
```bash
export BOTSWAIN_LLM_PROVIDER=claude_cli
# Or in settings:
BOTSWAIN_LLM_PROVIDER = 'claude_cli'
```
```

**Step 2: Commit**

```bash
git add docs/BEDROCK_SETUP.md
git commit -m "docs: add Bedrock setup and troubleshooting guide

- Document prerequisites and model access
- Document configuration options
- Add testing and cost management sections
- Add troubleshooting for common errors
- Document rollback procedure
"
```

---

## Task 15: Final Verification and Tag

**Step 1: Run full test suite one more time**

Run: `make test`
Expected: All tests passing

**Step 2: Test against production replica**

Run: `make run-barb-prod`

In another terminal:
```bash
./botswain-cli.py "How many instruments are in production?"
```

Expected: Works without nesting errors

**Step 3: Verify token logging**

Run: `make token-report`
Expected: Shows usage data

**Step 4: Create summary**

Run:
```bash
git log --oneline --graph HEAD~15..HEAD
```

**Step 5: Final commit and tag**

```bash
git commit --allow-empty -m "chore: AWS Bedrock SDK migration complete

Summary of changes:
- Replaced Claude CLI subprocess with AWS Bedrock SDK
- Added token usage tracking (input/output/cost)
- Added management commands for cost reporting
- Maintained backwards compatibility with CLI provider
- All 41+ tests passing
- Production-ready with monitoring

Migration provides:
- No more nesting errors (works in Claude Code)
- Token visibility for cost optimization
- Better error handling and retries
- Production-grade observability

See: docs/plans/2026-03-09-bedrock-sdk-migration-design.md
"

git tag -a v1.1.0-bedrock -m "Release v1.1.0 - AWS Bedrock SDK integration"
```

---

## Execution Notes

**Estimated Time:** 3-4 hours for complete implementation

**Testing Checkpoints:**
- After Task 2: BedrockProvider tests passing
- After Task 5: Token logging tests passing
- After Task 11: Integration tests with real API
- After Task 15: Full system verification

**Critical Success Criteria:**
- ✅ All existing tests still pass
- ✅ New Bedrock tests pass (41+ total)
- ✅ Works without nesting errors
- ✅ Tokens logged to database
- ✅ Management commands work
- ✅ Production replica connection works

**Rollback Plan:**
If issues arise during testing, rollback via:
```bash
export BOTSWAIN_LLM_PROVIDER=claude_cli
```

No code rollback needed - both providers coexist.

---

## References

- Design Doc: `docs/plans/2026-03-09-bedrock-sdk-migration-design.md`
- AWS Bedrock Models: `/home/danajanezic/.claude/projects/-home-danajanezic-code/memory/aws-bedrock-models.md`
- Anthropic SDK: https://docs.anthropic.com/en/api/client-sdks
