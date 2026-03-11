import time
from typing import Dict, Any, List
from .semantic_layer.registry import EntityRegistry
from .safety import SafetyValidator
from .cache import QueryCache
import logging

logger = logging.getLogger(__name__)


class QueryExecutor:
    """Executes queries safely with validation, programmatic aggregation, and Redis caching"""

    def __init__(self, registry: EntityRegistry = None, use_cache: bool = True):
        self.registry = registry or EntityRegistry()
        self.use_cache = use_cache

    def execute(self, intent: Dict[str, Any], user: str, bypass_cache: bool = False) -> Dict[str, Any]:
        """
        Execute query based on structured intent with Redis caching.

        Args:
            intent: Structured intent from IntentParser
            user: Username for audit logging and cache isolation
            bypass_cache: If True, skip cache and fetch fresh data

        Returns:
            Query results with metadata and optional aggregations
        """
        # Check cache first (unless bypassed)
        if self.use_cache and not bypass_cache:
            cached_result = QueryCache.get(intent, user)
            if cached_result is not None:
                logger.info(f"Returning cached result for {intent.get('entity')}")
                return cached_result

        start_time = time.time()

        # Validate intent safety
        SafetyValidator.validate_intent(intent)

        # Get entity
        entity = self.registry.get(intent['entity'])
        if not entity:
            raise ValueError(f"Unknown entity: {intent['entity']}")

        # Validate filters
        filters = intent.get('filters', {})
        if filters and not entity.validate_filters(filters):
            raise ValueError(f"Invalid filters for entity {intent['entity']}")

        # Build queryset
        queryset = entity.get_queryset(filters)

        # Apply limit (default 100, max 1000)
        intent_limit = intent.get('limit')
        if intent_limit is None:
            limit = 100
        else:
            limit = min(intent_limit, 1000)

        # Execute query - always convert to dicts for JSON serialization
        if hasattr(queryset, 'values') and callable(queryset.values):
            attributes = intent.get('attributes', [])

            # Map friendly attribute names to actual database fields
            field_mapping = {
                'barcode': 'barcode_ptr_id',
            }

            # Handle wildcard or empty attributes
            if not attributes or attributes == ['*']:
                # No specific attributes - get all fields as dicts
                results = list(queryset.values())[:limit]
            else:
                # User requested specific attributes
                # Filter out wildcards and map to database fields
                filtered_attrs = [attr for attr in attributes if attr != '*']
                mapped_attributes = [field_mapping.get(attr, attr) for attr in filtered_attrs]

                if mapped_attributes:
                    results = list(queryset.values(*mapped_attributes))[:limit]
                else:
                    # All attributes were wildcards, get everything
                    results = list(queryset.values())[:limit]

            # Rename fields back to friendly names in results
            reverse_mapping = {v: k for k, v in field_mapping.items()}
            results = [
                {reverse_mapping.get(k, k): v for k, v in item.items()}
                for item in results
            ]
        elif hasattr(queryset, '__iter__'):
            # Fallback for non-Django querysets
            results = list(queryset)[:limit]
        else:
            results = []

        execution_time = time.time() - start_time

        # Build base response
        response = {
            'success': True,
            'entity': intent['entity'],
            'results': results,
            'count': len(results),
            'execution_time_ms': int(execution_time * 1000)
        }

        # Add aggregations based on intent_type
        intent_type = intent.get('intent_type', 'query')

        if intent_type == 'count':
            # For count queries, provide accurate count and optional grouping
            aggregations = self._calculate_count_aggregations(results, intent)
            response['aggregations'] = aggregations
            # For count queries, limit raw results to reduce response size
            response['results'] = results[:10]  # Show sample only

        elif intent_type == 'aggregate':
            # For aggregate queries, calculate sum, avg, min, max
            aggregations = self._calculate_aggregations(results, intent)
            response['aggregations'] = aggregations

        # Cache the result (unless caching is disabled)
        if self.use_cache and not bypass_cache:
            QueryCache.set(intent, user, response)

        return response

    def _calculate_count_aggregations(self, results: List[Dict[str, Any]], intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate count aggregations including total count and optional grouping.

        Args:
            results: Query results
            intent: Original intent with optional group_by

        Returns:
            Dictionary with count aggregations
        """
        aggregations = {
            'total_count': len(results)
        }

        # Handle GROUP BY if specified
        group_by_field = intent.get('group_by')
        if group_by_field and results:
            group_counts = {}
            for item in results:
                group_value = item.get(group_by_field)
                if group_value is not None:
                    group_key = str(group_value)
                    group_counts[group_key] = group_counts.get(group_key, 0) + 1

            aggregations['group_counts'] = group_counts
            aggregations['grouped_by'] = group_by_field

        return aggregations

    def _calculate_aggregations(self, results: List[Dict[str, Any]], intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate programmatic aggregations (sum, avg, min, max) for numeric fields.

        Args:
            results: Query results
            intent: Original intent with attributes and aggregation_function

        Returns:
            Dictionary with calculated aggregations
        """
        if not results:
            return {'count': 0}

        aggregations = {
            'count': len(results)
        }

        # Get attributes to aggregate
        attributes = intent.get('attributes', [])
        if not attributes or attributes == ['*']:
            # If no specific attributes, aggregate all numeric fields
            attributes = list(results[0].keys()) if results else []

        # Get aggregation function (sum, avg, min, max, or all)
        agg_function = intent.get('aggregation_function', 'all')

        # Calculate aggregations for each numeric attribute
        for attr in attributes:
            # Extract numeric values for this attribute
            numeric_values = []
            for item in results:
                value = item.get(attr)
                if value is not None and self._is_numeric(value):
                    numeric_values.append(float(value))

            # Skip non-numeric or empty attributes
            if not numeric_values:
                continue

            # Calculate requested aggregations
            if agg_function in ('sum', 'all'):
                aggregations[f'sum_{attr}'] = sum(numeric_values)

            if agg_function in ('avg', 'all'):
                aggregations[f'avg_{attr}'] = sum(numeric_values) / len(numeric_values)

            if agg_function in ('min', 'all'):
                aggregations[f'min_{attr}'] = min(numeric_values)

            if agg_function in ('max', 'all'):
                aggregations[f'max_{attr}'] = max(numeric_values)

        return aggregations

    def _is_numeric(self, value: Any) -> bool:
        """
        Check if a value is numeric.

        Args:
            value: Value to check

        Returns:
            True if value is numeric, False otherwise
        """
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False
