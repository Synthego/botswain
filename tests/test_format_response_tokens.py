"""Test that format_response returns token usage alongside the formatted response"""
import pytest
from unittest.mock import Mock, patch
from core.llm.bedrock import BedrockProvider


def test_format_response_returns_tokens_and_text():
    """Test that format_response returns both text and token usage"""
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

        # Result should be a dict with 'text' and 'tokens' keys
        assert isinstance(result, dict)
        assert 'text' in result
        assert 'tokens' in result

        # Text should be the formatted response
        assert isinstance(result['text'], str)
        assert len(result['text']) > 0

        # Tokens should have input, output, and total
        assert result['tokens']['input'] == 100
        assert result['tokens']['output'] == 50
        assert result['tokens']['total'] == 150


def test_format_response_token_structure():
    """Test that format_response returns tokens in the correct nested structure"""
    provider = BedrockProvider()

    with patch.object(provider.client.messages, 'create') as mock_create:
        mock_create.return_value = Mock(
            content=[Mock(text='Test response')],
            usage=Mock(input_tokens=200, output_tokens=75)
        )

        result = provider.format_response({}, "test question")

        # Verify nested structure matches what audit logger expects
        assert 'tokens' in result
        assert 'input' in result['tokens']
        assert 'output' in result['tokens']
        assert 'total' in result['tokens']
        assert result['tokens']['total'] == 275  # 200 + 75
