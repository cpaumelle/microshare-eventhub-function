import azure.functions as func
import logging
from datetime import datetime
from app.config import get_config
from app.microshare_client import MicroshareClient
from app.eventhub_client import EventHubClient
from app.state_manager_azure import StateManagerAzure

app = func.FunctionApp()

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

        # Use dedicated state table for hourly snapshots
        state_mgr = StateManagerAzure(config, table_name='snapshotstate')

        last_fetch_time = state_mgr.get_last_fetch_time()
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

            state_mgr.update_state(
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

        # Use dedicated state table for people counter
        state_mgr = StateManagerAzure(config, table_name='peoplecounterstate')

        last_fetch_time = state_mgr.get_last_fetch_time()
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

            state_mgr.update_state(
                last_fetch_time=current_time,
                snapshots_sent=sent_count
            )

        logging.info("People Counter Forwarder - SUCCESS")

    except Exception as e:
        logging.error(f"People Counter Forwarder FAILED: {e}")
        logging.exception("Exception details:")
        raise
