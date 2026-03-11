# tests/test_query_executor.py
import pytest
from unittest.mock import Mock
from core.query_executor import QueryExecutor
from core.semantic_layer.registry import EntityRegistry
from core.semantic_layer.entities.synthesizer import SynthesizerEntity
from core.semantic_layer.entities.base import BaseEntity
from core.pagination import PaginationMetadata

@pytest.fixture
def registry_with_synthesizer():
    """Create registry with synthesizer entity"""
    registry = EntityRegistry()
    registry.register(SynthesizerEntity())
    return registry


@pytest.fixture
def registry_with_mock_entity():
    """Create registry with mock entity for pagination testing"""
    class MockEntity(BaseEntity):
        name = "mock"
        description = "Mock entity for testing"

        def get_queryset(self, filters=None):
            # Return a list that simulates a large dataset
            return [{'id': i, 'value': f'item_{i}'} for i in range(200)]

        def get_attributes(self):
            return ['id', 'value']

        def validate_filters(self, filters):
            return True

    registry = EntityRegistry()
    registry.register(MockEntity())
    return registry

def test_query_executor_initialization():
    """Test that query executor can be created"""
    executor = QueryExecutor()
    assert executor is not None

@pytest.mark.django_db
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
    assert 'pagination' in result

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


class TestQueryExecutorPagination:
    """Test QueryExecutor pagination support"""

    def test_execute_with_offset_and_limit(self, registry_with_mock_entity):
        """Execute should accept offset and limit parameters"""
        executor = QueryExecutor(registry=registry_with_mock_entity, use_cache=False)

        intent = {'entity': 'mock', 'intent_type': 'query', 'filters': {}}

        result = executor.execute(intent, user='testuser', offset=10, limit=5)

        assert 'pagination' in result
        assert result['pagination']['offset'] == 10
        assert result['pagination']['limit'] == 5

    def test_smart_estimation_fetches_limit_plus_one(self, registry_with_mock_entity):
        """Should fetch limit+1 results to determine has_next"""
        # This tests the internal behavior - we'll verify through has_next flag
        executor = QueryExecutor(registry=registry_with_mock_entity, use_cache=False)

        intent = {'entity': 'mock', 'intent_type': 'query', 'filters': {}}

        # Mock queryset with 200 results, fetch limit=50
        # Should detect has_next=True and return only 50 results
        result = executor.execute(intent, user='testuser', offset=0, limit=50)

        assert result['count'] == 50  # Trimmed to limit
        assert 'pagination' in result
        assert result['pagination']['has_next'] is True

    def test_has_next_true_when_more_results(self, registry_with_mock_entity):
        """has_next should be True when more results available"""
        executor = QueryExecutor(registry=registry_with_mock_entity, use_cache=False)

        intent = {'entity': 'mock', 'intent_type': 'query', 'filters': {}}

        # With 200 results total
        result = executor.execute(intent, user='testuser', offset=0, limit=10)

        assert result['count'] == 10
        assert 'pagination' in result
        assert result['pagination']['has_next'] is True

    def test_has_previous_false_on_first_page(self, registry_with_mock_entity):
        """has_previous should be False when offset=0"""
        executor = QueryExecutor(registry=registry_with_mock_entity, use_cache=False)

        intent = {'entity': 'mock', 'intent_type': 'query', 'filters': {}}

        result = executor.execute(intent, user='testuser', offset=0, limit=50)

        assert result['pagination']['has_previous'] is False

    def test_has_previous_true_when_offset_greater_than_zero(self, registry_with_mock_entity):
        """has_previous should be True when offset > 0"""
        executor = QueryExecutor(registry=registry_with_mock_entity, use_cache=False)

        intent = {'entity': 'mock', 'intent_type': 'query', 'filters': {}}

        result = executor.execute(intent, user='testuser', offset=50, limit=50)

        assert result['pagination']['has_previous'] is True

    def test_cache_respects_pagination_parameters(self, registry_with_mock_entity):
        """Cache should store different pages separately"""
        executor = QueryExecutor(registry=registry_with_mock_entity, use_cache=True)

        intent = {'entity': 'mock', 'intent_type': 'query', 'filters': {}}

        # Query page 1
        result1 = executor.execute(intent, user='testuser', offset=0, limit=50)

        # Query page 2
        result2 = executor.execute(intent, user='testuser', offset=50, limit=50)

        # Results should be different (different pages)
        assert result1['pagination']['offset'] == 0
        assert result2['pagination']['offset'] == 50
        # Verify different result sets
        assert result1['results'][0]['id'] == 0
        assert result2['results'][0]['id'] == 50
