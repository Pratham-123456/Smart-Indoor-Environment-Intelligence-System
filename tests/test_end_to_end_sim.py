"""End-to-End Simulation Test for SIEIS System.

Verifies end-to-end integration:
1. ESP32 Boot & Warmup Phase (Uptime < 5 min, MQ-135 warming up).
2. Stabilization & Baseline Convergence.
3. Controlled Environmental Perturbation (Simulated Gas Surge).
4. Automated Alert Triggering and Scoring Impact.
5. Ventilation Recovery & Automated Alert Resolution.
"""

from __future__ import annotations

import pytest


def test_full_system_lifecycle_simulation(client):
    device_id = "esp32-sieis-01"

    # ------------------------------------------------------------------
    # Step 1: Boot / Warmup Phase (Packets 1 - 5)
    # MQ-135 is warming up; should NOT trigger false gas alarms or be in EHS
    # ------------------------------------------------------------------
    for seq in range(1, 6):
        res = client.post(
            "/api/sensor",
            json={
                "device_id": device_id,
                "sequence_number": seq,
                "uptime_ms": seq * 10000,  # 10s .. 50s
                "temperature_c": 23.0,
                "humidity_percent": 50.0,
                "light_raw": 600,
                "light_label": "dim",
                "mq135_adc_mv": 1200,  # High transient during warmup
                "mq135_status": "warming_up",
                "sound_swing": 200,
                "sound_do": 0,
            },
        )
        assert res.status_code == 201

    # Check alerts: No MQ-135 elevation alerts should have been created during warmup!
    alerts_res = client.get(f"/api/alerts?device_id={device_id}")
    active_alerts = alerts_res.get_json()["alerts"]
    assert len([a for a in active_alerts if "MQ135" in a["rule_name"]]) == 0

    # ------------------------------------------------------------------
    # Step 2: Normal Stable Operation (Packets 6 - 15)
    # MQ-135 enters 'ready' state; stable baseline accumulates around 450 mV
    # ------------------------------------------------------------------
    for seq in range(6, 16):
        res = client.post(
            "/api/sensor",
            json={
                "device_id": device_id,
                "sequence_number": seq,
                "uptime_ms": 320000 + (seq * 5000),  # > 300,000ms
                "temperature_c": 23.2,
                "humidity_percent": 49.5,
                "light_raw": 620,
                "light_label": "dim",
                "mq135_adc_mv": 450,  # Stable baseline voltage
                "mq135_status": "ready",
                "sound_swing": 180,
                "sound_do": 0,
            },
        )
        assert res.status_code == 201

    # Verify baseline is now established in stats
    stats_res = client.get("/api/stats")
    stats_data = stats_res.get_json()
    assert stats_data["mq135_baseline_mv"] is not None
    assert 440.0 <= stats_data["mq135_baseline_mv"] <= 460.0

    # Verify health score is OPTIMAL
    latest_score = stats_data["latest_score"]
    assert latest_score["health_grade"] == "OPTIMAL"

    # ------------------------------------------------------------------
    # Step 3: Controlled Environmental Perturbation (Packet 16)
    # Gas response surges to 750 mV (>1.5x baseline)
    # ------------------------------------------------------------------
    surge_res = client.post(
        "/api/sensor",
        json={
            "device_id": device_id,
            "sequence_number": 16,
            "uptime_ms": 400000,
            "temperature_c": 23.2,
            "humidity_percent": 49.5,
            "light_raw": 620,
            "light_label": "dim",
            "mq135_adc_mv": 750,  # 750 / 450 = 1.66x baseline
            "mq135_status": "ready",
            "sound_swing": 180,
            "sound_do": 0,
        },
    )
    assert surge_res.status_code == 201
    surge_data = surge_res.get_json()
    assert surge_data["health_grade"] in ("GOOD", "FAIR", "POOR")  # Score degraded

    # Check that CRITICAL alert was raised
    alerts_surge = client.get(f"/api/alerts?device_id={device_id}").get_json()["alerts"]
    assert any(a["rule_name"] == "MQ135_ELEVATION_CRITICAL" for a in alerts_surge)

    # ------------------------------------------------------------------
    # Step 4: Ventilation Recovery (Packet 17)
    # Room is ventilated, MQ-135 returns to 445 mV
    # ------------------------------------------------------------------
    recovery_res = client.post(
        "/api/sensor",
        json={
            "device_id": device_id,
            "sequence_number": 17,
            "uptime_ms": 420000,
            "temperature_c": 23.0,
            "humidity_percent": 49.0,
            "light_raw": 620,
            "light_label": "dim",
            "mq135_adc_mv": 445,  # Returned to normal
            "mq135_status": "ready",
            "sound_swing": 180,
            "sound_do": 0,
        },
    )
    assert recovery_res.status_code == 201

    # Check that alert was automatically resolved!
    alerts_after = client.get(f"/api/alerts?device_id={device_id}").get_json()["alerts"]
    assert len([a for a in alerts_after if a["rule_name"] == "MQ135_ELEVATION_CRITICAL"]) == 0
