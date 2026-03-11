"""
ECS Services entity for querying AWS ECS cluster and service status.

Uses boto3 ECS client for READ-ONLY access to service and task information.

SECURITY: Read-only access to ECS cluster metadata. Requires AWS credentials (IAM or SSO).
"""
from typing import Dict, Any, List
from datetime import datetime, timezone
from .base import BaseEntity


class ECSServicesEntity(BaseEntity):
    """
    Queries AWS ECS cluster and service operational status.

    Provides information about:
    - Service running/stopped status
    - Task counts (desired vs actual)
    - Service health and stability
    - Recent deployment status
    - Container health

    SECURITY RESTRICTIONS:
    - READ-ONLY access via boto3 ECS client
    - No write operations allowed
    - Requires AWS credentials (SSO or IAM)

    SERVICE COVERAGE:
    - BARB (web, worker, beat)
    - Buckaneer (web, worker)
    - Kraken
    - SOS, Hook, Line
    - All production/stage/qa services
    """

    name = "ecs_service"
    description = "AWS ECS cluster and service operational status. Use for questions about service running status, task counts, deployment health, container status, whether services are up/down, how many instances are running."

    # ECS cluster name
    ECS_CLUSTER = 'synthego-production'

    # Known ECS services by environment
    KNOWN_SERVICES = {
        'prod': [
            'barb-prod-web',
            'barb-prod-worker',
            'barb-prod-beat',
            'buckaneer-prod-web',
            'buckaneer-prod-worker',
            'kraken-prod',
            'sos-prod',
            'hook-prod',
            'line-prod',
        ],
        'stage': [
            'barb-stage-web',
            'barb-stage-worker',
            'buckaneer-stage-web',
        ],
        'qa': [
            'barb-qa-web',
            'buckaneer-qa-web',
        ]
    }

    # Service aliases (user might say "BARB" instead of full service names)
    SERVICE_ALIASES = {
        'barb': ['barb-prod-web', 'barb-prod-worker', 'barb-prod-beat'],
        'buckaneer': ['buckaneer-prod-web', 'buckaneer-prod-worker'],
        'kraken': ['kraken-prod'],
        'sos': ['sos-prod'],
        'hook': ['hook-prod'],
        'line': ['line-prod'],
    }

    def _get_ecs_client(self):
        """
        Get ECS client.

        Returns:
            boto3 ECS client or None if unavailable
        """
        try:
            import boto3
            return boto3.client('ecs', region_name='us-west-2')
        except ImportError:
            # boto3 not installed
            return None
        except Exception:
            # AWS credentials not configured
            return None

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get ECS service status from AWS (READ-ONLY).

        Returns a list of dicts (not a Django queryset) since ECS is an external service.

        SECURITY: All operations are read-only. No modifications to services or tasks.
        """
        client = self._get_ecs_client()
        if client is None:
            # ECS client not available (no boto3 or credentials)
            return []

        if not filters:
            # Default: return all production services
            filters = {'environment': 'prod'}

        # Determine which service(s) to query
        service_names = self._get_service_names(filters)

        if not service_names:
            # No services to query
            return []

        # Query services
        results = []
        try:
            # Describe services (up to 10 at a time due to AWS API limits)
            for i in range(0, len(service_names), 10):
                batch = service_names[i:i+10]

                response = client.describe_services(
                    cluster=self.ECS_CLUSTER,
                    services=batch,
                    include=['TAGS']
                )

                for service in response['services']:
                    service_info = self._parse_service_info(service)

                    # Apply status filter if specified
                    if 'status' in filters:
                        if filters['status'].lower() == 'running' and service_info['running_count'] == 0:
                            continue
                        elif filters['status'].lower() == 'stopped' and service_info['running_count'] > 0:
                            continue

                    results.append(service_info)

        except Exception as e:
            # Query failed
            return []

        return results

    def _get_service_names(self, filters: Dict[str, Any]) -> List[str]:
        """
        Determine which service names to query based on filters.

        Args:
            filters: Query filters

        Returns:
            List of ECS service names
        """
        service_names = []

        # Specific service filter
        if 'service' in filters:
            service = filters['service'].lower()
            env_filter = filters.get('environment', 'prod').lower()

            # Check if it's an alias (barb, buckaneer, etc.)
            if service in self.SERVICE_ALIASES:
                # Get all services for this alias
                for service_name in self.SERVICE_ALIASES[service]:
                    if env_filter in service_name or env_filter == 'all':
                        service_names.append(service_name)
            else:
                # Direct service name
                service_names.append(service)

        # Environment filter only
        elif 'environment' in filters:
            env = filters['environment'].lower()
            if env in self.KNOWN_SERVICES:
                service_names.extend(self.KNOWN_SERVICES[env])
            elif env == 'all':
                # All services across all environments
                for services in self.KNOWN_SERVICES.values():
                    service_names.extend(services)

        # Role filter (web, worker, beat)
        if 'role' in filters:
            role = filters['role'].lower()
            service_names = [s for s in service_names if role in s]

        # No filters: return all production services
        if not service_names:
            service_names.extend(self.KNOWN_SERVICES['prod'])

        return service_names

    def _parse_service_info(self, service: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse ECS service information into structured format.

        Args:
            service: ECS service description from boto3

        Returns:
            Dict with service status and health information
        """
        # Extract deployment info
        deployments = service.get('deployments', [])
        primary_deployment = None
        if deployments:
            # Primary deployment is the one with status 'PRIMARY'
            primary_deployment = next(
                (d for d in deployments if d.get('status') == 'PRIMARY'),
                deployments[0]
            )

        # Check if service is stable
        is_stable = (
            service['runningCount'] == service['desiredCount'] and
            len(deployments) == 1 and
            service['runningCount'] > 0
        )

        # Extract service name components
        service_name = service['serviceName']
        service_parts = service_name.split('-')
        base_service = service_parts[0] if service_parts else service_name
        environment = service_parts[1] if len(service_parts) > 1 else 'unknown'
        role = service_parts[2] if len(service_parts) > 2 else 'web'

        # Calculate task health percentage
        running = service['runningCount']
        desired = service['desiredCount']
        health_percentage = (running / desired * 100) if desired > 0 else 0

        # Get latest event
        events = service.get('events', [])
        latest_event = None
        if events:
            latest_event = {
                'message': events[0]['message'],
                'created_at': events[0]['createdAt'].isoformat()
            }

        return {
            'service_name': service_name,
            'base_service': base_service,
            'environment': environment,
            'role': role,
            'status': service['status'],
            'desired_count': desired,
            'running_count': running,
            'pending_count': service.get('pendingCount', 0),
            'health_percentage': round(health_percentage, 1),
            'is_stable': is_stable,
            'is_healthy': running == desired and desired > 0,
            'created_at': service['createdAt'].isoformat(),
            'launch_type': service.get('launchType', 'FARGATE'),
            'platform_version': service.get('platformVersion', 'LATEST'),

            # Deployment info
            'deployment_status': primary_deployment.get('rolloutState', 'UNKNOWN') if primary_deployment else None,
            'deployment_created_at': primary_deployment['createdAt'].isoformat() if primary_deployment and 'createdAt' in primary_deployment else None,
            'task_definition': primary_deployment.get('taskDefinition', '').split('/')[-1] if primary_deployment else None,

            # Health and events
            'latest_event': latest_event,
            'deployment_count': len(deployments),
        }

    def get_attributes(self) -> List[str]:
        """Available attributes for ECS services"""
        return [
            'service_name',
            'base_service',
            'environment',
            'role',
            'status',
            'desired_count',
            'running_count',
            'pending_count',
            'health_percentage',
            'is_stable',
            'is_healthy',
            'created_at',
            'launch_type',
            'platform_version',
            'deployment_status',
            'deployment_created_at',
            'task_definition',
            'latest_event',
            'deployment_count'
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """
        Validate that filters are safe and recognized.
        """
        valid_filters = {
            'service',
            'environment',
            'role',
            'status',
            'cluster'
        }

        # Check all filter keys are valid
        if not all(key in valid_filters for key in filters.keys()):
            return False

        return True
