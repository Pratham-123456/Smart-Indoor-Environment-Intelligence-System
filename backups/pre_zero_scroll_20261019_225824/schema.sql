-- SIEIS Database Schema (SQLite)
-- Supports persistent time-series sensor observations, scores, alerts, and baselines.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    firmware_version TEXT,
    hardware_profile TEXT DEFAULT 'ESP32+DHT22+MQ135+LDR+LM393'
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    received_at TEXT NOT NULL,          -- UTC ISO8601 (YYYY-MM-DDTHH:MM:SS.fZ)
    device_timestamp TEXT,              -- Optional device-reported ISO8601
    sequence_number INTEGER,            -- Monotonically increasing counter from ESP32
    uptime_ms INTEGER,                  -- ESP32 millis()
    temperature_c REAL,                 -- DHT22 reading (-20 to 70 C)
    humidity_percent REAL,              -- DHT22 reading (0 to 100 %)
    light_raw INTEGER,                  -- LDR 12-bit ADC (0 to 4095)
    light_label TEXT,                   -- 'dark', 'dim', 'bright'
    mq135_adc_mv INTEGER,               -- ESP32 GPIO 34 ADC (mV)
    mq135_sensor_mv INTEGER,            -- Estimated sensor AO (mV, 1.5x divider conversion)
    mq135_status TEXT,                  -- 'warming_up', 'ready', 'conditioning', 'error'
    sound_swing INTEGER,                -- Peak-to-peak swing (150ms window)
    sound_do INTEGER,                   -- LM393 DO digital threshold (0 or 1)
    sensor_status_json TEXT,            -- Subsystem health map (JSON)
    validation_flags TEXT,              -- Semicolon-separated flags (e.g. 'OK', 'SUSPICIOUS_SPIKE')
    is_valid INTEGER DEFAULT 1,         -- 1 = Valid, 0 = Rejected by sanity checks
    FOREIGN KEY(device_id) REFERENCES devices(device_id)
);

CREATE TABLE IF NOT EXISTS environmental_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL,
    calculated_at TEXT NOT NULL,
    health_score REAL,                  -- 0 to 100
    health_grade TEXT,                  -- 'OPTIMAL', 'GOOD', 'FAIR', 'POOR', 'CRITICAL'
    comfort_index REAL,                 -- 0 to 100 (Thermal/hygric comfort)
    comfort_status TEXT,                -- 'COMFORTABLE', 'SLIGHTLY_UNCOMFORTABLE', 'UNCOMFORTABLE'
    data_coverage_pct REAL,             -- Percentage of active expected sensors
    components_json TEXT,               -- Sub-score breakdown (JSON)
    calculation_reason TEXT,            -- Explanation of factors
    FOREIGN KEY(observation_id) REFERENCES observations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    device_id TEXT NOT NULL,
    signal_name TEXT NOT NULL,          -- 'temperature', 'humidity', 'mq135', 'light', 'sound', 'system'
    severity TEXT NOT NULL,             -- 'INFO', 'WARNING', 'CRITICAL'
    rule_name TEXT NOT NULL,            -- e.g. 'MQ135_BASELINE_ELEVATION', 'COMFORT_TEMP_HIGH'
    trigger_value REAL,
    message TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    status TEXT DEFAULT 'ACTIVE',       -- 'ACTIVE', 'RESOLVED', 'ACKNOWLEDGED'
    resolved_at TEXT,
    FOREIGN KEY(device_id) REFERENCES devices(device_id)
);

CREATE TABLE IF NOT EXISTS mq135_baseline_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calculated_at TEXT NOT NULL,
    device_id TEXT NOT NULL,
    baseline_mv REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    window_size INTEGER NOT NULL,
    FOREIGN KEY(device_id) REFERENCES devices(device_id)
);

-- Performance and Query Indexes
CREATE INDEX IF NOT EXISTS idx_obs_device_received ON observations (device_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_obs_received ON observations (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_obs_device_seq ON observations (device_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_scores_obs ON environmental_scores (observation_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_baseline_device ON mq135_baseline_history (device_id, calculated_at DESC);
