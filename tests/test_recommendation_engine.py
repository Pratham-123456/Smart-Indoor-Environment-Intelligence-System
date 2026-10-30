"""Tests for Context-Aware Recommendation Engine and Diagnostics Matrix (Rules A-I)."""

from __future__ import annotations

import pytest
from intelligence.recommendation_engine import (
    evaluate_recommendations,
    evaluate_diagnostics_matrix,
)


def test_rule_a_firing():
    # Hot room (26°C), cooler outdoors (21°C), clean AQI (40)
    indoor = {"temperature": 26.0, "humidity": 50.0, "mq135_is_ready": True}
    outdoor = {"temperature_c": 21.0, "relative_humidity_pct": 50.0, "aqi": 40.0}
    comparison = {"humidity": {"psychrometrics": {}}}

    recs = evaluate_recommendations(indoor, outdoor, comparison)
    rule_ids = [r["rule_id"] for r in recs]
    assert "rule_a" in rule_ids
    rec_a = next(r for r in recs if r["rule_id"] == "rule_a")
    assert "Natural Ventilation" in rec_a["title"]


def test_rule_b_firing():
    # Elevated MQ-135 ratio (1.4x), bad outdoor air (AQI 140)
    indoor = {
        "temperature": 22.0,
        "humidity": 50.0,
        "mq135_pin_mv": 560,
        "mq135_baseline_mv": 400,
        "mq135_baseline_ratio": 1.40,
        "mq135_is_ready": True,
    }
    outdoor = {"temperature_c": 22.0, "aqi": 140.0}
    comparison = {"humidity": {"psychrometrics": {}}}

    recs = evaluate_recommendations(indoor, outdoor, comparison)
    rule_ids = [r["rule_id"] for r in recs]
    assert "rule_b" in rule_ids
    rec_b = next(r for r in recs if r["rule_id"] == "rule_b")
    assert "Keep windows closed" in rec_b["recommended_action"]


def test_rule_c_firing():
    # Elevated MQ-135 ratio (1.35x), clean outdoor air (AQI 45)
    indoor = {
        "temperature": 22.0,
        "humidity": 50.0,
        "mq135_pin_mv": 540,
        "mq135_baseline_mv": 400,
        "mq135_baseline_ratio": 1.35,
        "mq135_is_ready": True,
    }
    outdoor = {"temperature_c": 22.0, "aqi": 45.0}
    comparison = {"humidity": {"psychrometrics": {}}}

    recs = evaluate_recommendations(indoor, outdoor, comparison)
    rule_ids = [r["rule_id"] for r in recs]
    assert "rule_c" in rule_ids


def test_rule_d_firing():
    # Hot room (26°C), even hotter outdoors (32°C)
    indoor = {"temperature": 26.0, "humidity": 50.0, "mq135_is_ready": True}
    outdoor = {"temperature_c": 32.0, "aqi": 40.0}
    comparison = {"humidity": {"psychrometrics": {}}}

    recs = evaluate_recommendations(indoor, outdoor, comparison)
    rule_ids = [r["rule_id"] for r in recs]
    assert "rule_d" in rule_ids
    rec_d = next(r for r in recs if r["rule_id"] == "rule_d")
    assert "Do NOT open windows" in rec_d["recommended_action"]


def test_rule_f_dark_room():
    indoor = {"ldr_raw": 150, "temperature": 22.0, "humidity": 50.0}
    recs = evaluate_recommendations(indoor, {}, {"humidity": {"psychrometrics": {}}})
    rule_ids = [r["rule_id"] for r in recs]
    assert "rule_f" in rule_ids


def test_rule_g_sound():
    indoor = {"sound_swing": 1500, "sound_digital_trigger": 1, "temperature": 22.0, "humidity": 50.0}
    recs = evaluate_recommendations(indoor, {}, {"humidity": {"psychrometrics": {}}})
    rule_ids = [r["rule_id"] for r in recs]
    assert "rule_g" in rule_ids


def test_diagnostics_matrix_nine_subsystems():
    indoor = {"temperature": 23.0, "humidity": 50.0, "mq135_pin_mv": 420, "mq135_is_ready": True}
    outdoor = {"freshness_status": "live", "aqi": 40.0, "location_label": "Bengaluru"}
    rci_res = {"data_coverage_pct": 100}

    diag = evaluate_diagnostics_matrix(
        indoor_telemetry=indoor,
        outdoor_data=outdoor,
        rci_result=rci_res,
        usb_status="connected",
        wifi_status="active",
    )
    assert "subsystems" in diag
    subs = diag["subsystems"]
    expected_subs = [
        "usb_bridge",
        "wifi_telemetry",
        "backend_server",
        "sqlite_database",
        "dht22_sensor",
        "mq135_sensor",
        "experimental_estimators",
        "outdoor_api",
        "rci_coverage",
    ]
    for s in expected_subs:
        assert s in subs
        assert "status" in subs[s]
        assert "label" in subs[s]
