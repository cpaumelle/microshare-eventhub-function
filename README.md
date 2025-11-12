# Microshare to Azure Event Hub - Serverless Function

**Enterprise-grade secure serverless integration** that pulls occupancy snapshots from Microshare API and forwards them to Azure Event Hub using Azure Functions.

## Why This Approach is Secure

### Addressing Corporate IT Security Concerns

This solution is designed with enterprise security requirements in mind:

#### ✅ **No Inbound Attack Surface**
- **Outbound-only connections** - Function initiates all communication (pull model)
- **No exposed endpoints** - No public APIs or webhooks to secure
- **No firewall rules required** - No inbound ports to manage or protect
- **Zero IP whitelisting** - Eliminates IP management overhead and security gaps

#### ✅ **Complete Infrastructure Control**
- **100% within your Azure tenant** - All code, data, and credentials under your control
- **No third-party hosting** - No external services or middleware in the data path
- **Azure admin deploys and manages** - Full visibility and control via Azure Portal/CLI
- **Your subscription, your rules** - Apply your organization's policies and governance

#### ✅ **Industry-Standard Encryption & Authentication**
- **HTTPS/TLS 1.3 encryption** - All API communication encrypted end-to-end
- **Microshare JWT tokens** - Industry-standard authentication with automatic token refresh
- **Certificate-based trust** - Public certificate validation, no custom certificate management
- **Azure-managed secrets** - Credentials encrypted at rest in Azure Key Vault-backed app settings

#### ✅ **Minimal Attack Surface**
- **Serverless architecture** - No persistent VMs to patch, harden, or secure
- **Ephemeral execution** - Function instances spin up, execute, and terminate
- **Automatic runtime updates** - Microsoft manages Python runtime and security patches
- **No OS-level access** - No SSH, RDP, or shell access to compromise

#### ✅ **Built-in Compliance & Auditing**
- **Application Insights logging** - Complete audit trail of all executions
- **Azure Monitor integration** - Centralized logging with your existing SIEM
- **Azure Policy support** - Enforce organizational compliance rules
- **SOC 2, ISO 27001, HIPAA** - Azure Functions inherits Azure's compliance certifications

#### ✅ **Defense in Depth**
- **Network isolation (optional)** - Deploy to VNet with private endpoints
- **Managed Identity (optional)** - Eliminate connection strings entirely
- **IP restrictions (optional)** - Lock down function to specific IPs
- **Azure Private Link (optional)** - Keep traffic entirely on Microsoft backbone

### Security Comparison: Functions vs Other Methods

### Easy to Deploy & Maintain

**15-Minute Deployment** - Unlike complex VM setups:
- ✅ **5 CLI commands** to deploy (no complex configuration)
- ✅ **No OS installation** or hardening required
- ✅ **No firewall rules** to configure or test
- ✅ **No certificate management** (Microshare uses public CAs)
- ✅ **Zero ongoing maintenance** - Microsoft manages patches and updates
- ✅ **Deploy from laptop** - No need for jump boxes or bastion hosts

**IT Security teams love it because:**
- Security review is straightforward (outbound-only, standard Azure)
- No ongoing security maintenance burden
- Fits existing Azure governance and compliance
- Audit trail built-in via Application Insights
- Easy to demonstrate compliance to auditors

| Security Concern | This Solution | Alternative Approaches |
|-----------------|---------------|----------------------|
| **Inbound firewall rules** | ✅ None required | ❌ VMs require open ports |
| **OS patching** | ✅ Microsoft managed | ❌ Manual patching required |
| **Secret management** | ✅ Azure encrypted settings | ⚠️ Often stored in config files |
| **Infrastructure control** | ✅ 100% your Azure tenant | ❌ Third-party SaaS or middleware |
| **Audit trail** | ✅ Application Insights built-in | ⚠️ Manual logging setup |
| **Attack surface** | ✅ Minimal (ephemeral execution) | ❌ Persistent VMs/containers |
| **Compliance certifications** | ✅ Inherits Azure certifications | ⚠️ Depends on hosting |

## Architecture

```
┌─────────────────────────────────┐
│     Microshare API              │
│  (HTTPS/TLS 1.3 + JWT tokens)   │
└────────────┬────────────────────┘
             │ Outbound HTTPS only
             │ (Port 443)
             │
        [Timer Trigger]
        Every hour at :00
             │
┌────────────▼────────────────────┐
│    Azure Function               │
│    (Your Azure Tenant)          │
│  ┌──────────────────────────┐   │
│  │ Serverless Python 3.11   │   │
│  │ - Fetch data             │   │
│  │ - Track state            │   │
│  │ - Deduplicate            │   │
│  └──────────────────────────┘   │
│  Ephemeral execution (no VM)    │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│  Azure Table Storage            │
│  (State persistence)            │
│  - Encrypted at rest            │
│  - Your subscription            │
└─────────────────────────────────┘
             │
┌────────────▼────────────────────┐
│  Azure Event Hub                │
│  (Data ingress)                 │
│  - Your Event Hub namespace     │
│  - Full RBAC control            │
└─────────────────────────────────┘
```

**Security Benefits:**
- All components within your Azure tenant
- No data leaves your control
- No third-party services in data path
- Standard Azure security controls apply

## Features

✅ **Outbound-only security model** - No inbound firewall rules  
✅ **Enterprise authentication** - HTTPS + JWT tokens from Microshare  
✅ **Full Azure control** - Deploy and manage via Azure Portal/CLI  
✅ **Encrypted secrets** - Credentials stored in Azure app settings  
✅ **Automatic scheduling** - Runs hourly via timer trigger  
✅ **State persistence** - Azure Table Storage tracks last fetch time  
✅ **Deduplication** - Prevents sending duplicate snapshots  
✅ **Complete audit trail** - Application Insights logging  
✅ **Zero maintenance** - Microsoft manages runtime and patches  

## Quick Start

### Prerequisites

- Azure subscription with permissions for:
  - Storage Accounts
  - Function Apps
  - Event Hubs
- Azure CLI installed
- Azure Functions Core Tools v4
- Microshare API credentials (JWT-authenticated)
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

# 5. Configure environment variables (encrypted by Azure)
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

**That's it!** Your function will run automatically every hour with enterprise security.

## Detailed Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide with troubleshooting
- **[SECURITY.md](SECURITY.md)** - Detailed security architecture and best practices

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

Required settings (configured as Function App settings, encrypted by Azure):

| Variable | Description | Example |
|----------|-------------|---------|
| `MICROSHARE_USERNAME` | Microshare API username | `user@company.com` |
| `MICROSHARE_PASSWORD` | Microshare API password | `your_password` |
| `MICROSHARE_API_KEY` | Microshare API key (JWT) | `UUID-format-key` |
| `MICROSHARE_DATA_CONTEXT` | Data context filter | `CBRE` |
| `EVENT_HUB_CONNECTION_STRING` | Event Hub connection with EntityPath | `Endpoint=sb://...;EntityPath=hub` |
| `LOG_LEVEL` | Logging level | `INFO` or `DEBUG` |

**Security Note:** All settings are encrypted at rest by Azure and never appear in code or logs.

### Application Settings

Edit `config.yaml` to customize:

- Microshare view ID
- Location filters
- API timeouts
- Retry configuration

## Monitoring & Audit Trail

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
- **Authentication Events:** All API calls logged

### Audit Trail

Application Insights provides:
- Complete execution history
- API authentication attempts
- Error conditions and retries
- Data volume metrics
- Performance telemetry

## Cost Efficiency

**Monthly Cost: ~$3**

| Component | Cost |
|-----------|------|
| Function executions (720/month) | FREE* |
| Execution time (~2.5 hours/month) | FREE* |
| Storage Account (Standard LRS) | ~$2 |
| Application Insights | ~$1 |

*Azure Functions includes 1M free executions and 400,000 GB-s free per month

**Compare to VM alternatives:** $50-100/month plus patching overhead

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
│   ├── microshare_client.py  # Microshare API client (JWT auth)
│   ├── eventhub_client.py    # Event Hub client
│   └── state_manager_azure.py# Azure Table Storage state mgmt
├── host.json                 # Function runtime config
├── requirements.txt          # Python dependencies
├── config.yaml               # Application configuration
├── .env.example              # Template for credentials
├── DEPLOYMENT.md             # Detailed deployment guide
└── SECURITY.md               # Security documentation
```

## Enhanced Security Options

For additional security hardening:

### Option 1: Managed Identity (Eliminate Connection Strings)
```bash
# Enable system-assigned identity
az functionapp identity assign --name <function-name> --resource-group <rg>

# Grant Event Hub permissions via RBAC
az role assignment create \
  --assignee <function-principal-id> \
  --role "Azure Event Hubs Data Sender" \
  --scope <event-hub-resource-id>
```

### Option 2: VNet Integration (Private Network)
```bash
# Deploy function to VNet with private endpoints
az functionapp vnet-integration add \
  --name <function-name> \
  --resource-group <rg> \
  --vnet <vnet-name> \
  --subnet <subnet-name>
```

### Option 3: IP Restrictions
```bash
# Lock down function to specific corporate IPs
az functionapp config access-restriction add \
  --name <function-name> \
  --resource-group <rg> \
  --rule-name "CorporateNetwork" \
  --priority 100 \
  --ip-address <ip-range>
```

See [SECURITY.md](SECURITY.md) for detailed security architecture and best practices.

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
