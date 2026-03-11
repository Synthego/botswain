"""
Instrument Logs entity for querying all Synthego-Brain instrument logs from ElasticSearch.
Covers SSA (synthesizers), Hamilton, Tecan, and all other instrument modules.

Uses elasticsearch Python client for READ-ONLY access.

SECURITY: Read-only access to ElasticSearch. Requires VPN for production cluster.
"""
import json
from typing import Dict, Any, List
from datetime import datetime, timedelta
from .base import BaseEntity


class InstrumentLogsEntity(BaseEntity):
    """
    Queries all Synthego-Brain instrument logs from ElasticSearch cluster.

    Supports:
    - SSA (Solid State Synthesizers): SolidStateSynthesizerModule-{id}
    - Hamilton instruments: HamiltonInstrument-{id}
    - Tecan instruments: TecanInstrument-{id}
    - All other Synthego-Brain modules

    SECURITY RESTRICTIONS:
    - READ-ONLY access via elasticsearch client
    - No write operations allowed
    - Requires VPN for production cluster access
    """

    name = "instrument_log"
    description = "Synthego-Brain instrument logs from ElasticSearch. Covers SSA synthesizers, Hamilton, Tecan, and all lab instruments. Use for questions about synthesis runs, instrument errors, method executions, Hamilton/Tecan operations, synthesis duration, work orders, plate tracking."

    # ElasticSearch hosts (production cluster)
    ES_HOSTS = [
        'elasticsearch-01:9200',
        'elasticsearch-02:9200',
        'elasticsearch-03:9200',
        'elasticsearch-04:9200'
    ]

    # Index pattern for instrument logs
    ES_INDEX = "logstash-*"

    # Instrument type patterns
    INSTRUMENT_TYPES = {
        'ssa': 'SolidStateSynthesizerModule',
        'synthesizer': 'SolidStateSynthesizerModule',
        'hamilton': 'HamiltonInstrument',
        'tecan': 'TecanInstrument'
    }

    def _get_es_client(self):
        """
        Get ElasticSearch client with failover support.

        Returns:
            Elasticsearch client instance or None if unavailable
        """
        try:
            from elasticsearch import Elasticsearch

            # Try connecting to hosts in order
            return Elasticsearch(
                self.ES_HOSTS,
                timeout=30,
                max_retries=2,
                retry_on_timeout=True
            )
        except ImportError:
            # elasticsearch package not installed
            return None
        except Exception:
            return None

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get instrument logs from ElasticSearch (READ-ONLY).

        Returns a list of dicts (not a Django queryset) since ElasticSearch is an external service.

        SECURITY: All operations are read-only. No modifications to log data.
        """
        es = self._get_es_client()
        if es is None:
            # ElasticSearch not available (no package or connection failed)
            return []

        # Build ElasticSearch query
        query = self._build_es_query(filters)

        try:
            # Execute search
            response = es.search(
                index=self.ES_INDEX,
                body=query
            )

            # Parse results
            logs = []
            for hit in response['hits']['hits']:
                log_entry = hit['_source']

                # Determine instrument type from module name
                module_name = log_entry.get('modulename', '')
                instrument_type = 'unknown'
                if 'SolidStateSynthesizerModule' in module_name:
                    instrument_type = 'SSA'
                elif 'HamiltonInstrument' in module_name:
                    instrument_type = 'Hamilton'
                elif 'TecanInstrument' in module_name:
                    instrument_type = 'Tecan'

                # Extract key fields
                logs.append({
                    'timestamp': log_entry.get('@timestamp'),
                    'level': log_entry.get('level'),
                    'logger': log_entry.get('logger'),
                    'module_name': module_name,
                    'instrument_type': instrument_type,
                    'message': log_entry.get('msg'),
                    'tags': log_entry.get('tags', []),
                    'file': log_entry.get('file'),
                    'function': log_entry.get('function'),
                    'line': log_entry.get('line'),
                    # Extract extra fields (synthesis_id, workorder_id, linked_plate_barcode, etc.)
                    'synthesis_id': log_entry.get('extra', {}).get('synthesis_id'),
                    'workorder_id': log_entry.get('extra', {}).get('workorder_id'),
                    'linked_barcodes': log_entry.get('extra', {}).get('linked_plate_barcode', []),
                    'extra': log_entry.get('extra', {})
                })

            return logs

        except Exception as e:
            # Query failed
            return []

    def _build_es_query(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Build ElasticSearch query from filters.

        Args:
            filters: Query filters

        Returns:
            ElasticSearch query dict
        """
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"type": "synthego_module"}}
                    ],
                    "filter": []
                }
            },
            "size": 100,  # Default limit
            "sort": [{"@timestamp": {"order": "desc"}}]
        }

        if not filters:
            # Default: last 24 hours
            query["query"]["bool"]["filter"].append({
                "range": {"@timestamp": {"gte": "now-24h"}}
            })
            return query

        # Instrument type filter (ssa, hamilton, tecan)
        if 'instrument_type' in filters:
            inst_type = filters['instrument_type'].lower()
            if inst_type in self.INSTRUMENT_TYPES:
                pattern = self.INSTRUMENT_TYPES[inst_type]
                query["query"]["bool"]["must"].append({
                    "wildcard": {"modulename.raw": f"{pattern}*"}
                })

        # Module name filter (specific instrument)
        if 'module_name' in filters or 'synthesizer' in filters or 'instrument' in filters:
            module = filters.get('module_name') or filters.get('synthesizer') or filters.get('instrument')
            query["query"]["bool"]["must"].append({
                "match": {"modulename": module}
            })

        # Level filter (ERROR, INFO, etc.)
        if 'level' in filters:
            query["query"]["bool"]["must"].append({
                "match": {"level": filters['level'].upper()}
            })

        # Tags filter
        if 'tags' in filters:
            tag_value = filters['tags']
            if isinstance(tag_value, list):
                tags = tag_value
            else:
                tags = [tag_value]

            for tag in tags:
                query["query"]["bool"]["must"].append({
                    "match": {"tags": tag}
                })

        # Synthesis ID filter
        if 'synthesis_id' in filters:
            query["query"]["bool"]["must"].append({
                "match": {"extra.synthesis_id": filters['synthesis_id']}
            })

        # Work order ID filter
        if 'workorder_id' in filters or 'work_order_id' in filters:
            wo_id = filters.get('workorder_id') or filters.get('work_order_id')
            query["query"]["bool"]["must"].append({
                "match": {"extra.workorder_id": wo_id}
            })

        # Plate barcode filter (for Hamilton/Tecan)
        if 'plate_barcode' in filters or 'barcode' in filters:
            barcode = filters.get('plate_barcode') or filters.get('barcode')
            query["query"]["bool"]["must"].append({
                "match": {"extra.linked_plate_barcode": barcode}
            })

        # Message search filter
        if 'search' in filters or 'message' in filters:
            search_term = filters.get('search') or filters.get('message')
            query["query"]["bool"]["must"].append({
                "match": {"msg": search_term}
            })

        # Time range filters
        time_range = {}

        if 'since' in filters or 'start_time' in filters:
            since_value = filters.get('since') or filters.get('start_time')
            date_value = self._parse_date_filter(since_value)
            time_range['gte'] = date_value.isoformat()

        if 'until' in filters or 'end_time' in filters:
            until_value = filters.get('until') or filters.get('end_time')
            date_value = self._parse_date_filter(until_value)
            time_range['lte'] = date_value.isoformat()

        if time_range:
            query["query"]["bool"]["filter"].append({
                "range": {"@timestamp": time_range}
            })
        else:
            # Default: last 24 hours if no time filter specified
            query["query"]["bool"]["filter"].append({
                "range": {"@timestamp": {"gte": "now-24h"}}
            })

        # Limit override
        if 'limit' in filters:
            query["size"] = min(int(filters['limit']), 1000)  # Cap at 1000

        # Sort order
        if 'sort_order' in filters:
            order = filters['sort_order'].lower()
            if order in ['asc', 'desc']:
                query["sort"] = [{"@timestamp": {"order": order}}]

        return query

    def _parse_date_filter(self, date_value: str) -> datetime:
        """
        Parse date filter value into datetime.

        Handles:
        - SQL interval expressions: "NOW() - INTERVAL '30 days'"
        - ElasticSearch relative: "now-7d", "now-1h"
        - ISO dates: "2026-03-10T12:00:00"
        """
        date_str = str(date_value).strip()

        # Handle ElasticSearch relative dates (pass through)
        if date_str.startswith('now'):
            return datetime.now()  # ES will handle the actual relative calc

        # Handle SQL interval expressions
        date_str_upper = date_str.upper()
        if "NOW()" in date_str_upper and "INTERVAL" in date_str_upper:
            import re
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
        """Available attributes for instrument logs"""
        return [
            'timestamp',
            'level',
            'logger',
            'module_name',
            'instrument_type',
            'message',
            'tags',
            'file',
            'function',
            'line',
            'synthesis_id',
            'workorder_id',
            'linked_barcodes',
            'extra'
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """
        Validate that filters are safe and recognized.
        """
        valid_filters = {
            'instrument_type',
            'module_name',
            'synthesizer',
            'instrument',
            'level',
            'tags',
            'synthesis_id',
            'workorder_id',
            'work_order_id',
            'plate_barcode',
            'barcode',
            'search',
            'message',
            'since',
            'start_time',
            'until',
            'end_time',
            'limit',
            'sort_order'
        }

        # Check all filter keys are valid
        if not all(key in valid_filters for key in filters.keys()):
            return False

        return True
