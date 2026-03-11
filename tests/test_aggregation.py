"""
Tests for programmatic aggregation in QueryExecutor.

Tests that count and aggregate intent types produce accurate mathematical results
instead of relying on LLM to calculate from raw data.
"""
import pytest
from core.query_executor import QueryExecutor
from core.semantic_layer.registry import EntityRegistry
from core.semantic_layer.entities.base import BaseEntity


class MockAggregationEntity(BaseEntity):
    """Mock entity for testing aggregation"""
    name = "test_entity"
    description = "Test entity for aggregation"

    def get_queryset(self, filters=None):
        # Return sample data for testing
        return [
            {'id': 1, 'name': 'Item 1', 'price': 100.50, 'quantity': 5, 'status': 'active'},
            {'id': 2, 'name': 'Item 2', 'price': 200.00, 'quantity': 3, 'status': 'active'},
            {'id': 3, 'name': 'Item 3', 'price': 150.75, 'quantity': 0, 'status': 'inactive'},
            {'id': 4, 'name': 'Item 4', 'price': 300.25, 'quantity': 10, 'status': 'active'},
            {'id': 5, 'name': 'Item 5', 'price': 50.00, 'quantity': 2, 'status': 'active'},
        ]

    def validate_filters(self, filters):
        return True

    def get_attributes(self):
        return ['id', 'name', 'price', 'quantity', 'status']


class TestAggregation:
    """Test programmatic aggregation functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.registry = EntityRegistry()
        self.registry.register(MockAggregationEntity())
        self.executor = QueryExecutor(registry=self.registry)

    def test_query_intent_returns_raw_results(self):
        """Test that 'query' intent_type returns raw results"""
        intent = {
            'entity': 'test_entity',
            'intent_type': 'query',
            'attributes': ['id', 'name', 'price'],
            'filters': {},
            'limit': 10
        }

        result = self.executor.execute(intent, user='test_user')

        assert result['success'] is True
        assert result['entity'] == 'test_entity'
        assert result['count'] == 5
        assert len(result['results']) == 5
        assert 'aggregations' not in result  # No aggregations for query intent

    def test_count_intent_returns_accurate_count(self):
        """Test that 'count' intent_type returns accurate count"""
        intent = {
            'entity': 'test_entity',
            'intent_type': 'count',
            'attributes': [],
            'filters': {},
            'limit': 10
        }

        result = self.executor.execute(intent, user='test_user')

        assert result['success'] is True
        assert result['entity'] == 'test_entity'
        assert result['count'] == 5
        assert 'aggregations' in result
        assert result['aggregations']['total_count'] == 5
        # For count queries, we don't need to return all raw results
        assert len(result['results']) <= 10  # May be limited for response size

    def test_aggregate_intent_with_sum(self):
        """Test aggregate intent with SUM function"""
        intent = {
            'entity': 'test_entity',
            'intent_type': 'aggregate',
            'attributes': ['price', 'quantity'],  # Attributes to aggregate
            'filters': {},
            'aggregation_function': 'sum',
            'limit': 10
        }

        result = self.executor.execute(intent, user='test_user')

        assert result['success'] is True
        assert 'aggregations' in result
        assert result['aggregations']['sum_price'] == 801.50  # 100.50 + 200 + 150.75 + 300.25 + 50
        assert result['aggregations']['sum_quantity'] == 20  # 5 + 3 + 0 + 10 + 2

    def test_aggregate_intent_with_avg(self):
        """Test aggregate intent with AVG function"""
        intent = {
            'entity': 'test_entity',
            'intent_type': 'aggregate',
            'attributes': ['price', 'quantity'],
            'filters': {},
            'aggregation_function': 'avg',
            'limit': 10
        }

        result = self.executor.execute(intent, user='test_user')

        assert result['success'] is True
        assert 'aggregations' in result
        assert result['aggregations']['avg_price'] == pytest.approx(160.30, rel=0.01)  # 801.50 / 5
        assert result['aggregations']['avg_quantity'] == 4.0  # 20 / 5

    def test_aggregate_intent_with_max(self):
        """Test aggregate intent with MAX function"""
        intent = {
            'entity': 'test_entity',
            'intent_type': 'aggregate',
            'attributes': ['price', 'quantity'],
            'filters': {},
            'aggregation_function': 'max',
            'limit': 10
        }

        result = self.executor.execute(intent, user='test_user')

        assert result['success'] is True
        assert 'aggregations' in result
        assert result['aggregations']['max_price'] == 300.25
        assert result['aggregations']['max_quantity'] == 10

    def test_aggregate_intent_with_min(self):
        """Test aggregate intent with MIN function"""
        intent = {
            'entity': 'test_entity',
            'intent_type': 'aggregate',
            'attributes': ['price', 'quantity'],
            'filters': {},
            'aggregation_function': 'min',
            'limit': 10
        }

        result = self.executor.execute(intent, user='test_user')

        assert result['success'] is True
        assert 'aggregations' in result
        assert result['aggregations']['min_price'] == 50.00
        assert result['aggregations']['min_quantity'] == 0

    def test_aggregate_all_functions(self):
        """Test when no specific aggregation function is provided"""
        intent = {
            'entity': 'test_entity',
            'intent_type': 'aggregate',
            'attributes': ['price'],
            'filters': {},
            'limit': 10
        }

        result = self.executor.execute(intent, user='test_user')

        assert result['success'] is True
        assert 'aggregations' in result
        # Should provide multiple aggregations
        assert 'count' in result['aggregations']
        assert 'sum_price' in result['aggregations']
        assert 'avg_price' in result['aggregations']
        assert 'min_price' in result['aggregations']
        assert 'max_price' in result['aggregations']

    def test_aggregation_with_filters(self):
        """Test that aggregations respect filters"""
        # Note: This test shows the concept but actual filtering
        # depends on the entity's get_queryset implementation
        intent = {
            'entity': 'test_entity',
            'intent_type': 'aggregate',
            'attributes': ['price'],
            'filters': {'status': 'active'},  # Only active items
            'aggregation_function': 'sum',
            'limit': 10
        }

        result = self.executor.execute(intent, user='test_user')

        assert result['success'] is True
        # Aggregations should be calculated on filtered results
        assert 'aggregations' in result

    def test_aggregation_with_non_numeric_field(self):
        """Test that aggregation handles non-numeric fields gracefully"""
        intent = {
            'entity': 'test_entity',
            'intent_type': 'aggregate',
            'attributes': ['name', 'price'],  # name is non-numeric
            'filters': {},
            'aggregation_function': 'sum',
            'limit': 10
        }

        result = self.executor.execute(intent, user='test_user')

        assert result['success'] is True
        assert 'aggregations' in result
        # Should skip non-numeric field 'name'
        assert 'sum_price' in result['aggregations']
        assert 'sum_name' not in result['aggregations']

    def test_count_intent_with_grouping(self):
        """Test count with GROUP BY functionality"""
        intent = {
            'entity': 'test_entity',
            'intent_type': 'count',
            'attributes': [],
            'filters': {},
            'group_by': 'status',
            'limit': 10
        }

        result = self.executor.execute(intent, user='test_user')

        assert result['success'] is True
        assert 'aggregations' in result
        assert 'group_counts' in result['aggregations']
        # Should have counts grouped by status
        groups = result['aggregations']['group_counts']
        assert 'active' in groups
        assert 'inactive' in groups
        assert groups['active'] == 4
        assert groups['inactive'] == 1
