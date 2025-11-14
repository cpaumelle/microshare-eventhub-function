# Claude Code Reference

This file contains important context and references for Claude Code when working on this project.

## Project Overview

This is an Azure Functions project that fetches data from Microshare API and forwards it to Azure Event Hub. It's a serverless replacement for a legacy VM-based systemd deployment.

## Essential Reading

### **[ARCHITECTURE.md](./ARCHITECTURE.md)** ⭐ START HERE
**This is the most important document for understanding the project architecture.**

It explains:
- What CT4111 is (development machine) vs Azure VM (legacy) vs Azure Function App (new production)
- Where code lives and what each component does
- Data flow architecture
- Development workflow
- State management differences
- Migration plan from VM to serverless

**Always refer to ARCHITECTURE.md when confused about:**
- Where to deploy code
- What the Azure VM is for
- How the Azure Function App works
- Where credentials are stored
- How to SSH between components

### Other Important Documents

- **[README.md](./README.md)** - Project features, security architecture, quick start
- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Step-by-step deployment instructions
- **[SECURITY.md](./SECURITY.md)** - Security architecture and threat model
- **[COST_OPTIMIZATION_AND_MIGRATION.md](./COST_OPTIMIZATION_AND_MIGRATION.md)** - Azure cost analysis and OVH VPS migration guide
- **[2025-11-13-1733_MONITORING_STATUS.md](./2025-11-13-1733_MONITORING_STATUS.md)** - Current monitoring status and bug tracking
- **[2025-11-13-1730_DUAL_HUB_FIX.md](./2025-11-13-1730_DUAL_HUB_FIX.md)** - Dual Event Hub bug investigation and resolution

## Quick Reference

### Current Location (CT4111)
```
/opt/projects/microshare-eventhub-function/
```
This is the **development machine** where you write and deploy Azure Function code.

### Azure Resources
- **Function App**: `microshare-forwarder-func` (UK South)
- **Event Hubs**:
  - Primary (test/monitoring): `ehns-playground-26767/ingress-test` (UK South)
  - Client (production): `occupancydata-dev-ehns/occupancydata-microshare-dev-function-eh` (UK South)
- **Resource Group**: `rg-eh-playground`
- **VM** (legacy): `microshare-forwarder-vm` (104.45.41.81)

### Key Credentials
- Stored in `.env` (local development)
- Same credentials on Azure VM at `/opt/occupancy-snapshot/.env`
- Deployed as Function App Settings in Azure
- Username: `api_user@company.com`

### Common Tasks

#### Deploy to Azure Function App
```bash
func azure functionapp publish microshare-forwarder-func
```

#### SSH to Azure VM (legacy)
```bash
ssh azureuser@104.45.41.81
```

#### Test Event Hub Consumer
```bash
python tests/consumer.py
```

#### View Azure Function Logs
```bash
az functionapp logs tail --name microshare-forwarder-func --resource-group rg-eh-playground
```

#### Monitor VM Runtime Logs (real-time)
```bash
ssh azureuser@104.45.41.81 'tail -f /tmp/func-runtime.log'
```

#### Check State Files (VM)
```bash
ssh azureuser@104.45.41.81 'cat /var/lib/microshare-forwarder/peoplecounterstate.json'
ssh azureuser@104.45.41.81 'cat /var/lib/microshare-forwarder/snapshotstate.json'
```

## Project Structure

```
.
├── function_app.py           # Azure Function entry point (timer triggers)
├── app/
│   ├── forwarder.py          # Core forwarding logic
│   ├── microshare_client.py  # Microshare API client (JWT auth)
│   ├── eventhub_client.py    # Azure Event Hub client
│   ├── state_manager_azure.py # Azure Table Storage state
│   └── config.py             # Configuration loader
├── tests/
│   ├── producer.py           # Test producer (send to Event Hub)
│   └── consumer.py           # Test consumer (read from Event Hub)
├── .env                      # Credentials (NOT in git)
├── config.yaml               # Application configuration
└── requirements.txt          # Python dependencies
```

## Important Notes

### Multi-recType Support
The Function App runs **2 independent timer functions**:
1. `hourly_snapshot_forwarder` - Every hour (:00) - `io.microshare.lake.snapshot.hourly`
2. `people_counter_forwarder` - Every 15 minutes - `io.microshare.peoplecounter.unpacked.event.agg`

Each uses a separate Azure Table for state tracking (`snapshotstate` and `peoplecounterstate`).

### Dual Event Hub Broadcasting
The system sends data to **BOTH Event Hubs simultaneously**:
- Primary hub: For testing and monitoring (ingress-test)
- Client hub: For production client access (occupancydata-microshare-dev-function-eh)

Configuration uses `EVENT_HUB_CONNECTION_STRING` (single) + `EVENT_HUB_CONNECTION_STRINGS` (JSON array).
Enhanced INFO-level logging shows "MULTI-HUB BROADCASTING" messages and delivery confirmations for each hub.

**Recent Issue (2025-11-13)**: JSON array parsing failure caused 48-minute downtime (16:39-17:27 UTC).
Resolved by runtime restart. System auto-recovered missed data via state management.
See `2025-11-13-1730_DUAL_HUB_FIX.md` for details.

### Legacy VM
The Azure VM at `104.45.41.81` runs the **old systemd-based forwarder**. It's still operational but being phased out in favor of the Azure Function App. Don't make changes there unless explicitly asked.

### Development Workflow
1. Edit code on CT4111
2. Test locally (optional)
3. Deploy to Function App: `func azure functionapp publish microshare-forwarder-func`
4. Monitor logs in Azure Portal or via CLI

### State Management
- **VM** (legacy): Local JSON file `/var/lib/microshare-forwarder/state.json`
- **Function App** (new): Azure Table Storage (`snapshotstate`, `peoplecounterstate`, `occupancystate`)

## Environment Variables

Required in `.env`:
```bash
MICROSHARE_USERNAME              # Microshare API username
MICROSHARE_PASSWORD              # Microshare API password
MICROSHARE_API_KEY               # Microshare API key (UUID)
MICROSHARE_DATA_CONTEXT          # Data context (e.g., "COMPANY")
EVENT_HUB_CONNECTION_STRING      # Primary Event Hub connection string with EntityPath
EVENT_HUB_CONNECTION_STRINGS     # Additional Event Hubs (JSON array format)
                                 # Example: ["Endpoint=sb://...;EntityPath=hub2"]
LOG_LEVEL                        # INFO, DEBUG, WARNING, ERROR
```

**Dual Event Hub Configuration**:
- `EVENT_HUB_CONNECTION_STRING`: Primary hub (always used)
- `EVENT_HUB_CONNECTION_STRINGS`: JSON array of additional hubs (optional)
- Data is sent to ALL configured hubs simultaneously
- Config parser automatically detects and parses JSON arrays

## Git Repository

- Current branch: `main`
- Recent commits:
  - `c5c04c3` (2025-11-13 16:39 UTC): Enhanced logging for dual Event Hub broadcasting
  - `e3f561b` (2025-11-13 16:20 UTC): Add dual Event Hub broadcasting support
  - `99cafa7`: Add multi-function support for simultaneous recType processing
  - `aaf0cad`: Add multi-recType support with anonymized examples
- `.env` is gitignored (never commit credentials!)
- `tests/` directory not yet tracked

## Azure CLI Context

Logged in as: `cpaumelle@eroundit.eu`
Subscription: `Azure subscription 1` (fe17f352-cebf-4eb0-b9cc-31e8a0183a2b)

## When in Doubt

1. **Read [ARCHITECTURE.md](./ARCHITECTURE.md)** first
2. Check if you're working on the right machine (CT4111 vs VM vs Function App)
3. Verify credentials in `.env` match expected format
4. Test locally before deploying
5. Use Azure CLI to inspect resources: `az functionapp list`, `az eventhubs eventhub list`
