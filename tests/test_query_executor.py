# tests/test_query_executor.py
import pytest
from unittest.mock import Mock
from core.query_executor import QueryExecutor
from core.semantic_layer.registry import EntityRegistry
from core.semantic_layer.entities.synthesizer import SynthesizerEntity

@pytest.fixture
def registry_with_synthesizer():
    """Create registry with synthesizer entity"""
    registry = EntityRegistry()
    registry.register(SynthesizerEntity())
    return registry

def test_query_executor_initialization():
    """Test that query executor can be created"""
    executor = QueryExecutor()
    assert executor is not None

def test_query_executor_execute_simple_query(registry_with_synthesizer):
    """Test executing a simple query"""
    executor = QueryExecutor(registry=registry_with_synthesizer)

    intent = {
        'entity': 'synthesizer',
        'intent_type': 'query',
        'attributes': ['name', 'status'],
        'filters': {},
        'limit': 10
    }

    result = executor.execute(intent, user='test@synthego.com')

    assert result['success'] is True
    assert result['entity'] == 'synthesizer'
    assert 'results' in result
    assert 'execution_time_ms' in result

def test_query_executor_validates_intent(registry_with_synthesizer):
    """Test that executor validates intent before execution"""
    executor = QueryExecutor(registry=registry_with_synthesizer)

    intent = {
        'entity': 'synthesizer',
        'intent_type': 'query',
        'limit': 10000  # Exceeds max
    }

    with pytest.raises(ValueError, match="exceeds maximum"):
        executor.execute(intent, user='test@synthego.com')

def test_query_executor_unknown_entity():
    """Test that unknown entity raises error"""
    executor = QueryExecutor()

    intent = {
        'entity': 'nonexistent',
        'intent_type': 'query'
    }

    with pytest.raises(ValueError, match="Unknown entity"):
        executor.execute(intent, user='test@synthego.com')
