"""
RDS Databases entity for querying AWS RDS database operational status.

Uses boto3 RDS client for READ-ONLY access to database instance information.

SECURITY: Read-only access to RDS metadata. Requires AWS credentials (IAM or SSO).
"""
from typing import Dict, Any, List
from datetime import datetime, timezone
from .base import BaseEntity


class RDSDatabaseEntity(BaseEntity):
    """
    Queries AWS RDS database operational status and configuration.

    Provides information about:
    - Database availability and status
    - Instance type and configuration
    - Storage capacity and usage
    - Multi-AZ and replication status
    - Connection endpoints
    - Database version and engine

    SECURITY RESTRICTIONS:
    - READ-ONLY access via boto3 RDS client
    - No write operations allowed
    - Requires AWS credentials (SSO or IAM)

    DATABASE COVERAGE:
    - BARB: barb-prod-pg-0, barb-stage-pg-0, barb-qa-pg-0
    - Buckaneer: buckaneer-prod-pg-0, buckaneer-stage-pg-0
    - Kraken, SOS, and other services
    - Read replicas: barb-prod-pg-replica-0
    """

    name = "rds_database"
    description = "AWS RDS database operational status and configuration. Use for questions about database availability, instance status, storage, connections, Multi-AZ, read replicas, database version, whether databases are running/available."

    # Known RDS databases by service
    KNOWN_DATABASES = {
        'barb': {
            'prod': ['barb-prod-pg-0', 'barb-prod-pg-replica-0'],
            'stage': ['barb-stage-pg-0'],
            'qa': ['barb-qa-pg-0'],
            'dev': ['barb-dev-pg-0'],
        },
        'buckaneer': {
            'prod': ['buckaneer-prod-pg-0'],
            'stage': ['buckaneer-stage-pg-0'],
            'qa': ['buckaneer-qa-pg-0'],
            'dev': ['buckaneer-dev-pg-0'],
        },
        'kraken': {
            'prod': ['kraken-prod-pg-0'],
        },
        'sos': {
            'prod': ['sos-prod-pg-0'],
        },
    }

    def _get_rds_client(self):
        """
        Get RDS client.

        Returns:
            boto3 RDS client or None if unavailable
        """
        try:
            import boto3
            return boto3.client('rds', region_name='us-west-2')
        except ImportError:
            # boto3 not installed
            return None
        except Exception:
            # AWS credentials not configured
            return None

    def _get_cloudwatch_client(self):
        """
        Get CloudWatch client for database metrics.

        Returns:
            boto3 CloudWatch client or None if unavailable
        """
        try:
            import boto3
            return boto3.client('cloudwatch', region_name='us-west-2')
        except ImportError:
            return None
        except Exception:
            return None

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get RDS database status from AWS (READ-ONLY).

        Returns a list of dicts (not a Django queryset) since RDS is an external service.

        SECURITY: All operations are read-only. No modifications to databases.
        """
        client = self._get_rds_client()
        if client is None:
            # RDS client not available (no boto3 or credentials)
            return []

        if not filters:
            # Default: return all production databases
            filters = {'environment': 'prod'}

        # Determine which database(s) to query
        db_identifiers = self._get_db_identifiers(filters)

        if not db_identifiers:
            # No databases to query
            return []

        # Query each database
        results = []
        for db_id in db_identifiers:
            try:
                db_info = self._get_db_info(client, db_id)
                if db_info:
                    # Optionally add CloudWatch metrics
                    if 'include_metrics' not in filters or filters['include_metrics']:
                        metrics = self._get_db_metrics(db_id)
                        if metrics:
                            db_info.update(metrics)

                    # Apply status filter if specified
                    if 'status' in filters:
                        if filters['status'].lower() != db_info['status'].lower():
                            continue

                    # Apply replica filter if specified
                    if 'replica' in filters:
                        if filters['replica'] and not db_info['is_replica']:
                            continue
                        elif not filters['replica'] and db_info['is_replica']:
                            continue

                    results.append(db_info)
            except Exception:
                # Query failed for this database, skip it
                continue

        return results

    def _get_db_identifiers(self, filters: Dict[str, Any]) -> List[str]:
        """
        Determine which database identifiers to query based on filters.

        Args:
            filters: Query filters

        Returns:
            List of RDS database identifiers
        """
        db_identifiers = []
        environment = filters.get('environment', 'prod').lower()

        # Specific database filter
        if 'database' in filters:
            db_name = filters['database'].lower()

            # Check if it's a known service
            if db_name in self.KNOWN_DATABASES:
                service_dbs = self.KNOWN_DATABASES[db_name]
                if environment in service_dbs:
                    db_identifiers.extend(service_dbs[environment])
                elif environment == 'all':
                    for env_dbs in service_dbs.values():
                        db_identifiers.extend(env_dbs)
            else:
                # Direct database identifier
                db_identifiers.append(db_name)

        # Service filter
        elif 'service' in filters:
            service = filters['service'].lower()
            if service in self.KNOWN_DATABASES:
                service_dbs = self.KNOWN_DATABASES[service]
                if environment in service_dbs:
                    db_identifiers.extend(service_dbs[environment])
                elif environment == 'all':
                    for env_dbs in service_dbs.values():
                        db_identifiers.extend(env_dbs)

        # Environment filter only (all services in that environment)
        else:
            for service_dbs in self.KNOWN_DATABASES.values():
                if environment in service_dbs:
                    db_identifiers.extend(service_dbs[environment])
                elif environment == 'all':
                    for env_dbs in service_dbs.values():
                        db_identifiers.extend(env_dbs)

        return db_identifiers

    def _get_db_info(self, client, db_identifier: str) -> Dict[str, Any]:
        """
        Get comprehensive database information.

        Args:
            client: boto3 RDS client
            db_identifier: RDS database identifier

        Returns:
            Dict with database status and configuration
        """
        try:
            response = client.describe_db_instances(
                DBInstanceIdentifier=db_identifier
            )
            db = response['DBInstances'][0]
        except client.exceptions.DBInstanceNotFoundFault:
            return None

        # Extract service and environment from identifier
        # Pattern: {service}-{environment}-pg-{number}
        parts = db_identifier.split('-')
        service = parts[0] if parts else 'unknown'
        environment = parts[1] if len(parts) > 1 else 'unknown'
        is_replica = 'replica' in db_identifier.lower()

        # Get endpoint information
        endpoint = db.get('Endpoint', {})
        read_replica_source = db.get('ReadReplicaSourceDBInstanceIdentifier')

        return {
            'database_id': db_identifier,
            'service': service,
            'environment': environment,
            'is_replica': is_replica or bool(read_replica_source),
            'replica_source': read_replica_source,
            'read_replica_count': len(db.get('ReadReplicaDBInstanceIdentifiers', [])),

            # Status and availability
            'status': db['DBInstanceStatus'],
            'available': db['DBInstanceStatus'] == 'available',
            'multi_az': db['MultiAZ'],

            # Engine and version
            'engine': db['Engine'],
            'engine_version': db['EngineVersion'],

            # Instance configuration
            'instance_class': db['DBInstanceClass'],
            'storage_type': db.get('StorageType', 'Unknown'),
            'storage_gb': db['AllocatedStorage'],
            'storage_encrypted': db.get('StorageEncrypted', False),
            'iops': db.get('Iops'),

            # Connectivity
            'endpoint': endpoint.get('Address'),
            'port': endpoint.get('Port'),
            'publicly_accessible': db.get('PubliclyAccessible', False),

            # Backup configuration
            'backup_retention_days': db.get('BackupRetentionPeriod', 0),
            'backup_window': db.get('PreferredBackupWindow'),
            'maintenance_window': db.get('PreferredMaintenanceWindow'),

            # Timestamps
            'created_at': db['InstanceCreateTime'].isoformat() if db.get('InstanceCreateTime') else None,
            'latest_restorable_time': db.get('LatestRestorableTime').isoformat() if db.get('LatestRestorableTime') else None,
        }

    def _get_db_metrics(self, db_identifier: str) -> Dict[str, Any]:
        """
        Get CloudWatch metrics for database.

        Args:
            db_identifier: RDS database identifier

        Returns:
            Dict with metrics or empty dict if unavailable
        """
        cloudwatch = self._get_cloudwatch_client()
        if cloudwatch is None:
            return {}

        from datetime import timedelta
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=5)

        try:
            # Get database connections
            connections_response = cloudwatch.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName='DatabaseConnections',
                Dimensions=[
                    {'Name': 'DBInstanceIdentifier', 'Value': db_identifier}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,  # 5 minutes
                Statistics=['Average']
            )

            connections = None
            if connections_response['Datapoints']:
                connections = int(connections_response['Datapoints'][0]['Average'])

            # Get CPU utilization
            cpu_response = cloudwatch.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName='CPUUtilization',
                Dimensions=[
                    {'Name': 'DBInstanceIdentifier', 'Value': db_identifier}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average']
            )

            cpu_percent = None
            if cpu_response['Datapoints']:
                cpu_percent = round(cpu_response['Datapoints'][0]['Average'], 1)

            # Get free storage space
            storage_response = cloudwatch.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName='FreeStorageSpace',
                Dimensions=[
                    {'Name': 'DBInstanceIdentifier', 'Value': db_identifier}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average']
            )

            free_storage_gb = None
            if storage_response['Datapoints']:
                free_storage_bytes = storage_response['Datapoints'][0]['Average']
                free_storage_gb = round(free_storage_bytes / (1024**3), 1)

            return {
                'connections_current': connections,
                'cpu_percent': cpu_percent,
                'free_storage_gb': free_storage_gb,
            }

        except Exception:
            return {}

    def get_attributes(self) -> List[str]:
        """Available attributes for RDS databases"""
        return [
            'database_id',
            'service',
            'environment',
            'is_replica',
            'replica_source',
            'read_replica_count',
            'status',
            'available',
            'multi_az',
            'engine',
            'engine_version',
            'instance_class',
            'storage_type',
            'storage_gb',
            'storage_encrypted',
            'iops',
            'endpoint',
            'port',
            'publicly_accessible',
            'backup_retention_days',
            'backup_window',
            'maintenance_window',
            'created_at',
            'latest_restorable_time',
            'connections_current',
            'cpu_percent',
            'free_storage_gb',
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """
        Validate that filters are safe and recognized.
        """
        valid_filters = {
            'database',
            'service',
            'environment',
            'status',
            'replica',
            'include_metrics'
        }

        # Check all filter keys are valid
        if not all(key in valid_filters for key in filters.keys()):
            return False

        return True
