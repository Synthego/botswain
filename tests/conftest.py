import pytest
from django.contrib.auth.models import User
from unittest.mock import Mock

@pytest.fixture
def test_user():
    """Create a test user"""
    return User.objects.create_user(
        username='test@synthego.com',
        email='test@synthego.com',
        password='testpass123'
    )

@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing without actual LLM calls"""
    provider = Mock()
    provider.parse_intent.return_value = {
        'entity': 'synthesizer',
        'intent_type': 'query',
        'attributes': ['name', 'status'],
        'filters': {'status': 'ONLINE'},
    }
    provider.format_response.return_value = "Found 3 synthesizers online."
    return provider
