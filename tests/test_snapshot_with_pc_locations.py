#!/usr/bin/env python3
"""Test snapshot data using locations discovered from people counter with CBREOD filter"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.microshare_client import MicroshareClient
from app.config import get_config
from datetime import datetime
from collections import Counter
import requests
import json

def main():
    config = get_config()
    client = MicroshareClient(config.to_dict())
    token = client._get_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    identity_filter = config.to_dict().get('microshare', {}).get('identity', '')

    print("="*80)
    print("TESTING SNAPSHOT DATA WITH PEOPLE COUNTER LOCATIONS")
    print("="*80)
    print(f"Identity filter: {identity_filter}")

    # Step 1: Discover CBREOD locations from people counter
    print("\n" + "="*80)
    print("STEP 1: Discover CBREOD locations from people counter")
    print("="*80)

    discovery_params = {
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
        params=discovery_params,
        headers=headers
    )

    print(f"Discovery query status: {response.status_code}")

    cbreod_locations = set()
    if response.status_code == 200:
        records = response.json().get('objs', [])
        print(f"Total records: {len(records)}")

        for record in records:
            try:
                owner_org = record['data']['owner']['org']

                # Filter by CBREOD identity
                if identity_filter and identity_filter.upper() in owner_org.upper():
                    location = record['data']['data']['meta']['device'][0]
                    cbreod_locations.add(location)
            except (KeyError, TypeError, IndexError):
                pass

        print(f"\nCBREOD locations found: {sorted(cbreod_locations)}")

    if not cbreod_locations:
        print("\n✗ No CBREOD locations found. Cannot proceed.")
        return

    # Step 2: Try querying snapshots for each CBREOD location
    print("\n" + "="*80)
    print("STEP 2: Query snapshot data for CBREOD locations")
    print("="*80)

    all_snapshot_data = []
    successful_locations = []

    for location in sorted(cbreod_locations):
        print(f"\nQuerying snapshots for location: {location}")

        snapshot_params = {
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
            "loc1": location,
            "from": "2025-11-12T00:00:00.000Z",
            "to": "2025-11-12T23:59:59.999Z"
        }

        response = requests.get(
            "https://api.microshare.io/share/io.microshare.fm.master.agg/",
            params=snapshot_params,
            headers=headers
        )

        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            records = response.json().get('objs', [])
            print(f"  Records: {len(records)}")

            if records and 'line' in records[0].get('data', {}):
                entries = sum(len(r['data'].get('line', [])) for r in records)
                print(f"  Time entries: {entries}")

                successful_locations.append(location)

                # Collect all entries
                for record in records:
                    for entry in record['data'].get('line', []):
                        # Add location metadata
                        entry['_location'] = location
                        if '_id' in record['data'] and 'tags' in record['data']['_id']:
                            entry['_location_tags'] = record['data']['_id']['tags']

                        all_snapshot_data.append(entry)

    # Step 3: Analyze combined snapshot data
    print("\n" + "="*80)
    print("STEP 3: Analysis of CBREOD snapshot data")
    print("="*80)

    print(f"\nSuccessful locations: {successful_locations}")
    print(f"Total snapshot entries: {len(all_snapshot_data)}")

    if all_snapshot_data:
        # Extract times
        times = [e['time'] for e in all_snapshot_data if 'time' in e]

        if times:
            print(f"Time range: {min(times)} to {max(times)}")

            # Hourly distribution
            hours = [t.split('T')[1][:2] for t in times]
            hour_counts = Counter(hours)

            print("\nHourly distribution:")
            for hour in sorted(hour_counts.keys()):
                print(f"  {hour}:00 - {hour_counts[hour]} entries")

            missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
            if not missing_hours:
                print("\n✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
            else:
                coverage = (24-len(missing_hours))/24*100
                print(f"\n⚠ Missing hours: {sorted(missing_hours)}")
                print(f"Coverage: {coverage:.1f}% ({24-len(missing_hours)}/24 hours)")

        # Show unique location tags
        location_tags = set()
        for e in all_snapshot_data:
            if '_location_tags' in e:
                location_tags.add(tuple(e['_location_tags']))

        if location_tags:
            print(f"\nUnique location tags:")
            for tags in sorted(location_tags):
                print(f"  {' > '.join(tags)}")

        # Sample entry
        print("\nFirst snapshot entry sample:")
        print(json.dumps(all_snapshot_data[0], indent=2)[:800])

    # Step 4: Try location name variations if no results
    if not successful_locations:
        print("\n" + "="*80)
        print("STEP 4: Trying location name variations")
        print("="*80)

        for location in sorted(cbreod_locations):
            # Try variations: remove "CBRE " prefix, try "Prony" instead of "CBRE Prony", etc.
            variations = [
                location,
                location.replace("CBRE ", ""),
                location.split()[-1] if " " in location else location
            ]

            for variant in set(variations):
                if variant == location:
                    continue  # Already tried

                print(f"\nTrying variant '{variant}' (original: {location})")

                snapshot_params = {
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
                    "loc1": variant,
                    "from": "2025-11-12T00:00:00.000Z",
                    "to": "2025-11-12T23:59:59.999Z"
                }

                response = requests.get(
                    "https://api.microshare.io/share/io.microshare.fm.master.agg/",
                    params=snapshot_params,
                    headers=headers
                )

                print(f"  Status: {response.status_code}")

                if response.status_code == 200:
                    records = response.json().get('objs', [])
                    if records and 'line' in records[0].get('data', {}):
                        entries = sum(len(r['data'].get('line', [])) for r in records)
                        if entries > 0:
                            print(f"  ✓ SUCCESS with '{variant}': {entries} entries")
                            successful_locations.append((location, variant))

if __name__ == "__main__":
    main()
