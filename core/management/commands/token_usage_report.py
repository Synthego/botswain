# core/management/commands/token_usage_report.py
from django.core.management.base import BaseCommand
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import datetime
from core.models import QueryLog


class Command(BaseCommand):
    help = 'Generate token usage and cost report from QueryLog data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for filtering (YYYY-MM-DD format)',
            dest='start_date'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for filtering (YYYY-MM-DD format)',
            dest='end_date'
        )

    def handle(self, *args, **options):
        queryset = QueryLog.objects.all()

        # Filter by date range if provided
        if options.get('start_date'):
            # Parse date string and make it timezone-aware
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
            start_date = timezone.make_aware(start_date)
            queryset = queryset.filter(executed_at__gte=start_date)
        if options.get('end_date'):
            # Parse date string and make it timezone-aware
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d')
            end_date = timezone.make_aware(end_date)
            queryset = queryset.filter(executed_at__lte=end_date)

        # Calculate aggregates
        stats = queryset.aggregate(
            total_queries=Count('id'),
            total_input=Sum('input_tokens'),
            total_output=Sum('output_tokens'),
            total_cost=Sum('estimated_cost_usd')
        )

        # Output report header
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('Token Usage Report'))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))

        # Display date range if filters applied
        if options.get('start_date') or options.get('end_date'):
            self.stdout.write(self.style.WARNING('Date Range:'))
            if options.get('start_date'):
                self.stdout.write(f"  Start: {options['start_date']}")
            if options.get('end_date'):
                self.stdout.write(f"  End: {options['end_date']}")
            self.stdout.write('')

        # Display statistics
        self.stdout.write(f"Total Queries: {stats['total_queries']}")
        self.stdout.write(f"Total Input Tokens: {stats['total_input'] or 0}")
        self.stdout.write(f"Total Output Tokens: {stats['total_output'] or 0}")
        self.stdout.write(f"Total Cost: ${stats['total_cost'] or 0:.2f}")

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60 + '\n'))
