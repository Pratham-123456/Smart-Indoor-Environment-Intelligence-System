"""SIEIS (Smart Indoor Environmental Intelligence System) - Outdoor Weather & AQI Service.

Fetches live outdoor ambient weather and air quality conditions from:
1. WeatherAPI (primary provider when WEATHERAPI_API_KEY is configured):
   Provides actual physical weather station observations with native last_updated_epoch.
2. Open-Meteo (resilient, keyless fallback provider):
   Provides regional numerical weather prediction model estimates and air quality reanalysis.

Features:
- Configurable short-duration server-side caching (30-60s) to prevent external rate-limiting.
- Explicit concurrency deduplication so parallel requests share a single in-flight fetch.
- Strict distinction between underlying provider observation time (observed_at) and fetch time (fetched_at).
- Dynamic calculation of observation data age (age_seconds).
- Epistemic honesty: Explicit labelling of 'station_observation' vs 'numerical_model_estimate'.
- Resilient stale cache fallback with honest 'stale_cached' status on network failure.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

from config import Config

logger = logging.getLogger("sieis.outdoor")


def _classify_us_aqi(aqi: Optional[float]) -> str:
    """Classify numeric US AQI (0-500) into official EPA health categories."""
    if aqi is None:
        return "Unknown"
    val = round(aqi)
    if val <= 50:
        return "Good"
    elif val <= 100:
        return "Moderate"
    elif val <= 150:
        return "Unhealthy for Sensitive Groups"
    elif val <= 200:
        return "Unhealthy"
    elif val <= 300:
        return "Very Unhealthy"
    else:
        return "Hazardous"


def pm25_to_us_aqi(pm25: Optional[float]) -> Optional[float]:
    """Convert PM2.5 concentration in ug/m3 to US EPA AQI using official piecewise breakpoints."""
    if pm25 is None or pm25 < 0:
        return None
    c = round(float(pm25), 1)
    if c <= 9.0:
        return round(((50 - 0) / (9.0 - 0.0)) * (c - 0.0) + 0)
    elif c <= 35.4:
        return round(((100 - 51) / (35.4 - 9.1)) * (c - 9.1) + 51)
    elif c <= 55.4:
        return round(((150 - 101) / (55.4 - 35.5)) * (c - 35.5) + 101)
    elif c <= 125.4:
        return round(((200 - 151) / (125.4 - 55.5)) * (c - 55.5) + 151)
    elif c <= 225.4:
        return round(((300 - 201) / (225.4 - 125.5)) * (c - 125.5) + 201)
    else:
        return round(((500 - 301) / (325.4 - 225.5)) * (c - 225.5) + 301)


class OutdoorWeatherService:
    """Resilient client for real-time outdoor atmospheric telemetry."""

    def __init__(
        self,
        latitude: float = Config.DEFAULT_LATITUDE,
        longitude: float = Config.DEFAULT_LONGITUDE,
        location_label: str = Config.DEFAULT_LOCATION_LABEL,
        cache_ttl_seconds: int = Config.OUTDOOR_CACHE_TTL_SECONDS,
        timeout_seconds: int = Config.OUTDOOR_API_TIMEOUT_SECONDS,
        stale_threshold_seconds: int = Config.OUTDOOR_STALE_THRESHOLD_SECONDS,
        weatherapi_key: Optional[str] = None,
        provider_preference: Optional[str] = None,
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.location_label = location_label
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout_seconds = timeout_seconds
        self.stale_threshold_seconds = stale_threshold_seconds

        self.weatherapi_key = weatherapi_key if weatherapi_key is not None else Config.WEATHERAPI_API_KEY
        self.provider_preference = (provider_preference or Config.SIEIS_WEATHER_PROVIDER).lower()

        self._cache_lock = threading.Lock()
        self._fetch_lock = threading.Lock()
        self._cached_data: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0.0
        self._last_successful_refresh: Optional[str] = None
        self._last_error: Optional[str] = None

    def update_location(self, latitude: float, longitude: float, location_label: Optional[str] = None) -> None:
        """Update geographic coordinates and clear cache to trigger immediate fetch."""
        with self._cache_lock:
            self.latitude = float(latitude)
            self.longitude = float(longitude)
            if location_label:
                self.location_label = str(location_label)
            # Invalidate cache
            self._cached_data = None
            self._cache_time = 0.0
        logger.info(f"Updated outdoor coordinates to ({self.latitude}, {self.longitude}) for '{self.location_label}'")

    def get_outdoor_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Retrieve outdoor weather and AQI data with short caching, concurrency deduplication, and fallback.

        Returns structured dictionary containing accurate observation timestamps, data age, and epistemic source type.
        """
        now = time.time()

        # 1. Fast path: In-memory cache hit if not forcing refresh
        with self._cache_lock:
            if (
                not force_refresh
                and self._cached_data is not None
                and (now - self._cache_time) < self.cache_ttl_seconds
            ):
                return self._format_cache_response(now)

        # 2. Concurrency deduplication: Ensure only one thread fetches over network at a time
        if force_refresh:
            acquired = self._fetch_lock.acquire(blocking=True, timeout=float(self.timeout_seconds))
        else:
            acquired = self._fetch_lock.acquire(blocking=False)

        if not acquired:
            # Another thread is actively fetching. Return existing cache rather than creating duplicate requests.
            with self._cache_lock:
                if self._cached_data is not None:
                    return self._format_cache_response(time.time())
            # If no cache exists at all, wait for the other thread to finish
            acquired_wait = self._fetch_lock.acquire(blocking=True, timeout=float(self.timeout_seconds))
            try:
                with self._cache_lock:
                    if self._cached_data is not None:
                        return self._format_cache_response(time.time())
            finally:
                if acquired_wait and self._fetch_lock.locked():
                    self._fetch_lock.release()

        # We hold _fetch_lock, proceed to network fetch
        try:
            # Re-check cache inside lock in case another thread just completed the fetch
            with self._cache_lock:
                now = time.time()
                if (
                    not force_refresh
                    and self._cached_data is not None
                    and (now - self._cache_time) < self.cache_ttl_seconds
                ):
                    return self._format_cache_response(now)

            fetch_result, error_msg = self._fetch_live()

            with self._cache_lock:
                now = time.time()
                now_iso = datetime.now(timezone.utc).isoformat()
                if fetch_result is not None:
                    self._cached_data = fetch_result
                    self._cache_time = now
                    self._last_successful_refresh = now_iso
                    self._last_error = None

                    result = dict(fetch_result)
                    obs_epoch = result.get("observed_epoch", now)
                    age_sec = max(0, int(now - obs_epoch))
                    result["age_seconds"] = age_sec
                    result["cache_age_seconds"] = 0
                    result["fetched_at"] = now_iso
                    result["last_successful_refresh"] = now_iso

                    is_stale = age_sec > self.stale_threshold_seconds
                    result["is_stale"] = is_stale
                    result["freshness_status"] = "stale_observation" if is_stale else "live"
                    return result
                else:
                    self._last_error = error_msg
                    # Stale fallback if cache exists
                    if self._cached_data is not None:
                        result = dict(self._cached_data)
                        obs_epoch = result.get("observed_epoch", self._cache_time)
                        age_sec = max(0, int(now - obs_epoch))
                        result["age_seconds"] = age_sec
                        result["cache_age_seconds"] = max(0, int(now - self._cache_time))
                        result["last_successful_refresh"] = self._last_successful_refresh
                        result["freshness_status"] = "stale_cached"
                        result["is_stale"] = True
                        result["warning"] = f"Using stale cached data. Live fetch failed: {error_msg}"
                        return result

                    # Total failure - unavailable fallback (no fabricated data)
                    return {
                        "status": "unavailable",
                        "freshness_status": "offline",
                        "is_stale": True,
                        "latitude": self.latitude,
                        "longitude": self.longitude,
                        "location_label": self.location_label,
                        "temperature_c": None,
                        "relative_humidity_pct": None,
                        "aqi": None,
                        "aqi_scale": "us_aqi",
                        "aqi_category": "Unknown",
                        "european_aqi": None,
                        "pm25": None,
                        "pm10": None,
                        "source": "None",
                        "provider": "None",
                        "source_type": "unknown",
                        "attribution": "Atmospheric data unavailable",
                        "observed_at": None,
                        "observed_epoch": None,
                        "fetched_at": None,
                        "age_seconds": None,
                        "cache_age_seconds": None,
                        "cache_ttl_seconds": self.cache_ttl_seconds,
                        "staleness_threshold_seconds": self.stale_threshold_seconds,
                        "last_successful_refresh": None,
                        "error": error_msg,
                    }
        finally:
            if self._fetch_lock.locked():
                self._fetch_lock.release()

    def _format_cache_response(self, now: float) -> Dict[str, Any]:
        """Format a cached response with dynamically recalculated observation age and cache age."""
        result = dict(self._cached_data)  # type: ignore[arg-type]
        obs_epoch = result.get("observed_epoch", self._cache_time)
        age_sec = max(0, int(now - obs_epoch))
        result["age_seconds"] = age_sec
        result["cache_age_seconds"] = max(0, int(now - self._cache_time))
        result["cache_ttl_seconds"] = self.cache_ttl_seconds
        result["staleness_threshold_seconds"] = self.stale_threshold_seconds

        is_stale = age_sec > self.stale_threshold_seconds
        result["is_stale"] = is_stale
        result["freshness_status"] = "stale_observation" if is_stale else "cached"
        return result

    def _fetch_live(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Fetch fresh atmospheric data from preferred or available external weather API."""
        if self.latitude is None or self.longitude is None:
            return None, "Location coordinates unconfigured"

        # Determine strategy based on preferences and credentials
        use_weatherapi = False
        if self.provider_preference == "weatherapi":
            use_weatherapi = True
        elif self.provider_preference == "auto" and bool(self.weatherapi_key):
            use_weatherapi = True

        errs = []

        # 1. Attempt WeatherAPI if requested/available
        if use_weatherapi:
            if not self.weatherapi_key:
                errs.append("WeatherAPI preferred but WEATHERAPI_API_KEY environment variable is not set")
            else:
                data, err = self._fetch_weatherapi()
                if data is not None:
                    return data, None
                errs.append(f"WeatherAPI: {err}")
                logger.warning(f"WeatherAPI fetch failed ({err}). Falling back to Open-Meteo...")

        # 2. Fall back to Open-Meteo (keyless, regional model nowcasting)
        data_om, err_om = self._fetch_open_meteo()
        if data_om is not None:
            return data_om, None

        errs.append(f"Open-Meteo: {err_om}")
        return None, "; ".join(errs)

    def _fetch_weatherapi(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Fetch station observations from WeatherAPI."""
        query = f"{self.latitude},{self.longitude}"
        url = (
            f"https://api.weatherapi.com/v1/current.json?"
            f"key={urllib.parse.quote(self.weatherapi_key)}&q={urllib.parse.quote(query)}&aqi=yes"
        )
        headers = {
            "User-Agent": "SIEIS-Environmental-Intelligence/2.0 (Smart Indoor Environmental Intelligence System)"
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status != 200:
                    return None, f"HTTP {resp.status}"
                body = json.loads(resp.read().decode("utf-8"))

            current = body.get("current", {})
            location = body.get("location", {})

            temp_c = current.get("temp_c")
            humidity = current.get("humidity")
            last_updated_epoch = current.get("last_updated_epoch")
            last_updated_str = current.get("last_updated")

            if temp_c is None or humidity is None or last_updated_epoch is None:
                return None, "Incomplete payload from WeatherAPI"

            # Parse observation epoch into timezone-aware datetime
            # WeatherAPI last_updated_epoch is UTC Unix timestamp
            tz_str = location.get("tz_id", "Asia/Kolkata")
            # Calculate local observation time with offset
            obs_dt = datetime.fromtimestamp(float(last_updated_epoch), tz=timezone.utc)
            # WeatherAPI provides local string e.g. "2026-10-20 00:30"
            observed_at_iso = obs_dt.isoformat()

            # Air quality parsing
            aq_dict = current.get("air_quality", {})
            pm25 = aq_dict.get("pm2_5")
            pm10 = aq_dict.get("pm10")
            epa_index = aq_dict.get("us-epa-index")

            # Calculate standard US AQI from PM2.5 or EPA index
            calc_aqi = pm25_to_us_aqi(pm25)
            if calc_aqi is None and epa_index is not None:
                # Fallback mapping from EPA Index (1-6)
                epa_map = {1: 25, 2: 75, 3: 125, 4: 175, 5: 250, 6: 350}
                calc_aqi = float(epa_map.get(int(epa_index), 50))

            now_epoch = time.time()
            age_sec = max(0, int(now_epoch - float(last_updated_epoch)))

            loc_name = f"{location.get('name', '')}, {location.get('region', '')}, {location.get('country', '')}".strip(", ")
            if not loc_name or loc_name == ",":
                loc_name = self.location_label

            payload = {
                "status": "ok",
                "latitude": float(location.get("lat", self.latitude)),
                "longitude": float(location.get("lon", self.longitude)),
                "location_label": self.location_label or loc_name,
                "temperature_c": float(temp_c),
                "relative_humidity_pct": float(humidity),
                "aqi": calc_aqi,
                "aqi_scale": "us_aqi",
                "aqi_category": _classify_us_aqi(calc_aqi),
                "european_aqi": None,
                "pm25": float(pm25) if pm25 is not None else None,
                "pm10": float(pm10) if pm10 is not None else None,
                "source": "WeatherAPI",
                "provider": "WeatherAPI",
                "source_type": "station_observation",  # Physical surface weather station observation
                "attribution": "Weather data by WeatherAPI.com",
                "observed_at": last_updated_str or observed_at_iso,
                "observed_epoch": float(last_updated_epoch),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "age_seconds": age_sec,
                "cache_age_seconds": 0,
                "cache_ttl_seconds": self.cache_ttl_seconds,
                "staleness_threshold_seconds": self.stale_threshold_seconds,
                "is_stale": age_sec > self.stale_threshold_seconds,
            }
            return payload, None

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            return None, f"HTTP Error {e.code}: {err_body or e.reason}"
        except Exception as e:
            return None, str(e)

    def _fetch_open_meteo(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Fetch weather and air-quality numerical model reanalysis from Open-Meteo."""
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={self.latitude}&longitude={self.longitude}&"
            f"current=temperature_2m,relative_humidity_2m&timezone=Asia%2FKolkata"
        )
        air_url = (
            f"https://air-quality-api.open-meteo.com/v1/air-quality?"
            f"latitude={self.latitude}&longitude={self.longitude}&"
            f"current=us_aqi,european_aqi,pm2_5,pm10&timezone=Asia%2FKolkata"
        )

        headers = {
            "User-Agent": "SIEIS-Environmental-Intelligence/2.0 (Open-Meteo Client)"
        }

        temp_c: Optional[float] = None
        rh_pct: Optional[float] = None
        observed_at_str: Optional[str] = None
        observed_epoch: Optional[float] = None
        us_aqi: Optional[float] = None
        eur_aqi: Optional[float] = None
        pm25: Optional[float] = None
        pm10: Optional[float] = None
        errs = []

        # 1. Weather forecast endpoint
        for attempt in range(2):
            try:
                req_weather = urllib.request.Request(weather_url, headers=headers)
                with urllib.request.urlopen(req_weather, timeout=self.timeout_seconds) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        current = data.get("current", {})
                        temp_c = current.get("temperature_2m")
                        rh_pct = current.get("relative_humidity_2m")
                        time_raw = current.get("time")  # e.g. "2026-10-20T00:30"
                        offset_sec = data.get("utc_offset_seconds", 19800)

                        if time_raw:
                            try:
                                tz_local = timezone(timedelta(seconds=offset_sec))
                                obs_dt = datetime.fromisoformat(time_raw).replace(tzinfo=tz_local)
                                observed_at_str = obs_dt.isoformat()
                                observed_epoch = obs_dt.timestamp()
                            except Exception:
                                observed_at_str = time_raw
                                observed_epoch = time.time()
                        break
            except Exception as e:
                if attempt == 0:
                    time.sleep(0.3)
                else:
                    errs.append(f"Weather: {e}")

        # 2. Air Quality endpoint
        for attempt in range(2):
            try:
                req_air = urllib.request.Request(air_url, headers=headers)
                with urllib.request.urlopen(req_air, timeout=self.timeout_seconds) as resp:
                    if resp.status == 200:
                        data_aq = json.loads(resp.read().decode("utf-8"))
                        curr_aq = data_aq.get("current", {})
                        us_aqi = curr_aq.get("us_aqi")
                        eur_aqi = curr_aq.get("european_aqi")
                        pm25 = curr_aq.get("pm2_5")
                        pm10 = curr_aq.get("pm10")
                        if not observed_at_str:
                            time_aq = curr_aq.get("time")
                            offset_sec = data_aq.get("utc_offset_seconds", 19800)
                            if time_aq:
                                try:
                                    tz_local = timezone(timedelta(seconds=offset_sec))
                                    obs_dt = datetime.fromisoformat(time_aq).replace(tzinfo=tz_local)
                                    observed_at_str = obs_dt.isoformat()
                                    observed_epoch = obs_dt.timestamp()
                                except Exception:
                                    observed_at_str = time_aq
                                    observed_epoch = time.time()
                        break
            except Exception as e:
                if attempt == 0:
                    time.sleep(0.3)
                else:
                    errs.append(f"Air Quality: {e}")

        if temp_c is None and us_aqi is None:
            return None, "; ".join(errs) or "Both outdoor endpoints failed"

        now_epoch = time.time()
        final_obs_epoch = observed_epoch if observed_epoch is not None else now_epoch
        age_sec = max(0, int(now_epoch - final_obs_epoch))

        payload = {
            "status": "ok",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_label": self.location_label,
            "temperature_c": float(temp_c) if temp_c is not None else None,
            "relative_humidity_pct": float(rh_pct) if rh_pct is not None else None,
            "aqi": float(us_aqi) if us_aqi is not None else None,
            "aqi_scale": "us_aqi",
            "aqi_category": _classify_us_aqi(us_aqi),
            "european_aqi": float(eur_aqi) if eur_aqi is not None else None,
            "pm25": float(pm25) if pm25 is not None else None,
            "pm10": float(pm10) if pm10 is not None else None,
            "source": "Open-Meteo",
            "provider": "Open-Meteo",
            "source_type": "numerical_model_estimate",  # Distinct from physical station observation
            "attribution": "Weather & Air Quality model by Open-Meteo.com",
            "observed_at": observed_at_str or datetime.now(timezone.utc).isoformat(),
            "observed_epoch": final_obs_epoch,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "age_seconds": age_sec,
            "cache_age_seconds": 0,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "staleness_threshold_seconds": self.stale_threshold_seconds,
            "is_stale": age_sec > self.stale_threshold_seconds,
        }
        return payload, None


# Global singleton instance
_outdoor_service_instance: Optional[OutdoorWeatherService] = None
_instance_lock = threading.Lock()


def get_outdoor_service() -> OutdoorWeatherService:
    global _outdoor_service_instance
    with _instance_lock:
        if _outdoor_service_instance is None:
            _outdoor_service_instance = OutdoorWeatherService()
        return _outdoor_service_instance
