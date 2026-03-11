"""
NetSuite Orders entity for querying NetSuite sales order data cached in Buckaneer.

Queries Buckaneer's netsuite_netsuitesalesorder table for READ-ONLY access.

SECURITY: Read-only access to Buckaneer database. Uses existing database connection.
"""
from typing import Dict, Any, List
import logging
from .base import BaseEntity
from core.sql_validator import SQLValidator

logger = logging.getLogger(__name__)


class NetSuiteOrderEntity(BaseEntity):
    """
    Queries NetSuite sales order data cached in Buckaneer database.

    Provides information about:
    - Sales order sync status (synced, error, pending)
    - NetSuite internal IDs and external IDs
    - Order amounts and status
    - Customer information
    - Invoice and fulfillment status
    - Sync timestamps

    SECURITY RESTRICTIONS:
    - READ-ONLY access via Buckaneer database
    - No write operations allowed
    - Uses existing Buckaneer database connection

    DATA SOURCE:
    - Cached NetSuite data in Buckaneer (netsuite_netsuitesalesorder table)
    - Data synced from NetSuite SOAP API by Buckaneer
    """

    name = "netsuite_order"
    description = "NetSuite sales orders synced from NetSuite to Buckaneer. Use for questions about order sync status, NetSuite invoice status, fulfillment status, order amounts, customer billing, NetSuite IDs, sync errors."

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get NetSuite sales orders from Buckaneer database (READ-ONLY).

        Uses raw SQL since Buckaneer apps are not installed in Botswain.

        SECURITY: All operations are read-only.
        """
        from django.db import connections
        from datetime import datetime, timedelta

        # Build SQL query
        where_clauses = []
        params = []

        if not filters:
            # Default: recent orders (last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            where_clauses.append("date_created >= %s")
            params.append(thirty_days_ago)
        else:
            # Apply filters
            if 'order_id' in filters or 'external_id' in filters:
                order_id = filters.get('order_id') or filters.get('external_id')
                where_clauses.append("external_id = %s")
                params.append(str(order_id))

            if 'internal_id' in filters or 'netsuite_id' in filters:
                internal_id = filters.get('internal_id') or filters.get('netsuite_id')
                where_clauses.append("internal_id = %s")
                params.append(str(internal_id))

            if 'status' in filters:
                status = filters['status'].lower()
                status_map = {
                    'pending': 'Pending Fulfillment',
                    'fulfilled': 'Pending Billing',
                    'billed': 'Partially Billed',
                    'closed': 'Closed',
                    'cancelled': 'Cancelled'
                }
                if status in status_map:
                    where_clauses.append("status = %s")
                    params.append(status_map[status])

            if 'customer' in filters or 'customer_name' in filters:
                customer = filters.get('customer') or filters.get('customer_name')
                where_clauses.append("bill_addressee ILIKE %s")
                params.append(f'%{customer}%')

            if 'since' in filters or 'start_date' in filters:
                since = filters.get('since') or filters.get('start_date')
                date_value = self._parse_date_filter(since)
                where_clauses.append("date_created >= %s")
                params.append(date_value)

            if 'until' in filters or 'end_date' in filters:
                until = filters.get('until') or filters.get('end_date')
                date_value = self._parse_date_filter(until)
                where_clauses.append("date_created <= %s")
                params.append(date_value)

            # Note: has_error filter not applicable - table doesn't have error columns
            # Orders that fail sync wouldn't be in this table at all

        # Build full query
        limit = filters.get('limit', 100) if filters else 100
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT
                internal_id,
                external_id,
                status,
                transaction_date,
                date_created,
                last_modified_date,
                memo,
                total,
                bill_addressee,
                bill_city,
                bill_state,
                bill_country,
                invoice_id,
                item_fulfillment_id,
                customer_id,
                sales_rep_id
            FROM netsuite_netsuitesalesorder
            WHERE {where_sql}
            ORDER BY date_created DESC
            LIMIT %s
        """
        params.append(limit)

        # Execute query
        try:
            with connections['buckaneer'].cursor() as cursor:
                SQLValidator.validate(sql)
                cursor.execute(sql, params)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()

                # Convert to list of dicts
                results = []
                for row in rows:
                    order_dict = dict(zip(columns, row))
                    results.append({
                        'internal_id': order_dict['internal_id'],
                        'external_id': order_dict['external_id'],
                        'status': order_dict['status'],
                        'transaction_date': order_dict['transaction_date'].isoformat() if order_dict['transaction_date'] else None,
                        'date_created': order_dict['date_created'].isoformat() if order_dict['date_created'] else None,
                        'last_modified_date': order_dict['last_modified_date'].isoformat() if order_dict['last_modified_date'] else None,
                        'memo': order_dict['memo'],
                        'total': float(order_dict['total']) if order_dict['total'] else None,
                        'customer_name': order_dict['bill_addressee'],
                        'bill_city': order_dict['bill_city'],
                        'bill_state': order_dict['bill_state'],
                        'bill_country': order_dict['bill_country'],
                        'invoice_id': order_dict['invoice_id'],
                        'item_fulfillment_id': order_dict['item_fulfillment_id'],
                        'customer_id': order_dict['customer_id'],
                        'sales_rep_id': order_dict['sales_rep_id'],
                        'is_fulfilled': order_dict['item_fulfillment_id'] is not None,
                        'is_invoiced': order_dict['invoice_id'] is not None,
                    })

                return results

        except Exception as e:
            # Log the error and re-raise so it's visible
            logger.error(f"NetSuite order query failed: {e}", exc_info=True)
            raise

    def _parse_date_filter(self, date_value: str):
        """Parse date filter value into datetime."""
        from datetime import datetime, timedelta
        import re

        date_str = str(date_value).strip()

        # Handle SQL interval expressions
        date_str_upper = date_str.upper()
        if "NOW()" in date_str_upper and "INTERVAL" in date_str_upper:
            match = re.search(r"(\d+)\s*(DAY|HOUR|WEEK|MONTH)", date_str_upper)
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
        """Available attributes for NetSuite orders"""
        return [
            'internal_id',
            'external_id',
            'status',
            'transaction_date',
            'date_created',
            'last_modified_date',
            'memo',
            'total',
            'customer_name',
            'bill_city',
            'bill_state',
            'bill_country',
            'invoice_id',
            'item_fulfillment_id',
            'customer_id',
            'sales_rep_id',
            'is_fulfilled',
            'is_invoiced',
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """Validate that filters are safe and recognized."""
        valid_filters = {
            'order_id',
            'external_id',
            'internal_id',
            'netsuite_id',
            'status',
            'customer',
            'customer_name',
            'since',
            'start_date',
            'until',
            'end_date',
            'limit'
        }

        if not all(key in valid_filters for key in filters.keys()):
            return False

        return True
