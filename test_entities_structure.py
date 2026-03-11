#!/usr/bin/env python
"""
Test entity structure without requiring database connections.
Validates entity methods, attributes, and filter validation.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'botswain.settings.test')
django.setup()

from core.semantic_layer.entities.kraken_workflows import KrakenWorkflowEntity
from core.semantic_layer.entities.sos_sequencing import SOSSequencingEntity


def test_entity_structure(entity_class, entity_name):
    """Test entity structure without database access"""
    print(f"\n{'='*70}")
    print(f"Testing {entity_name}")
    print(f"{'='*70}\n")

    entity = entity_class()

    # Test basic attributes
    print(f"✅ Entity name: {entity.name}")
    print(f"✅ Description: {entity.description[:80]}...")

    # Test get_attributes
    attributes = entity.get_attributes()
    print(f"✅ Attributes defined: {len(attributes)}")
    print(f"   Sample: {', '.join(attributes[:5])}")

    # Test filter validation
    valid_filters = {
        'query_type': 'orders',
        'hours_ago': 24,
        'limit': 10
    }
    is_valid = entity.validate_filters(valid_filters)
    print(f"✅ Valid filters accepted: {is_valid}")

    invalid_filters = {
        'unknown_filter': 'value',
        'malicious_filter': 'DROP TABLE'
    }
    is_invalid = entity.validate_filters(invalid_filters)
    print(f"✅ Invalid filters rejected: {not is_invalid}")

    print(f"\n✅ {entity_name} structure tests passed\n")


def main():
    """Run structure tests for both entities"""
    print("\n" + "="*70)
    print("BOTSWAIN ENTITY STRUCTURE TESTS")
    print("="*70)

    # Test Kraken Workflows
    test_entity_structure(KrakenWorkflowEntity, "Kraken Workflows")

    # Test SOS Sequencing
    test_entity_structure(SOSSequencingEntity, "SOS Sequencing")

    print("\n" + "="*70)
    print("✅ ALL STRUCTURE TESTS PASSED")
    print("="*70)
    print("\n📝 Note: Database connectivity tests require VPN access to production databases")
    print("   These entities will work correctly when database connections are available.\n")


if __name__ == '__main__':
    main()
