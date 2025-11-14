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
    Uses Azure Table Storage if running in Azure Functions App (cloud),
    otherwise uses local file-based storage for VM/local deployment.
    """
    # Check if running in real Azure Functions App environment
    azure_storage_conn = os.environ.get('AzureWebJobsStorage', '')

    # Valid Azure Storage connection strings contain these markers
    is_valid_azure_storage = (
        azure_storage_conn and
        'AccountName=' in azure_storage_conn and
        'AccountKey=' in azure_storage_conn
    )

    if is_valid_azure_storage:
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

def update_state_unified(state_mgr, last_fetch_time: datetime, events_sent: int):
    """
    Unified state update that works with both state managers.
    Handles API differences between StateManagerAzure and StateManager.

    Args:
        state_mgr: State manager instance (Azure or local file-based)
        last_fetch_time: Timestamp of last successful fetch
        events_sent: Number of events/items sent to Event Hub
    """
    if isinstance(state_mgr, StateManagerAzure):
        # Azure state manager expects datetime objects
        state_mgr.update_state(
            last_fetch_time=last_fetch_time,
            snapshots_sent=events_sent  # Keep old param name for compatibility
        )
    elif isinstance(state_mgr, StateManager):
        # Local state manager expects ISO strings
        state_mgr.update_after_fetch(
            fetch_timestamp=last_fetch_time.isoformat(),
            snapshots_sent=events_sent,  # Keep old param name for compatibility
            duplicates_skipped=0,
            success=True
        )
    else:
        raise ValueError(f"Unknown state manager type: {type(state_mgr)}")


def run_forwarder(
    forwarder_name: str,
    state_table: str,
    fetch_function,
    config,
    data_type_name: str = "events"
):
    """
    Generic forwarder function that handles common orchestration logic.

    This eliminates code duplication between different recType forwarders while
    allowing each to maintain their specific data formats and retrieval methods.

    Args:
        forwarder_name: Display name for logging (e.g., "Hourly Snapshot Forwarder")
        state_table: State table/file name (e.g., "snapshotstate", "peoplecounterstate")
        fetch_function: Callable that fetches data. Signature: (ms_client, from_time, to_time) -> List
        config: Application configuration object
        data_type_name: Name for logging what was sent (e.g., "events", "snapshot responses")

    Returns:
        None (raises exception on failure)
    """
    logging.info("="*80)
    logging.info(f"{forwarder_name} - Starting")
    logging.info("="*80)

    try:
        # Initialize clients
        ms_client = MicroshareClient(config)
        eh_client = EventHubClient(config)

        # Setup state management (auto-detects Azure vs local)
        state_mgr = get_state_manager(config, table_name=state_table)

        # Get time window for fetch
        last_fetch_time = normalize_datetime(state_mgr.get_last_fetch_time())
        current_time = datetime.utcnow()

        # Log configuration
        identity_filter = config.get('microshare', {}).get('identity', '')
        logging.info(f"Fetching {data_type_name} since {last_fetch_time}")
        logging.info(f"Identity filter: {identity_filter}")

        # Call the specific fetch function (people counter vs snapshot)
        items = fetch_function(ms_client, last_fetch_time, current_time)

        logging.info(f"Retrieved {len(items)} {data_type_name}")

        # Send to Event Hub if we got data
        if items:
            sent_count = eh_client.send_events_batch(items)
            logging.info(f"Sent {sent_count} {data_type_name} to Event Hub")

            # Update state after successful send
            update_state_unified(
                state_mgr=state_mgr,
                last_fetch_time=current_time,
                events_sent=sent_count
            )

        logging.info(f"{forwarder_name} - SUCCESS")

    except Exception as e:
        logging.error(f"{forwarder_name} FAILED: {e}")
        logging.exception("Exception details:")
        raise


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

    - Uses separate state tracking: 'snapshotstate'
    - Data format: Complete API response with {meta, objs[], recType}
    - Provides full 24h coverage with identity filtering
    """
    config = get_config()
    run_forwarder(
        forwarder_name="Hourly Snapshot Forwarder",
        state_table="snapshotstate",
        fetch_function=lambda client, from_time, to_time:
            client.get_snapshot_full_coverage(from_time, to_time),
        config=config,
        data_type_name="snapshot API response(s)"
    )


# ============================================================================
# FUNCTION 2: People Counter Data - DISABLED
# ============================================================================
# Fetches 15-minute interval people counter event data
# Uses view-based query method (see MICROSHARE_PEOPLE_COUNTER_QUERY_GUIDE.md)
# Default schedule: Every 15 minutes
# STATUS: Temporarily disabled - only using hourly snapshots
# ============================================================================

# @app.timer_trigger(
#     schedule="0 */15 * * * *",  # Every 15 minutes
#     arg_name="mytimer",
#     run_on_startup=False,
#     use_monitor=False
# )
# def people_counter_forwarder(mytimer: func.TimerRequest) -> None:
#     """
#     Fetch people counter unpacked event data and forward to Azure Event Hub.
#
#     - Uses separate state tracking: 'peoplecounterstate'
#     - Data format: Flattened individual events with recType field
#     - Provides full 24h coverage with identity filtering
#     - Note: Uses different view_id and recType than snapshots
#     """
#     config = get_config()
#     run_forwarder(
#         forwarder_name="People Counter Forwarder",
#         state_table="peoplecounterstate",
#         fetch_function=lambda client, from_time, to_time:
#             client.get_people_counter_full_coverage(from_time, to_time),
#         config=config,
#         data_type_name="people counter events"
#     )
