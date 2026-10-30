"""Tests for SIEIS Database Layer (SQLite)."""

from __future__ import annotations

import pytest


def test_schema_initialization(db):
    conn = db.get_connection()
    tables = [
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
    ]
    assert "devices" in tables
    assert "observations" in tables
    assert "environmental_scores" in tables
    assert "alerts" in tables
    assert "mq135_baseline_history" in tables


def test_insert_observation_and_device_upsert(db):
    obs_data = {
        "device_id": "esp32-sieis-01",
        "received_at": "2026-10-19T03:00:00Z",
        "sequence_number": 1,
        "uptime_ms": 10000,
        "temperature_c": 24.2,
        "humidity_percent": 48.5,
        "light_raw": 550,
        "light_label": "dim",
        "mq135_adc_mv": 420,
        "mq135_sensor_mv": 630,
        "mq135_status": "ready",
        "sound_swing": 180,
        "sound_do": 0,
        "validation_flags": "OK",
        "is_valid": True,
    }

    obs_id, is_dup = db.insert_observation(obs_data)
    assert obs_id > 0
    assert is_dup is False

    # Check device was registered
    conn = db.get_connection()
    device = conn.execute("SELECT * FROM devices WHERE device_id = ?", ("esp32-sieis-01",)).fetchone()
    assert device is not None
    assert device["device_id"] == "esp32-sieis-01"


def test_duplicate_sequence_number_detection(db):
    obs_data = {
        "device_id": "esp32-sieis-01",
        "received_at": "2026-10-19T03:00:00Z",
        "sequence_number": 10,
        "temperature_c": 22.0,
        "is_valid": True,
    }

    obs_id1, is_dup1 = db.insert_observation(obs_data)
    assert is_dup1 is False

    # Resend same sequence number
    obs_id2, is_dup2 = db.insert_observation(obs_data)
    assert is_dup2 is True
    assert obs_id1 == obs_id2


def test_insert_and_retrieve_scores(db):
    obs_data = {
        "device_id": "esp32-01",
        "received_at": "2026-10-19T03:00:00Z",
        "temperature_c": 23.0,
        "is_valid": True,
    }
    obs_id, _ = db.insert_observation(obs_data)

    score_data = {
        "observation_id": obs_id,
        "calculated_at": "2026-10-19T03:00:01Z",
        "health_score": 92.5,
        "health_grade": "OPTIMAL",
        "comfort_index": 95.0,
        "comfort_status": "COMFORTABLE",
        "data_coverage_pct": 100.0,
        "components": {"comfort": 95.0, "gas": 90.0},
        "calculation_reason": "Optimal parameters",
    }
    score_id = db.insert_scores(score_data)
    assert score_id > 0

    latest = db.get_latest_scores("esp32-01")
    assert latest is not None
    assert latest["health_score"] == 92.5
    assert latest["health_grade"] == "OPTIMAL"
    assert latest["components"]["comfort"] == 95.0


def test_alert_lifecycle_and_resolution(db):
    # Insert device
    db.upsert_device("esp32-01", "2026-10-19T03:00:00Z")

    alert_data = {
        "created_at": "2026-10-19T03:00:00Z",
        "device_id": "esp32-01",
        "signal_name": "temperature",
        "severity": "WARNING",
        "rule_name": "TEMP_HIGH_BREACH",
        "trigger_value": 29.5,
        "message": "High temperature",
        "recommendation": "Cool room",
        "status": "ACTIVE",
    }
    alert_id = db.insert_alert(alert_data)
    assert alert_id > 0

    active = db.get_active_alerts("esp32-01")
    assert len(active) == 1
    assert active[0]["rule_name"] == "TEMP_HIGH_BREACH"

    # Resolve alert
    count = db.resolve_alerts_for_rule("esp32-01", "TEMP_HIGH_BREACH", "2026-10-19T03:05:00Z")
    assert count == 1

    active_after = db.get_active_alerts("esp32-01")
    assert len(active_after) == 0


def test_baseline_history_recording(db):
    db.upsert_device("esp32-01", "2026-10-19T03:00:00Z")
    db.record_baseline(
        device_id="esp32-01",
        calculated_at="2026-10-19T03:05:00Z",
        baseline_mv=450.0,
        sample_count=30,
        window_size=30,
    )

    baseline = db.get_latest_baseline("esp32-01")
    assert baseline is not None
    assert baseline["baseline_mv"] == 450.0
    assert baseline["sample_count"] == 30
