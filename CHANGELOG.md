# Changelog

All notable changes to the Botswain project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-03-10 - AWS Bedrock SDK Migration

### Added

**AWS Bedrock Integration**
- AWS Bedrock SDK integration via `anthropic[bedrock]==0.84.0`
- `BedrockProvider` class for direct API integration with AWS Bedrock
- Support for Claude Sonnet 4.5 and Claude Haiku 3.5 models
- Inference profile IDs with `us.` prefix for cross-region availability

**Token Usage Tracking**
- Automatic token counting for all queries (input, output, total)
- `input_tokens`, `output_tokens`, `total_tokens` fields in QueryLog model
- Token usage captured for both intent parsing and response formatting
- Backward-compatible nullable fields (existing records unaffected)

**Cost Monitoring**
- Real-time cost estimation in USD for all queries
- `estimated_cost_usd` field in QueryLog model (DecimalField with 6 decimal places)
- Cost calculation based on current AWS Bedrock pricing
- `core/utils/cost.py` module for cost calculation utilities

**Management Commands**
- `token_usage_report` command for analyzing token usage and costs
- Date range filtering: `--start-date` and `--end-date` options
- User filtering: `--user` option for per-user analysis
- Formatted output with thousands separators and currency formatting

**Configuration**
- Environment-based Bedrock configuration settings
- `BEDROCK_MODEL_ID` - Model selection (default: Sonnet 4.5)
- `BEDROCK_MAX_INTENT_TOKENS` - Token limit for intent parsing (default: 500)
- `BEDROCK_MAX_RESPONSE_TOKENS` - Token limit for responses (default: 1000)
- `BEDROCK_TIMEOUT` - API timeout in seconds (default: 30.0)
- `BEDROCK_AWS_REGION` - AWS region (default: us-west-2)

**Development Tools**
- Makefile commands for Bedrock and token reporting
  - `make run-bedrock` - Run with Bedrock provider
  - `make run-claude-cli` - Run with Claude CLI provider
  - `make check-bedrock` - Verify Bedrock configuration
  - `make show-provider` - Display current provider
  - `make token-report` - Generate all-time token usage report
  - `make token-report-today` - Today's token usage
  - `make token-report-week` - Past 7 days token usage
  - `make token-report-month` - Current month token usage

**Documentation**
- `docs/configuration.md` - Comprehensive configuration reference
- `MIGRATION_SUMMARY.md` - Complete migration documentation
- `DEPLOYMENT_GUIDE.md` - Production deployment guide
- `INTEGRATION_TEST_RESULTS.md` - Real API test results
- `TEST_SUITE_STATUS.md` - Test suite documentation
- Updated README.md with Bedrock integration guide

**Testing**
- 51 new tests across 6 test suites
- `tests/test_bedrock_provider.py` - BedrockProvider tests (6 tests)
- `tests/test_cost_calculation.py` - Cost calculation tests (9 tests)
- `tests/test_querylog_tokens.py` - Token field tests (5 tests)
- `tests/test_settings.py` - Configuration tests (14 tests)
- `tests/test_management_commands.py` - Command tests (7 tests)
- `tests/test_audit_cost_calculation.py` - Audit integration tests (3 tests)
- Integration testing with real AWS Bedrock API

### Changed

**Provider System**
- Default LLM provider changed from `ClaudeCLIProvider` to `BedrockProvider`
- `LLMProviderFactory` now supports environment-based provider selection
- `LLM_PROVIDER` environment variable controls provider choice (default: `bedrock`)

**API Layer**
- `api/views.py` updated to use factory pattern for provider selection
- API views now pass model ID to cost calculation for accurate pricing

**Audit System**
- `AuditLogger` enhanced with automatic token and cost capture
- Token usage and estimated costs logged for every query
- Error handling added for cost calculation failures

**Database Models**
- `QueryLog` model extended with 4 new fields:
  - `input_tokens` (PositiveIntegerField, nullable)
  - `output_tokens` (PositiveIntegerField, nullable)
  - `total_tokens` (PositiveIntegerField, nullable)
  - `estimated_cost_usd` (DecimalField, nullable)

**Documentation**
- README.md completely rewritten with Bedrock-first approach
- Added Bedrock troubleshooting section
- Added cost tracking and reporting documentation
- Updated quick start guide for Bedrock

**Dependencies**
- Added `anthropic[bedrock]==0.84.0` to requirements.txt
- Updated boto3 dependencies (included with anthropic[bedrock])

### Database Migrations

- **0002**: Add token tracking fields (input_tokens, output_tokens, total_tokens as IntegerField)
- **0003**: Change token fields to PositiveIntegerField for validation
- **0004**: Add estimated_cost_usd field (DecimalField, max_digits=8, decimal_places=6)

All fields are nullable for backward compatibility with existing QueryLog records.

### Deprecated

- `ClaudeCLIProvider` - Still available but no longer default
  - Use `LLM_PROVIDER=claude_cli` to enable
  - Recommended for development/testing only
  - Bedrock is recommended for production use

### Fixed

- Cost calculation precision issues (now uses DecimalField)
- Token tracking for both intent parsing and response formatting
- Error handling in AuditLogger for missing token usage data
- Date filtering in token_usage_report command (end_date now inclusive)

### Performance

- Query latency slightly improved (2-4s vs 2-5s with CLI)
- No subprocess overhead with direct SDK integration
- Proper connection pooling with AWS SDK

### Security

- AWS credentials never exposed in logs or code
- IAM role-based authentication supported for production
- Token usage data stored but contains no PII
- All queries maintain existing audit trail

### Testing

- 100 tests total (51 new, 49 existing)
- 100% pass rate
- ~75% code coverage
- Integration testing with real AWS Bedrock API
- 6.35 second test execution time

## [0.1.0] - 2026-03-08 - Initial Release

### Added

**Core Features**
- Natural language query interface for factory data
- REST API endpoint (`POST /api/query`)
- Command-line interface (`botswain-cli.py`)
- LLM-powered intent parsing
- Semantic layer for safe query execution
- Audit logging for all queries

**LLM Integration**
- Claude CLI subprocess integration
- `ClaudeCLIProvider` implementation
- Intent parsing from natural language to structured JSON
- Response formatting from query results to natural language

**Entity System**
- Entity registry pattern for extensibility
- Synthesizer entity implementation
- Support for filters, sorting, and field selection
- QuerySet-based execution against Django models

**Safety & Validation**
- Safety validator for query validation
- SQL injection pattern detection
- Query limit enforcement (max 1000 results)
- Dangerous keyword blocking

**Database**
- Django models for QueryLog audit trail
- SQLite for development and testing
- PostgreSQL support for production
- BARB database integration support

**API**
- Django REST Framework integration
- JSON request/response format
- Query caching support
- Multiple response formats (natural, json, table)

**CLI**
- Interactive command-line interface
- Multiple output formats
- Debug mode
- Raw JSON output option
- Remote server support

**Docker Support**
- Docker Compose configuration
- PostgreSQL service
- Redis service
- Development volume mounts

**Testing**
- 49 initial tests
- pytest configuration
- Coverage reporting
- Mock data sources for testing

**Documentation**
- README.md with comprehensive usage guide
- API documentation
- CLI usage examples
- Docker deployment guide
- Architecture overview

### Initial Configuration

- Django settings with multiple environments
- Support for local, BARB local, and BARB production connections
- Environment variable configuration
- Development and production settings separation

---

## Version History

- **0.2.0** (2026-03-10) - AWS Bedrock SDK Migration
  - Added token tracking and cost monitoring
  - Changed default provider to AWS Bedrock
  - Added 51 new tests
  - Added comprehensive documentation

- **0.1.0** (2026-03-08) - Initial Release
  - Core functionality with Claude CLI integration
  - REST API and CLI interfaces
  - 49 initial tests
  - Basic documentation

---

## Migration Notes

### Upgrading from 0.1.0 to 0.2.0

**Breaking Changes**: None - fully backward compatible

**Required Steps**:
1. Install new dependencies: `pip install -r requirements.txt`
2. Run database migrations: `python manage.py migrate`
3. Configure environment: `export LLM_PROVIDER=bedrock`
4. Verify AWS credentials configured
5. Restart application

**Optional Steps**:
- Configure Bedrock settings (model, token limits, timeout)
- Set up cost monitoring with `make token-report`
- Review token usage patterns

**Rollback**: Change `LLM_PROVIDER=claude_cli` and restart application

See `MIGRATION_SUMMARY.md` and `DEPLOYMENT_GUIDE.md` for complete details.

---

## Future Roadmap

### Planned Features

**Near-term** (Next 1-2 months):
- [ ] Redis caching for frequent queries
- [ ] Additional entities (WorkOrder, Inventory, Locations)
- [ ] Query result pagination
- [ ] Cost alerts and budget management

**Mid-term** (2-6 months):
- [ ] Web-based query interface
- [ ] User authentication and permissions
- [ ] Query history and favorites
- [ ] Cost dashboard with visualizations
- [ ] Slack integration

**Long-term** (6+ months):
- [ ] Support for additional LLM providers (OpenAI, direct Anthropic API)
- [ ] Advanced query optimization
- [ ] Natural language report generation
- [ ] Integration with Hook/Line/Loot frontends
- [ ] Multi-database federation

---

## Contributing

Internal Synthego project - see company policies for contribution guidelines.

## Support

For issues or questions:
- Check documentation: README.md, MIGRATION_SUMMARY.md, DEPLOYMENT_GUIDE.md
- Run diagnostics: `make check-bedrock`, `make show-provider`
- Contact: Data Analytics team
