"""Tests for Master Specification Endpoints in SIEIS Flask Application."""

from __future__ import annotations

import pytest


def test_api_comfort_index(client):
    # Post telemetry
    client.post(
        "/api/sensor",
        json={
            "device_id": "esp32-sieis-01",
            "sequence_number": 1,
            "temperature_c": 22.5,
            "humidity_percent": 50.0,
            "light_raw": 1500,
            "mq135_adc_mv": 420,
            "mq135_status": "ready",
            "sound_swing": 250,
        },
    )

    res = client.get("/api/comfort-index")
    assert res.status_code == 200
    data = res.get_json()
    assert "score" in data
    assert "status" in data
    assert "color_band" in data
    assert "data_coverage_percent" in data


def test_api_indoor_estimates(client):
    res = client.get("/api/indoor-estimates")
    assert res.status_code == 200
    data = res.get_json()
    assert "pm25" in data
    assert "co2" in data
    assert data["pm25"]["label"] == "EXPERIMENTAL ESTIMATE"
    assert data["co2"]["label"] == "EXPERIMENTAL ESTIMATE"


def test_api_outdoor_and_location(client):
    # Test location config GET
    res_loc = client.get("/api/config/location")
    assert res_loc.status_code == 200
    assert "latitude" in res_loc.get_json()

    # Test location config POST
    res_post = client.post(
        "/api/config/location",
        json={"latitude": 13.0, "longitude": 77.6, "location_label": "Test City"},
    )
    assert res_post.status_code == 200
    assert res_post.get_json()["status"] == "updated"

    # Test outdoor endpoint
    res_out = client.get("/api/outdoor")
    assert res_out.status_code == 200
    out_data = res_out.get_json()
    assert "aqi_scale" in out_data
    assert "provider" in out_data


def test_api_comparison(client):
    res = client.get("/api/comparison")
    assert res.status_code == 200
    data = res.get_json()
    assert "temperature" in data
    assert "humidity" in data
    assert "ventilation_assessment" in data


def test_api_diagnostics(client):
    res = client.get("/api/diagnostics")
    assert res.status_code == 200
    data = res.get_json()
    assert "subsystems" in data
    assert "usb_bridge" in data["subsystems"]
    assert "outdoor_api" in data["subsystems"]


def test_report_routes(client):
    # Test viewing HTML report
    res_html = client.get("/report")
    assert res_html.status_code == 200
    assert b"Smart Indoor Environmental Intelligence System" in res_html.data

    # Test downloading Markdown report
    res_md = client.get("/report/markdown")
    assert res_md.status_code == 200
    assert "text/markdown" in res_md.headers.get("Content-Type", "") or "text/plain" in res_md.headers.get("Content-Type", "")

    # Test downloading HTML report
    res_html_dl = client.get("/report/html/download")
    assert res_html_dl.status_code == 200
    assert "text/html" in res_html_dl.headers.get("Content-Type", "")

    # Test viewing RCI specification
    res_rci = client.get("/rci")
    assert res_rci.status_code == 200
    assert b"Room Comfort Index" in res_rci.data

    # Test downloading RCI markdown specification
    res_rci_md = client.get("/download/rci.md")
    assert res_rci_md.status_code == 200
    assert b"SIEIS-SPEC-RCI-2026-REV2" in res_rci_md.data


def test_serial_bridge_endpoints(client):
    # Test GET /api/serial/ports
    res_ports = client.get("/api/serial/ports")
    assert res_ports.status_code == 200
    data = res_ports.get_json()
    assert "ports" in data
    assert "bridge_status" in data

    # Test POST /api/serial/reset
    res_reset = client.post("/api/serial/reset")
    assert res_reset.status_code == 200
    assert "status" in res_reset.get_json()

    # Test POST /api/serial/reconnect
    res_reconn = client.post("/api/serial/reconnect", json={"port": "COM4"})
    assert res_reconn.status_code == 200
    assert res_reconn.get_json()["status"] in ("reconnected", "failed")

    # Test /api/stats serial status fields
    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    stats_data = res_stats.get_json()
    assert "serial_bridge_status" in stats_data
    assert "usb_bridge_status" in stats_data["subsystem_statuses"]
