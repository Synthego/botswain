# Connecting Botswain to Production BARB Data

This guide explains how to connect Botswain to your local BARB database to test with real production data.

## Prerequisites

1. **BARB must be running locally** with database on port 5434
2. **BARB database must have data** (instruments, etc.)

## Quick Start

### 1. Ensure BARB is Running

```bash
cd /home/danajanezic/code/barb
docker-compose up -d barb-db barb-web
```

Verify BARB database is accessible:
```bash
psql -h localhost -p 5434 -U barb -d barb_local -c "SELECT COUNT(*) FROM inventory_instrument;"
```

### 2. Start Botswain with BARB Settings

```bash
cd /home/danajanezic/code/.worktrees/botswain-implementation/botswain
source venv/bin/activate

# Use the BARB-specific settings
DJANGO_SETTINGS_MODULE=botswain.settings.barb_local python manage.py runserver 8002
```

### 3. Test with Real Data

```bash
# In another terminal
./botswain-cli.py "How many synthesizers are online?"
./botswain-cli.py "Show me all instruments"
./botswain-cli.py "What synthesizers are in Factory 1?"
```

## How It Works

### Settings Configuration

**botswain/settings/barb_local.py** configures:
- Database connection to `localhost:5434`
- Database name: `barb_local`
- User: `barb` (no password - trust auth)

### Entity Implementation

**Two SynthesizerEntity implementations:**

1. **synthesizer.py** - Mock data (for testing without BARB)
2. **synthesizer_barb.py** - Real BARB queries (uses raw SQL)

The API automatically selects the correct entity based on database settings.

### BARB Tables Queried

```sql
-- Main query in synthesizer_barb.py
SELECT
    i.barcode,
    i.name,
    i.status,
    i.host,
    i.port,
    it.name as instrument_type,
    f.name as factory,
    l.barcode as installation_location
FROM inventory_instrument i
JOIN inventory_instrument_type it ON i.instrument_type_id = it.id
LEFT JOIN factories_factory f ON i.factory_id = f.id
LEFT JOIN inventory_location l ON i.installation_location_id = l.id
WHERE it.name = 'Synthesizer'
```

## Testing with Different Environments

### Mock Data (SQLite)
```bash
DJANGO_SETTINGS_MODULE=botswain.settings.local python manage.py runserver 8002
```

### BARB Local (PostgreSQL)
```bash
DJANGO_SETTINGS_MODULE=botswain.settings.barb_local python manage.py runserver 8002
```

### BARB QA/Stage
Create `botswain/settings/barb_qa.py`:
```python
from .base import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'barb_qa',
        'USER': 'barb_qa_user',
        'PASSWORD': os.environ.get('BARB_QA_PASSWORD'),
        'HOST': 'barb-qa.synthego.com',
        'PORT': '5432',
    }
}
```

## Troubleshooting

### "Connection refused" on port 5434
BARB database is not running. Start it:
```bash
cd /home/danajanezic/code/barb
docker-compose up -d barb-db
```

### "relation 'inventory_instrument' does not exist"
You're connected to the wrong database or BARB migrations haven't run.

Check which database you're connected to:
```bash
psql -h localhost -p 5434 -U barb -d barb_local -c "\dt"
```

### "No synthesizers found"
BARB database might not have synthesizer instruments. Check:
```bash
psql -h localhost -p 5434 -U barb -d barb_local -c "
SELECT it.name, COUNT(*)
FROM inventory_instrument i
JOIN inventory_instrument_type it ON i.instrument_type_id = it.id
GROUP BY it.name;
"
```

### API returns mock data instead of BARB data
Check that you're using the correct settings module:
```bash
# Should show "barb_local"
DJANGO_SETTINGS_MODULE=botswain.settings.barb_local python -c "
from django.conf import settings
print(settings.DATABASES['default']['NAME'])
"
```

## Adding More Entities

To add new BARB entities (WorkOrder, Inventory, etc.):

1. Create `core/semantic_layer/entities/{entity}_barb.py`
2. Write SQL query against BARB tables
3. Register in `api/views.py`

Example for WorkOrder:
```python
# core/semantic_layer/entities/workorder_barb.py
class WorkOrderEntity(BaseEntity):
    name = "workorder"
    description = "Manufacturing work orders"

    def get_queryset(self, filters=None):
        query = """
            SELECT wo.barcode, wo.status, wo.created_date
            FROM work_orders_workorder wo
            WHERE 1=1
        """
        # Add filters...
        return execute_raw_sql(query)
```

## Security Notes

⚠️ **Important:**
- Botswain queries are **READ-ONLY** (SELECT statements only)
- Safety validator blocks INSERT/UPDATE/DELETE/DROP
- All queries are audit logged
- Use PostgreSQL read-only user in production

## Makefile Commands

Added convenience commands:

```bash
make run-barb          # Run with BARB settings
make test-barb         # Test against BARB database
make barb-shell        # Django shell with BARB access
```

Add these to your Makefile:
```makefile
run-barb: ## Run with BARB database connection
	DJANGO_SETTINGS_MODULE=botswain.settings.barb_local $(VENV_BIN)/python manage.py runserver 8002

barb-shell: ## Django shell connected to BARB
	DJANGO_SETTINGS_MODULE=botswain.settings.barb_local $(VENV_BIN)/python manage.py dbshell
```
