"""
SOS Sequencing entity for querying sequencing orders and analysis results.

Queries SOS PostgreSQL database for READ-ONLY access to sequencing data.

SECURITY: Read-only access to SOS database. Uses existing database connection.
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging
from .base import BaseEntity
from core.sql_validator import SQLValidator

logger = logging.getLogger(__name__)


class SOSSequencingEntity(BaseEntity):
    """
    Queries SOS sequencing orders and analysis results.

    Provides information about:
    - Sequencing orders and their status
    - Analysis runs and completion status
    - ICE/Lodestone analysis results and editing scores
    - Quality metrics (Phred scores, R-squared)
    - Failed sequencing orders and analysis failures
    - Orders by work order reference (BARB integration)

    SECURITY RESTRICTIONS:
    - READ-ONLY access via SOS database
    - No write operations allowed
    - Uses existing SOS database connection

    DATA SOURCE:
    - SOS PostgreSQL database (order_order, order_aliquot, analysis_analysisrun, analysis_analysis tables)
    - Connected to BARB work orders via source_order_reference
    - Connected to Kraken workflows via workflow_id/task_id
    """

    name = "sos_sequencing"
    description = (
        "SOS sequencing orders and analysis results. Use for questions about "
        "sequencing orders, sequencing status, analysis results, ICE scores, editing efficiency, "
        "quality metrics, Phred scores, work order sequencing, failed sequencing, analysis failures."
    )

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get SOS sequencing data from database (READ-ONLY).

        Uses raw SQL since SOS models are not installed in Botswain.

        SECURITY: All operations are read-only.
        """
        from django.db import connections
        from datetime import datetime, timedelta

        if not filters:
            filters = {}

        query_type = filters.get('query_type', 'orders')  # orders, analysis, failed_orders, failed_analysis, quality, work_order

        try:
            if query_type == 'orders':
                return self._get_sequencing_orders(connections['sos'], filters)
            elif query_type == 'analysis':
                return self._get_analysis_results(connections['sos'], filters)
            elif query_type == 'failed_orders':
                return self._get_failed_orders(connections['sos'], filters)
            elif query_type == 'failed_analysis':
                return self._get_failed_analysis(connections['sos'], filters)
            elif query_type == 'quality':
                return self._get_quality_metrics(connections['sos'], filters)
            elif query_type == 'work_order':
                return self._get_orders_by_work_order(connections['sos'], filters)
            else:
                return self._get_sequencing_orders(connections['sos'], filters)

        except Exception as e:
            logger.error(f"SOS sequencing query failed: {e}", exc_info=True)
            raise

    def _get_sequencing_orders(self, connection, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get sequencing orders with optional filters"""
        where_clauses = []
        params = []

        # Time filter
        hours_ago = filters.get('hours_ago', 168)  # Default 7 days
        cutoff_time = datetime.now() - timedelta(hours=hours_ago)
        where_clauses.append("o.created >= %s")
        params.append(cutoff_time)

        # Status filter
        if 'status' in filters:
            where_clauses.append("o.status = %s")
            params.append(filters['status'])

        # Sequencer filter
        if 'sequencer' in filters:
            where_clauses.append("o.sequencer ILIKE %s")
            params.append(f"%{filters['sequencer']}%")

        # Barcode filter
        if 'barcode' in filters:
            where_clauses.append("o.synthego_barcode ILIKE %s")
            params.append(f"%{filters['barcode']}%")

        # Workflow filter
        if 'workflow_id' in filters:
            where_clauses.append("o.workflow_id = %s")
            params.append(filters['workflow_id'])

        # Callback status filter
        if 'callback_status' in filters:
            where_clauses.append("o.callback_status = %s")
            params.append(filters['callback_status'])

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT
                o.id as order_id,
                o.synthego_barcode,
                o.sequencer_order_id,
                o.sequencer,
                o.status,
                o.email_status,
                o.callback_status,
                o.workflow_id,
                o.task_id,
                o.placing_system,
                o.placing_team,
                o.created,
                (SELECT COUNT(*) FROM order_aliquot WHERE order_id = o.id) as aliquot_count,
                (SELECT string_agg(DISTINCT source_order_reference, ', ')
                 FROM order_aliquot WHERE order_id = o.id) as source_order_references,
                (SELECT COUNT(*) > 0 FROM analysis_analysisrun WHERE order_id = o.id) as has_analysis,
                (SELECT id FROM analysis_analysisrun WHERE order_id = o.id ORDER BY run_date DESC LIMIT 1) as latest_analysis_run_id,
                (SELECT run_date FROM analysis_analysisrun WHERE order_id = o.id ORDER BY run_date DESC LIMIT 1) as latest_analysis_date
            FROM order_order o
            WHERE {where_sql}
            ORDER BY o.created DESC
            LIMIT %s
        """
        params.append(filters.get('limit', 100))

        with connection.cursor() as cursor:
            SQLValidator.validate(sql)
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            results = []
            for row in rows:
                result_dict = dict(zip(columns, row))
                results.append({
                    'order_id': result_dict['order_id'],
                    'synthego_barcode': result_dict['synthego_barcode'],
                    'sequencer_order_id': result_dict['sequencer_order_id'],
                    'sequencer': result_dict['sequencer'],
                    'status': result_dict['status'],
                    'email_status': result_dict['email_status'],
                    'callback_status': result_dict['callback_status'],
                    'workflow_id': result_dict['workflow_id'],
                    'task_id': result_dict['task_id'],
                    'placing_system': result_dict['placing_system'],
                    'placing_team': result_dict['placing_team'],
                    'created': result_dict['created'].isoformat() if result_dict['created'] else None,
                    'aliquot_count': result_dict['aliquot_count'],
                    'source_order_references': result_dict['source_order_references'],
                    'has_analysis': result_dict['has_analysis'],
                    'latest_analysis_run_id': result_dict['latest_analysis_run_id'],
                    'latest_analysis_date': result_dict['latest_analysis_date'].isoformat() if result_dict['latest_analysis_date'] else None
                })

            return results

    def _get_analysis_results(self, connection, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get analysis results with ICE/Lodestone scores"""
        where_clauses = []
        params = []

        # Time filter
        hours_ago = filters.get('hours_ago', 168)  # Default 7 days
        cutoff_time = datetime.now() - timedelta(hours=hours_ago)
        where_clauses.append("a.created >= %s")
        params.append(cutoff_time)

        # Status filter
        if 'status' in filters:
            where_clauses.append("a.status = %s")
            params.append(filters['status'])

        # Source order reference filter
        if 'source_order_reference' in filters:
            where_clauses.append("aliq.source_order_reference ILIKE %s")
            params.append(f"%{filters['source_order_reference']}%")

        # Barcode filter
        if 'barcode' in filters:
            where_clauses.append("o.synthego_barcode ILIKE %s")
            params.append(f"%{filters['barcode']}%")

        # Minimum ICE score filter
        if 'min_ice_score' in filters:
            where_clauses.append("a.ice_score >= %s")
            params.append(filters['min_ice_score'])

        # Maximum ICE score filter
        if 'max_ice_score' in filters:
            where_clauses.append("a.ice_score <= %s")
            params.append(filters['max_ice_score'])

        # Quality filter (phred percent)
        if 'min_phred_percent' in filters:
            where_clauses.append("a.phred_percent >= %s")
            params.append(filters['min_phred_percent'])

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT
                a.id as analysis_id,
                o.id as order_id,
                o.synthego_barcode,
                ar.id as run_id,
                ar.run_date,
                aliq.sample_name,
                aliq.position_label,
                aliq.source_order_reference,
                aliq.primer_type,
                aseq.guide_sequence,
                aseq.donor_sequence,
                aseq.identifier,
                a.status,
                a.ice_result_id,
                a.ice_status,
                a.ice_score,
                a.ice_ko_score,
                a.ice_ki_score,
                a.rsq,
                a.phred_total,
                a.phred_passed,
                a.phred_percent,
                a.quality_score,
                a.lodestone_status,
                a.created
            FROM analysis_analysis a
            JOIN analysis_analysisrun ar ON a.run_id = ar.id
            JOIN order_order o ON ar.order_id = o.id
            JOIN analysis_aliquotsequence aseq ON a.aliquot_sequence_id = aseq.id
            JOIN order_aliquot aliq ON aseq.aliquot_id = aliq.id
            WHERE {where_sql}
            ORDER BY a.created DESC
            LIMIT %s
        """
        params.append(filters.get('limit', 100))

        with connection.cursor() as cursor:
            SQLValidator.validate(sql)
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            results = []
            for row in rows:
                result_dict = dict(zip(columns, row))

                # Generate ICE link if we have a result ID
                ice_link = None
                if result_dict['ice_result_id']:
                    ice_link = f"https://ice.synthego.com/#/analyze/results/{result_dict['ice_result_id']}"

                results.append({
                    'analysis_id': result_dict['analysis_id'],
                    'order_id': result_dict['order_id'],
                    'synthego_barcode': result_dict['synthego_barcode'],
                    'run_id': result_dict['run_id'],
                    'run_date': result_dict['run_date'].isoformat() if result_dict['run_date'] else None,
                    'sample_name': result_dict['sample_name'],
                    'position_label': result_dict['position_label'],
                    'source_order_reference': result_dict['source_order_reference'],
                    'primer_type': result_dict['primer_type'],
                    'guide_sequence': result_dict['guide_sequence'],
                    'donor_sequence': result_dict['donor_sequence'],
                    'identifier': result_dict['identifier'],
                    'status': result_dict['status'],
                    'ice_result_id': result_dict['ice_result_id'],
                    'ice_status': result_dict['ice_status'],
                    'ice_score': result_dict['ice_score'],
                    'ice_ko_score': result_dict['ice_ko_score'],
                    'ice_ki_score': result_dict['ice_ki_score'],
                    'rsq': result_dict['rsq'],
                    'phred_total': result_dict['phred_total'],
                    'phred_passed': result_dict['phred_passed'],
                    'phred_percent': result_dict['phred_percent'],
                    'quality_score': result_dict['quality_score'],
                    'lodestone_status': result_dict['lodestone_status'],
                    'ice_link': ice_link,
                    'created': result_dict['created'].isoformat() if result_dict['created'] else None
                })

            return results

    def _get_failed_orders(self, connection, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get failed sequencing orders"""
        hours_ago = filters.get('hours_ago', 168)  # Default 7 days
        cutoff_time = datetime.now() - timedelta(hours=hours_ago)

        sql = """
            SELECT
                o.id as order_id,
                o.synthego_barcode,
                o.sequencer_order_id,
                o.sequencer,
                o.status,
                o.callback_status,
                o.workflow_id,
                o.task_id,
                o.placing_system,
                o.created,
                (SELECT COUNT(*) FROM order_aliquot WHERE order_id = o.id) as aliquot_count,
                (SELECT string_agg(DISTINCT source_order_reference, ', ')
                 FROM order_aliquot WHERE order_id = o.id) as source_order_references
            FROM order_order o
            WHERE (o.status = 'FAILED' OR o.callback_status = 'FAILED')
              AND o.created >= %s
            ORDER BY o.created DESC
            LIMIT %s
        """

        with connection.cursor() as cursor:
            SQLValidator.validate(sql)
            cursor.execute(sql, [cutoff_time, filters.get('limit', 50)])
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            results = []
            for row in rows:
                result_dict = dict(zip(columns, row))

                failure_type = 'order_submission' if result_dict['status'] == 'FAILED' else 'workflow_callback'

                results.append({
                    'order_id': result_dict['order_id'],
                    'synthego_barcode': result_dict['synthego_barcode'],
                    'sequencer_order_id': result_dict['sequencer_order_id'],
                    'sequencer': result_dict['sequencer'],
                    'status': result_dict['status'],
                    'callback_status': result_dict['callback_status'],
                    'workflow_id': result_dict['workflow_id'],
                    'task_id': result_dict['task_id'],
                    'placing_system': result_dict['placing_system'],
                    'created': result_dict['created'].isoformat() if result_dict['created'] else None,
                    'aliquot_count': result_dict['aliquot_count'],
                    'source_order_references': result_dict['source_order_references'],
                    'failure_type': failure_type
                })

            return results

    def _get_failed_analysis(self, connection, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get failed analysis results"""
        hours_ago = filters.get('hours_ago', 168)  # Default 7 days
        cutoff_time = datetime.now() - timedelta(hours=hours_ago)

        sql = """
            SELECT
                a.id as analysis_id,
                o.id as order_id,
                o.synthego_barcode,
                ar.id as run_id,
                aliq.sample_name,
                aliq.position_label,
                aliq.source_order_reference,
                a.status,
                a.ice_status,
                a.ice_error,
                a.lodestone_status,
                a.lodestone_results,
                a.created
            FROM analysis_analysis a
            JOIN analysis_analysisrun ar ON a.run_id = ar.id
            JOIN order_order o ON ar.order_id = o.id
            JOIN analysis_aliquotsequence aseq ON a.aliquot_sequence_id = aseq.id
            JOIN order_aliquot aliq ON aseq.aliquot_id = aliq.id
            WHERE (a.status = 'FAILED' OR a.ice_status = 'failed' OR a.lodestone_status = 'FAILED')
              AND a.created >= %s
            ORDER BY a.created DESC
            LIMIT %s
        """

        with connection.cursor() as cursor:
            SQLValidator.validate(sql)
            cursor.execute(sql, [cutoff_time, filters.get('limit', 50)])
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            results = []
            for row in rows:
                result_dict = dict(zip(columns, row))

                # Determine failure type
                if result_dict['status'] == 'FAILED':
                    failure_type = 'submission_failed'
                elif result_dict['ice_status'] == 'failed':
                    failure_type = 'ice_analysis_failed'
                elif result_dict['lodestone_status'] == 'FAILED':
                    failure_type = 'lodestone_analysis_failed'
                else:
                    failure_type = 'unknown'

                # Extract lodestone error if available
                lodestone_error = None
                if result_dict['lodestone_results']:
                    import json
                    try:
                        lodestone_data = json.loads(result_dict['lodestone_results']) if isinstance(result_dict['lodestone_results'], str) else result_dict['lodestone_results']
                        lodestone_error = lodestone_data.get('exception')
                    except:
                        pass

                results.append({
                    'analysis_id': result_dict['analysis_id'],
                    'order_id': result_dict['order_id'],
                    'synthego_barcode': result_dict['synthego_barcode'],
                    'run_id': result_dict['run_id'],
                    'sample_name': result_dict['sample_name'],
                    'position_label': result_dict['position_label'],
                    'source_order_reference': result_dict['source_order_reference'],
                    'status': result_dict['status'],
                    'ice_status': result_dict['ice_status'],
                    'ice_error': result_dict['ice_error'],
                    'lodestone_status': result_dict['lodestone_status'],
                    'lodestone_error': lodestone_error,
                    'created': result_dict['created'].isoformat() if result_dict['created'] else None,
                    'failure_type': failure_type
                })

            return results

    def _get_quality_metrics(self, connection, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get aggregated quality metrics"""
        hours_ago = filters.get('hours_ago', 168)  # Default 7 days
        cutoff_time = datetime.now() - timedelta(hours=hours_ago)

        sql = """
            SELECT
                COUNT(*) as total_analyses,
                AVG(ice_score) as avg_ice_score,
                AVG(ice_ko_score) as avg_ko_score,
                AVG(ice_ki_score) as avg_ki_score,
                AVG(phred_percent) as avg_phred_percent,
                AVG(rsq) as avg_rsq,
                SUM(CASE WHEN ice_status = 'succeeded' THEN 1 ELSE 0 END) as ice_success_count,
                SUM(CASE WHEN ice_status = 'failed' THEN 1 ELSE 0 END) as ice_failed_count,
                SUM(CASE WHEN ice_score >= 80 THEN 1 ELSE 0 END) as high_quality_count,
                SUM(CASE WHEN ice_score >= 50 AND ice_score < 80 THEN 1 ELSE 0 END) as medium_quality_count,
                SUM(CASE WHEN ice_score < 50 THEN 1 ELSE 0 END) as low_quality_count
            FROM analysis_analysis
            WHERE created >= %s
              AND status = 'COMPLETE'
              AND ice_score IS NOT NULL
        """

        with connection.cursor() as cursor:
            SQLValidator.validate(sql)
            cursor.execute(sql, [cutoff_time])
            row = cursor.fetchone()
            columns = [col[0] for col in cursor.description]
            stats = dict(zip(columns, row))

            total_analyses = stats['total_analyses'] or 0
            success_rate = (stats['ice_success_count'] / total_analyses * 100) if total_analyses > 0 else 0

            results = [{
                'time_window_hours': hours_ago,
                'total_analyses': total_analyses,
                'avg_ice_score': round(stats['avg_ice_score'], 2) if stats['avg_ice_score'] else None,
                'avg_ko_score': round(stats['avg_ko_score'], 2) if stats['avg_ko_score'] else None,
                'avg_ki_score': round(stats['avg_ki_score'], 2) if stats['avg_ki_score'] else None,
                'avg_phred_percent': round(stats['avg_phred_percent'], 2) if stats['avg_phred_percent'] else None,
                'avg_rsq': round(stats['avg_rsq'], 4) if stats['avg_rsq'] else None,
                'ice_success_count': stats['ice_success_count'],
                'ice_failed_count': stats['ice_failed_count'],
                'success_rate_percent': round(success_rate, 2),
                'high_quality_count': stats['high_quality_count'],
                'medium_quality_count': stats['medium_quality_count'],
                'low_quality_count': stats['low_quality_count']
            }]

            return results

    def _get_orders_by_work_order(self, connection, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get sequencing orders by BARB work order reference"""
        work_order_ref = filters.get('work_order_reference')
        if not work_order_ref:
            return []

        sql = """
            SELECT DISTINCT
                o.id as order_id,
                o.synthego_barcode,
                o.sequencer_order_id,
                o.sequencer,
                o.status,
                o.callback_status,
                o.workflow_id,
                o.created,
                (SELECT string_agg(DISTINCT source_order_reference, ', ')
                 FROM order_aliquot WHERE order_id = o.id) as source_order_references,
                (SELECT COUNT(*) FROM order_aliquot WHERE order_id = o.id) as aliquot_count,
                (SELECT id FROM analysis_analysisrun WHERE order_id = o.id ORDER BY run_date DESC LIMIT 1) as latest_analysis_run_id,
                (SELECT run_date FROM analysis_analysisrun WHERE order_id = o.id ORDER BY run_date DESC LIMIT 1) as latest_analysis_date
            FROM order_order o
            JOIN order_aliquot aliq ON o.id = aliq.order_id
            WHERE aliq.source_order_reference ILIKE %s
            ORDER BY o.created DESC
            LIMIT %s
        """

        with connection.cursor() as cursor:
            SQLValidator.validate(sql)
            cursor.execute(sql, [f"%{work_order_ref}%", filters.get('limit', 20)])
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            results = []
            for row in rows:
                result_dict = dict(zip(columns, row))

                # Get analysis counts for latest run if available
                total_analyses = 0
                complete_analyses = 0
                failed_analyses = 0

                if result_dict['latest_analysis_run_id']:
                    analysis_sql = """
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'COMPLETE' THEN 1 ELSE 0 END) as complete,
                            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed
                        FROM analysis_analysis
                        WHERE run_id = %s
                    """
                    SQLValidator.validate(analysis_sql)
                    cursor.execute(analysis_sql, [result_dict['latest_analysis_run_id']])
                    analysis_row = cursor.fetchone()
                    if analysis_row:
                        total_analyses = analysis_row[0]
                        complete_analyses = analysis_row[1]
                        failed_analyses = analysis_row[2]

                results.append({
                    'order_id': result_dict['order_id'],
                    'synthego_barcode': result_dict['synthego_barcode'],
                    'sequencer_order_id': result_dict['sequencer_order_id'],
                    'sequencer': result_dict['sequencer'],
                    'status': result_dict['status'],
                    'callback_status': result_dict['callback_status'],
                    'workflow_id': result_dict['workflow_id'],
                    'created': result_dict['created'].isoformat() if result_dict['created'] else None,
                    'source_order_references': result_dict['source_order_references'],
                    'aliquot_count': result_dict['aliquot_count'],
                    'latest_analysis_run_id': result_dict['latest_analysis_run_id'],
                    'latest_analysis_date': result_dict['latest_analysis_date'].isoformat() if result_dict['latest_analysis_date'] else None,
                    'total_analyses': total_analyses,
                    'complete_analyses': complete_analyses,
                    'failed_analyses': failed_analyses
                })

            return results

    def get_attributes(self) -> List[str]:
        """Available attributes for SOS sequencing"""
        return [
            # Order fields
            'order_id',
            'synthego_barcode',
            'sequencer_order_id',
            'sequencer',
            'status',
            'email_status',
            'callback_status',
            'workflow_id',
            'task_id',
            'placing_system',
            'placing_team',
            'created',
            'aliquot_count',
            'source_order_references',
            # Analysis fields
            'analysis_id',
            'run_id',
            'run_date',
            'sample_name',
            'position_label',
            'primer_type',
            'guide_sequence',
            'donor_sequence',
            'identifier',
            'ice_result_id',
            'ice_status',
            'ice_score',
            'ice_ko_score',
            'ice_ki_score',
            'rsq',
            'phred_total',
            'phred_passed',
            'phred_percent',
            'quality_score',
            'lodestone_status',
            'ice_link',
            # Quality metrics
            'avg_ice_score',
            'avg_ko_score',
            'avg_ki_score',
            'avg_phred_percent',
            'avg_rsq',
            'success_rate_percent'
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """Validate that filters are safe and recognized."""
        valid_filters = {
            'query_type',  # orders, analysis, failed_orders, failed_analysis, quality, work_order
            'hours_ago',
            'status',
            'sequencer',
            'barcode',
            'workflow_id',
            'callback_status',
            'source_order_reference',
            'work_order_reference',
            'min_ice_score',
            'max_ice_score',
            'min_phred_percent',
            'limit'
        }

        if not all(key in valid_filters for key in filters.keys()):
            return False

        return True
