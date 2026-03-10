import os
from typing import Dict, Type, List
from .provider import LLMProvider
from .claude_cli import ClaudeCLIProvider
from .bedrock import BedrockProvider

class LLMProviderFactory:
    """Factory for creating LLM provider instances"""

    _providers: Dict[str, Type[LLMProvider]] = {
        'claude_cli': ClaudeCLIProvider,
        'bedrock': BedrockProvider,
    }

    @classmethod
    def create(cls, provider_name: str, **kwargs) -> LLMProvider:
        """
        Create an LLM provider instance.

        Args:
            provider_name: Name of provider ('claude_cli', 'claude_api', etc.)
            **kwargs: Provider-specific configuration

        Returns:
            LLMProvider instance

        Raises:
            ValueError: If provider_name is unknown
        """
        provider_class = cls._providers.get(provider_name)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")

        return provider_class(**kwargs)

    @classmethod
    def list_providers(cls) -> List[str]:
        """List available provider names"""
        return list(cls._providers.keys())

    @classmethod
    def register(cls, name: str, provider_class: Type[LLMProvider]):
        """Register a new provider (for extensibility)"""
        cls._providers[name] = provider_class

    @classmethod
    def get_default(cls, **kwargs) -> LLMProvider:
        """
        Get the default LLM provider instance.

        The default provider is determined by the LLM_PROVIDER environment variable.
        If not set, defaults to 'bedrock'.

        Supported values:
        - 'bedrock': AWS Bedrock provider (default)
        - 'claude_cli': Claude CLI subprocess provider

        Args:
            **kwargs: Provider-specific configuration

        Returns:
            LLMProvider instance

        Raises:
            ValueError: If the provider name from env var is unknown
        """
        provider_name = os.environ.get('LLM_PROVIDER', 'bedrock')
        return cls.create(provider_name, **kwargs)
