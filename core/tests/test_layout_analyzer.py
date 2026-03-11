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
