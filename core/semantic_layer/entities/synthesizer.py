from typing import Dict, Any, List
from .base import BaseEntity
from data_sources.barb.models import Instrument

class SynthesizerEntity(BaseEntity):
    """Entity for querying RNA/DNA synthesis instruments"""

    name = "synthesizer"
    description = "RNA/DNA synthesis instruments (128-well capacity)"

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get queryset for synthesizers.

        Filters synthesizers from Instrument model where instrument_type = 'Synthesizer'.
        """
        qs = Instrument.objects.filter(
            instrument_type__name='Synthesizer'
        ).select_related('factory', 'installation_location', 'instrument_type')

        if filters:
            # Apply status filter
            if 'status' in filters:
                qs = qs.filter(status=filters['status'])

            # Apply factory filter
            if 'factory' in filters:
                qs = qs.filter(factory__name=filters['factory'])

            # Apply available filter (alias for ONLINE status)
            if filters.get('available'):
                qs = qs.filter(status='ONLINE')

        return qs

    def get_attributes(self) -> List[str]:
        """Return list of queryable attributes"""
        return [
            'name',
            'barcode',
            'status',
            'factory',
            'location',
            'instrument_type',
            'host',
            'port',
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """Validate that filters contain only allowed fields"""
        allowed_filters = {
            'status',
            'factory',
            'available',
            'barcode',
        }

        return set(filters.keys()).issubset(allowed_filters)
