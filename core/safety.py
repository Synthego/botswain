from typing import Dict, Any

class SafetyValidator:
    """Validates query intents for safety before execution"""

    MAX_RESULTS = 1000
    MAX_EXECUTION_TIME_SECONDS = 30

    # Dangerous SQL patterns to block (must be exact case match to avoid false positives)
    DANGEROUS_PATTERNS = [
        'DROP TABLE', 'DROP DATABASE', 'DELETE FROM', 'TRUNCATE TABLE',
        'ALTER TABLE', 'INSERT INTO', 'UPDATE SET',
        '--', ';--', 'UNION SELECT', '<SCRIPT', 'JAVASCRIPT:',
        'XP_CMDSHELL', 'SP_EXECUTESQL',
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
        limit = intent.get('limit')
        if limit is not None and limit > cls.MAX_RESULTS:
            raise ValueError(
                f"Limit {limit} exceeds maximum of {cls.MAX_RESULTS}"
            )

        # Check for dangerous patterns in filters
        cls._check_dangerous_filters(intent.get('filters', {}))

    @classmethod
    def _check_dangerous_filters(cls, filters: Dict[str, Any]):
        """
        Check for SQL injection patterns in filter values.

        Args:
            filters: Filter dict to check

        Raises:
            ValueError: If dangerous pattern detected
        """
        # Check each filter value individually (not the keys)
        for key, value in filters.items():
            if value is None:
                continue

            value_str = str(value).upper()

            for pattern in cls.DANGEROUS_PATTERNS:
                if pattern in value_str:
                    raise ValueError(f"Dangerous pattern detected in filter '{key}': {pattern}")
