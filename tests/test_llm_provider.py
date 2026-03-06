# tests/test_llm_provider.py
import pytest
from core.llm.provider import LLMProvider

def test_llm_provider_is_abstract():
    """Test that LLMProvider cannot be instantiated directly"""
    with pytest.raises(TypeError):
        LLMProvider()

def test_llm_provider_requires_parse_intent():
    """Test that subclasses must implement parse_intent"""
    class IncompleteProvider(LLMProvider):
        def format_response(self, query_results, original_question):
            return "response"

    with pytest.raises(TypeError):
        IncompleteProvider()

def test_llm_provider_requires_format_response():
    """Test that subclasses must implement format_response"""
    class IncompleteProvider(LLMProvider):
        def parse_intent(self, question, context):
            return {}

    with pytest.raises(TypeError):
        IncompleteProvider()
