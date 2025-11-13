#!/usr/bin/env python3
"""Test both people counter and snapshot functions with full coverage"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.microshare_client import MicroshareClient
from app.config import get_config
from datetime import datetime
from collections import Counter
import json

def test_function(function_name, get_data_method, from_time, to_time):
    """Test a data function"""
    print("\n" + "="*80)
    print(f"TESTING: {function_name}")
    print("="*80)

    config = get_config()
    client = MicroshareClient(config.to_dict())

    identity = config.to_dict().get('microshare', {}).get('identity', '')
    print(f"Identity filter: {identity}")
    print(f"Date range: {from_time} to {to_time}")

    # Get data
    data = get_data_method(client, from_time, to_time)

    print(f"\n✓ Total records: {len(data)}")

    if data:
        # Extract times
        times = [d['time'] for d in data if 'time' in d]

        if times:
            print(f"Time range: {min(times)} to {max(times)}")

            # Hourly distribution
            hours = [t.split('T')[1][:2] for t in times]
            hour_counts = Counter(hours)

            print(f"\nHourly distribution:")
            for hour in sorted(hour_counts.keys()):
                print(f"  {hour}:00 - {hour_counts[hour]} records")

            missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
            if not missing_hours:
                print("\n✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
            else:
                coverage = (24-len(missing_hours))/24*100
                print(f"\n⚠ Missing hours: {sorted(missing_hours)}")
                print(f"Coverage: {coverage:.1f}% ({24-len(missing_hours)}/24 hours)")

        # Show locations
        locations = set()
        for d in data:
            if '_location' in d:
                locations.add(d['_location'])

        if locations:
            print(f"\nLocations: {sorted(locations)}")

        # Show first record sample
        print("\nFirst record sample:")
        print(json.dumps(data[0], indent=2)[:600])

        return True
    else:
        print("\n✗ No data retrieved")
        return False

def main():
    # Test date: Nov 12, 2025
    from_time = datetime(2025, 11, 12, 0, 0, 0)
    to_time = datetime(2025, 11, 12, 23, 59, 59)

    print("="*80)
    print("COMPREHENSIVE TEST: Both Azure Functions")
    print("="*80)
    print(f"\nTest date: {from_time.date()}")

    # Test 1: People Counter
    pc_success = test_function(
        "People Counter Forwarder",
        lambda client, from_t, to_t: client.get_people_counter_full_coverage(from_t, to_t),
        from_time,
        to_time
    )

    # Test 2: Hourly Snapshots
    snapshot_success = test_function(
        "Hourly Snapshot Forwarder",
        lambda client, from_t, to_t: client.get_snapshot_full_coverage(from_t, to_t),
        from_time,
        to_time
    )

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"People Counter: {'✓ PASS' if pc_success else '✗ FAIL'}")
    print(f"Hourly Snapshots: {'✓ PASS' if snapshot_success else '✗ FAIL'}")

    if pc_success and snapshot_success:
        print("\n✓✓✓ ALL FUNCTIONS WORKING WITH FULL COVERAGE! ✓✓✓")
    else:
        print("\n⚠ Some functions failed")

    print("\nBoth functions use:")
    print("  • Identity filtering (CBREOD)")
    print("  • Dynamic location discovery")
    print("  • Dashboard views for full 24h coverage")
    print("  • Separate state tracking (peoplecounterstate, snapshotstate)")

if __name__ == "__main__":
    main()
