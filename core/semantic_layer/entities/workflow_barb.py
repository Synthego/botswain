"""
Workflow entity for querying MCP workflows from BARB.
Provides access to workflow execution data, templates, and status.
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from .base import BaseEntity


class WorkflowEntity(BaseEntity):
    """
    Queries MCP workflows from BARB's manufacturing control platform.

    Workflows represent automated manufacturing processes like RNA synthesis,
    plating, bulking, etc.
    """

    name = "workflow"
    description = "Manufacturing workflows (RNA synthesis, plating, bulking, etc.). Use this for questions about production processes, workflow status, and execution history."

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get workflows from BARB database.

        Uses raw SQL to query mcp_workflow with joins to templates and work orders.
        """
        from django.db import connections

        # Base query for workflows
        query = """
            SELECT
                w.id,
                w.status,
                w.created,
                w.updated,
                w.status_changed,
                wt.name as template_name,
                wt.id as template_id,
                wo.id as work_order_id
            FROM mcp_workflow w
            LEFT JOIN mcp_workflowtemplate wt ON w.workflow_template_id = wt.id
            LEFT JOIN wip_work_order wo ON w.work_order_id = wo.id
            WHERE 1=1
        """

        params = []

        # Apply filters
        if filters:
            if 'status' in filters:
                query += " AND w.status = %s"
                params.append(filters['status'])

            if 'template' in filters or 'template_name' in filters:
                template = filters.get('template') or filters.get('template_name')
                query += " AND wt.name ILIKE %s"
                params.append(f"%{template}%")

            if 'work_order_id' in filters:
                query += " AND wo.id = %s"
                params.append(int(filters['work_order_id']))

            if 'workflow_id' in filters:
                query += " AND w.id = %s"
                params.append(int(filters['workflow_id']))

            # Handle relative date ranges
            if 'created_after' in filters:
                date_value = self._parse_date_filter(filters['created_after'])
                query += " AND w.created >= %s"
                params.append(date_value)

            if 'created_before' in filters:
                date_value = self._parse_date_filter(filters['created_before'])
                query += " AND w.created <= %s"
                params.append(date_value)

        query += " ORDER BY w.created DESC"

        with connections['barb'].cursor() as cursor:
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            results = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        return results

    def _parse_date_filter(self, date_value: str) -> datetime:
        """
        Parse date filter value into datetime.

        Handles:
        - SQL interval expressions: "NOW() - INTERVAL '30 days'"
        - ISO dates: "2026-03-10"
        - Relative phrases: "30 days ago", "yesterday"
        """
        date_str = str(date_value).strip().upper()

        # Handle SQL interval expressions
        if "NOW()" in date_str and "INTERVAL" in date_str:
            # Extract number from interval like "NOW() - INTERVAL '30 days'"
            import re
            match = re.search(r"(\d+)\s*(DAY|HOUR|WEEK|MONTH)", date_str)
            if match:
                amount = int(match.group(1))
                unit = match.group(2)

                if unit == "DAY":
                    return datetime.now() - timedelta(days=amount)
                elif unit == "HOUR":
                    return datetime.now() - timedelta(hours=amount)
                elif unit == "WEEK":
                    return datetime.now() - timedelta(weeks=amount)
                elif unit == "MONTH":
                    return datetime.now() - timedelta(days=amount * 30)

        # Handle ISO dates
        try:
            return datetime.fromisoformat(date_value)
        except (ValueError, TypeError):
            pass

        # Default to now if can't parse
        return datetime.now()

    def get_attributes(self) -> List[str]:
        """Available attributes for workflows"""
        return [
            'id',
            'status',
            'created',
            'updated',
            'status_changed',
            'template_name',
            'template_id',
            'work_order_id'
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """Validate that filters are safe and recognized"""
        valid_filters = {
            'status',
            'template',
            'template_name',
            'work_order_id',
            'workflow_id',
            'created_after',
            'created_before'
        }
        return all(key in valid_filters for key in filters.keys())
