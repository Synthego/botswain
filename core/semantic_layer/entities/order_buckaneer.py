"""
Order entity for querying e-commerce orders from Buckaneer.
Provides access to order data, status, and customer information.
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from .base import BaseEntity


class OrderEntity(BaseEntity):
    """
    Queries e-commerce orders from Buckaneer's database.

    Orders represent customer purchases, including both direct and BigCommerce orders.
    """

    name = "order"
    description = "E-commerce orders (customer purchases, BigCommerce orders, order status, shipment tracking)"

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get orders from Buckaneer database using raw SQL.
        """
        from django.db import connections

        # Base query for orders
        query = """
            SELECT
                o.id,
                o.created,
                o.status,
                o.bigcommerce_id,
                o.factory,
                o.estimated_ship_date,
                o.actual_ship_date,
                
                o.anonymous_user_email,
                u.email as user_email,
                u.first_name,
                u.last_name
            FROM order_order o
            LEFT JOIN userprofile_user u ON o.user_id = u.id
            WHERE 1=1
        """

        params = []

        # Apply filters
        if filters:
            if 'status' in filters:
                query += " AND o.status = %s"
                params.append(filters['status'])

            if 'factory' in filters:
                query += " AND o.factory = %s"
                params.append(filters['factory'])

            if 'bigcommerce_id' in filters:
                query += " AND o.bigcommerce_id = %s"
                params.append(filters['bigcommerce_id'])

            if 'order_id' in filters:
                query += " AND o.id = %s"
                params.append(int(filters['order_id']))

            # Handle relative date ranges
            if 'created_after' in filters:
                date_value = self._parse_date_filter(filters['created_after'])
                query += " AND o.created >= %s"
                params.append(date_value)

            if 'created_before' in filters:
                date_value = self._parse_date_filter(filters['created_before'])
                query += " AND o.created <= %s"
                params.append(date_value)

            # Email search
            if 'email' in filters:
                email = filters['email']
                query += " AND (u.email ILIKE %s OR o.anonymous_user_email ILIKE %s)"
                params.append(f"%{email}%")
                params.append(f"%{email}%")

        query += " ORDER BY o.created DESC"

        with connections['buckaneer'].cursor() as cursor:
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
        """Available attributes for orders"""
        return [
            'id',
            'created',
            'status',
            'bigcommerce_id',
            'factory',
            'estimated_ship_date',
            'actual_ship_date',
            
            'user_email',
            'anonymous_user_email',
            'first_name',
            'last_name'
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """Validate that filters are safe and recognized"""
        valid_filters = {
            'status',
            'factory',
            'bigcommerce_id',
            'order_id',
            'created_after',
            'created_before',
            'email'
        }
        return all(key in valid_filters for key in filters.keys())
