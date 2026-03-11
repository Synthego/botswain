#!/usr/bin/env python
"""
Demo script showing programmatic aggregation functionality.

This demonstrates that Botswain now calculates accurate counts and aggregations
programmatically instead of relying on the LLM to do math.
"""
import sys
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'botswain.settings.test')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from core.query_executor import QueryExecutor
from core.semantic_layer.registry import EntityRegistry
from core.semantic_layer.entities.base import BaseEntity


class MockOrderEntity(BaseEntity):
    """Mock order entity with sample revenue data"""
    name = "mock_order"
    description = "Mock orders for demonstration"

    def get_queryset(self, filters=None):
        # Sample order data
        return [
            {'id': 1, 'customer': 'Acme Corp', 'total': 1500.00, 'status': 'shipped', 'items': 5},
            {'id': 2, 'customer': 'TechCo', 'total': 2300.50, 'status': 'shipped', 'items': 8},
            {'id': 3, 'customer': 'BioLab', 'total': 890.75, 'status': 'pending', 'items': 3},
            {'id': 4, 'customer': 'GeneTech', 'total': 4200.00, 'status': 'shipped', 'items': 12},
            {'id': 5, 'customer': 'Acme Corp', 'total': 750.25, 'status': 'shipped', 'items': 2},
            {'id': 6, 'customer': 'BioLab', 'total': 1100.00, 'status': 'pending', 'items': 4},
            {'id': 7, 'customer': 'ResearchCo', 'total': 3200.00, 'status': 'shipped', 'items': 10},
        ]

    def validate_filters(self, filters):
        return True

    def get_attributes(self):
        return ['id', 'customer', 'total', 'status', 'items']


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def demo_count_query():
    """Demonstrate accurate count queries"""
    print_section("COUNT QUERY - Accurate Programmatic Counting")

    registry = EntityRegistry()
    registry.register(MockOrderEntity())
    executor = QueryExecutor(registry=registry)

    # Count all orders
    intent = {
        'entity': 'mock_order',
        'intent_type': 'count',
        'attributes': [],
        'filters': {},
        'limit': 10
    }

    result = executor.execute(intent, user='demo_user')

    print("Question: How many orders are there?")
    print(f"\n✅ Result:")
    print(f"   Total Count: {result['aggregations']['total_count']}")
    print(f"   Execution Time: {result['execution_time_ms']}ms")
    print(f"\n   Sample Results: {len(result['results'])} shown (full count in aggregations)")


def demo_count_with_grouping():
    """Demonstrate GROUP BY counting"""
    print_section("COUNT WITH GROUP BY - Grouped Counting")

    registry = EntityRegistry()
    registry.register(MockOrderEntity())
    executor = QueryExecutor(registry=registry)

    intent = {
        'entity': 'mock_order',
        'intent_type': 'count',
        'attributes': [],
        'filters': {},
        'group_by': 'status',
        'limit': 10
    }

    result = executor.execute(intent, user='demo_user')

    print("Question: How many orders by status?")
    print(f"\n✅ Result:")
    print(f"   Total Count: {result['aggregations']['total_count']}")
    print(f"   Group Counts:")
    for status, count in result['aggregations']['group_counts'].items():
        print(f"      {status}: {count} orders")


def demo_sum_aggregate():
    """Demonstrate SUM aggregation"""
    print_section("SUM AGGREGATION - Accurate Revenue Total")

    registry = EntityRegistry()
    registry.register(MockOrderEntity())
    executor = QueryExecutor(registry=registry)

    intent = {
        'entity': 'mock_order',
        'intent_type': 'aggregate',
        'attributes': ['total', 'items'],
        'filters': {},
        'aggregation_function': 'sum',
        'limit': 10
    }

    result = executor.execute(intent, user='demo_user')

    print("Question: What's the total revenue from all orders?")
    print(f"\n✅ Result:")
    print(f"   Total Revenue: ${result['aggregations']['sum_total']:,.2f}")
    print(f"   Total Items: {result['aggregations']['sum_items']}")
    print(f"   Execution Time: {result['execution_time_ms']}ms")


def demo_avg_aggregate():
    """Demonstrate AVG aggregation"""
    print_section("AVG AGGREGATION - Average Order Value")

    registry = EntityRegistry()
    registry.register(MockOrderEntity())
    executor = QueryExecutor(registry=registry)

    intent = {
        'entity': 'mock_order',
        'intent_type': 'aggregate',
        'attributes': ['total'],
        'filters': {},
        'aggregation_function': 'avg',
        'limit': 10
    }

    result = executor.execute(intent, user='demo_user')

    print("Question: What's the average order value?")
    print(f"\n✅ Result:")
    print(f"   Average Order Value: ${result['aggregations']['avg_total']:,.2f}")
    print(f"   Based on: {result['aggregations']['count']} orders")


def demo_min_max_aggregate():
    """Demonstrate MIN/MAX aggregation"""
    print_section("MIN/MAX AGGREGATION - Order Value Range")

    registry = EntityRegistry()
    registry.register(MockOrderEntity())
    executor = QueryExecutor(registry=registry)

    intent = {
        'entity': 'mock_order',
        'intent_type': 'aggregate',
        'attributes': ['total'],
        'filters': {},
        'aggregation_function': 'all',  # Get all aggregations
        'limit': 10
    }

    result = executor.execute(intent, user='demo_user')

    print("Question: What are the min/max order values?")
    print(f"\n✅ Result:")
    print(f"   Minimum Order: ${result['aggregations']['min_total']:,.2f}")
    print(f"   Maximum Order: ${result['aggregations']['max_total']:,.2f}")
    print(f"   Average Order: ${result['aggregations']['avg_total']:,.2f}")
    print(f"   Total Revenue: ${result['aggregations']['sum_total']:,.2f}")


def main():
    """Run all demonstrations"""
    print("\n")
    print("┌" + "─" * 68 + "┐")
    print("│" + " " * 68 + "│")
    print("│" + "  BOTSWAIN PROGRAMMATIC AGGREGATION DEMONSTRATION".center(68) + "│")
    print("│" + " " * 68 + "│")
    print("│" + "  Accurate counts and math calculations without LLM errors".center(68) + "│")
    print("│" + " " * 68 + "│")
    print("└" + "─" * 68 + "┘")

    # Run demos
    demo_count_query()
    demo_count_with_grouping()
    demo_sum_aggregate()
    demo_avg_aggregate()
    demo_min_max_aggregate()

    # Summary
    print_section("BENEFITS")
    print("✅ Accurate Math: No LLM calculation errors")
    print("✅ Faster Responses: Less token usage for formatting")
    print("✅ Consistent Results: Same calculation every time")
    print("✅ Complex Aggregations: GROUP BY, SUM, AVG, MIN, MAX")
    print("✅ Cost Savings: Reduced output tokens\n")


if __name__ == '__main__':
    main()
