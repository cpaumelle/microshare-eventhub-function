#!/usr/bin/env python3
"""Test querying people counter recType WITHOUT using a view"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from collections import Counter
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    # Get credentials from env
    username = os.getenv("MICROSHARE_USERNAME")
    password = os.getenv("MICROSHARE_PASSWORD")
    api_key = os.getenv("MICROSHARE_API_KEY")

    print(f"Using username: {username}")
    if not all([username, password, api_key]):
        print("ERROR: Missing credentials in .env file")
        return

    # Get JWT token
    print("Authenticating...")
    auth_url = "https://auth.microshare.io/enduser/token"
    payload = {"username": username, "password": password}
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    response = requests.post(auth_url, json=payload, headers=headers)

    print(f"Auth status: {response.status_code}")
    if response.status_code != 200:
        print(f"Auth failed: {response.text}")
        return

    try:
        token = response.json().get("access_token")
    except Exception as e:
        print(f"Failed to parse auth response: {e}")
        print(f"Response text: {response.text}")
        return

    print("✓ Authenticated")

    # Test Nov 12 full day WITHOUT view
    print("="*80)
    print("Querying io.microshare.peoplecounter.unpacked.event.agg WITHOUT view")
    print("="*80)

    from_dt = datetime(2025, 11, 12, 0, 0, 0)
    to_dt = datetime(2025, 11, 12, 23, 59, 59)

    # Query WITHOUT view ID - just the recType endpoint
    params = {
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "pageSize": 999,
        # Note: NO view ID parameter!
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Try the recType endpoint directly
    url = "https://api.microshare.io/share/io.microshare.peoplecounter.unpacked.event.agg/"

    print(f"\nQuerying: {url}")
    print(f"Params: {json.dumps(params, indent=2)}")

    response = requests.get(url, params=params, headers=headers)

    print(f"\nStatus: {response.status_code}")

    if response.status_code != 200:
        print(f"Error response: {response.text[:500]}")
        return

    data = response.json()
    records = data.get('objs', [])
    print(f"Total records: {len(records)}")

    if records:
        # Extract times
        times = []
        for r in records:
            try:
                times.append(r.get('createDate') or r['data'].get('createDate'))
            except (KeyError, TypeError, AttributeError):
                try:
                    date = r['data']['data']['daily_total']['date']
                    hour = r['data']['data']['daily_total']['hour']
                    times.append(f"{date}T{hour:02d}:00:00.000Z")
                except (KeyError, TypeError):
                    pass

        if times:
            print(f"Time range: {min(times)} to {max(times)}")

            # Hourly distribution
            hours = [t.split('T')[1][:2] for t in times]
            hour_counts = Counter(hours)
            print("\nHourly distribution:")
            for hour in sorted(hour_counts.keys()):
                print(f"  {hour}:00 - {hour_counts[hour]} records")

            # Check for 24-hour coverage
            missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
            if missing_hours:
                print(f"\nMissing hours: {sorted(missing_hours)}")
            else:
                print("\n✓ Full 24-hour coverage!")

        # Show sample record
        print("\nFirst record sample:")
        print(json.dumps(records[0], indent=2)[:1000])
    else:
        print("No records returned")

    print("\n" + "="*80)
    print("Now compare with VIEW-based query (view ID 661eabafa0a03557a44bdd6c)")
    print("="*80)

    params_with_view = {
        "id": "661eabafa0a03557a44bdd6c",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "pageSize": 999,
        "dataContext": '["people"]',
        "loc1": "Prony",
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6"
    }

    response2 = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=params_with_view,
        headers=headers
    )

    print(f"Status: {response2.status_code}")
    records2 = response2.json().get('objs', [])
    print(f"Total records with view: {len(records2)}")

    if records2:
        # Extract times for view-based query
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

if __name__ == "__main__":
    main()
