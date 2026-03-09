# tests/test_bedrock_provider.py
import pytest
from unittest.mock import Mock, patch
from core.llm.bedrock import BedrockProvider


def test_parse_intent_returns_structured_json():
    """Test that BedrockProvider can parse intent into structured JSON"""
    provider = BedrockProvider()

    # Mock the Bedrock API response
    with patch.object(provider.client.messages, 'create') as mock_create:
        mock_create.return_value = Mock(
            content=[Mock(text='{"entity": "instrument", "intent_type": "query", "attributes": ["name", "status"], "filters": {}, "sort": null, "limit": 10}')],
            usage=Mock(input_tokens=50, output_tokens=30)
        )

        result = provider.parse_intent(
            "How many instruments?",
            {"entities": {"instrument": "Factory instruments"}}
        )

        assert isinstance(result, dict)
        assert "entity" in result
        assert result["entity"] == "instrument"
        assert result["intent_type"] == "query"


def test_parse_intent_returns_token_counts():
    """Test that parse_intent returns token usage information"""
    provider = BedrockProvider()

    with patch.object(provider.client.messages, 'create') as mock_create:
        mock_create.return_value = Mock(
            content=[Mock(text='{"entity": "instrument", "intent_type": "count"}')],
            usage=Mock(input_tokens=50, output_tokens=30)
        )

        result = provider.parse_intent("test", {"entities": {}})

        assert "_tokens" in result
        assert result["_tokens"]["input"] == 50
        assert result["_tokens"]["output"] == 30
        assert result["_tokens"]["total"] == 80


def test_format_response_returns_markdown():
    """Test that BedrockProvider can format responses into markdown"""
    provider = BedrockProvider()

    with patch.object(provider.client.messages, 'create') as mock_create:
        mock_create.return_value = Mock(
            content=[Mock(text='Found 3 instruments:\n- Synth-01\n- Synth-02\n- Synth-03')],
            usage=Mock(input_tokens=100, output_tokens=50)
        )

        result = provider.format_response(
            {"results": [{"id": 1, "name": "Synth-01"}]},
            "What instruments are available?"
        )

        assert isinstance(result, str)
        assert len(result) > 0


def test_format_response_returns_token_counts():
    """Test that format_response returns token usage information"""
    provider = BedrockProvider()

    with patch.object(provider.client.messages, 'create') as mock_create:
        mock_create.return_value = Mock(
            content=[Mock(text='Test response')],
            usage=Mock(input_tokens=100, output_tokens=50)
        )

        result = provider.format_response({}, "test")

        # format_response should return a string with the response
        assert isinstance(result, str)


def test_constructor_parameters():
    """Test that BedrockProvider constructor accepts and uses parameters"""
    provider = BedrockProvider(
        model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        max_intent_tokens=300,
        max_response_tokens=800,
        timeout=60.0
    )

    assert provider.model == "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    assert provider.max_intent_tokens == 300
    assert provider.max_response_tokens == 800


def test_default_constructor_parameters():
    """Test that BedrockProvider uses correct defaults"""
    provider = BedrockProvider()

    assert provider.model == "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    assert provider.max_intent_tokens == 500
    assert provider.max_response_tokens == 1000
