"""Test that AuditLogger calculates and stores cost data"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from core.audit import AuditLogger
from core.models import QueryLog


@pytest.mark.django_db
def test_audit_logger_calculates_cost_for_sonnet():
    """Test AuditLogger calculates cost using Sonnet pricing"""
    # Arrange
    logger = AuditLogger()
    User.objects.create_user(username='test@synthego.com', email='test@synthego.com')

    intent = {
        'entity': 'instrument',
        'intent_type': 'query',
        '_tokens': {
            'input': 1000,
            'output': 500,
            'total': 1500
        }
    }

    response = {
        'success': True,
        'results': [{'id': 1}],
        'response': 'Found 1 result'
    }

    # Act
    log_entry = logger.log(
        user='test@synthego.com',
        intent=intent,
        response=response,
        execution_time=0.5,
        question='Test query',
        interface='api',
        model='us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    )

    # Assert - Sonnet: (1000 * $3 + 500 * $15) / 1,000,000 = $0.0105
    assert log_entry.estimated_cost_usd is not None
    assert log_entry.estimated_cost_usd == Decimal('0.0105')


@pytest.mark.django_db
def test_audit_logger_calculates_cost_for_haiku():
    """Test AuditLogger calculates cost using Haiku pricing"""
    # Arrange
    logger = AuditLogger()
    User.objects.create_user(username='test@synthego.com', email='test@synthego.com')

    intent = {
        'entity': 'instrument',
        'intent_type': 'query',
        '_tokens': {
            'input': 1000,
            'output': 500,
            'total': 1500
        }
    }

    response = {
        'success': True,
        'results': [],
        'response': 'No results'
    }

    # Act
    log_entry = logger.log(
        user='test@synthego.com',
        intent=intent,
        response=response,
        execution_time=0.2,
        question='Test query',
        interface='api',
        model='us.anthropic.claude-3-5-haiku-20241022-v1:0'
    )

    # Assert - Haiku: (1000 * $0.25 + 500 * $1.25) / 1,000,000 = $0.000875
    assert log_entry.estimated_cost_usd is not None
    assert log_entry.estimated_cost_usd == Decimal('0.000875')


@pytest.mark.django_db
def test_audit_logger_handles_missing_tokens_no_cost():
    """Test AuditLogger sets cost to None when tokens are missing"""
    # Arrange
    logger = AuditLogger()
    User.objects.create_user(username='test@synthego.com', email='test@synthego.com')

    intent = {
        'entity': 'instrument',
        'intent_type': 'query',
        # No _tokens field (e.g., from ClaudeCLIProvider)
    }

    response = {
        'success': True,
        'results': [],
        'response': 'No results'
    }

    # Act
    log_entry = logger.log(
        user='test@synthego.com',
        intent=intent,
        response=response,
        execution_time=0.2,
        question='Test query',
        interface='cli',
        model='us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    )

    # Assert
    assert log_entry.input_tokens is None
    assert log_entry.output_tokens is None
    assert log_entry.total_tokens is None
    assert log_entry.estimated_cost_usd is None


@pytest.mark.django_db
def test_audit_logger_defaults_to_sonnet_when_model_not_specified():
    """Test AuditLogger uses Sonnet pricing when model parameter is not provided"""
    # Arrange
    logger = AuditLogger()
    User.objects.create_user(username='test@synthego.com', email='test@synthego.com')

    intent = {
        'entity': 'instrument',
        '_tokens': {
            'input': 1000,
            'output': 500,
            'total': 1500
        }
    }

    response = {
        'success': True,
        'results': [],
        'response': 'No results'
    }

    # Act - no model parameter
    log_entry = logger.log(
        user='test@synthego.com',
        intent=intent,
        response=response,
        execution_time=0.2,
        question='Test query',
        interface='api'
    )

    # Assert - should default to Sonnet pricing
    assert log_entry.estimated_cost_usd == Decimal('0.0105')
