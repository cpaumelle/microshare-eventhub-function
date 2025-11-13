"""
State Manager for Azure Functions
Uses Azure Table Storage for persistent state across function executions
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from azure.data.tables import TableServiceClient, TableEntity
from azure.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


class StateManagerAzure:
    """
    Manage forwarder state using Azure Table Storage.

    State includes:
    - last_fetch_time: When we last successfully fetched from Microshare
    - total_snapshots_sent: Running total of snapshots forwarded
    - last_run_timestamp: When the function last ran
    """

    DEFAULT_TABLE_NAME = "microshareforwarderstate"
    PARTITION_KEY = "forwarder"
    ROW_KEY = "state"

    def __init__(self, config, table_name: Optional[str] = None):
        """
        Initialize state manager with Azure Table Storage.

        Args:
            config: Configuration object (not used, kept for compatibility)
            table_name: Optional custom table name for multi-function deployments.
                       Each function should use a unique table name to avoid conflicts.
                       Defaults to 'microshareforwarderstate'
        """
        # Get connection string from environment
        connection_string = os.environ.get('AzureWebJobsStorage')

        if not connection_string:
            raise ValueError(
                "AzureWebJobsStorage environment variable not set. "
                "This is automatically provided by Azure Functions runtime."
            )

        # Use custom table name if provided, otherwise use default
        self.table_name = table_name or self.DEFAULT_TABLE_NAME

        # Initialize Table Service Client
        self.table_service = TableServiceClient.from_connection_string(connection_string)
        self.table_client = self.table_service.get_table_client(self.table_name)

        # Ensure table exists
        self._ensure_table_exists()

        logger.info(f"StateManagerAzure initialized with table: {self.table_name}")

    def _ensure_table_exists(self):
        """Create table if it doesn't exist"""
        try:
            self.table_service.create_table(self.table_name)
            logger.info(f"Created new table: {self.table_name}")
        except Exception as e:
            # Table likely already exists
            logger.debug(f"Table {self.table_name} already exists or error: {e}")

    def get_last_fetch_time(self) -> datetime:
        """
        Get the last successful fetch time from state.

        Returns:
            datetime: Last fetch time, or 24 hours ago if no state exists
        """
        try:
            entity = self.table_client.get_entity(
                partition_key=self.PARTITION_KEY,
                row_key=self.ROW_KEY
            )

            last_fetch_str = entity.get('last_fetch_time')
            if last_fetch_str:
                last_fetch = datetime.fromisoformat(last_fetch_str)
                logger.info(f"Retrieved last fetch time from state: {last_fetch}")
                return last_fetch
            else:
                logger.warning("State exists but no last_fetch_time found")
                return self._default_start_time()

        except ResourceNotFoundError:
            logger.info("No existing state found, using default start time")
            return self._default_start_time()
        except Exception as e:
            logger.error(f"Error reading state: {e}")
            return self._default_start_time()

    def _default_start_time(self) -> datetime:
        """Return default start time (24 hours ago)"""
        default = datetime.utcnow() - timedelta(hours=24)
        logger.info(f"Using default start time: {default}")
        return default

    def update_state(self, last_fetch_time: datetime, snapshots_sent: int):
        """
        Update state after successful run.

        Args:
            last_fetch_time: Time of this successful fetch
            snapshots_sent: Number of snapshots sent in this run
        """
        try:
            # Try to get existing entity to preserve total count
            try:
                existing = self.table_client.get_entity(
                    partition_key=self.PARTITION_KEY,
                    row_key=self.ROW_KEY
                )
                total_snapshots = existing.get('total_snapshots_sent', 0) + snapshots_sent
            except ResourceNotFoundError:
                total_snapshots = snapshots_sent

            # Create/update entity
            entity = {
                'PartitionKey': self.PARTITION_KEY,
                'RowKey': self.ROW_KEY,
                'last_fetch_time': last_fetch_time.isoformat(),
                'last_run_timestamp': datetime.utcnow().isoformat(),
                'snapshots_sent_this_run': snapshots_sent,
                'total_snapshots_sent': total_snapshots
            }

            self.table_client.upsert_entity(entity)

            logger.info(
                f"State updated: last_fetch={last_fetch_time}, "
                f"sent={snapshots_sent}, total={total_snapshots}"
            )

        except Exception as e:
            logger.error(f"Error updating state: {e}")
            raise

    def get_statistics(self) -> dict:
        """
        Get current statistics from state.

        Returns:
            dict: Statistics including total snapshots sent, last run, etc.
        """
        try:
            entity = self.table_client.get_entity(
                partition_key=self.PARTITION_KEY,
                row_key=self.ROW_KEY
            )

            return {
                'last_fetch_time': entity.get('last_fetch_time'),
                'last_run_timestamp': entity.get('last_run_timestamp'),
                'snapshots_sent_this_run': entity.get('snapshots_sent_this_run', 0),
                'total_snapshots_sent': entity.get('total_snapshots_sent', 0)
            }

        except ResourceNotFoundError:
            return {
                'last_fetch_time': None,
                'last_run_timestamp': None,
                'snapshots_sent_this_run': 0,
                'total_snapshots_sent': 0
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
