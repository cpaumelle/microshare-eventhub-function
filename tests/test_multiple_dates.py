#!/usr/bin/env python3
"""Test first view across multiple dates to see if coverage issue is date-specific"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from collections import Counter
import requests
import json
from app.microshare_client import MicroshareClient
from app.config import get_config

def test_date(date_str, description):
    """Test a specific date"""
    config = get_config()
    client = MicroshareClient(config.to_dict())
    token = client._get_token()

    from_dt = datetime.strptime(date_str, "%Y-%m-%d")
    to_dt = from_dt + timedelta(hours=23, minutes=59, seconds=59)

    params = {
        "id": "661eabafa0a03557a44bdd6c",
        "recType": "io.microshare.peoplecounter.unpacked.event.agg",
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "pageSize": 999,
        "dataContext": '["people"]',
        "field1": "daily_total",
        "field2": "meta",
        "field3": "change",
        "field4": "field4",
        "field5": "field5",
        "field6": "field6"
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    print("="*80)
    print(f"{description}: {date_str}")
    print("="*80)

    response = requests.get(
        "https://api.microshare.io/share/io.microshare.fm.master.agg/",
        params=params,
        headers=headers
    )

    if response.status_code == 200:
        records = response.json().get('objs', [])
        print(f"Total records: {len(records)}")

        if records:
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

                hours_with_data = sorted(hour_counts.keys())
                print(f"Hours with data: {', '.join(hours_with_data)}")

                missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
                coverage = (24-len(missing_hours))/24*100

                if not missing_hours:
                    print("✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
                else:
                    print(f"Coverage: {coverage:.1f}% ({24-len(missing_hours)}/24 hours)")

                # Check for zero counts
                zero_count = 0
                for r in records:
                    try:
                        change = r['data']['data']['change']
                        if change.get('in', 0) == 0 and change.get('out', 0) == 0:
                            zero_count += 1
                    except (KeyError, TypeError):
                        pass

                if zero_count > 0:
                    print(f"Zero-count records: {zero_count}/{len(records)} ({zero_count/len(records)*100:.1f}%)")
        else:
            print("No records returned")
    else:
        print(f"Error {response.status_code}: {response.text[:200]}")

    print()

def main():
    # Test multiple recent dates
    print("\nTesting view 661eabafa0a03557a44bdd6c across multiple dates")
    print("="*80)
    print()

    # Test last 7 days
    test_date("2025-11-06", "Thursday Nov 6")
    test_date("2025-11-07", "Friday Nov 7")
    test_date("2025-11-08", "Saturday Nov 8")
    test_date("2025-11-09", "Sunday Nov 9")
    test_date("2025-11-10", "Monday Nov 10")
    test_date("2025-11-11", "Tuesday Nov 11")
    test_date("2025-11-12", "Wednesday Nov 12")
    test_date("2025-11-13", "Thursday Nov 13 (today)")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("If all dates show similar limited coverage (19:00-23:59), then:")
    print("  → This is likely the view's pipeline filtering issue")
    print("  → The view pipeline filters on 'data.meta.iot.time'")
    print("  → But people counter uses 'data.createDate'")
    print("\nIf some dates have full coverage, then:")
    print("  → The data collection itself may be incomplete for certain dates")

if __name__ == "__main__":
    main()
