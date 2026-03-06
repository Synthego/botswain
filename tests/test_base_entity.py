# tests/test_base_entity.py
import pytest
from core.semantic_layer.entities.base import BaseEntity

def test_base_entity_is_abstract():
    """Test that BaseEntity cannot be instantiated directly"""
    with pytest.raises(TypeError):
        BaseEntity()

def test_base_entity_requires_get_queryset():
    """Test that subclasses must implement get_queryset"""
    class IncompleteEntity(BaseEntity):
        name = "test"
        description = "Test entity"

        def get_attributes(self):
            return []

        def validate_filters(self, filters):
            return True

    with pytest.raises(TypeError):
        IncompleteEntity()

def test_base_entity_complete_implementation():
    """Test that complete implementation works"""
    class CompleteEntity(BaseEntity):
        name = "test"
        description = "Test entity"

        def get_queryset(self, filters=None):
            return []

        def get_attributes(self):
            return ['name', 'status']

        def validate_filters(self, filters):
            return True

    entity = CompleteEntity()
    assert entity.name == "test"
    assert entity.get_attributes() == ['name', 'status']
    assert entity.validate_filters({}) is True
