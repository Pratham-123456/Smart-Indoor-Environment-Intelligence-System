"""SIEIS Local Device Telemetry Simulator (Pure Python Standard Library).

Sends realistic simulated telemetry packets to the local SIEIS backend.
Demonstrates:
- Startup / warmup state
- Normal comfortable indoor conditions
- Artificial gas elevation to trigger alert
- Normalization back to baseline
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

SERVER_URL = "http://127.0.0.1:5000/api/sensor"
DEVICE_ID = "esp32-sieis-sim"


def post_telemetry(payload: dict) -> tuple[int, dict]:
    """Posts telemetry using Python standard library urllib."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SERVER_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            status_code = response.getcode()
            res_body = json.loads(response.read().decode("utf-8"))
            return status_code, res_body
    except urllib.error.HTTPError as e:
        err_body = json.loads(e.read().decode("utf-8")) if e.fp else {}
        return e.code, err_body
    except Exception as e:
        return 0, {"error": str(e)}


def run_simulation():
    print("=" * 65)
    print("  SIEIS Local Telemetry Simulator")
    print(f"  Target: {SERVER_URL}")
    print("  Open http://localhost:5000/ to observe live dashboard updates!")
    print("=" * 65)
    print("Press Ctrl+C at any time to halt.\n")

    seq = 0
    start_time = time.time()

    # 1. Warmup Phase (Packets 1-3)
    print(">>> Phase 1: ESP32 Boot & MQ-135 Warmup (Excluded from EHS) <<<")
    for i in range(3):
        seq += 1
        uptime_ms = int((time.time() - start_time) * 1000)
        payload = {
            "device_id": DEVICE_ID,
            "firmware_version": "1.0.0-sim",
            "sequence_number": seq,
            "uptime_ms": uptime_ms,
            "temperature_c": 23.0,
            "humidity_percent": 50.0,
            "light_raw": 600,
            "light_label": "dim",
            "mq135_adc_mv": 1100,  # Transient warmup voltage
            "mq135_status": "warming_up",
            "sound_swing": 180,
            "sound_do": 0,
            "sensor_status": {"dht22": "ok", "ldr": "ok", "mq135": "warming_up", "sound": "ok"},
        }
        code, res = post_telemetry(payload)
        if code == 0:
            print(f"Connection failed: {res.get('error')}. Is the backend running? Run: .\\.venv\\Scripts\\python.exe backend\\app.py")
            return
        print(f"[Packet {seq:02d}] Warming Up | HTTP {code} | Health Score: {res.get('health_score')} (Warmup Quarantined)")
        time.sleep(2.5)

    # 2. Normal Stable Phase (Packets 4-9)
    print("\n>>> Phase 2: Sensor Ready & Baseline Learning (Optimal Indoor Air) <<<")
    for i in range(6):
        seq += 1
        uptime_ms = int(320000 + (time.time() - start_time) * 1000)
        payload = {
            "device_id": DEVICE_ID,
            "firmware_version": "1.0.0-sim",
            "sequence_number": seq,
            "uptime_ms": uptime_ms,
            "temperature_c": round(23.2 + (i * 0.1), 1),
            "humidity_percent": round(50.0 - (i * 0.2), 1),
            "light_raw": 650 + (i * 10),
            "light_label": "dim",
            "mq135_adc_mv": 450 + (i % 3) * 5,  # Stable baseline voltage
            "mq135_status": "ready",
            "sound_swing": 220,
            "sound_do": 0,
            "sensor_status": {"dht22": "ok", "ldr": "ok", "mq135": "ready", "sound": "ok"},
        }
        code, res = post_telemetry(payload)
        print(f"[Packet {seq:02d}] Ready | HTTP {code} | EHS Score: {res.get('health_score')} ({res.get('health_grade')})")
        time.sleep(2.5)

    # 3. Gas Elevation Event (Packets 10-12)
    print("\n>>> Phase 3: Simulated Reducing Gas Surge (Surge to 750 mV -> Critical Alert) <<<")
    for i in range(3):
        seq += 1
        uptime_ms = int(350000 + (time.time() - start_time) * 1000)
        payload = {
            "device_id": DEVICE_ID,
            "firmware_version": "1.0.0-sim",
            "sequence_number": seq,
            "uptime_ms": uptime_ms,
            "temperature_c": 23.8,
            "humidity_percent": 48.0,
            "light_raw": 680,
            "light_label": "dim",
            "mq135_adc_mv": 750,  # 750 / 450 = 1.66x baseline -> CRITICAL ALERT
            "mq135_status": "ready",
            "sound_swing": 250,
            "sound_do": 0,
            "sensor_status": {"dht22": "ok", "ldr": "ok", "mq135": "ready", "sound": "ok"},
        }
        code, res = post_telemetry(payload)
        print(f"[Packet {seq:02d} - SURGE] Gas Elevation | HTTP {code} | EHS: {res.get('health_score')} ({res.get('health_grade')})")
        time.sleep(2.5)

    # 4. Recovery to Normal (Packets 13-16)
    print("\n>>> Phase 4: Simulated Room Ventilation (Gas Drops Back to 445 mV) <<<")
    for i in range(4):
        seq += 1
        uptime_ms = int(370000 + (time.time() - start_time) * 1000)
        payload = {
            "device_id": DEVICE_ID,
            "firmware_version": "1.0.0-sim",
            "sequence_number": seq,
            "uptime_ms": uptime_ms,
            "temperature_c": 23.4,
            "humidity_percent": 49.5,
            "light_raw": 630,
            "light_label": "dim",
            "mq135_adc_mv": 445,  # Returned to clean baseline
            "mq135_status": "ready",
            "sound_swing": 180,
            "sound_do": 0,
            "sensor_status": {"dht22": "ok", "ldr": "ok", "mq135": "ready", "sound": "ok"},
        }
        code, res = post_telemetry(payload)
        print(f"[Packet {seq:02d} - RECOVERED] Normal Baseline | HTTP {code} | EHS: {res.get('health_score')} ({res.get('health_grade')})")
        time.sleep(2.5)

    print("\nSimulation successfully completed!")
    print("All points are recorded in SQLite and rendered in your web dashboard charts.")


if __name__ == "__main__":
    run_simulation()
