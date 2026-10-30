"""Tests for SIEIS Intelligence Engine."""

from __future__ import annotations

from intelligence.anomaly import AnomalyDetector
from intelligence.baseline import MQ135BaselineManager
from intelligence.decision import DecisionEngine
from intelligence.forecasting import TrendForecaster
from intelligence.scoring import EnvironmentalScorer
from intelligence.trends import TrendAnalyzer


def test_comfort_index_optimal():
    res = EnvironmentalScorer.calculate_comfort_index(temp_c=22.5, hum_pct=50.0)
    assert res["status"] == "COMFORTABLE"
    assert res["score"] == 100.0


def test_comfort_index_hot_and_humid():
    res = EnvironmentalScorer.calculate_comfort_index(temp_c=30.0, hum_pct=75.0)
    assert res["status"] in ("SLIGHTLY_UNCOMFORTABLE", "UNCOMFORTABLE")
    assert res["score"] < 70.0


def test_environmental_health_score_with_warmup_exclusion():
    obs = {
        "temperature_c": 23.0,
        "humidity_percent": 50.0,
        "light_raw": 600,
        "mq135_adc_mv": 1200,
        "mq135_status": "warming_up",  # warming up -> should be excluded!
        "sound_swing": 200,
    }

    ehs = EnvironmentalScorer.calculate_environmental_health_score(obs, mq135_baseline_mv=450.0)
    assert ehs["health_grade"] == "OPTIMAL"
    assert ehs["components"]["gas_response"] is None
    assert "MQ-135 is warming up" in ehs["calculation_reason"]


def test_environmental_health_score_with_gas_elevation():
    obs = {
        "temperature_c": 23.0,
        "humidity_percent": 50.0,
        "light_raw": 600,
        "mq135_adc_mv": 750,  # 750 / 450 = 1.66x baseline
        "mq135_status": "ready",
        "sound_swing": 200,
    }

    ehs = EnvironmentalScorer.calculate_environmental_health_score(obs, mq135_baseline_mv=450.0)
    assert ehs["components"]["gas_response"] is not None
    assert ehs["components"]["gas_response"] <= 40.0
    assert ehs["health_score"] < 80.0


def test_mq135_baseline_warmup_exclusion(db):
    db.upsert_device("esp32-01", "2026-10-19T03:00:00Z")
    mgr = MQ135BaselineManager(db, window_size=10)

    # Insert warming up readings (uptime < 300,000ms or status == 'warming_up')
    for i in range(10):
        db.insert_observation({
            "device_id": "esp32-01",
            "received_at": f"2026-10-19T03:0{i}:00Z",
            "uptime_ms": 10000 + (i * 1000),
            "mq135_adc_mv": 1500,
            "mq135_status": "warming_up",
            "is_valid": True,
        })

    baseline = mgr.update_baseline("esp32-01", "2026-10-19T03:10:00Z")
    # All were warmup -> baseline should not be established
    assert baseline is None

    # Now insert stable ready readings (uptime > 300,000ms and ready)
    for i in range(10):
        db.insert_observation({
            "device_id": "esp32-01",
            "received_at": f"2026-10-19T03:1{i}:00Z",
            "uptime_ms": 320000 + (i * 1000),
            "mq135_adc_mv": 450 + (i % 3) * 10,
            "mq135_status": "ready",
            "is_valid": True,
        })

    baseline2 = mgr.update_baseline("esp32-01", "2026-10-19T03:20:00Z")
    assert baseline2 is not None
    assert 440.0 <= baseline2 <= 470.0


def test_trend_analyzer():
    # Observations with rising temperature
    obs = [
        {"received_at": f"2026-10-19T03:{i:02d}:00Z", "temperature_c": 20.0 + (i * 0.2)}
        for i in range(10)
    ]

    trend = TrendAnalyzer.calculate_signal_trend(obs, "temperature_c")
    assert trend["direction"] == "RISING"
    assert trend["rate_per_min"] > 0.1
    assert trend["current"] == 21.8


def test_anomaly_detection_thermal_breach(db):
    db.upsert_device("esp32-01", "2026-10-19T03:00:00Z")
    detector = AnomalyDetector(db)

    obs = {
        "device_id": "esp32-01",
        "received_at": "2026-10-19T03:00:00Z",
        "temperature_c": 29.5,  # Exceeds 27.0
        "humidity_percent": 50.0,
    }

    alerts = detector.evaluate_observation(obs, trends={})
    assert len(alerts) >= 1
    assert alerts[0]["rule_name"] == "TEMP_HIGH_BREACH"
    assert alerts[0]["severity"] == "WARNING"


def test_forecaster_insufficient_data():
    obs = [
        {"received_at": f"2026-10-19T03:{i:02d}:00Z", "temperature_c": 22.0}
        for i in range(4)  # Only 4 observations, min required is 8
    ]

    fc = TrendForecaster.forecast_signal(obs, "temperature_c")
    assert fc["status"] == "insufficient_data"
    assert fc["valid_samples"] == 4


def test_forecaster_extrapolation_with_slope():
    # 10 observations with rising temperature
    obs = [
        {"received_at": f"2026-10-19T03:{i:02d}:00Z", "temperature_c": 20.0 + (i * 0.5)}
        for i in range(10)
    ]

    fc = TrendForecaster.forecast_signal(obs, "temperature_c", horizon_minutes=[5, 10])
    assert fc["status"] == "forecast_ready"
    assert fc["current_value"] == 24.5
    assert fc["slope_per_minute"] > 0.4
    assert len(fc["projections"]) == 2
    assert fc["projections"][0]["projected_value"] > 24.5


def test_decision_engine_stale_detection():
    recs = DecisionEngine.evaluate_recommendations(
        latest_observation=None,
        scores=None,
        trends=None,
        forecasts=None,
        is_stale=True,
    )
    assert len(recs) == 1
    assert recs[0]["category"] == "CONNECTIVITY"
    assert "Disconnected" in recs[0]["title"]
