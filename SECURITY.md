# Botswain Security Model

## Overview

Botswain is designed with security-first principles for querying sensitive production data across multiple sources.

## Data Source Access Controls

### BARB (Factory Operations)
- **Access**: READ-ONLY via PostgreSQL production read-replica
- **User**: `readonlyuser` with restricted permissions
- **Protection**:
  - Database router blocks all writes (`db_for_write` returns `None`)
  - PostgreSQL enforces read-only transactions
  - No migrations run on BARB database (`managed = False`)
- **Verification**: Writes fail at both application layer and database layer

### Buckaneer (E-commerce)
- **Access**: READ-ONLY via local PostgreSQL connection
- **Protection**:
  - Database router blocks all writes to Buckaneer tables
  - Table prefix matching prevents accidental writes
- **Current**: Local database (no production access yet)

### GitHub (Development)
- **Access**: READ-ONLY via GitHub CLI (`gh` command)
- **Protection**:
  - **Organization Restriction**: Only `Synthego/*` repositories allowed
  - Validation in `GitHubIssuesEntity._validate_repo()`
  - Non-Synthego repos return empty results
  - Only `gh issue list` and `gh pr list` commands used (read-only)
- **Git Operations**: Only read-only commands allowed:
  - `git remote get-url origin` (for repo detection)
  - No git write operations (`commit`, `push`, `add`, etc.)

## Query Safety

### SQL Injection Protection
- **File**: `core/safety.py`
- **Method**: Pattern matching for dangerous SQL keywords
- **Blocked Patterns**:
  - `DROP TABLE`, `DROP DATABASE`
  - `DELETE FROM`, `TRUNCATE TABLE`
  - `ALTER TABLE`, `INSERT INTO`, `UPDATE SET`
  - SQL comment injection (`--`, `;--`)
  - `UNION SELECT` attacks
  - Script injection (`<SCRIPT`, `JAVASCRIPT:`)

### Query Validation
- Each entity validates filters via `validate_filters()` method
- Only whitelisted filter keys accepted
- Invalid filters rejected before query execution

### Execution Limits
- **Max Results**: 1000 records per query (configurable)
- **Max Execution Time**: 30 seconds
- **Default Limit**: 10 records (override requires explicit confirmation)

## Database Routing Security

### Write Protection
**File**: `botswain/multi_db_router.py`

```python
def db_for_write(self, model, **hints):
    # BARB models - NEVER allow writes
    if is_barb_model:
        return None  # Causes write to fail

    # Buckaneer models - NEVER allow writes
    if is_buckaneer_model:
        return None

    # Only Botswain's own models can write
    return 'default'
```

### Migration Protection
```python
def allow_migrate(self, db, app_label, model_name=None, **hints):
    if db in ('barb', 'buckaneer'):
        return False  # Never run migrations on external databases
    return True
```

## GitHub Security

### Organization Restriction
**File**: `core/semantic_layer/entities/github_issues.py`

```python
ALLOWED_ORG = "Synthego"

def _validate_repo(self, repo: str) -> bool:
    if not repo or "/" not in repo:
        return False
    owner, _ = repo.split("/", 1)
    return owner == self.ALLOWED_ORG
```

### Read-Only Operations
- **Allowed**: `gh issue list`, `gh pr list` (with `--json` flag)
- **Blocked**: Any write operations to GitHub (create, update, close, comment)
- **Git Commands**: Only `git remote get-url origin` (read-only)

## Query Recovery

### LLM-Based Simplification
- **File**: `core/query_recovery.py`
- **Purpose**: Retry failed queries with simplified phrasing
- **Security**:
  - Only retries on recoverable errors
  - Does not bypass security checks
  - Simplified queries still validated

## Audit Logging

### All Queries Logged
- **File**: `core/audit.py`
- **Data Logged**:
  - User making request
  - Question asked
  - Intent parsed from LLM
  - Query results (count)
  - Execution time
  - LLM model and tokens used
- **Storage**: Local SQLite database
- **Purpose**: Security audit trail and cost tracking

## Network Security

### External Services
- **AWS Bedrock**: LLM inference (Sonnet 4.5, Haiku 3.5)
  - Uses AWS IAM credentials
  - No data stored by Bedrock
- **GitHub API**: Via `gh` CLI
  - Uses `GITHUB_TOKEN` from environment
  - Read-only scopes only

### No Outbound Writes
- Botswain never writes to external systems
- All operations are query/read-only
- No data modification capabilities

## Authentication

### Current Status (Development)
- **API**: `AllowAny` permission (no auth required)
- **TODO**: Change to `IsAuthenticated` in production
- **User Tracking**: Logs `anonymous` for unauthenticated requests

### Production Requirements
1. Enable Django authentication
2. Change `permission_classes = [IsAuthenticated]` in `api/views.py`
3. Implement user management (LDAP, OAuth, etc.)
4. Add per-user query quotas
5. Implement role-based access control

## Verification

### Testing Write Protection
```bash
# Test BARB write protection
venv/bin/python manage.py shell --settings=botswain.settings.barb_prod_replica
>>> from data_sources.barb.models import Instrument
>>> i = Instrument.objects.first()
>>> i.status = 'TEST'
>>> i.save()  # Should fail - no database route

# Test GitHub org restriction
./botswain-cli.py "show issues in torvalds/linux"
# Returns: 0 results (non-Synthego repo blocked)
```

### Security Checklist
- [x] Database writes blocked at application layer
- [x] Database writes blocked at database layer (read-only user)
- [x] GitHub restricted to Synthego org only
- [x] No git write operations in codebase
- [x] SQL injection protection enabled
- [x] Query results limited by default
- [x] All queries audited and logged
- [x] No external data writes

## Reporting Security Issues

If you discover a security vulnerability in Botswain:
1. Do not open a public issue
2. Contact security team directly
3. Provide details: affected component, reproduction steps, impact
4. Allow time for patching before disclosure
