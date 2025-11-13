#!/usr/bin/env python3
"""Test if we can discover available locations dynamically"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import requests
import json
from app.microshare_client import MicroshareClient
from app.config import get_config

def main():
    config = get_config()
    client = MicroshareClient(config.to_dict())
    token = client._get_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    print("="*80)
    print("Test 1: Query first view to extract unique locations from metadata")
    print("="*80)

    # Get sample data from first view (limited but fast)
    params = {
        "id": "661eabafa0a03557a44bdd6c",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": "2025-11-12T00:00:00.000Z",
        "to": "2025-11-12T23:59:59.999Z",
        "pageSize": 999,
        "dataContext": '["people"]',
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6"
    }

    response = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=params,
        headers=headers
    )

    if response.status_code == 200:
        records = response.json().get('objs', [])
        print(f"\nGot {len(records)} records from first view")

        # Extract unique locations from meta.device
        locations = set()
        for r in records:
            try:
                device_meta = r['data']['data']['meta']['device']
                if isinstance(device_meta, list) and len(device_meta) > 0:
                    # First element is typically the location
                    locations.add(device_meta[0])
            except (KeyError, TypeError):
                pass

        print(f"\nUnique locations found: {len(locations)}")
        for loc in sorted(locations):
            print(f"  - {loc}")

        if locations:
            print("\n" + "="*80)
            print("Test 2: Use discovered locations with dashboard view")
            print("="*80)

            # Test each location with dashboard view
            for loc in sorted(locations):
                print(f"\nQuerying dashboard view with loc1='{loc}'...")

                dashboard_params = {
                    "id": "6148d9814827f67b1b319dd4",
                    "recType": "io.microshare.peoplecounter.unpacked.event.agg",
                    "from": "2025-11-12T00:00:00.000Z",
                    "to": "2025-11-12T23:59:59.999Z",
                    "dataContext": '["people"]',
                    "field1": "daily_total",
                    "field2": "meta",
                    "field3": "change",
                    "field4": "field4",
                    "field5": "field5",
                    "field6": "field6",
                    "loc1": loc
                }

                dashboard_response = requests.get(
                    "https://api.microshare.io/share/io.microshare.fm.master.agg/",
                    params=dashboard_params,
                    headers=headers
                )

                if dashboard_response.status_code == 200:
                    dashboard_records = dashboard_response.json().get('objs', [])
                    print(f"  → {len(dashboard_records)} location groups")

                    if dashboard_records and 'line' in dashboard_records[0].get('data', {}):
                        total_entries = sum(len(r['data'].get('line', [])) for r in dashboard_records)
                        print(f"  → {total_entries} total time entries")

                        # Check hourly coverage
                        all_times = []
                        for r in dashboard_records:
                            for entry in r['data'].get('line', []):
                                time = entry.get('time')
                                if time:
                                    all_times.append(time)

                        if all_times:
                            hours = set(t.split('T')[1][:2] for t in all_times)
                            coverage = len(hours) / 24 * 100
                            if len(hours) == 24:
                                print(f"  → ✓ FULL 24-HOUR COVERAGE!")
                            else:
                                print(f"  → {coverage:.1f}% coverage ({len(hours)}/24 hours)")
                else:
                    print(f"  → Error {dashboard_response.status_code}")

            print("\n" + "="*80)
            print("STRATEGY")
            print("="*80)
            print("To get full 24-hour coverage with dynamic locations:")
            print("1. Query first view (quick, limited) to discover locations")
            print("2. For each location, query dashboard view (full 24h data)")
            print("3. Flatten and combine all line[] arrays into events")
            print("\nPros:")
            print("  ✓ Full 24-hour coverage")
            print("  ✓ Dynamic location discovery (no hardcoding)")
            print("\nCons:")
            print("  ✗ Multiple API calls per run")
            print("  ✗ More complex data processing")

    else:
        print(f"Error: {response.status_code}")

if __name__ == "__main__":
    main()
