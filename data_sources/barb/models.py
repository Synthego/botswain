"""
Mock BARB models for development.

In production, this would import from syntheseas-barbie package:
    from syntheseas.barbie.models import Instrument, InstrumentType, etc.

For now, we provide mock implementations.
"""

class MockQuerySet:
    """Mock Django queryset for testing"""

    def __init__(self, data=None):
        self._data = data or []

    def filter(self, **kwargs):
        # Simple filter implementation
        return MockQuerySet(self._data)

    def select_related(self, *args):
        return self

    def values(self, *fields):
        return self._data

    def __iter__(self):
        return iter(self._data)

class MockManager:
    """Mock Django model manager"""

    def __init__(self, model_class):
        self.model_class = model_class

    def filter(self, **kwargs):
        return MockQuerySet([])

    def all(self):
        return MockQuerySet([])

class InstrumentType:
    """Mock InstrumentType model"""
    name = None

class Factory:
    """Mock Factory model"""
    name = None

class Location:
    """Mock Location model"""
    name = None

class Instrument:
    """
    Mock Instrument model.

    In real implementation, this would be:
        from syntheseas.barbie.models import Instrument
    """

    objects = MockManager(None)

    def __init__(self):
        self.name = None
        self.status = None
        self.instrument_type = InstrumentType()
        self.factory = Factory()
        self.installation_location = Location()
