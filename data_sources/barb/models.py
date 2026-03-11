"""
Unmanaged Django models for BARB production tables.

These models map to existing BARB database tables without creating/managing them.
Django will query these tables directly from the 'barb' database connection.

NOTE: syntheseas-barbie package is deprecated. Using unmanaged models instead.
"""
from django.db import models


class InstrumentType(models.Model):
    """Unmanaged model for BARB's inventory_instrument_type table"""

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'inventory_instrument_type'

    def __str__(self):
        return self.name


class Instrument(models.Model):
    """
    Unmanaged model for BARB's inventory_instrument table.

    Maps to existing production table - does NOT create or migrate.
    """

    barcode_ptr_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    host = models.CharField(max_length=255, null=True, blank=True)
    port = models.IntegerField(null=True, blank=True)

    # Foreign key to instrument type (other foreign keys removed - tables don't exist)
    instrument_type = models.ForeignKey(InstrumentType, on_delete=models.DO_NOTHING, db_column='instrument_type_id')

    class Meta:
        managed = False  # Don't create/migrate this table
        db_table = 'inventory_instrument'  # Use existing BARB table

    def __str__(self):
        return f"{self.name} ({self.barcode_ptr_id})"

    @property
    def barcode(self):
        """Alias for barcode_ptr_id"""
        return str(self.barcode_ptr_id)
