#!/usr/bin/env python3
"""Test the TWO correct view/recType combinations from the guide"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.microshare_client import MicroshareClient
from app.config import get_config
from datetime import datetime
from collections import Counter
import json

def test_combination(view_id, rec_type, description):
    """Test a specific view/recType combination"""
    print("="*80)
    print(f"Testing: {description}")
    print(f"View ID: {view_id}")
    print(f"recType: {rec_type}")
    print("="*80)

    config = get_config()
    config_dict = config.to_dict()
    config_dict['microshare']['view_id'] = view_id
    config_dict['microshare']['rec_type'] = rec_type

    client = MicroshareClient(config_dict)

    # Test Nov 12 full day
    from_time = datetime(2025, 11, 12, 0, 0, 0)
    to_time = datetime(2025, 11, 12, 23, 59, 59)

    try:
        records = client.get_snapshots_in_range(
            from_time=from_time,
            to_time=to_time
        )

        print(f"\n✓ Total records: {len(records)}")

        if records:
            # Extract times based on record structure
            times = []
            for r in records:
                try:
                    # Try createDate first
                    times.append(r['data']['createDate'])
                except (KeyError, TypeError):
                    try:
                        # Try meta.iot.time
                        times.append(r['data']['meta']['iot']['time'])
                    except (KeyError, TypeError):
                        try:
                            # Try constructing from daily_total
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

                # Check coverage
                missing_hours = set(f"{h:02d}" for h in range(24)) - set(hour_counts.keys())
                if missing_hours:
                    print(f"\n⚠ Missing hours: {sorted(missing_hours)} ({len(missing_hours)}/24)")
                    print(f"Coverage: {(24-len(missing_hours))/24*100:.1f}%")
                else:
                    print("\n✓ Full 24-hour coverage!")

            # Show sample record structure
            print("\nFirst record structure (first 800 chars):")
            print(json.dumps(records[0], indent=2)[:800])
        else:
            print("⚠ No records returned")

    except Exception as e:
        print(f"\n✗ Error: {e}")

    print("\n")

def main():
    print("\n" + "="*80)
    print("TESTING CORRECT VIEW/RECTYPE COMBINATIONS FROM GUIDE")
    print("="*80 + "\n")

    # Method 1: Event data (15-min intervals)
    test_combination(
        view_id="661eabafa0a03557a44bdd6c",
        rec_type="io.microshare.peoplecounter.unpacked.event",
        description="Method 1: Granular Event Data (15-min intervals)"
    )

    # Method 2: Aggregated dashboard data (hourly)
    test_combination(
        view_id="6148d9814827f67b1b319dd4",
        rec_type="io.microshare.peoplecounter.unpacked.event.agg",
        description="Method 2: Pre-Aggregated Dashboard Data (hourly)"
    )

    # For comparison: What we've been using (wrong combo)
    test_combination(
        view_id="661eabafa0a03557a44bdd6c",
        rec_type="io.microshare.peoplecounter.unpacked.event.agg",
        description="What we've been using (MIXED - wrong combo)"
    )

if __name__ == "__main__":
    main()
