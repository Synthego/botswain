# Accessing BARB Production Data

The BARB production database credentials have been configured in `botswain/settings/barb_prod_replica.py`, but the database is in an AWS VPC and requires special access.

## Production Credentials (from AWS Secrets Manager)

```
Secret: barb/prod
Host: barb-prod-pg-replica-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com
Port: 5432
Database: barb
User: readonlyuser
Password: BARB_READONLY_PASSWORD_HERE
```

## Access Options

### Option 1: SSH Tunnel via Bastion Host (Recommended)

If you have SSH access to a bastion/jump host in the VPC:

```bash
# Create SSH tunnel (replace with actual bastion host)
ssh -L 5433:barb-prod-pg-replica-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com:5432 user@bastion-host

# In another terminal, update settings to use localhost:5433
# Then run:
make run-barb-prod
```

### Option 2: AWS Session Manager Port Forwarding

If you have an EC2 instance in the VPC with Systems Manager:

```bash
# Start port forwarding session
aws ssm start-session \
  --target i-<instance-id> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{
    "host":["barb-prod-pg-replica-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com"],
    "portNumber":["5432"],
    "localPortNumber":["5433"]
  }'

# Update settings to use localhost:5433, then run:
make run-barb-prod
```

### Option 3: VPN Connection

If Synthego has a VPN to the AWS VPC:

```bash
# Connect to VPN first
# Then run directly:
make run-barb-prod
```

### Option 4: Run Botswain in AWS

Deploy Botswain to an EC2 instance or ECS container in the same VPC:

```bash
# On the EC2 instance in the VPC
cd botswain
make run-barb-prod
```

## Settings File Created

**`botswain/settings/barb_prod_replica.py`** - Production read-replica settings:
- Read-only user for safety
- Production replica (not primary) to avoid impacting prod writes
- Same configuration as local but points to production database

## Makefile Commands Added

```bash
make run-barb-prod       # Run with production replica
make check-barb-prod     # Test production connection
```

## Testing Production Access

Once you have connectivity (via tunnel/VPN/AWS):

```bash
# Test database connection
PGPASSWORD='BARB_READONLY_PASSWORD_HERE' psql \
  -h barb-prod-pg-replica-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com \
  -p 5432 -U readonlyuser -d barb \
  -c "SELECT COUNT(*) FROM inventory_instrument;"

# Run Botswain with production data
make run-barb-prod

# Query production data
./botswain-cli.py "How many instruments are in production?"
```

## Security Notes

✅ **Safe:**
- Using read-only user (`readonlyuser`)
- Connecting to replica (not primary)
- All queries are SELECT only (enforced by SafetyValidator)

⚠️ **Important:**
- Database is in VPC - requires bastion/tunnel/VPN
- Credentials are from AWS Secrets Manager `barb/prod`
- Read-only access prevents accidental data modification

## Troubleshooting

### "Connection timed out"
**Cause:** Database is in VPC, not accessible from internet
**Solution:** Use SSH tunnel, VPN, or run Botswain in AWS

### "FATAL: password authentication failed"
**Cause:** Wrong credentials or password changed
**Solution:** Re-fetch from AWS Secrets Manager:
```bash
source /home/danajanezic/code/jormungand/bash/lib/aws_functions.sh
getSecretByNauticalCodenameAndEnv barb prod
```

### "SSL connection required"
**Cause:** RDS requires SSL
**Solution:** Add to settings:
```python
DATABASES = {
    'default': {
        ...
        'OPTIONS': {
            'sslmode': 'require',
        },
    }
}
```

## Next Steps

1. **Establish connectivity** - Choose one of the access options above
2. **Test connection** - Run `make check-barb-prod`
3. **Start Botswain** - Run `make run-barb-prod`
4. **Query production data** - Use CLI to query live factory state

Contact DevOps or Platform team for:
- VPN access
- Bastion host credentials
- EC2 instance for running Botswain in VPC
