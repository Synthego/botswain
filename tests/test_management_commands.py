# tests/test_management_commands.py
import pytest
from decimal import Decimal
from io import StringIO
from django.core.management import call_command
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from core.models import QueryLog


@pytest.mark.django_db
class TestTokenUsageReportCommand:
    """Tests for token_usage_report management command"""

    def test_token_usage_report_command_basic(self):
        """Test basic token usage report output"""
        # Create test user
        user = User.objects.create_user(username='test@synthego.com')

        # Create test data
        QueryLog.objects.create(
            user=user,
            username='test@synthego.com',
            question="test query 1",
            intent={'entity': 'synthesizer'},
            entity='synthesizer',
            intent_type='query',
            execution_time_ms=100,
            interface='api',
            success=True,
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            estimated_cost_usd=Decimal('0.0105')
        )

        # Run command
        out = StringIO()
        call_command('token_usage_report', stdout=out)

        output = out.getvalue()

        # Verify output contains expected statistics
        assert 'Total Queries: 1' in output
        assert 'Total Input Tokens: 1000' in output
        assert 'Total Output Tokens: 500' in output
        assert 'Total Cost: $0.01' in output

    def test_token_usage_report_multiple_queries(self):
        """Test report with multiple queries"""
        user = User.objects.create_user(username='test@synthego.com')

        # Create multiple queries
        QueryLog.objects.create(
            user=user,
            username='test@synthego.com',
            question="query 1",
            intent={'entity': 'synthesizer'},
            entity='synthesizer',
            intent_type='query',
            execution_time_ms=100,
            interface='api',
            success=True,
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            estimated_cost_usd=Decimal('0.0105')
        )

        QueryLog.objects.create(
            user=user,
            username='test@synthego.com',
            question="query 2",
            intent={'entity': 'instrument'},
            entity='instrument',
            intent_type='query',
            execution_time_ms=150,
            interface='api',
            success=True,
            input_tokens=2000,
            output_tokens=1000,
            total_tokens=3000,
            estimated_cost_usd=Decimal('0.021')
        )

        # Run command
        out = StringIO()
        call_command('token_usage_report', stdout=out)

        output = out.getvalue()

        # Verify aggregated statistics
        assert 'Total Queries: 2' in output
        assert 'Total Input Tokens: 3000' in output
        assert 'Total Output Tokens: 1500' in output
        assert 'Total Cost: $0.03' in output

    def test_token_usage_report_with_date_range(self):
        """Test report with date range filtering"""
        user = User.objects.create_user(username='test@synthego.com')

        # Create old query (30 days ago)
        old_time = timezone.now() - timedelta(days=30)
        old_query = QueryLog.objects.create(
            user=user,
            username='test@synthego.com',
            question="old query",
            intent={'entity': 'synthesizer'},
            entity='synthesizer',
            intent_type='query',
            execution_time_ms=100,
            interface='api',
            success=True,
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            estimated_cost_usd=Decimal('0.0105')
        )
        # Manually update executed_at to bypass auto_now_add
        QueryLog.objects.filter(pk=old_query.pk).update(executed_at=old_time)

        # Create recent query
        QueryLog.objects.create(
            user=user,
            username='test@synthego.com',
            question="recent query",
            intent={'entity': 'instrument'},
            entity='instrument',
            intent_type='query',
            execution_time_ms=150,
            interface='api',
            success=True,
            input_tokens=2000,
            output_tokens=1000,
            total_tokens=3000,
            estimated_cost_usd=Decimal('0.021')
        )

        # Run command with date filter (last 7 days)
        start_date = (timezone.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        out = StringIO()
        call_command('token_usage_report', start_date=start_date, stdout=out)

        output = out.getvalue()

        # Verify only recent query is counted
        assert 'Total Queries: 1' in output
        assert 'Total Input Tokens: 2000' in output
        assert 'Total Output Tokens: 1000' in output

    def test_token_usage_report_empty_database(self):
        """Test report when no queries exist"""
        out = StringIO()
        call_command('token_usage_report', stdout=out)

        output = out.getvalue()

        # Should handle empty data gracefully
        assert 'Total Queries: 0' in output
        assert 'Total Input Tokens: 0' in output
        assert 'Total Output Tokens: 0' in output
        assert 'Total Cost: $0.00' in output

    def test_token_usage_report_null_tokens(self):
        """Test report with queries that have null token values"""
        user = User.objects.create_user(username='test@synthego.com')

        # Create query with null tokens (legacy data)
        QueryLog.objects.create(
            user=user,
            username='test@synthego.com',
            question="legacy query",
            intent={'entity': 'synthesizer'},
            entity='synthesizer',
            intent_type='query',
            execution_time_ms=100,
            interface='api',
            success=True,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            estimated_cost_usd=None
        )

        # Create query with tokens
        QueryLog.objects.create(
            user=user,
            username='test@synthego.com',
            question="new query",
            intent={'entity': 'instrument'},
            entity='instrument',
            intent_type='query',
            execution_time_ms=150,
            interface='api',
            success=True,
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            estimated_cost_usd=Decimal('0.0105')
        )

        # Run command
        out = StringIO()
        call_command('token_usage_report', stdout=out)

        output = out.getvalue()

        # Should only count non-null values
        assert 'Total Queries: 2' in output
        assert 'Total Input Tokens: 1000' in output
        assert 'Total Output Tokens: 500' in output
        assert 'Total Cost: $0.01' in output
