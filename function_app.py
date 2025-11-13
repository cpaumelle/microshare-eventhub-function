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
    """
    logging.info("="*80)
    logging.info("Hourly Snapshot Forwarder - Starting")
    logging.info("="*80)
    
    try:
        config = get_config()
        
        # Override recType for hourly snapshots
        config['microshare']['rec_type'] = 'io.microshare.lake.snapshot.hourly'
        
        ms_client = MicroshareClient(config)
        eh_client = EventHubClient(config)
        
        # Use dedicated state table for hourly snapshots
        state_mgr = StateManagerAzure(config, table_name='snapshotstate')
        
        last_fetch_time = state_mgr.get_last_fetch_time()
        current_time = datetime.utcnow()
        
        logging.info(f"Fetching hourly snapshots since {last_fetch_time}")
        
        snapshots = ms_client.get_snapshots_in_range(
            from_time=last_fetch_time,
            to_time=current_time
        )
        
        logging.info(f"Retrieved {len(snapshots)} snapshot records")
        
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
# FUNCTION 2: People Counter Data (OPTIONAL)
# ============================================================================
# Fetches 15-minute aggregated people counter data
# Default schedule: Every 15 minutes
# Comment out this entire function block if not needed
# ============================================================================

@app.timer_trigger(
    schedule="0 */15 * * * *",  # Every 15 minutes
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=False
)
def people_counter_forwarder(mytimer: func.TimerRequest) -> None:
    """
    Fetch people counter data every 15 minutes.
    Uses separate state tracking: 'peoplecounterstate'
    """
    logging.info("="*80)
    logging.info("People Counter Forwarder - Starting")
    logging.info("="*80)
    
    try:
        config = get_config()
        
        # Override recType for people counter
        config['microshare']['rec_type'] = 'io.microshare.peoplecounter.unpacked.event.agg'
        
        ms_client = MicroshareClient(config)
        eh_client = EventHubClient(config)
        
        # Use dedicated state table for people counter
        state_mgr = StateManagerAzure(config, table_name='peoplecounterstate')
        
        last_fetch_time = state_mgr.get_last_fetch_time()
        current_time = datetime.utcnow()
        
        logging.info(f"Fetching people counter data since {last_fetch_time}")
        
        snapshots = ms_client.get_snapshots_in_range(
            from_time=last_fetch_time,
            to_time=current_time
        )
        
        logging.info(f"Retrieved {len(snapshots)} people counter records")
        
        if snapshots:
            sent_count = eh_client.send_batch(snapshots)
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


# ============================================================================
# FUNCTION 3: Occupancy Sensors (OPTIONAL)
# ============================================================================
# Fetches real-time occupancy sensor data
# Default schedule: Every 5 minutes
# Comment out this entire function block if not needed
# ============================================================================

@app.timer_trigger(
    schedule="0 */5 * * * *",  # Every 5 minutes
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=False
)
def occupancy_sensor_forwarder(mytimer: func.TimerRequest) -> None:
    """
    Fetch occupancy sensor data every 5 minutes.
    Uses separate state tracking: 'occupancysensorstate'
    """
    logging.info("="*80)
    logging.info("Occupancy Sensor Forwarder - Starting")
    logging.info("="*80)
    
    try:
        config = get_config()
        
        # Override recType for occupancy sensors
        config['microshare']['rec_type'] = 'io.microshare.occupancy.unpacked'
        
        ms_client = MicroshareClient(config)
        eh_client = EventHubClient(config)
        
        # Use dedicated state table for occupancy sensors
        state_mgr = StateManagerAzure(config, table_name='occupancysensorstate')
        
        last_fetch_time = state_mgr.get_last_fetch_time()
        current_time = datetime.utcnow()
        
        logging.info(f"Fetching occupancy sensor data since {last_fetch_time}")
        
        snapshots = ms_client.get_snapshots_in_range(
            from_time=last_fetch_time,
            to_time=current_time
        )
        
        logging.info(f"Retrieved {len(snapshots)} occupancy sensor records")
        
        if snapshots:
            sent_count = eh_client.send_batch(snapshots)
            logging.info(f"Sent {sent_count} occupancy events to Event Hub")
            
            state_mgr.update_state(
                last_fetch_time=current_time,
                snapshots_sent=sent_count
            )
        
        logging.info("Occupancy Sensor Forwarder - SUCCESS")
        
    except Exception as e:
        logging.error(f"Occupancy Sensor Forwarder FAILED: {e}")
        logging.exception("Exception details:")
        raise
