from typing import Dict, Any

class SafetyValidator:
    """Validates query intents for safety before execution"""

    MAX_RESULTS = 1000
    MAX_EXECUTION_TIME_SECONDS = 30

    # Dangerous SQL patterns to block
    DANGEROUS_PATTERNS = [
        'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'INSERT', 'UPDATE',
        '--', ';--', 'EXEC', 'EXECUTE', 'UNION', 'SCRIPT',
        'xp_', 'sp_',  # SQL Server stored procedures
    ]

    @classmethod
    def validate_intent(cls, intent: Dict[str, Any]):
        """
        Validate that intent is safe to execute.

        Args:
            intent: Structured intent dict

        Raises:
            ValueError: If intent is unsafe
        """
        # Check limit
        limit = intent.get('limit', 0)
        if limit > cls.MAX_RESULTS:
            raise ValueError(
                f"Limit {limit} exceeds maximum of {cls.MAX_RESULTS}"
            )

        # Check for dangerous patterns in filters
        cls._check_dangerous_filters(intent.get('filters', {}))

    @classmethod
    def _check_dangerous_filters(cls, filters: Dict[str, Any]):
        """
        Check for SQL injection patterns in filters.

        Args:
            filters: Filter dict to check

        Raises:
            ValueError: If dangerous pattern detected
        """
        # Convert filters to string for pattern matching
        filter_str = str(filters).upper()

        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern in filter_str:
                raise ValueError(f"Dangerous pattern detected: {pattern}")
