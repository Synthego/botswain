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

    # ECS clusters are named {service}-{environment}
    # Each cluster contains services: web, worker, beat

    # Known ECS clusters
    KNOWN_CLUSTERS = {
        'barb': {
            'prod': 'barb-prod',
            'stage': 'barb-stage',
            'qa': 'barb-qa',
            'dev': 'barb-dev',
        },
        'buckaneer': {
            'prod': 'buckaneer-prod',
            'stage': 'buckaneer-stage',
            'qa': 'buckaneer-qa',
        },
        'kraken': {
            'prod': 'kraken-prod',
        },
        'sos': {
            'prod': 'sos-prod',
        },
        'hook': {
            'prod': 'hook-prod',
        },
        'line': {
            'prod': 'line-prod',
        },
    }

    # Service roles within each cluster
    SERVICE_ROLES = ['web', 'worker', 'beat']

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

        # Determine which cluster(s) and service(s) to query
        clusters_to_query = self._get_clusters_to_query(filters)

        if not clusters_to_query:
            # No clusters to query
            return []

        # Query each cluster
        results = []
        for cluster_name, service_roles in clusters_to_query:
            try:
                # List services in cluster if service_roles is None (query all)
                if service_roles is None:
                    list_response = client.list_services(cluster=cluster_name)
                    service_arns = list_response.get('serviceArns', [])
                    # Extract service names from ARNs
                    service_names = [arn.split('/')[-1] for arn in service_arns]
                else:
                    service_names = service_roles

                if not service_names:
                    continue

                # Describe services (up to 10 at a time due to AWS API limits)
                for i in range(0, len(service_names), 10):
                    batch = service_names[i:i+10]

                    response = client.describe_services(
                        cluster=cluster_name,
                        services=batch,
                        include=['TAGS']
                    )

                    for service in response['services']:
                        service_info = self._parse_service_info(service, cluster_name)

                        # Apply status filter if specified
                        if 'status' in filters:
                            if filters['status'].lower() == 'running' and service_info['running_count'] == 0:
                                continue
                            elif filters['status'].lower() == 'stopped' and service_info['running_count'] > 0:
                                continue

                        results.append(service_info)

            except Exception as e:
                # Query failed for this cluster, continue with others
                continue

        return results

    def _get_clusters_to_query(self, filters: Dict[str, Any]) -> List[tuple]:
        """
        Determine which clusters and services to query based on filters.

        Args:
            filters: Query filters

        Returns:
            List of tuples: (cluster_name, service_roles_list or None for all)
        """
        clusters = []
        environment = filters.get('environment', 'prod').lower()
        role_filter = filters.get('role', '').lower()

        # Specific service filter
        if 'service' in filters:
            service_name = filters['service'].lower()

            if service_name in self.KNOWN_CLUSTERS:
                # Get cluster for this service and environment
                service_clusters = self.KNOWN_CLUSTERS[service_name]
                if environment in service_clusters:
                    cluster = service_clusters[environment]
                    # Get roles to query
                    if role_filter:
                        roles = [role_filter] if role_filter in self.SERVICE_ROLES else []
                    else:
                        roles = None  # Query all services in cluster
                    clusters.append((cluster, roles))

        # Environment filter only (query all known services in that environment)
        else:
            for service_name, service_clusters in self.KNOWN_CLUSTERS.items():
                if environment in service_clusters:
                    cluster = service_clusters[environment]
                    # Get roles to query
                    if role_filter:
                        roles = [role_filter] if role_filter in self.SERVICE_ROLES else []
                    else:
                        roles = None  # Query all services in cluster
                    clusters.append((cluster, roles))

        return clusters

    def _parse_service_info(self, service: Dict[str, Any], cluster_name: str) -> Dict[str, Any]:
        """
        Parse ECS service information into structured format.

        Args:
            service: ECS service description from boto3
            cluster_name: Name of the ECS cluster (e.g., 'barb-prod')

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

        # Extract service components from cluster name and service name
        # Cluster: barb-prod, Service: web → base_service=barb, environment=prod, role=web
        cluster_parts = cluster_name.split('-')
        base_service = cluster_parts[0] if cluster_parts else 'unknown'
        environment = cluster_parts[1] if len(cluster_parts) > 1 else 'unknown'

        service_name = service['serviceName']
        role = service_name  # The service name within the cluster is the role (web, worker, beat)

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
            'service_name': f"{cluster_name}-{service_name}",  # Full name: barb-prod-web
            'cluster': cluster_name,
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
            'cluster',
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
