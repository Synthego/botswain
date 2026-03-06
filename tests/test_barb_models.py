# tests/test_barb_models.py
import pytest

def test_can_import_mock_instrument():
    """Test that we can import mock Instrument model"""
    from data_sources.barb.models import Instrument
    assert Instrument is not None

def test_mock_instrument_has_required_fields():
    """Test that mock Instrument has required fields"""
    from data_sources.barb.models import Instrument

    # For now, just verify it's importable
    # In real implementation, this would use syntheseas-barbie package
    assert hasattr(Instrument, 'objects')
