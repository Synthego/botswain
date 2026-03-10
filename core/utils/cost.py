"""Cost calculation utilities for LLM API usage

Calculates the cost in USD for LLM API calls based on token usage.
"""
from decimal import Decimal

# Pricing per million tokens (USD)
# Source: https://aws.amazon.com/bedrock/pricing/
# Verified: 2026-03-09
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

# Tokens per million constant for cost calculations
TOKENS_PER_MILLION = Decimal('1000000')


def calculate_bedrock_cost(input_tokens: int, output_tokens: int, model: str) -> Decimal:
    """Calculate cost in USD for given token usage

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model ID (e.g., 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')

    Returns:
        Cost in USD (Decimal)

    Note:
        Unknown models default to Sonnet 4.5 pricing

    Example:
        >>> calculate_bedrock_cost(1000, 500, 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
        Decimal('0.0105')
    """
    # Default to Sonnet 4.5 pricing if model is unknown
    pricing = PRICING.get(
        model,
        PRICING['us.anthropic.claude-sonnet-4-5-20250929-v1:0']
    )

    # Calculate cost per token type
    # Cost = (tokens / 1,000,000) * price_per_million
    input_cost = (Decimal(input_tokens) / TOKENS_PER_MILLION) * pricing['input']
    output_cost = (Decimal(output_tokens) / TOKENS_PER_MILLION) * pricing['output']

    return input_cost + output_cost


def calculate_query_bedrock_cost(query_log: 'QueryLog', model: str) -> Decimal:
    """Calculate cost for a QueryLog instance

    Args:
        query_log: QueryLog model instance with input_tokens and output_tokens fields
        model: Model ID used for the query

    Returns:
        Cost in USD (Decimal), or Decimal('0') if token data is incomplete

    Example:
        >>> query_log = QueryLog(input_tokens=1000, output_tokens=500, ...)
        >>> calculate_query_bedrock_cost(query_log, 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
        Decimal('0.0105')
    """
    # Return 0 if token data is incomplete (e.g., from ClaudeCLIProvider)
    if query_log.input_tokens is None or query_log.output_tokens is None:
        return Decimal('0')

    return calculate_bedrock_cost(
        input_tokens=query_log.input_tokens,
        output_tokens=query_log.output_tokens,
        model=model
    )
