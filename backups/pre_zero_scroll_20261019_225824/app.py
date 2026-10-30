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
from typing import Any, Dict, Optional

from flask import Flask, jsonify, render_template, request

from config import Config
from database import Database
from intelligence.anomaly import AnomalyDetector
from intelligence.baseline import MQ135BaselineManager
from intelligence.decision import DecisionEngine
from intelligence.forecasting import TrendForecaster
from intelligence.scoring import EnvironmentalScorer
from intelligence.trends import TrendAnalyzer
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
        logger.info("Demo worker stream started.")
        while demo_state["is_active"]:
            demo_state["seq"] += 1
            seq = demo_state["seq"]
            mode = demo_state["event_mode"]

            temp = 23.2
            hum = 50.0
            mq = 450
            light = 650
            sound = 200

            if mode == "gas_surge":
                mq = 780  # Surge > 1.5x baseline -> Trigger CRITICAL Gas Alert
            elif mode == "temp_spike":
                temp = 29.8  # Thermal breach > 27C -> Trigger WARNING Thermal Alert
                hum = 38.0

            packet = {
                "device_id": "esp32-demo-stream",
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
        return jsonify({"ports": ports, "connected_port": serial_bridge.port if serial_bridge.is_running else None}), 200

    @app.route("/api/serial/connect", methods=["POST"])
    def connect_serial():
        """Connects background USB serial bridge to a COM port."""
        data = request.get_json(silent=True) or {}
        port = data.get("port", "COM4")
        serial_bridge.port = port
        success = serial_bridge.start()
        return jsonify({"status": "connected" if success else "failed", "port": port}), 200

    @app.route("/api/serial/disconnect", methods=["POST"])
    def disconnect_serial():
        """Disconnects USB serial bridge."""
        serial_bridge.stop()
        return jsonify({"status": "disconnected"}), 200

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

    @app.route("/api/stats", methods=["GET"])
    def get_stats():
        stats = db.get_system_stats()
        latest_obs = db.get_latest_observation()
        staleness = check_staleness(latest_obs)
        latest_score = db.get_latest_scores()
        dev_id = latest_obs["device_id"] if latest_obs else app.config["EXPECTED_DEVICE_ID"]
        current_baseline = baseline_mgr.get_current_baseline(dev_id)

        return jsonify({
            "stats": stats,
            "freshness": staleness,
            "latest_observation": latest_obs,
            "latest_score": latest_score,
            "mq135_baseline_mv": current_baseline,
            "demo_active": demo_state["is_active"],
            "serial_bridge_active": serial_bridge.is_running,
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

    @app.route("/api/recommendations", methods=["GET"])
    def get_recommendations():
        latest_obs = db.get_latest_observation()
        staleness = check_staleness(latest_obs)
        scores = db.get_latest_scores()
        active_alerts = db.get_active_alerts(limit=10)

        history = db.get_observations(limit=25, valid_only=True)
        trends = TrendAnalyzer.analyze_all_trends(history)
        forecasts = TrendForecaster.generate_all_forecasts(history)

        recs = DecisionEngine.evaluate_recommendations(
            latest_observation=latest_obs,
            scores=scores,
            trends=trends,
            forecasts=forecasts,
            active_alerts=active_alerts,
            is_stale=staleness["is_stale"],
        )
        return jsonify({"count": len(recs), "recommendations": recs}), 200

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
