#!/usr/bin/env python3
"""Test the full snapshot implementation with identity filtering"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.microshare_client import MicroshareClient
from app.config import get_config
from datetime import datetime
from collections import Counter
import json

def main():
    config = get_config()
    client = MicroshareClient(config.to_dict())

    identity = config.to_dict().get('microshare', {}).get('identity', '')

    print("="*80)
    print("TESTING FULL SNAPSHOT IMPLEMENTATION")
    print("="*80)
    print(f"\nIdentity filter: {identity}")

    # Test with Nov 12 (full day)
    from_time = datetime(2025, 11, 12, 0, 0, 0)
    to_time = datetime(2025, 11, 12, 23, 59, 59)

    print(f"\nDate range: {from_time} to {to_time}")

    snapshots = client.get_snapshot_full_coverage(
        from_time=from_time,
        to_time=to_time
    )

    print(f"\n✓ Total snapshots: {len(snapshots)}")

    if snapshots:
        # Extract times
        times = []
        for s in snapshots:
            if 'time' in s:
                times.append(s['time'])

        if times:
            print(f"Time range: {min(times)} to {max(times)}")

            # Hourly distribution
            hours = [t.split('T')[1][:2] for t in times]
            hour_counts = Counter(hours)

            print("\nHourly distribution:")
            for hour in sorted(hour_counts.keys()):
                print(f"  {hour}:00 - {hour_counts[hour]} snapshots")

            missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
            if not missing_hours:
                print("\n✓✓✓ FULL 24-HOUR COVERAGE! ✓✓✓")
            else:
                print(f"\n⚠ Missing hours: {sorted(missing_hours)}")
                print(f"Coverage: {(24-len(missing_hours))/24*100:.1f}%")

        # Show location tags
        location_tags = set()
        for s in snapshots:
            tags = s.get('_location_tags', [])
            if tags:
                location_tags.add(tuple(tags))

        if location_tags:
            print(f"\nLocation tags found:")
            for tags in sorted(location_tags):
                print(f"  {' > '.join(tags)}")

        # Show unique locations
        locations = set()
        for s in snapshots:
            if '_location' in s:
                locations.add(s['_location'])

        if locations:
            print(f"\nSnapshot locations: {sorted(locations)}")

        # Show first snapshot sample
        print("\nFirst snapshot sample:")
        print(json.dumps(snapshots[0], indent=2)[:1000])

if __name__ == "__main__":
    main()
