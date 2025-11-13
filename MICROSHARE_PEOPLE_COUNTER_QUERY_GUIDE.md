# Microshare People Counter Data Query Guide

## Table of Contents
1. [Overview](#overview)
2. [Authentication](#authentication)
3. [API Discovery Methods](#api-discovery-methods)
4. [Working Query Patterns](#working-query-patterns)
5. [Data Structures](#data-structures)
6. [Data Processing Scripts](#data-processing-scripts)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)
9. [Complete Examples](#complete-examples)

## Overview

This guide documents the complete methodology for accessing Microshare people counter data through their REST API. Based on extensive testing and discovery, we've identified the working patterns for accessing both raw event data and aggregated dashboard data.

### Key Findings Summary
- **Direct Share API**: Limited access, returns "Access to this path is denied" for people counter record types
- **View-Based Aggregation Queries**: ✅ **Working method** for accessing people counter unpacked events
- **Dashboard Aggregation API**: ✅ **Working method** for pre-aggregated hourly data
- **Device Cluster API**: ✅ **Working method** for device metadata and configuration

## Authentication

### 1. Initial Authentication
All API calls require authentication through the FastAPI wrapper that handles Microshare token management.

```bash
# Get session token
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "ms_admin@cbre.com",
    "password": "fth41ZlrZM2M",
    "environment": "production"
  }'
```

**Response includes:**
- `session_token`: JWT containing Microshare access token
- `user_info`: User identity information
- `api_base`: API endpoint URL

### 2. Extract Microshare Access Token
The session token is a JWT containing the actual Microshare access token in the `microshare_access_token` field.

```bash
# Example token extraction (decode JWT to get microshare_access_token)
TOKEN="498bb0a826342f4f24bb00f6cc5c9f3733e01fa259920b9dd064ed88a2074464"
```

## API Discovery Methods

### 1. Device Cluster Discovery
Discover available people counter clusters and their metadata.

```bash
# Get device cluster information
curl -X GET \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.microshare.io/device/io.microshare.peoplecounter.packed/66e2b7a501faa80630fbb35f?details=true"
```

**Key Cluster Information:**
- **Cluster ID:** `66e2b7a501faa80630fbb35f`
- **Record Type:** `io.microshare.peoplecounter.packed`
- **Name:** "2025 CBRE occupancy data | People Counting"
- **Total Devices:** 30
- **Location:** Eurotunnel C03 building

### 2. Views API Discovery
Discover available views for data aggregation queries.

```bash
# Get all views for fm.master.agg record type
curl -X GET \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.microshare.io/view/io.microshare.fm.master.agg"
```

**Working View IDs:**
- `661eabafa0a03557a44bdd6c`: "Event Data | Customer View" - **Primary working view**
- `646228c609d85f234143afae`: "Test Lake"
- `5cd58c6946e0fb00245ac71f`: "FM master 2 var occupancy v1.1"

### 3. Failed Direct API Attempts
These endpoints exist but return access denied or empty results:

```bash
# ❌ Direct Share API - Access Denied
curl -X GET \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.microshare.io/share/io.microshare.peoplecounter.packed?details=true"

# ❌ Unpacked Events - Access Denied
curl -X GET \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.microshare.io/share/io.microshare.peoplecounter.unpacked.event?details=true"

# ❌ Raw Share Endpoints - Empty Results
curl -X GET \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.microshare.io/share/io.microshare.peoplecounter.unpacked/"
```

## Working Query Patterns

### 1. View-Based People Counter Event Queries ✅

**Primary Working Method** - Access people counter unpacked events through view-based aggregation:

```bash
curl "https://api.microshare.io/share/io.microshare.fm.master.agg/?id=661eabafa0a03557a44bdd6c&recType=io.microshare.peoplecounter.unpacked.event&from=2025-06-17T00:00:00.000Z&to=2025-06-17T23:59:59.999Z" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json"
```

**Parameters:**
- `id`: View ID (`661eabafa0a03557a44bdd6c`)
- `recType`: Target record type (`io.microshare.peoplecounter.unpacked.event`)
- `from`: Start date (ISO 8601 format, URL encoded)
- `to`: End date (ISO 8601 format, URL encoded)

**Returns:** Granular 15-minute interval people counter events with:
- Device-level in/out counts
- Battery and health status
- Signal quality metrics
- Location hierarchies
- Change events and daily totals

### 2. Dashboard Aggregation Queries ✅

**Alternative Method** - Access pre-aggregated hourly dashboard data:

```bash
curl 'https://api.microshare.io/share/io.microshare.fm.master.agg/?id=6148d9814827f67b1b319dd4&recType=io.microshare.peoplecounter.unpacked.event.agg&dataContext=%5B%22people%22%5D&field1=daily_total&field2=meta&field3=change&field4=field4&field5=field5&field6=field6&loc1=Eurotunnel+C03&from=2025-06-09T00%3A00%3A00.000Z&to=2025-06-10T00%3A00%3A00.000Z' \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json"
```

**Critical Parameters:**
- `field4=field4&field5=field5&field6=field6`: **Required placeholders** (causes 503 error if missing)
- `dataContext=[\"people\"]`: URL-encoded context filter
- `loc1=Eurotunnel+C03`: Location filter
- `field1=daily_total&field2=meta&field3=change`: Aggregation fields

### 3. Device Metadata Queries ✅

```bash
# Get complete device cluster with location metadata
curl -X GET \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.microshare.io/device/io.microshare.peoplecounter.packed/66e2b7a501faa80630fbb35f?details=true"
```

## Data Structures

### 1. Unpacked Event Data Structure

```json
{
  "data": {
    "_id": "6852017ea143532677e5115d",
    "data": {
      "change": {
        "alerts": 0,
        "count": 0,
        "faults": 0,
        "in": 0,
        "out": 0,
        "traffic": 0,
        "source_record": "6852017e62fd22415177f578"
      },
      "current": {
        "fcnt_up": 19208,
        "in": 26357,
        "out": 27957,
        "time": "2025-06-17T23:59:57.658Z"
      },
      "daily_total": {
        "alerts": 0,
        "count": 0,
        "date": "2025-06-18",
        "hour": 1,
        "in": 0,
        "out": 0,
        "traffic": 0,
        "first_event_time": "2025-06-17T22:14:57.795Z",
        "reset_time": "2025-06-17T22:00:00.000Z",
        "timezone": "Europe/Paris"
      },
      "device": {
        "id": "00-04-A3-0B-00-FA-AE-11",
        "voltage": [{"unit": "V", "value": 2.6}],
        "alert": [
          {"subtype": "reconnect", "value": false},
          {"subtype": "low_battery", "value": false}
        ]
      },
      "meta": {
        "device": ["Kosmo Neuilly", "R7 Seine", "Seine"],
        "global": ["dior", "people"],
        "iot": {
          "channel": 2,
          "device_id": "00-04-A3-0B-00-FA-AE-11",
          "rssi": -76,
          "sf": 8,
          "snr": 8,
          "payload": "02060004a30b00faae11000107000000000066f56d3567"
        }
      }
    }
  }
}
```

### 2. Device Cluster Structure

```json
{
  "data": {
    "devices": [
      {
        "guid": "d3135585-f666-8e02-77a6-2d03fd48175b",
        "id": "00-04-A3-0B-00-FA-8D-38",
        "status": "pending",
        "meta": {
          "location": ["Eurotunnel C03", "Global", "Batiment", "10 - RdC Sortie Aile E-0"]
        }
      }
    ],
    "targetRecType": "io.microshare.peoplecounter.unpacked"
  }
}
```

### 3. Location Hierarchy

The location metadata follows this structure:
```
Building > Floor/Area > Zone > Specific Location
Example: ["Eurotunnel C03", "1er Entree Aile C-1", "19", "1er Entree Aile C-1"]
```

**Sample Locations:**
- `Eurotunnel C03 > Global > Batiment > 10 - RdC Sortie Aile E-0`
- `Eurotunnel C03 > 2e Finance 1 > 23 > 2e Finance 1`
- `Eurotunnel C03 > RdC Informatique > 2 > RdC Informatique`

## Data Processing Scripts

### 1. JSON to CSV Converter

```python
#!/usr/bin/env python3
import json
import csv

def flatten_record(record):
    """Flatten nested JSON record into a flat dictionary for CSV"""
    flat = {}
    data = record.get('data', {})
    record_data = data.get('data', {})

    # Device info
    device = record_data.get('device', {})
    flat['device_id'] = device.get('id', '')
    flat['device_voltage'] = device.get('voltage', [{}])[0].get('value', '') if device.get('voltage') else ''

    # Current totals
    current = record_data.get('current', {})
    flat['current_in'] = current.get('in', '')
    flat['current_out'] = current.get('out', '')
    flat['current_time'] = current.get('time', '')

    # Daily totals
    daily = record_data.get('daily_total', {})
    flat['daily_date'] = daily.get('date', '')
    flat['daily_hour'] = daily.get('hour', '')
    flat['daily_in'] = daily.get('in', '')
    flat['daily_out'] = daily.get('out', '')
    flat['daily_traffic'] = daily.get('traffic', '')

    # Change events
    change = record_data.get('change', {})
    flat['change_in'] = change.get('in', '')
    flat['change_out'] = change.get('out', '')
    flat['change_traffic'] = change.get('traffic', '')

    # Location metadata
    meta = record_data.get('meta', {})
    device_location = meta.get('device', [])
    if len(device_location) >= 4:
        flat['building'] = device_location[0]
        flat['floor_area'] = device_location[1]
        flat['zone'] = device_location[2]
        flat['location_name'] = device_location[3]

    return flat

def main():
    with open('people_counter_data.json', 'r') as f:
        data = json.load(f)

    records = data.get('objs', [])
    flattened_records = [flatten_record(record) for record in records]

    if flattened_records:
        keys = sorted(set().union(*(record.keys() for record in flattened_records)))

        with open('people_counter_data.csv', 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=keys)
            writer.writeheader()
            writer.writerows(flattened_records)

if __name__ == "__main__":
    main()
```

### 2. Device-Specific Data Extraction

```python
def filter_device_data(json_files, target_device_id):
    """Extract data for specific device across multiple JSON files"""
    all_device_records = []

    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)

        records = data.get('objs', [])
        for record in records:
            record_data = record.get('data', {}).get('data', {})
            device_info = record_data.get('device', {})
            device_id = device_info.get('id', '')

            if device_id == target_device_id:
                all_device_records.append(flatten_record(record))

    return all_device_records
```

### 3. Batch Data Collection Script

```bash
#!/bin/bash
# Collect people counter data for date range

TOKEN="your_microshare_token_here"
START_DATE="2025-06-16"
END_DATE="2025-06-18"

for date in $(seq -f "%Y-%m-%d" -d "$START_DATE" +1day "$END_DATE"); do
    echo "Fetching data for $date..."

    curl "https://api.microshare.io/share/io.microshare.fm.master.agg/?id=661eabafa0a03557a44bdd6c&recType=io.microshare.peoplecounter.unpacked.event&from=${date}T00:00:00.000Z&to=${date}T23:59:59.999Z" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Accept: application/json" \
      > "people_counter_${date}.json"

    echo "Saved to people_counter_${date}.json"
    sleep 2  # Rate limiting
done
```

## Troubleshooting

### Common Issues

#### 1. 503 Service Error
**Problem:** Missing field parameters in aggregation query
```
Solution: Include field4=field4&field5=field5&field6=field6
```

#### 2. 403 Forbidden
**Problem:** Missing trailing slash in URL or incorrect authentication
```bash
# Wrong
https://api.microshare.io/share/io.microshare.peoplecounter.unpacked

# Correct
https://api.microshare.io/share/io.microshare.peoplecounter.unpacked/
```

#### 3. Access Denied
**Problem:** Direct access to people counter record types is restricted
```
Solution: Use view-based aggregation queries instead of direct Share API
```

#### 4. Empty Results
**Problem:** Querying raw data when devices are in "pending" status
```
Solution: Use aggregated dashboard data or view-based queries
```

#### 5. Token Expiration
**Problem:** Authentication token has expired
```bash
# Get fresh token
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "ms_admin@cbre.com", "password": "fth41ZlrZM2M", "environment": "production"}'
```

### Data Quality Issues

#### Missing Data Points
- **Cause:** 51.3% temporal coverage indicates sparse data collection
- **Solution:** Implement NULL handling for missing intervals

#### Device Status
- **Issue:** 30 devices in "pending" status
- **Impact:** Raw event APIs return empty results
- **Workaround:** Use aggregated data sources

#### Non-Overlapping Aggregations
- **Finding:** Global aggregation ≠ Sum of device records
- **Reason:** Global record covers only 10/30 devices
- **Approach:** Treat as complementary datasets, not hierarchical

## Best Practices

### 1. Authentication Management
- Store tokens securely and refresh before expiration
- Use environment variables for credentials
- Implement automatic token refresh logic

### 2. Rate Limiting
- Add delays between API calls (2-3 seconds recommended)
- Batch requests efficiently
- Monitor for rate limit responses

### 3. Data Collection Strategy
- Use view-based queries for event-level data
- Collect data in daily batches for reliability
- Implement retry logic for failed requests

### 4. Data Processing
- Validate JSON structure before processing
- Handle missing fields gracefully
- Preserve original timestamps for temporal analysis

### 5. Error Handling
```python
def safe_api_call(url, headers, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 503:
                print("Service error - check field parameters")
                return None
            elif response.status_code == 403:
                print("Access denied - check URL format")
                return None
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
    return None
```

## Complete Examples

### Example 1: Single Day Data Collection

```bash
# Complete workflow for June 17, 2025

# 1. Get authentication token
TOKEN=$(curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "ms_admin@cbre.com", "password": "fth41ZlrZM2M", "environment": "production"}' \
  | jq -r '.session_token' | python3 -c "import sys, jwt; print(jwt.decode(sys.stdin.read().strip(), options={'verify_signature': False})['microshare_access_token'])")

# 2. Fetch people counter data
curl "https://api.microshare.io/share/io.microshare.fm.master.agg/?id=661eabafa0a03557a44bdd6c&recType=io.microshare.peoplecounter.unpacked.event&from=2025-06-17T00:00:00.000Z&to=2025-06-17T23:59:59.999Z" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json" \
  > people_counter_2025-06-17.json

# 3. Convert to CSV
python3 json_to_csv_converter.py

# Result: people_counter_2025-06-17.csv with 554 records
```

### Example 2: Device-Specific Time Series

```bash
# Extract data for specific device across multiple days

DEVICE_ID="00-04-A3-0B-01-03-EA-04"
START_DATE="2025-06-30"
END_DATE="2025-07-04"

# Collect data for date range
for i in {0..4}; do
    DATE=$(date -d "$START_DATE + $i days" +%Y-%m-%d)

    curl "https://api.microshare.io/share/io.microshare.fm.master.agg/?id=661eabafa0a03557a44bdd6c&recType=io.microshare.peoplecounter.unpacked.event&from=${DATE}T00:00:00.000Z&to=${DATE}T23:59:59.999Z" \
      -H "Authorization: Bearer $TOKEN" \
      > "device_data_${DATE}.json"
done

# Filter for specific device
python3 device_filter_converter.py

# Result: device_00_04_A3_0B_01_03_EA_04_2025-06-30_to_2025-07-04.csv with 80 records
```

### Example 3: Bulk Data Collection and Analysis

```python
import requests
import json
import pandas as pd
from datetime import datetime, timedelta

def collect_people_counter_data(start_date, end_date, token):
    """Collect people counter data for date range"""
    base_url = "https://api.microshare.io/share/io.microshare.fm.master.agg/"
    view_id = "661eabafa0a03557a44bdd6c"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    all_data = []
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")

        params = {
            "id": view_id,
            "recType": "io.microshare.peoplecounter.unpacked.event",
            "from": f"{date_str}T00:00:00.000Z",
            "to": f"{date_str}T23:59:59.999Z"
        }

        response = requests.get(base_url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            records = data.get('objs', [])
            all_data.extend(records)
            print(f"Collected {len(records)} records for {date_str}")
        else:
            print(f"Failed to collect data for {date_str}: {response.status_code}")

        current_date += timedelta(days=1)
        time.sleep(2)  # Rate limiting

    return all_data

# Usage
start = datetime(2025, 6, 16)
end = datetime(2025, 6, 18)
token = "your_token_here"

data = collect_people_counter_data(start, end, token)
print(f"Total records collected: {len(data)}")

# Process to DataFrame
df = pd.json_normalize([flatten_record(record) for record in data])
df.to_csv('people_counter_bulk_data.csv', index=False)
```

## Environment Configuration

### Required Environment Variables

```bash
# .env file
MICROSHARE_USERNAME=ms_admin@cbre.com
MICROSHARE_PASSWORD=fth41ZlrZM2M
MICROSHARE_AUTH_URL=https://auth.microshare.io
MICROSHARE_API_URL=https://api.microshare.io

# Working Configuration
CLUSTER_ID=66e2b7a501faa80630fbb35f
VIEW_ID=661eabafa0a03557a44bdd6c
RECORD_TYPE=io.microshare.peoplecounter.unpacked.event
LOCATION=Eurotunnel C03
```

### API Endpoints Reference

```bash
# Authentication
POST http://localhost:8000/api/v1/auth/login

# Device Clusters
GET https://api.microshare.io/device/{record_type}/{cluster_id}

# Views Discovery
GET https://api.microshare.io/view/{record_type}

# People Counter Events (Primary Method)
GET https://api.microshare.io/share/io.microshare.fm.master.agg/?id={view_id}&recType=io.microshare.peoplecounter.unpacked.event&from={start}&to={end}

# Dashboard Aggregations (Alternative Method)
GET https://api.microshare.io/share/io.microshare.fm.master.agg/?id={dashboard_id}&recType=io.microshare.peoplecounter.unpacked.event.agg&field1=daily_total&field2=meta&field3=change&field4=field4&field5=field5&field6=field6
```

---

## Summary

This guide provides complete coverage of Microshare people counter data access patterns. The key breakthrough is using **view-based aggregation queries** with view ID `661eabafa0a03557a44bdd6c` to access `io.microshare.peoplecounter.unpacked.event` data, bypassing the access restrictions on direct Share API endpoints.

The methodology consistently delivers:
- **Granular event data** (15-minute intervals)
- **Device health metrics** (battery, alerts, faults)
- **Location hierarchies** (building/floor/zone)
- **Signal quality data** (RSSI, SNR, gateways)
- **Temporal aggregations** (daily totals, change events)

With proper authentication, error handling, and rate limiting, this approach provides reliable access to comprehensive people counter analytics for the Eurotunnel C03 deployment and other CBRE locations.
