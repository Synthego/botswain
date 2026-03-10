# Release Notes - Botswain v0.2.0

## AWS Bedrock SDK Migration

**Release Date**: March 10, 2026
**Migration Type**: Major Enhancement (Backward Compatible)

## Overview

Migrated from subprocess-based Claude CLI to AWS Bedrock SDK with comprehensive token tracking and cost monitoring capabilities.

## Key Features

### Token Usage Tracking
- Automatic capture of input/output/total tokens for all queries
- Real-time token counting via Bedrock API responses
- Historical tracking in QueryLog model

### Cost Monitoring
- USD cost estimation for all queries
- Sonnet 4.5: $3/$15 per million tokens (input/output)
- Management command for cost reports: `make token-report`
- Date range filtering for analysis

### Provider Factory Pattern
- Easy switching between Bedrock (default) and Claude CLI (legacy)
- Environment variable configuration: `LLM_PROVIDER`
- Graceful fallback support

## What's New

### New Components
- BedrockProvider with direct API integration
- Cost calculation utilities
- Token usage management command
- Bedrock configuration settings
- Provider factory with environment-based selection

### Enhanced Components
- QueryLog model with token tracking fields
- AuditLogger with cost capture
- API view with factory pattern
- Comprehensive documentation

### New Commands
- `make token-report` - Generate usage report
- `make token-report-week` - Weekly report
- `make token-report-month` - Monthly report
- `make check-bedrock` - Verify configuration
- `make show-provider` - Display current provider

## Migration Guide

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for complete instructions.

**Quick Start**:
```bash
# 1. Set environment
export LLM_PROVIDER=bedrock

# 2. Configure AWS
aws configure

# 3. Run migrations
python manage.py migrate

# 4. Start application
make run
```

## Testing

- 100 tests (51 new)
- 100% pass rate
- ~75% code coverage
- Integration testing complete

## Known Limitations

1. Management command cost display uses 2 decimal places (data is accurate to 6 decimal places)
2. Old queries (pre-migration) have NULL token/cost values
3. Default region is us-west-2 (configurable)

## Rollback

To rollback: `export LLM_PROVIDER=claude_cli`

## Contributors

Implemented via Subagent-Driven Development with Claude Sonnet 4.5.
