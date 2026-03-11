"""
Kraken Workflows entity for querying workflow orchestration data.

Queries Kraken's PostgreSQL database for READ-ONLY access to workflow execution data.

SECURITY: Read-only access to Kraken database. Uses existing database connection.
"""
from typing import Dict, Any, List
import logging
from .base import BaseEntity

logger = logging.getLogger(__name__)


class KrakenWorkflowEntity(BaseEntity):
    """
    Queries Kraken workflow orchestration data.

    Provides information about:
    - Running workflows and tasks
    - Workflow execution status
    - Failed workflows and error details
    - Workflow statistics and success rates
    - Task execution history

    SECURITY RESTRICTIONS:
    - READ-ONLY access via Kraken database
    - No write operations allowed
    - Uses existing Kraken database connection

    DATA SOURCE:
    - Kraken PostgreSQL database (task, task_execution, task_state, workflow, runtime tables)
    - Workflow orchestration execution data
    """

    name = "kraken_workflow"
    description = "Kraken workflow orchestration execution data. Use for questions about running workflows, workflow status, failed workflows, task execution, lab automation status, work order workflows."

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get Kraken workflow data from database (READ-ONLY).

        Uses raw SQL since Kraken models are not installed in Botswain.

        SECURITY: All operations are read-only.
        """
        from django.db import connections
        from datetime import datetime, timedelta

        if not filters:
            filters = {}

        query_type = filters.get('query_type', 'status')  # status, running, failed, statistics

        try:
            if query_type == 'running':
                return self._get_running_workflows(connections['kraken'])
            elif query_type == 'failed':
                hours_ago = filters.get('hours_ago', 24)
                return self._get_failed_workflows(connections['kraken'], hours_ago)
            elif query_type == 'statistics':
                days_ago = filters.get('days_ago', 7)
                workflow_name = filters.get('workflow_name')
                return self._get_workflow_statistics(connections['kraken'], workflow_name, days_ago)
            else:  # status
                return self._get_workflow_status(connections['kraken'], filters)

        except Exception as e:
            logger.error(f"Kraken workflow query failed: {e}", exc_info=True)
            raise

    def _get_running_workflows(self, connection) -> List[Dict[str, Any]]:
        """Get all currently running workflows"""
        sql = """
            SELECT DISTINCT
                w.id as workflow_id,
                w.name as workflow_name,
                r.id as runtime_id,
                r.created_at as started_at,
                COUNT(DISTINCT te.id) as running_task_count
            FROM workflow w
            JOIN task t ON w.id = t.workflow_id
            JOIN task_execution te ON t.id = te.task_id
            JOIN runtime r ON te.runtime_id = r.id
            JOIN task_state ts ON te.id = ts.task_execution_id
            WHERE ts.status = 'RUNNING'
            GROUP BY w.id, w.name, r.id, r.created_at
            ORDER BY r.created_at DESC
            LIMIT 50
        """

        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            results = []
            for row in rows:
                workflow_dict = dict(zip(columns, row))

                # Get running task details for this workflow
                task_sql = """
                    SELECT
                        t.name as task_name,
                        t.id as task_id,
                        te.id as execution_id,
                        te.started_at
                    FROM task t
                    JOIN task_execution te ON t.id = te.task_id
                    JOIN task_state ts ON te.id = ts.task_execution_id
                    WHERE t.workflow_id = %s
                      AND te.runtime_id = %s
                      AND ts.status = 'RUNNING'
                    ORDER BY te.started_at
                """
                cursor.execute(task_sql, [workflow_dict['workflow_id'], workflow_dict['runtime_id']])
                task_columns = [col[0] for col in cursor.description]
                task_rows = cursor.fetchall()

                running_tasks = []
                for task_row in task_rows:
                    task_dict = dict(zip(task_columns, task_row))
                    running_tasks.append({
                        'task_name': task_dict['task_name'],
                        'task_id': task_dict['task_id'],
                        'execution_id': task_dict['execution_id'],
                        'started_at': task_dict['started_at'].isoformat() if task_dict['started_at'] else None
                    })

                results.append({
                    'workflow_id': workflow_dict['workflow_id'],
                    'workflow_name': workflow_dict['workflow_name'],
                    'runtime_id': workflow_dict['runtime_id'],
                    'started_at': workflow_dict['started_at'].isoformat() if workflow_dict['started_at'] else None,
                    'running_task_count': workflow_dict['running_task_count'],
                    'running_tasks': running_tasks,
                    'status': 'RUNNING'
                })

            return results

    def _get_workflow_status(self, connection, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get workflow status with optional filters"""
        where_clauses = []
        params = []

        # Time filter
        hours_ago = filters.get('hours_ago', 24)
        cutoff_time = datetime.now() - timedelta(hours=hours_ago)
        where_clauses.append("r.created_at >= %s")
        params.append(cutoff_time)

        # Workflow name filter
        if 'workflow_name' in filters:
            where_clauses.append("w.name ILIKE %s")
            params.append(f"%{filters['workflow_name']}%")

        # Work order filter
        if 'work_order_id' in filters:
            where_clauses.append("r.metadata::text ILIKE %s")
            params.append(f"%{filters['work_order_id']}%")

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT DISTINCT
                w.id as workflow_id,
                w.name as workflow_name,
                r.id as runtime_id,
                r.created_at as started_at,
                r.metadata,
                COUNT(DISTINCT t.id) as total_tasks
            FROM workflow w
            JOIN task t ON w.id = t.workflow_id
            JOIN task_execution te ON t.id = te.task_id
            JOIN runtime r ON te.runtime_id = r.id
            WHERE {where_sql}
            GROUP BY w.id, w.name, r.id, r.created_at, r.metadata
            ORDER BY r.created_at DESC
            LIMIT 100
        """

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            results = []
            for row in rows:
                workflow_dict = dict(zip(columns, row))

                # Get task status breakdown
                status_sql = """
                    SELECT
                        ts.status,
                        COUNT(*) as count
                    FROM task t
                    JOIN task_execution te ON t.id = te.task_id
                    JOIN task_state ts ON te.id = ts.task_execution_id
                    WHERE t.workflow_id = %s
                      AND te.runtime_id = %s
                    GROUP BY ts.status
                """
                cursor.execute(status_sql, [workflow_dict['workflow_id'], workflow_dict['runtime_id']])
                status_rows = cursor.fetchall()

                status_counts = {row[0]: row[1] for row in status_rows}

                # Determine overall status
                if status_counts.get('RUNNING', 0) > 0:
                    overall_status = 'RUNNING'
                elif status_counts.get('FAILED', 0) > 0:
                    overall_status = 'FAILED'
                elif status_counts.get('PENDING', 0) > 0:
                    overall_status = 'PENDING'
                elif status_counts.get('COMPLETED', 0) == workflow_dict['total_tasks']:
                    overall_status = 'COMPLETED'
                else:
                    overall_status = 'UNKNOWN'

                results.append({
                    'workflow_id': workflow_dict['workflow_id'],
                    'workflow_name': workflow_dict['workflow_name'],
                    'runtime_id': workflow_dict['runtime_id'],
                    'started_at': workflow_dict['started_at'].isoformat() if workflow_dict['started_at'] else None,
                    'status': overall_status,
                    'total_tasks': workflow_dict['total_tasks'],
                    'completed_tasks': status_counts.get('COMPLETED', 0),
                    'running_tasks': status_counts.get('RUNNING', 0),
                    'failed_tasks': status_counts.get('FAILED', 0),
                    'pending_tasks': status_counts.get('PENDING', 0),
                    'metadata': workflow_dict['metadata']
                })

            return results

    def _get_failed_workflows(self, connection, hours_ago: int) -> List[Dict[str, Any]]:
        """Get workflows with failed tasks"""
        cutoff_time = datetime.now() - timedelta(hours=hours_ago)

        sql = """
            SELECT
                w.id as workflow_id,
                w.name as workflow_name,
                r.id as runtime_id,
                t.name as task_name,
                t.id as task_id,
                te.id as execution_id,
                te.started_at,
                te.finished_at,
                r.metadata
            FROM workflow w
            JOIN task t ON w.id = t.workflow_id
            JOIN task_execution te ON t.id = te.task_id
            JOIN runtime r ON te.runtime_id = r.id
            JOIN task_state ts ON te.id = ts.task_execution_id
            WHERE ts.status = 'FAILED'
              AND te.finished_at >= %s
            ORDER BY te.finished_at DESC
            LIMIT 100
        """

        with connection.cursor() as cursor:
            cursor.execute(sql, [cutoff_time])
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            results = []
            for row in rows:
                failure_dict = dict(zip(columns, row))

                duration_seconds = None
                if failure_dict['finished_at'] and failure_dict['started_at']:
                    duration = failure_dict['finished_at'] - failure_dict['started_at']
                    duration_seconds = duration.total_seconds()

                results.append({
                    'workflow_id': failure_dict['workflow_id'],
                    'workflow_name': failure_dict['workflow_name'],
                    'runtime_id': failure_dict['runtime_id'],
                    'task_name': failure_dict['task_name'],
                    'task_id': failure_dict['task_id'],
                    'execution_id': failure_dict['execution_id'],
                    'started_at': failure_dict['started_at'].isoformat() if failure_dict['started_at'] else None,
                    'finished_at': failure_dict['finished_at'].isoformat() if failure_dict['finished_at'] else None,
                    'duration_seconds': duration_seconds,
                    'status': 'FAILED',
                    'metadata': failure_dict['metadata']
                })

            return results

    def _get_workflow_statistics(self, connection, workflow_name: str, days_ago: int) -> List[Dict[str, Any]]:
        """Get aggregated workflow statistics"""
        cutoff_time = datetime.now() - timedelta(days=days_ago)

        where_clause = "r.created_at >= %s"
        params = [cutoff_time]

        if workflow_name:
            where_clause += " AND w.name ILIKE %s"
            params.append(f"%{workflow_name}%")

        sql = f"""
            SELECT
                w.id as workflow_id,
                w.name as workflow_name,
                COUNT(DISTINCT r.id) as total_runs,
                AVG(EXTRACT(EPOCH FROM (te.finished_at - te.started_at))) as avg_duration_seconds
            FROM workflow w
            JOIN task t ON w.id = t.workflow_id
            JOIN task_execution te ON t.id = te.task_id
            JOIN runtime r ON te.runtime_id = r.id
            WHERE {where_clause}
            GROUP BY w.id, w.name
            ORDER BY total_runs DESC
            LIMIT 50
        """

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            results = []
            for row in rows:
                stats_dict = dict(zip(columns, row))

                # Count completed runs
                completed_sql = """
                    SELECT COUNT(DISTINCT r.id)
                    FROM runtime r
                    JOIN task_execution te ON r.id = te.runtime_id
                    JOIN task t ON te.task_id = t.id
                    JOIN task_state ts ON te.id = ts.task_execution_id
                    WHERE t.workflow_id = %s
                      AND r.created_at >= %s
                      AND ts.status = 'COMPLETED'
                """
                cursor.execute(completed_sql, [stats_dict['workflow_id'], cutoff_time])
                completed_runs = cursor.fetchone()[0]

                # Count failed runs
                failed_sql = """
                    SELECT COUNT(DISTINCT r.id)
                    FROM runtime r
                    JOIN task_execution te ON r.id = te.runtime_id
                    JOIN task t ON te.task_id = t.id
                    JOIN task_state ts ON te.id = ts.task_execution_id
                    WHERE t.workflow_id = %s
                      AND r.created_at >= %s
                      AND ts.status = 'FAILED'
                """
                cursor.execute(failed_sql, [stats_dict['workflow_id'], cutoff_time])
                failed_runs = cursor.fetchone()[0]

                total_runs = stats_dict['total_runs']
                success_rate = (completed_runs / total_runs * 100) if total_runs > 0 else 0

                results.append({
                    'workflow_id': stats_dict['workflow_id'],
                    'workflow_name': stats_dict['workflow_name'],
                    'total_runs': total_runs,
                    'completed_runs': completed_runs,
                    'failed_runs': failed_runs,
                    'success_rate_percent': round(success_rate, 2),
                    'avg_duration_minutes': round(stats_dict['avg_duration_seconds'] / 60, 2) if stats_dict['avg_duration_seconds'] else None,
                    'time_window_days': days_ago
                })

            return results

    def get_attributes(self) -> List[str]:
        """Available attributes for Kraken workflows"""
        return [
            'workflow_id',
            'workflow_name',
            'runtime_id',
            'started_at',
            'finished_at',
            'status',
            'total_tasks',
            'completed_tasks',
            'running_tasks',
            'failed_tasks',
            'pending_tasks',
            'task_name',
            'task_id',
            'execution_id',
            'duration_seconds',
            'metadata',
            'success_rate_percent',
            'avg_duration_minutes',
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """Validate that filters are safe and recognized."""
        valid_filters = {
            'query_type',      # running, failed, status, statistics
            'workflow_name',
            'work_order_id',
            'hours_ago',
            'days_ago',
            'limit'
        }

        if not all(key in valid_filters for key in filters.keys()):
            return False

        return True
