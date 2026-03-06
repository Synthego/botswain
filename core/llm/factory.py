from typing import Dict, Type, List
from .provider import LLMProvider
from .claude_cli import ClaudeCLIProvider

class LLMProviderFactory:
    """Factory for creating LLM provider instances"""

    _providers: Dict[str, Type[LLMProvider]] = {
        'claude_cli': ClaudeCLIProvider,
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
