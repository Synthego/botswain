"""
LayoutAnalyzer - Analyzes query results and generates layout specifications.

Determines which components to display based on result count, data types, and entity metadata.
Intelligently selects chart visualizations for aggregations and distributions.
"""
from typing import Dict, Any, List


class LayoutAnalyzer:
    """Analyzes query results and returns layout specification array."""

    @staticmethod
    def _transform_complex_fields(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform complex fields (dicts, lists) into displayable strings.

        Handles:
        - author dict: {'login': 'username'} → 'username'
        - labels list: [{'name': 'bug'}, ...] → 'bug, feature'
        - assignees list: [{'login': 'user1'}, ...] → 'user1, user2'
        - body text: Truncate to 200 chars

        Args:
            data: List of result dicts

        Returns:
            Transformed data with simple types
        """
        if not data:
            return data

        transformed = []
        for row in data:
            new_row = {}
            for key, value in row.items():
                # Transform author dict to string
                if key == 'author' and isinstance(value, dict):
                    new_row[key] = value.get('login', '')
                # Transform labels list to comma-separated string
                elif key == 'labels' and isinstance(value, list):
                    label_names = [label.get('name', '') for label in value if isinstance(label, dict)]
                    new_row[key] = ', '.join(label_names) if label_names else ''
                # Transform assignees list to comma-separated string
                elif key == 'assignees' and isinstance(value, list):
                    assignee_logins = [assignee.get('login', '') for assignee in value if isinstance(assignee, dict)]
                    new_row[key] = ', '.join(assignee_logins) if assignee_logins else ''
                # Truncate long body text
                elif key == 'body' and isinstance(value, str) and len(value) > 200:
                    new_row[key] = value[:200] + '...'
                # Keep other fields as-is
                else:
                    new_row[key] = value
            transformed.append(new_row)

        return transformed

    @staticmethod
    def analyze(results: Dict[str, Any], intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze query results and return layout specification.

        Args:
            results: Query results dict with 'count', 'results', 'entity', 'aggregations' keys
            intent: Intent dict with 'entity', 'group_by', and other metadata

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

        # Check for aggregations - prefer charts over tables for aggregated data
        aggregations = results.get('aggregations', {})
        if aggregations and 'group_counts' in aggregations:
            return LayoutAnalyzer._generate_aggregation_layout(
                results, intent, aggregations
            )

        # Small dataset (< 5): summary only
        if count < 5:
            layout.append({
                'type': 'summary',
                'content': f'Found {count} {intent.get("entity", "items")}'
            })
            return layout

        # Medium/large dataset (5+): summary + table
        if count >= 5:
            entity_name = intent.get('entity', 'items')

            # Use pagination metadata if available
            pagination = results.get('pagination')

            if pagination:
                # Build summary with pagination info
                estimated_total = pagination['estimated_total']
                start = pagination['offset'] + 1
                end = pagination['offset'] + count

                # Format total (could be string "100+" or int)
                total_str = str(estimated_total)

                summary_text = f'Found {total_str} {entity_name} (showing results {start}-{end})'
            else:
                # Fallback for non-paginated responses (backward compatibility)
                limit = intent.get('limit', 100)
                if count > 50:
                    summary_text = f'Found {count} {entity_name} (showing first {min(limit, count)})'
                else:
                    summary_text = f'Found {count} {entity_name}'

            layout.append({
                'type': 'summary',
                'content': summary_text
            })

            # Generate table columns from first result
            data = results.get('results', [])

            # Transform complex fields into displayable strings
            data = LayoutAnalyzer._transform_complex_fields(data)

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

    @staticmethod
    def _generate_aggregation_layout(
        results: Dict[str, Any],
        intent: Dict[str, Any],
        aggregations: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate layout for aggregated data using charts.

        Args:
            results: Query results
            intent: Intent dict
            aggregations: Aggregations data with group_counts

        Returns:
            List of layout specifications with chart components
        """
        layout = []
        entity_name = intent.get('entity', 'items')
        grouped_by = aggregations.get('grouped_by', 'category')
        group_counts = aggregations.get('group_counts', {})
        total_count = aggregations.get('total_count', 0)

        # Summary text
        num_groups = len(group_counts)
        layout.append({
            'type': 'summary',
            'content': f'Found {total_count} {entity_name} across {num_groups} categories'
        })

        # Determine chart type based on data characteristics
        # - Pie chart: 2-5 categories, showing proportions of a whole
        # - Bar chart: 3+ categories, better for comparisons
        # - Line chart: time series data (future enhancement)

        # Transform group_counts into chart data format
        chart_data = [
            {'name': str(name), 'value': count}
            for name, count in group_counts.items()
        ]

        # Sort by value descending for better visualization
        chart_data.sort(key=lambda x: x['value'], reverse=True)

        # Generate title
        title = f'{entity_name.title()} by {grouped_by.replace("_", " ").title()}'

        # Choose chart type based on number of categories
        num_categories = len(chart_data)

        if num_categories <= 5:
            # 2-5 categories: pie chart shows proportions well
            chart_type = 'pie_chart'
        else:
            # Many categories (6+): bar chart better for comparison
            chart_type = 'bar_chart'

        layout.append({
            'type': chart_type,
            'title': title,
            'data': chart_data
        })

        # Also include a small summary table with the counts
        table_data = [
            {grouped_by.title(): name, 'Count': count}
            for name, count in group_counts.items()
        ]

        # Transform any complex fields
        table_data = LayoutAnalyzer._transform_complex_fields(table_data)

        layout.append({
            'type': 'table',
            'data': table_data,
            'columns': [
                {'field': grouped_by.title(), 'header': grouped_by.replace('_', ' ').title(), 'sortable': True},
                {'field': 'Count', 'header': 'Count', 'sortable': True}
            ]
        })

        return layout
