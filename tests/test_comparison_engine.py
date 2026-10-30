"""Tests for Indoor vs Outdoor Comparison Engine."""

from __future__ import annotations

import pytest
from intelligence.comparison_engine import (
    calculate_magnus_tetens_dew_point,
    calculate_absolute_humidity,
    evaluate_ventilation_favourability,
    compare_indoor_and_outdoor,
)


def test_magnus_tetens_dew_point():
    # At 25°C and 50% RH, dew point is ~13.9°C
    dp = calculate_magnus_tetens_dew_point(25.0, 50.0)
    assert dp is not None
    assert 13.5 <= dp <= 14.2

    # 100% RH -> Dew point equals temperature
    dp_sat = calculate_magnus_tetens_dew_point(20.0, 100.0)
    assert dp_sat == 20.0

    # None inputs
    assert calculate_magnus_tetens_dew_point(None, 50.0) is None
    assert calculate_magnus_tetens_dew_point(25.0, None) is None


def test_absolute_humidity():
    # At 20°C and 50% RH, absolute humidity is ~8.6 g/m³
    ah = calculate_absolute_humidity(20.0, 50.0)
    assert ah is not None
    assert 8.0 <= ah <= 9.2

    assert calculate_absolute_humidity(None, 50.0) is None


def test_ventilation_assessment_rules():
    # 1. Unfavourable due to polluted outdoor air (AQI > 100)
    rating, expl, _ = evaluate_ventilation_favourability(
        indoor_temp=26.0,
        indoor_rh=50.0,
        outdoor_temp=22.0,
        outdoor_rh=50.0,
        outdoor_aqi=140.0,
        indoor_ah=12.0,
        outdoor_ah=10.0,
    )
    assert rating == "unfavourable"
    assert "US AQI" in expl

    # 2. Favourable cooling (Indoor hot 26°C, Outdoor cooler 21°C, Clean AQI 45)
    rating_fav, expl_fav, _ = evaluate_ventilation_favourability(
        indoor_temp=26.0,
        indoor_rh=50.0,
        outdoor_temp=21.0,
        outdoor_rh=50.0,
        outdoor_aqi=45.0,
        indoor_ah=12.0,
        outdoor_ah=10.0,
    )
    assert rating_fav == "favourable"
    assert "cooler" in expl_fav

    # 3. Intermediate AQI (76 - 100) -> Mixed
    rating_mixed, _, _ = evaluate_ventilation_favourability(
        indoor_temp=26.0,
        indoor_rh=50.0,
        outdoor_temp=21.0,
        outdoor_rh=50.0,
        outdoor_aqi=85.0,
        indoor_ah=12.0,
        outdoor_ah=10.0,
    )
    assert rating_mixed == "mixed"

    # 4. Unfavourable overheating (Indoor 25°C, Outdoor hotter 32°C)
    rating_hot, _, _ = evaluate_ventilation_favourability(
        indoor_temp=25.0,
        indoor_rh=50.0,
        outdoor_temp=32.0,
        outdoor_rh=40.0,
        outdoor_aqi=40.0,
        indoor_ah=11.0,
        outdoor_ah=13.0,
    )
    assert rating_hot == "unfavourable"


def test_compare_indoor_and_outdoor_schema():
    indoor = {
        "temperature": 25.0,
        "humidity": 55.0,
        "mq135_pin_mv": 450,
        "mq135_baseline_mv": 400,
        "mq135_is_ready": True,
    }
    outdoor = {
        "temperature_c": 21.0,
        "relative_humidity_pct": 50.0,
        "aqi": 45.0,
        "aqi_scale": "us_aqi",
        "aqi_category": "Good",
    }
    res = compare_indoor_and_outdoor(indoor, outdoor)
    assert res["status"] == "ok"
    assert res["temperature"]["delta_c"] == 4.0
    assert res["temperature"]["direction"] == "outdoor_cooler"
    assert res["humidity"]["delta_rh_pp"] == 5.0
    assert res["humidity"]["unit"] == "pp"
    assert "psychrometrics" in res["humidity"]
    assert res["ventilation_assessment"]["rating"] == "favourable"
