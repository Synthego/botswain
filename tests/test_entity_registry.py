# tests/test_entity_registry.py
import pytest
from core.semantic_layer.registry import EntityRegistry
from core.semantic_layer.entities.base import BaseEntity

class MockEntity(BaseEntity):
    name = "mock_entity"
    description = "Mock entity for testing"

    def get_queryset(self, filters=None):
        return []

    def get_attributes(self):
        return ['name', 'status']

    def validate_filters(self, filters):
        return True

def test_registry_initialization():
    """Test that registry can be initialized"""
    registry = EntityRegistry()
    assert registry is not None

def test_registry_register_entity():
    """Test that entities can be registered"""
    registry = EntityRegistry()
    entity = MockEntity()

    registry.register(entity)
    assert 'mock_entity' in registry.list_entities()

def test_registry_get_entity():
    """Test that registered entities can be retrieved"""
    registry = EntityRegistry()
    entity = MockEntity()
    registry.register(entity)

    retrieved = registry.get('mock_entity')
    assert retrieved is entity

def test_registry_get_nonexistent_entity():
    """Test that getting nonexistent entity returns None"""
    registry = EntityRegistry()

    result = registry.get('nonexistent')
    assert result is None

def test_registry_get_entity_descriptions():
    """Test getting all entity descriptions"""
    registry = EntityRegistry()
    entity = MockEntity()
    registry.register(entity)

    descriptions = registry.get_entity_descriptions()
    assert descriptions['mock_entity'] == "Mock entity for testing"
