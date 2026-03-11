"""
Tests for SQL validator - read-only enforcement.

Tests TDD approach: write tests first, implement after.
"""
import pytest

from core.sql_validator import SQLValidator


class TestSQLValidatorBlocking:
    """Test that SQLValidator blocks all write operations."""

    def test_sql_validator_blocks_delete(self):
        """DELETE statements must be blocked."""
        sql = "DELETE FROM orders WHERE created_at < '2020-01-01'"

        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate(sql)

    def test_sql_validator_blocks_update(self):
        """UPDATE statements must be blocked."""
        sql = "UPDATE synthesizer SET status='offline' WHERE id=1"

        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate(sql)

    def test_sql_validator_blocks_insert(self):
        """INSERT statements must be blocked."""
        sql = "INSERT INTO workflow (id, name) VALUES (1, 'test')"

        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate(sql)

    def test_sql_validator_blocks_drop(self):
        """DROP statements must be blocked."""
        sql = "DROP TABLE inventory_synthesizer"

        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate(sql)

    def test_sql_validator_blocks_alter(self):
        """ALTER statements must be blocked."""
        sql = "ALTER TABLE orders ADD COLUMN new_field VARCHAR(255)"

        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate(sql)

    def test_sql_validator_blocks_truncate(self):
        """TRUNCATE statements must be blocked."""
        sql = "TRUNCATE TABLE workflow"

        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate(sql)


class TestSQLValidatorAllowing:
    """Test that SQLValidator allows read-only operations."""

    def test_sql_validator_allows_select(self):
        """Simple SELECT statements must be allowed."""
        sql = "SELECT * FROM orders WHERE status='pending'"

        # Should not raise
        SQLValidator.validate(sql)

    def test_sql_validator_allows_select_with_join(self):
        """Complex SELECT with JOINs must be allowed."""
        sql = """
            SELECT o.id, o.status, s.name
            FROM orders o
            JOIN synthesizer s ON o.synthesizer_id = s.id
            WHERE o.created_at > '2024-01-01'
        """

        # Should not raise
        SQLValidator.validate(sql)


class TestSQLValidatorEdgeCases:
    """Test edge cases and potential bypass attempts."""

    def test_sql_validator_rejects_empty_sql(self):
        """Empty or whitespace-only SQL must be rejected."""
        with pytest.raises(ValueError, match="Empty SQL statement"):
            SQLValidator.validate("")

        with pytest.raises(ValueError, match="Empty SQL statement"):
            SQLValidator.validate("   ")

    def test_sql_validator_strips_comments(self):
        """Comments should be stripped before validation."""
        # SELECT with comments should pass
        sql = """
            -- This is a comment
            SELECT * FROM orders
        """
        SQLValidator.validate(sql)  # Should not raise

    def test_sql_validator_blocks_write_in_comments(self):
        """Write keywords in comments should still be blocked if found in actual SQL."""
        # This has DELETE in comment but UPDATE in actual SQL - should block
        sql = """
            -- This query will DELETE old records
            UPDATE orders SET status='archived'
        """

        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate(sql)

    def test_sql_validator_case_insensitive(self):
        """Validation must be case-insensitive."""
        # Lowercase delete
        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate("delete from orders")

        # Mixed case update
        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate("uPdAtE orders SET status='done'")

        # Uppercase select should work
        SQLValidator.validate("SELECT * FROM ORDERS")  # Should not raise
