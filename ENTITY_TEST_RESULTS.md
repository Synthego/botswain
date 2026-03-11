# Botswain Entity Test Results

## Test Summary

Comprehensive testing of Kraken Workflows and SOS Sequencing entities without requiring production database access.

**Date**: 2026-03-11
**Commit**: 3656a94 (fix: add missing datetime imports)

---

## Test Coverage

### Structure Tests (`test_entities_structure.py`)

Validates entity attributes, filter validation, and basic structure:

| Entity | Name | Attributes | Filter Validation | Status |
|--------|------|------------|-------------------|--------|
| Kraken Workflows | `kraken_workflow` | 18 attributes | ✅ Valid/Invalid | ✅ PASS |
| SOS Sequencing | `sos_sequencing` | 41 attributes | ✅ Valid/Invalid | ✅ PASS |

**Key Validations**:
- ✅ Entity names and descriptions defined
- ✅ Attribute lists complete and documented
- ✅ Filter validation accepts valid filters
- ✅ Filter validation rejects malicious/unknown filters

---

### SQL Generation Tests (`test_entities_sql.py`)

Tests SQL query generation logic with mocked database connections:

#### Kraken Workflows (4 query types)

| Query Type | Method | Parameters | Status |
|------------|--------|------------|--------|
| `running` | `_get_running_workflows()` | - | ✅ PASS |
| `failed` | `_get_failed_workflows()` | `hours_ago` | ✅ PASS |
| `status` | `_get_workflow_status()` | `workflow_name`, `hours_ago` | ✅ PASS |
| `statistics` | `_get_workflow_statistics()` | `workflow_name`, `days_ago` | ✅ PASS |

**Validated**:
- ✅ SQL query structure correct
- ✅ Parameter handling (time windows, workflow names)
- ✅ Returns list of dictionaries
- ✅ Date filtering logic works

#### SOS Sequencing (6 query types)

| Query Type | Method | Parameters | Status |
|------------|--------|------------|--------|
| `orders` | `_get_sequencing_orders()` | `hours_ago`, `status`, `sequencer`, `barcode` | ✅ PASS |
| `analysis` | `_get_analysis_results()` | `min_ice_score`, `max_ice_score`, `barcode` | ✅ PASS |
| `failed_orders` | `_get_failed_orders()` | `hours_ago` | ✅ PASS |
| `failed_analysis` | `_get_failed_analysis()` | `hours_ago` | ✅ PASS |
| `quality` | `_get_quality_metrics()` | `hours_ago` | ✅ PASS |
| `work_order` | `_get_orders_by_work_order()` | `work_order_reference` | ✅ PASS |

**Validated**:
- ✅ SQL query structure correct
- ✅ Complex filter handling (ICE scores, quality metrics)
- ✅ Aggregation logic (quality metrics, success rates)
- ✅ Work order reference lookups
- ✅ Date filtering and time windows

---

### Integration Tests

| Test | Description | Status |
|------|-------------|--------|
| Entity Registration | Both entities register in EntityRegistry | ✅ PASS |
| Entity Descriptions | LLM-readable descriptions available | ✅ PASS |
| Query Executor | Entities compatible with QueryExecutor | ✅ PASS |

---

## Example Query Intents

### Kraken Workflows

**Running workflows:**
```python
{
    'entity': 'kraken_workflow',
    'intent_type': 'query',
    'filters': {'query_type': 'running'},
    'limit': 10
}
```

**Failed workflows (last 24 hours):**
```python
{
    'entity': 'kraken_workflow',
    'intent_type': 'query',
    'filters': {'query_type': 'failed', 'hours_ago': 24},
    'limit': 10
}
```

**Workflow statistics:**
```python
{
    'entity': 'kraken_workflow',
    'intent_type': 'query',
    'filters': {'query_type': 'statistics', 'workflow_name': 'RNA', 'days_ago': 7},
    'limit': 10
}
```

### SOS Sequencing

**Recent sequencing orders:**
```python
{
    'entity': 'sos_sequencing',
    'intent_type': 'query',
    'filters': {'query_type': 'orders', 'hours_ago': 24},
    'limit': 10
}
```

**ICE analysis results (low scores):**
```python
{
    'entity': 'sos_sequencing',
    'intent_type': 'query',
    'filters': {'query_type': 'analysis', 'max_ice_score': 50},
    'limit': 10
}
```

**Work order sequencing status:**
```python
{
    'entity': 'sos_sequencing',
    'intent_type': 'query',
    'filters': {'query_type': 'work_order', 'work_order_reference': 'WO-12345'},
    'limit': 10
}
```

**Quality metrics (last 7 days):**
```python
{
    'entity': 'sos_sequencing',
    'intent_type': 'query',
    'filters': {'query_type': 'quality', 'hours_ago': 168},
    'limit': 1
}
```

---

## Natural Language Examples

These queries will work once database connections are available:

### Kraken Workflows

- "Show me running workflows"
- "Failed workflows in the last hour"
- "Workflow statistics for RNA synthesis"
- "Status of workflows for work order 578630"
- "Plating workflow statistics last 30 days"

### SOS Sequencing

- "Show me recent sequencing orders"
- "What's the sequencing status for WO-12345?"
- "Show me ICE analysis results below 50%"
- "Any failed sequencing today?"
- "What's the overall sequencing quality this week?"
- "Show me Sequetech orders from yesterday"
- "Analysis results for plate PLT-45678"

---

## Issues Fixed

1. **Missing datetime imports** (commit 3656a94)
   - Added `from datetime import datetime, timedelta` to both entities
   - Required for time filtering (`hours_ago`, `days_ago` parameters)

2. **Import statement in get_queryset()**
   - Imports moved inside methods to avoid circular dependencies
   - Pattern: `from django.db import connections` inside `get_queryset()`

---

## Database Connectivity

**Note**: These tests validate entity structure and SQL generation **without** requiring database access.

### Production Database Access

To test with live data, you need:

1. **VPN Connection**: Required for production RDS access
2. **Environment Variables**:
   ```bash
   KRAKEN_READONLY_PASSWORD=<password>
   SOS_READONLY_PASSWORD=<password>
   ```
3. **Settings Module**: Use `botswain.settings.barb_prod_replica`

### Database Hosts

Configured in `botswain/settings/barb_prod_replica.py`:

| Database | Host | Port | User |
|----------|------|------|------|
| Kraken | kraken-prod-pg-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com | 5432 | readonlyuser |
| SOS | sos-prod-pg-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com | 5432 | readonlyuser |

---

## Test Execution

Run tests locally:

```bash
# Activate virtual environment
source venv/bin/activate

# Structure tests
python test_entities_structure.py

# SQL generation tests
python test_entities_sql.py
```

**Expected Output**:
- ✅ All structure tests pass
- ✅ All SQL generation tests pass (with mocked connections)
- ✅ Entity registration tests pass

---

## Next Steps

1. **Connect via VPN** to test with live production data
2. **Run integration tests** with actual database queries
3. **Verify LLM intent parsing** for natural language queries
4. **Test multi-entity queries** combining Kraken + SOS data

---

## Summary

✅ **Kraken Workflows**: 4/4 query types validated
✅ **SOS Sequencing**: 6/6 query types validated
✅ **Entity Integration**: Registration and compatibility confirmed
✅ **Filter Validation**: Security checks working
✅ **SQL Generation**: All queries structured correctly

**Status**: Ready for production database testing via VPN.
