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
        Fetch occupancy snapshots in time range with automatic pagination

        Args:
            from_time: Start time (inclusive)
            to_time: End time (inclusive)
            page_size: Records per page (max 999)

        Returns:
            List of snapshot dictionaries
        """
        token = self._get_token()

        # Format timestamps for API
        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        to_str = to_time.strftime("%Y-%m-%dT%H:%M:%S.999Z")

        # Get config parameters
        ms_config = self.config.get('microshare', {})

        # Build base parameters (using aggregated endpoint)
        base_params = {
            "id": ms_config.get('view_id'),
            "recType": ms_config.get('rec_type'),
            "dataContext": ms_config.get('data_context'),
            "category": ms_config.get('category'),
            "metric": ms_config.get('metric'),
            "ownerOrg": ms_config.get('owner_org'),
            "loc1": ms_config.get('location'),
            "from": from_str,
            "to": to_str,
            "pageSize": min(page_size, 999)  # Enforce max
        }

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
