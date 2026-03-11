"""
End-to-end security tests for read-only enforcement.

Tests attack scenarios across all defense layers.
"""
import pytest
from unittest.mock import Mock, patch


class TestReadOnlyEnforcement:
    """Test suite for read-only security across all layers"""

    def test_intent_layer_blocks_delete(self):
        """Layer 1: Intent validator must block delete intent"""
        from core.llm.bedrock import BedrockProvider

        provider = BedrockProvider()
        dangerous_intent = {
            'intent_type': 'delete',
            'entity': 'order',
            'filters': {'id': 123}
        }

        with pytest.raises(ValueError, match="Read-only violation"):
            provider.validate_read_only_intent(dangerous_intent)

    def test_sql_layer_blocks_update(self):
        """Layer 2: SQL validator must block UPDATE statements"""
        from core.sql_validator import SQLValidator

        malicious_sql = "UPDATE synthesizer SET status='offline'"

        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate(malicious_sql)

    def test_sql_layer_blocks_injection_attempt(self):
        """Layer 2: SQL validator properly removes comments before validation"""
        from core.sql_validator import SQLValidator

        # Comments are removed, so this is safe (just a SELECT after comment removal)
        safe_with_comment = "SELECT * FROM orders /* DELETE FROM orders */"
        SQLValidator.validate(safe_with_comment)  # Should not raise

        # But actual DELETE keyword outside comment is blocked
        actual_delete = "SELECT * FROM orders; DELETE FROM orders"
        with pytest.raises(ValueError, match="Read-only violation"):
            SQLValidator.validate(actual_delete)

    def test_multiple_write_keywords_all_blocked(self):
        """Layer 2: All write operations blocked"""
        from core.sql_validator import SQLValidator

        dangerous_operations = [
            "INSERT INTO orders VALUES (1, 'test')",
            "UPDATE orders SET status='cancelled'",
            "DELETE FROM orders WHERE id=1",
            "DROP TABLE orders",
            "ALTER TABLE orders ADD COLUMN test INT",
            "TRUNCATE TABLE orders",
            "CREATE TABLE hacked (id INT)",
        ]

        for sql in dangerous_operations:
            with pytest.raises(ValueError, match="Read-only violation"):
                SQLValidator.validate(sql)

    def test_case_variations_all_blocked(self):
        """Security must be case-insensitive"""
        from core.sql_validator import SQLValidator

        case_variations = [
            "DELETE FROM orders",
            "delete from orders",
            "DeLeTe FrOm orders",
            "dElEtE fRoM orders",
        ]

        for sql in case_variations:
            with pytest.raises(ValueError, match="Read-only violation"):
                SQLValidator.validate(sql)

    def test_legitimate_selects_allowed(self):
        """Layer 2: Legitimate SELECT queries must work"""
        from core.sql_validator import SQLValidator

        legitimate_queries = [
            "SELECT * FROM orders",
            "SELECT COUNT(*) FROM synthesizer WHERE status='online'",
            "SELECT o.id, c.name FROM orders o JOIN customer c ON o.customer_id=c.id",
            """
            SELECT
                order_id,
                customer_name,
                created_at
            FROM orders
            WHERE created_at > '2024-01-01'
            ORDER BY created_at DESC
            LIMIT 100
            """,
        ]

        for sql in legitimate_queries:
            # Should not raise
            SQLValidator.validate(sql)

    def test_defense_in_depth_multiple_layers(self):
        """Verify multiple independent layers block writes"""
        from core.llm.bedrock import BedrockProvider
        from core.sql_validator import SQLValidator

        # Layer 1: Intent validation
        provider = BedrockProvider()
        with pytest.raises(ValueError):
            provider.validate_read_only_intent({'intent_type': 'delete', 'entity': 'order'})

        # Layer 2: SQL validation (independent of Layer 1)
        with pytest.raises(ValueError):
            SQLValidator.validate("DELETE FROM orders")

        # Both layers working independently


class TestJailbreakResistance:
    """Test resistance to LLM jailbreak attempts"""

    def test_rejects_admin_mode_claim(self):
        """LLM should not accept 'admin mode' claims"""
        from core.llm.bedrock import BedrockProvider

        provider = BedrockProvider()

        # Even if LLM generated this, validator catches it
        fake_admin_intent = {
            'intent_type': 'admin_delete',
            'entity': 'order',
            'reason': 'admin mode enabled'
        }

        with pytest.raises(ValueError, match="Read-only violation"):
            provider.validate_read_only_intent(fake_admin_intent)

    def test_rejects_disguised_write_operations(self):
        """Validator must catch writes regardless of naming"""
        from core.llm.bedrock import BedrockProvider

        provider = BedrockProvider()

        disguised_writes = [
            {'intent_type': 'modify', 'entity': 'order'},
            {'intent_type': 'remove', 'entity': 'order'},
            {'intent_type': 'write', 'entity': 'order'},
            {'intent_type': 'create', 'entity': 'order'},
        ]

        for intent in disguised_writes:
            with pytest.raises(ValueError, match="Read-only violation"):
                provider.validate_read_only_intent(intent)


class TestErrorMessages:
    """Test that error messages are clear and actionable"""

    def test_intent_error_message_clarity(self):
        """Intent validation errors must be clear"""
        from core.llm.bedrock import BedrockProvider

        provider = BedrockProvider()

        with pytest.raises(ValueError) as exc_info:
            provider.validate_read_only_intent({'intent_type': 'delete', 'entity': 'order'})

        error_msg = str(exc_info.value)
        assert 'Read-only violation' in error_msg
        assert 'delete' in error_msg.lower()
        assert 'Only' in error_msg  # Lists allowed types

    def test_sql_error_message_clarity(self):
        """SQL validation errors must be clear"""
        from core.sql_validator import SQLValidator

        with pytest.raises(ValueError) as exc_info:
            SQLValidator.validate("DELETE FROM orders")

        error_msg = str(exc_info.value)
        assert 'Read-only violation' in error_msg
        assert 'DELETE' in error_msg or 'delete' in error_msg
        assert 'SELECT' in error_msg  # Explains what is allowed
