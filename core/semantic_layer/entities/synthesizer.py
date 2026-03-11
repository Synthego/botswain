from typing import Dict, Any, List
from .base import BaseEntity
from data_sources.barb.models import Instrument

class SynthesizerEntity(BaseEntity):
    """Entity for querying RNA/DNA synthesis instruments"""

    name = "synthesizer"
    description = "RNA/DNA synthesis instruments ONLY. Use 'instrument' entity for other equipment types (printers, liquid handlers, thermal cyclers, etc.)"

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get queryset for synthesizers.

        Filters synthesizers from Instrument model where instrument_type = 'synthesizer'.
        """
        qs = Instrument.objects.filter(
            instrument_type__name='synthesizer'
        ).select_related('instrument_type')

        if filters:
            # Apply status filter
            if 'status' in filters:
                qs = qs.filter(status=filters['status'])

            # Apply available filter (alias for online status)
            if filters.get('available'):
                qs = qs.filter(status='online')

            # Apply barcode filter
            if 'barcode' in filters:
                qs = qs.filter(barcode_ptr_id=filters['barcode'])

        return qs

    def get_attributes(self) -> List[str]:
        """Return list of queryable attributes"""
        return [
            'name',
            'barcode',
            'status',
            'instrument_type',
            'host',
            'port',
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """Validate that filters contain only allowed fields"""
        allowed_filters = {
            'status',
            'available',
            'barcode',
        }

        return set(filters.keys()).issubset(allowed_filters)
