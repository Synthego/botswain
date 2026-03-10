# Botswain Configuration

This document describes the configuration settings for the Botswain factory query assistant.

## Environment Variables

Configuration is managed through environment variables, which can be set in `.env` files or via your deployment environment.

### LLM Provider Settings

#### BOTSWAIN_LLM_PROVIDER

- **Default**: `bedrock`
- **Options**: `bedrock`, `claude_cli`
- **Description**: Selects which LLM provider to use for natural language processing.
  - `bedrock` - AWS Bedrock with Anthropic SDK (recommended for production)
  - `claude_cli` - Claude CLI subprocess (for development/testing)

**Example:**
```bash
BOTSWAIN_LLM_PROVIDER=bedrock
```

### AWS Bedrock Configuration

These settings configure the AWS Bedrock integration when `BOTSWAIN_LLM_PROVIDER=bedrock`.

#### BEDROCK_MODEL_ID

- **Default**: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
- **Description**: AWS Bedrock model inference profile ID. Must use the `us.` prefix for cross-region inference profiles.
- **Available Models**:
  - `us.anthropic.claude-sonnet-4-5-20250929-v1:0` - Sonnet 4.5 (recommended, balanced performance)
  - `us.anthropic.claude-3-7-sonnet-20250219-v1:0` - Sonnet 3.7 (faster, lower cost)
  - `us.anthropic.claude-3-5-haiku-20241022-v1:0` - Haiku 3.5 (fastest, lowest cost)

**Example:**
```bash
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

#### BEDROCK_MAX_INTENT_TOKENS

- **Default**: `500`
- **Description**: Maximum number of tokens the model can generate when parsing user questions into structured intent JSON.
- **Guidance**: 500 tokens is sufficient for most intent parsing tasks. Increase if you have complex queries with many filters.

**Example:**
```bash
BEDROCK_MAX_INTENT_TOKENS=500
```

#### BEDROCK_MAX_RESPONSE_TOKENS

- **Default**: `1000`
- **Description**: Maximum number of tokens the model can generate when formatting query results into natural language responses.
- **Guidance**: 1000 tokens allows for detailed responses with tables and formatting. Increase for very long result sets.

**Example:**
```bash
BEDROCK_MAX_RESPONSE_TOKENS=1000
```

#### AWS_REGION

- **Default**: `us-west-2`
- **Description**: AWS region for Bedrock API calls. Must be a region where Bedrock is available.
- **Available Regions**: `us-east-1`, `us-west-2`, `eu-west-1`, `ap-southeast-1`, etc.

**Example:**
```bash
AWS_REGION=us-west-2
```

#### BEDROCK_TIMEOUT

- **Default**: `30.0`
- **Description**: Request timeout in seconds for Bedrock API calls.
- **Guidance**: 30 seconds is usually sufficient. Increase if you experience timeout errors with complex queries.

**Example:**
```bash
BEDROCK_TIMEOUT=30.0
```

## Django Settings

These environment variables are read by Django settings in `botswain/settings/base.py`:

```python
# LLM Provider Configuration
LLM_PROVIDER = os.environ.get('BOTSWAIN_LLM_PROVIDER', 'bedrock')

# AWS Bedrock Configuration
BEDROCK_MODEL_ID = os.environ.get(
    'BEDROCK_MODEL_ID',
    'us.anthropic.claude-sonnet-4-5-20250929-v1:0'
)
BEDROCK_MAX_INTENT_TOKENS = int(os.environ.get('BEDROCK_MAX_INTENT_TOKENS', '500'))
BEDROCK_MAX_RESPONSE_TOKENS = int(os.environ.get('BEDROCK_MAX_RESPONSE_TOKENS', '1000'))
BEDROCK_AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
BEDROCK_TIMEOUT = float(os.environ.get('BEDROCK_TIMEOUT', '30.0'))
```

## Using Settings in Code

The BedrockProvider automatically uses Django settings:

```python
from core.llm.bedrock import BedrockProvider

# Uses settings defaults
provider = BedrockProvider()

# Override specific settings
provider = BedrockProvider(
    model='us.anthropic.claude-3-5-haiku-20241022-v1:0',
    max_response_tokens=2000
)
```

## Environment-Specific Configuration

### Local Development

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
# Edit .env with your preferred settings
```

### Docker Compose

Environment variables are set in `docker-compose.yaml`:

```yaml
environment:
  - BOTSWAIN_LLM_PROVIDER=bedrock
  - BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### Production Deployment

Set environment variables in your deployment platform (ECS, Kubernetes, etc.):

```bash
# AWS ECS Task Definition
"environment": [
  {
    "name": "BOTSWAIN_LLM_PROVIDER",
    "value": "bedrock"
  },
  {
    "name": "BEDROCK_MODEL_ID",
    "value": "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
  }
]
```

## AWS Credentials

Bedrock uses AWS SDK credential chain:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM role (when running on EC2/ECS)

**Production**: Use IAM roles (recommended)
**Development**: Use AWS credentials file or environment variables

## Troubleshooting

### "Access denied" errors with Bedrock

- Ensure you're using inference profile IDs with `us.` prefix
- Verify your AWS credentials have Bedrock permissions
- Check that the model is available in your region

### Timeout errors

- Increase `BEDROCK_TIMEOUT` setting
- Check network connectivity to AWS
- Consider using a faster model (Haiku instead of Sonnet)

### Token limit errors

- Increase `BEDROCK_MAX_INTENT_TOKENS` or `BEDROCK_MAX_RESPONSE_TOKENS`
- Simplify your queries to require less context
- Use pagination for large result sets
