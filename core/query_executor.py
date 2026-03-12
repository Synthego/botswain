import time
from typing import Dict, Any, List
from .semantic_layer.registry import EntityRegistry
from .safety import SafetyValidator
from .cache import QueryCache
from .pagination import PaginationMetadata
import logging

logger = logging.getLogger(__name__)


class QueryExecutor:
    """Executes queries safely with validation, programmatic aggregation, and Redis caching"""

    def __init__(self, registry: EntityRegistry = None, use_cache: bool = True):
        self.registry = registry or EntityRegistry()
        self.use_cache = use_cache

    def execute(self, intent: Dict[str, Any], user: str,
                offset: int = 0, limit: int = 100,
                bypass_cache: bool = False) -> Dict[str, Any]:
        """
        Execute query based on structured intent with pagination support.

        Args:
            intent: Structured intent from IntentParser
            user: Username for audit logging and cache isolation
            offset: Number of results to skip (default 0)
            limit: Maximum results to return (default 100)
            bypass_cache: If True, skip cache and fetch fresh data

        Returns:
            Query results with metadata and pagination
        """
        # Check if this is an aggregation query
        intent_type = intent.get('intent_type', 'query')
        aggregation_function = intent.get('aggregation_function', '')
        is_aggregation = (intent_type == 'count' or (intent_type == 'aggregate' and aggregation_function == 'count')) and intent.get('group_by')

        # For aggregation queries, use cache key without pagination (aggregations are same for all pages)
        # For regular queries, include pagination in cache key
        cache_offset = 0 if is_aggregation else offset
        cache_limit = 10000 if is_aggregation else limit

        # Check cache first
        if self.use_cache and not bypass_cache:
            cached_result = QueryCache.get(intent, user, cache_offset, cache_limit)
            if cached_result is not None:
                logger.info(f"Returning cached result for {intent.get('entity')} (aggregation={is_aggregation})")
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

        # For aggregation queries, fetch ALL data to aggregate
        # For regular queries, use pagination
        if is_aggregation:
            # Fetch all matching results for aggregation (limit to reasonable max)
            fetch_limit = 10000  # Max safety limit
            fetch_offset = 0
        else:
            # Smart estimation: fetch limit+1 to determine has_next
            fetch_limit = limit + 1
            fetch_offset = offset

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
                # Apply fetch_offset and fetch_limit
                results = list(queryset.values()[fetch_offset:fetch_offset + fetch_limit])
            else:
                # User requested specific attributes
                # Filter out wildcards and map to database fields
                filtered_attrs = [attr for attr in attributes if attr != '*']
                mapped_attributes = [field_mapping.get(attr, attr) for attr in filtered_attrs]

                if mapped_attributes:
                    # Apply fetch_offset and fetch_limit
                    results = list(queryset.values(*mapped_attributes)[fetch_offset:fetch_offset + fetch_limit])
                else:
                    # All attributes were wildcards, get everything
                    # Apply fetch_offset and fetch_limit
                    results = list(queryset.values()[fetch_offset:fetch_offset + fetch_limit])

            # Rename fields back to friendly names in results
            reverse_mapping = {v: k for k, v in field_mapping.items()}
            results = [
                {reverse_mapping.get(k, k): v for k, v in item.items()}
                for item in results
            ]
        elif hasattr(queryset, '__iter__'):
            # Fallback for non-Django querysets (e.g., GitHub API, external APIs)
            # Apply fetch_offset and fetch_limit
            if hasattr(queryset, '__getitem__'):
                # Sliceable iterable
                results = list(queryset[fetch_offset:fetch_offset + fetch_limit])
            else:
                # Non-sliceable iterable - materialize and slice
                all_results = list(queryset)
                results = all_results[fetch_offset:fetch_offset + fetch_limit]

            # Apply attribute filtering for non-Django querysets
            attributes = intent.get('attributes', [])
            if attributes and attributes != ['*'] and results:
                # Filter each dict to only include requested attributes
                filtered_results = []
                for item in results:
                    if isinstance(item, dict):
                        filtered_item = {k: v for k, v in item.items() if k in attributes}
                        filtered_results.append(filtered_item)
                    else:
                        # Not a dict - keep as-is
                        filtered_results.append(item)
                results = filtered_results
        else:
            results = []

        # For aggregation queries, disable pagination of raw results
        if is_aggregation:
            # We fetched all data for aggregation
            has_next = False
            has_previous = False
            # Don't trim results yet - need all for aggregation
        else:
            # Determine pagination state for regular queries
            has_next = len(results) > limit
            has_previous = offset > 0

            # Trim to requested limit
            if has_next:
                results = results[:limit]

        execution_time = time.time() - start_time

        # Build pagination metadata
        pagination = PaginationMetadata.build(
            offset=offset,
            limit=limit,
            has_next=has_next,
            has_previous=has_previous,
            result_count=len(results)
        )

        # Build base response with pagination
        response = {
            'success': True,
            'entity': intent['entity'],
            'results': results,
            'count': len(results),
            'execution_time_ms': int(execution_time * 1000),
            'pagination': pagination
        }

        # Add aggregations based on intent_type
        if intent_type == 'count' or (intent_type == 'aggregate' and aggregation_function == 'count'):
            # For count queries, provide accurate count and optional grouping
            # Also treat aggregate queries with aggregation_function='count' as count queries
            aggregations = self._calculate_count_aggregations(results, intent)
            response['aggregations'] = aggregations

            # For aggregation queries with group_by, the table should show aggregated groups
            # For simple count queries without group_by, show sample of raw results
            if intent.get('group_by') and aggregations.get('group_counts'):
                # Convert group_counts to table format for display
                group_counts = aggregations['group_counts']
                grouped_by = aggregations['grouped_by']

                # Transform to table rows
                grouped_results = [
                    {grouped_by.title(): name, 'Count': count}
                    for name, count in group_counts.items()
                ]

                # For aggregated results, replace raw results with grouped results
                response['results'] = grouped_results
                response['count'] = len(grouped_results)

                # Update pagination to reflect aggregated results (no pagination needed)
                response['pagination'] = PaginationMetadata.build(
                    offset=0,
                    limit=len(grouped_results),
                    has_next=False,
                    has_previous=False,
                    result_count=len(grouped_results)
                )
            else:
                # For simple count queries, limit raw results to reduce response size
                response['results'] = results[:10]  # Show sample only

        elif intent_type == 'aggregate':
            # For aggregate queries, calculate sum, avg, min, max
            aggregations = self._calculate_aggregations(results, intent)
            response['aggregations'] = aggregations

        # Cache the result (use same cache key as GET)
        if self.use_cache and not bypass_cache:
            QueryCache.set(intent, user, response, cache_offset, cache_limit)

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

            # Handle multiple group-by fields (comma-separated)
            if ',' in group_by_field:
                group_fields = [f.strip() for f in group_by_field.split(',')]

                # Map field names to actual result keys
                actual_fields = []
                for field in group_fields:
                    if results and field not in results[0]:
                        # Try with _name suffix (common for ForeignKeys)
                        if f"{field}_name" in results[0]:
                            actual_fields.append(f"{field}_name")
                        # Try with _id suffix
                        elif f"{field}_id" in results[0]:
                            actual_fields.append(f"{field}_id")
                        else:
                            actual_fields.append(field)
                    else:
                        actual_fields.append(field)

                # Create composite keys from ALL results
                for item in results:
                    values = []
                    for field in actual_fields:
                        value = item.get(field)
                        if value is not None:
                            values.append(str(value))

                    if values:
                        group_key = " - ".join(values)
                        group_counts[group_key] = group_counts.get(group_key, 0) + 1

                aggregations['group_counts'] = group_counts
                aggregations['grouped_by'] = group_by_field
            else:
                # Single field grouping
                # Try to find the actual field name in results
                # (handle cases like group_by="author" but field is "author_name")
                actual_field = group_by_field
                if results and group_by_field not in results[0]:
                    # Try with _name suffix (common for ForeignKeys)
                    if f"{group_by_field}_name" in results[0]:
                        actual_field = f"{group_by_field}_name"
                    # Try with _id suffix
                    elif f"{group_by_field}_id" in results[0]:
                        actual_field = f"{group_by_field}_id"

                for item in results:
                    group_value = item.get(actual_field)
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
