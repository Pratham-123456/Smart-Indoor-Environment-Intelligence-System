"""Tests for Authoritative Room Comfort Index (RCI) Calculation Engine."""

from __future__ import annotations

import pytest
from intelligence.rci import RoomComfortIndexEngine, calculate_rci


def test_temperature_scoring():
    # Optimal band: 21.0 - 24.0 C -> 100
    assert RoomComfortIndexEngine.calculate_temp_score(21.0) == 100.0
    assert RoomComfortIndexEngine.calculate_temp_score(22.5) == 100.0
    assert RoomComfortIndexEngine.calculate_temp_score(24.0) == 100.0

    # Below optimal: (T - 14) / 7 * 100
    assert RoomComfortIndexEngine.calculate_temp_score(17.5) == 50.0
    assert RoomComfortIndexEngine.calculate_temp_score(14.0) == 0.0
    assert RoomComfortIndexEngine.calculate_temp_score(10.0) == 0.0

    # Above optimal: (33 - T) / 9 * 100
    assert RoomComfortIndexEngine.calculate_temp_score(28.5) == 50.0
    assert RoomComfortIndexEngine.calculate_temp_score(33.0) == 0.0
    assert RoomComfortIndexEngine.calculate_temp_score(35.0) == 0.0

    # Missing or invalid
    assert RoomComfortIndexEngine.calculate_temp_score(None) is None


def test_humidity_scoring():
    # Optimal band: 40.0 - 60.0 % -> 100
    assert RoomComfortIndexEngine.calculate_humidity_score(40.0) == 100.0
    assert RoomComfortIndexEngine.calculate_humidity_score(50.0) == 100.0
    assert RoomComfortIndexEngine.calculate_humidity_score(60.0) == 100.0

    # Below optimal: (RH - 15) / 25 * 100
    assert RoomComfortIndexEngine.calculate_humidity_score(27.5) == 50.0
    assert RoomComfortIndexEngine.calculate_humidity_score(15.0) == 0.0
    assert RoomComfortIndexEngine.calculate_humidity_score(10.0) == 0.0

    # Above optimal: (85 - RH) / 25 * 100
    assert RoomComfortIndexEngine.calculate_humidity_score(72.5) == 50.0
    assert RoomComfortIndexEngine.calculate_humidity_score(85.0) == 0.0
    assert RoomComfortIndexEngine.calculate_humidity_score(90.0) == 0.0


def test_gas_scoring():
    # Ratio <= 1.05 -> 100
    assert RoomComfortIndexEngine.calculate_gas_score(400, 400, "ready") == 100.0
    assert RoomComfortIndexEngine.calculate_gas_score(420, 400, "ready") == 100.0

    # Ratio >= 2.50 -> 0
    assert RoomComfortIndexEngine.calculate_gas_score(1000, 400, "ready") == 0.0

    # Intermediate ratio
    score = RoomComfortIndexEngine.calculate_gas_score(600, 400, "ready")  # ratio = 1.5
    assert score is not None
    assert 0.0 < score < 100.0

    # Unready or warming up -> None (excluded from weighting)
    assert RoomComfortIndexEngine.calculate_gas_score(400, 400, "warming_up") is None
    assert RoomComfortIndexEngine.calculate_gas_score(400, None, "ready") is None


def test_light_scoring():
    assert RoomComfortIndexEngine.calculate_light_score(2000) == 100.0
    assert RoomComfortIndexEngine.calculate_light_score(1000) == 85.0
    assert RoomComfortIndexEngine.calculate_light_score(150) == 50.0


def test_sound_scoring():
    assert RoomComfortIndexEngine.calculate_sound_score(250, 0) == 100.0
    assert RoomComfortIndexEngine.calculate_sound_score(600, 0) == 80.0
    assert RoomComfortIndexEngine.calculate_sound_score(1500, 0) == 40.0
    assert RoomComfortIndexEngine.calculate_sound_score(250, 1) == 40.0


def test_rci_perfect_conditions():
    obs = {
        "temperature_c": 22.5,
        "humidity_percent": 50.0,
        "mq135_adc_mv": 400,
        "mq135_status": "ready",
        "light_raw": 2000,
        "sound_swing": 200,
        "sound_do": 0,
    }
    res = calculate_rci(observation=obs, mq_baseline=400.0, stale_seconds_elapsed=5)
    assert res["score"] == 100.0
    assert res["status"] == "Optimal / Comfortable"
    assert res["color_band"] == "green"
    assert res["data_coverage_percent"] == 100.0


def test_rci_missing_core_returns_indeterminate():
    obs = {
        "temperature_c": None,
        "humidity_percent": 50.0,
    }
    res = calculate_rci(observation=obs, mq_baseline=400.0)
    assert res["score"] is None
    assert "Indeterminate" in res["status"]


def test_rci_stale_telemetry_returns_indeterminate():
    obs = {
        "temperature_c": 22.5,
        "humidity_percent": 50.0,
    }
    # Stale threshold is 120s
    res = calculate_rci(observation=obs, mq_baseline=400.0, stale_seconds_elapsed=150)
    assert res["score"] is None
    assert res["is_stale"] is True
