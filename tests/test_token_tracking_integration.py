"""Integration test for complete token tracking flow"""
import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from unittest.mock import patch, Mock
from core.models import QueryLog


@pytest.mark.django_db
def test_complete_token_tracking_flow():
    """
    End-to-end test: Verify tokens flow from both LLM calls through to audit log.

    This test verifies:
    1. parse_intent returns tokens in _tokens field
    2. format_response returns tokens in tokens field
    3. API combines both token counts
    4. Audit logger extracts and stores total tokens in database
    5. API response includes breakdown of format_response tokens
    """
    client = APIClient()
    user = User.objects.create_user(
        username='integrationtest@synthego.com',
        email='integrationtest@synthego.com'
    )
    client.force_authenticate(user=user)

    with patch('core.llm.factory.LLMProviderFactory.create') as mock_factory:
        mock_provider = Mock()

        # Mock parse_intent to return intent with tokens
        mock_provider.parse_intent.return_value = {
            'entity': 'synthesizer',
            'intent_type': 'count',
            'filters': {'status': 'ONLINE'},
            '_tokens': {
                'input': 150,
                'output': 80,
                'total': 230
            }
        }

        # Mock format_response to return formatted text with tokens
        mock_provider.format_response.return_value = {
            'text': 'There are currently 42 synthesizers online and ready for use.',
            'tokens': {
                'input': 300,
                'output': 120,
                'total': 420
            }
        }

        mock_factory.return_value = mock_provider

        # Make API request
        response = client.post('/api/query', {
            'question': 'How many synthesizers are online?',
            'format': 'natural'
        }, format='json')

        # Verify API response structure
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.json()}")
        assert response.status_code == 200
        data = response.json()

        # 1. Response text should be extracted from format_response
        assert data['response'] == 'There are currently 42 synthesizers online and ready for use.'

        # 2. Format tokens should be included separately in response
        assert 'format_tokens' in data
        assert data['format_tokens']['input'] == 300
        assert data['format_tokens']['output'] == 120
        assert data['format_tokens']['total'] == 420

        # 3. Intent should have combined tokens
        assert '_tokens' in data['intent']
        assert data['intent']['_tokens']['input'] == 450  # 150 + 300
        assert data['intent']['_tokens']['output'] == 200  # 80 + 120
        assert data['intent']['_tokens']['total'] == 650  # 230 + 420

        # 4. Verify audit log captures combined tokens
        log_entry = QueryLog.objects.filter(username='integrationtest@synthego.com').first()
        assert log_entry is not None

        # Database should have TOTAL from both LLM calls
        assert log_entry.input_tokens == 450  # parse_intent (150) + format_response (300)
        assert log_entry.output_tokens == 200  # parse_intent (80) + format_response (120)
        assert log_entry.total_tokens == 650  # parse_intent (230) + format_response (420)

        # Verify other audit fields
        assert log_entry.question == 'How many synthesizers are online?'
        assert log_entry.entity == 'synthesizer'
        assert log_entry.intent_type == 'count'
        assert log_entry.success is True
        assert log_entry.interface == 'api'

        # Verify intent stored in audit doesn't have _tokens (extracted)
        assert '_tokens' not in log_entry.intent


@pytest.mark.django_db
def test_backwards_compatibility_with_string_format_response():
    """
    Test that providers returning strings (like ClaudeCLI) still work.

    Verifies backwards compatibility when format_response returns a string
    instead of a dict with text and tokens.
    """
    client = APIClient()
    user = User.objects.create_user(
        username='compat@synthego.com',
        email='compat@synthego.com'
    )
    client.force_authenticate(user=user)

    with patch('core.llm.factory.LLMProviderFactory.create') as mock_factory:
        mock_provider = Mock()

        # parse_intent returns tokens
        mock_provider.parse_intent.return_value = {
            'entity': 'synthesizer',
            'intent_type': 'query',
            'filters': {},
            '_tokens': {
                'input': 100,
                'output': 50,
                'total': 150
            }
        }

        # format_response returns OLD STRING format (no tokens)
        mock_provider.format_response.return_value = "Found 3 synthesizers."

        mock_factory.return_value = mock_provider

        response = client.post('/api/query', {
            'question': 'Show synthesizers',
            'format': 'natural'
        }, format='json')

        assert response.status_code == 200
        data = response.json()

        # Response should still work
        assert data['response'] == "Found 3 synthesizers."

        # format_tokens should be empty dict
        assert data['format_tokens'] == {}

        # Intent should only have parse_intent tokens
        assert data['intent']['_tokens']['input'] == 100
        assert data['intent']['_tokens']['output'] == 50
        assert data['intent']['_tokens']['total'] == 150

        # Audit log should have only parse_intent tokens
        log_entry = QueryLog.objects.filter(username='compat@synthego.com').first()
        assert log_entry is not None
        assert log_entry.input_tokens == 100
        assert log_entry.output_tokens == 50
        assert log_entry.total_tokens == 150
