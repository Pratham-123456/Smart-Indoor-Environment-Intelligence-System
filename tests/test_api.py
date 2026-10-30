"""Tests for SIEIS REST API Endpoints."""

from __future__ import annotations

import json
import pytest


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "SIEIS Backend"
    assert "device_freshness" in data


def test_dashboard_route_serves_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Smart Indoor Environmental Intelligence System" in response.data
    assert b"SIEIS" in response.data


def test_hardware_status_endpoint(client):
    response = client.get("/api/hardware-status")
    assert response.status_code == 200
    data = response.get_json()
    assert "active_hardware" in data
    assert "unsupported_channels" in data

    # Verify honest reporting of hardware
    sensors = [s["sensor"] for s in data["active_hardware"]]
    assert "DHT22" in sensors
    assert "MQ-135 Gas Sensor" in sensors
    assert "Bare LDR Divider" in sensors

    unsupported = [s["sensor"] for s in data["unsupported_channels"]]
    assert "BME280" in unsupported
    assert "ENS160" in unsupported


def test_post_sensor_telemetry_success(client):
    payload = {
        "device_id": "esp32-sieis-01",
        "firmware_version": "1.0.0",
        "sequence_number": 1,
        "uptime_ms": 320000,
        "temperature_c": 22.8,
        "humidity_percent": 50.0,
        "light_raw": 520,
        "light_label": "dim",
        "mq135_adc_mv": 450,
        "mq135_sensor_mv": 675,
        "mq135_status": "ready",
        "sound_swing": 210,
        "sound_do": 0,
        "sensor_status": {"dht22": "ok"},
    }

    response = client.post("/api/sensor", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "accepted"
    assert data["observation_id"] is not None
    assert data["is_valid"] is True


def test_post_sensor_malformed_json_400(client):
    response = client.post(
        "/api/sensor", data="invalid non-json text", content_type="application/json"
    )
    assert response.status_code == 400


def test_post_sensor_missing_device_id_400(client):
    response = client.post("/api/sensor", json={"temperature_c": 22.0})
    assert response.status_code == 400
    data = response.get_json()
    assert "device_id" in data["error"]


def test_get_readings_limit(client):
    # Post 3 packets
    for i in range(1, 4):
        client.post(
            "/api/sensor",
            json={
                "device_id": "esp32-sieis-01",
                "sequence_number": i,
                "temperature_c": 20.0 + i,
                "humidity_percent": 50.0,
            },
        )

    res = client.get("/api/readings?limit=2")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["readings"]) == 2


def test_get_stats_and_recommendations(client):
    client.post(
        "/api/sensor",
        json={
            "device_id": "esp32-sieis-01",
            "sequence_number": 1,
            "temperature_c": 23.5,
            "humidity_percent": 50.0,
            "light_raw": 500,
            "light_label": "dim",
            "mq135_adc_mv": 400,
            "mq135_status": "ready",
            "sound_swing": 200,
        },
    )

    stats_res = client.get("/api/stats")
    assert stats_res.status_code == 200
    assert stats_res.get_json()["stats"]["total_observations"] >= 1

    recs_res = client.get("/api/recommendations")
    assert recs_res.status_code == 200
    assert "recommendations" in recs_res.get_json()
