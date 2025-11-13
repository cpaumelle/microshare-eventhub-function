#!/usr/bin/env python3
"""Test with dashboard view ID 6148d9814827f67b1b319dd4 and CBRE Prony location"""

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
    # Get token
    config = get_config()
    client = MicroshareClient(config.to_dict())
    token = client._get_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    print("="*80)
    print("Test 1: Dashboard view with CBRE Prony (Nov 8-9 from curl)")
    print("="*80)

    # Exact params from curl
    params = {
        "id": "6148d9814827f67b1b319dd4",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "dataContext": '["people"]',
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6",
        "loc1": "CBRE Prony",  # Space, not +
        "from": "2025-11-08T23:00:00.000Z",
        "to": "2025-11-09T23:00:00.000Z"
    }

    url = "https://api.microshare.io/share/io.microshare.fm.master.agg/"

    print(f"\nURL: {url}")
    print(f"Params: {json.dumps(params, indent=2)}")

    response = requests.get(url, params=params, headers=headers)
    print(f"\nStatus: {response.status_code}")

    if response.status_code == 200:
        records = response.json().get('objs', [])
        print(f"Total records: {len(records)}")

        if records:
            # Extract times
            times = []
            for r in records:
                try:
                    times.append(r['data']['createDate'])
                except (KeyError, TypeError):
                    pass

            if times:
                print(f"Time range: {min(times)} to {max(times)}")

                hours = [t.split('T')[1][:2] for t in times]
                hour_counts = Counter(hours)
                print("\nHourly distribution:")
                for hour in sorted(hour_counts.keys()):
                    print(f"  {hour}:00 - {hour_counts[hour]} records")

                missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
                if not missing_hours:
                    print("\n✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
                else:
                    print(f"\n⚠ Missing hours: {sorted(missing_hours)}")
                    print(f"Coverage: {(24-len(missing_hours))/24*100:.1f}%")

            # Show first record
            print("\nFirst record sample:")
            print(json.dumps(records[0], indent=2)[:600])
        else:
            print("No records returned")
    else:
        print(f"Error: {response.text[:500]}")

    print("\n" + "="*80)
    print("Test 2: Same view with Nov 12 (our date)")
    print("="*80)

    params2 = params.copy()
    params2["from"] = "2025-11-12T00:00:00.000Z"
    params2["to"] = "2025-11-12T23:59:59.999Z"

    print(f"\nParams: {json.dumps(params2, indent=2)}")

    response2 = requests.get(url, params=params2, headers=headers)
    print(f"\nStatus: {response2.status_code}")

    if response2.status_code == 200:
        records2 = response2.json().get('objs', [])
        print(f"Total records: {len(records2)}")

        if records2:
            times2 = []
            for r in records2:
                try:
                    times2.append(r['data']['createDate'])
                except (KeyError, TypeError):
                    pass

            if times2:
                print(f"Time range: {min(times2)} to {max(times2)}")
                hours2 = [t.split('T')[1][:2] for t in times2]
                hour_counts2 = Counter(hours2)

                print("\nHourly distribution:")
                for hour in sorted(hour_counts2.keys()):
                    print(f"  {hour}:00 - {hour_counts2[hour]} records")

                missing_hours2 = set(f"{h:02d}" for h in range(24)) - set(hour_counts2.keys())
                if not missing_hours2:
                    print("\n✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
                else:
                    print(f"\n⚠ Missing hours: {sorted(missing_hours2)}")
                    print(f"Coverage: {(24-len(missing_hours2))/24*100:.1f}%")
        else:
            print("No records returned")
    else:
        print(f"Error: {response2.text[:500]}")

    print("\n" + "="*80)
    print("Test 3: Without loc1 filter (dashboard view)")
    print("="*80)

    params3 = {
        "id": "6148d9814827f67b1b319dd4",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "dataContext": '["people"]',
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6",
        # NO loc1
        "from": "2025-11-12T00:00:00.000Z",
        "to": "2025-11-12T23:59:59.999Z"
    }

    print(f"\nParams: {json.dumps(params3, indent=2)}")

    response3 = requests.get(url, params=params3, headers=headers)
    print(f"\nStatus: {response3.status_code}")

    if response3.status_code == 200:
        records3 = response3.json().get('objs', [])
        print(f"Total records: {len(records3)}")

        if records3:
            times3 = []
            for r in records3:
                try:
                    times3.append(r['data']['createDate'])
                except (KeyError, TypeError):
                    pass

            if times3:
                print(f"Time range: {min(times3)} to {max(times3)}")
                hours3 = [t.split('T')[1][:2] for t in times3]
                hour_counts3 = Counter(hours3)

                print("\nHourly distribution:")
                for hour in sorted(hour_counts3.keys()):
                    print(f"  {hour}:00 - {hour_counts3[hour]} records")

                missing_hours3 = set(f"{h:02d}" for h in range(24)) - set(hour_counts3.keys())
                if not missing_hours3:
                    print("\n✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
                else:
                    print(f"\n⚠ Missing hours: {sorted(missing_hours3)}")
                    print(f"Coverage: {(24-len(missing_hours3))/24*100:.1f}%")
        else:
            print("No records returned")
    else:
        print(f"Error: {response3.text[:500]}")

if __name__ == "__main__":
    main()
