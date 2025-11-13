#!/usr/bin/env python3
"""Test dashboard view with MINIMAL parameters"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from collections import Counter
import requests
import json
from app.microshare_client import MicroshareClient
from app.config import get_config

def test_params(test_name, params, url="https://api.microshare.io/share/io.microshare.fm.master.agg/"):
    """Test a specific parameter combination"""
    config = get_config()
    client = MicroshareClient(config.to_dict())
    token = client._get_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    print("="*80)
    print(f"{test_name}")
    print("="*80)
    print(f"\nParams: {json.dumps(params, indent=2)}")

    response = requests.get(url, params=params, headers=headers)
    print(f"\nStatus: {response.status_code}")

    if response.status_code == 200:
        records = response.json().get('objs', [])
        print(f"Total records: {len(records)}")

        if records:
            # Check if it's dashboard format (with line array)
            if 'line' in records[0].get('data', {}):
                print("✓ Dashboard format detected (nested line array)")

                # Count total entries across all lines
                total_entries = sum(len(r['data'].get('line', [])) for r in records)
                print(f"  {len(records)} location groups")
                print(f"  {total_entries} total time entries across all locations")

                # Extract all times from line arrays
                all_times = []
                locations = []
                for r in records:
                    location = r['data']['_id'].get('tags', [])
                    locations.append(' > '.join(location) if isinstance(location, list) else str(location))

                    for entry in r['data'].get('line', []):
                        time = entry.get('time')
                        if time:
                            all_times.append(time)

                if all_times:
                    print(f"\n  Time range: {min(all_times)} to {max(all_times)}")

                    hours = [t.split('T')[1][:2] for t in all_times]
                    hour_counts = Counter(hours)
                    print(f"\n  Hourly coverage:")
                    for hour in sorted(hour_counts.keys()):
                        print(f"    {hour}:00 - {hour_counts[hour]} entries")

                    missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
                    if not missing_hours:
                        print("\n  ✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
                    else:
                        print(f"\n  ⚠ Missing hours: {sorted(missing_hours)}")
                        print(f"  Coverage: {(24-len(missing_hours))/24*100:.1f}%")

                print(f"\n  Locations found:")
                for loc in sorted(set(locations)):
                    print(f"    - {loc}")

            else:
                # Flat format
                print("✓ Flat format (individual records)")
                times = []
                for r in records:
                    try:
                        times.append(r['data']['createDate'])
                    except (KeyError, TypeError):
                        pass

                if times:
                    print(f"  Time range: {min(times)} to {max(times)}")
                    hours = [t.split('T')[1][:2] for t in times]
                    hour_counts = Counter(hours)
                    missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
                    if not missing_hours:
                        print("\n  ✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
                    else:
                        print(f"  Coverage: {(24-len(missing_hours))/24*100:.1f}%")
        else:
            print("⚠ No records returned")
    else:
        print(f"✗ Error: {response.text[:300]}")

    print()

def main():
    from_dt = datetime(2025, 11, 12, 0, 0, 0)
    to_dt = datetime(2025, 11, 12, 23, 59, 59)

    # Test 1: Absolutely minimal - just view ID and dates
    test_params("Test 1: MINIMAL - Just view ID, recType, from, to", {
        "id": "6148d9814827f67b1b319dd4",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z")
    })

    # Test 2: Add dataContext
    test_params("Test 2: Add dataContext", {
        "id": "6148d9814827f67b1b319dd4",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "dataContext": '["people"]'
    })

    # Test 3: Add field params (no loc1)
    test_params("Test 3: Add field1/2/3/4/5/6 (no loc1)", {
        "id": "6148d9814827f67b1b319dd4",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "dataContext": '["people"]',
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6"
    })

    # Test 4: Try with empty string loc1
    test_params("Test 4: Try empty string loc1", {
        "id": "6148d9814827f67b1b319dd4",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "dataContext": '["people"]',
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6",
        "loc1": ""
    })

    # Test 5: Try with wildcard loc1
    test_params("Test 5: Try wildcard loc1 (*)", {
        "id": "6148d9814827f67b1b319dd4",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "dataContext": '["people"]',
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6",
        "loc1": "*"
    })

    # Test 6: Try with regex loc1
    test_params("Test 6: Try regex loc1 (.*)", {
        "id": "6148d9814827f67b1b319dd4",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "dataContext": '["people"]',
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6",
        "loc1": ".*"
    })

if __name__ == "__main__":
    main()
