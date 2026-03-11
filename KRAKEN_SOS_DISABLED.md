# Kraken and SOS Integrations - Currently Disabled

## Status: DISABLED

Kraken workflows and SOS sequencing integrations have been disabled due to database connectivity issues.

**Date Disabled**: 2026-03-11
**Reason**: Database hosts not accessible via VPN/AWS RDS

---

## Investigation Summary

### What We Found

**AWS Secrets Manager** contains credentials for both services:
- **Kraken**: `aws secretsmanager get-secret-value --secret-id kraken/prod`
  - User: `kraken`
  - Password: `KrrxPLz28vmIxi`
  - Database: `kraken`
  - Host: `kraken-prod-pg-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com`

- **SOS**: `aws secretsmanager get-secret-value --secret-id sos/prod`
  - User: `readonlyuser`
  - Password: `IhuaQZZ5r9Id`
  - Database: `sos`
  - Host: `sos-prod-pg-01.cb7xtwywa7y5.us-west-2.rds.amazonaws.com`

### Problem: Databases Not in AWS RDS

```bash
$ aws rds describe-db-instances | grep -E "kraken|sos"
(no results)

$ nslookup kraken-prod-pg-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com
** server can't find kraken-prod-pg-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com: NXDOMAIN
```

**Likely Infrastructure**:
- Kraken and SOS appear to run on internal `.ad.synthego.com` infrastructure
- Not accessible via standard VPN/AWS RDS endpoints
- May require different network configuration or on-premises access

---

## What Was Disabled

### 1. Database Configurations

**File**: `botswain/settings/barb_prod_replica.py`

```python
# DISABLED: Kraken and SOS databases not accessible
# 'kraken': { ... }
# 'sos': { ... }
```

### 2. Entity Registrations

**File**: `api/views.py`

```python
# DISABLED: Kraken and SOS integrations
# has_kraken = 'kraken' in settings.DATABASES
# if has_kraken:
#     from core.semantic_layer.entities.kraken_workflows import KrakenWorkflowEntity
#     registry.register(KrakenWorkflowEntity())
```

### 3. LLM Prompt Documentation

**File**: `core/llm/bedrock.py`

Removed filter documentation and query examples for:
- `kraken_workflow` entity (section 13)
- `sos_sequencing` entity (section 14)

---

## Entity Code Preserved

The entity implementation files are **still in place** and **tested**:

### Kraken Workflows Entity
- **File**: `core/semantic_layer/entities/kraken_workflows.py`
- **Tests**: `test_entities_structure.py`, `test_entities_sql.py`
- **Status**: ✅ Code validated, SQL generation tested
- **Query Types**: 4 (running, failed, status, statistics)

### SOS Sequencing Entity
- **File**: `core/semantic_layer/entities/sos_sequencing.py`
- **Tests**: `test_entities_structure.py`, `test_entities_sql.py`
- **Status**: ✅ Code validated, SQL generation tested
- **Query Types**: 6 (orders, analysis, failed_orders, failed_analysis, quality, work_order)

**Test Results**: See `ENTITY_TEST_RESULTS.md`

---

## How to Re-Enable

### Prerequisites

1. **Verify database access**:
   ```bash
   psql -h <kraken_host> -U kraken -d kraken -c "SELECT version();"
   psql -h <sos_host> -U readonlyuser -d sos -c "SELECT version();"
   ```

2. **Set environment variables**:
   ```bash
   export KRAKEN_DB_PASSWORD='KrrxPLz28vmIxi'
   export SOS_DB_READONLY_PASSWORD='IhuaQZZ5r9Id'
   ```

3. **Confirm network connectivity** (VPN profile, firewall rules, DNS resolution)

### Steps to Re-Enable

#### 1. Uncomment Database Configurations

**File**: `botswain/settings/barb_prod_replica.py`

```python
DATABASES = {
    # ... existing databases ...
    'kraken': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'kraken',
        'USER': 'kraken',
        'PASSWORD': os.environ.get('KRAKEN_DB_PASSWORD', ''),
        'HOST': '<verify_correct_hostname>',  # Check actual hostname
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 10,
        },
    },
    'sos': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'sos',
        'USER': 'readonlyuser',
        'PASSWORD': os.environ.get('SOS_DB_READONLY_PASSWORD', ''),
        'HOST': '<verify_correct_hostname>',  # Check actual hostname
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}
```

#### 2. Uncomment Entity Registrations

**File**: `api/views.py`

```python
# Check if we have Kraken database configured
has_kraken = 'kraken' in settings.DATABASES
if has_kraken:
    from core.semantic_layer.entities.kraken_workflows import KrakenWorkflowEntity
    registry.register(KrakenWorkflowEntity())

# Check if we have SOS database configured
has_sos = 'sos' in settings.DATABASES
if has_sos:
    from core.semantic_layer.entities.sos_sequencing import SOSSequencingEntity
    registry.register(SOSSequencingEntity())
```

#### 3. Add LLM Prompt Documentation

**File**: `core/llm/bedrock.py`

Add back to filter list:
```python
- kraken_workflow: query_type, workflow_name, work_order_id, hours_ago, days_ago, limit
- sos_sequencing: query_type, hours_ago, status, sequencer, barcode, workflow_id, callback_status, source_order_reference, work_order_reference, min_ice_score, max_ice_score, min_phred_percent, limit
```

Add back documentation sections (see git history for full text):
- Section 13: Kraken workflows
- Section 14: SOS sequencing

#### 4. Test Connectivity

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=botswain.settings.barb_prod_replica
export KRAKEN_DB_PASSWORD='...'
export SOS_DB_READONLY_PASSWORD='...'

python << 'EOF'
import django
django.setup()
from django.db import connections

# Test Kraken
with connections['kraken'].cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM workflow;")
    print(f"Kraken workflows: {cursor.fetchone()[0]}")

# Test SOS
with connections['sos'].cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM order_order;")
    print(f"SOS orders: {cursor.fetchone()[0]}")
EOF
```

---

## Alternative: Local Development Instances

If production databases remain inaccessible, consider:

1. **Docker Compose** local instances of Kraken/SOS
2. **Database dumps** restored to local PostgreSQL
3. **Mock data** for development/testing

---

## Current Working Entities

Botswain currently has **9 active datasources**:

1. **BARB (3 entities)**:
   - `synthesizer` - SSA synthesizer status
   - `instrument` - Lab instrument status
   - `workflow` - BARB workflow executions

2. **Buckaneer (2 entities)**:
   - `order` - Customer orders
   - `netsuite_order` - NetSuite order sync data

3. **GitHub (1 entity)**:
   - `github_issue` - GitHub issues and PRs

4. **Git (1 entity)**:
   - `git_commit` - Local git commit history

5. **AWS (2 entities)**:
   - `ecs_service` - ECS service status
   - `rds_database` - RDS database metrics

**Total**: 9 entities across 5 data sources

---

## References

- **Integration Guides**:
  - `BOTSWAIN_KRAKEN_INTEGRATION.md`
  - `BOTSWAIN_SOS_INTEGRATION.md`
- **Entity Code**:
  - `core/semantic_layer/entities/kraken_workflows.py`
  - `core/semantic_layer/entities/sos_sequencing.py`
- **Test Results**: `ENTITY_TEST_RESULTS.md`
- **Git Commits**:
  - 6933111 - Initial Kraken/SOS implementation
  - 3656a94 - Fixed datetime imports
  - (current) - Disabled due to connectivity issues
