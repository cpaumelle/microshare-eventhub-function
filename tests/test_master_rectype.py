#!/usr/bin/env python3
"""Test querying with master recType instead of peoplecounter recType"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.microshare_client import MicroshareClient
from app.config import get_config
from datetime import datetime
from collections import Counter

def main():
    # Test Nov 12 full day with MASTER recType
    print("="*80)
    print("Testing with io.microshare.fm.master.agg (MASTER recType)")
    print("="*80)

    from_time = datetime(2025, 11, 12, 0, 0, 0)
    to_time = datetime(2025, 11, 12, 23, 59, 59)

    # Create config with MASTER recType and PEOPLE COUNTER view
    config = get_config()
    config_dict = config.to_dict()
    config_dict['microshare']['rec_type'] = 'io.microshare.fm.master.agg'
    config_dict['microshare']['view_id'] = '661eabafa0a03557a44bdd6c'  # People counter view
    client = MicroshareClient(config_dict)

    records = client.get_snapshots_in_range(
        from_time=from_time,
        to_time=to_time
    )

    print(f"\nTotal records: {len(records)}")

    if records:
        times = [r['data']['meta']['iot']['time'] for r in records]
        print(f"Time range: {min(times)} to {max(times)}")

        # Hourly distribution
        hours = [t.split('T')[1][:2] for t in times]
        hour_counts = Counter(hours)
        print("\nHourly distribution:")
        for hour in sorted(hour_counts.keys()):
            print(f"  {hour}:00 - {hour_counts[hour]} records")

        # Show sample record
        print("\nFirst record:")
        import json
        print(json.dumps(records[0], indent=2)[:1000])
    else:
        print("No records returned")

    print("\n" + "="*80)
    print("Now comparing with io.microshare.peoplecounter.unpacked.event.agg")
    print("="*80)

    # Create new client with peoplecounter recType
    config2 = get_config()
    config2_dict = config2.to_dict()
    config2_dict['microshare']['rec_type'] = 'io.microshare.peoplecounter.unpacked.event.agg'
    config2_dict['microshare']['view_id'] = '661eabafa0a03557a44bdd6c'  # People counter view
    client2 = MicroshareClient(config2_dict)

    records2 = client2.get_snapshots_in_range(
        from_time=from_time,
        to_time=to_time
    )

    print(f"\nTotal records: {len(records2)}")

    if records2:
        # Extract times - people counter uses createDate, not meta.iot.time
        times2 = []
        for r in records2:
            try:
                # Try data.meta.iot.time first (hourly snapshots)
                times2.append(r['data']['meta']['iot']['time'])
            except (KeyError, TypeError):
                try:
                    # Try createDate (people counter)
                    times2.append(r['data']['createDate'])
                except (KeyError, TypeError):
                    try:
                        # Construct from daily_total fields
                        date = r['data']['data']['daily_total']['date']
                        hour = r['data']['data']['daily_total']['hour']
                        times2.append(f"{date}T{hour:02d}:00:00.000Z")
                    except (KeyError, TypeError):
                        pass

        if times2:
            print(f"Time range: {min(times2)} to {max(times2)}")

            # Hourly distribution
            hours2 = [t.split('T')[1][:2] for t in times2]
            hour_counts2 = Counter(hours2)
            print("\nHourly distribution:")
            for hour in sorted(hour_counts2.keys()):
                print(f"  {hour}:00 - {hour_counts2[hour]} records")

        # Show sample record for debugging
        print("\nFirst record structure:")
        import json
        print(json.dumps(records2[0], indent=2)[:1000])

if __name__ == "__main__":
    main()
