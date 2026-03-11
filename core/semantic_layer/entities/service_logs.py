"""
Service Logs entity for querying Django/FastAPI/gRPC service logs from CloudWatch.
Covers BARB, Buckaneer, Kraken, SOS, Hook, Line, and other web services.

Uses boto3 CloudWatch Logs client for READ-ONLY access.

SECURITY: Read-only access to CloudWatch Logs. Requires AWS credentials.
RETENTION: Production logs retained for 30 days, Stage 14 days, QA/Dev 7 days.
"""
import json
from typing import Dict, Any, List
from datetime import datetime, timedelta
from .base import BaseEntity


class ServiceLogsEntity(BaseEntity):
    """
    Queries Django/FastAPI/gRPC service logs from AWS CloudWatch Logs.

    Supports:
    - BARB (Django web + Celery workers)
    - Buckaneer (Django e-commerce backend)
    - Kraken (gRPC workflow orchestration)
    - SOS (Sequencing coordination)
    - Hook, Line (Internal UIs)
    - All other ECS Fargate services

    SECURITY RESTRICTIONS:
    - READ-ONLY access via boto3 CloudWatch Logs client
    - No write operations allowed
    - Requires AWS credentials (SSO or IAM)

    RETENTION:
    - Production: 30 days
    - Stage: 14 days
    - QA/Dev: 7 days
    """

    name = "service_log"
    description = "Django/FastAPI/gRPC service logs from CloudWatch. Covers BARB, Buckaneer, Kraken, SOS, Hook, Line. Use for questions about web service errors, API failures, Celery task issues, 500 errors, database errors, Django exceptions."

    # CloudWatch Log Groups by service and environment
    LOG_GROUPS = {
        'barb-prod': '/ecs/fargate/barb-prod',
        'barb-stage': '/ecs/fargate/barb-stage',
        'barb-qa': '/ecs/fargate/barb-qa',
        'buckaneer-prod': '/ecs/fargate/buckaneer-prod',
        'buckaneer-stage': '/ecs/fargate/buckaneer-stage',
        'buckaneer-qa': '/ecs/fargate/buckaneer-qa',
        'kraken-prod': '/ecs/fargate/kraken-prod',
        'sos-prod': '/ecs/fargate/sos-prod',
        'hook-prod': '/ecs/fargate/hook-prod',
        'line-prod': '/ecs/fargate/line-prod',
    }

    # Service name inference (user might say "BARB" instead of "barb-prod")
    SERVICE_ALIASES = {
        'barb': 'barb-prod',
        'buckaneer': 'buckaneer-prod',
        'kraken': 'kraken-prod',
        'sos': 'sos-prod',
        'hook': 'hook-prod',
        'line': 'line-prod',
    }

    def _get_cloudwatch_client(self):
        """
        Get CloudWatch Logs client.

        Returns:
            boto3 CloudWatch Logs client or None if unavailable
        """
        try:
            import boto3
            return boto3.client('logs', region_name='us-west-2')
        except ImportError:
            # boto3 not installed
            return None
        except Exception:
            # AWS credentials not configured
            return None

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get service logs from CloudWatch Logs (READ-ONLY).

        Returns a list of dicts (not a Django queryset) since CloudWatch is an external service.

        SECURITY: All operations are read-only. No modifications to log data.
        """
        client = self._get_cloudwatch_client()
        if client is None:
            # CloudWatch not available (no boto3 or credentials)
            return []

        # Build CloudWatch Insights query
        log_groups, query_string, start_time, end_time = self._build_cloudwatch_query(filters)

        if not log_groups:
            # No log groups specified
            return []

        try:
            # Start CloudWatch Insights query
            response = client.start_query(
                logGroupNames=log_groups,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query_string,
                limit=filters.get('limit', 100) if filters else 100
            )

            query_id = response['queryId']

            # Poll for results
            import time
            max_wait = 30  # seconds
            start_poll = time.time()

            while time.time() - start_poll < max_wait:
                result = client.get_query_results(queryId=query_id)
                status = result['status']

                if status == 'Complete':
                    # Parse results
                    logs = []
                    for result_row in result['results']:
                        log_entry = {}
                        for field in result_row:
                            field_name = field['field'].lstrip('@')  # Remove @ prefix
                            log_entry[field_name] = field['value']
                        logs.append(log_entry)
                    return logs

                elif status == 'Failed' or status == 'Cancelled':
                    # Query failed
                    return []

                # Still running, wait before polling again
                time.sleep(1)

            # Timeout
            return []

        except Exception as e:
            # Query failed
            return []

    def _build_cloudwatch_query(self, filters: Dict[str, Any] = None):
        """
        Build CloudWatch Insights query from filters.

        Args:
            filters: Query filters

        Returns:
            Tuple of (log_groups, query_string, start_time, end_time)
        """
        # Default time range: last 1 hour
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)

        # Default: query production services
        log_groups = [self.LOG_GROUPS['barb-prod']]

        # Base query
        query_parts = ['fields @timestamp, @message, @logStream']
        filters_list = []

        if not filters:
            query_string = ' | '.join(query_parts + ['sort @timestamp desc', 'limit 100'])
            return log_groups, query_string, start_time, end_time

        # Service filter (determines which log group(s) to query)
        if 'service' in filters:
            service = filters['service'].lower()
            # Handle aliases (barb → barb-prod)
            if service in self.SERVICE_ALIASES:
                service = self.SERVICE_ALIASES[service]

            if service in self.LOG_GROUPS:
                log_groups = [self.LOG_GROUPS[service]]

        # Environment filter (prod, stage, qa)
        if 'environment' in filters:
            env = filters['environment'].lower()
            if 'service' in filters:
                base_service = filters['service'].lower()
                if base_service in self.SERVICE_ALIASES:
                    base_service = list(self.SERVICE_ALIASES.keys())[
                        list(self.SERVICE_ALIASES.values()).index(base_service)
                    ]
                service_key = f"{base_service}-{env}"
                if service_key in self.LOG_GROUPS:
                    log_groups = [self.LOG_GROUPS[service_key]]

        # Level filter (ERROR, WARNING, INFO, etc.)
        if 'level' in filters:
            level = filters['level'].upper()
            filters_list.append(f'@message like /{level}/')

        # Search filter (message content)
        if 'search' in filters or 'message' in filters:
            search_term = filters.get('search') or filters.get('message')
            # Escape special regex characters
            search_term = search_term.replace('/', '\\/')
            filters_list.append(f'@message like /{search_term}/')

        # Role filter (web, worker, beat)
        if 'role' in filters:
            role = filters['role'].lower()
            filters_list.append(f'@logStream like /{role}/')

        # Time range filters
        if 'since' in filters or 'start_time' in filters:
            since_value = filters.get('since') or filters.get('start_time')
            start_time = self._parse_date_filter(since_value)

        if 'until' in filters or 'end_time' in filters:
            until_value = filters.get('until') or filters.get('end_time')
            end_time = self._parse_date_filter(until_value)

        # Add filters to query
        if filters_list:
            query_parts.append('filter ' + ' and '.join(filters_list))

        # Sort and limit
        query_parts.append('sort @timestamp desc')
        limit = filters.get('limit', 100)
        query_parts.append(f'limit {min(limit, 1000)}')  # Cap at 1000

        query_string = ' | '.join(query_parts)

        return log_groups, query_string, start_time, end_time

    def _parse_date_filter(self, date_value: str) -> datetime:
        """
        Parse date filter value into datetime.

        Handles:
        - SQL interval expressions: "NOW() - INTERVAL '30 days'"
        - Relative: "1h", "24h", "7d", "30d"
        - ISO dates: "2026-03-10T12:00:00"
        """
        date_str = str(date_value).strip()

        # Handle relative time expressions (1h, 24h, 7d, etc.)
        if date_str.endswith('h'):
            hours = int(date_str[:-1])
            return datetime.utcnow() - timedelta(hours=hours)
        elif date_str.endswith('d'):
            days = int(date_str[:-1])
            return datetime.utcnow() - timedelta(days=days)

        # Handle SQL interval expressions
        date_str_upper = date_str.upper()
        if "NOW()" in date_str_upper and "INTERVAL" in date_str_upper:
            import re
            match = re.search(r"(\d+)\s*(DAY|HOUR|WEEK|MONTH)", date_str_upper)
            if match:
                amount = int(match.group(1))
                unit = match.group(2)

                if unit == "DAY":
                    return datetime.utcnow() - timedelta(days=amount)
                elif unit == "HOUR":
                    return datetime.utcnow() - timedelta(hours=amount)
                elif unit == "WEEK":
                    return datetime.utcnow() - timedelta(weeks=amount)
                elif unit == "MONTH":
                    return datetime.utcnow() - timedelta(days=amount * 30)

        # Handle ISO dates
        try:
            return datetime.fromisoformat(date_value)
        except (ValueError, TypeError):
            pass

        # Default to now if can't parse
        return datetime.utcnow()

    def get_attributes(self) -> List[str]:
        """Available attributes for service logs"""
        return [
            'timestamp',
            'message',
            'logStream',
            'service',
            'environment',
            'role'
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """
        Validate that filters are safe and recognized.
        """
        valid_filters = {
            'service',
            'environment',
            'level',
            'role',
            'search',
            'message',
            'since',
            'start_time',
            'until',
            'end_time',
            'limit'
        }

        # Check all filter keys are valid
        if not all(key in valid_filters for key in filters.keys()):
            return False

        return True
