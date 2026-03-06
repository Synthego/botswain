# tests/test_llm_factory.py
import pytest
from core.llm.factory import LLMProviderFactory
from core.llm.claude_cli import ClaudeCLIProvider

def test_factory_creates_claude_cli_provider():
    """Test that factory can create Claude CLI provider"""
    provider = LLMProviderFactory.create('claude_cli')
    assert isinstance(provider, ClaudeCLIProvider)

def test_factory_raises_error_for_unknown_provider():
    """Test that factory raises error for unknown provider"""
    with pytest.raises(ValueError, match="Unknown provider"):
        LLMProviderFactory.create('unknown_provider')

def test_factory_lists_available_providers():
    """Test that factory can list available providers"""
    providers = LLMProviderFactory.list_providers()
    assert 'claude_cli' in providers
