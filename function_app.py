import azure.functions as func
import logging
from datetime import datetime, timedelta
from app.config import get_config
from app.microshare_client import MicroshareClient
from app.eventhub_client import EventHubClient
from app.state_manager_azure import StateManagerAzure

app = func.FunctionApp()

@app.timer_trigger(
    schedule="0 0 * * * *",  # Run every hour at :00
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=False
)
def microshare_forwarder(mytimer: func.TimerRequest) -> None:
    """
    Fetch Microshare occupancy snapshots and forward to Azure Event Hub.
    
    Runs every hour via timer trigger.
    State is persisted in Azure Table Storage.
    """
    logging.info("="*80)
    logging.info("Microshare Forwarder - Starting fetch cycle")
    logging.info("="*80)
    
    try:
        # Load configuration from environment variables
        config = get_config()
        
        # Initialize clients
        ms_client = MicroshareClient(config)
        eh_client = EventHubClient(config)
        state_mgr = StateManagerAzure(config)
        
        # Get last successful fetch time
        last_fetch_time = state_mgr.get_last_fetch_time()
        current_time = datetime.utcnow()
        
        logging.info(f"Fetching snapshots since {last_fetch_time}")
        logging.info(f"Time window: {last_fetch_time} to {current_time}")
        
        # Fetch snapshots from Microshare
        snapshots = ms_client.get_snapshots_in_range(
            from_time=last_fetch_time,
            to_time=current_time
        )
        
        logging.info(f"Retrieved {len(snapshots)} device records from Microshare")
        
        if snapshots:
            # Send to Event Hub
            sent_count = eh_client.send_batch(snapshots)
            logging.info(f"✓ Sent {sent_count} snapshots to Event Hub")
            
            # Update state
            state_mgr.update_state(
                last_fetch_time=current_time,
                snapshots_sent=sent_count
            )
            
            logging.info("✓ State updated successfully")
        else:
            logging.info("No new snapshots to process")
        
        logging.info("="*80)
        logging.info("Fetch cycle complete - SUCCESS")
        logging.info(f"  Snapshots sent: {len(snapshots)}")
        logging.info(f"  Next run: {mytimer.schedule_status[Next]}")
        logging.info("="*80)
        
    except Exception as e:
        logging.error("="*80)
        logging.error(f"Fetch cycle FAILED: {e}")
        logging.error("="*80)
        logging.exception("Exception details:")
        raise
