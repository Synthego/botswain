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
        limit = min(intent.get('limit', 100), 1000)

        # Execute query
        if hasattr(queryset, '__iter__'):
            # It's a list or queryset
            results = list(queryset)[:limit]
        else:
            results = []

        # If queryset has values() method, call it to get dicts
        if hasattr(queryset, 'values') and callable(queryset.values):
            attributes = intent.get('attributes', [])
            if attributes:
                results = list(queryset.values(*attributes))[:limit]

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
