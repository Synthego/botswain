"""
Database router for multi-database setup.

Routes:
- BARB models (inventory_*, etc.) -> 'barb' database (read-only production replica)
- Botswain models (QueryLog, etc.) -> 'default' database (local, read-write)
"""


class BarbDatabaseRouter:
    """
    Route database operations based on app labels and model names.

    BARB models (from production) are read-only and go to 'barb' database.
    Botswain models (QueryLog, audit data) are read-write and go to 'default' database.
    """

    # BARB database table prefixes (these come from production BARB)
    BARB_TABLE_PREFIXES = [
        'inventory_',
        'auth_',
        'django_',
    ]

    # BARB app labels
    BARB_APP_LABELS = [
        'data_sources',  # data_sources.barb.models
    ]

    def db_for_read(self, model, **hints):
        """
        Route read operations.

        BARB models read from 'barb' database.
        Botswain models read from 'default' database.
        """
        # Check app label first (data_sources.barb.models)
        if model._meta.app_label in self.BARB_APP_LABELS:
            return 'barb'

        # Check table name prefix
        table_name = model._meta.db_table
        for prefix in self.BARB_TABLE_PREFIXES:
            if table_name.startswith(prefix):
                return 'barb'

        # All other models (QueryLog, etc.) use default
        return 'default'

    def db_for_write(self, model, **hints):
        """
        Route write operations.

        BARB models CANNOT be written to (read-only replica).
        Botswain models write to 'default' database.
        """
        # Check app label first
        if model._meta.app_label in self.BARB_APP_LABELS:
            # NEVER allow writes to BARB - it's read-only production data
            return None  # This will cause an error if write is attempted

        # Check table name prefix
        table_name = model._meta.db_table
        for prefix in self.BARB_TABLE_PREFIXES:
            if table_name.startswith(prefix):
                # NEVER allow writes to BARB - it's read-only production data
                return None  # This will cause an error if write is attempted

        # All Botswain models write to default
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between models in the same database.
        """
        db1 = self.db_for_read(obj1.__class__)
        db2 = self.db_for_read(obj2.__class__)

        # Allow relations if both models are in the same database
        if db1 == db2:
            return True

        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Only allow migrations on 'default' database.

        NEVER run migrations on 'barb' - it's production data.
        """
        if db == 'barb':
            # Never run migrations on BARB database
            return False

        # Run migrations on default database
        return True
