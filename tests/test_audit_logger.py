# tests/test_audit_logger.py
import pytest
from django.contrib.auth.models import User
from core.audit import AuditLogger
from core.models import QueryLog

@pytest.mark.django_db
def test_audit_logger_log_creates_entry():
    """Test that logging creates database entry"""
    user = User.objects.create_user(username='test@synthego.com')
    logger = AuditLogger()

    intent = {
        'entity': 'synthesizer',
        'intent_type': 'query'
    }

    response = {
        'success': True,
        'results': [{'name': 'Synth-01'}],
        'response': 'Found 1 synthesizer'
    }

    log_entry = logger.log(
        user='test@synthego.com',
        intent=intent,
        response=response,
        execution_time=0.5,
        question="Test question",
        interface='api'
    )

    assert log_entry.id is not None
    assert log_entry.username == 'test@synthego.com'
    assert log_entry.entity == 'synthesizer'
    assert log_entry.success is True

@pytest.mark.django_db
def test_audit_logger_log_error():
    """Test error logging"""
    logger = AuditLogger()

    logger.log_error(
        user='test@synthego.com',
        question="Test question",
        error=Exception("Test error"),
        interface='api'
    )

    log = QueryLog.objects.filter(username='test@synthego.com').first()
    assert log.success is False
    assert "Test error" in log.error_message
