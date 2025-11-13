#!/usr/bin/env python3
"""Test dashboard view with location from guide (Eurotunnel C03)"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.microshare_client import MicroshareClient
from app.config import get_config
from datetime import datetime
from collections import Counter

def main():
    print("="*80)
    print("Testing Dashboard View with Eurotunnel C03 location (from guide)")
    print("="*80)

    config = get_config()
    config_dict = config.to_dict()

    # Dashboard view configuration from guide
    config_dict['microshare']['view_id'] = '6148d9814827f67b1b319dd4'
    config_dict['microshare']['rec_type'] = 'io.microshare.peoplecounter.unpacked.event.agg'
    config_dict['microshare']['location'] = 'Eurotunnel C03'  # From guide

    client = MicroshareClient(config_dict)

    # Test Nov 12
    from_time = datetime(2025, 11, 12, 0, 0, 0)
    to_time = datetime(2025, 11, 12, 23, 59, 59)

    print(f"\nQuerying with:")
    print(f"  View ID: 6148d9814827f67b1b319dd4")
    print(f"  recType: io.microshare.peoplecounter.unpacked.event.agg")
    print(f"  Location: Eurotunnel C03")
    print(f"  Date: Nov 12, 2025\n")

    try:
        records = client.get_snapshots_in_range(
            from_time=from_time,
            to_time=to_time
        )

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
                    print(f"\n⚠ Missing {len(missing_hours)} hours")
                    print(f"Coverage: {(24-len(missing_hours))/24*100:.1f}%")

    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "="*80)
    print("Now compare with Prony location (what we've been using)")
    print("="*80)

    config_dict['microshare']['location'] = 'Prony'
    client2 = MicroshareClient(config_dict)

    print(f"\nQuerying with:")
    print(f"  View ID: 6148d9814827f67b1b319dd4")
    print(f"  recType: io.microshare.peoplecounter.unpacked.event.agg")
    print(f"  Location: Prony")
    print(f"  Date: Nov 12, 2025\n")

    try:
        records2 = client2.get_snapshots_in_range(
            from_time=from_time,
            to_time=to_time
        )
        print(f"Total records: {len(records2)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
