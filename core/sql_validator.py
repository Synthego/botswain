"""
SQL statement validation for read-only enforcement.

Uses whitelist approach - only SELECT statements allowed.
"""
import re
import logging

logger = logging.getLogger(__name__)


class SQLValidator:
    """
    Validates SQL statements are read-only.

    Blocks any SQL that isn't a SELECT statement.
    """

    # Only SELECT is allowed
    ALLOWED_STATEMENTS = {'SELECT'}

    # These keywords indicate write operations
    WRITE_KEYWORDS = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
        'ALTER', 'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT',
        'REVOKE', 'EXECUTE', 'CALL', 'EXEC', 'PRAGMA'
    }

    @classmethod
    def validate(cls, sql: str) -> None:
        """
        Validate SQL statement is read-only.

        Args:
            sql: SQL statement to validate

        Raises:
            ValueError: If SQL attempts write operation
        """
        if not sql or not sql.strip():
            raise ValueError("Empty SQL statement")

        # Normalize SQL
        sql_upper = sql.strip().upper()

        # Remove comments (both -- and /* */ style)
        sql_upper = cls._remove_comments(sql_upper)

        # Get first keyword
        first_keyword = cls._get_first_keyword(sql_upper)

        # Check if first keyword is allowed
        if first_keyword not in cls.ALLOWED_STATEMENTS:
            logger.warning(
                "Read-only violation: SQL statement blocked",
                extra={
                    'first_keyword': first_keyword,
                    'sql_preview': sql[:100]
                }
            )
            raise ValueError(
                f"Read-only violation: SQL statement starts with '{first_keyword}'. "
                f"Only SELECT statements are allowed."
            )

        # Check for write keywords anywhere in statement (whole word match only)
        for keyword in cls.WRITE_KEYWORDS:
            # Use word boundary regex to avoid false positives like "created_at" matching "CREATE"
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, sql_upper):
                logger.warning(
                    "Read-only violation: Dangerous keyword detected",
                    extra={
                        'keyword': keyword,
                        'sql_preview': sql[:100]
                    }
                )
                raise ValueError(
                    f"Read-only violation: Dangerous keyword '{keyword}' detected in SQL. "
                    f"Only SELECT queries are allowed."
                )

    @classmethod
    def _remove_comments(cls, sql: str) -> str:
        """Remove SQL comments."""
        # Remove -- style comments
        lines = []
        for line in sql.split('\n'):
            if '--' in line:
                line = line[:line.index('--')]
            lines.append(line)
        sql = ' '.join(lines)

        # Remove /* */ style comments
        sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)

        return sql

    @classmethod
    def _get_first_keyword(cls, sql: str) -> str:
        """Get first SQL keyword."""
        tokens = sql.split()
        return tokens[0] if tokens else ''
