"""
Database router for multi-source setup.

Routes:
- BARB models -> 'barb' database (read-only production replica)
- Buckaneer models -> 'buckaneer' database (local, read-only)
- Botswain models -> 'default' database (local, read-write)
"""


class MultiSourceDatabaseRouter:
    """
    Route database operations for multiple data sources.

    - BARB: Production read-replica for factory data
    - Buckaneer: Local database for e-commerce data
    - Default: Botswain's own database for audit logs
    """

    # Database-specific table prefixes
    BARB_TABLE_PREFIXES = [
        'inventory_',
        'mcp_',
        'wip_',
        'factories_',
    ]

    BUCKANEER_TABLE_PREFIXES = [
        'order_',
        'voucher_',
        'userprofile_',
        'api_',
    ]

    # App labels for each database
    BARB_APP_LABELS = [
        'data_sources',  # When the models are in data_sources.barb
    ]

    BUCKANEER_APP_LABELS = [
        # Add if we create buckaneer-specific apps
    ]

    def db_for_read(self, model, **hints):
        """
        Route read operations based on model origin.
        """
        table_name = model._meta.db_table
        app_label = model._meta.app_label

        # Check BARB first
        if app_label in self.BARB_APP_LABELS:
            return 'barb'

        for prefix in self.BARB_TABLE_PREFIXES:
            if table_name.startswith(prefix):
                return 'barb'

        # Check Buckaneer
        if app_label in self.BUCKANEER_APP_LABELS:
            return 'buckaneer'

        for prefix in self.BUCKANEER_TABLE_PREFIXES:
            if table_name.startswith(prefix):
                return 'buckaneer'

        # Default to Botswain's own database
        return 'default'

    def db_for_write(self, model, **hints):
        """
        Route write operations.

        BARB and Buckaneer are READ-ONLY - no writes allowed.
        Only Botswain models can be written.
        """
        table_name = model._meta.db_table
        app_label = model._meta.app_label

        # Check BARB - never allow writes
        if app_label in self.BARB_APP_LABELS:
            return None

        for prefix in self.BARB_TABLE_PREFIXES:
            if table_name.startswith(prefix):
                return None

        # Check Buckaneer - never allow writes
        if app_label in self.BUCKANEER_APP_LABELS:
            return None

        for prefix in self.BUCKANEER_TABLE_PREFIXES:
            if table_name.startswith(prefix):
                return None

        # Allow writes to Botswain's own database
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between models in the same database.
        """
        db1 = self.db_for_read(obj1.__class__)
        db2 = self.db_for_read(obj2.__class__)

        if db1 == db2:
            return True

        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Only allow migrations on 'default' database.

        Never run migrations on BARB or Buckaneer - they're external databases.
        """
        if db in ('barb', 'buckaneer'):
            return False

        return True
