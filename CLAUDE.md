# Claude Code Reference

This file contains important context and references for Claude Code when working on this project.

## Project Overview

This is an Azure Functions project that fetches data from Microshare API and forwards it to Azure Event Hub. The **active production system** runs on Azure VM (`104.45.41.81`) using Azure Functions Core Tools (`func start`). The cloud Azure Function App exists but is NOT currently in production use.

## Essential Reading

### **[ARCHITECTURE.md](./ARCHITECTURE.md)** ⭐ START HERE
**This is the most important document for understanding the project architecture.**

It explains:
- What CT4111 is (development machine) vs Azure VM (active production)
- Where code lives and what each component does
- Data flow architecture
- Development workflow
- State management (local JSON files on VM)
- Future migration possibilities to cloud Function App

**Always refer to ARCHITECTURE.md when confused about:**
- Where to deploy code (answer: deploy to VM)
- What the Azure VM does (answer: runs active production system)
- How the Function App runtime works
- Where credentials are stored
- How to SSH to the VM

### Other Important Documents

- **[README.md](./README.md)** - Project features, security architecture, quick start
- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Step-by-step deployment instructions
- **[SECURITY.md](./SECURITY.md)** - Security architecture and threat model
- **[COST_OPTIMIZATION_AND_MIGRATION.md](./COST_OPTIMIZATION_AND_MIGRATION.md)** - Azure cost analysis and OVH VPS migration guide
- **[2025-11-14-1200_RECTYPE_FIX_AND_CLIENT_HUB_PAUSE.md](./2025-11-14-1200_RECTYPE_FIX_AND_CLIENT_HUB_PAUSE.md)** - recType field fix and client hub pause (2025-11-14)
- **[2025-11-13-1733_MONITORING_STATUS.md](./2025-11-13-1733_MONITORING_STATUS.md)** - Current monitoring status and bug tracking
- **[2025-11-13-1730_DUAL_HUB_FIX.md](./2025-11-13-1730_DUAL_HUB_FIX.md)** - Dual Event Hub bug investigation and resolution

## Quick Reference

### Current Location (CT4111)
```
/opt/projects/microshare-eventhub-function/
```
This is the **development machine** where you write and deploy Azure Function code.

### Azure Resources
- **VM (ACTIVE PRODUCTION)**: `microshare-forwarder-vm` (104.45.41.81)
  - Running: `func start --port 7072`
  - Location: `/opt/microshare-eventhub-function/`
  - State files: `/var/lib/microshare-forwarder/*.json`
- **Function App** (not in use): `microshare-forwarder-func` (UK South)
- **Event Hubs**:
  - Primary (test/monitoring): `ehns-playground-26767/ingress-test` (UK South)
  - Client (production): `occupancydata-dev-ehns/occupancydata-microshare-dev-function-eh` (UK South)
- **Resource Group**: `rg-eh-playground`

### Key Credentials
- Stored in `.env` (local development on CT4111)
- Same credentials on Azure VM at `/opt/microshare-eventhub-function/.env`
- **NOT** currently deployed as cloud Function App Settings (VM is active, not cloud)
- Username: `api_user@company.com`

### Common Tasks

#### Deploy Code to Production VM
```bash
# Copy updated files to VM
scp app/microshare_client.py azureuser@104.45.41.81:/opt/microshare-eventhub-function/app/
# Or deploy entire app directory
rsync -av --exclude='.env' app/ azureuser@104.45.41.81:/opt/microshare-eventhub-function/app/
# Function runtime auto-reloads, no restart needed
```

#### SSH to Production VM
```bash
ssh azureuser@104.45.41.81
```

#### Test Event Hub Consumer (Local)
```bash
python3 consumer.py          # Read all events from beginning
python3 consumer_latest.py   # Read only new events
```

#### Monitor VM Production Logs (real-time)
```bash
ssh azureuser@104.45.41.81 'tail -f /tmp/func-runtime-new.log'
```

#### Check VM Function Status
```bash
ssh azureuser@104.45.41.81 'ps aux | grep "func start" | grep -v grep'
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

### Active Production System (VM)
The Azure VM at `104.45.41.81` is the **ACTIVE PRODUCTION** system running modern Azure Functions code via `func start`.

**Key Details:**
- **NOT legacy/systemd** - runs current Azure Functions implementation
- Location: `/opt/microshare-eventhub-function/`
- Process: `func start --port 7072` (Azure Functions Core Tools)
- Logs: `/tmp/func-runtime-new.log`
- State: Local JSON files in `/var/lib/microshare-forwarder/`
- Dual Event Hub broadcasting enabled
- Handles both people counter (15min) and snapshots (hourly)

**Important**: All production code changes should be deployed to the VM. The cloud Azure Function App exists but is NOT in active use.

### Development Workflow
1. Edit code on CT4111 (`/opt/projects/microshare-eventhub-function/`)
2. Test locally (optional)
3. **Deploy to VM**: `scp` or `rsync` files to VM `/opt/microshare-eventhub-function/`
4. Monitor VM logs: `ssh azureuser@104.45.41.81 'tail -f /tmp/func-runtime-new.log'`
5. Commit to git on CT4111

**Note**: To deploy to cloud Function App (future), use: `func azure functionapp publish microshare-forwarder-func`

### State Management
- **VM** (active production): Local JSON files
  - `/var/lib/microshare-forwarder/peoplecounterstate.json`
  - `/var/lib/microshare-forwarder/snapshotstate.json`
- **Function App** (not in use): Would use Azure Table Storage if deployed to cloud

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
  - `eeefd9a` (2025-11-14 12:00 UTC): **Fix missing recType field in Event Hub events** ⭐ CRITICAL FIX
  - `c5c04c3` (2025-11-13 16:39 UTC): Enhanced logging for dual Event Hub broadcasting
  - `e3f561b` (2025-11-13 16:20 UTC): Add dual Event Hub broadcasting support
  - `99cafa7`: Add multi-function support for simultaneous recType processing
  - `aaf0cad`: Add multi-recType support with anonymized examples
- `.env` is gitignored (never commit credentials!)
- Test files (`consumer.py`, `consumer_latest.py`) not yet tracked

## Azure CLI Context

Logged in as: `cpaumelle@eroundit.eu`
Subscription: `Azure subscription 1` (fe17f352-cebf-4eb0-b9cc-31e8a0183a2b)

## Current System Status (as of 2025-11-14)

**Production System**: Azure VM (`104.45.41.81`)
- ✅ Running: `func start --port 7072`
- ✅ People Counter: Active (every 15 min)
- ✅ Snapshots: Active (hourly, when data available)
- ✅ recType field: **FIXED** (commit `eeefd9a`)
- ⏸️ Client Hub: **PAUSED for testing** (see `2025-11-14-1200_RECTYPE_FIX_AND_CLIENT_HUB_PAUSE.md`)
  - Primary hub (ingress-test): Active
  - Client hub (occupancydata-microshare-dev-function-eh): Paused
  - To re-enable: Follow steps in reference document

## When in Doubt

1. **Read [ARCHITECTURE.md](./ARCHITECTURE.md)** first (though note: it may need updating)
2. Check if you're working on the right machine:
   - **CT4111**: Development machine
   - **VM (104.45.41.81)**: ACTIVE production system
   - **Cloud Function App**: NOT in use
3. Verify credentials in `.env` match expected format
4. Test locally before deploying to VM
5. Deploy to VM, NOT to cloud Function App (unless migrating)
6. Use Azure CLI to inspect resources: `az eventhubs eventhub list`
