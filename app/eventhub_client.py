"""
Event Hub Client - Simplified
Sends data dictionaries to Azure Event Hub (no database dependencies)
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from azure.eventhub import EventHubProducerClient, EventData
from azure.eventhub.exceptions import EventHubError

logger = logging.getLogger(__name__)


class EventHubClientError(Exception):
    """Raised when Event Hub operations fail"""
    pass


class EventHubClient:
    """
    Simplified Azure Event Hub client
    Works with dictionaries instead of ORM objects
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Event Hub client with support for multiple Event Hubs

        Args:
            config: Configuration dictionary with event_hub settings
        """
        self.config = config
        eh_config = config.get('event_hub', {})

        # Support both single connection string and multiple
        connection_string = eh_config.get('connection_string')
        connection_strings = eh_config.get('connection_strings', [])

        # Build list of connection strings
        self.connection_strings = []
        if connection_string:
            self.connection_strings.append(connection_string)
        if connection_strings:
            self.connection_strings.extend(connection_strings)

        if not self.connection_strings:
            raise ValueError("Event Hub connection string(s) missing in config")

        self.max_batch_size = eh_config.get('batch_size', 100)
        self._producers: List[EventHubProducerClient] = []

        logger.info(f"EventHubClient initialized with {len(self.connection_strings)} Event Hub(s)")
    
    def _get_producers(self) -> List[EventHubProducerClient]:
        """Get or create Event Hub producer clients for all configured hubs"""
        if not self._producers:
            try:
                for i, conn_str in enumerate(self.connection_strings):
                    producer = EventHubProducerClient.from_connection_string(conn_str)
                    self._producers.append(producer)
                    # Extract hub name from connection string for logging
                    hub_name = "unknown"
                    if "EntityPath=" in conn_str:
                        hub_name = conn_str.split("EntityPath=")[1].split(";")[0]
                    logger.info(f"Event Hub producer {i+1} created: {hub_name}")
            except Exception as e:
                logger.error(f"Failed to create Event Hub producer: {e}")
                raise EventHubClientError(f"Failed to create producer: {e}")

        return self._producers
    
    def send_event(self, event_data: Dict[str, Any], properties: Optional[Dict[str, str]] = None):
        """
        Send single event to Event Hub
        
        Args:
            event_data: Event data dictionary
            properties: Optional custom properties for routing/filtering
        """
        try:
            producer = self._get_producer()
            
            # Create Event Data
            event = EventData(json.dumps(event_data))
            
            # Add properties
            if properties:
                event.properties = properties
            elif 'device_id' in event_data:
                # Default properties
                event.properties = {
                    'device_id': event_data.get('device_id', ''),
                    'source': 'microshare-forwarder'
                }
            
            # Send
            with producer:
                producer.send_batch([event])
            
            logger.debug(f"Event sent: device_id={event_data.get('device_id')}")
            
        except EventHubError as e:
            logger.error(f"Event Hub error: {e}")
            raise EventHubClientError(f"Event Hub send failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending to Event Hub: {e}", exc_info=True)
            raise EventHubClientError(f"Unexpected error: {e}")
    
    def send_events_batch(self, events: List[Dict[str, Any]]) -> int:
        """
        Send multiple events to ALL configured Event Hubs in batches

        Args:
            events: List of event data dictionaries

        Returns:
            Number of events successfully sent (to first hub, all hubs get same count)
        """
        if not events:
            logger.debug("No events to send")
            return 0

        try:
            producers = self._get_producers()

            total_sent = 0
            batch_count = 0

            # Process in batches
            for i in range(0, len(events), self.max_batch_size):
                batch = events[i:i + self.max_batch_size]
                batch_count += 1

                # Create event batch
                event_batch = []
                for event_data in batch:
                    event = EventData(json.dumps(event_data))

                    # Add properties
                    event.properties = {
                        'device_id': event_data.get('device_id', ''),
                        'source': 'microshare-forwarder'
                    }

                    if 'location' in event_data and 'building' in event_data['location']:
                        event.properties['building'] = event_data['location']['building']

                    event_batch.append(event)

                # Send batch to ALL Event Hubs
                logger.debug(f"Sending batch {batch_count} with {len(event_batch)} events to {len(producers)} hub(s)")

                for hub_idx, producer in enumerate(producers):
                    with producer:
                        producer.send_batch(event_batch)
                    logger.debug(f"  → Hub {hub_idx + 1}: Batch {batch_count} sent")

                total_sent += len(batch)
                logger.info(f"Batch {batch_count} sent: {len(batch)} events")

            logger.info(f"Successfully sent {total_sent} events in {batch_count} batches to {len(producers)} Event Hub(s)")
            return total_sent

        except EventHubError as e:
            logger.error(f"Event Hub error while sending batch: {e}")
            raise EventHubClientError(f"Event Hub batch send failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error while sending batch to Event Hub: {e}", exc_info=True)
            raise EventHubClientError(f"Unexpected error: {e}")
    
    def test_connection(self) -> bool:
        """
        Test Event Hub connection
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            producer = self._get_producer()
            
            # Send a test event
            test_data = {
                'test': True,
                'timestamp': datetime.utcnow().isoformat(),
                'message': 'Connection test from Microshare Forwarder'
            }
            
            event = EventData(json.dumps(test_data))
            event.properties = {'source': 'microshare-forwarder', 'test': True}
            
            with producer:
                producer.send_batch([event])
            
            logger.info("✓ Event Hub connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"✗ Event Hub connection test failed: {e}")
            return False
    
    def close(self):
        """Close all Event Hub producer connections"""
        for i, producer in enumerate(self._producers):
            try:
                producer.close()
                logger.info(f"Event Hub producer {i+1} closed")
            except Exception as e:
                logger.warning(f"Error closing Event Hub producer {i+1}: {e}")
        self._producers = []
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
