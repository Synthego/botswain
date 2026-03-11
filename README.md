# Botswain - Natural Language Factory Query Assistant

Botswain is a Django-based microservice that enables natural language queries across multiple data sources using LLM-powered intent parsing and a semantic layer for safe query execution.

## 🌟 Features

- **Natural Language Interface**: Ask questions in plain English across 11+ data sources
- **Multi-Database Support**: Query BARB (factory operations), Buckaneer (e-commerce), NetSuite, AWS infrastructure
- **Redis Caching**: 99%+ faster repeat queries with intelligent per-entity TTL configuration
- **Command-Line Interface**: Interactive CLI for quick queries with cache indicators
- **AWS Bedrock Integration**: Production-ready LLM integration using Claude Sonnet 4.5
- **Multi-Entity Queries**: Automatically combine data from multiple sources in a single query
- **Cost Tracking**: Automatic token usage and cost tracking for all queries
- **Semantic Layer**: Safe, validated queries with automatic intent parsing
- **Audit Logging**: Complete audit trail with token usage metrics
- **REST API**: HTTP endpoint for integration with other services
- **Query Result Pagination**: Comprehensive pagination support with smart estimation (no COUNT queries)
- **Cross-System Correlation**: Link factory operations, orders, infrastructure, and code changes

## 📊 Supported Data Sources

Botswain provides unified natural language access to 11 different data sources:

| Data Source | Description | Examples |
|-------------|-------------|----------|
| **Synthesizers** | RNA/DNA synthesis instruments (BARB) | "Show me available synthesizers", "Which SSA is offline?" |
| **Instruments** | All lab instruments (BARB) | "List Hamilton instruments in Fremont", "Show offline instruments" |
| **Workflows** | Production workflows and work orders (BARB) | "Show workflows from last 30 days", "Find work order 578630" |
| **Orders** | E-commerce orders (Buckaneer) | "Show recent orders", "Orders shipped this week" |
| **NetSuite Orders** | NetSuite sales orders (cached in Buckaneer) | "Show unfulfilled NetSuite orders", "Orders for customer ABC Corp" |
| **GitHub Issues** | Issues and PRs across Synthego repos | "My open issues", "Show barb PRs", "Issues assigned to dana" |
| **Git Commits** | Commit history across repos | "My recent commits", "Commits about midscale", "Changes in barb last week" |
| **Instrument Logs** | Lab instrument logs (ElasticSearch) | "SSA errors today", "Hamilton logs for plate ABC123", "Synthesis 578630" |
| **Service Logs** | Application logs (CloudWatch) | "BARB errors today", "Buckaneer 500 errors", "Celery task failures" |
| **ECS Services** | Container service status (AWS) | "Is BARB running?", "Show production services", "BARB worker status" |
| **RDS Databases** | Database operational status (AWS) | "Is BARB database available?", "Show BARB replicas", "Database connections" |
## 🏗️ Architecture

User Question
    ↓
AWS Bedrock (Claude Sonnet 4.5)
    ↓
Intent Parser → Structured JSON
    ↓
Query Planner (detects multi-entity queries)
    ↓
Safety Validator
    ↓
Redis Cache Check (per-entity TTL: 30s - 1hr)
    ↓ (cache miss)
Query Executor → Entity Registry
    ↓                    ↓
Multi-Database Access:  External APIs:
- BARB (factory)       - GitHub CLI (issues, commits)
- Buckaneer (orders)   - AWS Bedrock (LLM)
- NetSuite (cached)    - ElasticSearch (instrument logs)
                       - CloudWatch (service logs)
                       - AWS ECS/RDS (infrastructure)
    ↓
Cache Result → Redis (with TTL)
    ↓
LLM Response Formatter
    ↓
Natural Language Response + Audit Log

### Multi-Database Architecture

Botswain uses Django's multi-database routing to safely query multiple data sources:

- **`default`**: Botswain's own database (SQLite/PostgreSQL) for audit logs
- **`barb`**: BARB production read-replica (factory operations, instruments, workflows)
- **`buckaneer`**: Buckaneer production database (e-commerce orders, NetSuite cache)

All database access is **READ-ONLY** via dedicated read-only users or read replicas.

## 🚀 Quick Start

### Prerequisites
- Redis (optional, for caching - dramatically improves performance)

- Python 3.9+
- AWS credentials configured (for Bedrock, CloudWatch, ECS, RDS queries)
- VPN access (for production database and ElasticSearch queries)
- GitHub CLI installed (for GitHub issue/commit queries)

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/Synthego/botswain.git
cd botswain

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

3. **Install dependencies:**
```bash
pip install -r requirements.txt

4. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env and add your credentials (see Configuration section)

5. **Run migrations:**
```bash
python manage.py migrate

6. **Start development server:**
```bash
python manage.py runserver --settings=botswain.settings.barb_prod_replica 8002

7. **Test the API:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What synthesizers are available?"}'

## ⚙️ Configuration

### Required Environment Variables

**Production Database Credentials** (see `.env.example`):
```bash
# BARB Production Read-Replica
BARB_READONLY_PASSWORD=your_password_here

# Buckaneer Production Database
BUCKANEER_PASSWORD=your_password_here

# AWS Bedrock (uses AWS credentials from aws configure or env vars)
AWS_REGION=us-west-2
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

**⚠️ SECURITY**: Never commit `.env` to git. It contains production credentials.

### Settings Modules

Choose the appropriate settings module based on your use case:

| Settings Module | Use Case | Databases |
|-----------------|----------|-----------|
| `botswain.settings.local` | Local development/testing | SQLite only |
| `botswain.settings.barb_local` | BARB local database | SQLite + local BARB |
| `botswain.settings.barb_prod_replica` | **Production queries** (recommended) | SQLite + BARB replica + Buckaneer |
| `botswain.settings.multi_source` | Multi-database development | All databases |

**Recommended for production queries:**
```bash
python manage.py runserver --settings=botswain.settings.barb_prod_replica 8002

### AWS Configuration

Botswain requires AWS credentials for:
- **Bedrock**: LLM queries (Claude Sonnet 4.5)
- **CloudWatch Logs**: Service log queries
- **ECS**: Container service status
- **RDS**: Database operational status

Configure via AWS CLI or environment variables:
```bash
# Option 1: AWS CLI (recommended)
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-west-2

### Redis Caching

Botswain uses Redis for query result caching, providing 99%+ performance improvement for repeat queries.

**Start Redis (Docker):**
```bash
docker run -d --name botswain-redis -p 6379:6379 redis:7-alpine

**Configure in `.env`:**
```bash
REDIS_URL=redis://localhost:6379/0

**Per-Entity TTL Configuration:**
- **Real-time data** (30-60s): Synthesizers, Instruments, Workflows, ECS Services
- **Semi-static data** (5-10min): Orders, NetSuite Orders, GitHub Issues, RDS Databases
- **Historical data** (1hr): Git Commits

**Cache Controls:**
```bash
# Use cache (default)
./botswain-cli.py "Show my commits"

# Bypass cache (force fresh data)
./botswain-cli.py "Show my commits" --no-cache

# HTTP header bypass
curl -H "X-Botswain-Cache-Bypass: 1" http://localhost:8002/api/query
```

**Cache indicators in CLI:**
```
Cache:          ✓ Cached result  (when data from Redis)
Execution Time: 2ms              (vs 1250ms uncached)
```

See `CACHING.md` for detailed documentation including cache invalidation, monitoring, and troubleshooting.

## 📖 Usage Examples

### Single-Entity Queries

```bash
# Factory operations (BARB)
curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "Show me available synthesizers"}'

curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "Show workflows from last 30 days"}'

# E-commerce (Buckaneer)
curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "Show recent orders"}'

# NetSuite (Buckaneer cache)
curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "Show unfulfilled NetSuite orders"}'

# GitHub
curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "My open issues"}'

# Instrument logs (ElasticSearch)
curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "SSA errors today"}'

# Service logs (CloudWatch)
curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "BARB errors in the last hour"}'

# Infrastructure (AWS)
curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "Is BARB running?"}'

### Multi-Entity Queries

Botswain automatically detects when a question requires data from multiple sources and executes parallel queries with intelligent synthesis:

```bash
# Factory + E-commerce correlation
curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "Show me offline synthesizers and recent orders"}'

# NetSuite + E-commerce cross-reference
curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "Show me NetSuite orders for EditCo"}'

# Infrastructure + Logs correlation
curl -X POST http://localhost:8002/api/query -H "Content-Type: application/json" \
  -d '{"question": "Show me BARB service status and recent errors"}'

### CLI Usage

```bash
# Basic query
./botswain-cli.py "What synthesizers are available?"

# Multi-entity query
./botswain-cli.py "Show me offline synthesizers and recent orders"

# JSON output
./botswain-cli.py "Show workflows from last week" --format json

# Debug mode
./botswain-cli.py "Show BARB errors today" --debug

## 📄 Query Result Pagination

Botswain supports comprehensive pagination for navigating large result sets efficiently.

### Dual Parameter Support

**Page-based (user-friendly):**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders",
    "page": 2,
    "page_size": 50
  }'
```

**Offset-based (developer-friendly):**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders",
    "offset": 50,
    "limit": 50
  }'
```

**Priority:** If both styles are provided, `offset`/`limit` takes precedence.

### Smart Estimation

Botswain uses the **limit+1 trick** instead of expensive COUNT queries:
- Fetches `limit + 1` results to detect if more exist
- Provides "at least N results" estimates: `"100+"`
- Shows exact totals on the last page: `125`
- Works with all data sources (SQL, APIs, logs, GitHub)
- **Performance:** Single query, no COUNT overhead

### Pagination Metadata

Every paginated response includes comprehensive metadata:

```json
{
  "question": "Show orders",
  "response": "Found 245 orders (showing results 51-100)",
  "results": [...],
  "count": 50,
  "pagination": {
    "current_page": 2,
    "page_size": 50,
    "offset": 50,
    "limit": 50,
    "has_next": true,
    "has_previous": true,
    "next_page": 3,
    "previous_page": 1,
    "next_offset": 100,
    "previous_offset": 0,
    "estimated_total": "100+",
    "estimated_total_pages": "3+"
  }
}
```

### Caching with Pagination

- Each page is cached independently
- Cache key includes `offset` and `limit`
- `page=1, page_size=50` and `offset=0, limit=50` → same cache entry
- Cache TTL remains per-entity (30s - 1hr)

### Defaults

When no pagination parameters are provided:
- **Page:** 1 (or `offset=0`)
- **Page size / Limit:** 100
- **Maximum:** 1000 results per page

### Complete Documentation

See design document: `docs/plans/2026-03-11-pagination-design.md`

## 🔍 Query Capabilities by Entity

### Synthesizers (BARB)
**Filters**: `status`, `available`, `barcode`
"Show available synthesizers"
"Which SSA is offline?"
"Show synthesizer 1717"

### Instruments (BARB)
**Filters**: `status`, `factory`, `barcode`, `instrument_type`, `type`
"List Hamilton instruments in Fremont"
"Show offline instruments"
"All Tecan instruments"

### Workflows (BARB)
**Filters**: `status`, `template`, `template_name`, `work_order_id`, `workflow_id`, `created_after`, `created_before`
"Show workflows from last 30 days"
"Find work order 578630"
"RNA synthesis workflows this week"

### Orders (Buckaneer)
**Filters**: `status`, `factory`, `bigcommerce_id`, `order_id`, `created_after`, `created_before`, `email`
"Show recent orders"
"Orders shipped this week"
"Orders for dana@synthego.com"

### NetSuite Orders (Buckaneer)
**Filters**: `order_id`, `external_id`, `internal_id`, `netsuite_id`, `status`, `customer`, `customer_name`, `since`, `until`
"Show unfulfilled NetSuite orders"
"NetSuite orders for ABC Corp"
"Orders invoiced in the last week"

### GitHub Issues
**Filters**: `state`, `label`, `assignee`, `author`, `mention`, `type`, `created_after`, `updated_after`, `search`, `repo`
"My open issues"
"Show barb PRs"
"Issues assigned to dana"
"Issues with bug label in buckaneer"

### Git Commits
**Filters**: `author`, `since`, `until`, `search`, `message`, `branch`, `repo`
"My recent commits"
"Commits about midscale"
"Changes in barb last week"

### Instrument Logs (ElasticSearch)
**Filters**: `instrument_type`, `module_name`, `synthesizer`, `instrument`, `level`, `tags`, `synthesis_id`, `workorder_id`, `plate_barcode`, `search`, `since`, `until`
**Requires**: VPN connection
"SSA errors today"
"Hamilton logs for plate ABC123"
"Logs for synthesis 578630"
"Tecan operations this week"

### Service Logs (CloudWatch)
**Filters**: `service`, `environment`, `level`, `role`, `search`, `since`, `until`
**Retention**: 30 days (prod), 14 days (stage), 7 days (qa/dev)
"BARB errors today"
"Buckaneer 500 errors in the last hour"
"Celery task failures this week"

### ECS Services (AWS)
**Filters**: `service`, `environment`, `role`, `status`, `cluster`
"Is BARB running?"
"Show production services"
"What's the status of BARB workers?"

### RDS Databases (AWS)
**Filters**: `database`, `service`, `environment`, `status`, `replica`, `include_metrics`
"Is BARB database available?"
"Show all production databases"
"Show BARB read replicas"

## 💰 Cost Tracking

Botswain automatically tracks token usage and costs for all queries.

### Generate Cost Report

```bash
# All-time token usage report
python manage.py token_usage_report

# Report for specific date range
python manage.py token_usage_report --start-date 2026-03-01 --end-date 2026-03-10

# Filter by user
python manage.py token_usage_report --user dana

**Sample Output:**
Token Usage Report
Date Range: 2026-03-01 to 2026-03-10
Total Queries: 1,247

Token Usage:
  Input Tokens:       245,892
  Output Tokens:      178,543
  Total Tokens:       424,435

Estimated Costs:
  Input Cost:         $0.74
  Output Cost:        $2.68
  Total Cost:         $3.42

Average per Query:
  Tokens:             340
  Cost:               $0.003

### Pricing (Claude Sonnet 4.5 via Bedrock)
- Input: $3.00 per million tokens
- Output: $15.00 per million tokens

## 🗂️ Project Structure

botswain/
├── api/                           # REST API endpoints
│   ├── views.py                  # QueryAPIView endpoint
│   └── serializers.py            # Request/response serializers
├── core/                          # Core business logic
│   ├── llm/                      # LLM provider abstraction
│   │   ├── bedrock.py           # AWS Bedrock provider (default)
│   │   ├── claude_cli.py        # Claude CLI provider (legacy)
│   │   └── factory.py           # Provider factory
│   ├── semantic_layer/           # Entity definitions
│   │   ├── entities/
│   │   │   ├── synthesizer.py           # BARB synthesizers
│   │   │   ├── instrument_barb.py       # BARB instruments
│   │   │   ├── workflow_barb.py         # BARB workflows
│   │   │   ├── order_buckaneer.py       # Buckaneer orders
│   │   │   ├── netsuite_orders.py       # NetSuite orders (Buckaneer cache)
│   │   │   ├── github_issues.py         # GitHub issues/PRs
│   │   │   ├── git_commits.py           # Git commit history
│   │   │   ├── instrument_logs.py       # ElasticSearch instrument logs
│   │   │   ├── service_logs.py          # CloudWatch service logs
│   │   │   ├── ecs_services.py          # AWS ECS services
│   │   │   └── rds_databases.py         # AWS RDS databases
│   │   ├── base.py              # BaseEntity abstract class
│   │   └── registry.py          # Entity registry
│   ├── models.py                 # Django models (QueryLog, etc.)
│   ├── cache.py                   # Redis caching with per-entity TTL
│   ├── audit.py                  # Audit logging
│   ├── query_executor.py         # Query execution engine
│   ├── query_planner.py          # Multi-entity query orchestration
│   ├── query_recovery.py         # Automatic query error recovery
│   └── safety.py                 # Safety validation
├── botswain/                      # Django project settings
│   ├── settings/
│   │   ├── base.py              # Shared settings
│   │   ├── local.py             # Local development
│   │   ├── barb_local.py        # BARB local database
│   │   ├── barb_prod_replica.py # Production (recommended)
│   │   └── multi_source.py      # Multi-database development
│   ├── db_router.py             # Database routing logic
│   └── urls.py                  # URL configuration
├── data_sources/                  # Unmanaged BARB models
│   └── barb/
│       └── models.py             # Unmanaged BARB Django models
├── tests/                         # Test suite
├── botswain-cli.py               # Command-line interface
├── .env.example                  # Environment variable template
├── requirements.txt              # Python dependencies
└── README.md                     # This file

## 🔒 Security

### Read-Only Enforcement - Defense in Depth

Botswain implements a **3-layer security architecture** to guarantee read-only operations:

**Layer 1: LLM Constraints**
- System prompts explicitly forbid write operations
- LLM trained to reject modification requests
- Post-generation intent validation (whitelist: query, count, aggregate only)

**Layer 2: SQL Validation**
- All raw SQL statements validated before execution
- Whitelist approach: Only SELECT statements allowed
- Blocks dangerous keywords (INSERT, UPDATE, DELETE, DROP, ALTER, etc.)

**Layer 3: Database Access Control**
- Read-only database users (`readonlyuser`)
- BARB production read-replica (not primary)
- Database router blocks write operations

**Why Defense-in-Depth?**
Each layer independently prevents writes. If one layer is bypassed (e.g., LLM jailbreak, SQL injection), the other layers still protect the database.

See `SECURITY.md` for complete security documentation, threat model, and attack scenario testing.

### Credential Management

**✅ DO:**
- Use environment variables for all credentials
- Keep `.env` file out of git (already in `.gitignore`)
- Use read-only database users
- Use BARB production read-replica (not primary)
- Rotate credentials if exposed

**❌ DON'T:**
- Commit credentials to git
- Share `.env` files
- Use write-capable database users
- Hardcode passwords in settings files

### Access Controls

- **Database Access**: All connections are READ-ONLY
  - BARB: Uses `readonlyuser` on read-replica
  - Buckaneer: Uses `buckaneer` user with read-only permissions (enforced by router)
- **SQL Injection Protection**: Dangerous patterns blocked (DROP, DELETE, INSERT, UPDATE, etc.)
- **Query Limits**: Maximum 100-1000 results per query (configurable)
- **Input Validation**: All inputs validated through Django serializers
- **Audit Trail**: All queries logged with user, intent, and execution details

### Network Requirements

- **VPN**: Required for ElasticSearch (instrument logs) and production databases
- **AWS**: Requires valid credentials for Bedrock, CloudWatch, ECS, RDS
- **GitHub**: Requires GitHub CLI configured (`gh auth login`)

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=api --cov-report=html

# Run specific test file
pytest tests/test_query_executor.py

# Run with verbose output
pytest -v

## 🚢 Deployment

### Production Checklist

- [ ] Set `DEBUG=False` in settings
- [ ] Change `AllowAny` to `IsAuthenticated` in `api/views.py`
- [ ] Configure `DJANGO_SECRET_KEY` environment variable
- [ ] Set `ALLOWED_HOSTS` for your domain
- [ ] Use PostgreSQL for default database (not SQLite)
- [ ] Enable HTTPS and configure CSRF settings
- [ ] Set up monitoring (Django admin, QueryLog model)
- [ ] Configure AWS IAM roles with least privilege
- [ ] Set up cost alerts for AWS Bedrock usage
- [ ] Review and adjust token limits
- [ ] Configure log retention policies
- [ ] Set up backup strategy for audit logs
- [ ] Document incident response procedures

### Environment Variables for Production

```bash
# Django
DEBUG=False
DJANGO_SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=botswain.yourdomain.com

# Databases
BARB_READONLY_PASSWORD=your-production-password
BUCKANEER_PASSWORD=your-production-password

# AWS
AWS_REGION=us-west-2
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

## 🐛 Troubleshooting

### Common Issues

**"Access denied" errors for AWS:**
- Run `aws configure` to set up credentials
- Verify Bedrock access in AWS console
- Check IAM permissions for CloudWatch, ECS, RDS
- Use inference profile IDs with `us.` prefix

**"Connection refused" to databases:**
- Verify VPN connection for production databases
- Check `.env` file has correct passwords
- Verify database hosts are reachable
- Check firewall rules

**"No results" for queries:**
- Check VPN connection (required for ElasticSearch, production DBs)
- Verify AWS credentials (`aws sts get-caller-identity`)
- Check CloudWatch Logs retention (prod: 30 days, stage: 14 days, qa/dev: 7 days)
- Review audit logs in Django admin

**GitHub queries failing:**
- Run `gh auth login` to authenticate
- Verify repository access permissions
- Check GitHub CLI version: `gh --version`

**High AWS costs:**
- Run `python manage.py token_usage_report` to analyze usage
- Consider using Claude Haiku 3.5 for simpler queries
- Adjust `BEDROCK_MAX_INTENT_TOKENS` and `BEDROCK_MAX_RESPONSE_TOKENS`
- Enable Redis caching (see CACHING.md)

### Getting Help

- Check application logs: Django admin → Core → Query logs
- Review audit logs for query patterns
- Contact Data Analytics team
- Create issue in GitHub repository

## 📋 Roadmap

**Completed:**
- [x] AWS Bedrock integration with Claude Sonnet 4.5
- [x] Multi-database support (BARB, Buckaneer)
- [x] NetSuite orders datasource
- [x] GitHub issues and commits integration
- [x] ElasticSearch instrument logs
- [x] CloudWatch service logs
- [x] AWS infrastructure queries (ECS, RDS)
- [x] Multi-entity query orchestration
- [x] Token usage and cost tracking
- [x] Automatic query recovery
- [x] Environment variable credential management
- [x] Redis caching with per-entity TTL (30s - 1hr)
- [x] Query result pagination with smart estimation
- [ ] Slack integration

**Planned:**
- [ ] Web-based query interface
- [ ] Query history and favorites
- [ ] User authentication and RBAC
- [ ] Custom entity creation via API
- [ ] Real-time query subscriptions
- [ ] Advanced analytics dashboards
- [ ] Query performance optimization
- [ ] Additional AWS services (Lambda, S3, etc.)

## 📄 License

Internal Synthego project - see company policies for usage guidelines.

## 🤝 Support

For issues or questions:
- **Email**: Data Analytics team
- **GitHub Issues**: https://github.com/Synthego/botswain/issues
- **Slack**: #data-analytics channel

## 🙏 Acknowledgments

Built with:
- Django 4.2
- AWS Bedrock (Claude Sonnet 4.5)
- PostgreSQL
- ElasticSearch
- GitHub CLI
- AWS SDK (boto3)
- Redis
