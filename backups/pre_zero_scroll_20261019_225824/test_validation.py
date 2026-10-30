"""Tests for SIEIS Payload Validation Layer."""

from __future__ import annotations

import pytest
from validation import PayloadValidator, ValidationError


def test_validate_valid_full_payload():
    payload = {
        "device_id": "esp32-sieis-01",
        "firmware_version": "1.0.0",
        "sequence_number": 42,
        "uptime_ms": 350000,
        "temperature_c": 23.5,
        "humidity_percent": 52.0,
        "light_raw": 650,
        "light_label": "dim",
        "mq135_adc_mv": 480,
        "mq135_sensor_mv": 720,
        "mq135_status": "ready",
        "sound_swing": 280,
        "sound_do": 0,
        "sensor_status": {"dht22": "ok", "ldr": "ok", "mq135": "ready", "sound": "ok"},
    }

    sanitized, flags, is_valid = PayloadValidator.validate_incoming_packet(payload)

    assert is_valid is True
    assert sanitized["device_id"] == "esp32-sieis-01"
    assert sanitized["temperature_c"] == 23.5
    assert sanitized["humidity_percent"] == 52.0
    assert sanitized["light_raw"] == 650
    assert sanitized["light_label"] == "dim"
    assert sanitized["mq135_adc_mv"] == 480
    assert sanitized["mq135_sensor_mv"] == 720
    assert sanitized["mq135_status"] == "ready"
    assert sanitized["sound_swing"] == 280
    assert sanitized["sound_do"] == 0
    assert "OK" in flags


def test_validate_missing_device_id_raises_error():
    payload = {"temperature_c": 22.0}
    with pytest.raises(ValidationError) as exc_info:
        PayloadValidator.validate_incoming_packet(payload)
    assert "device_id" in exc_info.value.message


def test_validate_out_of_bounds_temperature():
    payload = {
        "device_id": "esp32-sieis-01",
        "temperature_c": 150.0,  # Extreme impossible indoor value
        "humidity_percent": 45.0,
    }
    sanitized, flags, is_valid = PayloadValidator.validate_incoming_packet(payload)

    assert is_valid is False
    assert any("TEMP_OUT_OF_BOUNDS" in f for f in flags)
    assert sanitized["temperature_c"] == 150.0


def test_validate_nan_values():
    payload = {
        "device_id": "esp32-sieis-01",
        "temperature_c": float("nan"),
        "humidity_percent": 50.0,
    }
    sanitized, flags, is_valid = PayloadValidator.validate_incoming_packet(payload)

    assert is_valid is False
    assert any("TEMP_NAN_OR_INF" in f for f in flags)
    assert sanitized["temperature_c"] is None


def test_validate_derived_light_label():
    # Test dark threshold (<250)
    p_dark = {"device_id": "esp32-01", "light_raw": 120}
    s_dark, _, _ = PayloadValidator.validate_incoming_packet(p_dark)
    assert s_dark["light_label"] == "dark"

    # Test dim threshold (250..1699)
    p_dim = {"device_id": "esp32-01", "light_raw": 800}
    s_dim, _, _ = PayloadValidator.validate_incoming_packet(p_dim)
    assert s_dim["light_label"] == "dim"

    # Test bright threshold (>=1700)
    p_bright = {"device_id": "esp32-01", "light_raw": 2200}
    s_bright, _, _ = PayloadValidator.validate_incoming_packet(p_bright)
    assert s_bright["light_label"] == "bright"


def test_validate_mq135_sensor_mv_derivation():
    # If mq135_sensor_mv is omitted, should compute pin_mv * 1.5
    payload = {"device_id": "esp32-01", "mq135_adc_mv": 600}
    sanitized, _, _ = PayloadValidator.validate_incoming_packet(payload)
    assert sanitized["mq135_sensor_mv"] == 900
