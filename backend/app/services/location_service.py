"""
Jan-Seva AI — Location Service
Resolves user IP address to Indian state using free ip-api.com (no key needed).
Results are cached in-memory (TTL 30 min) to avoid repeated calls.
"""

import time
import asyncio
import httpx
from app.utils.logger import logger


# Full map: ip-api.com region names → Indian state codes & display names
REGION_TO_STATE = {
    # South
    "Tamil Nadu": {"code": "TN", "name": "Tamil Nadu"},
    "Kerala": {"code": "KL", "name": "Kerala"},
    "Karnataka": {"code": "KA", "name": "Karnataka"},
    "Andhra Pradesh": {"code": "AP", "name": "Andhra Pradesh"},
    "Telangana": {"code": "TS", "name": "Telangana"},
    # West
    "Maharashtra": {"code": "MH", "name": "Maharashtra"},
    "Goa": {"code": "GA", "name": "Goa"},
    "Gujarat": {"code": "GJ", "name": "Gujarat"},
    "Rajasthan": {"code": "RJ", "name": "Rajasthan"},
    # North
    "Delhi": {"code": "DL", "name": "Delhi"},
    "Uttar Pradesh": {"code": "UP", "name": "Uttar Pradesh"},
    "Haryana": {"code": "HR", "name": "Haryana"},
    "Punjab": {"code": "PB", "name": "Punjab"},
    "Himachal Pradesh": {"code": "HP", "name": "Himachal Pradesh"},
    "Uttarakhand": {"code": "UK", "name": "Uttarakhand"},
    "Jammu and Kashmir": {"code": "JK", "name": "Jammu & Kashmir"},
    "Ladakh": {"code": "LA", "name": "Ladakh"},
    # East
    "West Bengal": {"code": "WB", "name": "West Bengal"},
    "Bihar": {"code": "BR", "name": "Bihar"},
    "Jharkhand": {"code": "JH", "name": "Jharkhand"},
    "Odisha": {"code": "OD", "name": "Odisha"},
    # Northeast
    "Assam": {"code": "AS", "name": "Assam"},
    "Meghalaya": {"code": "ML", "name": "Meghalaya"},
    "Manipur": {"code": "MN", "name": "Manipur"},
    "Nagaland": {"code": "NL", "name": "Nagaland"},
    "Arunachal Pradesh": {"code": "AR", "name": "Arunachal Pradesh"},
    "Mizoram": {"code": "MZ", "name": "Mizoram"},
    "Tripura": {"code": "TR", "name": "Tripura"},
    "Sikkim": {"code": "SK", "name": "Sikkim"},
    # Central
    "Madhya Pradesh": {"code": "MP", "name": "Madhya Pradesh"},
    "Chhattisgarh": {"code": "CG", "name": "Chhattisgarh"},
    # UTs
    "Chandigarh": {"code": "CH", "name": "Chandigarh"},
    "Puducherry": {"code": "PY", "name": "Puducherry"},
    "Pondicherry": {"code": "PY", "name": "Puducherry"},
    "Andaman and Nicobar Islands": {"code": "AN", "name": "Andaman & Nicobar"},
    "Lakshadweep": {"code": "LD", "name": "Lakshadweep"},
    "Dadra and Nagar Haveli": {"code": "DN", "name": "Dadra & Nagar Haveli"},
    "Daman and Diu": {"code": "DD", "name": "Daman & Diu"},
}

# Private IPs and local development IPs
_PRIVATE_IPS = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}

# Cache: {ip: (state_info, expires_at)}
_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 30 * 60  # 30 minutes


class LocationService:
    """
    Resolves IP addresses to Indian states.
    Uses ip-api.com (free, no key needed, 45 req/min limit).
    Falls back gracefully if the lookup fails.
    """

    IP_API_URL = "http://ip-api.com/json/{ip}?fields=status,regionName,country"

    async def get_state_from_ip(self, ip: str) -> dict | None:
        """
        Returns: {"code": "TN", "name": "Tamil Nadu"} or None if not resolvable.
        Checks cache first. Only resolves Indian IPs.
        """
        if not ip or ip in _PRIVATE_IPS:
            logger.debug(f"📍 Location: private/local IP '{ip}' — skipping lookup")
            return None

        # Check cache
        if ip in _cache:
            info, expires = _cache[ip]
            if time.monotonic() < expires:
                logger.debug(f"📍 Location: cache hit for {ip} → {info}")
                return info

        # Make request
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.IP_API_URL.format(ip=ip))
                data = response.json()

            if data.get("status") != "success":
                logger.debug(f"📍 Location: ip-api returned non-success for {ip}")
                return None

            if data.get("country") != "India":
                logger.debug(f"📍 Location: IP {ip} is not from India ({data.get('country')})")
                return None

            region = data.get("regionName", "")
            state_info = REGION_TO_STATE.get(region)

            if state_info:
                logger.info(f"📍 Location: {ip} → {region} → {state_info['name']}")
                _cache[ip] = (state_info, time.monotonic() + _CACHE_TTL)
                return state_info
            else:
                logger.debug(f"📍 Location: unknown region '{region}' for IP {ip}")
                return None

        except Exception as e:
            logger.warning(f"📍 Location: lookup failed for {ip}: {e}")
            return None


# Singleton
_location_service: LocationService | None = None


def get_location_service() -> LocationService:
    global _location_service
    if _location_service is None:
        _location_service = LocationService()
    return _location_service
