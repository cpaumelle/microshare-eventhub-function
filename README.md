# Microshare to Azure Event Hub - Serverless Function

**Production-ready serverless integration** that pulls occupancy snapshots from Microshare API and forwards them to Azure Event Hub using Azure Functions.

## Why Azure Functions?

- **Cost-effective:** ~$3/month (vs $50-100 for VM deployment)
- **Zero maintenance:** Fully managed by Azure, no OS updates
- **Auto-scaling:** Handles load automatically
- **Built-in monitoring:** Application Insights included
- **Reliable:** Azure SLA with automatic retries

## Architecture

```
┌─────────────────┐
│  Microshare API │
│   (HTTPS Pull)  │
└────────┬────────┘
         │
    [Timer Trigger]
    Every hour at :00
         │
┌────────▼───────────┐
│  Azure Function    │
│  (Python 3.11)     │
│  - Fetch data      │
│  - Track state     │
│  - Deduplicate     │
└────────┬───────────┘
         │
┌────────▼───────────┐
│  Azure Table       │
│  Storage (State)   │
└────────────────────┘
         │
┌────────▼───────────┐
│  Azure Event Hub   │
│  (Data ingress)    │
└────────────────────┘
```

## Features

✅ **Automatic scheduling** - Runs hourly via timer trigger  
✅ **State persistence** - Azure Table Storage tracks last fetch time  
✅ **Deduplication** - Prevents sending duplicate snapshots  
✅ **Error handling** - Automatic retries and detailed logging  
✅ **Monitoring** - Application Insights for tracking executions  
✅ **Secure** - Credentials stored as app settings, never in code  
✅ **Scalable** - Consumption plan auto-scales as needed  

## Quick Start

### Prerequisites

- Azure subscription with permissions for:
  - Storage Accounts
  - Function Apps
  - Event Hubs
- Azure CLI installed
- Azure Functions Core Tools v4
- Microshare API credentials
- Event Hub connection string

### Deploy in 5 Steps

```bash
# 1. Authenticate with Azure
az login

# 2. Create storage account
az storage account create \
  --name <unique-storage-name> \
  --resource-group <your-resource-group> \
  --location <region> \
  --sku Standard_LRS

# 3. Create Function App
az functionapp create \
  --name <unique-function-name> \
  --storage-account <storage-name> \
  --resource-group <your-resource-group> \
  --consumption-plan-location <region> \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type Linux

# 4. Deploy function code
func azure functionapp publish <function-name>

# 5. Configure environment variables
az functionapp config appsettings set \
  --name <function-name> \
  --resource-group <your-resource-group> \
  --settings \
    MICROSHARE_USERNAME="your_username" \
    MICROSHARE_PASSWORD="your_password" \
    MICROSHARE_API_KEY="your_api_key" \
    MICROSHARE_DATA_CONTEXT="your_context" \
    EVENT_HUB_CONNECTION_STRING="your_connection_string" \
    LOG_LEVEL="INFO"
```

**That's it!** Your function will run automatically every hour.

## Detailed Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide with troubleshooting
- **[SECURITY.md](SECURITY.md)** - Security architecture and best practices

## Configuration

### Schedule

Default: Every hour at :00 (`0 0 * * * *`)

Change the schedule in `function_app.py`:

```python
@app.timer_trigger(
    schedule="0 */15 * * * *",  # Every 15 minutes
    # schedule="0 0 * * * *",   # Every hour (default)
    # schedule="0 */30 * * * *", # Every 30 minutes
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=False
)
```

### Environment Variables

Required settings (configured as Function App settings):

| Variable | Description | Example |
|----------|-------------|---------|
| `MICROSHARE_USERNAME` | Microshare API username | `user@company.com` |
| `MICROSHARE_PASSWORD` | Microshare API password | `your_password` |
| `MICROSHARE_API_KEY` | Microshare API key | `UUID-format-key` |
| `MICROSHARE_DATA_CONTEXT` | Data context filter | `CBRE` |
| `EVENT_HUB_CONNECTION_STRING` | Event Hub connection with EntityPath | `Endpoint=sb://...;EntityPath=hub` |
| `LOG_LEVEL` | Logging level | `INFO` or `DEBUG` |

### Application Settings

Edit `config.yaml` to customize:

- Microshare view ID
- Location filters
- API timeouts
- Retry configuration

## Monitoring

### View Logs in Azure Portal

1. Go to https://portal.azure.com
2. Search for your Function App
3. Navigate to **Monitor** → **Application Insights**
4. Query recent executions:

```kusto
traces
| where timestamp > ago(24h)
| where message contains "Microshare Forwarder"
| project timestamp, message, severityLevel
| order by timestamp desc
```

### Key Metrics

- **Execution Count:** ~24/day (hourly schedule)
- **Success Rate:** Should be 100%
- **Duration:** Typically 5-30 seconds
- **Data Volume:** Check snapshots sent in logs

### Check State

State is stored in Azure Table Storage (`microshareforwarderstate` table):

```bash
az storage entity show \
  --connection-string "$STORAGE_CONN_STRING" \
  --table-name microshareforwarderstate \
  --partition-key state \
  --row-key global
```

## Cost Breakdown

**Monthly Cost: ~$3**

| Component | Cost |
|-----------|------|
| Function executions (720/month) | FREE* |
| Execution time (~2.5 hours/month) | FREE* |
| Storage Account (Standard LRS) | ~$2 |
| Application Insights | ~$1 |

*Azure Functions includes 1M free executions and 400,000 GB-s free per month

## Troubleshooting

### Function not executing?

```bash
# Check function status
az functionapp show \
  --name <function-name> \
  --resource-group <resource-group> \
  --query "{name:name, state:state}"
```

### Authentication errors?

Verify environment variables are set:

```bash
az functionapp config appsettings list \
  --name <function-name> \
  --resource-group <resource-group>
```

### No data in Event Hub?

1. Check Application Insights logs for errors
2. Verify Event Hub connection string includes `EntityPath=<hub-name>`
3. Confirm Microshare credentials are correct
4. Check state table for last_fetch_time

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed troubleshooting.

## Development

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Create local settings
cp .env.example .env
# Edit .env with your credentials

# Run locally
func start
```

### Update Deployed Function

```bash
# Make code changes
git commit -am "Description of changes"

# Redeploy
func azure functionapp publish <function-name>
```

## Project Structure

```
├── function_app.py           # Main function entry point (timer trigger)
├── app/
│   ├── config.py             # Configuration loader
│   ├── microshare_client.py  # Microshare API client
│   ├── eventhub_client.py    # Event Hub client
│   └── state_manager_azure.py# Azure Table Storage state mgmt
├── host.json                 # Function runtime config
├── requirements.txt          # Python dependencies
├── config.yaml               # Application configuration
├── .env.example              # Template for credentials
├── DEPLOYMENT.md             # Detailed deployment guide
└── SECURITY.md               # Security documentation
```

## Security

- Credentials stored as encrypted app settings (never in code)
- HTTPS-only communication (TLS 1.2+)
- Managed Identity support (optional)
- Azure Key Vault integration (optional)
- Network restrictions (optional)

See [SECURITY.md](SECURITY.md) for detailed security architecture.

## Support

- **Issues:** Report bugs or feature requests via GitHub Issues
- **Documentation:** See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Azure Functions:** https://docs.microsoft.com/azure/azure-functions/

## License

Copyright © 2025. All rights reserved.

---

**Live Demo Deployment:**
- Function: `microshare-forwarder-func.azurewebsites.net`
- Region: UK South
- Deployed: 2025-11-12
