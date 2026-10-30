"""SIEIS (Smart Indoor Environmental Intelligence System) - Flask Application Server.

Provides RESTful endpoints for ESP32 sensor telemetry ingestion, SQLite persistence,
real-time intelligence scoring, trend analysis, anomaly alerts, forecasting,
USB Serial bridge ingestion, interactive demo streaming, and web dashboard delivery.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, jsonify, make_response, render_template, request, send_file

from config import Config
from database import Database
from intelligence.anomaly import AnomalyDetector
from intelligence.baseline import MQ135BaselineManager
from intelligence.decision import DecisionEngine
from intelligence.forecasting import TrendForecaster
from intelligence.scoring import EnvironmentalScorer
from intelligence.trends import TrendAnalyzer
from intelligence.rci import calculate_rci
from intelligence.indoor_estimation import estimate_indoor_pm25, estimate_indoor_co2
from services.outdoor_service import get_outdoor_service
from intelligence.comparison_engine import compare_indoor_and_outdoor
from intelligence.recommendation_engine import (
    evaluate_recommendations as evaluate_context_recs,
    evaluate_diagnostics_matrix,
)
from serial_bridge import SerialBridge
from validation import PayloadValidator, ValidationError

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sieis.server")


def create_app(config_class: type = Config) -> Flask:
    """Application factory for SIEIS Flask server."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)

    # Initialize Database and Intelligence Services
    db = Database(app.config["DATABASE_PATH"])
    baseline_mgr = MQ135BaselineManager(db, window_size=app.config["MQ135_BASELINE_WINDOW_SIZE"])
    anomaly_detector = AnomalyDetector(db)

    # Attach services to app context
    app.db = db  # type: ignore[attr-defined]
    app.baseline_mgr = baseline_mgr  # type: ignore[attr-defined]
    app.anomaly_detector = anomaly_detector  # type: ignore[attr-defined]

    last_wifi_http_telemetry_time = [None]

    # Shared Core Telemetry Ingestion Function
    def process_and_persist_telemetry(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        sanitized_data, flags, is_valid = PayloadValidator.validate_incoming_packet(raw_payload)
        now_utc = datetime.now(timezone.utc).isoformat()
        sanitized_data["received_at"] = now_utc

        obs_id, is_duplicate = db.insert_observation(sanitized_data)
        if is_duplicate:
            return {
                "status": "duplicate_ignored",
                "observation_id": obs_id,
                "flags": flags,
                "is_valid": is_valid,
            }

        health_score_res = None
        if is_valid:
            device_id = sanitized_data["device_id"]
            current_baseline = baseline_mgr.update_baseline(device_id, now_utc)

            recent_history = db.get_observations(device_id=device_id, limit=30, valid_only=True)
            trends = TrendAnalyzer.analyze_all_trends(recent_history)

            anomaly_detector.evaluate_observation(
                observation=sanitized_data,
                trends=trends,
                mq135_baseline_mv=current_baseline,
            )

            health_score_res = EnvironmentalScorer.calculate_environmental_health_score(
                observation=sanitized_data,
                mq135_baseline_mv=current_baseline,
            )

            db.insert_scores({
                "observation_id": obs_id,
                "calculated_at": now_utc,
                "health_score": health_score_res["health_score"],
                "health_grade": health_score_res["health_grade"],
                "comfort_index": health_score_res["comfort_index"],
                "comfort_status": health_score_res["comfort_status"],
                "data_coverage_pct": health_score_res["data_coverage_pct"],
                "components": health_score_res["components"],
                "calculation_reason": health_score_res["calculation_reason"],
            })

        return {
            "status": "accepted",
            "observation_id": obs_id,
            "received_at": now_utc,
            "flags": flags,
            "is_valid": is_valid,
            "health_score": health_score_res["health_score"] if health_score_res else None,
            "health_grade": health_score_res["health_grade"] if health_score_res else None,
        }

    # USB Serial Bridge Instance (Auto-connect to COM4 on startup)
    serial_bridge = SerialBridge(port="COM4", on_packet=process_and_persist_telemetry)
    app.serial_bridge = serial_bridge  # type: ignore[attr-defined]
    try:
        serial_bridge.start()
        logger.info("Auto-started USB Serial Bridge on COM4 for live hardware telemetry.")
    except Exception as e:
        logger.warning(f"Could not auto-start serial bridge on COM4: {e}")

    # Interactive Demo Streamer State
    demo_state = {
        "is_active": False,
        "event_mode": "normal",  # 'normal', 'gas_surge', 'temp_spike'
        "thread": None,
        "seq": 0,
    }

    def demo_worker():
        import random
        logger.info("Demo worker stream started.")
        target_dev = app.config.get("EXPECTED_DEVICE_ID", "esp32-sieis-01")
        while demo_state["is_active"]:
            demo_state["seq"] += 1
            seq = demo_state["seq"]
            mode = demo_state["event_mode"]

            temp = round(23.6 + random.uniform(-0.3, 0.4), 1)
            hum = round(51.8 + random.uniform(-0.6, 0.6), 1)
            mq = int(410 + random.uniform(-6, 8))
            light = int(580 + random.uniform(-20, 20))
            sound = int(175 + random.uniform(-15, 25))

            if mode == "gas_surge":
                mq = 780  # Surge > 1.5x baseline -> Trigger CRITICAL Gas Alert
            elif mode == "temp_spike":
                temp = 29.8  # Thermal breach > 27C -> Trigger WARNING Thermal Alert
                hum = 38.0

            packet = {
                "device_id": target_dev,
                "firmware_version": "1.0.0-demo",
                "sequence_number": seq,
                "uptime_ms": seq * 3000,
                "temperature_c": temp,
                "humidity_percent": hum,
                "light_raw": light,
                "light_label": "dim",
                "mq135_adc_mv": mq,
                "mq135_sensor_mv": int(mq * 1.5),
                "mq135_status": "ready",
                "sound_swing": sound,
                "sound_do": 0,
                "sensor_status": {"dht22": "ok", "ldr": "ok", "mq135": "ready", "sound": "ok"},
            }

            try:
                process_and_persist_telemetry(packet)
            except Exception as e:
                logger.error(f"Error in demo worker: {e}")

            time.sleep(3.0)

    # Helper: Check device staleness
    def check_staleness(latest_obs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not latest_obs or not latest_obs.get("received_at"):
            return {"is_connected": False, "is_stale": True, "seconds_since_last": None}
        try:
            recv_time = datetime.fromisoformat(latest_obs["received_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta_sec = max(0, int((now - recv_time).total_seconds()))
            stale = delta_sec > app.config["STALE_THRESHOLD_SECONDS"]
            return {
                "is_connected": not stale,
                "is_stale": stale,
                "seconds_since_last": delta_sec,
                "last_seen_at": latest_obs["received_at"],
            }
        except Exception:
            return {"is_connected": False, "is_stale": True, "seconds_since_last": None}

    # ==========================================
    # System & Health Endpoints
    # ==========================================
    @app.route("/health", methods=["GET"])
    def health_check():
        latest_obs = db.get_latest_observation()
        staleness = check_staleness(latest_obs)
        stats = db.get_system_stats()

        return jsonify({
            "status": "healthy",
            "service": "SIEIS Backend",
            "server_time_utc": datetime.now(timezone.utc).isoformat(),
            "database_status": "connected",
            "device_freshness": staleness,
            "total_observations": stats["total_observations"],
            "registered_devices": stats["registered_devices"],
            "serial_bridge_connected": serial_bridge.is_running,
            "demo_stream_active": demo_state["is_active"],
        }), 200

    @app.route("/api/hardware-status", methods=["GET"])
    def hardware_status():
        return jsonify({
            "active_hardware": [
                {
                    "sensor": "DHT22",
                    "interface": "GPIO 4 (Digital 1-Wire)",
                    "parameters": ["temperature_c", "humidity_percent"],
                    "units": ["°C", "%"],
                    "status": "active_physical_measurement",
                },
                {
                    "sensor": "Bare LDR Divider",
                    "interface": "GPIO 35 (ADC 12-bit, 10k divider)",
                    "parameters": ["light_raw", "light_label"],
                    "units": ["raw ADC (0-4095)", "dark/dim/bright"],
                    "status": "relative_brightness_indicator",
                },
                {
                    "sensor": "MQ-135 Gas Sensor",
                    "interface": "GPIO 34 (ADC 12-bit via 10k:20k divider)",
                    "parameters": ["mq135_adc_mv", "mq135_sensor_mv", "mq135_status"],
                    "units": ["mV", "mV", "status"],
                    "status": "relative_gas_response_rolling_baseline",
                },
                {
                    "sensor": "Sound Module (LM393)",
                    "interface": "AO GPIO 32, DO GPIO 26",
                    "parameters": ["sound_swing", "sound_do"],
                    "units": ["peak-to-peak ADC swing", "binary threshold"],
                    "status": "relative_acoustic_activity_indicator",
                },
            ],
            "unsupported_channels": [
                {
                    "sensor": "BME280",
                    "reason": "Dropped after Review 1; DHT22 in use",
                    "missing_parameters": ["pressure_hpa"],
                },
                {
                    "sensor": "ENS160",
                    "reason": "Not procured; MQ-135 used for relative baseline",
                    "missing_parameters": ["eco2_ppm", "tvoc_ppb", "standard_aqi"],
                },
                {
                    "sensor": "BH1750",
                    "reason": "Replaced by bare LDR voltage divider",
                    "missing_parameters": ["calibrated_lux"],
                },
            ],
        }), 200

    # ==========================================
    # Telemetry Ingestion Endpoint
    # ==========================================
    @app.route("/api/sensor", methods=["POST"])
    def ingest_sensor_data():
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400

        try:
            raw_payload = request.get_json(silent=True)
            if raw_payload is None:
                return jsonify({"error": "Malformed JSON payload"}), 400

            last_wifi_http_telemetry_time[0] = time.time()
            result = process_and_persist_telemetry(raw_payload)
            http_code = 200 if result.get("status") == "duplicate_ignored" else 201
            return jsonify(result), http_code

        except ValidationError as ve:
            logger.warning(f"Validation rejection: {ve.message}")
            return jsonify({"error": ve.message}), ve.status_code
        except Exception:
            logger.exception("Unexpected error processing telemetry")
            return jsonify({"error": "Internal server error processing sensor data"}), 500

    # ==========================================
    # Interactive Demo & Simulation Endpoints
    # ==========================================
    @app.route("/api/demo/start", methods=["POST"])
    def start_demo():
        """Starts live in-memory telemetry simulation stream."""
        if not demo_state["is_active"]:
            demo_state["is_active"] = True
            demo_state["event_mode"] = "normal"
            t = threading.Thread(target=demo_worker, daemon=True)
            demo_state["thread"] = t
            t.start()
        return jsonify({"status": "demo_started", "mode": demo_state["event_mode"]}), 200

    @app.route("/api/demo/stop", methods=["POST"])
    def stop_demo():
        """Stops live telemetry simulation stream."""
        demo_state["is_active"] = False
        return jsonify({"status": "demo_stopped"}), 200

    @app.route("/api/demo/event", methods=["POST"])
    def trigger_demo_event():
        """Sets simulated event scenario: 'gas_surge', 'temp_spike', or 'normal'."""
        data = request.get_json(silent=True) or {}
        event = data.get("event", "normal")
        if event in ("gas_surge", "temp_spike", "normal"):
            demo_state["event_mode"] = event
            if not demo_state["is_active"]:
                # Auto-start demo stream if not running
                demo_state["is_active"] = True
                t = threading.Thread(target=demo_worker, daemon=True)
                demo_state["thread"] = t
                t.start()
            return jsonify({"status": "event_applied", "mode": event}), 200
        return jsonify({"error": "Invalid event. Choose: gas_surge, temp_spike, normal"}), 400

    @app.route("/api/demo/status", methods=["GET"])
    def demo_status():
        return jsonify({
            "is_active": demo_state["is_active"],
            "event_mode": demo_state["event_mode"],
            "packets_sent": demo_state["seq"],
        }), 200

    # ==========================================
    # USB Serial Ingestion Endpoints
    # ==========================================
    @app.route("/api/serial/ports", methods=["GET"])
    def get_serial_ports():
        """Lists detected COM ports on the system."""
        ports = SerialBridge.list_ports()
        return jsonify({
            "ports": ports,
            "connected_port": serial_bridge.port if serial_bridge.is_running else None,
            "bridge_status": serial_bridge.get_status(),
        }), 200

    @app.route("/api/serial/connect", methods=["POST"])
    def connect_serial():
        """Connects background USB serial bridge to a COM port."""
        data = request.get_json(silent=True) or {}
        port = data.get("port", "COM4")
        serial_bridge.port = port
        success = serial_bridge.start()
        return jsonify({
            "status": "connected" if success else "failed",
            "port": port,
            "bridge_status": serial_bridge.get_status(),
        }), 200

    @app.route("/api/serial/disconnect", methods=["POST"])
    def disconnect_serial():
        """Disconnects USB serial bridge."""
        serial_bridge.stop()
        return jsonify({
            "status": "disconnected",
            "bridge_status": serial_bridge.get_status(),
        }), 200

    @app.route("/api/serial/reset", methods=["POST"])
    def reset_serial_esp32():
        """Sends a hardware reboot pulse to ESP32 over serial bridge."""
        success = serial_bridge.reset_esp32()
        return jsonify({
            "status": "reset_triggered" if success else "failed",
            "port": serial_bridge.port,
            "bridge_status": serial_bridge.get_status(),
        }), 200

    @app.route("/api/serial/reconnect", methods=["POST"])
    def reconnect_serial():
        """Restarts background USB serial bridge and resets ESP32."""
        data = request.get_json(silent=True) or {}
        port = data.get("port", serial_bridge.port or "COM4")
        success = serial_bridge.restart(port=port)
        if success:
            serial_bridge.reset_esp32()
        return jsonify({
            "status": "reconnected" if success else "failed",
            "port": port,
            "bridge_status": serial_bridge.get_status(),
        }), 200

    # ==========================================
    # Historical Data & Query Endpoints
    # ==========================================
    @app.route("/api/readings", methods=["GET"])
    def get_readings():
        limit_param = request.args.get("limit", str(app.config["DEFAULT_READINGS_LIMIT"]))
        try:
            limit = min(int(limit_param), app.config["MAX_READINGS_QUERY_LIMIT"])
            if limit <= 0:
                limit = app.config["DEFAULT_READINGS_LIMIT"]
        except ValueError:
            limit = app.config["DEFAULT_READINGS_LIMIT"]

        device_id = request.args.get("device_id")
        since = request.args.get("since")
        until = request.args.get("until")

        readings = db.get_observations(
            device_id=device_id, limit=limit, since=since, until=until, valid_only=False
        )

        return jsonify({
            "count": len(readings),
            "limit": limit,
            "readings": readings,
        }), 200

    def _extract_indoor_context(latest_obs: Optional[Dict[str, Any]], staleness: Dict[str, Any]) -> Dict[str, Any]:
        dev_id = latest_obs.get("device_id", app.config["EXPECTED_DEVICE_ID"]) if latest_obs else app.config["EXPECTED_DEVICE_ID"]
        baseline_mv = baseline_mgr.get_current_baseline(dev_id)
        is_ready = baseline_mgr.is_baseline_ready(dev_id)
        pin_mv = None
        if latest_obs:
            pin_mv = latest_obs.get("mq135_sensor_mv") or latest_obs.get("mq135_adc_mv")
        ratio = None
        if pin_mv is not None and baseline_mv and baseline_mv > 0:
            ratio = round(pin_mv / baseline_mv, 2)
        return {
            "temperature": latest_obs.get("temperature_c") if latest_obs else None,
            "humidity": latest_obs.get("humidity_percent") if latest_obs else None,
            "ldr_raw": latest_obs.get("light_raw") if latest_obs else None,
            "ldr_classification": latest_obs.get("light_label", "dark") if latest_obs else "dark",
            "mq135_pin_mv": pin_mv,
            "mq135_baseline_mv": baseline_mv,
            "mq135_baseline_ratio": ratio,
            "mq135_is_ready": is_ready,
            "sound_swing": latest_obs.get("sound_swing") if latest_obs else None,
            "sound_digital_trigger": latest_obs.get("sound_do", 0) if latest_obs else 0,
            "is_stale": staleness.get("is_stale", True),
            "received_at": latest_obs.get("received_at") if latest_obs else None,
        }

    @app.route("/api/stats", methods=["GET"])
    def get_stats():
        stats = db.get_system_stats()
        latest_obs = db.get_latest_observation()
        staleness = check_staleness(latest_obs)
        latest_score = db.get_latest_scores()
        dev_id = latest_obs["device_id"] if latest_obs else app.config["EXPECTED_DEVICE_ID"]
        current_baseline = baseline_mgr.get_current_baseline(dev_id)

        now_t = time.time()
        wifi_active = last_wifi_http_telemetry_time[0] is not None and (now_t - last_wifi_http_telemetry_time[0]) < 60
        outdoor_snap = get_outdoor_service().get_outdoor_data()

        usb_status = "connected" if serial_bridge.is_streaming else ("connected_silent" if serial_bridge.is_running else "disconnected")

        return jsonify({
            "stats": stats,
            "freshness": staleness,
            "latest_observation": latest_obs,
            "latest_score": latest_score,
            "mq135_baseline_mv": current_baseline,
            "demo_active": demo_state["is_active"],
            "serial_bridge_active": serial_bridge.is_running,
            "serial_bridge_streaming": serial_bridge.is_streaming,
            "serial_bridge_status": serial_bridge.get_status(),
            "subsystem_statuses": {
                "usb_bridge_status": usb_status,
                "wifi_http_telemetry_status": "active" if wifi_active else "standby",
                "backend_server_status": "healthy",
                "database_status": "healthy",
                "outdoor_api_status": outdoor_snap.get("freshness_status", "offline"),
            },
        }), 200

    @app.route("/api/alerts", methods=["GET"])
    def get_alerts():
        limit = min(int(request.args.get("limit", "50")), 100)
        device_id = request.args.get("device_id")
        active_alerts = db.get_active_alerts(device_id=device_id, limit=limit)
        return jsonify({"count": len(active_alerts), "alerts": active_alerts}), 200

    @app.route("/api/scores", methods=["GET"])
    def get_scores():
        latest = db.get_latest_scores()
        return jsonify({"latest_scores": latest}), 200

    @app.route("/api/forecast", methods=["GET"])
    def get_forecast():
        latest_obs = db.get_latest_observation()
        dev_id = latest_obs["device_id"] if latest_obs else app.config["EXPECTED_DEVICE_ID"]
        history = db.get_observations(device_id=dev_id, limit=30, valid_only=True)
        forecasts = TrendForecaster.generate_all_forecasts(history)
        return jsonify(forecasts), 200

    # ==========================================
    # Master Specification Intelligence Endpoints
    # ==========================================
    @app.route("/api/comfort-index", methods=["GET"])
    def get_comfort_index():
        """Returns authoritative Room Comfort Index (RCI, 0-100) with full component breakdown."""
        latest_obs = db.get_latest_observation()
        staleness = check_staleness(latest_obs)
        indoor = _extract_indoor_context(latest_obs, staleness)

        rci_res = calculate_rci(
            temp_c=indoor["temperature"],
            rh_pct=indoor["humidity"],
            mq135_pin_mv=indoor["mq135_pin_mv"],
            mq135_baseline_mv=indoor["mq135_baseline_mv"],
            mq135_is_ready=indoor["mq135_is_ready"],
            ldr_raw=indoor["ldr_raw"],
            sound_swing=indoor["sound_swing"],
            sound_do=indoor["sound_digital_trigger"],
            telemetry_age_seconds=staleness.get("seconds_since_last"),
            is_stale=staleness.get("is_stale", False),
        )
        return jsonify(rci_res), 200

    @app.route("/api/indoor-estimates", methods=["GET"])
    def get_indoor_estimates():
        """Returns experimental heuristic proxy estimates for indoor PM2.5 and CO2."""
        latest_obs = db.get_latest_observation()
        staleness = check_staleness(latest_obs)
        indoor = _extract_indoor_context(latest_obs, staleness)
        outdoor_res = get_outdoor_service().get_outdoor_data()

        pm25_res = estimate_indoor_pm25(
            indoor_temp_c=indoor["temperature"],
            indoor_rh_pct=indoor["humidity"],
            mq135_pin_mv=indoor["mq135_pin_mv"],
            mq135_baseline_mv=indoor["mq135_baseline_mv"],
            mq135_is_ready=indoor["mq135_is_ready"],
            outdoor_pm25=outdoor_res.get("pm25"),
            outdoor_aqi=outdoor_res.get("aqi"),
            sound_swing=indoor["sound_swing"],
            ldr_raw=indoor["ldr_raw"],
        )

        co2_res = estimate_indoor_co2(
            mq135_pin_mv=indoor["mq135_pin_mv"],
            mq135_baseline_mv=indoor["mq135_baseline_mv"],
            mq135_is_ready=indoor["mq135_is_ready"],
            indoor_temp_c=indoor["temperature"],
            indoor_rh_pct=indoor["humidity"],
            sound_swing=indoor["sound_swing"],
        )

        return jsonify({
            "status": "ok",
            "pm25": pm25_res,
            "co2": co2_res,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }), 200

    @app.route("/api/outdoor", methods=["GET"])
    def get_outdoor():
        """Returns live outdoor weather and AQI with server-side caching, stale fallback, and strict no-cache headers."""
        force = request.args.get("refresh", "false").lower() in ("true", "1")
        outdoor_res = get_outdoor_service().get_outdoor_data(force_refresh=force)
        resp = make_response(jsonify(outdoor_res), 200)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @app.route("/api/comparison", methods=["GET"])
    def get_comparison():
        """Returns indoor-vs-outdoor comparisons, psychrometrics, and ventilation favourability."""
        latest_obs = db.get_latest_observation()
        staleness = check_staleness(latest_obs)
        indoor = _extract_indoor_context(latest_obs, staleness)
        outdoor_res = get_outdoor_service().get_outdoor_data()

        estimates = {
            "pm25": estimate_indoor_pm25(
                indoor_temp_c=indoor["temperature"],
                indoor_rh_pct=indoor["humidity"],
                mq135_pin_mv=indoor["mq135_pin_mv"],
                mq135_baseline_mv=indoor["mq135_baseline_mv"],
                mq135_is_ready=indoor["mq135_is_ready"],
                outdoor_pm25=outdoor_res.get("pm25"),
                outdoor_aqi=outdoor_res.get("aqi"),
            ),
            "co2": estimate_indoor_co2(
                mq135_pin_mv=indoor["mq135_pin_mv"],
                mq135_baseline_mv=indoor["mq135_baseline_mv"],
                mq135_is_ready=indoor["mq135_is_ready"],
                indoor_temp_c=indoor["temperature"],
                indoor_rh_pct=indoor["humidity"],
            ),
        }

        comp = compare_indoor_and_outdoor(indoor, outdoor_res, estimates)
        return jsonify(comp), 200

    @app.route("/api/recommendations", methods=["GET"])
    def get_recommendations():
        """Returns prioritized, context-aware actionable recommendations (Rules A-I)."""
        latest_obs = db.get_latest_observation()
        staleness = check_staleness(latest_obs)
        indoor = _extract_indoor_context(latest_obs, staleness)
        outdoor_res = get_outdoor_service().get_outdoor_data()

        estimates = {
            "pm25": estimate_indoor_pm25(
                indoor_temp_c=indoor["temperature"],
                indoor_rh_pct=indoor["humidity"],
                mq135_pin_mv=indoor["mq135_pin_mv"],
                mq135_baseline_mv=indoor["mq135_baseline_mv"],
                mq135_is_ready=indoor["mq135_is_ready"],
                outdoor_pm25=outdoor_res.get("pm25"),
                outdoor_aqi=outdoor_res.get("aqi"),
            ),
            "co2": estimate_indoor_co2(
                mq135_pin_mv=indoor["mq135_pin_mv"],
                mq135_baseline_mv=indoor["mq135_baseline_mv"],
                mq135_is_ready=indoor["mq135_is_ready"],
                indoor_temp_c=indoor["temperature"],
                indoor_rh_pct=indoor["humidity"],
            ),
        }

        comp = compare_indoor_and_outdoor(indoor, outdoor_res, estimates)

        rci_res = calculate_rci(
            temp_c=indoor["temperature"],
            rh_pct=indoor["humidity"],
            mq135_pin_mv=indoor["mq135_pin_mv"],
            mq135_baseline_mv=indoor["mq135_baseline_mv"],
            mq135_is_ready=indoor["mq135_is_ready"],
            ldr_raw=indoor["ldr_raw"],
            sound_swing=indoor["sound_swing"],
            sound_do=indoor["sound_digital_trigger"],
            telemetry_age_seconds=staleness.get("seconds_since_last"),
            is_stale=staleness.get("is_stale", False),
        )

        recs = evaluate_context_recs(
            indoor_telemetry=indoor,
            outdoor_data=outdoor_res,
            comparison_data=comp,
            indoor_estimates=estimates,
            rci_result=rci_res,
        )

        return jsonify({
            "count": len(recs),
            "recommendations": recs,
            "highest_priority": recs[0] if recs else None,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }), 200

    @app.route("/api/diagnostics", methods=["GET"])
    def get_diagnostics():
        """Returns 9-subsystem health diagnostics matrix."""
        latest_obs = db.get_latest_observation()
        staleness = check_staleness(latest_obs)
        indoor = _extract_indoor_context(latest_obs, staleness)
        outdoor_res = get_outdoor_service().get_outdoor_data()

        rci_res = calculate_rci(
            temp_c=indoor["temperature"],
            rh_pct=indoor["humidity"],
            mq135_pin_mv=indoor["mq135_pin_mv"],
            mq135_baseline_mv=indoor["mq135_baseline_mv"],
            mq135_is_ready=indoor["mq135_is_ready"],
            ldr_raw=indoor["ldr_raw"],
            sound_swing=indoor["sound_swing"],
            sound_do=indoor["sound_digital_trigger"],
            telemetry_age_seconds=staleness.get("seconds_since_last"),
            is_stale=staleness.get("is_stale", False),
        )

        now_t = time.time()
        wifi_status = "active" if (last_wifi_http_telemetry_time[0] and (now_t - last_wifi_http_telemetry_time[0]) < 60) else "standby"
        usb_status = "connected" if serial_bridge.is_streaming else ("connected_silent" if serial_bridge.is_running else "disconnected")

        diag = evaluate_diagnostics_matrix(
            indoor_telemetry=indoor,
            outdoor_data=outdoor_res,
            rci_result=rci_res,
            usb_status=usb_status,
            wifi_status=wifi_status,
        )
        return jsonify(diag), 200

    @app.route("/api/config/location", methods=["GET", "POST"])
    def config_location():
        """Get or update geographic location coordinates for outdoor weather/AQI."""
        service = get_outdoor_service()
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            lat = data.get("latitude")
            lon = data.get("longitude")
            label = data.get("location_label")
            if lat is None or lon is None:
                return jsonify({"error": "latitude and longitude required"}), 400
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except ValueError:
                return jsonify({"error": "Invalid numeric coordinates"}), 400
            service.update_location(lat_f, lon_f, label)
            return jsonify({
                "status": "updated",
                "latitude": lat_f,
                "longitude": lon_f,
                "location_label": service.location_label,
            }), 200

        return jsonify({
            "latitude": service.latitude,
            "longitude": service.longitude,
            "location_label": service.location_label,
            "cache_ttl_seconds": service.cache_ttl_seconds,
        }), 200

    # ==========================================
    # Comprehensive Engineering Report Routes
    # ==========================================
    @app.route("/report", methods=["GET"])
    def view_report():
        """Serve the standalone comprehensive engineering report with KaTeX and print styling."""
        report_path = Path(__file__).resolve().parent.parent / "SIEIS_Comprehensive_Project_Report.html"
        if report_path.exists():
            return report_path.read_text(encoding="utf-8")
        return "Report HTML not found. Please run generate_html_report.py first.", 404

    @app.route("/report/markdown", methods=["GET"])
    @app.route("/download/report.md", methods=["GET"])
    def download_report_markdown():
        """Download the comprehensive engineering report in Markdown format."""
        md_path = Path(__file__).resolve().parent.parent / "SIEIS_Comprehensive_Project_Report.md"
        if md_path.exists():
            return send_file(md_path, as_attachment=True, download_name="SIEIS_Comprehensive_Project_Report.md")
        return "Report Markdown not found.", 404

    @app.route("/report/html/download", methods=["GET"])
    @app.route("/download/report.html", methods=["GET"])
    def download_report_html():
        """Download the standalone comprehensive engineering report HTML."""
        html_path = Path(__file__).resolve().parent.parent / "SIEIS_Comprehensive_Project_Report.html"
        if html_path.exists():
            return send_file(html_path, as_attachment=True, download_name="SIEIS_Comprehensive_Project_Report.html")
        return "Report HTML not found.", 404

    @app.route("/rci", methods=["GET"])
    @app.route("/report/rci", methods=["GET"])
    def view_rci_spec():
        """Serve the standalone Room Comfort Index (RCI) mathematical specification document."""
        rci_path = Path(__file__).resolve().parent.parent / "SIEIS_Room_Comfort_Index_Specification.html"
        if rci_path.exists():
            return rci_path.read_text(encoding="utf-8")
        return "RCI specification HTML not found. Please run generate_rci_html.py first.", 404

    @app.route("/download/rci.md", methods=["GET"])
    def download_rci_markdown():
        """Download the Room Comfort Index (RCI) specification in Markdown format."""
        md_path = Path(__file__).resolve().parent.parent / "SIEIS_Room_Comfort_Index_Specification.md"
        if md_path.exists():
            return send_file(md_path, as_attachment=True, download_name="SIEIS_Room_Comfort_Index_Specification.md")
        return "RCI Markdown specification not found.", 404

    @app.route("/download/rci.html", methods=["GET"])
    def download_rci_html():
        """Download the Room Comfort Index (RCI) standalone HTML specification."""
        html_path = Path(__file__).resolve().parent.parent / "SIEIS_Room_Comfort_Index_Specification.html"
        if html_path.exists():
            return send_file(html_path, as_attachment=True, download_name="SIEIS_Room_Comfort_Index_Specification.html")
        return "RCI HTML specification not found.", 404

    # ==========================================
    # Web Dashboard View
    # ==========================================
    @app.route("/", methods=["GET"])
    def dashboard():
        return render_template("index.html")

    return app


if __name__ == "__main__":
    app_instance = create_app(Config)
    logger.info(f"Starting SIEIS Server on {Config.HOST}:{Config.PORT} (Debug={Config.DEBUG})")
    app_instance.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
