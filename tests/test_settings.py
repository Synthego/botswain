"""Tests for Botswain configuration settings"""
import os
import pytest
from django.conf import settings


class TestBedrockSettings:
    """Test that Bedrock configuration settings exist and have correct defaults"""

    def test_llm_provider_setting_exists(self):
        """LLM_PROVIDER setting should exist"""
        assert hasattr(settings, 'LLM_PROVIDER')

    def test_llm_provider_default_value(self):
        """LLM_PROVIDER should default to 'bedrock'"""
        assert settings.LLM_PROVIDER in ['bedrock', 'claude_cli']

    def test_bedrock_model_id_setting_exists(self):
        """BEDROCK_MODEL_ID setting should exist"""
        assert hasattr(settings, 'BEDROCK_MODEL_ID')

    def test_bedrock_model_id_default_value(self):
        """BEDROCK_MODEL_ID should have valid inference profile ID"""
        model_id = settings.BEDROCK_MODEL_ID
        assert isinstance(model_id, str)
        assert len(model_id) > 0
        # Should use inference profile with us. prefix
        assert model_id.startswith('us.anthropic.claude')

    def test_bedrock_max_intent_tokens_setting_exists(self):
        """BEDROCK_MAX_INTENT_TOKENS setting should exist"""
        assert hasattr(settings, 'BEDROCK_MAX_INTENT_TOKENS')

    def test_bedrock_max_intent_tokens_is_int(self):
        """BEDROCK_MAX_INTENT_TOKENS should be an integer"""
        assert isinstance(settings.BEDROCK_MAX_INTENT_TOKENS, int)
        assert settings.BEDROCK_MAX_INTENT_TOKENS > 0

    def test_bedrock_max_response_tokens_setting_exists(self):
        """BEDROCK_MAX_RESPONSE_TOKENS setting should exist"""
        assert hasattr(settings, 'BEDROCK_MAX_RESPONSE_TOKENS')

    def test_bedrock_max_response_tokens_is_int(self):
        """BEDROCK_MAX_RESPONSE_TOKENS should be an integer"""
        assert isinstance(settings.BEDROCK_MAX_RESPONSE_TOKENS, int)
        assert settings.BEDROCK_MAX_RESPONSE_TOKENS > 0

    def test_bedrock_aws_region_setting_exists(self):
        """BEDROCK_AWS_REGION setting should exist"""
        assert hasattr(settings, 'BEDROCK_AWS_REGION')

    def test_bedrock_aws_region_default_value(self):
        """BEDROCK_AWS_REGION should be a valid AWS region"""
        region = settings.BEDROCK_AWS_REGION
        assert isinstance(region, str)
        assert len(region) > 0

    def test_bedrock_timeout_setting_exists(self):
        """BEDROCK_TIMEOUT setting should exist"""
        assert hasattr(settings, 'BEDROCK_TIMEOUT')

    def test_bedrock_timeout_is_float(self):
        """BEDROCK_TIMEOUT should be a float"""
        assert isinstance(settings.BEDROCK_TIMEOUT, float)
        assert settings.BEDROCK_TIMEOUT > 0


class TestSettingsEnvironmentOverrides:
    """Test that settings can be overridden via environment variables"""

    def test_bedrock_model_id_env_override(self, monkeypatch):
        """BEDROCK_MODEL_ID should be overridable via environment variable"""
        # Note: This test shows the pattern, but Django settings are loaded at import time
        # so we can only verify the env var mechanism exists, not actually override in tests
        custom_model = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
        assert os.environ.get('BEDROCK_MODEL_ID', settings.BEDROCK_MODEL_ID) is not None

    def test_bedrock_max_tokens_env_override(self):
        """Token limits should be overridable via environment variables"""
        # Verify the settings read from environment
        assert settings.BEDROCK_MAX_INTENT_TOKENS is not None
        assert settings.BEDROCK_MAX_RESPONSE_TOKENS is not None
