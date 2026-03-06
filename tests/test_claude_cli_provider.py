# tests/test_claude_cli_provider.py
import pytest
from unittest.mock import Mock, patch
from core.llm.claude_cli import ClaudeCLIProvider

def test_claude_cli_provider_parse_intent():
    """Test that Claude CLI provider can parse intent"""
    provider = ClaudeCLIProvider()

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            stdout='{"entity": "synthesizer", "intent_type": "query"}',
            returncode=0
        )

        result = provider.parse_intent("What synthesizers are available?", {})

        assert result['entity'] == 'synthesizer'
        assert result['intent_type'] == 'query'

def test_claude_cli_provider_format_response():
    """Test that Claude CLI provider can format responses"""
    provider = ClaudeCLIProvider()

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            stdout='Found 3 synthesizers online.',
            returncode=0
        )

        result = provider.format_response(
            {'results': [{'name': 'Synth-01'}]},
            "What synthesizers are available?"
        )

        assert 'Found' in result
