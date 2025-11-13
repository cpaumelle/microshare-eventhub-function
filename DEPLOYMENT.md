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


## Running Multiple Data Sources Simultaneously

The function app supports running multiple Microshare data types (recTypes) simultaneously using **multiple timer-triggered functions** in the same deployment.

### Multi-Function Architecture

The `function_app.py` includes three independent functions:

1. **hourly_snapshot_forwarder** - Hourly occupancy snapshots
   - recType: `io.microshare.lake.snapshot.hourly`
   - Schedule: Every hour at :00 (`0 0 * * * *`)
   - State table: `snapshotstate`

2. **people_counter_forwarder** - 15-minute people counter aggregates  
   - recType: `io.microshare.peoplecounter.unpacked.event.agg`
   - Schedule: Every 15 minutes (`0 */15 * * * *`)
   - State table: `peoplecounterstate`

3. **occupancy_sensor_forwarder** - Real-time motion sensor data
   - recType: `io.microshare.occupancy.unpacked`
   - Schedule: Every 5 minutes (`0 */5 * * * *`)
   - State table: `occupancysensorstate`

### Key Benefits

- **Independent schedules** - Each function runs on its own schedule
- **Isolated failures** - If one function fails, others continue unaffected
- **Separate state tracking** - Each uses its own Azure Table for state
- **Single deployment** - All functions deployed together (~$3/month total)
- **Easy monitoring** - Single Application Insights for all functions

### Enabling/Disabling Functions

By default, all three functions are active. To run **only the functions you need**, comment out unwanted functions in `function_app.py`:

#### Example: Run Only Hourly Snapshots

Edit `function_app.py` and comment out the functions you don't need:

```python
# KEEP: Hourly snapshots
@app.timer_trigger(schedule="0 0 * * * *", ...)
def hourly_snapshot_forwarder(mytimer):
    # ...function code...

# COMMENT OUT: People counter (not needed for this deployment)
# @app.timer_trigger(schedule="0 */15 * * * *", ...)
# def people_counter_forwarder(mytimer):
#     # ...function code...

# COMMENT OUT: Occupancy sensors (not needed for this deployment)
# @app.timer_trigger(schedule="0 */5 * * * *", ...)
# def occupancy_sensor_forwarder(mytimer):
#     # ...function code...
```

Redeploy after making changes:

```bash
func azure functionapp publish microshare-forwarder-func
```

### State Isolation

Each function uses a dedicated Azure Table to track its own state independently:

| Function | Table Name | Purpose |
|----------|------------|---------|
| `hourly_snapshot_forwarder` | `snapshotstate` | Track hourly snapshot fetch times |
| `people_counter_forwarder` | `peoplecounterstate` | Track people counter fetch times |
| `occupancy_sensor_forwarder` | `occupancysensorstate` | Track occupancy sensor fetch times |

Tables are **automatically created** on first execution in the same storage account (`AzureWebJobsStorage`).

**IMPORTANT:** Each function must use a unique `table_name` to prevent state conflicts:

```python
# Each function specifies its own table
state_mgr = StateManagerAzure(config, table_name='peoplecounterstate')
```

### Monitoring Multiple Functions

#### Azure Portal

Navigate to: **Function App → microshare-forwarder-func → Functions**

All active functions appear with:
- Independent execution history
- Separate success/failure metrics  
- Individual invocation logs

Click each function to view detailed metrics and logs.

#### Application Insights Queries

Filter logs for a specific function:

```kusto
traces
| where timestamp > ago(24h)
| where message contains "People Counter Forwarder"
| project timestamp, message, severityLevel
| order by timestamp desc
```

View all forwarder functions:

```kusto
traces
| where timestamp > ago(24h)
| where message contains "Forwarder"
| project timestamp, message, severityLevel
| order by timestamp desc
```

### Troubleshooting Multi-Function Setup

#### Functions Overwriting Each Other's State

**Symptom:** Functions show unexpected "last fetch time" or skip/duplicate data

**Cause:** Multiple functions using the same state table name

**Solution:** Verify each function specifies a unique `table_name`:

```python
# ✅ CORRECT - Each function has unique table
state_mgr = StateManagerAzure(config, table_name='snapshotstate')
state_mgr = StateManagerAzure(config, table_name='peoplecounterstate')

# ❌ WRONG - Both use default table (conflict!)
state_mgr = StateManagerAzure(config)  # Both functions would share state
```

#### Function Not Executing

Verify all functions are deployed:

```bash
az functionapp function list \
  --name microshare-forwarder-func \
  --resource-group rg-eh-playground \
  --query "[].{Name:name}" \
  --output table
```

Expected output should list all active functions.

### Cost Considerations

Running multiple functions increases execution count but remains cost-effective:

**Monthly execution estimates (Consumption plan):**
- 1 function (hourly): ~720 executions/month
- + People counter (15-min): ~2,880 executions/month
- + Occupancy sensors (5-min): ~8,640 executions/month
- **Total: ~12,240 executions/month = $3-5/month**

Consumption plan includes 1 million free executions/month, so you stay well within free tier.



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
