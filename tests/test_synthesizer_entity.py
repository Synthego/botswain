# tests/test_synthesizer_entity.py
import pytest
from core.semantic_layer.entities.synthesizer import SynthesizerEntity

def test_synthesizer_entity_initialization():
    """Test that synthesizer entity can be created"""
    entity = SynthesizerEntity()
    assert entity.name == "synthesizer"
    assert "RNA/DNA" in entity.description

def test_synthesizer_entity_get_attributes():
    """Test that synthesizer entity returns correct attributes"""
    entity = SynthesizerEntity()
    attributes = entity.get_attributes()

    assert 'name' in attributes
    assert 'status' in attributes
    assert 'factory' in attributes

def test_synthesizer_entity_validate_filters():
    """Test filter validation"""
    entity = SynthesizerEntity()

    # Valid filters
    assert entity.validate_filters({'status': 'ONLINE'}) is True
    assert entity.validate_filters({'factory': 'ec'}) is True

    # Invalid filters
    assert entity.validate_filters({'invalid_field': 'value'}) is False

def test_synthesizer_entity_get_queryset():
    """Test that queryset is returned"""
    entity = SynthesizerEntity()
    qs = entity.get_queryset()

    # Should return a queryset-like object
    assert hasattr(qs, 'filter')

def test_synthesizer_entity_get_queryset_with_filters():
    """Test queryset with filters applied"""
    entity = SynthesizerEntity()
    qs = entity.get_queryset(filters={'status': 'ONLINE'})

    assert qs is not None
