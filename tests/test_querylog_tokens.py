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
