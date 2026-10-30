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


class TestConfig(Config):
    """Configuration for automated test execution."""

    TESTING = True
    DEBUG = False
    DATABASE_PATH = Path(":memory:")
    ALERT_COOLDOWN_SECONDS = 0
