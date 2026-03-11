import time
from typing import Dict, Any, List
from .semantic_layer.registry import EntityRegistry
from .safety import SafetyValidator

class QueryExecutor:
    """Executes queries safely with validation"""

    def __init__(self, registry: EntityRegistry = None):
        self.registry = registry or EntityRegistry()

    def execute(self, intent: Dict[str, Any], user: str) -> Dict[str, Any]:
        """
        Execute query based on structured intent.

        Args:
            intent: Structured intent from IntentParser
            user: Username for audit logging

        Returns:
            Query results with metadata
        """
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

        # Build response
        response = {
            'success': True,
            'entity': intent['entity'],
            'results': results,
            'count': len(results),
            'execution_time_ms': int(execution_time * 1000)
        }

        return response
