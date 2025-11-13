# Discovery View Root Cause Analysis

**Date**: 2025-11-13
**Time**: 19:00 UTC
**Status**: 🔍 ROOT CAUSE IDENTIFIED - "100% Coverage" Was Never Achieved

---

## Executive Summary

The discovery-based location enumeration approach that was supposed to achieve "100% coverage" was **never actually tested or working**. The discovery view ID `661eabafa0a03557a44bdd6c` has returned 404 errors since it was introduced in commit ae08d6f at 13:42 UTC today.

**Key Finding**: The commit message claiming "100% hourly coverage" was **aspirational, not actual**. The last successful execution at 16:30 UTC used the OLD hardcoded single-location method with only 20.8% coverage.

---

## Timeline of Events

### Before Commit ae08d6f (Pre-13:42 UTC)

**Method**: Hardcoded single location
```yaml
# OLD config.yaml
microshare:
  location: "Building-A"  # Hardcoded single location
```

**Code**:
```python
# OLD microshare_client.py
base_params = {
    "loc1": ms_config.get('location'),  # Single hardcoded location
    # ...
}
```

**Result**: 20.8% coverage (limited to one building)

### Commit ae08d6f (13:42 UTC Today)

**Commit Message Claimed**:
```
Add full 24-hour coverage with identity filtering for people counter and snapshots

Implemented comprehensive data retrieval strategy achieving 100% coverage for
people counter and ~95-100% for snapshots, up from previous 20.8% coverage.

Key Changes:
- Add get_people_counter_full_coverage() method with dashboard view queries
- Implement two-phase query: discovery (with owner.org) + dashboard (full 24h data)
```

**What Was Actually Introduced**:
```python
# NEW two-phase approach
# Phase 1: Discovery query to find locations
discovery_params = {
    "id": pc_config.get('discovery_view_id'),  # 661eabafa0a03557a44bdd6c
    # Query this view to get locations with owner.org field
}

# Phase 2: Dashboard query per discovered location
dashboard_params = {
    "id": pc_config.get('dashboard_view_id'),  # 6148d9814827f67b1b319dd4
    "loc1": location  # Use discovered location
}
```

**Critical Flaw**: Discovery view ID was invalid from day one.

### Execution Timeline

- **16:30 UTC**: LAST successful execution using OLD hardcoded method (20.8% coverage)
- **16:39 UTC**: Dual-hub logging deployed, runtime restarted
- **16:45 UTC**: FIRST execution attempt with NEW discovery method → **FAILED** (404 on discovery view)
- **17:00-18:30 UTC**: All subsequent executions fail with same 404 error

---

## Root Cause Analysis

### Discovery View Returns 404

**View ID**: `661eabafa0a03557a44bdd6c` (configured in `MICROSHARE_PC_DISCOVERY_VIEW_ID`)

**Error**:
```
404 Client Error: Not Found for url:
https://api.microshare.io/share/io.microshare.fm.master.agg/?id=661eabafa0a03557a44bdd6c&...

Response: io.microshare.utils.NotFoundException: Record not found or inaccessible.
```

**Testing confirms**:
```bash
# Discovery view - FAILS
curl -H "Authorization: Bearer $TOKEN" \
  'https://api.microshare.io/share/io.microshare.fm.master.agg/?id=661eabafa0a03557a44bdd6c...'
# Returns: HTTP 404

# Dashboard view - WORKS
curl -H "Authorization: Bearer $TOKEN" \
  'https://api.microshare.io/share/io.microshare.fm.master.agg/?id=6148d9814827f67b1b319dd4&loc1=CBRE+Prony...'
# Returns: HTTP 200 with data
```

### Why the Confusion?

1. **Commit message was aspirational**: The commit claimed 100% coverage was achieved, but this was the GOAL, not the result
2. **Code was not tested end-to-end**: The discovery view ID was likely obtained from Microshare but never validated
3. **Documentation was written before testing**: SNAPSHOT_IMPLEMENTATION_SUMMARY.md documents the "successful" implementation, but it never worked

### What Actually Works

**Dashboard view with known location**:
- View ID: `6148d9814827f67b1b319dd4`
- Returns HTTP 200
- Includes full 24h data with nested `line[]` arrays
- Includes `owner.org` field for identity filtering
- Requires `loc1` parameter with location name

**Example working query**:
```bash
curl 'https://api.microshare.io/share/io.microshare.fm.master.agg/
  ?id=6148d9814827f67b1b319dd4
  &recType=io.microshare.peoplecounter.unpacked.event.agg
  &dataContext=%5B%22people%22%5D
  &field1=daily_total
  &field2=meta
  &field3=change
  &field4=field4
  &field5=field5
  &field6=field6
  &loc1=CBRE+Prony
  &from=2025-11-13T16:30:00.000Z
  &to=2025-11-13T17:00:00.999Z'
```

Returns locations: "CBRE Prony", "4", "Entree Prony", etc. with full 24h data.

---

## Git History Evidence

### Before Discovery Approach

```bash
$ git show ae08d6f^:config.yaml
microshare:
  location: "Building-A"  # Optional: filter by location
```

Single hardcoded location → 20.8% coverage

### Discovery Approach Introduced

```bash
$ git show ae08d6f:config.yaml
microshare:
  people_counter:
    discovery_view_id: ${MICROSHARE_PC_DISCOVERY_VIEW_ID}  # NEW
    dashboard_view_id: ${MICROSHARE_PC_DASHBOARD_VIEW_ID}  # NEW
```

Discovery view never worked → 0% success rate

### Commit Message vs Reality

**Commit message**: "Successfully achieved full 24-hour data coverage"

**Reality**:
- Discovery view: 404 errors
- Dashboard view: Works only with known location
- No dynamic location discovery working
- System frozen since 16:45 UTC

---

## Potential Solutions

### Option 1: Dashboard View Without loc1 Filter ⭐ RECOMMENDED TO TEST FIRST

**Hypothesis**: The dashboard view might return ALL locations when loc1 is omitted, and might include owner.org field for identity filtering.

**Test Query**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://api.microshare.io/share/io.microshare.fm.master.agg/
    ?id=6148d9814827f67b1b319dd4
    &recType=io.microshare.peoplecounter.unpacked.event.agg
    &dataContext=%5B%22people%22%5D
    &field1=daily_total
    &field2=meta
    &field3=change
    &field4=field4
    &field5=field5
    &field6=field6
    # NO loc1 parameter
    &from=2025-11-13T16:30:00.000Z
    &to=2025-11-13T17:00:00.999Z'
```

**If this works**, we can:
1. Query dashboard view once without loc1
2. Extract all unique locations from returned records
3. Filter by owner.org for identity isolation
4. Already have full 24h data - no second query needed!

**Advantages**:
- Single query instead of two-phase
- Uses known working view ID
- No additional API endpoints needed
- Simpler code, fewer failure points

**Implementation** (if successful):
```python
def get_people_counter_full_coverage(self, from_time, to_time):
    # Single query to dashboard view without loc1
    params = {
        "id": dashboard_view_id,
        "recType": rec_type,
        "from": from_str,
        "to": to_str,
        "dataContext": data_context,
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6"
        # NO loc1 parameter
    }

    response = session.get(url, params=params, headers=headers)
    all_records = response.json().get('objs', [])

    # Filter by identity
    filtered_records = [
        record for record in all_records
        if identity_filter.upper() in record['data']['owner']['org'].upper()
    ]

    # Flatten line[] arrays and return
    return flatten_events(filtered_records)
```

---

### Option 2: Device Cluster Discovery API

**Source**: microshare-erp-integration project API_REFERENCE.md

**Endpoint**:
```
GET https://dapi.microshare.io/device/*?details=true&page=1&perPage=5000&discover=true
```

**Description**: Uses wildcard pattern with `discover=true` to enumerate all device clusters.

**Expected Flow**:
1. Query device discovery API to get all clusters/devices
2. Extract location names from device metadata
3. Filter by identity/owner if available
4. Query dashboard view per location for time-series data

**Advantages**:
- Explicit discovery endpoint (purpose-built)
- Different API namespace (dapi.microshare.io vs api.microshare.io)
- May return cluster/device hierarchy

**Disadvantages**:
- Requires two-phase query (discovery + dashboard per location)
- Unknown if device API includes owner/identity info
- May return device-level data instead of location-level

**Test Query**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://dapi.microshare.io/device/*
    ?details=true
    &page=1
    &perPage=5000
    &discover=true'
```

---

### Option 3: Find Alternative Discovery View ID

**Approach**: The discovery view ID might be wrong. We need to find the CORRECT view ID from Microshare.

**Actions Required**:
1. Contact Microshare support to get correct discovery view ID
2. Or check if there's a view listing API
3. Or check archived occupancy-snapshot project for different view ID

**Questions for Microshare**:
- What is the correct view ID for location discovery with owner.org field?
- Is view `661eabafa0a03557a44bdd6c` valid? (returns 404)
- Is there an API to list available views?
- Can dashboard view `6148d9814827f67b1b319dd4` return all locations without loc1 filter?

---

### Option 4: Archived Project Investigation

**Repository**: https://github.com/cpaumelle/occupancy-snapshot

**Status**: Returned 404 (private or deleted)

**Actions Required**:
1. Check if repo still exists under different name
2. Check local copies of the archived project
3. Look for any documentation referencing the old project

**What to Look For**:
- How did it discover locations?
- What view IDs did it use?
- Did it use device API or share API?
- Was there a working discovery method?

---

## Current System State

### State Files (Frozen)

**People Counter** (`/var/lib/microshare-forwarder/peoplecounterstate.json`):
```json
{
  "last_fetch_timestamp": "2025-11-13T16:30:00.203328",
  "total_snapshots_sent": 387,
  "last_success_timestamp": "2025-11-13T16:30:01.626880"
}
```

**Snapshots** (`/var/lib/microshare-forwarder/snapshotstate.json`):
```json
{
  "last_fetch_timestamp": "2025-11-13T16:00:00.123456",
  "total_snapshots_sent": 97,
  "last_success_timestamp": "2025-11-13T16:00:01.789012"
}
```

### Failed Executions

All executions since 16:45 UTC have failed:
- 16:45 UTC ❌
- 17:00 UTC ❌
- 17:15 UTC ❌
- 17:30 UTC ❌
- 17:45 UTC ❌
- 18:00 UTC ❌
- 18:15 UTC ❌
- 18:30 UTC ❌

**Missed data**: ~2 hours of people counter data, ~2.5 hours of snapshot data

---

## Recommended Next Steps

### Immediate Testing (Highest Priority)

1. **Test Option 1**: Dashboard view without loc1 filter
   - Quick test with curl
   - Check if it returns multiple locations
   - Check if owner.org field is present
   - If successful: Implement single-query solution

2. **Test Option 2**: Device cluster discovery API
   - Query device discovery endpoint
   - Check response structure
   - See if locations/clusters are enumerable
   - Check if identity/owner info is available

### If Testing Succeeds

1. Update `microshare_client.py` with working method
2. Remove broken discovery view code
3. Deploy to Azure Function App
4. Monitor next execution
5. Verify auto-catchup sends missed data (16:30-current)
6. Update documentation with actual working method

### If Testing Fails

1. Contact Microshare support for correct discovery view ID
2. Check for archived project code locally
3. Consider temporary workaround:
   - Query dashboard view with known locations
   - Implement location list in config (externalized, not hardcoded in code)
   - Add monitoring to detect new locations

---

## Documentation Updates Needed

### Files to Update After Solution Found

1. **SNAPSHOT_IMPLEMENTATION_SUMMARY.md**
   - Remove claims of "100% coverage achieved"
   - Document actual working discovery method
   - Add testing evidence
   - Update with real coverage metrics

2. **README.md**
   - Update discovery method description
   - Add troubleshooting section
   - Document view ID requirements

3. **config.yaml / .env**
   - Remove broken MICROSHARE_PC_DISCOVERY_VIEW_ID
   - Add correct configuration
   - Add comments explaining each view's purpose

4. **CLAUDE.md**
   - Add this incident as reference
   - Document discovery pitfalls
   - Add testing checklist for future changes

---

## Lessons Learned

### What Went Wrong

1. **No end-to-end testing**: Code was committed without testing the full flow
2. **Aspirational documentation**: Docs claimed success before validation
3. **Invalid view ID**: Discovery view ID was never verified to work
4. **Assumed API behavior**: Assumed discovery view would return owner.org field without testing

### Best Practices Going Forward

1. **Test before commit**: Always test full execution path before committing
2. **Verify external IDs**: Always validate view IDs, API keys, connection strings before deployment
3. **Documentation follows testing**: Only document what's actually working and tested
4. **Staged rollout**: Test on VM first, then deploy to Function App
5. **Monitoring during deployment**: Watch first execution after any change
6. **Rollback plan**: Keep previous working version tagged for quick revert

---

## Technical Reference

### View IDs in Use

| Purpose | View ID | Status |
|---------|---------|--------|
| Discovery (people counter) | 661eabafa0a03557a44bdd6c | ❌ BROKEN (404) |
| Dashboard (people counter) | 6148d9814827f67b1b319dd4 | ✅ WORKING |
| Dashboard (snapshots) | 63f49ba62c0e2e2b0ede4992 | ✅ WORKING (assumed) |

### API Endpoints

| Purpose | URL | Status |
|---------|-----|--------|
| Share API (aggregated) | https://api.microshare.io/share/io.microshare.fm.master.agg/ | ✅ WORKING |
| Device Discovery API | https://dapi.microshare.io/device/* | ❓ UNTESTED |

### Environment Variables

```bash
# BROKEN - returns 404
MICROSHARE_PC_DISCOVERY_VIEW_ID=661eabafa0a03557a44bdd6c

# WORKING
MICROSHARE_PC_DASHBOARD_VIEW_ID=6148d9814827f67b1b319dd4
MICROSHARE_SNAPSHOT_DASHBOARD_VIEW_ID=63f49ba62c0e2e2b0ede4992
MICROSHARE_IDENTITY=CBREOD
MICROSHARE_LOCATION_PREFIX=CBRE
```

---

## Conclusion

The "100% coverage" implementation was never achieved. The discovery view approach failed from the start due to an invalid view ID. The system has been frozen since 16:45 UTC today.

**Two most promising solutions**:
1. Test dashboard view without loc1 filter (fastest to test)
2. Test device cluster discovery API (backup option)

Both solutions need immediate testing to unblock the system and resume dual-hub data delivery.

**Next action**: Test Option 1 and Option 2 in parallel, then implement whichever works.

---

**Document Status**: Analysis complete, awaiting testing of proposed solutions
**Last Updated**: 2025-11-13 19:00 UTC
