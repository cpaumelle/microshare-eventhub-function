#!/usr/bin/env python3
"""Test querying WITHOUT location filter"""

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
    # Get token using our client
    config = get_config()
    client = MicroshareClient(config.to_dict())
    token = client._get_token()

    from_dt = datetime(2025, 11, 12, 0, 0, 0)
    to_dt = datetime(2025, 11, 12, 23, 59, 59)

    print("="*80)
    print("Test 1: WITHOUT location filter (loc1 removed)")
    print("="*80)

    params = {
        "id": "661eabafa0a03557a44bdd6c",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "pageSize": 999,
        "dataContext": '["people"]',
        # NO loc1 parameter!
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6"
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print(f"\nQuery params (NO loc1):")
    print(json.dumps(params, indent=2))

    response = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=params,
        headers=headers
    )

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
                    print("\n✓ Full 24-hour coverage!")
                else:
                    print(f"\n⚠ Missing hours: {sorted(missing_hours)}")
                    print(f"Coverage: {(24-len(missing_hours))/24*100:.1f}%")

            # Show location diversity
            locations = set()
            for r in records[:50]:  # Sample first 50
                try:
                    device_meta = r['data']['data']['meta']['device']
                    if device_meta:
                        locations.add(device_meta[0] if isinstance(device_meta, list) else device_meta)
                except (KeyError, TypeError):
                    pass

            if locations:
                print(f"\nLocations in data: {locations}")
    else:
        print(f"Error: {response.text[:500]}")

    print("\n" + "="*80)
    print("Test 2: WITH location filter (loc1=Prony) - for comparison")
    print("="*80)

    params_with_loc = params.copy()
    params_with_loc["loc1"] = "Prony"

    print(f"\nQuery params (WITH loc1=Prony):")
    print(json.dumps(params_with_loc, indent=2))

    response2 = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=params_with_loc,
        headers=headers
    )

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
                    print("\n✓ Full 24-hour coverage!")
                else:
                    print(f"\n⚠ Missing hours: {sorted(missing_hours2)}")
                    print(f"Coverage: {(24-len(missing_hours2))/24*100:.1f}%")

if __name__ == "__main__":
    main()
