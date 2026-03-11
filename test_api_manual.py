#!/usr/bin/env python
"""Manual API test with mocked LLM provider"""
import os
import sys
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'botswain.settings.test')
django.setup()

from unittest.mock import patch, Mock
from core.llm.factory import LLMProviderFactory
from rest_framework.test import APIClient
from django.contrib.auth.models import User
import json

# Create a mock provider
mock_provider = Mock()
mock_provider.parse_intent.return_value = {
    'entity': 'synthesizer',
    'intent_type': 'query',
    'filters': {'status': 'ONLINE'},
    'attributes': ['name', 'status', 'factory'],
    'limit': 10
}
mock_provider.format_response.return_value = "Found 3 online synthesizers ready for RNA synthesis."

# Patch the factory to return our mock
with patch.object(LLMProviderFactory, 'create', return_value=mock_provider):
    client = APIClient()
    user = User.objects.create_user(username='test@synthego.com', email='test@synthego.com')
    client.force_authenticate(user=user)
    
    # Test query
    response = client.post('/api/query', {
        'question': 'What synthesizers are available?',
        'format': 'json',
        'use_cache': True
    }, format='json')
    
    print("=" * 80)
    print("BOTSWAIN API TEST - Natural Language Query")
    print("=" * 80)
    print(f"\nStatus Code: {response.status_code}")
    print(f"\nRequest:")
    print('  POST /api/query')
    print('  {')
    print('    "question": "What synthesizers are available?",')
    print('    "format": "json",')
    print('    "use_cache": true')
    print('  }')
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nResponse:")
        print(json.dumps(data, indent=2, default=str))
        print(f"\n✓ Query executed successfully!")
        print(f"  - Intent parsed: {data['intent']['entity']}")
        print(f"  - Query type: {data['intent']['intent_type']}")
        print(f"  - Filters: {data['intent']['filters']}")
        print(f"  - Natural language response: {data['response']}")
        print(f"  - Execution time: {data['results']['execution_time_ms']}ms")
    else:
        print(f"\n✗ Error: {response.content.decode()}")
    
    print("\n" + "=" * 80)
    
    # Check audit log
    from core.models import QueryLog
    latest_log = QueryLog.objects.order_by('-executed_at').first()
    if latest_log:
        print("AUDIT LOG CREATED:")
        print("=" * 80)
        print(f"  User: {latest_log.username}")
        print(f"  Question: {latest_log.question}")
        print(f"  Entity: {latest_log.entity}")
        print(f"  Intent Type: {latest_log.intent_type}")
        print(f"  Success: {latest_log.success}")
        print(f"  Execution Time: {latest_log.execution_time_ms}ms")
        print(f"  Interface: {latest_log.interface}")
        print(f"  Timestamp: {latest_log.executed_at}")
        print("=" * 80)
    
    sys.exit(0)
