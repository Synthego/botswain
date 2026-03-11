# tests/test_intent_validator.py
"""
Tests for intent validation layer - Layer 1 defense for read-only enforcement.

These tests verify the intent validator blocks all write intent_types using
a whitelist approach (only query, count, aggregate allowed).
"""
import pytest
from core.llm.bedrock import BedrockProvider


class TestIntentValidator:
    """Test suite for validate_read_only_intent() method"""

    def test_intent_validator_allows_query(self):
        """Query intent_type should be allowed"""
        provider = BedrockProvider()
        intent = {'intent_type': 'query', 'entity': 'synthesizer'}

        # Should not raise
        provider.validate_read_only_intent(intent)

    def test_intent_validator_allows_count(self):
        """Count intent_type should be allowed"""
        provider = BedrockProvider()
        intent = {'intent_type': 'count', 'entity': 'workflow'}

        # Should not raise
        provider.validate_read_only_intent(intent)

    def test_intent_validator_allows_aggregate(self):
        """Aggregate intent_type should be allowed"""
        provider = BedrockProvider()
        intent = {'intent_type': 'aggregate', 'entity': 'order'}

        # Should not raise
        provider.validate_read_only_intent(intent)

    def test_intent_validator_blocks_delete(self):
        """Delete intent_type should be blocked"""
        provider = BedrockProvider()
        intent = {'intent_type': 'delete', 'entity': 'order'}

        with pytest.raises(ValueError) as exc_info:
            provider.validate_read_only_intent(intent)

        assert "Read-only violation" in str(exc_info.value)
        assert "delete" in str(exc_info.value)

    def test_intent_validator_blocks_update(self):
        """Update intent_type should be blocked"""
        provider = BedrockProvider()
        intent = {'intent_type': 'update', 'entity': 'synthesizer'}

        with pytest.raises(ValueError) as exc_info:
            provider.validate_read_only_intent(intent)

        assert "Read-only violation" in str(exc_info.value)
        assert "update" in str(exc_info.value)

    def test_intent_validator_blocks_insert(self):
        """Insert intent_type should be blocked"""
        provider = BedrockProvider()
        intent = {'intent_type': 'insert', 'entity': 'workflow'}

        with pytest.raises(ValueError) as exc_info:
            provider.validate_read_only_intent(intent)

        assert "Read-only violation" in str(exc_info.value)
        assert "insert" in str(exc_info.value)

    def test_intent_validator_blocks_create(self):
        """Create intent_type should be blocked"""
        provider = BedrockProvider()
        intent = {'intent_type': 'create', 'entity': 'order'}

        with pytest.raises(ValueError) as exc_info:
            provider.validate_read_only_intent(intent)

        assert "Read-only violation" in str(exc_info.value)
        assert "create" in str(exc_info.value)

    def test_intent_validator_blocks_drop(self):
        """Drop intent_type should be blocked"""
        provider = BedrockProvider()
        intent = {'intent_type': 'drop', 'entity': 'synthesizer'}

        with pytest.raises(ValueError) as exc_info:
            provider.validate_read_only_intent(intent)

        assert "Read-only violation" in str(exc_info.value)
        assert "drop" in str(exc_info.value)

    def test_intent_validator_case_insensitive(self):
        """Validation should be case insensitive"""
        provider = BedrockProvider()

        # QUERY (uppercase) should be allowed
        intent_upper = {'intent_type': 'QUERY', 'entity': 'instrument'}
        provider.validate_read_only_intent(intent_upper)

        # Query (mixed case) should be allowed
        intent_mixed = {'intent_type': 'Query', 'entity': 'instrument'}
        provider.validate_read_only_intent(intent_mixed)

        # DELETE (uppercase) should be blocked
        intent_delete = {'intent_type': 'DELETE', 'entity': 'order'}
        with pytest.raises(ValueError) as exc_info:
            provider.validate_read_only_intent(intent_delete)
        assert "Read-only violation" in str(exc_info.value)

    def test_intent_validator_missing_intent_type(self):
        """Missing intent_type should be blocked"""
        provider = BedrockProvider()
        intent = {'entity': 'synthesizer'}  # No intent_type

        with pytest.raises(ValueError) as exc_info:
            provider.validate_read_only_intent(intent)

        assert "Read-only violation" in str(exc_info.value)
