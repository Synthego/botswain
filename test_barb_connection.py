#!/usr/bin/env python
"""
Test script to verify BARB connection and query instruments.
Run with: DJANGO_SETTINGS_MODULE=botswain.settings.barb_local python test_barb_connection.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'botswain.settings.barb_local')
django.setup()

from core.semantic_layer.entities.instrument_barb import InstrumentEntity
from django.conf import settings

def test_barb_connection():
    print("=" * 60)
    print("Testing BARB Database Connection")
    print("=" * 60)
    print()

    # Show database config
    print(f"Database: {settings.DATABASES['default']['NAME']}")
    print(f"Host: {settings.DATABASES['default']['HOST']}")
    print(f"Port: {settings.DATABASES['default']['PORT']}")
    print()

    # Test instrument entity
    entity = InstrumentEntity()
    print(f"Entity: {entity.name}")
    print(f"Description: {entity.description}")
    print()

    # Query all instruments
    print("Querying all instruments...")
    results = entity.get_queryset()
    print(f"Found {len(results)} instruments")
    print()

    # Show summary by type
    if results:
        from collections import Counter
        types = Counter(r['instrument_type'] for r in results)
        print("Instruments by type:")
        for inst_type, count in types.most_common():
            print(f"  {inst_type}: {count}")
        print()

        # Show first few instruments
        print("Sample instruments:")
        for i, inst in enumerate(results[:5], 1):
            print(f"  {i}. {inst['barcode']} - {inst['instrument_type']} - {inst['status']}")
        print()

    # Test filtered query
    print("Testing filtered query (zebra_printer)...")
    filtered = entity.get_queryset({'instrument_type': 'zebra_printer'})
    print(f"Found {len(filtered)} zebra printers")
    print()

    # Test status filter
    print("Testing status filter (ONLINE)...")
    online = entity.get_queryset({'status': 'ONLINE'})
    print(f"Found {len(online)} ONLINE instruments")
    print()

    print("=" * 60)
    print("✓ BARB Connection Test Complete!")
    print("=" * 60)

if __name__ == '__main__':
    test_barb_connection()
