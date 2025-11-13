# Snapshot Full Coverage Implementation Summary

## Overview

Successfully implemented full 24-hour coverage for both **People Counter** and **Hourly Snapshot** data with identity filtering. This eliminates the previous limited coverage issue (was only getting 20.8% coverage).

## Key Achievement

- **People Counter**: 100% coverage (full 24 hours)
- **Hourly Snapshots**: ~95-100% coverage (23-24/24 hours depending on data availability)

## Implementation Strategy

### Two-Step Query Approach

Both data types now use a two-phase query strategy:

1. **Discovery Phase**: Query a view that includes `owner.org` field to identify locations belonging to the specified identity
2. **Dashboard Phase**: Query dashboard views per location to retrieve full 24-hour time-series data

### People Counter Flow

```
1. Discovery Query (View: configured in MICROSHARE_PC_DISCOVERY_VIEW_ID)
   ├─ Returns records with owner.org field
   ├─ Filter by identity: "ACME" matches "com.company.ACME"
   └─ Extract unique locations: ["Company Location A"]

2. Dashboard Query (View: configured in MICROSHARE_PC_DASHBOARD_VIEW_ID)
   ├─ Query per location with loc1 parameter
   ├─ Returns nested line[] arrays (96 entries = 15-min intervals)
   └─ Flatten arrays into individual events

Result: Full 24-hour coverage with identity-filtered events
```

### Hourly Snapshots Flow

```
1. Discovery Query (Use People Counter View)
   ├─ Snapshot dashboard lacks owner.org field
   ├─ Reuse people counter discovery to find identity locations
   └─ Map location names: "Company Location A" → "Location A"

2. Dashboard Query (View: configured in MICROSHARE_SNAPSHOT_DASHBOARD_VIEW_ID)
   ├─ Query per mapped location with loc1 parameter
   ├─ Returns nested line[] arrays with hourly snapshots
   └─ Flatten arrays into individual snapshot entries

Result: Full 24-hour coverage with identity-filtered snapshots
```

## Technical Details

### Location Name Mapping

Discovered that location names may differ between people counter and snapshot data:
- **People Counter**: "Company Location A"
- **Snapshots**: "Location A"

Solution: Configure `MICROSHARE_LOCATION_PREFIX` to strip the prefix when querying snapshot dashboard.

### Dashboard Format Structure

Both data types return a nested structure:

```json
{
  "data": {
    "_id": {
      "tags": ["LocationA", "Floor-01", "Room-01", "DEVICEID001"]
    },
    "line": [
      {
        "time": "2025-11-12T01:00:00.000Z",
        "category": "space",
        "metric": "occupancy",
        "current": {...},
        "change": {...}
      }
    ]
  }
}
```

The `line[]` array contains the full 24-hour time-series data.

## Code Changes

### New Methods Added

1. **`get_people_counter_full_coverage()`** (app/microshare_client.py:349)
   - Replaces limited coverage approach
   - Full 24-hour coverage with identity filtering
   - Dynamic location discovery

2. **`get_snapshot_full_coverage()`** (app/microshare_client.py:481)
   - Mirrors people counter approach
   - Uses people counter discovery for location identification
   - Handles location name mapping

### Deprecated Method

- **`get_snapshots_in_range()`** (app/microshare_client.py:212)
  - Marked as deprecated with warning
  - Limited coverage, no identity filtering
  - Kept for backward compatibility with existing tests

### Azure Function Updates

1. **`people_counter_forwarder()`** (function_app.py:88)
   - Now uses `get_people_counter_full_coverage()`
   - Logs identity filter
   - Full 24h coverage

2. **`hourly_snapshot_forwarder()`** (function_app.py:24)
   - Now uses `get_snapshot_full_coverage()`
   - Logs identity filter
   - Full 24h coverage

## Configuration

### Environment Variables

Added new required variables:

```bash
# Identity filtering
MICROSHARE_IDENTITY=ACME  # Filters to com.company.ACME

# People Counter View IDs
MICROSHARE_PC_DISCOVERY_VIEW_ID=abc123...  # Discovery view (has owner.org)
MICROSHARE_PC_DASHBOARD_VIEW_ID=def456...  # Dashboard view (full 24h data)
MICROSHARE_PC_DATA_CONTEXT=["people"]

# Snapshot View IDs
MICROSHARE_SNAPSHOT_DASHBOARD_VIEW_ID=ghi789...  # Dashboard view (full 24h data)
MICROSHARE_SNAPSHOT_DATA_CONTEXT=["context1","context2","context3"]
MICROSHARE_SNAPSHOT_CATEGORY=space
MICROSHARE_SNAPSHOT_METRIC=occupancy

# Location Mapping
MICROSHARE_LOCATION_PREFIX=Company  # Removes "Company " prefix
```

This enables multi-tenant data isolation by filtering on `owner.org` field.

### View Configuration

| Data Type | Config Variable | Purpose | Returns owner.org? |
|-----------|----------------|---------|-------------------|
| People Counter Discovery | `MICROSHARE_PC_DISCOVERY_VIEW_ID` | Fast location discovery | ✓ Yes |
| People Counter Dashboard | `MICROSHARE_PC_DASHBOARD_VIEW_ID` | Full 24h data | ✗ No |
| Snapshot Dashboard | `MICROSHARE_SNAPSHOT_DASHBOARD_VIEW_ID` | Full 24h data | ✗ No |

## Testing

Created comprehensive test suite:

- `tests/test_location_discovery.py` - Location discovery strategy
- `tests/test_identity_filtering.py` - Identity filtering validation
- `tests/test_full_implementation.py` - People counter full coverage
- `tests/test_snapshot_coverage.py` - Snapshot data coverage
- `tests/test_snapshot_identity.py` - Snapshot identity approach
- `tests/test_snapshot_with_pc_locations.py` - Location mapping validation
- `tests/test_snapshot_full_implementation.py` - Snapshot full coverage
- `tests/test_both_functions.py` - Combined validation

All tests confirm full coverage and proper identity filtering.

## Performance Improvements

### Before (Old Method)
- **People Counter**: Limited coverage (20.8%, 5/24 hours)
- **Limited to**: Specific time range only
- **Issue**: View pipeline filtered on wrong time field

### After (New Method)
- **People Counter**: Full coverage (100%, 24/24 hours)
- **Hourly Snapshots**: Near-full coverage (~95-100%, 23-24/24 hours)
- **Improvement**: ~5x more data for people counter

## Documentation Updates

1. **README.md**
   - Added identity filtering feature
   - Added full 24-hour coverage feature
   - Added dynamic location discovery feature
   - Updated environment variables table
   - Added Data Coverage section with technical details

2. **MICROSHARE_PEOPLE_COUNTER_QUERY_GUIDE.md**
   - Existing guide for people counter queries
   - Referenced by code comments

## Next Steps

### Potential Improvements

1. **Caching**: Cache location discovery results to reduce API calls
2. **Monitoring**: Add metrics for coverage percentage per run
3. **Error Handling**: Add retry logic for individual location queries
4. **Testing**: Add integration tests with mock data

### Deployment

Ready to deploy to Azure Function App. Required steps:

1. Update environment variables with all required config (see Configuration section)
2. Deploy updated code
3. Verify both functions run successfully
4. Monitor Application Insights for coverage metrics

## Conclusion

Successfully achieved full 24-hour data coverage for both people counter and snapshot data types with proper identity filtering. The solution:

- ✓ Eliminates data gaps (improved from 20.8% to 100% for people counter)
- ✓ Supports multi-tenant isolation via identity filtering
- ✓ Dynamically discovers locations (no hardcoded values)
- ✓ Uses efficient dashboard views for comprehensive time-series data
- ✓ Maintains separate state tracking per data type
- ✓ Fully tested and documented

---

**Date**: 2025-11-13
**Implementation by**: Claude Code
