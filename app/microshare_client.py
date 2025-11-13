"""
Microshare API Client - Simplified
Fetches occupancy snapshots from Microshare API without database dependencies
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class MicroshareAPIError(Exception):
    """Base exception for Microshare API errors"""
    pass


class MicroshareAuthError(MicroshareAPIError):
    """Authentication related errors"""
    pass


class MicroshareClient:
    """
    Simplified client for Microshare API
    - OAuth2 token management with file caching (no database)
    - Retry logic
    - Snapshot fetching
    """
    
    WEB_LOGIN_URL = "https://app.microshare.io/login"
    API_BASE_URL = "https://api.microshare.io/share"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Microshare client
        
        Args:
            config: Configuration dictionary with microshare settings
        """
        self.config = config
        ms_config = config.get('microshare', {})
        
        self.username = ms_config.get('username')
        self.password = ms_config.get('password')
        self.api_key = ms_config.get('api_key')
        
        if not all([self.username, self.password, self.api_key]):
            raise ValueError("Microshare credentials missing in config")
        
        # Token caching in file
        self.token_file = Path("/var/lib/microshare-forwarder/token_cache.json")
        self._token = None
        self._token_expires_at = None
        
        # HTTP session with retry logic
        self.session = self._create_session()
        
        logger.info("MicroshareClient initialized")
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def _load_token_from_file(self) -> bool:
        """Load cached token from file"""
        try:
            if self.token_file.exists():
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self._token = data.get('access_token')
                    expires_at_str = data.get('expires_at')
                    
                    if expires_at_str:
                        self._token_expires_at = datetime.fromisoformat(expires_at_str)
                        
                        # Check if token is still valid (with 5 min buffer)
                        if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                            logger.info("Loaded valid token from cache")
                            return True
        except Exception as e:
            logger.warning(f"Error loading token from file: {e}")
        
        return False
    
    def _save_token_to_file(self):
        """Save token to file"""
        try:
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'access_token': self._token,
                'expires_at': self._token_expires_at.isoformat() if self._token_expires_at else None
            }
            
            with open(self.token_file, 'w') as f:
                json.dump(data, f)
            
            # Secure the file
            os.chmod(self.token_file, 0o600)
            
            logger.debug("Token saved to file")
        except Exception as e:
            logger.warning(f"Error saving token to file: {e}")
    
    def _get_token(self) -> str:
        """Get valid OAuth token (from cache or new via web login)"""
        # Try to load from file first
        if self._load_token_from_file():
            return self._token

        # Request new token via web app login
        logger.info("Fetching token via web app login")

        payload = {
            "csrfToken": "customer-occupancy-service",
            "username": self.username,
            "password": self.password
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "CUSTOMER-Occupancy-Service/1.0"
        }

        try:
            response = self.session.post(
                self.WEB_LOGIN_URL,
                data=payload,
                headers=headers,
                allow_redirects=False,
                timeout=30
            )

            # Successful login returns 303 redirect with PLAY_SESSION cookie
            if response.status_code != 303:
                logger.error(f"Login failed with status {response.status_code}")
                raise MicroshareAuthError(f"Login failed: HTTP {response.status_code}")

            # Extract JWT from cookie
            jwt_token = response.cookies.get('PLAY_SESSION')
            if not jwt_token:
                raise MicroshareAuthError("No PLAY_SESSION cookie in response")

            # Decode JWT to extract access token
            import base64

            parts = jwt_token.split('.')
            if len(parts) != 3:
                raise MicroshareAuthError("Invalid JWT format")

            # Decode payload (second part)
            payload_b64 = parts[1]
            # Add padding if needed
            padding = len(payload_b64) % 4
            if padding:
                payload_b64 += '=' * (4 - padding)

            payload_data = json.loads(base64.urlsafe_b64decode(payload_b64))

            # Extract access token from JWT payload
            token_data = payload_data.get('data', {})
            access_token = token_data.get('access_token')

            if not access_token:
                raise MicroshareAuthError("No access_token in JWT payload")

            # Calculate expiration (default 24 hours if not in JWT)
            exp_timestamp = payload_data.get('exp', 0)
            if exp_timestamp:
                expires_in = int(exp_timestamp - datetime.utcnow().timestamp())
            else:
                expires_in = 86400  # 24 hours

            self._token = access_token
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            # Save to file
            self._save_token_to_file()

            logger.info(f"New token obtained, expires at {self._token_expires_at}")
            return self._token

        except requests.exceptions.RequestException as e:
            logger.error(f"Web login failed: {e}")
            raise MicroshareAuthError(f"Failed to get token via web login: {e}")
        except Exception as e:
            logger.error(f"Token extraction failed: {e}")
            raise MicroshareAuthError(f"Failed to extract token from JWT: {e}")
    
    def get_snapshots_in_range(
        self,
        from_time: datetime,
        to_time: datetime,
        page_size: int = 999
    ) -> List[Dict[str, Any]]:
        """
        [DEPRECATED] Fetch occupancy snapshots in time range with automatic pagination

        DEPRECATED: This method has limited coverage and doesn't support identity filtering.
        Use get_snapshot_full_coverage() or get_people_counter_full_coverage() instead.

        Args:
            from_time: Start time (inclusive)
            to_time: End time (inclusive)
            page_size: Records per page (max 999)

        Returns:
            List of snapshot dictionaries
        """
        logger.warning(
            "get_snapshots_in_range() is deprecated. "
            "Use get_snapshot_full_coverage() or get_people_counter_full_coverage() instead."
        )
        token = self._get_token()

        # Format timestamps for API
        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        to_str = to_time.strftime("%Y-%m-%dT%H:%M:%S.999Z")

        # Get config parameters
        ms_config = self.config.get('microshare', {})
        rec_type = ms_config.get('rec_type')

        # Build base parameters - common for all recTypes
        base_params = {
            "id": ms_config.get('view_id'),
            "recType": rec_type,
            "from": from_str,
            "to": to_str,
            "pageSize": min(page_size, 999)  # Enforce max
        }

        # Add recType-specific parameters
        if 'peoplecounter' in rec_type:
            # People counter specific parameters (from MICROSHARE_PEOPLE_COUNTER_QUERY_GUIDE.md)
            # Note: field4/5/6 are required placeholders to avoid 503 errors
            base_params.update({
                "dataContext": ms_config.get('data_context', '["people"]'),
                "loc1": ms_config.get('location'),
                "field1": "daily_total",
                "field2": "meta",
                "field3": "change",
                "field4": "field4",  # Required placeholder
                "field5": "field5",  # Required placeholder
                "field6": "field6"   # Required placeholder
            })
            logger.info("Using people counter parameter set")
        else:
            # Hourly snapshot parameters (default)
            base_params.update({
                "dataContext": ms_config.get('data_context'),
                "category": ms_config.get('category'),
                "metric": ms_config.get('metric'),
                "ownerOrg": ms_config.get('owner_org'),
                "loc1": ms_config.get('location')
            })
            logger.info("Using hourly snapshot parameter set")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Use aggregated endpoint for hourly snapshots
        url = "https://api.microshare.io/share/io.microshare.fm.master.agg/"

        logger.info(f"Fetching snapshots from {from_str} to {to_str}")

        all_snapshots = []
        page = 1

        try:
            while True:
                # Add page number to params
                params = {**base_params, "page": page}

                logger.debug(f"Requesting page {page} (pageSize={page_size})")

                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=60
                )

                response.raise_for_status()
                data = response.json()

                # Extract snapshots and metadata
                snapshots = data.get('objs', [])
                meta = data.get('meta', {})

                total_pages = meta.get('totalPages', 1)
                current_page = meta.get('currentPage', page)
                total_count = meta.get('totalCount', 0)

                if snapshots:
                    all_snapshots.extend(snapshots)
                    logger.info(
                        f"Page {current_page}/{total_pages}: "
                        f"{len(snapshots)} records (total: {len(all_snapshots)}/{total_count})"
                    )
                else:
                    logger.debug(f"No records on page {page}")
                    break

                # Check if we got all pages
                if current_page >= total_pages:
                    logger.info(f"Retrieved all {total_pages} page(s)")
                    break

                # Alert if multiple pages (indicates high volume)
                if page == 1 and total_pages > 1:
                    logger.warning(
                        f"⚠️  Data volume requires {total_pages} pages "
                        f"({total_count} total records) - consider polling more frequently"
                    )

                page += 1

            logger.info(f"Retrieved total of {len(all_snapshots)} snapshots")

            # Transform to consistent format
            transformed = []
            for snap in all_snapshots:
                transformed.append(snap)

            return transformed

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed on page {page}: {e}")
            raise MicroshareAPIError(f"Failed to fetch snapshots: {e}")

    def get_people_counter_full_coverage(
        self,
        from_time: datetime,
        to_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get full 24-hour people counter data with identity filtering.

        Strategy:
        1. Query first view (fast, limited coverage) to discover locations
        2. Filter by identity (owner.org)
        3. Query dashboard view per location for full 24h coverage
        4. Flatten line[] arrays into individual events

        Args:
            from_time: Start time (inclusive)
            to_time: End time (inclusive)

        Returns:
            List of flattened people counter events with full 24h coverage
        """
        token = self._get_token()
        ms_config = self.config.get('microshare', {})
        identity_filter = ms_config.get('identity', '')

        logger.info(f"Getting full people counter coverage with identity filter: {identity_filter}")

        # Step 1: Query first view to discover locations
        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        to_str = to_time.strftime("%Y-%m-%dT%H:%M:%S.999Z")

        # Get people counter config
        pc_config = ms_config.get('people_counter', {})

        discovery_params = {
            "id": pc_config.get('discovery_view_id'),
            "recType": pc_config.get('rec_type', 'io.microshare.peoplecounter.unpacked.event.agg'),
            "from": from_str,
            "to": to_str,
            "pageSize": 999,
            "dataContext": pc_config.get('data_context', '["people"]'),
            "field1": "daily_total",
            "field2": "meta",
            "field3": "change",
            "field4": "field4",
            "field5": "field5",
            "field6": "field6"
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            response = self.session.get(
                "https://api.microshare.io/share/io.microshare.fm.master.agg/",
                params=discovery_params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            discovery_records = response.json().get('objs', [])
            logger.info(f"Discovery query returned {len(discovery_records)} records")

            # Step 2: Filter by identity and extract unique locations
            locations_for_identity = set()
            for record in discovery_records:
                try:
                    owner_org = record['data']['owner']['org']

                    # Check if identity filter matches (case-insensitive substring match)
                    if identity_filter and identity_filter.upper() not in owner_org.upper():
                        continue

                    # Extract location from meta.device
                    location = record['data']['data']['meta']['device'][0]
                    locations_for_identity.add(location)

                except (KeyError, TypeError, IndexError):
                    continue

            logger.info(f"Found {len(locations_for_identity)} unique locations for identity '{identity_filter}': {sorted(locations_for_identity)}")

            # Step 3: Query dashboard view for each location
            all_events = []

            for location in sorted(locations_for_identity):
                logger.info(f"Querying dashboard view for location: {location}")

                dashboard_params = {
                    "id": pc_config.get('dashboard_view_id'),
                    "recType": pc_config.get('rec_type', 'io.microshare.peoplecounter.unpacked.event.agg'),
                    "from": from_str,
                    "to": to_str,
                    "dataContext": pc_config.get('data_context', '["people"]'),
                    "field1": "daily_total",
                    "field2": "meta",
                    "field3": "change",
                    "field4": "field4",
                    "field5": "field5",
                    "field6": "field6",
                    "loc1": location
                }

                dashboard_response = self.session.get(
                    "https://api.microshare.io/share/io.microshare.fm.master.agg/",
                    params=dashboard_params,
                    headers=headers,
                    timeout=30
                )
                dashboard_response.raise_for_status()

                dashboard_records = dashboard_response.json().get('objs', [])

                # Step 4: Flatten line[] arrays
                for dr in dashboard_records:
                    line_entries = dr.get('data', {}).get('line', [])

                    # Each entry in line[] is a time-series event
                    for entry in line_entries:
                        # Add metadata from parent record
                        entry['_location_tags'] = dr.get('data', {}).get('_id', {}).get('tags', [])
                        all_events.append(entry)

                logger.info(f"  → Added {len(line_entries) if dashboard_records else 0} events from {location}")

            logger.info(f"Total events retrieved: {len(all_events)}")
            return all_events

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get full people counter coverage: {e}")
            raise MicroshareAPIError(f"Failed to get people counter data: {e}")

    def get_snapshot_full_coverage(
        self,
        from_time: datetime,
        to_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get full 24-hour snapshot data with identity filtering.

        Strategy:
        1. Query people counter discovery view to find locations for identity
        2. Map location names (removes configured prefix from people counter location names)
        3. Query snapshot dashboard view per mapped location for full 24h coverage
        4. Flatten line[] arrays into individual snapshot entries

        Args:
            from_time: Start time (inclusive)
            to_time: End time (inclusive)

        Returns:
            List of flattened snapshot entries with full 24h coverage
        """
        token = self._get_token()
        ms_config = self.config.get('microshare', {})
        identity_filter = ms_config.get('identity', '')

        logger.info(f"Getting full snapshot coverage with identity filter: {identity_filter}")

        # Step 1: Query people counter discovery view to find locations for identity
        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        to_str = to_time.strftime("%Y-%m-%dT%H:%M:%S.999Z")

        # Get people counter config for discovery (snapshot dashboard lacks owner.org)
        pc_config = ms_config.get('people_counter', {})

        discovery_params = {
            "id": pc_config.get('discovery_view_id'),
            "recType": pc_config.get('rec_type', 'io.microshare.peoplecounter.unpacked.event.agg'),
            "from": from_str,
            "to": to_str,
            "pageSize": 999,
            "dataContext": pc_config.get('data_context', '["people"]'),
            "field1": "daily_total",
            "field2": "meta",
            "field3": "change",
            "field4": "field4",
            "field5": "field5",
            "field6": "field6"
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            response = self.session.get(
                "https://api.microshare.io/share/io.microshare.fm.master.agg/",
                params=discovery_params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            discovery_records = response.json().get('objs', [])
            logger.info(f"Discovery query returned {len(discovery_records)} records")

            # Step 2: Filter by identity and extract unique locations
            pc_locations = set()
            for record in discovery_records:
                try:
                    owner_org = record['data']['owner']['org']

                    # Check if identity filter matches (case-insensitive substring match)
                    if identity_filter and identity_filter.upper() not in owner_org.upper():
                        continue

                    # Extract location from meta.device
                    location = record['data']['data']['meta']['device'][0]
                    pc_locations.add(location)

                except (KeyError, TypeError, IndexError):
                    continue

            logger.info(f"Found {len(pc_locations)} unique locations for identity '{identity_filter}': {sorted(pc_locations)}")

            # Step 3: Map location names for snapshot queries
            # Example: "PREFIX Location" → "Location"
            location_prefix = ms_config.get('location_prefix', '')
            snapshot_locations = []
            for pc_loc in sorted(pc_locations):
                # Remove configured prefix (e.g., "COMPANY " → "")
                if location_prefix:
                    snapshot_loc = pc_loc.replace(f"{location_prefix} ", "")
                else:
                    snapshot_loc = pc_loc
                snapshot_locations.append((pc_loc, snapshot_loc))

            logger.info(f"Location mapping (PC → Snapshot): {snapshot_locations}")

            # Step 4: Query snapshot dashboard for each mapped location
            all_snapshots = []

            # Get snapshot config
            snapshot_config = ms_config.get('snapshot', {})

            for pc_loc, snapshot_loc in snapshot_locations:
                logger.info(f"Querying snapshot dashboard for location: {snapshot_loc} (from PC: {pc_loc})")

                snapshot_params = {
                    "id": snapshot_config.get('dashboard_view_id'),
                    "recType": snapshot_config.get('rec_type', 'io.microshare.lake.snapshot.hourly'),
                    "from": from_str,
                    "to": to_str,
                    "dataContext": snapshot_config.get('data_context', '[]'),
                    "field1": "current",
                    "field2": "field2",
                    "field3": "field3",
                    "field4": "field4",
                    "field5": "field5",
                    "field6": "field6",
                    "category": snapshot_config.get('category', 'space'),
                    "metric": snapshot_config.get('metric', 'occupancy'),
                    "ownerOrg": snapshot_config.get('owner_org', '"[a-zA-Z]"'),
                    "loc1": snapshot_loc
                }

                snapshot_response = self.session.get(
                    "https://api.microshare.io/share/io.microshare.fm.master.agg/",
                    params=snapshot_params,
                    headers=headers,
                    timeout=30
                )
                snapshot_response.raise_for_status()

                snapshot_records = snapshot_response.json().get('objs', [])

                # Step 5: Flatten line[] arrays
                for sr in snapshot_records:
                    line_entries = sr.get('data', {}).get('line', [])

                    # Each entry in line[] is an hourly snapshot
                    for entry in line_entries:
                        # Add metadata from parent record
                        entry['_location_tags'] = sr.get('data', {}).get('_id', {}).get('tags', [])
                        entry['_location'] = snapshot_loc
                        entry['_pc_location'] = pc_loc  # Original people counter location name
                        all_snapshots.append(entry)

                logger.info(f"  → Added {len(line_entries) if snapshot_records else 0} snapshots from {snapshot_loc}")

            logger.info(f"Total snapshots retrieved: {len(all_snapshots)}")
            return all_snapshots

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get full snapshot coverage: {e}")
            raise MicroshareAPIError(f"Failed to get snapshot data: {e}")

    def _transform_snapshot(self, raw_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Transform raw Microshare snapshot to standardized format"""
        data = raw_snapshot.get('data', {})
        obj_id = raw_snapshot.get('id')
        create_date = raw_snapshot.get('createDate')
        
        # Extract location hierarchy
        meta = data.get('meta', {})
        device_cluster_id = meta.get('device_cluster_id', '')
        parts = device_cluster_id.split(' > ') if device_cluster_id else []
        
        location = {
            'building': parts[0] if len(parts) > 0 else '',
            'floor': parts[1] if len(parts) > 1 else '',
            'room': parts[2] if len(parts) > 2 else '',
            'full_path': device_cluster_id
        }
        
        # Extract occupancy data
        minutes_occupied = data.get('minutes_occupied', 0)
        minutes_free = data.get('minutes_free', 0)
        
        return {
            'snapshot_id': hash(obj_id) if obj_id else None,  # Generate ID from Microshare ID
            'timestamp': create_date,
            'device_id': meta.get('device', ''),
            'location': location,
            'occupancy': {
                'minutes_occupied': minutes_occupied,
                'minutes_free': minutes_free,
                'utilization_percent': round((minutes_occupied / 60.0) * 100, 2) if minutes_occupied else 0
            },
            'raw_data': data  # Keep raw data for reference
        }
    
    def test_connection(self) -> bool:
        """Test Microshare API connection"""
        try:
            token = self._get_token()
            logger.info("✓ Microshare API connection test successful")
            return True
        except Exception as e:
            logger.error(f"✗ Microshare API connection test failed: {e}")
            return False
