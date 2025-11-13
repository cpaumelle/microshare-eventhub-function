# Architecture Overview: CT4111 vs Azure VM vs Azure Resources

This document clarifies the role and location of each component in the Microshare to Event Hub integration system.

## Quick Summary

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| **CT4111** | Local development machine | Development environment for Azure Function code | Active (you are here) |
| **Azure VM** | Azure (`microshare-forwarder-vm`) | **OLD** systemd-based forwarder (legacy) | Running but being replaced |
| **Azure Function App** | Azure (`microshare-forwarder-func`) | **NEW** serverless forwarder (target deployment) | Deployed and running |
| **Azure Event Hub** | Azure (`ehns-playground-26767/ingress-test`) | Message broker for all data | Active |

---

## Detailed Component Breakdown

### 1. CT4111 (This Machine)
**Path**: `/opt/projects/microshare-eventhub-function`
**Type**: Development/deployment workstation
**OS**: Proxmox LXC Container (Linux)

#### What's Here:
- **Azure Function source code** (`function_app.py`, `app/` directory)
- **Development tools** (Python virtual env, Azure CLI, git)
- **Configuration files** (`.env`, `config.yaml`)
- **Testing tools** (`tests/producer.py`, `tests/consumer.py`)
- **Documentation** (README, DEPLOYMENT, SECURITY docs)

#### Purpose:
- Write and test Azure Function code locally
- Deploy to Azure Function App using Azure CLI/Core Tools
- Run tests against Event Hub
- SSH into Azure VM for troubleshooting

#### Key Files:
```
/opt/projects/microshare-eventhub-function/
├── function_app.py           # Main Azure Function entry point
├── app/
│   ├── forwarder.py          # Core forwarder logic
│   ├── microshare_client.py  # Microshare API client
│   ├── eventhub_client.py    # Event Hub client
│   ├── state_manager_azure.py # Azure Table state storage
│   └── config.py             # Config loader
├── .env                      # Credentials (same as VM)
├── config.yaml               # App settings
└── requirements.txt          # Python dependencies
```

---

### 2. Azure VM: `microshare-forwarder-vm`
**IP**: `104.45.41.81`
**Path**: `/opt/occupancy-snapshot`
**Type**: Ubuntu 22.04 VM (Standard B1s)
**Status**: **LEGACY DEPLOYMENT** (being replaced)

#### What's Here:
- **OLD systemd-based forwarder** (runs hourly via cron)
- Same core logic as Function App (different execution model)
- State stored in local JSON file: `/var/lib/microshare-forwarder/state.json`

#### Purpose:
- **Original production deployment** (VM-based approach)
- Runs `python3 -m app.forwarder` every hour via systemd timer
- Being **migrated to Azure Functions** for serverless benefits

#### Key Files on VM:
```
/opt/occupancy-snapshot/
├── app/forwarder.py          # Main script (systemd execution)
├── .env                      # Same credentials as CT4111
├── systemd/
│   ├── microshare-forwarder.service
│   └── microshare-forwarder.timer (hourly schedule)
└── /var/lib/microshare-forwarder/
    └── state.json            # Local state file
```

#### Why It's Being Replaced:
- **Manual maintenance**: OS patching, Python updates, systemd management
- **Single point of failure**: If VM is down, no data flows
- **Scaling limitations**: Can't easily scale or add new data types
- **Cost**: Always-on VM vs pay-per-execution functions

---

### 3. Azure Function App: `microshare-forwarder-func`
**URL**: `microshare-forwarder-func.azurewebsites.net`
**Location**: UK South
**Type**: Linux Consumption Plan (serverless)
**Status**: **DEPLOYED AND RUNNING** (NEW PRODUCTION)

#### What's Here:
- **Deployed Python code** from CT4111
- Runs multiple timer-triggered functions:
  - `hourly_snapshot_forwarder` (every hour at :00)
  - `peoplecounter_forwarder` (every 15 minutes)
  - `occupancy_forwarder` (every 5 minutes)
- State stored in **Azure Table Storage** (not local files)

#### Purpose:
- **Serverless replacement** for VM-based forwarder
- Automatically scales, no OS maintenance
- Multiple independent functions for different data types
- Azure-native logging (Application Insights)

#### Execution Flow:
```
Azure Timer Trigger
        ↓
Function App starts (cold start or warm instance)
        ↓
Load config from App Settings (.env variables)
        ↓
Fetch last state from Azure Table Storage
        ↓
Call Microshare API (JWT auth, pagination loop)
        ↓
Forward events to Event Hub
        ↓
Save new state to Azure Table Storage
        ↓
Function terminates (serverless)
```

#### Configuration:
- **Environment variables**: Stored as Function App Settings (Azure portal)
- **State storage**: Azure Table Storage (`snapshotstate`, `peoplecounterstate`, `occupancystate`)
- **Logging**: Application Insights (automatic)

---

### 4. Azure Event Hub: `ehns-playground-26767/ingress-test`
**Namespace**: `ehns-playground-26767.servicebus.windows.net`
**Hub Name**: `ingress-test`
**Type**: Standard tier, 4 partitions
**Status**: **PRODUCTION** (receives data from both VM and Function)

#### What's Here:
- Message broker that receives occupancy events
- Retains messages for 1 day
- Supports Kafka protocol (can use Kafka clients)

#### Purpose:
- **Central data ingestion point** for all Microshare data
- Decouples data producers (VM, Function) from consumers
- Enables multiple downstream consumers (analytics, storage, etc.)

#### Connection:
- Both VM and Function App use **connection string authentication**
- Connection string includes: `Endpoint`, `SharedAccessKey`, `EntityPath`

---

## Data Flow Architecture

### Current State (Dual Deployment)
```
                    Microshare API
                    (api.share.microshare.io)
                           ↓
                    [JWT Authentication]
                           ↓
            ┌──────────────┴──────────────┐
            ↓                              ↓
    Azure VM (LEGACY)              Azure Function App (NEW)
    systemd timer hourly           Timer triggers (hourly, 15min, 5min)
    /opt/occupancy-snapshot        microshare-forwarder-func
            ↓                              ↓
            └──────────────┬──────────────┘
                           ↓
                  Azure Event Hub
                  ehns-playground-26767
                  Hub: ingress-test
                           ↓
                  [Downstream Consumers]
                  (Analytics, Storage, etc.)
```

### Target State (After VM Decommission)
```
    Microshare API
         ↓
    Azure Function App
    (Multiple timer functions)
         ↓
    Azure Event Hub
         ↓
    Downstream Consumers
```

---

## Development Workflow

### Typical Development Cycle on CT4111

1. **Edit code** in `/opt/projects/microshare-eventhub-function/`
   ```bash
   nano function_app.py
   nano app/forwarder.py
   ```

2. **Test locally** (if needed)
   ```bash
   cd /opt/projects/microshare-eventhub-function
   source .venv/bin/activate
   python -m app.forwarder  # Direct execution
   ```

3. **Deploy to Azure Function App**
   ```bash
   func azure functionapp publish microshare-forwarder-func
   ```

4. **Monitor execution**
   ```bash
   # Azure portal → Function App → Logs
   # Or use Azure CLI:
   az functionapp logs tail --name microshare-forwarder-func --resource-group rg-eh-playground
   ```

5. **Test Event Hub data**
   ```bash
   python tests/consumer.py  # Consume from Event Hub
   ```

---

## SSH Access Between Components

### From CT4111 to Azure VM
```bash
ssh azureuser@104.45.41.81
```
- **Purpose**: Troubleshoot legacy VM deployment
- **Authentication**: SSH key (`~/.ssh/id_rsa`)
- **Common tasks**:
  - Check systemd status: `systemctl status microshare-forwarder.service`
  - View logs: `journalctl -u microshare-forwarder.service -f`
  - Check state: `cat /var/lib/microshare-forwarder/state.json`

---

## State Management Differences

### VM Approach (Legacy)
- **Storage**: Local JSON file (`/var/lib/microshare-forwarder/state.json`)
- **Persistence**: Survives VM restarts
- **Limitations**: Single VM only, no high availability
- **Format**:
  ```json
  {
    "last_fetch_timestamp": "2025-11-13T10:00:00",
    "total_snapshots_sent": 1500,
    "total_duplicates_skipped": 25
  }
  ```

### Function App Approach (NEW)
- **Storage**: Azure Table Storage (separate tables per data type)
- **Persistence**: Cloud-native, high availability
- **Scalability**: Multiple function instances can share state
- **Tables**:
  - `snapshotstate` (hourly snapshots)
  - `peoplecounterstate` (15-min people counter)

---

## Key Differences: VM vs Function App

| Aspect | VM Deployment | Function App Deployment |
|--------|---------------|------------------------|
| **Execution** | Systemd timer (cron-like) | Timer trigger (serverless) |
| **Scaling** | Manual (resize VM) | Automatic (Azure manages) |
| **Availability** | Single VM (SPOF) | High availability (Azure SLA) |
| **Maintenance** | OS patches, Python updates | Zero maintenance (Azure managed) |
| **Cost** | Always-on VM (~$10/month) | Pay-per-execution (~$0.20/million) |
| **State** | Local JSON file | Azure Table Storage |
| **Monitoring** | Journalctl logs | Application Insights |
| **Deployment** | Git pull + systemd restart | `func azure functionapp publish` |
| **Multi-recType** | Single cron job | Multiple independent functions |

---

## Credentials and Secrets

### Where Credentials Are Stored

#### CT4111 (Development)
- **File**: `/opt/projects/microshare-eventhub-function/.env`
- **Format**: Key-value pairs
- **Security**: File permissions 600, not tracked in git

#### Azure VM (Legacy)
- **File**: `/opt/occupancy-snapshot/.env`
- **Format**: Same as CT4111
- **Security**: File permissions 600, sudo required

#### Azure Function App (Production)
- **Location**: Function App Settings (Azure Portal)
- **Format**: Environment variables
- **Security**: Encrypted at rest, accessed via Azure RBAC
- **Access**: `az functionapp config appsettings list`

### Credential Contents
```bash
# Microshare API
MICROSHARE_USERNAME=api_user@company.com
MICROSHARE_PASSWORD=fth41ZlrZM2M
MICROSHARE_API_KEY=BF78C881-BB1E-465F-BE79-F7A45BB2366F
MICROSHARE_DATA_CONTEXT=COMPANY

# Azure Event Hub
EVENT_HUB_CONNECTION_STRING=Endpoint=sb://ehns-playground-26767...

# Logging
LOG_LEVEL=INFO
```

---

## What You Should Work On

### On CT4111 (This Machine)
- ✅ **Edit Azure Function code** (`function_app.py`, `app/`)
- ✅ **Test changes locally** (if possible)
- ✅ **Deploy to Azure Function App**
- ✅ **Write/run tests** (`tests/`)
- ✅ **Update documentation**

### On Azure VM (Rare)
- ⚠️ **Troubleshoot legacy deployment** (if still needed)
- ⚠️ **Compare behavior** between VM and Function
- ⚠️ **Eventually decommission** (once Function is stable)

### On Azure Function App
- ✅ **Monitor production logs** (Application Insights)
- ✅ **Adjust timer schedules** (if needed)
- ✅ **Scale configuration** (retention, throughput)

---

## Next Steps / Migration Plan

1. ✅ **Deploy Azure Function App** (DONE - running)
2. ✅ **Add multi-recType support** (DONE - 3 functions deployed)
3. 🔄 **Monitor both VM and Function in parallel** (validate Function works)
4. ⏳ **Disable VM systemd timer** (once Function is proven stable)
5. ⏳ **Decommission VM** (or repurpose for other tasks)
6. ⏳ **Remove VM-specific code** from CT4111 repo

---

## Useful Commands Reference

### CT4111 Commands
```bash
# Deploy to Function App
cd /opt/projects/microshare-eventhub-function
func azure functionapp publish microshare-forwarder-func

# Test Event Hub consumer
python tests/consumer.py

# SSH to VM
ssh azureuser@104.45.41.81

# Check Azure resources
az functionapp list --output table
az eventhubs eventhub list --namespace-name ehns-playground-26767 --output table
```

### Azure VM Commands (via SSH)
```bash
# Check service status
systemctl status microshare-forwarder.timer
systemctl status microshare-forwarder.service

# View logs
journalctl -u microshare-forwarder.service -f

# Check state
cat /var/lib/microshare-forwarder/state.json | jq

# Manual run
cd /opt/occupancy-snapshot
sudo python3 -m app.forwarder
```

### Azure CLI Commands (from CT4111)
```bash
# Function App logs
az functionapp logs tail --name microshare-forwarder-func --resource-group rg-eh-playground

# Function list
az functionapp function list --name microshare-forwarder-func --resource-group rg-eh-playground

# Event Hub info
az eventhubs eventhub show --name ingress-test --namespace-name ehns-playground-26767 --resource-group rg-eh-playground
```

---

## Summary

**CT4111** = Your development machine with Azure Function code
**Azure VM** = Legacy systemd-based forwarder (being phased out)
**Azure Function App** = New serverless forwarder (production target)
**Azure Event Hub** = Central message broker for all data

You should primarily work on **CT4111** to develop and deploy to the **Azure Function App**. The **Azure VM** is legacy and will eventually be decommissioned.
