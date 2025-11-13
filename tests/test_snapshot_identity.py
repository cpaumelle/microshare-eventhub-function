#!/usr/bin/env python3
"""Test snapshot data identity filtering approach"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.microshare_client import MicroshareClient
from app.config import get_config
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

    print("="*80)
    print("TESTING SNAPSHOT IDENTITY FILTERING APPROACH")
    print("="*80)

    # Test 1: Try querying snapshots WITHOUT loc1 to see if we get owner.org
    print("\n1. Testing snapshot query WITHOUT loc1 (discovery format?):")
    print("-" * 80)

    discovery_params = {
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
        "from": "2025-11-12T00:00:00.000Z",
        "to": "2025-11-12T23:59:59.999Z"
    }

    response = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=discovery_params,
        headers=headers
    )

    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        records = response.json().get('objs', [])
        print(f"Total records: {len(records)}")

        if records:
            # Check format and look for owner.org
            first_record = records[0]

            print("\nFirst record structure (checking for owner.org):")
            print(json.dumps(first_record, indent=2)[:1500])

            # Try to find owner.org
            has_owner_org = False
            owner_org_path = None

            # Check common paths
            if 'data' in first_record:
                if 'owner' in first_record['data']:
                    if 'org' in first_record['data']['owner']:
                        has_owner_org = True
                        owner_org_path = "data.owner.org"
                        print(f"\n✓ Found owner.org at: {owner_org_path}")
                        print(f"  Value: {first_record['data']['owner']['org']}")

            if 'owner' in first_record:
                if 'org' in first_record['owner']:
                    has_owner_org = True
                    owner_org_path = "owner.org"
                    print(f"\n✓ Found owner.org at: {owner_org_path}")
                    print(f"  Value: {first_record['owner']['org']}")

            if not has_owner_org:
                print("\n✗ No owner.org field found in response")

    elif response.status_code == 503:
        print("503 Error - Query requires loc1 parameter (dashboard only)")
        print(f"Error: {response.text[:300]}")
    else:
        print(f"Error: {response.text[:300]}")

    # Test 2: Check if we can use similar field params as people counter
    print("\n" + "="*80)
    print("2. Testing with people-counter-style field params:")
    print("-" * 80)

    alt_params = {
        "id": "63f49ba62c0e2e2b0ede4992",
        "recType": "io.microshare.lake.snapshot.hourly",
        "from": "2025-11-12T00:00:00.000Z",
        "to": "2025-11-12T23:59:59.999Z",
        "pageSize": 999,
        "dataContext": '["CBRE","occupancytesting","room"]',
        "field1": "current",
        "field2": "change",
        "field3": "meta",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6"
    }

    response2 = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=alt_params,
        headers=headers
    )

    print(f"Status: {response2.status_code}")

    if response2.status_code == 200:
        records2 = response2.json().get('objs', [])
        print(f"Total records: {len(records2)}")

        if records2:
            print("\nFirst record structure:")
            print(json.dumps(records2[0], indent=2)[:1500])

            # Look for owner.org
            if 'data' in records2[0] and 'owner' in records2[0]['data']:
                if 'org' in records2[0]['data']['owner']:
                    print(f"\n✓ Found owner.org: {records2[0]['data']['owner']['org']}")
    else:
        print(f"Error: {response2.text[:300]}")

    # Test 3: Try using the dashboard but checking locations we know
    print("\n" + "="*80)
    print("3. Testing known location with dashboard to infer identity:")
    print("-" * 80)
    print("Strategy: Query 'CBRE Prony' location (known CBREOD) vs other locations")

    # We know from people counter that "CBRE Prony" belongs to CBREOD
    dashboard_params = {
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
        "loc1": "CBRE Prony",  # Known CBREOD location
        "from": "2025-11-12T00:00:00.000Z",
        "to": "2025-11-12T23:59:59.999Z"
    }

    response3 = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=dashboard_params,
        headers=headers
    )

    print(f"\nQuerying loc1='CBRE Prony' (expected CBREOD)")
    print(f"Status: {response3.status_code}")

    if response3.status_code == 200:
        records3 = response3.json().get('objs', [])
        print(f"Total records: {len(records3)}")

        if records3 and 'line' in records3[0].get('data', {}):
            entries = len(records3[0]['data']['line'])
            print(f"Time entries: {entries}")

            # Show location tags
            if '_id' in records3[0]['data'] and 'tags' in records3[0]['data']['_id']:
                tags = records3[0]['data']['_id']['tags']
                print(f"Location tags: {tags}")

    print("\n" + "="*80)
    print("CONCLUSION:")
    print("="*80)
    print("Based on tests above, we need to determine:")
    print("1. Can we query snapshots in discovery format with owner.org?")
    print("2. Or should we assume location mapping from people counter applies?")
    print("3. Or do we need a separate mechanism to map locations to identities?")

if __name__ == "__main__":
    main()
