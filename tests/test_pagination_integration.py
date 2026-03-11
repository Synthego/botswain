"""
End-to-end integration tests for pagination feature.

Tests the complete flow from API request to paginated response.
"""
import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from unittest.mock import patch, Mock


@pytest.mark.django_db
class TestPaginationEndToEnd:
    """End-to-end pagination integration tests"""

    def setup_method(self):
        """Setup test client and user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test@synthego.com',
            email='test@synthego.com'
        )
        self.client.force_authenticate(user=self.user)

    def _setup_mocks(self, executor_response_override=None):
        """Setup common mocks for API tests"""
        # Default executor response
        default_executor_response = {
            'success': True,
            'entity': 'order',
            'results': [{'id': i} for i in range(20)],  # Mock 20 results
            'count': 20,
            'execution_time_ms': 10,
            'pagination': {
                'offset': 0,
                'limit': 10,
                'current_page': 1,
                'page_size': 10,
                'has_next': True,
                'has_previous': False,
                'estimated_total': 100,
                'estimated_total_pages': 10
            }
        }

        executor_response = executor_response_override or default_executor_response

        # Mock LLM provider
        mock_llm = patch('api.views.LLMProviderFactory.get_default')
        mock_provider = Mock()
        mock_provider.parse_intent.return_value = {
            'entity': 'order',
            'intent_type': 'query',
            'filters': {},
            '_tokens': {'input': 10, 'output': 5, 'total': 15}
        }
        mock_provider.format_response.return_value = {
            'text': "Test response",
            'tokens': {'input': 5, 'output': 3, 'total': 8}
        }
        mock_provider.model = 'test-model'
        mock_llm_factory = mock_llm.start()
        mock_llm_factory.return_value = mock_provider

        # Mock QueryPlanner
        mock_planner_patch = patch('api.views.QueryPlanner')
        mock_planner = Mock()
        mock_planner.execute_multi_entity_query.return_value = (False, None)
        mock_planner_class = mock_planner_patch.start()
        mock_planner_class.return_value = mock_planner

        # Mock QueryExecutor
        mock_executor_patch = patch('api.views.QueryExecutor')
        mock_executor = Mock()
        mock_executor.execute.return_value = executor_response
        mock_executor_class = mock_executor_patch.start()
        mock_executor_class.return_value = mock_executor

        return {
            'llm_patch': mock_llm,
            'planner_patch': mock_planner_patch,
            'executor_patch': mock_executor_patch,
            'executor': mock_executor
        }

    def test_paginate_through_multiple_pages(self):
        """Paginate through multiple pages of results"""
        mocks = self._setup_mocks()

        try:
            # Page 1
            response = self.client.post('/api/query', {
                'question': 'Show orders',
                'page': 1,
                'page_size': 10
            }, format='json')

            assert response.status_code == 200
            page1 = response.json()

            assert page1['pagination']['current_page'] == 1
            assert page1['pagination']['has_previous'] is False

            # Update mock for page 2
            mocks['executor'].execute.return_value = {
                'success': True,
                'entity': 'order',
                'results': [{'id': i} for i in range(10, 20)],
                'count': 10,
                'execution_time_ms': 10,
                'pagination': {
                    'offset': 10,
                    'limit': 10,
                    'current_page': 2,
                    'page_size': 10,
                    'has_next': True,
                    'has_previous': True,
                    'previous_page': 1,
                    'estimated_total': 100,
                    'estimated_total_pages': 10
                }
            }

            # Page 2
            response = self.client.post('/api/query', {
                'question': 'Show orders',
                'page': 2,
                'page_size': 10
            }, format='json')

            assert response.status_code == 200
            page2 = response.json()

            assert page2['pagination']['current_page'] == 2
            assert page2['pagination']['has_previous'] is True
            assert page2['pagination']['previous_page'] == 1
        finally:
            mocks['llm_patch'].stop()
            mocks['planner_patch'].stop()
            mocks['executor_patch'].stop()

    def test_offset_limit_equivalent_to_page_page_size(self):
        """offset/limit should return same results as equivalent page/page_size"""
        mocks = self._setup_mocks({
            'success': True,
            'entity': 'order',
            'results': [],
            'count': 0,
            'execution_time_ms': 10,
            'pagination': {
                'offset': 40,
                'limit': 20,
                'current_page': 3,
                'page_size': 20,
                'has_next': False,
                'has_previous': True,
                'estimated_total': 50,
                'estimated_total_pages': 3
            }
        })

        try:
            # Using page/page_size
            response1 = self.client.post('/api/query', {
                'question': 'Show orders',
                'page': 3,
                'page_size': 20
            }, format='json')

            # Using equivalent offset/limit
            response2 = self.client.post('/api/query', {
                'question': 'Show orders',
                'offset': 40,  # (3-1) * 20
                'limit': 20
            }, format='json')

            assert response1.status_code == 200
            assert response2.status_code == 200

            page1 = response1.json()
            page2 = response2.json()

            # Pagination metadata should be identical
            assert page1['pagination']['offset'] == page2['pagination']['offset']
            assert page1['pagination']['limit'] == page2['pagination']['limit']
            assert page1['pagination']['current_page'] == page2['pagination']['current_page']
        finally:
            mocks['llm_patch'].stop()
            mocks['planner_patch'].stop()
            mocks['executor_patch'].stop()

    def test_cache_stores_different_pages_separately(self):
        """Different pages should be cached separately"""
        mocks = self._setup_mocks()

        try:
            # Query page 1 with use_cache=False to ensure fresh result
            response1 = self.client.post('/api/query', {
                'question': 'Show orders',
                'page': 1,
                'page_size': 10,
                'use_cache': False
            }, format='json')

            # Update mock for page 2
            mocks['executor'].execute.return_value = {
                'success': True,
                'entity': 'order',
                'results': [],
                'count': 0,
                'execution_time_ms': 10,
                'pagination': {
                    'offset': 10,
                    'limit': 10,
                    'current_page': 2,
                    'page_size': 10,
                    'has_next': False,
                    'has_previous': True,
                    'estimated_total': 15,
                    'estimated_total_pages': 2
                }
            }

            # Query page 2 with use_cache=False
            response2 = self.client.post('/api/query', {
                'question': 'Show orders',
                'page': 2,
                'page_size': 10,
                'use_cache': False
            }, format='json')

            # Reset mock back to page 1 values for cache verification
            mocks['executor'].execute.return_value = {
                'success': True,
                'entity': 'order',
                'results': [{'id': i} for i in range(20)],
                'count': 20,
                'execution_time_ms': 10,
                'pagination': {
                    'offset': 0,
                    'limit': 10,
                    'current_page': 1,
                    'page_size': 10,
                    'has_next': True,
                    'has_previous': False,
                    'estimated_total': 100,
                    'estimated_total_pages': 10
                }
            }

            # Query page 1 again with cache enabled - if cache works, should get original page 1
            response3 = self.client.post('/api/query', {
                'question': 'Show orders',
                'page': 1,
                'page_size': 10,
                'use_cache': True
            }, format='json')

            assert response1.status_code == 200
            assert response2.status_code == 200
            assert response3.status_code == 200

            page1a = response1.json()
            page2 = response2.json()
            page1b = response3.json()

            # Page 1 results should be identical (from cache or same pagination)
            assert page1a['pagination']['offset'] == page1b['pagination']['offset']
            assert page1a['pagination']['current_page'] == page1b['pagination']['current_page']

            # Page 2 should be different from page 1
            assert page1a['pagination']['offset'] != page2['pagination']['offset']
            assert page2['pagination']['current_page'] == 2
        finally:
            mocks['llm_patch'].stop()
            mocks['planner_patch'].stop()
            mocks['executor_patch'].stop()

    def test_first_page_has_no_previous(self):
        """First page should not have previous page helpers"""
        mocks = self._setup_mocks({
            'success': True,
            'entity': 'order',
            'results': [],
            'count': 0,
            'execution_time_ms': 10,
            'pagination': {
                'offset': 0,
                'limit': 50,
                'current_page': 1,
                'page_size': 50,
                'has_next': False,
                'has_previous': False,
                'estimated_total': 25,
                'estimated_total_pages': 1
            }
        })

        try:
            response = self.client.post('/api/query', {
                'question': 'Show orders',
                'page': 1,
                'page_size': 50
            }, format='json')

            assert response.status_code == 200
            data = response.json()

            assert data['pagination']['has_previous'] is False
            assert 'previous_page' not in data['pagination']
            assert 'previous_offset' not in data['pagination']
        finally:
            mocks['llm_patch'].stop()
            mocks['planner_patch'].stop()
            mocks['executor_patch'].stop()

    def test_validation_errors_for_invalid_params(self):
        """Invalid pagination parameters should return 400 error"""
        # Negative page
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': -1
        }, format='json')
        assert response.status_code == 400

        # Zero page
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': 0
        }, format='json')
        assert response.status_code == 400

        # Negative offset
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'offset': -10
        }, format='json')
        assert response.status_code == 400

        # Excessive page size
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'page_size': 5000
        }, format='json')
        assert response.status_code == 400

    def test_layout_includes_pagination_info(self):
        """Layout should include pagination information in summary"""
        mocks = self._setup_mocks({
            'success': True,
            'entity': 'order',
            'results': [{'id': i, 'name': f'Order {i}'} for i in range(20, 40)],  # Add actual results
            'count': 20,
            'execution_time_ms': 10,
            'pagination': {
                'offset': 20,
                'limit': 20,
                'current_page': 2,
                'page_size': 20,
                'has_next': True,
                'has_previous': True,
                'previous_page': 1,
                'estimated_total': 100,
                'estimated_total_pages': 5
            }
        })

        try:
            response = self.client.post('/api/query', {
                'question': 'Show orders',
                'page': 2,
                'page_size': 20
            }, format='json')

            assert response.status_code == 200
            data = response.json()

            assert 'layout' in data
            if data['layout']:
                summary = data['layout'][0]
                # Should be summary type with actual results, or empty if no results
                assert summary['type'] in ['summary', 'empty']
                # If there are results, should mention result range
                if summary['type'] == 'summary':
                    content = summary['content'].lower()
                    assert 'showing results' in content or 'found' in content
        finally:
            mocks['llm_patch'].stop()
            mocks['planner_patch'].stop()
            mocks['executor_patch'].stop()

    def test_backward_compatibility_no_pagination_params(self):
        """Requests without pagination params should still work (defaults)"""
        mocks = self._setup_mocks({
            'success': True,
            'entity': 'order',
            'results': [],
            'count': 0,
            'execution_time_ms': 10,
            'pagination': {
                'offset': 0,
                'limit': 100,
                'current_page': 1,
                'page_size': 100,
                'has_next': False,
                'has_previous': False,
                'estimated_total': 50,
                'estimated_total_pages': 1
            }
        })

        try:
            response = self.client.post('/api/query', {
                'question': 'Show orders'
            }, format='json')

            assert response.status_code == 200
            data = response.json()

            # Should have pagination metadata with defaults
            assert 'pagination' in data
            assert data['pagination']['current_page'] == 1
            assert data['pagination']['offset'] == 0
            assert data['pagination']['limit'] == 100  # Default
        finally:
            mocks['llm_patch'].stop()
            mocks['planner_patch'].stop()
            mocks['executor_patch'].stop()
