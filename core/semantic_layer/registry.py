from typing import Dict, List, Optional
from .entities.base import BaseEntity

class EntityRegistry:
    """Central registry of all queryable entities"""

    def __init__(self):
        self._entities: Dict[str, BaseEntity] = {}

    def register(self, entity: BaseEntity):
        """
        Register an entity in the registry.

        Args:
            entity: BaseEntity instance to register
        """
        self._entities[entity.name] = entity

    def get(self, entity_name: str) -> Optional[BaseEntity]:
        """
        Get an entity by name.

        Args:
            entity_name: Name of entity to retrieve

        Returns:
            BaseEntity instance or None if not found
        """
        return self._entities.get(entity_name)

    def list_entities(self) -> List[str]:
        """
        List all registered entity names.

        Returns:
            List of entity names
        """
        return list(self._entities.keys())

    def get_entity_descriptions(self) -> Dict[str, str]:
        """
        Get descriptions for all registered entities.

        Returns:
            Dict mapping entity names to descriptions
        """
        return {
            name: entity.description
            for name, entity in self._entities.items()
        }
