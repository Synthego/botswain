"""
Tests for LayoutAnalyzer - analyzes query results and generates layout specifications.
"""
import pytest
from core.layout_analyzer import LayoutAnalyzer


class TestLayoutAnalyzer:
    """Tests for layout analysis and component selection logic."""

    def test_empty_results_returns_empty_state(self):
        """When count is 0, return empty state component."""
        results = {
            'count': 0,
            'results': [],
            'entity': 'synthesizer'
        }
        intent = {'entity': 'synthesizer'}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert len(layout) == 1
        assert layout[0]['type'] == 'empty'
        assert 'message' in layout[0]

    def test_small_dataset_returns_summary_only(self):
        """When count < 5, return summary card only."""
        results = {
            'count': 2,
            'results': [
                {'name': 'SSA-101', 'status': 'running'},
                {'name': 'SSA-102', 'status': 'idle'}
            ],
            'entity': 'synthesizer'
        }
        intent = {'entity': 'synthesizer'}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert len(layout) == 1
        assert layout[0]['type'] == 'summary'
        assert 'content' in layout[0]

    def test_medium_dataset_returns_summary_and_table(self):
        """When count 5-50, return summary + table."""
        results = {
            'count': 10,
            'results': [
                {'name': f'SSA-{i}', 'status': 'running', 'location': 'Lab A'}
                for i in range(10)
            ],
            'entity': 'synthesizer'
        }
        intent = {'entity': 'synthesizer'}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert len(layout) == 2
        assert layout[0]['type'] == 'summary'
        assert layout[1]['type'] == 'table'
        assert 'data' in layout[1]
        assert 'columns' in layout[1]
        assert len(layout[1]['data']) == 10

    def test_large_dataset_adds_pagination_hint(self):
        """When count > 50, add pagination hint to summary."""
        results = {
            'count': 100,
            'results': [
                {'name': f'SSA-{i}', 'status': 'running'}
                for i in range(100)
            ],
            'entity': 'synthesizer'
        }
        intent = {'entity': 'synthesizer', 'limit': 100}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert len(layout) == 2
        assert layout[0]['type'] == 'summary'
        assert 'showing' in layout[0]['content'].lower() or 'limited' in layout[0]['content'].lower()
        assert layout[1]['type'] == 'table'


class TestLayoutAnalyzerPagination:
    """Test layout analyzer with pagination metadata"""

    def test_summary_includes_page_range_from_pagination(self):
        """Summary should show 'showing results X-Y' when pagination present"""
        results = {
            'count': 50,
            'results': [{'name': f'Item {i}'} for i in range(50)],
            'entity': 'order',
            'pagination': {
                'current_page': 2,
                'offset': 50,
                'limit': 50,
                'estimated_total': '100+'
            }
        }
        intent = {'entity': 'order', 'limit': 50}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert len(layout) == 2
        assert layout[0]['type'] == 'summary'
        assert 'showing results 51-100' in layout[0]['content'].lower()

    def test_summary_shows_estimated_total(self):
        """Summary should show estimated total from pagination"""
        results = {
            'count': 50,
            'results': [{'name': f'Item {i}'} for i in range(50)],
            'entity': 'order',
            'pagination': {
                'current_page': 1,
                'offset': 0,
                'estimated_total': '150+'
            }
        }
        intent = {'entity': 'order', 'limit': 50}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert '150+' in layout[0]['content']

    def test_summary_shows_exact_total_on_last_page(self):
        """Summary should show exact total (not +) on last page"""
        results = {
            'count': 25,
            'results': [{'name': f'Item {i}'} for i in range(25)],
            'entity': 'order',
            'pagination': {
                'current_page': 3,
                'offset': 100,
                'estimated_total': 125,  # Exact, not string
                'has_next': False
            }
        }
        intent = {'entity': 'order', 'limit': 50}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert '125' in layout[0]['content']
        assert '125+' not in layout[0]['content']

    def test_fallback_to_old_format_without_pagination(self):
        """Should work with old response format (no pagination field)"""
        results = {
            'count': 10,
            'results': [{'name': f'Item {i}'} for i in range(10)],
            'entity': 'order'
        }
        intent = {'entity': 'order', 'limit': 100}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert len(layout) == 2
        assert layout[0]['type'] == 'summary'
        assert 'Found 10 order' in layout[0]['content']
