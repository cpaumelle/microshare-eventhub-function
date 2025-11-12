# Azure Function Deployment Guide

## Overview

This guide covers deploying the Microshare-to-EventHub forwarder as a serverless **Azure Function**.

## Architecture

### Serverless Function Approach
- **Azure Function** (Consumption plan) - runs hourly via timer trigger
- **Azure Table Storage** - persists state (last fetch time, counters)
- **Azure Event Hub** - receives occupancy snapshots  
- **Application Insights** - monitoring and logging


### 1. Azure Subscription
- Active Azure subscription with permissions to create:
  - Storage Accounts
  - Function Apps
  - Event Hubs (already exists: `ehns-playground-26767`)

### 2. Required Tools
```bash
# Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Azure Functions Core Tools
wget -q https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install azure-functions-core-tools-4
```

### 3. Credentials Needed
- **Microshare API:** Username, Password, API Key, Data Context
- **Azure Event Hub:** Connection string with EntityPath
- **Azure:** Account with contributor access to resource group

## Deployment Steps

### Step 1: Clone and Switch to Azure Function Branch

```bash
git clone <your-repo-url>
cd occupancy-snapshot-updated
git checkout azure-function
```

### Step 2: Authenticate with Azure

```bash
az login --use-device-code
# Follow browser prompts to authenticate

# Verify authentication
az account show
```

### Step 3: Create Azure Storage Account

```bash
# Create storage account for function app and state management
az storage account create \
  --name microsharefuncstore \
  --resource-group rg-eh-playground \
  --location uksouth \
  --sku Standard_LRS \
  --kind StorageV2
```

> **Note:** Storage account name must be globally unique. Change `microsharefuncstore` if needed.

### Step 4: Create Azure Function App

```bash
az functionapp create \
  --name microshare-forwarder-func \
  --storage-account microsharefuncstore \
  --resource-group rg-eh-playground \
  --consumption-plan-location uksouth \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type Linux
```

> **Note:** Function app name must be globally unique and becomes part of URL: `<name>.azurewebsites.net`

### Step 5: Deploy Function Code

```bash
cd /path/to/occupancy-snapshot-updated
func azure functionapp publish microshare-forwarder-func
```

Expected output:
```
Remote build succeeded!
Syncing triggers...
Functions in microshare-forwarder-func:
    microshare_forwarder - [timerTrigger]
```

### Step 6: Configure Environment Variables

```bash
az functionapp config appsettings set \
  --name microshare-forwarder-func \
  --resource-group rg-eh-playground \
  --settings \
    MICROSHARE_USERNAME="your_username" \
    MICROSHARE_PASSWORD="your_password" \
    MICROSHARE_API_KEY="your_api_key" \
    MICROSHARE_DATA_CONTEXT="YourCompany" \
    EVENT_HUB_CONNECTION_STRING="Endpoint=sb://your-namespace.servicebus.windows.net/;SharedAccessKeyName=...;SharedAccessKey=...;EntityPath=your-hub" \
    LOG_LEVEL="INFO"
```

> **Security Note:** Never commit credentials to git. Use Azure Key Vault for production deployments.

### Step 7: Verify Deployment

```bash
# Check function app status
az functionapp show \
  --name microshare-forwarder-func \
  --resource-group rg-eh-playground \
  --query "{name:name, state:state, defaultHostName:defaultHostName}"
```

Expected output:
```
Name                       State    DefaultHostName
-------------------------  -------  -------------------------------------------
microshare-forwarder-func  Running  microshare-forwarder-func.azurewebsites.net
```

## Monitoring

### View Logs in Azure Portal

1. Navigate to: https://portal.azure.com
2. Search for: `microshare-forwarder-func`
3. Click: **Monitor** → **Logs** → **Application Insights**
4. Query recent executions

### Application Insights Metrics

Key metrics to monitor:
- **Execution Count:** Should be ~24/day (hourly schedule)
- **Failures:** Should be 0
- **Duration:** Typically < 30 seconds
- **Data Sent:** Check Event Hub ingress metrics

## Timer Schedule

The function runs on the following schedule:

```python
schedule="0 0 * * * *"  # Every hour at :00
```

**Cron format:** `{second} {minute} {hour} {day} {month} {day-of-week}`

Examples of schedule modifications:

| Schedule | Cron Expression | Description |
|----------|-----------------|-------------|
| Every hour | `0 0 * * * *` | Current (every hour at :00) |
| Every 30 min | `0 */30 * * * *` | Twice per hour |
| Every 15 min | `0 */15 * * * *` | Four times per hour |
| Daily at 2 AM | `0 0 2 * * *` | Once per day |
| Every 6 hours | `0 0 */6 * * *` | Four times per day |

To change the schedule, edit `function_app.py` and redeploy.

## State Management

State is stored in Azure Table Storage to track:
- **Last fetch time:** Prevents duplicate data retrieval
- **Snapshots sent:** Running counter for monitoring

**Table:** `microshareforwarderstate`  
**Connection:** Automatically configured via `AzureWebJobsStorage`

## Configuring Data Sources (recTypes)

The Azure Function supports multiple Microshare data types. Here's how to configure it for your specific data source.

### Step 1: Identify Your Data Source

Contact Microshare support to determine:

1. **Which recType** contains your data:
   - `io.microshare.lake.snapshot.hourly` - Hourly occupancy snapshots
   - `io.microshare.peoplecounter.unpacked.event.agg` - 15-min people counting
   - `io.microshare.occupancy.unpacked` - Motion sensor data

2. **Your View ID** - Required for all queries (e.g., `661eabafa0a03557a44bdd6c`)

3. **Your data context** - Organization identifier (e.g., `YourCompanyName`)

### Step 2: Configure for Your recType

#### Option A: Using config.yaml (Recommended)

Edit `config.yaml` with your specific settings:

```yaml
microshare:
  username: ${MICROSHARE_USERNAME}
  password: ${MICROSHARE_PASSWORD}
  api_key: ${MICROSHARE_API_KEY}
  
  # Your View ID from Microshare
  view_id: "YOUR-VIEW-ID-HERE"
  
  # Choose your recType:
  rec_type: "io.microshare.peoplecounter.unpacked.event.agg"
  
  # Your organization's data context
  data_context: '["YourCompany","people"]'
  
  # Optional location filter
  location: "Building-A"
```

#### Option B: Using Environment Variables

Override config.yaml settings via Function App settings:

```bash
az functionapp config appsettings set \
  --name microshare-forwarder-func \
  --resource-group rg-eh-playground \
  --settings \
    MICROSHARE_VIEW_ID="your-view-id" \
    MICROSHARE_REC_TYPE="io.microshare.occupancy.unpacked" \
    MICROSHARE_DATA_CONTEXT="YourCompany"
```

### Step 3: Test Your Configuration

Before deploying, test locally:

```bash
# Update local.settings.json with your settings
func start

# Trigger the function manually
# Check logs for data retrieval
```

### Step 4: Deploy and Verify

```bash
# Deploy updated configuration
func azure functionapp publish microshare-forwarder-func

# Verify settings were applied
az functionapp config appsettings list \
  --name microshare-forwarder-func \
  --resource-group rg-eh-playground \
  --query "[?name=='MICROSHARE_REC_TYPE'].{Name:name, Value:value}"

# Monitor first execution
# (Azure Portal -> Function App -> Monitor -> Application Insights)
```

### Common Configurations

#### Configuration 1: Hourly Occupancy Snapshots

```bash
MICROSHARE_REC_TYPE="io.microshare.lake.snapshot.hourly"
MICROSHARE_DATA_CONTEXT="["YourCompany","occupancy","room"]"
```

#### Configuration 2: People Counter (15-min aggregates)

```bash
MICROSHARE_REC_TYPE="io.microshare.peoplecounter.unpacked.event.agg"
MICROSHARE_DATA_CONTEXT="["people"]"
```

#### Configuration 3: Motion Sensors

```bash
MICROSHARE_REC_TYPE="io.microshare.occupancy.unpacked"
MICROSHARE_DATA_CONTEXT="["room","motion"]"
```

### Switching Between recTypes

To switch data sources after deployment:

```bash
# Update the recType setting
az functionapp config appsettings set \
  --name microshare-forwarder-func \
  --resource-group rg-eh-playground \
  --settings MICROSHARE_REC_TYPE="io.microshare.occupancy.unpacked"

# Function will automatically use new recType on next execution
# No code redeployment needed!
```


## Troubleshooting

### Function Not Executing

1. Check timer status in Azure Portal
2. Verify environment variables are set
3. Check Application Insights for errors

### Authentication Errors

**Symptom:** `401 Unauthorized` from Microshare API

**Solution:** Verify credentials in function app settings

### Event Hub Connection Issues

**Symptom:** `EventHub error: Unauthorized`

**Solution:** Verify connection string includes `EntityPath=your-hub-name`

### Cold Start Delays

**Symptom:** First execution after idle period takes 5-10 seconds

**Solution:** This is normal for Consumption plan

## Cost Optimization

### Current Configuration (Consumption Plan)

**Estimated Monthly Cost:** ~$3

Breakdown:
- **Function executions:** 720/month (hourly) = FREE (1M free/month)
- **Execution time:** ~5s/run × 720 = 1 hour = FREE (400,000 GB-s free/month)
- **Storage account:** Standard LRS = ~$2/month
- **Application Insights:** Basic tier = ~$1/month


- **Documentation:** [README.md](README.md)
- **VM Deployment:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Security:** [SECURITY.md](SECURITY.md)
- **Azure Functions Docs:** https://docs.microsoft.com/azure/azure-functions/

---

**Deployment Date:** 2025-11-12  
**Azure Function App:** microshare-forwarder-func.azurewebsites.net  
**Resource Group:** rg-eh-playground  
**Region:** UK South
## Support

- **Documentation:** [README.md](README.md)
- **Security:** [SECURITY.md](SECURITY.md)
- **Azure Functions Docs:** https://docs.microsoft.com/azure/azure-functions/

---

**Deployment Date:** 2025-11-12  
**Azure Function App:** microshare-forwarder-func.azurewebsites.net  
**Resource Group:** rg-eh-playground  
**Region:** UK South
