import pytest
from core.pagination import PaginationMetadata


class TestPaginationMetadata:
    """Test pagination metadata calculation"""

    def test_first_page_with_more_results(self):
        """First page with has_next=True"""
        metadata = PaginationMetadata.build(
            offset=0,
            limit=50,
            has_next=True,
            has_previous=False,
            result_count=50
        )

        assert metadata['current_page'] == 1
        assert metadata['page_size'] == 50
        assert metadata['offset'] == 0
        assert metadata['limit'] == 50
        assert metadata['has_next'] is True
        assert metadata['has_previous'] is False
        assert metadata['next_page'] == 2
        assert metadata['next_offset'] == 50
        assert 'previous_page' not in metadata
        assert 'previous_offset' not in metadata
        assert metadata['estimated_total'] == '51+'
        assert metadata['estimated_total_pages'] == '2+'

    def test_middle_page(self):
        """Middle page with both next and previous"""
        metadata = PaginationMetadata.build(
            offset=100,
            limit=50,
            has_next=True,
            has_previous=True,
            result_count=50
        )

        assert metadata['current_page'] == 3
        assert metadata['has_next'] is True
        assert metadata['has_previous'] is True
        assert metadata['next_page'] == 4
        assert metadata['next_offset'] == 150
        assert metadata['previous_page'] == 2
        assert metadata['previous_offset'] == 50
        assert metadata['estimated_total'] == '151+'

    def test_last_page_exact_count(self):
        """Last page shows exact total (not estimated)"""
        metadata = PaginationMetadata.build(
            offset=200,
            limit=50,
            has_next=False,
            has_previous=True,
            result_count=25
        )

        assert metadata['current_page'] == 5
        assert metadata['has_next'] is False
        assert metadata['has_previous'] is True
        assert 'next_page' not in metadata
        assert 'next_offset' not in metadata
        assert metadata['previous_page'] == 4
        assert metadata['previous_offset'] == 150
        assert metadata['estimated_total'] == 225  # Exact, not string
        assert metadata['estimated_total_pages'] == 5  # Exact, not string

    def test_only_page_no_more_results(self):
        """Single page with all results"""
        metadata = PaginationMetadata.build(
            offset=0,
            limit=100,
            has_next=False,
            has_previous=False,
            result_count=10
        )

        assert metadata['current_page'] == 1
        assert metadata['has_next'] is False
        assert metadata['has_previous'] is False
        assert metadata['estimated_total'] == 10
        assert metadata['estimated_total_pages'] == 1

    def test_empty_results(self):
        """Empty results page"""
        metadata = PaginationMetadata.build(
            offset=0,
            limit=50,
            has_next=False,
            has_previous=False,
            result_count=0
        )

        assert metadata['current_page'] == 1
        assert metadata['estimated_total'] == 0
        assert metadata['estimated_total_pages'] == 0

    def test_different_page_sizes(self):
        """Test with various page sizes"""
        # Page size 25
        metadata = PaginationMetadata.build(
            offset=25,
            limit=25,
            has_next=True,
            has_previous=True,
            result_count=25
        )
        assert metadata['current_page'] == 2
        assert metadata['previous_offset'] == 0
        assert metadata['next_offset'] == 50

        # Page size 200
        metadata = PaginationMetadata.build(
            offset=400,
            limit=200,
            has_next=False,
            has_previous=True,
            result_count=50
        )
        assert metadata['current_page'] == 3
        assert metadata['previous_offset'] == 200
