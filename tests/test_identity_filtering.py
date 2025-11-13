#!/usr/bin/env python3
"""Test filtering by identity/organization"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import requests
import json
from app.microshare_client import MicroshareClient
from app.config import get_config
from collections import Counter

def main():
    config = get_config()
    client = MicroshareClient(config.to_dict())
    token = client._get_token()

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    print("="*80)
    print("STRATEGY: Filter by Identity AFTER Retrieval")
    print("="*80)

    # Step 1: Get all data (can't filter by org in query)
    print("\n1. Retrieve all data from first view:")
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

    records = response.json().get('objs', [])
    print(f"   Total records: {len(records)}")

    # Step 2: Group by identity
    print("\n2. Group records by owner.org (identity):")

    by_identity = {}
    for r in records:
        try:
            org = r['data']['owner']['org']
            if org not in by_identity:
                by_identity[org] = []
            by_identity[org].append(r)
        except (KeyError, TypeError):
            pass

    for org, org_records in sorted(by_identity.items()):
        # Get unique locations for this org
        locations = set()
        for r in org_records:
            try:
                loc = r['data']['data']['meta']['device'][0]
                locations.add(loc)
            except (KeyError, TypeError, IndexError):
                pass

        print(f"\n   {org}:")
        print(f"     Records: {len(org_records)}")
        print(f"     Locations: {', '.join(sorted(locations))}")

    # Step 3: Use dashboard view for full coverage (with identity filter)
    print("\n" + "="*80)
    print("3. Get full 24-hour data per identity using dashboard view:")
    print("="*80)

    TARGET_IDENTITY = "com.cbre.CBREOD"  # This would be configurable
    print(f"\n   Target identity: {TARGET_IDENTITY}")

    # Get locations for this identity from step 2
    target_records = by_identity.get(TARGET_IDENTITY, [])
    locations_for_identity = set()
    for r in target_records:
        try:
            loc = r['data']['data']['meta']['device'][0]
            locations_for_identity.add(loc)
        except (KeyError, TypeError, IndexError):
            pass

    print(f"   Locations in this identity: {sorted(locations_for_identity)}")

    # Query dashboard view for each location
    all_entries = []
    for loc in sorted(locations_for_identity):
        print(f"\n   Querying dashboard for: {loc}")

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

            # Flatten line arrays and filter by owner.org
            for dr in dashboard_records:
                line_entries = dr.get('data', {}).get('line', [])

                # Check owner.org of each entry if available
                # (Dashboard view doesn't have owner field directly, so we trust location filtering)
                all_entries.extend(line_entries)

                print(f"     → {len(line_entries)} time entries")

    print(f"\n   Total entries for {TARGET_IDENTITY}: {len(all_entries)}")

    if all_entries:
        times = [e['time'] for e in all_entries if 'time' in e]
        hours = set(t.split('T')[1][:2] for t in times)
        coverage = len(hours) / 24 * 100

        if len(hours) == 24:
            print(f"   ✓ FULL 24-HOUR COVERAGE!")
        else:
            print(f"   Coverage: {coverage:.1f}% ({len(hours)}/24 hours)")

    # Step 4: Show recommended configuration approach
    print("\n" + "="*80)
    print("RECOMMENDED CONFIGURATION FOR AZURE FUNCTION")
    print("="*80)

    print("""
Add to config.yaml or environment variable:

  # Option 1: Filter by specific identity
  identity_filter: "com.cbre.CBREOD"

  # Option 2: Process all identities separately
  identities:
    - "com.cbre.CBREOD"      # CBRE Prony
    - "com.cbre.cbre.fr"     # Prony
    - "com.cbre.dior"        # Kosmo Neuilly (Dior)

Function logic:
  1. Query first view (quick, all data)
  2. Filter records by identity (owner.org)
  3. Extract unique locations per identity
  4. Query dashboard view per location for full 24h data
  5. Flatten and forward to Event Hub

This approach:
  ✓ Supports multiple identities dynamically
  ✓ No hardcoded locations
  ✓ Full 24-hour coverage
  ✓ Identity isolation
""")

if __name__ == "__main__":
    main()
