# HAR File Analysis - Working Microshare API Patterns

**Date**: 2025-11-13 19:15 UTC
**Source**: Firefox Developer Tools capture from Microshare web UI

---

## Key Discovery: Device Cluster API Pattern

### Working API Call Found

The Microshare web UI uses the **Device Cluster API** to enumerate locations:

```
GET https://api.microshare.io/device/io.microshare.peoplecounter.packed/66e2b7a501faa80630fbb35f?details=true

Authorization: Bearer {token}
```

### Response Structure

```json
{
  "meta": {
    "currentCount": 1,
    "totalCount": 1
  },
  "objs": [{
    "_id": "66e2b7a501faa80630fbb35f",
    "data": {
      "devices": [
        {
          "id": "00-04-A3-0B-00-EE-6D-51",
          "meta": {
            "location": ["CBRE Prony", "8", "Rooftop"]
          }
        },
        {
          "id": "00-04-A3-0B-01-03-7E-C2",
          "meta": {
            "location": ["CBRE Prony", "4", "Sortie Prony"]
          }
        },
        {
          "id": "00-04-A3-0B-01-06-5C-D0",
          "meta": {
            "location": ["CBRE Prony", "4", "Entree Prony"]
          }
        },
        {
          "id": "00-04-A3-0B-01-14-61-7F",
          "meta": {
            "location": ["CBRE Prony", "4", "Entree Villiers"]
          }
        }
      ]
    },
    "owner": {
      "appid": "2761E567-69D7-46A7-8D1F-524780731EA2",
      "org": "com.cbre.CBREOD",
      "user": "ms_admin@cbre.com"
    },
    "recType": "io.microshare.peoplecounter.packed"
  }]
}
```

### Key Findings

1. **Locations are hierarchical arrays**: `["Building", "Floor", "Specific Location"]`
2. **Owner information is present**: `owner.org = "com.cbre.CBREOD"` (matches our `MICROSHARE_IDENTITY`)
3. **Device cluster ID is fixed**: `66e2b7a501faa80630fbb35f`
4. **API namespace is `api.microshare.io`**, not `dapi.microshare.io`

### Discovered Locations

From the device cluster response:
- `CBRE Prony` (building level)
  - Floor 8: Rooftop
  - Floor 4: Sortie Prony, Entree Prony, Entree Villiers

### Location Extraction Strategy

From the HAR data, we can extract unique location combinations:

**Building-level location** (loc1):
```
"CBRE Prony"
```

**Full hierarchical locations**:
```
"CBRE Prony" > "8" > "Rooftop"
"CBRE Prony" > "4" > "Sortie Prony"
"CBRE Prony" > "4" > "Entree Prony"
"CBRE Prony" > "4" > "Entree Villiers"
```

---

## Implementation Strategy

### Two-Phase Approach (Confirmed Working)

**Phase 1: Get Devices from Cluster**
```python
# Query device cluster API
device_cluster_id = "66e2b7a501faa80630fbb35f"
url = f"https://api.microshare.io/device/io.microshare.peoplecounter.packed/{device_cluster_id}"
params = {"details": "true"}

response = requests.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
cluster_data = response.json()

# Extract unique locations from devices
locations = set()
for obj in cluster_data.get("objs", []):
    for device in obj.get("data", {}).get("devices", []):
        location_array = device.get("meta", {}).get("location", [])
        if location_array:
            # Use first element (building name) as loc1
            building = location_array[0]
            locations.add(building)

# Filter by owner identity
owner_org = cluster_data["objs"][0]["owner"]["org"]  # "com.cbre.CBREOD"
if "CBREOD" in owner_org:  # Match identity filter
    print(f"Identity matches: {owner_org}")
```

**Phase 2: Query Dashboard Per Location**
```python
# For each discovered location, query dashboard view
for location in locations:
    dashboard_params = {
        "id": "6148d9814827f67b1b319dd4",  # Dashboard view ID
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "loc1": location,  # e.g., "CBRE Prony"
        "from": from_timestamp,
        "to": to_timestamp,
        # ... other fields
    }

    response = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=dashboard_params,
        headers={"Authorization": f"Bearer {token}"}
    )
```

---

## Configuration Updates Needed

### New Environment Variable

Add to `.env`:
```bash
# Device Cluster Configuration
MICROSHARE_PC_DEVICE_CLUSTER_ID=66e2b7a501faa80630fbb35f
```

### Remove Broken Variable

Remove from `.env`:
```bash
# BROKEN - returns 404
# MICROSHARE_PC_DISCOVERY_VIEW_ID=661eabafa0a03557a44bdd6c
```

---

## Advantages of This Approach

1. **Actually works** - proven by web UI usage
2. **Provides owner/identity info** - can filter by `owner.org`
3. **Single query for location enumeration** - no wildcard discovery needed
4. **Hierarchical location data** - can extract building, floor, room levels
5. **Fixed cluster ID** - no need for complex discovery logic

---

## Next Steps

1. ✅ Update `microshare_client.py` with device cluster API method
2. ✅ Add `MICROSHARE_PC_DEVICE_CLUSTER_ID` to config
3. ✅ Remove broken discovery view code
4. ✅ Test locally with device cluster approach
5. ⬜ Deploy to Azure Function App
6. ⬜ Monitor execution and verify data flow

---

## API Comparison

| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| **Device Cluster (HAR)** | `api.microshare.io/device/{recType}/{clusterId}` | ✅ **WORKING** | Used by web UI |
| Discovery View | `api.microshare.io/share/.../id=661eabafa0a03557a44bdd6c` | ❌ BROKEN | Returns 404 |
| Dashboard View | `api.microshare.io/share/.../id=6148d9814827f67b1b319dd4` | ✅ WORKING | Requires loc1 |
| Device Wildcard (docs) | `dapi.microshare.io/device/*?discover=true` | ❓ UNTESTED | From old docs |

---

**Conclusion**: The HAR file revealed the actual working pattern used by the Microshare web UI. We should implement the Device Cluster API approach (Option 2 from the root cause document) using the exact pattern shown in the HAR capture.
