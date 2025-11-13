import azure.functions as func
import logging
import os
from datetime import datetime
from app.config import get_config
from app.microshare_client import MicroshareClient
from app.eventhub_client import EventHubClient
from app.state_manager_azure import StateManagerAzure
from app.state_manager import StateManager

app = func.FunctionApp()

def get_state_manager(config, table_name: str):
    """
    Factory function to get the appropriate state manager.
    Uses Azure Table Storage if running in Azure Functions,
    otherwise uses local file-based storage for VM deployment.
    """
    # Check if running in Azure Functions environment
    if os.environ.get('AzureWebJobsStorage'):
        logging.info(f"Using Azure Table Storage state manager (table: {table_name})")
        return StateManagerAzure(config, table_name=table_name)
    else:
        logging.info(f"Using local file-based state manager (file: /var/lib/microshare-forwarder/{table_name}.json)")
        # Use separate JSON files for each "table"
        return StateManager(state_file_path=f"/var/lib/microshare-forwarder/{table_name}.json")

def normalize_datetime(dt) -> datetime:
    """Convert various datetime formats to datetime object"""
    if isinstance(dt, datetime):
        return dt
    elif isinstance(dt, str):
        return datetime.fromisoformat(dt)
    elif dt is None:
        # Default to 24 hours ago
        from datetime import timedelta
        return datetime.utcnow() - timedelta(hours=24)
    else:
        raise ValueError(f"Cannot convert {type(dt)} to datetime")

def update_state_unified(state_mgr, last_fetch_time: datetime, snapshots_sent: int):
    """
    Unified state update that works with both state managers.
    Handles API differences between StateManagerAzure and StateManager.
    """
    if isinstance(state_mgr, StateManagerAzure):
        # Azure state manager expects datetime objects
        state_mgr.update_state(
            last_fetch_time=last_fetch_time,
            snapshots_sent=snapshots_sent
        )
    elif isinstance(state_mgr, StateManager):
        # Local state manager expects ISO strings
        state_mgr.update_after_fetch(
            fetch_timestamp=last_fetch_time.isoformat(),
            snapshots_sent=snapshots_sent,
            duplicates_skipped=0,
            success=True
        )
    else:
        raise ValueError(f"Unknown state manager type: {type(state_mgr)}")

# ============================================================================
# FUNCTION 1: Hourly Snapshot Data
# ============================================================================
# Fetches hourly aggregated occupancy snapshot data
# Default schedule: Every hour at :00 minutes
# ============================================================================

@app.timer_trigger(
    schedule="0 0 * * * *",  # Every hour at :00
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=False
)
def hourly_snapshot_forwarder(mytimer: func.TimerRequest) -> None:
    """
    Fetch hourly occupancy snapshots and forward to Azure Event Hub.
    Uses separate state tracking: 'snapshotstate'
    Uses full 24h coverage with identity filtering (same as people counter)
    """
    logging.info("="*80)
    logging.info("Hourly Snapshot Forwarder - Starting")
    logging.info("="*80)

    try:
        config = get_config()

        ms_client = MicroshareClient(config)
        eh_client = EventHubClient(config)

        # Use dedicated state table for hourly snapshots (auto-detects Azure vs local)
        state_mgr = get_state_manager(config, table_name='snapshotstate')

        last_fetch_time = normalize_datetime(state_mgr.get_last_fetch_time())
        current_time = datetime.utcnow()

        identity_filter = config.get('microshare', {}).get('identity', '')
        logging.info(f"Fetching hourly snapshots since {last_fetch_time}")
        logging.info(f"Identity filter: {identity_filter}")

        # Use new method with full 24h coverage and identity filtering
        snapshots = ms_client.get_snapshot_full_coverage(
            from_time=last_fetch_time,
            to_time=current_time
        )

        logging.info(f"Retrieved {len(snapshots)} snapshot entries (full 24h coverage)")

        if snapshots:
            sent_count = eh_client.send_batch(snapshots)
            logging.info(f"Sent {sent_count} snapshots to Event Hub")

            update_state_unified(
                state_mgr=state_mgr,
                last_fetch_time=current_time,
                snapshots_sent=sent_count
            )

        logging.info("Hourly Snapshot Forwarder - SUCCESS")

    except Exception as e:
        logging.error(f"Hourly Snapshot Forwarder FAILED: {e}")
        logging.exception("Exception details:")
        raise


# ============================================================================
# FUNCTION 2: People Counter Data
# ============================================================================
# Fetches 15-minute interval people counter event data
# Uses view-based query method (see MICROSHARE_PEOPLE_COUNTER_QUERY_GUIDE.md)
# Default schedule: Every 15 minutes
# ============================================================================

@app.timer_trigger(
    schedule="0 */15 * * * *",  # Every 15 minutes
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=False
)
def people_counter_forwarder(mytimer: func.TimerRequest) -> None:
    """
    Fetch people counter unpacked event data and forward to Azure Event Hub.
    Uses separate state tracking: 'peoplecounterstate'

    Note: People counter data requires different view_id and recType than hourly snapshots.
    See MICROSHARE_PEOPLE_COUNTER_QUERY_GUIDE.md for details.
    """
    logging.info("="*80)
    logging.info("People Counter Forwarder - Starting")
    logging.info("="*80)

    try:
        config = get_config()

        ms_client = MicroshareClient(config)
        eh_client = EventHubClient(config)

        # Use dedicated state table for people counter (auto-detects Azure vs local)
        state_mgr = get_state_manager(config, table_name='peoplecounterstate')

        last_fetch_time = normalize_datetime(state_mgr.get_last_fetch_time())
        current_time = datetime.utcnow()

        identity_filter = config.get('microshare', {}).get('identity', '')
        logging.info(f"Fetching people counter data since {last_fetch_time}")
        logging.info(f"Identity filter: {identity_filter}")

        # Use new method with full 24h coverage and identity filtering
        events = ms_client.get_people_counter_full_coverage(
            from_time=last_fetch_time,
            to_time=current_time
        )

        logging.info(f"Retrieved {len(events)} people counter events (full 24h coverage)")

        if events:
            sent_count = eh_client.send_batch(events)
            logging.info(f"Sent {sent_count} people counter events to Event Hub")

            update_state_unified(
                state_mgr=state_mgr,
                last_fetch_time=current_time,
                snapshots_sent=sent_count
            )

        logging.info("People Counter Forwarder - SUCCESS")

    except Exception as e:
        logging.error(f"People Counter Forwarder FAILED: {e}")
        logging.exception("Exception details:")
        raise
