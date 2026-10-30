"""Tests for Experimental Indoor PM2.5 and CO2 Estimators."""

from __future__ import annotations

import pytest
from intelligence.indoor_estimation import estimate_indoor_pm25, estimate_indoor_co2


def test_pm25_estimator_valid_bounds():
    res = estimate_indoor_pm25(
        indoor_temp_c=23.0,
        indoor_rh_pct=50.0,
        mq135_pin_mv=450.0,
        mq135_baseline_mv=400.0,
        mq135_is_ready=True,
        outdoor_pm25=25.0,
    )
    assert res["status"] == "ok"
    assert res["label"] == "EXPERIMENTAL ESTIMATE"
    assert res["unit"] == "µg/m³"
    assert 2.0 <= res["value"] <= 500.0
    assert res["calibration_status"] == "uncalibrated_heuristic"
    assert "uncertainty_note" in res
    assert "limitations" in res


def test_pm25_estimator_missing_essential_inputs():
    res = estimate_indoor_pm25(
        indoor_temp_c=23.0,
        indoor_rh_pct=None,
        mq135_pin_mv=450.0,
        mq135_baseline_mv=400.0,
    )
    assert res["status"] == "insufficient_data"
    assert res["value"] is None


def test_co2_estimator_nominal_and_elevation():
    # Nominal clean conditions
    res_clean = estimate_indoor_co2(
        mq135_pin_mv=400.0,
        mq135_baseline_mv=400.0,
        mq135_is_ready=True,
        indoor_temp_c=22.0,
        indoor_rh_pct=50.0,
    )
    assert res_clean["status"] == "ok"
    assert res_clean["label"] == "EXPERIMENTAL ESTIMATE"
    assert res_clean["unit"] == "ppm"
    assert 400 <= res_clean["value"] <= 500

    # Elevated gas excursion
    res_elevated = estimate_indoor_co2(
        mq135_pin_mv=800.0,
        mq135_baseline_mv=400.0,
        mq135_is_ready=True,
        indoor_temp_c=22.0,
        indoor_rh_pct=50.0,
    )
    assert res_elevated["status"] == "ok"
    assert res_elevated["value"] > res_clean["value"]
    assert res_elevated["value"] <= 5000


def test_co2_estimator_warmup_status():
    res = estimate_indoor_co2(
        mq135_pin_mv=450.0,
        mq135_baseline_mv=None,
        mq135_is_ready=False,
    )
    assert res["status"] == "ok"
    assert res["calibration_status"] == "uncalibrated_warmup"
    assert res["confidence_level"] == "low"
