# Botswain - Natural Language Factory Query Assistant

Botswain is a Django-based microservice that enables natural language queries against factory systems using LLM-powered intent parsing and a semantic layer for safe query execution.

## Features

- **Natural Language Interface**: Ask questions in plain English (e.g., "What synthesizers are available?")
- **Command-Line Interface**: Interactive CLI for quick queries
- **AWS Bedrock Integration**: Production-ready LLM integration using Claude Sonnet 4.5 via AWS Bedrock
- **LLM Provider Abstraction**: Pluggable LLM providers (Bedrock, Claude CLI)
- **Cost Tracking**: Automatic token usage and cost tracking for all queries
- **Semantic Layer**: Safe, validated queries against BARB database entities
- **Audit Logging**: Complete audit trail of all queries with token usage metrics
- **REST API**: HTTP endpoint for integration with other services
- **Docker Support**: Containerized deployment with PostgreSQL and Redis

## Architecture

```
User Question
    ↓
LLM Provider (AWS Bedrock / Claude CLI)
    ↓
Intent Parser → Structured JSON
    ↓
Safety Validator
    ↓
Query Executor → Entity Registry → BARB Models
    ↓
Results → LLM Formatter
    ↓
Natural Language Response
    ↓
Audit Logger (with token usage & cost tracking)
```

## Quick Start

### Prerequisites

- Python 3.9+
- Django 4.2+
- Docker & Docker Compose (for containerized deployment)
- AWS Account with Bedrock access (for LLM integration)
- AWS credentials configured (via `aws configure` or environment variables)

### Using Docker (Recommended)

1. **Start services:**
```bash
docker-compose up -d
```

2. **Run migrations:**
```bash
docker-compose exec web python manage.py migrate
```

3. **Test the API:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What synthesizers are available?"}'
```

### Local Development

1. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure settings:**
```bash
export DJANGO_SETTINGS_MODULE=botswain.settings.local
```

4. **Run migrations:**
```bash
python manage.py migrate
```

5. **Start development server:**
```bash
python manage.py runserver 8002
```

## API Usage

### POST /api/query

Submit a natural language query.

**Request:**
```json
{
  "question": "What synthesizers are available?",
  "format": "natural",
  "use_cache": true
}
```

**Response:**
```json
{
  "question": "What synthesizers are available?",
  "response": "Found 3 synthesizers online: Synth-01, Synth-02, Synth-03",
  "intent": {
    "entity": "synthesizer",
    "intent_type": "query",
    "filters": {"status": "ONLINE"}
  },
  "results": {
    "success": true,
    "entity": "synthesizer",
    "results": [...],
    "count": 3,
    "execution_time_ms": 45
  },
  "cached": false
}
```

## CLI Usage

Botswain includes a command-line interface for interactive queries.

### Basic Usage

```bash
./botswain-cli.py "What synthesizers are available?"
```

### Options

```bash
./botswain-cli.py "QUESTION" [OPTIONS]

Options:
  --format {natural,json,table}  Response format (default: natural)
  --url URL                      API base URL (default: http://localhost:8002)
  --no-cache                     Disable query caching
  --raw                          Show raw JSON response
  --debug                        Show debug information
  -h, --help                     Show help message
```

### Examples

**Basic query:**
```bash
./botswain-cli.py "What synthesizers are available?"
```

**JSON format:**
```bash
./botswain-cli.py "Show me online instruments" --format json
```

**Debug mode:**
```bash
./botswain-cli.py "List all synthesizers" --debug
```

**Raw JSON output:**
```bash
./botswain-cli.py "What synthesizers are available?" --raw
```

**Connect to remote server:**
```bash
./botswain-cli.py "What synthesizers are available?" --url http://production:8002
```

### Example Output

```
📊 Query Results
============================================================

Found 3 synthesizers online: Synth-01, Synth-02, Synth-03

────────────────────────────────────────────────────────────
Entity:         synthesizer
Results Count:  3
Execution Time: 45ms
```

**Note:** The server must be running for the CLI to work. Start it with `make run` or `make docker-up`.

## Configuration

Configuration is managed through Django settings modules:

- `botswain.settings.base` - Shared settings
- `botswain.settings.local` - Local development (DEBUG=True, SQLite for tests)
- `botswain.settings.barb_local` - BARB local database connection
- `botswain.settings.barb_prod_replica` - BARB production replica (read-only)
- `botswain.settings.test` - Testing configuration

### Core Environment Variables

**Database:**
- `DJANGO_SECRET_KEY` - Django secret key
- `POSTGRES_DB/USER/PASSWORD/HOST/PORT` - Database configuration
- `REDIS_URL` - Redis connection string

**LLM Provider (AWS Bedrock - Default):**
```bash
# LLM Provider (default: bedrock)
LLM_PROVIDER=bedrock

# Bedrock Model (default: Claude Sonnet 4.5)
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Token Limits
BEDROCK_MAX_INTENT_TOKENS=500
BEDROCK_MAX_RESPONSE_TOKENS=1000

# AWS Configuration (uses default AWS credentials)
AWS_REGION=us-west-2
```

**Legacy Provider (Claude CLI):**
```bash
# Switch to Claude CLI provider
LLM_PROVIDER=claude_cli
```

### AWS Bedrock Setup

Botswain uses AWS Bedrock by default for production-grade LLM integration.

**Prerequisites:**
1. AWS account with Bedrock access
2. AWS credentials configured (via `aws configure` or environment variables)
3. Bedrock model access enabled (Claude Sonnet 4.5)

**Configuration:**
- Default model: `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (Claude Sonnet 4.5)
- Uses inference profile IDs with `us.` prefix for cross-region availability
- Automatic token tracking and cost estimation

**Available Models:**
- `us.anthropic.claude-sonnet-4-5-20250929-v1:0` - Claude Sonnet 4.5 (default, best quality)
- `us.anthropic.claude-3-5-haiku-20241022-v1:0` - Claude Haiku 3.5 (faster, lower cost)

### Switching LLM Providers

Change the `LLM_PROVIDER` environment variable:

```bash
# Use AWS Bedrock (default, recommended)
LLM_PROVIDER=bedrock

# Use Claude CLI (legacy, requires Claude CLI installed)
LLM_PROVIDER=claude_cli
```

**Note:** Bedrock is recommended for production use due to better reliability, cost tracking, and scalability.

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=core --cov=api --cov-report=html
```

## Cost Tracking

Botswain automatically tracks token usage and estimates costs for all queries when using AWS Bedrock.

### Generate Cost Report

View token usage and estimated costs across all queries:

```bash
# All-time token usage report
python manage.py token_usage_report

# Report for specific date range
python manage.py token_usage_report --start-date 2026-03-01 --end-date 2026-03-10

# Filter by user
python manage.py token_usage_report --user dana
```

**Sample Output:**
```
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
```

### Cost Tracking in QueryLog Model

All token usage is stored in the `QueryLog` model:

```python
from core.models import QueryLog

# Query token usage data
recent_queries = QueryLog.objects.filter(
    created_at__gte='2026-03-01'
).values('input_tokens', 'output_tokens', 'estimated_cost_usd')

# Calculate total costs
from django.db.models import Sum
total_cost = QueryLog.objects.aggregate(
    total_cost=Sum('estimated_cost_usd')
)
```

### Pricing (as of 2025)

AWS Bedrock Claude Sonnet 4.5 pricing:
- Input: $3.00 per million tokens
- Output: $15.00 per million tokens

**Note:** Actual costs may vary. Check AWS Bedrock pricing for current rates.

## Migrating from Claude CLI to Bedrock

If you were using the Claude CLI provider and want to migrate to AWS Bedrock:

### Step 1: Configure AWS Credentials

```bash
# Configure AWS CLI with your credentials
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-west-2
```

### Step 2: Update Environment Variables

```bash
# Change LLM provider to Bedrock
export LLM_PROVIDER=bedrock

# Optional: Specify model (defaults to Sonnet 4.5)
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### Step 3: Restart Botswain

```bash
# Using Docker
docker-compose restart

# Or using Makefile
make run
```

### Migration Benefits

- **Better Reliability**: AWS Bedrock provides production-grade uptime
- **Cost Tracking**: Automatic token usage and cost monitoring
- **No CLI Dependency**: No need to install or maintain Claude CLI
- **Scalability**: AWS handles scaling automatically
- **Consistent Performance**: Predictable response times

**Note:** No code changes required - the migration is seamless. All existing queries and data are preserved.

## Project Structure

```
botswain/
├── api/                    # REST API endpoints
├── core/                   # Core business logic
│   ├── llm/               # LLM provider abstraction
│   ├── semantic_layer/    # Entity definitions and registry
│   ├── models.py          # Django models (QueryLog)
│   ├── audit.py           # Audit logging
│   ├── query_executor.py  # Query execution engine
│   └── safety.py          # Safety validation
├── data_sources/          # Mock data sources
│   └── barb/              # Mock BARB models
├── botswain/              # Django project settings
├── tests/                 # Test suite
├── botswain-cli.py        # Command-line interface
├── Dockerfile             # Docker image definition
├── docker-compose.yml     # Multi-container setup
├── Makefile               # Development tooling
└── requirements.txt       # Python dependencies
```

## Entities

Currently supported entities:

- **synthesizer** - RNA/DNA synthesis instruments
  - Attributes: name, barcode, status, factory, location, instrument_type, host, port
  - Filters: status, factory, available, barcode

## Security

- **SQL Injection Protection**: Dangerous patterns blocked (DROP, DELETE, etc.)
- **Query Limits**: Maximum 1000 results per query
- **Input Validation**: All inputs validated through serializers
- **Audit Trail**: All queries logged with user, intent, and execution details

## Troubleshooting

### AWS Bedrock Issues

**"Access denied" errors:**
- Ensure AWS credentials are configured: `aws configure`
- Verify Bedrock access in your AWS account
- Check that model access is enabled in Bedrock console
- Verify you're using inference profile IDs with `us.` prefix

**"Model not found" errors:**
- Use inference profile IDs, not direct model IDs
- Correct: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
- Incorrect: `anthropic.claude-sonnet-4-5-20250929-v1:0`

**High costs:**
- Review token usage with: `python manage.py token_usage_report`
- Consider switching to Claude Haiku 3.5 for lower costs
- Adjust `BEDROCK_MAX_INTENT_TOKENS` and `BEDROCK_MAX_RESPONSE_TOKENS`

### General Issues

**"QueryLog has no column 'input_tokens'" error:**
- Run migrations: `python manage.py migrate`
- Migrations automatically add token tracking columns

**Queries failing:**
- Check LLM provider configuration: `echo $LLM_PROVIDER`
- Verify AWS credentials: `aws sts get-caller-identity`
- Check Django logs for detailed error messages

**Docker networking issues:**
- Ensure services are on `synthego-local` network
- Check `docker-compose.yml` network configuration

### Getting Help

For additional support:
- Check application logs: `docker-compose logs -f web`
- Review QueryLog in Django admin: http://localhost:8002/admin
- Contact the Data Analytics team

## Deployment

### Production Considerations

1. **Change permission classes** in `api/views.py` from `AllowAny` to `IsAuthenticated`
2. **Set DEBUG=False** in production settings
3. **Use proper secret key** via `DJANGO_SECRET_KEY` environment variable
4. **Configure ALLOWED_HOSTS** for your domain
5. **Use production-grade database** (PostgreSQL)
6. **Enable HTTPS** and configure CSRF settings
7. **Set up monitoring** using Django admin and QueryLog model
8. **Configure AWS Bedrock** with proper IAM roles and permissions
9. **Set up cost alerts** for AWS Bedrock usage
10. **Review token limits** (`BEDROCK_MAX_INTENT_TOKENS`, `BEDROCK_MAX_RESPONSE_TOKENS`)

### Docker Production

Update `docker-compose.yml`:
- Use production Django settings
- Set strong database passwords
- Remove volume mounts for code
- Use environment file for secrets
- Configure reverse proxy (nginx/traefik)

## Roadmap

**Completed:**
- [x] AWS Bedrock integration with Claude Sonnet 4.5
- [x] Token usage and cost tracking
- [x] LLM provider abstraction (Bedrock, Claude CLI)

**In Progress:**
- [ ] Add more entities (WorkOrder, Inventory, Locations)
- [ ] Implement Redis caching for frequent queries
- [ ] Add Slack integration

**Planned:**
- [ ] Support additional LLM providers (OpenAI, Anthropic API)
- [ ] Add query result pagination
- [ ] Implement query history and favorites
- [ ] Add user authentication and permissions
- [ ] Create web-based query interface
- [ ] Cost optimization and caching strategies

## License

Internal Synthego project - see company policies for usage guidelines.

## Support

For issues or questions, contact the Data Analytics team or create an issue in the project repository.
