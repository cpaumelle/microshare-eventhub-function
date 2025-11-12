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
        Initialize Event Hub client
        
        Args:
            config: Configuration dictionary with event_hub settings
        """
        self.config = config
        eh_config = config.get('event_hub', {})
        
        self.connection_string = eh_config.get('connection_string')
        self.max_batch_size = eh_config.get('batch_size', 100)
        
        if not self.connection_string:
            raise ValueError("Event Hub connection string missing in config")
        
        self._producer: Optional[EventHubProducerClient] = None
        
        logger.info("EventHubClient initialized")
    
    def _get_producer(self) -> EventHubProducerClient:
        """Get or create Event Hub producer client"""
        if self._producer is None:
            try:
                self._producer = EventHubProducerClient.from_connection_string(
                    self.connection_string
                )
                logger.debug("Event Hub producer client created")
            except Exception as e:
                logger.error(f"Failed to create Event Hub producer: {e}")
                raise EventHubClientError(f"Failed to create producer: {e}")
        
        return self._producer
    
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
        Send multiple events to Event Hub in batches
        
        Args:
            events: List of event data dictionaries
        
        Returns:
            Number of events successfully sent
        """
        if not events:
            logger.debug("No events to send")
            return 0
        
        try:
            producer = self._get_producer()
            
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
                
                # Send batch
                logger.debug(f"Sending batch {batch_count} with {len(event_batch)} events")
                
                with producer:
                    producer.send_batch(event_batch)
                
                total_sent += len(batch)
                logger.info(f"Batch {batch_count} sent: {len(batch)} events")
            
            logger.info(f"Successfully sent {total_sent} events in {batch_count} batches")
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
        """Close Event Hub producer connection"""
        if self._producer:
            try:
                self._producer.close()
                logger.info("Event Hub producer closed")
            except Exception as e:
                logger.warning(f"Error closing Event Hub producer: {e}")
            finally:
                self._producer = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
