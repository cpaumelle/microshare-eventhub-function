#!/usr/bin/env python3
"""Test hourly snapshot data coverage"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from collections import Counter
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
    print("TESTING HOURLY SNAPSHOT DATA COVERAGE")
    print("="*80)

    # Test with the exact params from curl (Oct 30-31)
    print("\n1. Testing Oct 30-31 (from curl):")

    params = {
        "id": "63f49ba62c0e2e2b0ede4992",
        "recType": "io.microshare.lake.snapshot.hourly",
        "dataContext": '["CBRE","occupancytesting","room"]',
        "field1": "current",
        "field2": "field2",
        "field3": "field3",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6",
        "category": "space",
        "metric": "occupancy",
        "ownerOrg": '"[a-zA-Z]"',
        "loc1": "Prony",
        "from": "2025-10-30T23:00:00.000Z",
        "to": "2025-10-31T23:00:00.000Z"
    }

    response = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=params,
        headers=headers
    )

    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        records = response.json().get('objs', [])
        print(f"   Total records: {len(records)}")

        if records:
            # Check if it's dashboard format with line array
            if 'line' in records[0].get('data', {}):
                print("   Format: Dashboard (nested line array)")

                total_entries = sum(len(r['data'].get('line', [])) for r in records)
                print(f"   Total time entries: {total_entries}")

                # Extract times from line arrays
                all_times = []
                for r in records:
                    for entry in r['data'].get('line', []):
                        time = entry.get('time')
                        if time:
                            all_times.append(time)

                if all_times:
                    print(f"   Time range: {min(all_times)} to {max(all_times)}")

                    hours = [t.split('T')[1][:2] for t in all_times]
                    hour_counts = Counter(hours)

                    print(f"\n   Hourly distribution:")
                    for hour in sorted(hour_counts.keys()):
                        print(f"     {hour}:00 - {hour_counts[hour]} entries")

                    missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
                    if not missing_hours:
                        print("\n   ✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
                    else:
                        print(f"\n   ⚠ Missing hours: {sorted(missing_hours)}")
                        print(f"   Coverage: {(24-len(missing_hours))/24*100:.1f}%")
            else:
                # Flat format
                print("   Format: Flat (individual records)")

                times = []
                for r in records:
                    try:
                        # Try different time fields
                        time = r.get('createDate') or r.get('data', {}).get('createDate') or r.get('tstamp')
                        if time:
                            times.append(time)
                    except (KeyError, TypeError):
                        pass

                if times:
                    print(f"   Time range: {min(times)} to {max(times)}")

                    hours = [t.split('T')[1][:2] if 'T' in t else t.split()[1][:2] for t in times]
                    hour_counts = Counter(hours)

                    print(f"\n   Hourly distribution:")
                    for hour in sorted(hour_counts.keys()):
                        print(f"     {hour}:00 - {hour_counts[hour]} records")

                    missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
                    if not missing_hours:
                        print("\n   ✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
                    else:
                        print(f"\n   ⚠ Missing hours: {sorted(missing_hours)}")
                        print(f"   Coverage: {(24-len(missing_hours))/24*100:.1f}%")

            # Show sample record
            print("\n   First record structure (truncated):")
            print(json.dumps(records[0], indent=2)[:800])

    else:
        print(f"   Error: {response.text[:300]}")

    # Test 2: Try without loc1 to see if it works like people counter
    print("\n" + "="*80)
    print("2. Testing WITHOUT loc1 parameter:")
    print("="*80)

    params_no_loc = params.copy()
    del params_no_loc['loc1']

    response2 = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=params_no_loc,
        headers=headers
    )

    print(f"   Status: {response2.status_code}")

    if response2.status_code == 200:
        records2 = response2.json().get('objs', [])
        print(f"   Total records: {len(records2)}")

        if records2 and 'line' in records2[0].get('data', {}):
            total_entries2 = sum(len(r['data'].get('line', [])) for r in records2)
            print(f"   Total time entries: {total_entries2}")
    else:
        print(f"   Error: {response2.text[:200]}")

    # Test 3: Recent date (Nov 12)
    print("\n" + "="*80)
    print("3. Testing recent date (Nov 12):")
    print("="*80)

    params3 = params.copy()
    params3['from'] = "2025-11-12T00:00:00.000Z"
    params3['to'] = "2025-11-12T23:59:59.999Z"

    response3 = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=params3,
        headers=headers
    )

    print(f"   Status: {response3.status_code}")

    if response3.status_code == 200:
        records3 = response3.json().get('objs', [])
        print(f"   Total records: {len(records3)}")

        if records3:
            if 'line' in records3[0].get('data', {}):
                total_entries3 = sum(len(r['data'].get('line', [])) for r in records3)
                print(f"   Total time entries: {total_entries3}")

                all_times3 = []
                for r in records3:
                    for entry in r['data'].get('line', []):
                        time = entry.get('time')
                        if time:
                            all_times3.append(time)

                if all_times3:
                    hours3 = [t.split('T')[1][:2] for t in all_times3]
                    hour_counts3 = Counter(hours3)
                    missing_hours3 = set(f"{h:02d}" for h in range(24)) - set(hour_counts3.keys())

                    if not missing_hours3:
                        print("   ✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
                    else:
                        coverage = (24-len(missing_hours3))/24*100
                        print(f"   Coverage: {coverage:.1f}% ({24-len(missing_hours3)}/24 hours)")
            else:
                # Flat format
                times3 = []
                for r in records3:
                    try:
                        time = r.get('createDate') or r.get('data', {}).get('createDate')
                        if time:
                            times3.append(time)
                    except:
                        pass

                if times3:
                    hours3 = [t.split('T')[1][:2] for t in times3]
                    hour_counts3 = Counter(hours3)
                    missing_hours3 = set(f"{h:02d}" for h in range(24)) - set(hour_counts3.keys())

                    if not missing_hours3:
                        print("   ✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
                    else:
                        coverage = (24-len(missing_hours3))/24*100
                        print(f"   Coverage: {coverage:.1f}% ({24-len(missing_hours3)}/24 hours)")

if __name__ == "__main__":
    main()
