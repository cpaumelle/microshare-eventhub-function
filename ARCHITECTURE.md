# Architecture Overview: CT4111 vs Azure VM vs Azure Resources

**Last Updated**: 2025-11-14

This document clarifies the role and location of each component in the Microshare to Event Hub integration system.

## Quick Summary

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| **CT4111** | Local development machine (LXC container) | Development environment for Azure Function code | Active (you are here) |
| **Azure VM** | Azure (`microshare-forwarder-vm`, 104.45.41.81) | **ACTIVE PRODUCTION** - Runs Azure Functions via Core Tools | Production (running) |
| **Azure Function App** | Azure (`microshare-forwarder-func`) | Cloud Function App (exists but NOT in use) | Deployed but inactive |
| **Azure Event Hub** | Azure (UK South) | Message broker for all data | Active (dual-hub capable) |

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

### 2. Azure VM: `microshare-forwarder-vm` ⭐ **ACTIVE PRODUCTION**
**IP**: `104.45.41.81`
**Path**: `/opt/microshare-eventhub-function/`
**Type**: Ubuntu 22.04 VM (Standard B1s)
**Status**: **ACTIVE PRODUCTION SYSTEM**

#### What's Here:
- **Modern Azure Functions code** (same as CT4111, runs via `func start`)
- **NOT legacy systemd** - uses Azure Functions Core Tools runtime
- Two independent timer functions:
  - `people_counter_forwarder` - Every 15 minutes
  - `hourly_snapshot_forwarder` - Every hour at :00
- State stored in local JSON files (auto-detected, not Azure Table)

#### Purpose:
- **Current production deployment** running Azure Functions locally on VM
- Provides cost-effective alternative to cloud Function App consumption plan
- Uses same modern code as cloud deployment would use
- Full Azure Functions feature set (timer triggers, logging, etc.)

#### Key Files on VM:
```
/opt/microshare-eventhub-function/
├── function_app.py           # Azure Function entry point (2 timer functions)
├── app/
│   ├── microshare_client.py  # Microshare API client
│   ├── eventhub_client.py    # Event Hub client (dual-hub capable)
│   ├── state_manager.py      # Local JSON state (used on VM)
│   ├── state_manager_azure.py # Azure Table state (unused on VM)
│   └── config.py             # Config loader
├── .env                      # Credentials (same as CT4111)
├── config.yaml               # App configuration
└── /var/lib/microshare-forwarder/
    ├── peoplecounterstate.json   # People counter state
    └── snapshotstate.json        # Snapshot state
```

#### How It Runs:
```bash
# Started manually (auto-restarts on file changes)
cd /opt/microshare-eventhub-function
func start --port 7072

# Logs
tail -f /tmp/func-runtime-new.log
```

#### Deployment from CT4111:
```bash
# Deploy code changes
scp app/microshare_client.py azureuser@104.45.41.81:/opt/microshare-eventhub-function/app/
# Or full app directory
rsync -av --exclude='.env' app/ azureuser@104.45.41.81:/opt/microshare-eventhub-function/app/
# Runtime auto-reloads, no restart needed
```

#### Why VM Instead of Cloud Function App:
- **Cost savings**: Fixed VM cost vs per-execution consumption pricing
- **State management**: Simple local JSON files vs Azure Table Storage setup
- **Same code**: Uses identical Azure Functions implementation
- **Easy migration**: Can move to cloud Function App anytime without code changes

---

### 3. Azure Function App: `microshare-forwarder-func`
**URL**: `microshare-forwarder-func.azurewebsites.net`
**Location**: UK South
**Type**: Linux Consumption Plan (serverless)
**Status**: **DEPLOYED BUT NOT IN ACTIVE USE**

#### What's Here:
- Azure Function App exists and is deployed
- May contain older code version (not currently maintained)
- Would use Azure Table Storage for state if activated
- Application Insights configured

#### Purpose:
- **Future migration option** when ready to move from VM to cloud
- Provides serverless alternative with auto-scaling
- No OS maintenance required
- Azure-native logging and monitoring

#### Why Not Currently Used:
- VM provides sufficient performance and reliability
- VM approach is more cost-effective for current load
- Simpler state management with local JSON files
- Can migrate anytime without code changes (same codebase)

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

### 4. Azure Event Hubs
**Status**: **ACTIVE** (dual-hub capable)

#### Primary Hub (Test/Monitoring)
- **Namespace**: `ehns-playground-26767.servicebus.windows.net`
- **Hub Name**: `ingress-test`
- **Type**: Standard tier, 4 partitions
- **Purpose**: Testing, monitoring, and development

#### Client Hub (Production)
- **Namespace**: `occupancydata-dev-ehns.servicebus.windows.net`
- **Hub Name**: `occupancydata-microshare-dev-function-eh`
- **Type**: Standard tier
- **Purpose**: Client production data delivery
- **Status**: Currently paused for testing (can be re-enabled)

#### Dual-Hub Broadcasting
The system supports simultaneous delivery to multiple Event Hubs:
- Configured via `EVENT_HUB_CONNECTION_STRING` (primary) + `EVENT_HUB_CONNECTION_STRINGS` (JSON array of additional hubs)
- All hubs receive identical data simultaneously
- Enhanced logging shows delivery confirmation for each hub
- Either hub can be enabled/disabled independently via `.env` configuration

#### What's Here:
- Message brokers that receive occupancy events
- Retains messages for 1 day (configurable)
- Supports Kafka protocol (can use Kafka clients)
- Multiple consumer groups for different downstream systems

#### Purpose:
- **Central data ingestion point** for all Microshare data
- Decouples data producers (VM) from consumers
- Enables multiple downstream consumers (analytics, storage, client systems)
- Provides reliable message delivery with retry and ordering guarantees

#### Connection:
- Both VM and Function App use **connection string authentication**
- Connection string includes: `Endpoint`, `SharedAccessKey`, `EntityPath`

---

## Code Architecture (As of 2025-11-14)

### Function App Structure

The codebase uses a **refactored, DRY (Don't Repeat Yourself) architecture** with minimal code duplication:

```python
function_app.py
├── run_forwarder()                    # Generic orchestration helper
│   ├── State management setup
│   ├── Time window calculation
│   ├── Client initialization
│   ├── Error handling & logging
│   └── Event Hub delivery
│
├── hourly_snapshot_forwarder()        # Timer: Every hour at :00
│   └── Calls: run_forwarder() + get_snapshot_full_coverage()
│
└── people_counter_forwarder()         # Timer: Every 15 minutes
    └── Calls: run_forwarder() + get_people_counter_full_coverage()
```

**Key Design Principles:**
- ✅ **Separate functions** for different recTypes (independent schedules, state, formats)
- ✅ **Shared orchestration** via `run_forwarder()` (eliminates 95% duplication)
- ✅ **Different data formats** preserved (flattened events vs complete API responses)
- ✅ **Easy to extend** (add new recType = new timer function + fetch method)

### MicroshareClient Architecture

```python
app/microshare_client.py
├── _query_dashboard_api()             # Common dashboard API helper
│   ├── Token management
│   ├── Headers & authentication
│   └── Error handling
│
├── discover_locations()                # Device cluster API (identity filtering)
│
├── get_people_counter_full_coverage()  # Returns: List[Event] (flattened)
│   ├── Uses: discover_locations()
│   ├── Uses: _query_dashboard_api()
│   └── Adds: recType field to each event
│
└── get_snapshot_full_coverage()        # Returns: List[APIResponse] (complete)
    ├── Uses: discover_locations()
    ├── Uses: _query_dashboard_api()
    └── Adds: recType field to response
```

### Event Data Formats

**People Counter Events** (flattened):
```json
{
  "recType": "io.microshare.peoplecounter.unpacked.event.agg",
  "time": "2025-11-14T14:30:00.000Z",
  "change": {"in": 5, "out": 3, "count": 2},
  "daily_total": {"traffic": 150, "count": 42},
  "meta": {"device": [...], "timezone": "Europe/Paris"},
  "_location_tags": ["Building A", "Floor 2", "Zone 3"],
  "record": "abc123..."
}
```

**Snapshot Events** (complete API response):
```json
{
  "recType": "io.microshare.lake.snapshot.hourly",
  "meta": {
    "currentCount": 5,
    "totalPages": 1,
    "source": "db"
  },
  "objs": [
    {
      "data": {
        "line": [
          {"time": "2025-11-14T14:00:00Z", "current": 42}
        ]
      }
    }
  ]
}
```

---

## Data Flow Architecture

### Current Production State
```
                    Microshare API
                    (api.microshare.io)
                           ↓
                    [JWT Authentication]
                    [Device Cluster Discovery]
                    [Dashboard View Queries]
                           ↓
                    Azure VM (ACTIVE)
                    func start --port 7072
                    /opt/microshare-eventhub-function
                    ├── People Counter (15min)
                    └── Snapshots (hourly)
                           ↓
                    [recType field added]
                           ↓
              ┌────────────┴────────────┐
              ↓                         ↓
       Primary Hub              Client Hub (paused)
       ingress-test             occupancydata-*
              ↓                         ↓
       Test/Monitor             Production Clients
```

### Future Option (Cloud Migration)
```
    Microshare API
         ↓
    Azure Function App (Cloud)
    microshare-forwarder-func
    (Consumption Plan)
         ↓
    Azure Event Hubs
         ↓
    Downstream Consumers
```
**Note:** Can migrate anytime - same code runs on both VM and cloud

---

## Development Workflow

### Typical Development Cycle on CT4111

1. **Edit code** in `/opt/projects/microshare-eventhub-function/`
   ```bash
   nano function_app.py
   nano app/microshare_client.py
   ```

2. **Test locally** (optional)
   ```bash
   cd /opt/projects/microshare-eventhub-function
   python3 test_rectype.py           # Test people counter
   python3 test_snapshot_rectype.py  # Test snapshots
   ```

3. **Deploy to Production VM**
   ```bash
   # Single file deployment
   scp app/microshare_client.py azureuser@104.45.41.81:/opt/microshare-eventhub-function/app/

   # Or full app directory
   rsync -av --exclude='.env' app/ azureuser@104.45.41.81:/opt/microshare-eventhub-function/app/

   # Or deploy function_app.py
   scp function_app.py azureuser@104.45.41.81:/opt/microshare-eventhub-function/

   # Runtime auto-reloads - no restart needed!
   ```

4. **Monitor VM execution**
   ```bash
   # Real-time logs
   ssh azureuser@104.45.41.81 'tail -f /tmp/func-runtime-new.log'

   # Check function status
   ssh azureuser@104.45.41.81 'ps aux | grep "func start" | grep -v grep'

   # View state files
   ssh azureuser@104.45.41.81 'cat /var/lib/microshare-forwarder/peoplecounterstate.json | python3 -m json.tool'
   ```

5. **Test Event Hub data** (from CT4111)
   ```bash
   python3 consumer.py          # Read all events from beginning
   python3 consumer_latest.py   # Read only new events
   ```

6. **Commit changes**
   ```bash
   git add function_app.py app/microshare_client.py
   git commit -m "Description of changes"
   git push origin main
   ```

### Alternative: Deploy to Cloud Function App (Future)

```bash
# If migrating to cloud deployment
func azure functionapp publish microshare-forwarder-func

# Monitor cloud logs
az functionapp logs tail --name microshare-forwarder-func --resource-group rg-eh-playground
```

---

## SSH Access and VM Management

### From CT4111 to Azure VM
```bash
ssh azureuser@104.45.41.81
```

**Authentication**: SSH key (`~/.ssh/id_rsa`)

**Common VM Tasks:**

```bash
# Check function runtime status
ps aux | grep "func start"

# View real-time logs
tail -f /tmp/func-runtime-new.log

# Check state files
cat /var/lib/microshare-forwarder/peoplecounterstate.json | python3 -m json.tool
cat /var/lib/microshare-forwarder/snapshotstate.json | python3 -m json.tool

# Check .env configuration
grep EVENT_HUB /opt/microshare-eventhub-function/.env

# Restart function runtime (if needed)
pkill -f "func start"
cd /opt/microshare-eventhub-function && nohup func start --port 7072 > /tmp/func-runtime-new.log 2>&1 &
```

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

### Azure VM Commands (via SSH - Current Production)
```bash
# Check function runtime status
ps aux | grep "func start" | grep -v grep

# View real-time logs
tail -f /tmp/func-runtime-new.log

# Check state files
cat /var/lib/microshare-forwarder/peoplecounterstate.json | python3 -m json.tool
cat /var/lib/microshare-forwarder/snapshotstate.json | python3 -m json.tool

# Restart function runtime (if needed)
pkill -f "func start"
cd /opt/microshare-eventhub-function && nohup func start --port 7072 > /tmp/func-runtime-new.log 2>&1 &
```

### Azure CLI Commands (from CT4111)
```bash
# Event Hub info
az eventhubs eventhub show --name ingress-test --namespace-name ehns-playground-26767 --resource-group rg-eh-playground

# List Event Hub namespaces
az eventhubs namespace list --output table

# Function App info (not currently used)
az functionapp show --name microshare-forwarder-func --resource-group rg-eh-playground
```

---

## Recent Changes (2025-11-14)

### Code Refactoring
- ✅ **Added `run_forwarder()` helper** - Eliminates 95% code duplication between timer functions
- ✅ **Added `_query_dashboard_api()` helper** - Common dashboard API query logic
- ✅ **Simplified timer functions** - From 50+ lines to 8 lines each
- ✅ **Better variable naming** - `events_sent` instead of confusing `snapshots_sent`

### recType Field Implementation
- ✅ **People counter events** - All events now include `recType: "io.microshare.peoplecounter.unpacked.event.agg"`
- ✅ **Snapshot responses** - All responses include `recType: "io.microshare.lake.snapshot.hourly"`
- ✅ **Client routing** - recType field enables downstream systems to route/process events correctly

### Dual Event Hub Support
- ✅ **Multi-hub broadcasting** - Can send to multiple Event Hubs simultaneously
- ✅ **Flexible configuration** - Primary hub + JSON array of additional hubs
- ✅ **Enhanced logging** - Shows delivery confirmation for each hub
- ⏸️ **Client hub paused** - Currently only sending to primary hub for testing

---

## Summary

**CT4111** = Development machine (where you edit code and test)
**Azure VM (104.45.41.81)** = **ACTIVE PRODUCTION** (runs Azure Functions via Core Tools)
**Azure Function App** = Cloud option (exists but not in use)
**Azure Event Hubs** = Message brokers (primary + client, dual-hub capable)

**Current Workflow:**
1. Edit code on CT4111
2. Deploy to VM via `scp` or `rsync`
3. Runtime auto-reloads (no restart needed)
4. Monitor logs via `ssh azureuser@104.45.41.81 'tail -f /tmp/func-runtime-new.log'`
5. Commit to git

**Future Option:**
- Can migrate to cloud Function App anytime (same code, just deploy with `func azure functionapp publish`)
