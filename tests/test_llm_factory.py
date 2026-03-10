# tests/test_llm_factory.py
import os
import pytest
from core.llm.factory import LLMProviderFactory
from core.llm.claude_cli import ClaudeCLIProvider
from core.llm.bedrock import BedrockProvider

def test_factory_creates_claude_cli_provider():
    """Test that factory can create Claude CLI provider"""
    provider = LLMProviderFactory.create('claude_cli')
    assert isinstance(provider, ClaudeCLIProvider)

def test_factory_creates_bedrock_provider():
    """Test that factory can create Bedrock provider"""
    provider = LLMProviderFactory.create('bedrock')
    assert isinstance(provider, BedrockProvider)

def test_factory_raises_error_for_unknown_provider():
    """Test that factory raises error for unknown provider"""
    with pytest.raises(ValueError, match="Unknown provider"):
        LLMProviderFactory.create('unknown_provider')

def test_factory_lists_available_providers():
    """Test that factory can list available providers"""
    providers = LLMProviderFactory.list_providers()
    assert 'claude_cli' in providers
    assert 'bedrock' in providers

def test_factory_defaults_to_bedrock():
    """Test that factory defaults to Bedrock provider"""
    # Save original env var if it exists
    original_env = os.environ.get('LLM_PROVIDER')

    try:
        # Remove env var to test default
        if 'LLM_PROVIDER' in os.environ:
            del os.environ['LLM_PROVIDER']

        provider = LLMProviderFactory.get_default()
        assert isinstance(provider, BedrockProvider)
        assert not isinstance(provider, ClaudeCLIProvider)
    finally:
        # Restore original env var
        if original_env is not None:
            os.environ['LLM_PROVIDER'] = original_env
        elif 'LLM_PROVIDER' in os.environ:
            del os.environ['LLM_PROVIDER']

def test_factory_respects_env_variable_for_claude_cli():
    """Test that factory respects LLM_PROVIDER environment variable for Claude CLI"""
    # Save original env var if it exists
    original_env = os.environ.get('LLM_PROVIDER')

    try:
        os.environ['LLM_PROVIDER'] = 'claude_cli'

        provider = LLMProviderFactory.get_default()
        assert isinstance(provider, ClaudeCLIProvider)
        assert not isinstance(provider, BedrockProvider)
    finally:
        # Restore original env var
        if original_env is not None:
            os.environ['LLM_PROVIDER'] = original_env
        else:
            del os.environ['LLM_PROVIDER']

def test_factory_respects_env_variable_for_bedrock():
    """Test that factory respects LLM_PROVIDER environment variable for Bedrock"""
    # Save original env var if it exists
    original_env = os.environ.get('LLM_PROVIDER')

    try:
        os.environ['LLM_PROVIDER'] = 'bedrock'

        provider = LLMProviderFactory.get_default()
        assert isinstance(provider, BedrockProvider)
    finally:
        # Restore original env var
        if original_env is not None:
            os.environ['LLM_PROVIDER'] = original_env
        else:
            del os.environ['LLM_PROVIDER']

def test_both_providers_still_available():
    """Test that both providers can be instantiated (backwards compatibility)"""
    bedrock = LLMProviderFactory.create('bedrock')
    claude_cli = LLMProviderFactory.create('claude_cli')

    assert bedrock is not None
    assert claude_cli is not None
    assert isinstance(bedrock, BedrockProvider)
    assert isinstance(claude_cli, ClaudeCLIProvider)
