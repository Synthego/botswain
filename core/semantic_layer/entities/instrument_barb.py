"""
Generic Instrument entity using real BARB database.
Works with all instrument types in BARB.
"""
from typing import Dict, Any, List
from .base import BaseEntity


class InstrumentEntity(BaseEntity):
    """
    Queries all instruments from BARB's inventory.

    More flexible than SynthesizerEntity - works with any instrument type.
    """

    name = "instrument"
    description = "Factory instruments and equipment (printers, sequencers, liquid handlers, etc.)"

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get instruments from BARB database.

        Uses raw SQL to query BARB's inventory_instrument table.
        """
        from django.db import connections

        # Base query for all instruments
        # Note: Instrument inherits from Barcode, so we need to join on barcode_ptr_id
        query = """
            SELECT
                b.barcode,
                i.name,
                i.status,
                i.host,
                i.port,
                it.name as instrument_type,
                it.description as type_description,
                f.name as factory,
                lb.barcode as installation_location
            FROM inventory_instrument i
            JOIN inventory_barcode b ON i.barcode_ptr_id = b.id
            JOIN inventory_instrument_type it ON i.instrument_type_id = it.id
            LEFT JOIN factories_factory f ON i.factory_id = f.id
            LEFT JOIN inventory_location l ON i.installation_location_id = l.barcode_ptr_id
            LEFT JOIN inventory_barcode lb ON l.barcode_ptr_id = lb.id
            WHERE 1=1
        """

        params = []

        # Apply filters
        if filters:
            if 'status' in filters:
                query += " AND i.status = %s"
                params.append(filters['status'])

            if 'factory' in filters:
                query += " AND f.name = %s"
                params.append(filters['factory'])

            if 'barcode' in filters:
                query += " AND b.barcode = %s"
                params.append(filters['barcode'])

            if 'instrument_type' in filters:
                query += " AND it.name = %s"
                params.append(filters['instrument_type'])

            if 'type' in filters:
                # Alias for instrument_type
                query += " AND it.name = %s"
                params.append(filters['type'])

        query += " ORDER BY b.barcode"

        with connections['barb'].cursor() as cursor:
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            results = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        return results

    def get_attributes(self) -> List[str]:
        """Available attributes for instruments"""
        return [
            'barcode',
            'name',
            'status',
            'host',
            'port',
            'instrument_type',
            'type_description',
            'factory',
            'installation_location'
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """Validate that filters are safe and recognized"""
        valid_filters = {'status', 'factory', 'barcode', 'instrument_type', 'type'}
        return all(key in valid_filters for key in filters.keys())
