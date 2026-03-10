"""Tests for cost calculation utility"""
import pytest
from decimal import Decimal
from core.models import QueryLog


def test_calculate_cost_sonnet():
    """Test cost calculation for Sonnet 4.5 model"""
    from core.utils.cost import calculate_cost

    cost = calculate_cost(
        input_tokens=1000,
        output_tokens=500,
        model='us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    )

    # Input: 1000 tokens * $3.00/1M = $0.003
    # Output: 500 tokens * $15.00/1M = $0.0075
    # Total: $0.0105
    assert cost == 0.0105


def test_calculate_cost_haiku():
    """Test cost calculation for Haiku 3.5 model"""
    from core.utils.cost import calculate_cost

    cost = calculate_cost(
        input_tokens=10000,
        output_tokens=5000,
        model='us.anthropic.claude-3-5-haiku-20241022-v1:0'
    )

    # Input: 10000 * $0.25/1M = $0.0025
    # Output: 5000 * $1.25/1M = $0.00625
    # Total: $0.00875
    assert cost == 0.00875


def test_calculate_cost_zero_tokens():
    """Test cost calculation with zero tokens"""
    from core.utils.cost import calculate_cost

    cost = calculate_cost(
        input_tokens=0,
        output_tokens=0,
        model='us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    )

    assert cost == 0.0


def test_calculate_cost_unknown_model():
    """Test cost calculation raises error for unknown model"""
    from core.utils.cost import calculate_cost

    with pytest.raises(ValueError, match="Unknown model"):
        calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model='unknown-model'
        )


def test_calculate_query_cost():
    """Test calculate_query_cost helper for QueryLog instances"""
    from core.utils.cost import calculate_query_cost

    # Create a mock QueryLog instance
    query_log = QueryLog(
        username='test_user',
        question='test question',
        intent={'type': 'query'},
        entity='synthesizer',
        intent_type='query',
        execution_time_ms=100,
        interface='cli',
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500
    )

    cost = calculate_query_cost(query_log, model='us.anthropic.claude-sonnet-4-5-20250929-v1:0')
    assert cost == 0.0105


def test_calculate_query_cost_null_tokens():
    """Test calculate_query_cost handles null tokens gracefully"""
    from core.utils.cost import calculate_query_cost

    # Create a QueryLog with null tokens (e.g., from ClaudeCLIProvider)
    query_log = QueryLog(
        username='test_user',
        question='test question',
        intent={'type': 'query'},
        entity='synthesizer',
        intent_type='query',
        execution_time_ms=100,
        interface='cli',
        input_tokens=None,
        output_tokens=None,
        total_tokens=None
    )

    cost = calculate_query_cost(query_log, model='us.anthropic.claude-sonnet-4-5-20250929-v1:0')
    assert cost == 0.0


def test_calculate_query_cost_partial_null_tokens():
    """Test calculate_query_cost handles partial null tokens"""
    from core.utils.cost import calculate_query_cost

    # Create a QueryLog with one null token field
    query_log = QueryLog(
        username='test_user',
        question='test question',
        intent={'type': 'query'},
        entity='synthesizer',
        intent_type='query',
        execution_time_ms=100,
        interface='cli',
        input_tokens=1000,
        output_tokens=None,
        total_tokens=None
    )

    cost = calculate_query_cost(query_log, model='us.anthropic.claude-sonnet-4-5-20250929-v1:0')
    assert cost == 0.0


def test_calculate_cost_large_numbers():
    """Test cost calculation with large token counts"""
    from core.utils.cost import calculate_cost

    # Test with 1 million tokens each
    cost = calculate_cost(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        model='us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    )

    # Input: 1M tokens * $3.00/1M = $3.00
    # Output: 1M tokens * $15.00/1M = $15.00
    # Total: $18.00
    assert cost == 18.0


def test_calculate_cost_precision():
    """Test cost calculation maintains precision for small amounts"""
    from core.utils.cost import calculate_cost

    # Test with 1 token each
    cost = calculate_cost(
        input_tokens=1,
        output_tokens=1,
        model='us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    )

    # Input: 1 token * $3.00/1M = $0.000003
    # Output: 1 token * $15.00/1M = $0.000015
    # Total: $0.000018
    assert cost == 0.000018
