"""SIEIS (Smart Indoor Environmental Intelligence System) - Recommendation & Diagnostic Engine.

Executes deterministic rules (A through I) based on combined indoor telemetry,
outdoor atmospheric context, and system health status.
Implements explicit handling for intermediate US AQI (76-100) and priority sorting:
critical > warning > advisory > info.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional

from config import Config


SEVERITY_ORDER = {
    "critical": 0,
    "warning": 1,
    "advisory": 2,
    "info": 3,
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_rec_id(rule_id: str, key_val: str) -> str:
    h = hashlib.md5(f"{rule_id}:{key_val}".encode("utf-8")).hexdigest()[:8]
    return f"rec_{rule_id}_{h}"


def evaluate_recommendations(
    indoor_telemetry: Dict[str, Any],
    outdoor_data: Dict[str, Any],
    comparison_data: Dict[str, Any],
    indoor_estimates: Optional[Dict[str, Any]] = None,
    rci_result: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Evaluate context-aware recommendation rules A through I.

    Returns a prioritized list of active recommendation objects compliant with Section 12.
    """
    recs: List[Dict[str, Any]] = []
    now_str = _iso_now()

    # Extract indoor features
    t_in = indoor_telemetry.get("temperature")
    rh_in = indoor_telemetry.get("humidity")
    ldr_raw = indoor_telemetry.get("ldr_raw")
    ldr_class = indoor_telemetry.get("ldr_classification")
    sound_swing = indoor_telemetry.get("sound_swing")
    sound_do = indoor_telemetry.get("sound_digital_trigger", 0)
    mq135_mv = indoor_telemetry.get("mq135_pin_mv")
    mq135_ratio = indoor_telemetry.get("mq135_baseline_ratio")
    mq135_ready = indoor_telemetry.get("mq135_is_ready", False)
    is_stale = indoor_telemetry.get("is_stale", False)

    # Compute ratio fallback if needed
    if mq135_ratio is None and mq135_mv is not None:
        base_mv = indoor_telemetry.get("mq135_baseline_mv")
        if base_mv and base_mv > 0:
            mq135_ratio = round(mq135_mv / base_mv, 2)

    # Extract outdoor features
    t_out = outdoor_data.get("temperature_c")
    rh_out = outdoor_data.get("relative_humidity_pct")
    aqi_out = outdoor_data.get("aqi")
    outdoor_status = outdoor_data.get("status", "unavailable")
    is_outdoor_stale = outdoor_data.get("is_stale", False) or outdoor_data.get("freshness_status") in ("stale", "stale_cached", "stale_observation", "offline", "unavailable")

    # Extract psychrometrics
    psych = comparison_data.get("humidity", {}).get("psychrometrics", {})
    ah_in = psych.get("indoor_absolute_humidity_gm3")
    ah_out = psych.get("outdoor_absolute_humidity_gm3")

    # Extract estimates
    pm25_val = None
    co2_val = None
    if indoor_estimates:
        pm25_val = indoor_estimates.get("pm25", {}).get("value")
        co2_val = indoor_estimates.get("co2", {}).get("value")

    # -------------------------------------------------------------
    # RULE A: Hot Room, Cooler Outdoors, Favourable Outdoor AQI
    # -------------------------------------------------------------
    if (
        not is_outdoor_stale
        and t_in is not None
        and t_out is not None
        and aqi_out is not None
        and t_in > 24.0
        and (t_in - t_out) >= 1.0
        and aqi_out <= Config.OUTDOOR_AQI_FAVOURABLE_MAX  # <= 75
    ):
        delta = round(t_in - t_out, 1)
        recs.append({
            "id": _gen_rec_id("rule_a", f"{t_in}_{t_out}"),
            "rule_id": "rule_a",
            "category": "thermal",
            "severity": "advisory",
            "title": "Natural Ventilation for Thermal Relief",
            "what_is_wrong": f"Indoor room is warm ({t_in:.1f}°C > 24.0°C) while outdoor air is cooler and clean.",
            "target_metric": "Indoor Temperature (Optimal: 21.0 - 24.0°C)",
            "current_value_summary": f"Indoor: {t_in:.1f}°C vs Outdoor: {t_out:.1f}°C (Delta: -{delta}°C)",
            "recommended_action": "Open windows or enable fresh-air intake to naturally cool the room with clean outdoor air.",
            "explanation": f"Outdoor air is {delta}°C cooler and outdoor air quality is favourable (US AQI {aqi_out:.0f} <= 75).",
            "indoor_evidence": {"indoor_temp_c": t_in, "target_max_c": 24.0},
            "outdoor_evidence": {"outdoor_temp_c": t_out, "outdoor_aqi": aqi_out},
            "measurement_limitations": "Room thermal cooling rate depends on airflow velocity and building thermal mass.",
            "created_at": now_str,
            "status": "active",
        })

    # -------------------------------------------------------------
    # Intermediate AQI (76 - 100) variant for Hot Room / Cooler Outdoors
    # -------------------------------------------------------------
    elif (
        not is_outdoor_stale
        and t_in is not None
        and t_out is not None
        and aqi_out is not None
        and t_in > 24.0
        and (t_in - t_out) >= 1.0
        and (Config.OUTDOOR_AQI_FAVOURABLE_MAX < aqi_out <= Config.OUTDOOR_AQI_UNFAVOURABLE_MIN)
    ):
        delta = round(t_in - t_out, 1)
        recs.append({
            "id": _gen_rec_id("rule_a_intermediate", f"{t_in}_{t_out}"),
            "rule_id": "rule_a",
            "category": "thermal",
            "severity": "advisory",
            "title": "Moderate Ventilation with Caution",
            "what_is_wrong": f"Indoor room is warm ({t_in:.1f}°C), but outdoor air quality is moderate (US AQI {aqi_out:.0f}).",
            "target_metric": "Indoor Temperature (Optimal: 21.0 - 24.0°C)",
            "current_value_summary": f"Indoor: {t_in:.1f}°C vs Outdoor: {t_out:.1f}°C (Outdoor US AQI: {aqi_out:.0f})",
            "recommended_action": "Ventilate briefly or use partial window openings for cooling, avoiding prolonged outdoor exposure if sensitive to particulate matter.",
            "explanation": f"Outdoor temperature is {delta}°C cooler, but outdoor AQI is intermediate (76-100).",
            "indoor_evidence": {"indoor_temp_c": t_in},
            "outdoor_evidence": {"outdoor_temp_c": t_out, "outdoor_aqi": aqi_out},
            "measurement_limitations": "Intermediate outdoor AQI can cause irritation in sensitive individuals.",
            "created_at": now_str,
            "status": "active",
        })

    # -------------------------------------------------------------
    # RULE B: Elevated MQ-135 Signal, Unfavourable Outdoor AQI
    # -------------------------------------------------------------
    if (
        mq135_ready
        and mq135_ratio is not None
        and mq135_ratio >= Config.MQ135_ELEVATION_RATIO_WARN  # >= 1.25
        and aqi_out is not None
        and aqi_out > Config.OUTDOOR_AQI_UNFAVOURABLE_MIN  # > 100
    ):
        recs.append({
            "id": _gen_rec_id("rule_b", f"{mq135_ratio}_{aqi_out}"),
            "rule_id": "rule_b",
            "category": "air_quality",
            "severity": "warning",
            "title": "Elevated Gas Signal with Unfavourable Outdoor Air",
            "what_is_wrong": "Indoor gas response is elevated above baseline, but outdoor air quality is polluted.",
            "target_metric": "MQ-135 Baseline Ratio (Target: <= 1.05)",
            "current_value_summary": f"MQ-135 Ratio: {mq135_ratio:.2f}x vs Outdoor US AQI: {aqi_out:.0f}",
            "recommended_action": "Keep windows closed against outdoor pollution. Inspect for indoor odour or chemical sources, and activate internal recirculating filtration or HEPA purifier.",
            "explanation": "Opening windows would admit hazardous outdoor pollutants into the room.",
            "indoor_evidence": {"mq135_ratio": mq135_ratio, "mq135_pin_mv": mq135_mv},
            "outdoor_evidence": {"outdoor_aqi": aqi_out, "outdoor_scale": "us_aqi"},
            "measurement_limitations": "MQ-135 is a broad-band non-specific metal-oxide sensor; elevation indicates general oxidisable gases, not individual compound identity.",
            "created_at": now_str,
            "status": "active",
        })

    # -------------------------------------------------------------
    # RULE C: Elevated MQ-135 Signal, Favourable Outdoor AQI
    # -------------------------------------------------------------
    if (
        mq135_ready
        and mq135_ratio is not None
        and mq135_ratio >= Config.MQ135_ELEVATION_RATIO_WARN  # >= 1.25
        and aqi_out is not None
        and aqi_out <= Config.OUTDOOR_AQI_FAVOURABLE_MAX  # <= 75
    ):
        recs.append({
            "id": _gen_rec_id("rule_c", f"{mq135_ratio}_{aqi_out}"),
            "rule_id": "rule_c",
            "category": "air_quality",
            "severity": "warning",
            "title": "Purge Indoor Stale Air via Natural Ventilation",
            "what_is_wrong": "Indoor gas/odour levels are elevated above baseline while outdoor air is clean.",
            "target_metric": "MQ-135 Baseline Ratio (Target: <= 1.05)",
            "current_value_summary": f"MQ-135 Ratio: {mq135_ratio:.2f}x (Clean outdoor AQI: {aqi_out:.0f})",
            "recommended_action": "Open windows to flush the room with fresh outdoor air. Observe whether the MQ-135 signal recovers toward baseline.",
            "explanation": "Outdoor air quality is clean and suitable for purging indoor volatile contaminants.",
            "indoor_evidence": {"mq135_ratio": mq135_ratio, "mq135_pin_mv": mq135_mv},
            "outdoor_evidence": {"outdoor_aqi": aqi_out},
            "measurement_limitations": "Verify sensor signal decrease after 10-15 minutes of air flushing.",
            "created_at": now_str,
            "status": "active",
        })

    # -------------------------------------------------------------
    # RULE D: Hot Room and Hotter Outdoor Air
    # -------------------------------------------------------------
    if (
        t_in is not None
        and t_out is not None
        and t_in > 24.0
        and t_out >= t_in
    ):
        recs.append({
            "id": _gen_rec_id("rule_d", f"{t_in}_{t_out}"),
            "rule_id": "rule_d",
            "category": "thermal",
            "severity": "warning",
            "title": "Prevent Solar Heat Ingress",
            "what_is_wrong": f"Indoor room is hot ({t_in:.1f}°C) and outdoor air is even hotter ({t_out:.1f}°C).",
            "target_metric": "Indoor Temperature (Optimal: 21.0 - 24.0°C)",
            "current_value_summary": f"Indoor: {t_in:.1f}°C vs Outdoor: {t_out:.1f}°C",
            "recommended_action": "Do NOT open windows. Draw curtains/blinds, power down unnecessary internal heat-generating appliances, and turn on active mechanical air conditioning.",
            "explanation": "Natural ventilation would introduce thermal energy from the hotter outdoor air into the room.",
            "indoor_evidence": {"indoor_temp_c": t_in},
            "outdoor_evidence": {"outdoor_temp_c": t_out},
            "measurement_limitations": "Internal heat generation from lights/laptops can elevate indoor temperatures without external heat transfer.",
            "created_at": now_str,
            "status": "active",
        })

    # -------------------------------------------------------------
    # RULE E: High or Low Indoor Humidity
    # -------------------------------------------------------------
    if rh_in is not None:
        if rh_in > 60.0:
            # Check absolute humidity if available
            can_dehumidify_outdoors = False
            if ah_in is not None and ah_out is not None and (ah_in - ah_out) >= 1.5 and aqi_out and aqi_out <= 100:
                can_dehumidify_outdoors = True

            action = (
                "Open windows for cross-ventilation; outdoor air has lower absolute moisture content."
                if can_dehumidify_outdoors
                else "Engage AC Dry Mode or run a dedicated dehumidifier to suppress mould-risk conditions."
            )
            recs.append({
                "id": _gen_rec_id("rule_e_high", str(rh_in)),
                "rule_id": "rule_e",
                "category": "humidity",
                "severity": "warning" if rh_in > 70.0 else "advisory",
                "title": "Elevated Indoor Humidity",
                "what_is_wrong": f"Indoor relative humidity ({rh_in:.1f}%) exceeds the 60.0% comfort and fungal threshold.",
                "target_metric": "Relative Humidity (Optimal: 40.0 - 60.0%)",
                "current_value_summary": f"Indoor RH: {rh_in:.1f}% (Optimal: 40-60%)",
                "recommended_action": action,
                "explanation": "Sustained high indoor humidity promotes dust mite proliferation and mould growth.",
                "indoor_evidence": {"indoor_rh_pct": rh_in, "indoor_ah_gm3": ah_in},
                "outdoor_evidence": {"outdoor_rh_pct": rh_out, "outdoor_ah_gm3": ah_out},
                "measurement_limitations": "DHT22 RH accuracy is nominally +/- 2-5% across commercial operating spans.",
                "created_at": now_str,
                "status": "active",
            })
        elif rh_in < 40.0:
            recs.append({
                "id": _gen_rec_id("rule_e_low", str(rh_in)),
                "rule_id": "rule_e",
                "category": "humidity",
                "severity": "advisory",
                "title": "Dry Indoor Air",
                "what_is_wrong": f"Indoor relative humidity ({rh_in:.1f}%) is below the 40.0% minimum threshold.",
                "target_metric": "Relative Humidity (Optimal: 40.0 - 60.0%)",
                "current_value_summary": f"Indoor RH: {rh_in:.1f}% (Optimal: 40-60%)",
                "recommended_action": "Use an ultrasonic humidifier or place indoor water trays to reduce respiratory discomfort and static electrical build-up.",
                "explanation": "Dry indoor air dehydrates mucous membranes and increases susceptibility to airborne viral transmission.",
                "indoor_evidence": {"indoor_rh_pct": rh_in},
                "outdoor_evidence": {"outdoor_rh_pct": rh_out},
                "measurement_limitations": "Ensure humidifier reservoir is kept hygienic.",
                "created_at": now_str,
                "status": "active",
            })

    # -------------------------------------------------------------
    # RULE F: Dark Room
    # -------------------------------------------------------------
    if ldr_raw is not None and ldr_raw < Config.LDR_DARK_THRESHOLD:
        recs.append({
            "id": _gen_rec_id("rule_f", str(ldr_raw)),
            "rule_id": "rule_f",
            "category": "lighting",
            "severity": "info",
            "title": "Insufficient Ambient Lighting",
            "what_is_wrong": f"LDR raw ADC count ({ldr_raw}) indicates the room is dark (< 250 count threshold).",
            "target_metric": "LDR Ambient Light (Adequate: >= 250 ADC count)",
            "current_value_summary": f"LDR Count: {ldr_raw} (Classification: Dark)",
            "recommended_action": "Switch on task illumination or open window blinds to reduce visual fatigue during active occupancy.",
            "explanation": "Dim environments cause eye strain during study, coding, or reading activities.",
            "indoor_evidence": {"ldr_raw": ldr_raw, "threshold": Config.LDR_DARK_THRESHOLD},
            "outdoor_evidence": {},
            "measurement_limitations": "LDR provides qualitative relative brightness (0-4095), not calibrated Lux (lm/m²).",
            "created_at": now_str,
            "status": "active",
        })

    # -------------------------------------------------------------
    # RULE G: Elevated Sound Activity
    # -------------------------------------------------------------
    if sound_swing is not None and (sound_swing >= 1200 or sound_do == 1):
        recs.append({
            "id": _gen_rec_id("rule_g", f"{sound_swing}_{sound_do}"),
            "rule_id": "rule_g",
            "category": "acoustics",
            "severity": "advisory",
            "title": "Elevated Acoustic Disturbance",
            "what_is_wrong": f"Microphone detected high peak-to-peak sound swing ({sound_swing}) or digital trigger active.",
            "target_metric": "Sound Swing (Quiet: < 400 count)",
            "current_value_summary": f"Sound Swing: {sound_swing} | Digital Trigger: {sound_do}",
            "recommended_action": "Close room doors to isolate corridor noise, lower media volume, or inspect for vibrating machinery/appliances.",
            "explanation": "Persistent acoustic disruption hinders concentration and cognitive performance.",
            "indoor_evidence": {"sound_swing": sound_swing, "digital_pin": sound_do},
            "outdoor_evidence": {},
            "measurement_limitations": "LM393 module provides relative sound swing; this is not a calibrated Class 1/2 dB(A) sound level meter.",
            "created_at": now_str,
            "status": "active",
        })

    # -------------------------------------------------------------
    # RULE H: Elevated Experimental Pollutant Estimate
    # -------------------------------------------------------------
    if pm25_val is not None and pm25_val > 55.0:
        recs.append({
            "id": _gen_rec_id("rule_h_pm25", str(pm25_val)),
            "rule_id": "rule_h",
            "category": "air_quality",
            "severity": "advisory",
            "title": "Model Advisory: Elevated Experimental PM2.5 Proxy",
            "what_is_wrong": f"Experimental heuristic PM2.5 proxy indicates elevated particulate concentration (~{pm25_val:.0f} µg/m³).",
            "target_metric": "Experimental PM2.5 Proxy (Nominal: < 35.0 µg/m³)",
            "current_value_summary": f"Proxy Estimate: {pm25_val:.1f} µg/m³ [EXPERIMENTAL]",
            "recommended_action": "Verify if indoor dust, incense, or cooking is present. Consider running a HEPA air purifier.",
            "explanation": "Calculated by heuristic estimation model using gas excursion and ambient humidity factors.",
            "indoor_evidence": {"pm25_estimate_ugm3": pm25_val},
            "outdoor_evidence": {"outdoor_pm25": outdoor_data.get("pm25")},
            "measurement_limitations": "EXPERIMENTAL PROXY ONLY. Uncalibrated mathematical estimate; not a validated optical counter reading.",
            "created_at": now_str,
            "status": "active",
        })

    if co2_val is not None and co2_val > 1200:
        recs.append({
            "id": _gen_rec_id("rule_h_co2", str(co2_val)),
            "rule_id": "rule_h",
            "category": "air_quality",
            "severity": "advisory",
            "title": "Model Advisory: Elevated Experimental CO2 Proxy",
            "what_is_wrong": f"Experimental heuristic CO2 proxy indicates elevated metabolic accumulation (~{co2_val} ppm).",
            "target_metric": "Experimental CO2 Proxy (Target: < 1000 ppm)",
            "current_value_summary": f"Proxy Estimate: {co2_val} ppm [EXPERIMENTAL]",
            "recommended_action": "Increase room ventilation rate if outdoor conditions allow, or reduce occupant crowding.",
            "explanation": "Estimated by non-linear heuristic projection based on MQ-135 clean air baseline elevation.",
            "indoor_evidence": {"co2_estimate_ppm": co2_val},
            "outdoor_evidence": {},
            "measurement_limitations": "EXPERIMENTAL PROXY ONLY. Uses metal-oxide MQ-135; not a non-dispersive infrared (NDIR) optical measurement.",
            "created_at": now_str,
            "status": "active",
        })

    # -------------------------------------------------------------
    # RULE I: Sensor, Calibration and Data-Quality Diagnostics
    # -------------------------------------------------------------
    if is_stale:
        recs.append({
            "id": _gen_rec_id("rule_i_stale", "stale_telemetry"),
            "rule_id": "rule_i",
            "category": "system_diagnostics",
            "severity": "warning",
            "title": "Stale Sensor Telemetry",
            "what_is_wrong": "Telemetry data from ESP32 is older than freshness threshold (> 30s).",
            "target_metric": "Telemetry Freshness (< 30 seconds)",
            "current_value_summary": "Telemetry status: STALE / OFFLINE",
            "recommended_action": "Check USB Serial Bridge (COM4) or verify ESP32 Wi-Fi connectivity and power supply.",
            "explanation": "Real-time intelligence requires active periodic telemetry packets.",
            "indoor_evidence": {"is_stale": True},
            "outdoor_evidence": {},
            "measurement_limitations": "Automation recommendations will be suspended or marked provisional when data is stale.",
            "created_at": now_str,
            "status": "active",
        })

    if not mq135_ready:
        recs.append({
            "id": _gen_rec_id("rule_i_mq135_warmup", "warmup"),
            "rule_id": "rule_i",
            "category": "system_diagnostics",
            "severity": "info",
            "title": "MQ-135 Heater Conditioning in Progress",
            "what_is_wrong": "MQ-135 sensor is either in initial warm-up phase (< 5 min) or rolling baseline is accumulating.",
            "target_metric": "Sensor Warm-Up (> 300 seconds & baseline established)",
            "current_value_summary": "Status: Conditioning / Accumulating Clean-Air Baseline",
            "recommended_action": "Allow the sensor heater to stabilize continuously. Gas response scoring uses provisional default baseline.",
            "explanation": "Metal-oxide semiconductor sensors require heater thermal equilibrium to form a stable surface resistance.",
            "indoor_evidence": {"mq135_ready": False, "pin_mv": mq135_mv},
            "outdoor_evidence": {},
            "measurement_limitations": "Freshly powered sensors exhibit drift until initial burn-in (24-48h) is completed.",
            "created_at": now_str,
            "status": "active",
        })

    if outdoor_status != "ok" and outdoor_status != "live":
        recs.append({
            "id": _gen_rec_id("rule_i_outdoor_offline", outdoor_status),
            "rule_id": "rule_i",
            "category": "system_diagnostics",
            "severity": "info",
            "title": "Outdoor API Offline or Cached",
            "what_is_wrong": f"Outdoor weather & AQI service is currently in '{outdoor_status}' state.",
            "target_metric": "Outdoor API Connectivity (Open-Meteo)",
            "current_value_summary": f"Outdoor status: {outdoor_status.upper()}",
            "recommended_action": "Check laptop internet connectivity. The system will continue using cached outdoor data if available.",
            "explanation": "Comparison engine requires outdoor weather and AQI for complete ventilation assessment.",
            "indoor_evidence": {},
            "outdoor_evidence": {"outdoor_status": outdoor_status},
            "measurement_limitations": "Outdoor comparisons may be indeterminate while offline.",
            "created_at": now_str,
            "status": "active",
        })

    # Sort recommendations by severity order: critical (0) > warning (1) > advisory (2) > info (3)
    recs.sort(key=lambda r: SEVERITY_ORDER.get(r["severity"], 99))
    return recs


def evaluate_diagnostics_matrix(
    indoor_telemetry: Dict[str, Any],
    outdoor_data: Dict[str, Any],
    rci_result: Optional[Dict[str, Any]] = None,
    usb_status: str = "connected",
    wifi_status: str = "standby",
) -> Dict[str, Any]:
    """Compile comprehensive 9-subsystem diagnostics matrix for the dashboard.

    Subsystems:
    1. usb_bridge
    2. wifi_telemetry
    3. backend_server
    4. sqlite_database
    5. dht22_sensor
    6. mq135_sensor
    7. experimental_estimators
    8. outdoor_api
    9. rci_coverage
    """
    now_str = _iso_now()

    # 1. USB Bridge
    usb_state = usb_status

    # 2. Wi-Fi Telemetry
    wifi_state = wifi_status

    # 3. Backend Server
    backend_state = "healthy"

    # 4. Database
    db_state = "healthy"

    # 5. DHT22
    t = indoor_telemetry.get("temperature")
    rh = indoor_telemetry.get("humidity")
    if t is not None and rh is not None:
        dht_state = "healthy"
        dht_detail = f"{t:.1f}°C, {rh:.1f}%"
    else:
        dht_state = "error"
        dht_detail = "Missing or invalid temperature/humidity"

    # 6. MQ-135
    mq_ready = indoor_telemetry.get("mq135_is_ready", False)
    mq_mv = indoor_telemetry.get("mq135_pin_mv")
    if mq_mv is None:
        mq_state = "error"
        mq_detail = "No ADC signal received"
    elif not mq_ready:
        mq_state = "warming_up"
        mq_detail = f"{mq_mv:.0f} mV (Conditioning heater)"
    else:
        mq_state = "healthy"
        mq_detail = f"{mq_mv:.0f} mV (Baseline ready)"

    # 7. Estimators
    est_state = "uncalibrated_heuristic"
    est_detail = "Operational (Demonstration heuristic proxy)"

    # 8. Outdoor API
    out_fresh = outdoor_data.get("freshness_status", "offline")
    provider_name = outdoor_data.get("provider", "Outdoor")
    if out_fresh in ("live", "cached"):
        out_state = "healthy"
        out_detail = f"{outdoor_data.get('location_label', 'Active')} ({provider_name}, US AQI: {outdoor_data.get('aqi')})"
    elif out_fresh in ("stale", "stale_cached", "stale_observation"):
        out_state = "degraded"
        age_str = f"{outdoor_data.get('age_seconds', '?')}s old"
        out_detail = f"Stale {provider_name} data ({age_str})"
    else:
        out_state = "offline"
        out_detail = outdoor_data.get("error", "No connection")

    # 9. RCI Coverage
    cov = 0.0
    if rci_result:
        cov = float(rci_result.get("data_coverage_percent") or rci_result.get("data_coverage_pct") or 0.0)
    if cov >= 80:
        rci_state = "complete"
        rci_detail = f"{cov:.0f}% coverage"
    elif cov >= 50:
        rci_state = "partial"
        rci_detail = f"{cov:.0f}% coverage"
    else:
        rci_state = "insufficient"
        rci_detail = "< 50% sensor coverage"

    return {
        "timestamp": now_str,
        "subsystems": {
            "usb_bridge": {"status": usb_state, "label": "USB Serial Bridge (COM4)"},
            "wifi_telemetry": {"status": wifi_state, "label": "Wi-Fi HTTP Telemetry"},
            "backend_server": {"status": backend_state, "label": "Flask Backend Server"},
            "sqlite_database": {"status": db_state, "label": "SQLite Persistence"},
            "dht22_sensor": {"status": dht_state, "detail": dht_detail, "label": "DHT22 Digital Interface"},
            "mq135_sensor": {"status": mq_state, "detail": mq_detail, "label": "MQ-135 Gas Channel"},
            "experimental_estimators": {"status": est_state, "detail": est_detail, "label": "Experimental Estimators"},
            "outdoor_api": {"status": out_state, "detail": out_detail, "label": f"{provider_name} Atmospheric API"},
            "rci_coverage": {"status": rci_state, "detail": rci_detail, "label": "RCI Telemetry Coverage"},
        },
    }
