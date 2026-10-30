"""SIEIS (Smart Indoor Environmental Intelligence System) - Backend Configuration.

Handles environment variables and defaults for server, database,
sensor bounds, intelligence thresholds, and alerting rules.
"""

from __future__ import annotations

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_PATH = DATA_DIR / "sieis.db"


def _load_env_file() -> None:
    """Load key-value pairs from .env into os.environ if present."""
    for candidate in [BASE_DIR.parent / ".env", BASE_DIR / ".env"]:
        if candidate.exists():
            try:
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass


_load_env_file()


class Config:
    """Base application configuration."""

    # Server Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "sieis-insecure-dev-key-2026")
    HOST = os.getenv("SIEIS_HOST", "0.0.0.0")
    PORT = int(os.getenv("SIEIS_PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")

    # Database
    DATABASE_PATH = Path(os.getenv("SIEIS_DB_PATH", str(DEFAULT_DB_PATH)))

    # Device & Freshness Settings
    EXPECTED_DEVICE_ID = os.getenv("SIEIS_DEVICE_ID", "esp32-sieis-01")
    STALE_THRESHOLD_SECONDS = int(os.getenv("SIEIS_STALE_SECONDS", "30"))
    MAX_READINGS_QUERY_LIMIT = int(os.getenv("SIEIS_MAX_QUERY_LIMIT", "500"))
    DEFAULT_READINGS_LIMIT = int(os.getenv("SIEIS_DEFAULT_QUERY_LIMIT", "100"))

    # Plausible Physical Sensor Validation Bounds
    # DHT22
    TEMP_MIN_C = -20.0
    TEMP_MAX_C = 70.0
    HUMIDITY_MIN = 0.0
    HUMIDITY_MAX = 100.0

    # LDR (12-bit ADC: 0 - 4095)
    LDR_MIN_RAW = 0
    LDR_MAX_RAW = 4095
    LDR_DARK_THRESHOLD = 250
    LDR_DIM_THRESHOLD = 1700  # <250 dark, 250..1699 dim, >=1700 bright

    # MQ-135 Gas Response (Millivolts)
    MQ135_PIN_MV_MIN = 0
    MQ135_PIN_MV_MAX = 3300
    MQ135_WARMUP_SECONDS = 300  # 5 minutes warm-up after boot
    MQ135_BURNIN_HOURS = 24  # 24-48 hours initial burn-in requirement

    # Sound Sensor (LM393 analog peak-to-peak swing & digital output)
    SOUND_SWING_MIN = 0
    SOUND_SWING_MAX = 4095

    # Comfort Index Thresholds (ASHRAE 55 / CIBSE aligned residential/lab guidelines)
    COMFORT_TEMP_OPTIMAL_MIN = 20.0
    COMFORT_TEMP_OPTIMAL_MAX = 25.0
    COMFORT_TEMP_ACCEPTABLE_MIN = 18.0
    COMFORT_TEMP_ACCEPTABLE_MAX = 27.0

    COMFORT_HUM_OPTIMAL_MIN = 40.0
    COMFORT_HUM_OPTIMAL_MAX = 60.0
    COMFORT_HUM_ACCEPTABLE_MIN = 30.0
    COMFORT_HUM_ACCEPTABLE_MAX = 70.0

    # Intelligence & Baseline Settings
    MQ135_BASELINE_WINDOW_SIZE = int(os.getenv("SIEIS_BASELINE_WINDOW", "30"))  # Samples
    MQ135_ELEVATION_RATIO_WARN = 1.25  # 25% above rolling baseline
    MQ135_ELEVATION_RATIO_ALERT = 1.50  # 50% above rolling baseline

    ALERT_COOLDOWN_SECONDS = 60  # Cooldown between duplicate alerts

    # Authoritative Room Comfort Index (RCI) Specification Thresholds
    RCI_WEIGHT_TEMP = 0.30
    RCI_WEIGHT_HUM = 0.25
    RCI_WEIGHT_GAS = 0.25
    RCI_WEIGHT_LIGHT = 0.10
    RCI_WEIGHT_SOUND = 0.10

    RCI_TEMP_OPT_MIN = 21.0
    RCI_TEMP_OPT_MAX = 24.0
    RCI_TEMP_MIN = 14.0
    RCI_TEMP_MAX = 33.0

    RCI_HUM_OPT_MIN = 40.0
    RCI_HUM_OPT_MAX = 60.0
    RCI_HUM_MIN = 15.0
    RCI_HUM_MAX = 85.0

    RCI_GAS_CLEAN_RATIO = 1.05
    RCI_GAS_MAX_RATIO = 2.50

    RCI_STALE_THRESHOLD_SECONDS = 120
    RCI_MIN_COVERAGE_PCT = 50.0

    # Outdoor Weather & AQI Service Settings
    WEATHERAPI_API_KEY = os.getenv("WEATHERAPI_API_KEY", "").strip()
    SIEIS_WEATHER_PROVIDER = os.getenv("SIEIS_WEATHER_PROVIDER", "auto").strip().lower()  # "auto", "weatherapi", "open-meteo"
    DEFAULT_LATITUDE = float(os.getenv("SIEIS_LATITUDE", "12.9165"))
    DEFAULT_LONGITUDE = float(os.getenv("SIEIS_LONGITUDE", "79.1325"))
    DEFAULT_LOCATION_LABEL = os.getenv("SIEIS_LOCATION_LABEL", "Vellore, Tamil Nadu, India")
    DEFAULT_TIMEZONE = os.getenv("SIEIS_TIMEZONE", "Asia/Kolkata")
    OUTDOOR_API_TIMEOUT_SECONDS = int(os.getenv("SIEIS_OUTDOOR_TIMEOUT", "6"))
    OUTDOOR_CACHE_TTL_SECONDS = int(os.getenv("SIEIS_OUTDOOR_TTL", "45"))  # 45 seconds for fresh internet data
    OUTDOOR_STALE_THRESHOLD_SECONDS = int(os.getenv("SIEIS_OUTDOOR_STALE_SECONDS", "7200"))  # 2 hours observation age threshold
    OUTDOOR_AQI_FAVOURABLE_MAX = 75.0
    OUTDOOR_AQI_UNFAVOURABLE_MIN = 100.0

    # Experimental Estimator Bounds
    PM25_ESTIMATE_MIN = 2.0
    PM25_ESTIMATE_MAX = 500.0
    CO2_ESTIMATE_MIN = 400.0
    CO2_ESTIMATE_MAX = 5000.0
    CO2_NOMINAL_ATMOSPHERIC_BASELINE = 420.0


class TestConfig(Config):
    """Configuration for automated test execution."""

    TESTING = True
    DEBUG = False
    DATABASE_PATH = Path(":memory:")
    ALERT_COOLDOWN_SECONDS = 0
    OUTDOOR_CACHE_TTL_SECONDS = 60
    DEFAULT_LOCATION_LABEL = "Test Lab"
