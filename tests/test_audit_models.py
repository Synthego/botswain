# tests/test_audit_models.py
import pytest
from django.contrib.auth.models import User

@pytest.mark.django_db
def test_can_import_query_log():
    """Test that QueryLog model can be imported"""
    from core.models import QueryLog
    assert QueryLog is not None

@pytest.mark.django_db
def test_can_create_query_log():
    """Test that QueryLog can be created"""
    from core.models import QueryLog

    user = User.objects.create_user(username='test@synthego.com')

    log = QueryLog.objects.create(
        user=user,
        username='test@synthego.com',
        question="What synthesizers are available?",
        intent={'entity': 'synthesizer'},
        entity='synthesizer',
        intent_type='query',
        execution_time_ms=100,
        interface='api',
        success=True
    )

    assert log.id is not None
    assert log.username == 'test@synthego.com'
    assert log.entity == 'synthesizer'
