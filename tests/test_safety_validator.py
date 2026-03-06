# tests/test_safety_validator.py
import pytest
from core.safety import SafetyValidator

def test_safety_validator_accepts_valid_intent():
    """Test that valid intent passes validation"""
    intent = {
        'entity': 'synthesizer',
        'intent_type': 'query',
        'limit': 10
    }

    # Should not raise
    SafetyValidator.validate_intent(intent)

def test_safety_validator_blocks_excessive_limit():
    """Test that excessive limit is rejected"""
    intent = {
        'entity': 'synthesizer',
        'intent_type': 'query',
        'limit': 10000
    }

    with pytest.raises(ValueError, match="exceeds maximum"):
        SafetyValidator.validate_intent(intent)

def test_safety_validator_blocks_sql_injection_patterns():
    """Test that SQL injection patterns are detected"""
    intent = {
        'entity': 'synthesizer',
        'intent_type': 'query',
        'filters': {
            'status': "'; DROP TABLE instruments; --"
        }
    }

    with pytest.raises(ValueError, match="Dangerous pattern"):
        SafetyValidator.validate_intent(intent)

def test_safety_validator_blocks_dangerous_keywords():
    """Test that dangerous SQL keywords are blocked"""
    dangerous_patterns = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'INSERT']

    for pattern in dangerous_patterns:
        intent = {
            'entity': 'test',
            'intent_type': 'query',
            'filters': {'field': pattern}
        }

        with pytest.raises(ValueError, match="Dangerous pattern"):
            SafetyValidator.validate_intent(intent)
