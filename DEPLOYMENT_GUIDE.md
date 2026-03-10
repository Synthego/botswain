# Deployment Guide - AWS Bedrock Integration

This guide covers deploying Botswain with AWS Bedrock SDK integration for production use.

## Prerequisites

### Required

- **AWS Account** with Bedrock access
- **AWS Credentials** configured (IAM role or credentials file)
- **Bedrock Model Access** granted in AWS console (Claude Sonnet 4.5)
- **Python 3.9+**
- **Django 4.2+**
- **PostgreSQL** (for production) or SQLite (for development)
- **Redis** (optional, for caching)

### AWS Bedrock Setup

1. **Enable Bedrock Access** in your AWS account
2. **Request Model Access** in Bedrock console:
   - Navigate to AWS Bedrock console → Model access
   - Request access to: `Claude Sonnet 4.5` (or `Claude Haiku 3.5` for lower cost)
   - Wait for approval (usually instant for standard models)

3. **Verify Model Access**:
```bash
aws bedrock list-foundation-models --region us-west-2 | grep claude-sonnet-4
```

## Environment Variables

### Required

```bash
# LLM Provider
LLM_PROVIDER=bedrock

# AWS Region
AWS_REGION=us-west-2

# Database (PostgreSQL recommended for production)
POSTGRES_DB=botswain
POSTGRES_USER=botswain
POSTGRES_PASSWORD=<strong_password>
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Django Secret Key
DJANGO_SECRET_KEY=<generate_strong_secret_key>
```

### Optional (with defaults)

```bash
# Bedrock Model (default: Claude Sonnet 4.5)
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Token Limits
BEDROCK_MAX_INTENT_TOKENS=500
BEDROCK_MAX_RESPONSE_TOKENS=1000

# Timeout (seconds)
BEDROCK_TIMEOUT=30.0

# Redis (for caching, optional)
REDIS_URL=redis://localhost:6379/0
```

### Production-Specific

```bash
# Disable debug mode
DEBUG=False

# Set allowed hosts
ALLOWED_HOSTS=your-domain.com,api.your-domain.com

# HTTPS settings
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

## Deployment Steps

### Step 1: Update Dependencies

```bash
# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Verify Bedrock SDK installed
python -c "import anthropic; print(anthropic.__version__)"
```

### Step 2: Run Database Migrations

```bash
# Ensure correct settings module
export DJANGO_SETTINGS_MODULE=botswain.settings.production

# Run migrations
python manage.py migrate

# Verify migrations applied
python manage.py showmigrations
```

Expected output:
```
core
 [X] 0001_initial
 [X] 0002_querylog_input_tokens_querylog_output_tokens_and_more
 [X] 0003_alter_querylog_input_tokens_and_more
 [X] 0004_add_estimated_cost_usd
```

### Step 3: Configure AWS Credentials

Choose one of the following methods:

#### Option A: IAM Role (Recommended for ECS/EC2)

No configuration needed - credentials automatically available via instance role.

**Required IAM Permissions**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-west-2::foundation-model/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
      ]
    }
  ]
}
```

#### Option B: AWS Credentials File

```bash
# Configure AWS CLI
aws configure

# Verify credentials
aws sts get-caller-identity
```

#### Option C: Environment Variables

```bash
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_REGION=us-west-2
```

**Security Note**: Never commit AWS credentials to version control.

### Step 4: Test Configuration

```bash
# Check Bedrock provider configuration
make check-bedrock

# Show current provider
make show-provider

# Run test query
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What synthesizers are available?"}'
```

### Step 5: Collect Static Files

```bash
# Collect static files for production
python manage.py collectstatic --noinput
```

### Step 6: Start Application

Choose your deployment method:

#### Local Development
```bash
make run
```

#### Production with Gunicorn
```bash
gunicorn botswain.wsgi:application \
  --bind 0.0.0.0:8002 \
  --workers 4 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
```

#### Docker Compose
```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# View logs
docker-compose logs -f
```

#### AWS ECS (Fargate)

See "AWS ECS Deployment" section below.

### Step 7: Verify Deployment

```bash
# Health check
curl http://localhost:8002/api/query

# Test query
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What synthesizers are available?"}'

# Check token tracking
python manage.py token_usage_report
```

### Step 8: Monitor Token Usage

```bash
# View all-time usage
make token-report

# View today's usage
make token-report-today

# Set up automated daily reports (optional)
0 0 * * * cd /path/to/botswain && make token-report-today | mail -s "Daily Token Report" admin@example.com
```

## AWS ECS Deployment

### Task Definition

```json
{
  "family": "botswain",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/BotswainTaskRole",
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "botswain",
      "image": "ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/botswain:latest",
      "portMappings": [
        {
          "containerPort": 8002,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "LLM_PROVIDER",
          "value": "bedrock"
        },
        {
          "name": "AWS_REGION",
          "value": "us-west-2"
        },
        {
          "name": "DJANGO_SETTINGS_MODULE",
          "value": "botswain.settings.production"
        }
      ],
      "secrets": [
        {
          "name": "DJANGO_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:botswain/django-secret-key"
        },
        {
          "name": "POSTGRES_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:botswain/postgres-password"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/botswain",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Service Definition

```json
{
  "serviceName": "botswain",
  "cluster": "production",
  "taskDefinition": "botswain:1",
  "desiredCount": 2,
  "launchType": "FARGATE",
  "networkConfiguration": {
    "awsvpcConfiguration": {
      "subnets": ["subnet-xxxxx", "subnet-yyyyy"],
      "securityGroups": ["sg-xxxxx"],
      "assignPublicIp": "DISABLED"
    }
  },
  "loadBalancers": [
    {
      "targetGroupArn": "arn:aws:elasticloadbalancing:us-west-2:ACCOUNT_ID:targetgroup/botswain/xxxxx",
      "containerName": "botswain",
      "containerPort": 8002
    }
  ]
}
```

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8002

# Run gunicorn
CMD ["gunicorn", "botswain.wsgi:application", \
     "--bind", "0.0.0.0:8002", \
     "--workers", "4", \
     "--timeout", "60"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8002:8002"
    environment:
      - LLM_PROVIDER=bedrock
      - AWS_REGION=us-west-2
      - DJANGO_SETTINGS_MODULE=botswain.settings.production
      - POSTGRES_HOST=db
    env_file:
      - .env.production
    depends_on:
      - db
      - redis
    networks:
      - botswain-network

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=botswain
      - POSTGRES_USER=botswain
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - botswain-network

  redis:
    image: redis:7-alpine
    networks:
      - botswain-network

volumes:
  postgres_data:

networks:
  botswain-network:
    driver: bridge
```

## Monitoring

### CloudWatch Logs

```bash
# View logs
aws logs tail /ecs/botswain --follow

# Filter for errors
aws logs tail /ecs/botswain --follow --filter-pattern "ERROR"
```

### Cost Monitoring

```bash
# Generate daily token report
python manage.py token_usage_report --start-date $(date +%Y-%m-%d)

# Generate monthly report
python manage.py token_usage_report --start-date $(date +%Y-%m-01)
```

### Set Up Cost Alerts

Create a script to alert on high costs:

```bash
#!/bin/bash
# cost_alert.sh

COST=$(python manage.py token_usage_report --start-date $(date +%Y-%m-01) | grep "Total Cost:" | awk '{print $3}' | tr -d '$')
THRESHOLD=100.00

if (( $(echo "$COST > $THRESHOLD" | bc -l) )); then
    echo "Alert: Monthly cost ($COST) exceeds threshold ($THRESHOLD)" | \
        mail -s "Botswain Cost Alert" admin@example.com
fi
```

## Performance Tuning

### Gunicorn Workers

```bash
# Calculate optimal workers
# workers = 2 * CPU_CORES + 1

# For 2 CPU cores:
gunicorn botswain.wsgi:application --workers 5

# For 4 CPU cores:
gunicorn botswain.wsgi:application --workers 9
```

### Database Connection Pooling

Add to `settings/production.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB'),
        'USER': os.environ.get('POSTGRES_USER'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD'),
        'HOST': os.environ.get('POSTGRES_HOST'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': 600,  # Connection pooling
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
```

### Redis Caching

Add to `settings/production.py`:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'botswain',
        'TIMEOUT': 300,  # 5 minutes
    }
}
```

## Rollback Plan

If issues occur after deployment:

### Step 1: Rollback to Claude CLI

```bash
# Update environment
export LLM_PROVIDER=claude_cli

# Restart application
systemctl restart botswain  # or your restart method
```

### Step 2: Monitor

```bash
# Check logs
tail -f /var/log/botswain/error.log

# Test queries
make test-api-call
```

### Step 3: Rollback Database (if needed)

```bash
# Rollback migrations (only if necessary)
python manage.py migrate core 0001

# Note: This removes token tracking fields but doesn't lose data
```

## Troubleshooting

### "Access denied" errors

**Cause**: AWS credentials or Bedrock permissions issue

**Solution**:
```bash
# Verify credentials
aws sts get-caller-identity

# Verify Bedrock access
aws bedrock list-foundation-models --region us-west-2

# Check IAM permissions
aws iam get-role-policy --role-name BotswainTaskRole --policy-name BedrockAccess
```

### "Model not found" errors

**Cause**: Using direct model ID instead of inference profile ID

**Solution**:
```bash
# Correct (with us. prefix)
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Incorrect (without us. prefix)
# BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0
```

### High latency

**Cause**: Timeout settings or network issues

**Solution**:
```bash
# Increase timeout
export BEDROCK_TIMEOUT=60.0

# Check network latency
ping bedrock-runtime.us-west-2.amazonaws.com

# Use Bedrock in closer region
export AWS_REGION=us-east-1
```

### High costs

**Cause**: Excessive token usage

**Solution**:
```bash
# Analyze usage
make token-report

# Reduce token limits
export BEDROCK_MAX_INTENT_TOKENS=300
export BEDROCK_MAX_RESPONSE_TOKENS=500

# Switch to cheaper model
export BEDROCK_MODEL_ID=us.anthropic.claude-3-5-haiku-20241022-v1:0
```

### Database migration issues

**Cause**: Migration already applied or database locked

**Solution**:
```bash
# Show migration status
python manage.py showmigrations

# Fake migration if already applied manually
python manage.py migrate core 0004 --fake

# Rollback and reapply
python manage.py migrate core 0003
python manage.py migrate core 0004
```

## Security Checklist

Before deploying to production:

- [ ] `DEBUG=False` in production settings
- [ ] Strong `DJANGO_SECRET_KEY` generated and stored securely
- [ ] AWS credentials never committed to version control
- [ ] HTTPS enabled with proper SSL certificates
- [ ] `ALLOWED_HOSTS` configured correctly
- [ ] Database passwords stored in secrets manager
- [ ] IAM roles follow least privilege principle
- [ ] Security groups restrict access appropriately
- [ ] Logs don't contain sensitive information
- [ ] CSRF and session cookies secured

## Maintenance

### Regular Tasks

**Daily**:
- Monitor token usage: `make token-report-today`
- Check error logs for issues

**Weekly**:
- Review cost trends: `make token-report-week`
- Check for AWS service updates

**Monthly**:
- Generate cost report: `make token-report-month`
- Review and optimize token usage
- Update dependencies: `pip install --upgrade -r requirements.txt`
- Verify Bedrock model availability

### Backup

```bash
# Backup database
pg_dump -h $POSTGRES_HOST -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d).sql

# Backup QueryLog data
python manage.py dumpdata core.QueryLog > querylog_backup_$(date +%Y%m%d).json
```

## Support

For deployment issues or questions:

1. **Check logs**: Django logs and CloudWatch logs
2. **Review documentation**: README.md, MIGRATION_SUMMARY.md
3. **Run diagnostics**: `make check-bedrock`, `make show-provider`
4. **Test connectivity**: `aws bedrock list-foundation-models`
5. **Contact team**: Data Analytics team or DevOps

## Additional Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [Gunicorn Configuration](https://docs.gunicorn.org/en/stable/configure.html)
