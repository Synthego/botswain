# Botswain - Natural Language Factory Query Assistant

Botswain is a Django-based microservice that enables natural language queries against factory systems using LLM-powered intent parsing and a semantic layer for safe query execution.

## Features

- **Natural Language Interface**: Ask questions in plain English (e.g., "What synthesizers are available?")
- **LLM Provider Abstraction**: Pluggable LLM providers (currently supports Claude CLI)
- **Semantic Layer**: Safe, validated queries against BARB database entities
- **Audit Logging**: Complete audit trail of all queries
- **REST API**: HTTP endpoint for integration with other services
- **Docker Support**: Containerized deployment with PostgreSQL and Redis

## Architecture

```
User Question
    ↓
LLM Provider (Claude CLI)
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
Audit Logger
```

## Quick Start

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

## Configuration

Configuration is managed through Django settings modules:

- `botswain.settings.base` - Shared settings
- `botswain.settings.local` - Local development (DEBUG=True, SQLite for tests)
- `botswain.settings.test` - Testing configuration

Environment variables:
- `DJANGO_SECRET_KEY` - Django secret key
- `POSTGRES_DB/USER/PASSWORD/HOST/PORT` - Database configuration
- `REDIS_URL` - Redis connection string
- `BOTSWAIN_LLM_PROVIDER` - LLM provider to use (default: claude_cli)

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=core --cov=api --cov-report=html
```

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
├── Dockerfile             # Docker image definition
├── docker-compose.yml     # Multi-container setup
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

## Deployment

### Production Considerations

1. **Change permission classes** in `api/views.py` from `AllowAny` to `IsAuthenticated`
2. **Set DEBUG=False** in production settings
3. **Use proper secret key** via `DJANGO_SECRET_KEY` environment variable
4. **Configure ALLOWED_HOSTS** for your domain
5. **Use production-grade database** (PostgreSQL)
6. **Enable HTTPS** and configure CSRF settings
7. **Set up monitoring** using Django admin and QueryLog model

### Docker Production

Update `docker-compose.yml`:
- Use production Django settings
- Set strong database passwords
- Remove volume mounts for code
- Use environment file for secrets
- Configure reverse proxy (nginx/traefik)

## Roadmap

- [ ] Add more entities (WorkOrder, Inventory, Locations)
- [ ] Implement Redis caching for frequent queries
- [ ] Add Slack integration
- [ ] Support additional LLM providers (Claude API, OpenAI)
- [ ] Add query result pagination
- [ ] Implement query history and favorites
- [ ] Add user authentication and permissions
- [ ] Create web-based query interface

## License

Internal Synthego project - see company policies for usage guidelines.

## Support

For issues or questions, contact the Data Analytics team or create an issue in the project repository.
