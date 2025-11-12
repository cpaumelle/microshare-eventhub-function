"""
Simple JSON-based state management
Replaces database with lightweight file-based persistence
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ForwarderState:
    """State of the forwarder"""
    last_fetch_timestamp: Optional[str] = None
    last_snapshot_id: Optional[int] = None
    total_snapshots_sent: int = 0
    total_duplicates_skipped: int = 0
    total_errors: int = 0
    last_success_timestamp: Optional[str] = None
    last_error_timestamp: Optional[str] = None
    last_error_message: Optional[str] = None
    devices_tracked: List[str] = None
    # Pagination tracking
    total_pages_fetched: int = 0
    max_pages_in_single_fetch: int = 0
    last_pagination_warning: Optional[str] = None

    def __post_init__(self):
        if self.devices_tracked is None:
            self.devices_tracked = []


class StateManager:
    """Manages forwarder state using JSON file"""
    
    def __init__(self, state_file_path: str = "/var/lib/microshare-forwarder/state.json"):
        self.state_file_path = Path(state_file_path)
        self.state = ForwarderState()
        self._recent_snapshot_ids: Set[int] = set()
        self._load_state()
    
    def _ensure_directory(self):
        """Ensure state directory exists"""
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_state(self):
        """Load state from JSON file"""
        try:
            if self.state_file_path.exists():
                with open(self.state_file_path, 'r') as f:
                    data = json.load(f)
                    self.state = ForwarderState(**data)
                    logger.info(f"Loaded state from {self.state_file_path}")
                    logger.info(f"Last fetch: {self.state.last_fetch_timestamp}, "
                              f"Total sent: {self.state.total_snapshots_sent}")
            else:
                logger.info("No existing state file, starting fresh")
                self._save_state()
        except Exception as e:
            logger.error(f"Error loading state: {e}, starting with empty state")
            self.state = ForwarderState()
    
    def _save_state(self):
        """Save state to JSON file"""
        try:
            self._ensure_directory()
            with open(self.state_file_path, 'w') as f:
                json.dump(asdict(self.state), f, indent=2)
            logger.debug(f"State saved to {self.state_file_path}")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def is_duplicate(self, snapshot_id: int) -> bool:
        """
        Check if snapshot ID is a duplicate
        Uses in-memory set for fast lookups
        """
        if snapshot_id in self._recent_snapshot_ids:
            return True
        
        # Keep only recent IDs in memory (last 1000)
        if len(self._recent_snapshot_ids) > 1000:
            # Remove oldest half
            sorted_ids = sorted(self._recent_snapshot_ids)
            self._recent_snapshot_ids = set(sorted_ids[500:])
        
        self._recent_snapshot_ids.add(snapshot_id)
        return False
    
    def update_after_fetch(
        self,
        fetch_timestamp: str,
        snapshots_sent: int,
        duplicates_skipped: int,
        last_snapshot_id: Optional[int] = None,
        devices: Optional[List[str]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        pages_fetched: int = 1,
        total_records: Optional[int] = None
    ):
        """Update state after a fetch operation"""
        self.state.last_fetch_timestamp = fetch_timestamp
        self.state.total_snapshots_sent += snapshots_sent
        self.state.total_duplicates_skipped += duplicates_skipped

        if last_snapshot_id:
            self.state.last_snapshot_id = last_snapshot_id

        if devices:
            # Update devices list (union)
            existing = set(self.state.devices_tracked)
            new_devices = set(devices)
            self.state.devices_tracked = list(existing.union(new_devices))

        # Track pagination metrics
        self.state.total_pages_fetched += pages_fetched
        if pages_fetched > self.state.max_pages_in_single_fetch:
            self.state.max_pages_in_single_fetch = pages_fetched

        # Alert if multiple pages required
        if pages_fetched > 1:
            warning_msg = (
                f"High data volume: {pages_fetched} pages fetched "
                f"({total_records} records) - consider polling more frequently"
            )
            self.state.last_pagination_warning = datetime.utcnow().isoformat()
            logger.warning(f"⚠️  {warning_msg}")

        if success:
            self.state.last_success_timestamp = datetime.utcnow().isoformat()
        else:
            self.state.total_errors += 1
            self.state.last_error_timestamp = datetime.utcnow().isoformat()
            self.state.last_error_message = error_message

        self._save_state()
    
    def get_last_fetch_time(self) -> Optional[str]:
        """Get last successful fetch timestamp"""
        return self.state.last_fetch_timestamp
    
    def get_stats(self) -> Dict:
        """Get current statistics"""
        return {
            "last_fetch": self.state.last_fetch_timestamp,
            "total_sent": self.state.total_snapshots_sent,
            "total_duplicates": self.state.total_duplicates_skipped,
            "total_errors": self.state.total_errors,
            "last_success": self.state.last_success_timestamp,
            "last_error": self.state.last_error_timestamp,
            "devices_count": len(self.state.devices_tracked),
            "devices": self.state.devices_tracked
        }
    
    def reset(self):
        """Reset all state (for testing)"""
        self.state = ForwarderState()
        self._recent_snapshot_ids = set()
        self._save_state()
        logger.info("State reset")
