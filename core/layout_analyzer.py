"""
LayoutAnalyzer - Analyzes query results and generates layout specifications.

Determines which components to display based on result count, data types, and entity metadata.
"""
from typing import Dict, Any, List


class LayoutAnalyzer:
    """Analyzes query results and returns layout specification array."""

    @staticmethod
    def analyze(results: Dict[str, Any], intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze query results and return layout specification.

        Args:
            results: Query results dict with 'count', 'results', 'entity' keys
            intent: Intent dict with 'entity' and other metadata

        Returns:
            List of component specifications
        """
        layout = []
        count = results.get('count', 0)

        # Empty results
        if count == 0:
            entity_name = intent.get('entity', 'items')
            layout.append({
                'type': 'empty',
                'message': f'No {entity_name} found matching your criteria'
            })
            return layout

        # Small dataset (< 5): summary only
        if count < 5:
            layout.append({
                'type': 'summary',
                'content': f'Found {count} {intent.get("entity", "items")}'
            })
            return layout

        # Medium/large dataset (5+): summary + table
        if count >= 5:
            # Adjust summary for large datasets
            limit = intent.get('limit', 100)
            if count > 50:
                summary_text = f'Found {count} {intent.get("entity", "items")} (showing first {min(limit, count)})'
            else:
                summary_text = f'Found {count} {intent.get("entity", "items")}'

            layout.append({
                'type': 'summary',
                'content': summary_text
            })

            # Generate table columns from first result
            data = results.get('results', [])
            columns = []
            if data:
                for field in data[0].keys():
                    columns.append({
                        'field': field,
                        'header': field.replace('_', ' ').title(),
                        'sortable': True
                    })

            layout.append({
                'type': 'table',
                'data': data,
                'columns': columns
            })
            return layout

        return layout
