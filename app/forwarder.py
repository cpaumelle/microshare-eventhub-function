"""
Microshare to Event Hub Forwarder
Simple application that pulls data from Microshare API and forwards to Azure Event Hub
"""

import logging
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

from app.microshare_client import MicroshareClient
from app.eventhub_client import EventHubClient
from app.state_manager import StateManager
from app.config import get_config

logger = logging.getLogger(__name__)


class MicroshareForwarder:
    """
    Main forwarder application
    Fetches data from Microshare API and forwards to Event Hub
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = get_config(config_path)
        self.microshare_client = MicroshareClient(self.config)
        self.eventhub_client = EventHubClient(self.config)
        
        # Get state file path from config or use default
        state_path = self.config.get("state_file", "/var/lib/microshare-forwarder/state.json")
        self.state_manager = StateManager(state_path)
        
        logger.info("Microshare Forwarder initialized")
    
    def fetch_and_forward(self) -> Tuple[int, int, int]:
        """
        Main execution: fetch from Microshare and forward to Event Hub
        
        Returns:
            Tuple of (snapshots_sent, duplicates_skipped, errors)
        """
        fetch_start = datetime.utcnow()
        
        try:
            # Determine fetch window
            last_fetch = self.state_manager.get_last_fetch_time()
            if last_fetch:
                from_time = datetime.fromisoformat(last_fetch.replace('Z', '+00:00'))
                logger.info(f"Fetching snapshots since {from_time}")
            else:
                # First run: fetch last 24 hours
                from_time = fetch_start - timedelta(hours=24)
                logger.info("First run: fetching last 24 hours of data")
            
            to_time = fetch_start
            
            # Fetch snapshots from Microshare (with pagination)
            logger.info(f"Calling Microshare API for data from {from_time} to {to_time}")
            snapshots = self.microshare_client.get_snapshots_in_range(
                from_time=from_time,
                to_time=to_time
            )

            total_records = len(snapshots)
            logger.info(f"Retrieved {total_records} snapshots from Microshare")
            
            if not snapshots:
                logger.info("No new snapshots to process")
                self.state_manager.update_after_fetch(
                    fetch_timestamp=fetch_start.isoformat(),
                    snapshots_sent=0,
                    duplicates_skipped=0,
                    success=True
                )
                return 0, 0, 0
            
            # Process and forward snapshots
            sent, duplicates, errors = self._process_snapshots(snapshots)
            
            # Update state
            last_snapshot_id = max([s.get('snapshot_id') for s in snapshots if s.get('snapshot_id')]) if snapshots else None
            devices = list(set([s.get('device_id') for s in snapshots if s.get('device_id')]))

            # Calculate pages (estimate based on page size of 999)
            pages_fetched = (total_records // 999) + (1 if total_records % 999 else 0) if total_records > 0 else 1

            self.state_manager.update_after_fetch(
                fetch_timestamp=fetch_start.isoformat(),
                snapshots_sent=sent,
                duplicates_skipped=duplicates,
                last_snapshot_id=last_snapshot_id,
                devices=devices,
                success=(errors == 0),
                pages_fetched=pages_fetched,
                total_records=total_records
            )
            
            logger.info(f"Fetch complete: sent={sent}, duplicates={duplicates}, errors={errors}")
            return sent, duplicates, errors
            
        except Exception as e:
            logger.error(f"Error in fetch_and_forward: {e}", exc_info=True)
            self.state_manager.update_after_fetch(
                fetch_timestamp=fetch_start.isoformat(),
                snapshots_sent=0,
                duplicates_skipped=0,
                success=False,
                error_message=str(e)
            )
            raise
    
    def _process_snapshots(self, snapshots: List[Dict[str, Any]]) -> Tuple[int, int, int]:
        """
        Process snapshots: deduplicate and send to Event Hub
        
        Returns:
            Tuple of (sent_count, duplicate_count, error_count)
        """
        sent = 0
        duplicates = 0
        errors = 0
        
        for snapshot in snapshots:
            try:
                snapshot_id = snapshot.get('snapshot_id')
                
                # Check for duplicates
                if snapshot_id and self.state_manager.is_duplicate(snapshot_id):
                    duplicates += 1
                    logger.debug(f"Skipping duplicate snapshot_id={snapshot_id}")
                    continue
                
                # Transform snapshot for Event Hub
                event_data = self._transform_snapshot(snapshot)
                
                # Send to Event Hub
                self.eventhub_client.send_event(event_data)
                sent += 1
                
                if sent % 10 == 0:
                    logger.info(f"Progress: sent {sent} snapshots")
                
            except Exception as e:
                errors += 1
                logger.error(f"Error processing snapshot: {e}")
                # Continue processing other snapshots
        
        return sent, duplicates, errors
    
    def _transform_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Microshare snapshot to Event Hub event format
        """
        # Add metadata
        event = snapshot.copy()
        event['forwarded_at'] = datetime.utcnow().isoformat()
        event['source'] = 'microshare-forwarder'
        
        return event
    
    def check_data_continuity(self, snapshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Check for gaps in data (missing snapshots)
        Returns list of detected gaps
        """
        gaps = []
        
        # Group by device
        by_device = {}
        for snapshot in snapshots:
            device_id = snapshot.get('device_id')
            if device_id:
                if device_id not in by_device:
                    by_device[device_id] = []
                by_device[device_id].append(snapshot)
        
        # Check each device for gaps
        expected_interval_minutes = 12  # Microshare sends every ~12 minutes
        
        for device_id, device_snapshots in by_device.items():
            # Sort by timestamp
            sorted_snapshots = sorted(
                device_snapshots,
                key=lambda s: s.get('timestamp', '')
            )
            
            for i in range(len(sorted_snapshots) - 1):
                current = sorted_snapshots[i]
                next_snap = sorted_snapshots[i + 1]
                
                try:
                    current_time = datetime.fromisoformat(current['timestamp'].replace('Z', '+00:00'))
                    next_time = datetime.fromisoformat(next_snap['timestamp'].replace('Z', '+00:00'))
                    
                    gap_minutes = (next_time - current_time).total_seconds() / 60
                    
                    if gap_minutes > expected_interval_minutes * 1.5:  # 18 minutes threshold
                        gap_info = {
                            'device_id': device_id,
                            'gap_start': current_time.isoformat(),
                            'gap_end': next_time.isoformat(),
                            'gap_minutes': gap_minutes,
                            'expected_minutes': expected_interval_minutes
                        }
                        gaps.append(gap_info)
                        logger.warning(f"Data gap detected: {gap_info}")
                
                except Exception as e:
                    logger.error(f"Error checking continuity: {e}")
        
        return gaps
    
    def get_stats(self) -> Dict[str, Any]:
        """Get forwarder statistics"""
        return self.state_manager.get_stats()
    
    def run_once(self):
        """Run one fetch cycle"""
        logger.info("="*80)
        logger.info("Microshare Forwarder - Starting fetch cycle")
        logger.info("="*80)
        
        try:
            sent, duplicates, errors = self.fetch_and_forward()
            
            logger.info("="*80)
            logger.info("Fetch cycle complete")
            logger.info(f"  Snapshots sent: {sent}")
            logger.info(f"  Duplicates skipped: {duplicates}")
            logger.info(f"  Errors: {errors}")
            
            stats = self.get_stats()
            logger.info(f"  Total sent (all time): {stats['total_sent']}")
            logger.info("="*80)
            
            return sent, duplicates, errors
            
        except Exception as e:
            logger.error(f"Fetch cycle failed: {e}", exc_info=True)
            raise


def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Create and run forwarder
    forwarder = MicroshareForwarder()
    forwarder.run_once()


if __name__ == "__main__":
    main()
