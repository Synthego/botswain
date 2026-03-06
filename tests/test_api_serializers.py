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
