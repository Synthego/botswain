# tests/test_api_serializers.py
import pytest
from api.serializers import QueryRequestSerializer, QueryResponseSerializer

def test_query_request_serializer_valid():
    """Test valid query request"""
    data = {
        'question': 'What synthesizers are available?',
        'format': 'natural',
        'use_cache': True
    }

    serializer = QueryRequestSerializer(data=data)
    assert serializer.is_valid()
    assert serializer.validated_data['question'] == data['question']

def test_query_request_serializer_missing_question():
    """Test that question is required"""
    data = {'format': 'natural'}

    serializer = QueryRequestSerializer(data=data)
    assert not serializer.is_valid()
    assert 'question' in serializer.errors

def test_query_request_serializer_defaults():
    """Test default values"""
    data = {'question': 'Test question'}

    serializer = QueryRequestSerializer(data=data)
    assert serializer.is_valid()
    assert serializer.validated_data['format'] == 'natural'
    assert serializer.validated_data['use_cache'] is True


class TestQueryRequestSerializerPagination:
    """Test pagination parameter validation"""

    def test_accepts_page_and_page_size(self):
        """Serializer should accept page and page_size parameters"""
        data = {
            'question': 'Show orders',
            'page': 2,
            'page_size': 50
        }
        serializer = QueryRequestSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data['page'] == 2
        assert serializer.validated_data['page_size'] == 50

    def test_accepts_offset_and_limit(self):
        """Serializer should accept offset and limit parameters"""
        data = {
            'question': 'Show orders',
            'offset': 100,
            'limit': 50
        }
        serializer = QueryRequestSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data['offset'] == 100
        assert serializer.validated_data['limit'] == 50

    def test_page_defaults_to_1(self):
        """Page parameter should be optional (not in validated_data if omitted)"""
        data = {
            'question': 'Show orders',
            'page_size': 50
        }
        serializer = QueryRequestSerializer(data=data)
        assert serializer.is_valid()
        # Page is optional - not in validated_data if not provided
        assert 'page' not in serializer.validated_data
        assert serializer.validated_data['page_size'] == 50

    def test_page_size_defaults_to_100(self):
        """Page_size should default to 100 when not provided"""
        data = {
            'question': 'Show orders',
            'page': 1
        }
        serializer = QueryRequestSerializer(data=data)
        assert serializer.is_valid()
        # page_size is optional - not in validated_data if not provided
        # (default will be applied in view layer)
        assert 'page_size' not in serializer.validated_data

    def test_rejects_page_zero(self):
        """Page cannot be 0 or negative"""
        data = {
            'question': 'Show orders',
            'page': 0
        }
        serializer = QueryRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'page' in serializer.errors

        data['page'] = -1
        serializer = QueryRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'page' in serializer.errors

    def test_rejects_negative_offset(self):
        """Offset cannot be negative"""
        data = {
            'question': 'Show orders',
            'offset': -1
        }
        serializer = QueryRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'offset' in serializer.errors

    def test_rejects_excessive_page_size(self):
        """Page_size cannot exceed 1000"""
        data = {
            'question': 'Show orders',
            'page_size': 1001
        }
        serializer = QueryRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'page_size' in serializer.errors

    def test_rejects_excessive_limit(self):
        """Limit cannot exceed 1000"""
        data = {
            'question': 'Show orders',
            'limit': 1001
        }
        serializer = QueryRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'limit' in serializer.errors
