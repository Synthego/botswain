"""Cost calculation utilities for LLM API usage

Calculates the cost in USD for LLM API calls based on token usage.
"""
from decimal import Decimal
from typing import Optional

# Pricing per million tokens (USD)
PRICING = {
    'us.anthropic.claude-sonnet-4-5-20250929-v1:0': {
        'input': Decimal('3.00'),
        'output': Decimal('15.00'),
    },
    'us.anthropic.claude-3-5-haiku-20241022-v1:0': {
        'input': Decimal('0.25'),
        'output': Decimal('1.25'),
    },
}


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate cost in USD for given token usage

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model ID (e.g., 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')

    Returns:
        Cost in USD (float)

    Raises:
        ValueError: If model is not recognized

    Example:
        >>> calculate_cost(1000, 500, 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
        0.0105
    """
    if model not in PRICING:
        raise ValueError(f"Unknown model: {model}")

    pricing = PRICING[model]

    # Calculate cost per token type
    # Cost = (tokens / 1,000,000) * price_per_million
    input_cost = (Decimal(input_tokens) / Decimal('1000000')) * pricing['input']
    output_cost = (Decimal(output_tokens) / Decimal('1000000')) * pricing['output']

    return float(input_cost + output_cost)


def calculate_query_cost(query_log, model: str) -> float:
    """Calculate cost for a QueryLog instance

    Args:
        query_log: QueryLog model instance with input_tokens and output_tokens fields
        model: Model ID used for the query

    Returns:
        Cost in USD (float), or 0.0 if token data is incomplete

    Example:
        >>> query_log = QueryLog(input_tokens=1000, output_tokens=500, ...)
        >>> calculate_query_cost(query_log, 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
        0.0105
    """
    # Return 0.0 if token data is incomplete (e.g., from ClaudeCLIProvider)
    if query_log.input_tokens is None or query_log.output_tokens is None:
        return 0.0

    return calculate_cost(
        input_tokens=query_log.input_tokens,
        output_tokens=query_log.output_tokens,
        model=model
    )
