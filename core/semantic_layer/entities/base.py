from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseEntity(ABC):
    """Base class for all queryable entities"""

    name: str
    description: str

    @abstractmethod
    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Return Django ORM queryset (or list of dicts for non-ORM sources).

        Args:
            filters: Dictionary of filter conditions

        Returns:
            Queryset or list of result dicts
        """
        pass

    @abstractmethod
    def get_attributes(self) -> List[str]:
        """
        Return list of queryable attribute names.

        Returns:
            List of attribute names (e.g., ['name', 'status', 'factory'])
        """
        pass

    @abstractmethod
    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """
        Validate that filter dict contains only allowed fields.

        Args:
            filters: Dictionary of filter conditions

        Returns:
            True if valid, False otherwise
        """
        pass
