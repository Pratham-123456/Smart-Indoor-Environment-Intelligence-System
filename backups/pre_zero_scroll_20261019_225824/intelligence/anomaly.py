"""SIEIS Anomaly Detection and Alert Evaluation Layer.

Detects multi-parameter threshold breaches, rapid rates-of-change, and
baseline-relative gas elevations. Includes deduplication, cooldowns,
and automatic resolution when conditions normalize.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from config import Config

logger = logging.getLogger("sieis.anomaly")


class AnomalyDetector:
    """Evaluates observations against contextual rules and manages alert lifecycles."""

    def __init__(self, db: Any):
        self.db = db

    def evaluate_observation(
        self,
        observation: Dict[str, Any],
        trends: Dict[str, Any],
        mq135_baseline_mv: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluates an observation and generates alerts if anomalies are detected.

        Returns a list of generated or updated alert dicts.
        """
        device_id = observation["device_id"]
        received_at = observation["received_at"]
        generated_alerts: List[Dict[str, Any]] = []

        temp_c = observation.get("temperature_c")
        hum_pct = observation.get("humidity_percent")
        mq_pin_mv = observation.get("mq135_adc_mv")
        mq_status = observation.get("mq135_status", "unknown")
        sound_swing = observation.get("sound_swing")

        # ----------------------------------------------------
        # Rule 1 & 2: Thermal Threshold Breaches
        # ----------------------------------------------------
        if temp_c is not None:
            if temp_c > Config.COMFORT_TEMP_ACCEPTABLE_MAX:
                alert = self._process_rule(
                    device_id=device_id,
                    rule_name="TEMP_HIGH_BREACH",
                    signal_name="temperature",
                    severity="WARNING",
                    trigger_value=temp_c,
                    message=f"High ambient temperature: {temp_c}°C exceeds acceptable upper threshold (27.0°C).",
                    recommendation="Enable room ventilation, air cooling, or adjust climate controls to restore comfort.",
                    current_iso=received_at,
                )
                if alert:
                    generated_alerts.append(alert)
            elif temp_c < Config.COMFORT_TEMP_ACCEPTABLE_MIN:
                alert = self._process_rule(
                    device_id=device_id,
                    rule_name="TEMP_LOW_BREACH",
                    signal_name="temperature",
                    severity="WARNING",
                    trigger_value=temp_c,
                    message=f"Low ambient temperature: {temp_c}°C falls below acceptable lower threshold (18.0°C).",
                    recommendation="Inspect room heating or draft sources to prevent cold indoor discomfort.",
                    current_iso=received_at,
                )
                if alert:
                    generated_alerts.append(alert)
            else:
                # Normal conditions: resolve active thermal alerts
                self.db.resolve_alerts_for_rule(device_id, "TEMP_HIGH_BREACH", received_at)
                self.db.resolve_alerts_for_rule(device_id, "TEMP_LOW_BREACH", received_at)

        # ----------------------------------------------------
        # Rule 3 & 4: Humidity Threshold Breaches
        # ----------------------------------------------------
        if hum_pct is not None:
            if hum_pct > Config.COMFORT_HUM_ACCEPTABLE_MAX:
                alert = self._process_rule(
                    device_id=device_id,
                    rule_name="HUM_HIGH_BREACH",
                    signal_name="humidity",
                    severity="WARNING",
                    trigger_value=hum_pct,
                    message=f"High relative humidity: {hum_pct}% exceeds comfortable moisture threshold (70%).",
                    recommendation="Increase fresh air exchange or enable dehumidification to mitigate stuffiness and condensation risk.",
                    current_iso=received_at,
                )
                if alert:
                    generated_alerts.append(alert)
            elif hum_pct < Config.COMFORT_HUM_ACCEPTABLE_MIN:
                alert = self._process_rule(
                    device_id=device_id,
                    rule_name="HUM_LOW_BREACH",
                    signal_name="humidity",
                    severity="WARNING",
                    trigger_value=hum_pct,
                    message=f"Low relative humidity: {hum_pct}% is below recommended threshold (30%).",
                    recommendation="Dry air can irritate mucous membranes. Consider humidification or moderate airflow.",
                    current_iso=received_at,
                )
                if alert:
                    generated_alerts.append(alert)
            else:
                self.db.resolve_alerts_for_rule(device_id, "HUM_HIGH_BREACH", received_at)
                self.db.resolve_alerts_for_rule(device_id, "HUM_LOW_BREACH", received_at)

        # ----------------------------------------------------
        # Rule 5 & 6: MQ-135 Relative Gas Response Elevation
        # ----------------------------------------------------
        if mq_status == "ready" and mq_pin_mv is not None and mq135_baseline_mv and mq135_baseline_mv > 0:
            ratio = mq_pin_mv / mq135_baseline_mv

            if ratio >= Config.MQ135_ELEVATION_RATIO_ALERT:
                alert = self._process_rule(
                    device_id=device_id,
                    rule_name="MQ135_ELEVATION_CRITICAL",
                    signal_name="mq135_gas_response",
                    severity="CRITICAL",
                    trigger_value=round(ratio, 2),
                    message=(
                        f"Gas response significantly elevated ({round(ratio, 2)}x baseline, "
                        f"{mq_pin_mv} mV vs {mq135_baseline_mv} mV baseline)."
                    ),
                    recommendation=(
                        "Relative reducing gas response has surged 50%+ above established baseline. "
                        "Open windows, activate active ventilation, and inspect room for unventilated fumes."
                    ),
                    current_iso=received_at,
                )
                if alert:
                    generated_alerts.append(alert)
            elif ratio >= Config.MQ135_ELEVATION_RATIO_WARN:
                alert = self._process_rule(
                    device_id=device_id,
                    rule_name="MQ135_ELEVATION_WARN",
                    signal_name="mq135_gas_response",
                    severity="WARNING",
                    trigger_value=round(ratio, 2),
                    message=(
                        f"Gas response moderately elevated ({round(ratio, 2)}x baseline, "
                        f"{mq_pin_mv} mV vs {mq135_baseline_mv} mV baseline)."
                    ),
                    recommendation="Air freshness indicator is deteriorating relative to room baseline. Consider refreshing room ventilation.",
                    current_iso=received_at,
                )
                if alert:
                    generated_alerts.append(alert)
            else:
                self.db.resolve_alerts_for_rule(device_id, "MQ135_ELEVATION_CRITICAL", received_at)
                self.db.resolve_alerts_for_rule(device_id, "MQ135_ELEVATION_WARN", received_at)

        # ----------------------------------------------------
        # Rule 7: High Acoustic Disturbance
        # ----------------------------------------------------
        if sound_swing is not None:
            if sound_swing >= 2200:
                alert = self._process_rule(
                    device_id=device_id,
                    rule_name="SOUND_ELEVATED_DISTURBANCE",
                    signal_name="sound_activity",
                    severity="INFO",
                    trigger_value=sound_swing,
                    message=f"Elevated acoustic activity detected (peak swing {sound_swing}).",
                    recommendation="Substantial background noise or ongoing vocal activity detected. Check room occupancy levels.",
                    current_iso=received_at,
                )
                if alert:
                    generated_alerts.append(alert)
            elif sound_swing < 1200:
                self.db.resolve_alerts_for_rule(device_id, "SOUND_ELEVATED_DISTURBANCE", received_at)

        # ----------------------------------------------------
        # Rule 8: Rapid Rate-of-Change Anomalies (Trends)
        # ----------------------------------------------------
        temp_trend = trends.get("temperature", {})
        rate = temp_trend.get("rate_per_min")
        if rate is not None and abs(rate) >= 1.5:
            direction_str = "increase" if rate > 0 else "drop"
            alert = self._process_rule(
                device_id=device_id,
                rule_name="RAPID_TEMP_CHANGE",
                signal_name="temperature",
                severity="WARNING",
                trigger_value=rate,
                message=f"Rapid temperature {direction_str} detected ({rate:+.2f}°C/min).",
                recommendation="Sudden thermal swing observed. Check whether doors/windows were opened or HVAC equipment cycled.",
                current_iso=received_at,
            )
            if alert:
                generated_alerts.append(alert)

        return generated_alerts

    def _process_rule(
        self,
        device_id: str,
        rule_name: str,
        signal_name: str,
        severity: str,
        trigger_value: float,
        message: str,
        recommendation: str,
        current_iso: str,
    ) -> Optional[Dict[str, Any]]:
        """Handles alert persistence with cooldown deduplication."""
        # Check if an alert for this rule was raised recently
        if Config.ALERT_COOLDOWN_SECONDS > 0:
            # Parse current_iso to timestamp and calculate cutoff
            dt_curr = datetime.fromisoformat(current_iso.replace("Z", "+00:00"))
            cutoff_ts = dt_curr.timestamp() - Config.ALERT_COOLDOWN_SECONDS
            cutoff_iso = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).isoformat()

            recent = self.db.get_recent_alert_by_rule(device_id, rule_name, cutoff_iso)
            if recent:
                # In cooldown, suppress duplicate entry
                return None

        alert_data = {
            "created_at": current_iso,
            "device_id": device_id,
            "signal_name": signal_name,
            "severity": severity,
            "rule_name": rule_name,
            "trigger_value": trigger_value,
            "message": message,
            "recommendation": recommendation,
            "status": "ACTIVE",
        }
        alert_id = self.db.insert_alert(alert_data)
        alert_data["id"] = alert_id
        return alert_data
