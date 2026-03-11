"""Test that AuditLogger correctly extracts token data from intent"""
import pytest
from django.contrib.auth.models import User
from core.audit import AuditLogger
from core.models import QueryLog


@pytest.mark.django_db
def test_audit_logger_extracts_tokens_from_intent():
    """Test that AuditLogger extracts _tokens from intent and stores in QueryLog"""
    # Arrange
    logger = AuditLogger()
    user = User.objects.create_user(username='test@synthego.com', email='test@synthego.com')

    intent = {
        'entity': 'instrument',
        'intent_type': 'query',
        'attributes': ['name', 'status'],
        'filters': {},
        '_tokens': {
            'input': 50,
            'output': 30,
            'total': 80
        }
    }

    response = {
        'success': True,
        'results': [{'id': 1, 'name': 'Synth-01'}],
        'response': 'Found 1 instrument'
    }

    # Act
    log_entry = logger.log(
        user='test@synthego.com',
        intent=intent,
        response=response,
        execution_time=0.5,
        question='How many instruments?',
        interface='api'
    )

    # Assert
    assert log_entry.input_tokens == 50
    assert log_entry.output_tokens == 30
    assert log_entry.total_tokens == 80

    # Verify token data was removed from stored intent (to avoid redundancy)
    assert '_tokens' not in log_entry.intent

    # Verify we can retrieve and query by token fields
    retrieved = QueryLog.objects.get(id=log_entry.id)
    assert retrieved.input_tokens == 50
    assert retrieved.output_tokens == 30
    assert retrieved.total_tokens == 80


@pytest.mark.django_db
def test_audit_logger_handles_missing_tokens_gracefully():
    """Test that AuditLogger handles intents without _tokens field"""
    # Arrange
    logger = AuditLogger()
    User.objects.create_user(username='test@synthego.com', email='test@synthego.com')

    intent = {
        'entity': 'instrument',
        'intent_type': 'query',
        'attributes': ['name'],
        # No _tokens field
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
        interface='api'
    )

    # Assert - should be None when not provided
    assert log_entry.input_tokens is None
    assert log_entry.output_tokens is None
    assert log_entry.total_tokens is None


@pytest.mark.django_db
def test_audit_logger_handles_partial_token_data():
    """Test that AuditLogger handles incomplete token data"""
    # Arrange
    logger = AuditLogger()
    User.objects.create_user(username='test@synthego.com', email='test@synthego.com')

    intent = {
        'entity': 'instrument',
        'intent_type': 'count',
        '_tokens': {
            'input': 100,
            # Missing output and total
        }
    }

    response = {
        'success': True,
        'results': [],
        'response': 'Count: 0'
    }

    # Act
    log_entry = logger.log(
        user='test@synthego.com',
        intent=intent,
        response=response,
        execution_time=0.3,
        question='Count instruments',
        interface='api'
    )

    # Assert - should handle partial data
    assert log_entry.input_tokens == 100
    assert log_entry.output_tokens is None
    assert log_entry.total_tokens is None
