# Microshare to Azure Event Hub – Serverless Function

This Azure Function enables Microshare™ customers to securely and reliably retrieve data from the Microshare™ API and forward it to Azure Event Hub. The solution runs entirely within the customer’s Azure tenant and uses a serverless, outbound-only design with no inbound network exposure.

## Features

- **Outbound-only communication**: The function initiates all HTTPS requests; no inbound ports or public endpoints are used.
- **Microshare™ API integration**: Authenticates using JWT tokens over TLS 1.3.
- **Serverless execution**: Runs on Azure Functions (Python 3.11) with no VMs or containers to manage.
- **Automatic scheduling**: Executes on an hourly timer trigger (configurable).
- **State tracking**: Uses Azure Table Storage to store the last successful fetch timestamp.
- **Deduplication**: Ensures only new snapshots are forwarded to Event Hub.
- **Azure-native logging**: Application Insights provides full execution logs, metrics, and telemetry.
- **Encrypted configuration**: All secrets stored as Azure Function App settings, encrypted at rest.

## Security Architecture

### No Inbound Attack Surface

- No webhooks, callbacks, or public endpoints.
- No inbound firewall rules or listener ports.
- All communication is outbound HTTPS on port 443.

### Runs Entirely in Customer’s Azure Tenant

- All compute, storage, and messaging resources reside in the customer’s subscription.
- No third-party infrastructure is involved in the data path.

### Encryption & Authentication

- TLS 1.3 for all API communication.
- Microshare™ JWT authentication with automatic token refresh.
- Function App settings encrypted at rest with Azure-managed keys.

### Minimal Attack Surface

- Ephemeral compute: Function instances start, execute, and shut down automatically.
- No operating system to patch, maintain, or access (no SSH/RDP).
- Azure manages all runtime and security updates.

### Auditing & Compliance

- Application Insights captures execution history, API calls, errors, and timing.
- Logs and metrics integrate with Azure Monitor and SIEM systems.
- Azure Functions inherit Azure’s platform certifications (SOC 2, ISO 27001, HIPAA, and others).

## Architecture

```
┌─────────────────────────────────┐
│     Microshare API              │
│  (HTTPS/TLS 1.3 + JWT tokens)   │
└────────────┬────────────────────┘
             │ Outbound HTTPS only
             │
        [Timer Trigger]
        Every hour
             │
┌────────────▼────────────────────┐
│        Azure Function           │
│   (Python 3.11, serverless)     │
│  - Fetch data                   │
│  - Track state                  │
│  - Deduplicate                  │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│   Azure Table Storage           │
│     (State persistence)         │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│        Azure Event Hub          │
│        (Data ingestion)         │
└─────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Azure subscription with permissions for:
  - Storage Accounts
  - Function Apps
  - Event Hubs
- Azure CLI
- Azure Functions Core Tools v4
- Microshare™ API credentials
- Event Hub connection string

### Deployment

```bash
# Authenticate with Azure
az login

# Create storage account
az storage account create   --name <storage-name>   --resource-group <resource-group>   --location <region>   --sku Standard_LRS

# Create Function App
az functionapp create   --name <function-name>   --storage-account <storage-name>   --resource-group <resource-group>   --consumption-plan-location <region>   --runtime python   --runtime-version 3.11   --functions-version 4   --os-type Linux

# Deploy code
func azure functionapp publish <function-name>

# Configure application settings
az functionapp config appsettings set   --name <function-name>   --resource-group <resource-group>   --settings     MICROSHARE_USERNAME="your_username"     MICROSHARE_PASSWORD="your_password"     MICROSHARE_API_KEY="your_api_key"     MICROSHARE_DATA_CONTEXT="your_context"     EVENT_HUB_CONNECTION_STRING="your_connection_string"     LOG_LEVEL="INFO"
```

## Configuration

### Schedule

Default schedule: hourly (`0 0 * * * *`)

Configurable in `function_app.py`.

### Environment Variables

| Variable | Description |
| --- | --- |
| `MICROSHARE_USERNAME` | Microshare API username |
| `MICROSHARE_PASSWORD` | Microshare API password |
| `MICROSHARE_API_KEY` | Microshare API key (JWT) |
| `MICROSHARE_DATA_CONTEXT` | Data context filter |
| `EVENT_HUB_CONNECTION_STRING` | Event Hub connection string including `EntityPath` |
| `LOG_LEVEL` | Logging level (INFO/DEBUG) |

## Monitoring

- Application Insights provides logs, traces, exceptions, dependencies, and performance metrics.
- Azure Monitor can aggregate logs into dashboards or SIEM tools.
- Kusto queries allow filtering by timestamp, message content, or severity.

Example:

```kusto
traces
| where timestamp > ago(24h)
| where message contains "Microshare"
| order by timestamp desc
```

## Troubleshooting

- Validate Function App state using `az functionapp show`.
- Verify application settings via `az functionapp config appsettings list`.
- Check for errors in Application Insights.
- Confirm Event Hub connection string contains an `EntityPath`.
- Review state table entries for last fetch timestamps.

## Development

```bash
pip install -r requirements.txt
cp .env.example .env
func start
```

## Project Structure

```
├── function_app.py
├── app/
│   ├── config.py
│   ├── microshare_client.py
│   ├── eventhub_client.py
│   └── state_manager_azure.py
├── host.json
├── requirements.txt
├── config.yaml
├── .env.example
├── DEPLOYMENT.md
└── SECURITY.md
```

## Optional Security Enhancements

### Managed Identity (no connection strings)

- Enable system-assigned identity
- Assign Event Hub Data Sender role

### VNet Integration

- Deploy Function App with VNet integration
- Use private endpoints for storage and Event Hub

### IP Restrictions

- Add IP allowlists via Function App access restriction rules

## License

© Microshare 2025. All rights reserved.
