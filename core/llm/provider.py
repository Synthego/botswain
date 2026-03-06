from abc import ABC, abstractmethod
from typing import Dict, Any

class LLMProvider(ABC):
    """Abstract interface for LLM providers"""

    @abstractmethod
    def parse_intent(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse natural language question into structured intent JSON.

        Args:
            question: User's natural language question
            context: Additional context (entity catalog, user info, etc.)

        Returns:
            Structured intent dict with entity, filters, attributes
        """
        pass

    @abstractmethod
    def format_response(self, query_results: Any, original_question: str) -> str:
        """
        Format query results into natural language response.

        Args:
            query_results: Query execution results
            original_question: User's original question

        Returns:
            Natural language response string
        """
        pass
