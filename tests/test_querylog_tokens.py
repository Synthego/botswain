# tests/test_querylog_tokens.py
import pytest
from django.contrib.auth.models import User
from core.models import QueryLog


@pytest.mark.django_db
def test_querylog_stores_token_counts():
    """Test that QueryLog can store token usage data"""
    user = User.objects.create_user(username='test@synthego.com')

    query_log = QueryLog.objects.create(
        user=user,
        username='test@synthego.com',
        question="test query",
        intent={'entity': 'synthesizer'},
        entity='synthesizer',
        intent_type='query',
        execution_time_ms=100,
        interface='api',
        input_tokens=50,
        output_tokens=100,
        total_tokens=150
    )

    assert query_log.input_tokens == 50
    assert query_log.output_tokens == 100
    assert query_log.total_tokens == 150


@pytest.mark.django_db
def test_querylog_token_fields_nullable():
    """Test that token fields are nullable for backwards compatibility"""
    user = User.objects.create_user(username='test@synthego.com')

    query_log = QueryLog.objects.create(
        user=user,
        username='test@synthego.com',
        question="test without tokens",
        intent={'entity': 'synthesizer'},
        entity='synthesizer',
        intent_type='query',
        execution_time_ms=100,
        interface='api'
    )

    assert query_log.input_tokens is None
    assert query_log.output_tokens is None
    assert query_log.total_tokens is None


@pytest.mark.django_db
def test_audit_logger_extracts_tokens_from_intent():
    """Test that AuditLogger extracts _tokens from intent and stores them"""
    from core.audit import AuditLogger

    intent = {
        "entity": "instrument",
        "intent_type": "query",
        "_tokens": {
            "input": 50,
            "output": 100,
            "total": 150
        }
    }

    logger = AuditLogger()
    logger.log(
        user="test@synthego.com",
        intent=intent,
        response={"success": True, "response": "test response"},
        execution_time=0.5,
        question="test query",
        interface='api'
    )

    log_entry = QueryLog.objects.latest('executed_at')
    assert log_entry.input_tokens == 50
    assert log_entry.output_tokens == 100
    assert log_entry.total_tokens == 150
    assert '_tokens' not in log_entry.intent  # Should be removed from stored intent
