"""SIEIS Rule-Based Decision Support Module.

Synthesizes environmental states, trends, and scores into actionable, explainable
operational recommendations without overreaching into uncalibrated or medical claims.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import Config


class DecisionEngine:
    """Evaluates multi-sensor states and generates actionable operational recommendations."""

    @classmethod
    def evaluate_recommendations(
        cls,
        latest_observation: Optional[Dict[str, Any]],
        scores: Optional[Dict[str, Any]],
        trends: Optional[Dict[str, Any]],
        forecasts: Optional[Dict[str, Any]],
        active_alerts: Optional[List[Dict[str, Any]]] = None,
        is_stale: bool = False,
    ) -> List[Dict[str, Any]]:
        """Generates prioritized list of actionable recommendations."""
        recommendations: List[Dict[str, Any]] = []

        # 1. Device Stale / Connectivity Check
        if is_stale or not latest_observation:
            recommendations.append({
                "category": "CONNECTIVITY",
                "priority": "HIGH",
                "title": "Sensor Node Disconnected or Stale",
                "explanation": (
                    f"No packets received from sensor node within {Config.STALE_THRESHOLD_SECONDS} seconds. "
                    "Current data does not reflect real-time room conditions."
                ),
                "action": "Verify ESP32 power supply, check USB serial monitor, and ensure Wi-Fi hotspot connection is active.",
            })
            return recommendations

        obs = latest_observation
        temp = obs.get("temperature_c")
        hum = obs.get("humidity_percent")
        light_label = obs.get("light_label")
        mq_status = obs.get("mq135_status")
        mq_pin_mv = obs.get("mq135_adc_mv")
        sound_swing = obs.get("sound_swing")

        # 2. Thermal Comfort Decision
        if temp is not None:
            if temp > Config.COMFORT_TEMP_ACCEPTABLE_MAX:
                recommendations.append({
                    "category": "THERMAL_COMFORT",
                    "priority": "MEDIUM",
                    "title": "High Indoor Temperature",
                    "explanation": f"Current temperature is {temp}°C (optimal is 20–25°C).",
                    "action": "Increase room air circulation, open windows for cross-breeze, or enable cooling.",
                })
            elif temp < Config.COMFORT_TEMP_ACCEPTABLE_MIN:
                recommendations.append({
                    "category": "THERMAL_COMFORT",
                    "priority": "MEDIUM",
                    "title": "Low Indoor Temperature",
                    "explanation": f"Current temperature is {temp}°C (optimal is 20–25°C).",
                    "action": "Inspect for drafts from open windows or doors, or engage supplemental space heating.",
                })

        # 3. Hygric / Humidity Comfort Decision
        if hum is not None:
            if hum > Config.COMFORT_HUM_ACCEPTABLE_MAX:
                recommendations.append({
                    "category": "HUMIDITY",
                    "priority": "MEDIUM",
                    "title": "Elevated Humidity Level",
                    "explanation": f"Relative humidity is {hum}% (comfort range is 40–60%).",
                    "action": "High moisture levels encourage stuffiness and mold growth. Increase exhaust ventilation.",
                })
            elif hum < Config.COMFORT_HUM_ACCEPTABLE_MIN:
                recommendations.append({
                    "category": "HUMIDITY",
                    "priority": "LOW",
                    "title": "Dry Indoor Air",
                    "explanation": f"Relative humidity is {hum}% (optimal is 40–60%).",
                    "action": "Dry air can cause respiratory irritation and static. Consider introducing indoor plants or humidification.",
                })

        # 4. Air Quality / Gas Response Decision (MQ-135)
        if mq_status == "warming_up":
            recommendations.append({
                "category": "AIR_QUALITY",
                "priority": "LOW",
                "title": "MQ-135 Sensor Warming Up",
                "explanation": "Internal heater requires 5 minutes after power-on to stabilize chemical baseline.",
                "action": "Allow sensor warmup to finish before relying on gas-response elevation indicators.",
            })
        elif mq_status == "ready":
            # Check active alerts for baseline elevation
            if active_alerts:
                for alert in active_alerts:
                    if "MQ135_ELEVATION" in alert.get("rule_name", ""):
                        recommendations.append({
                            "category": "AIR_QUALITY",
                            "priority": "HIGH" if "CRITICAL" in alert.get("rule_name", "") else "MEDIUM",
                            "title": "Ventilation Recommended: Gas Response Elevated",
                            "explanation": alert.get("message", "Gas response reading elevated above room baseline."),
                            "action": alert.get("recommendation", "Open windows or doors to promote fresh air exchange."),
                        })
                        break

        # 5. Visual Lighting Decision
        if light_label == "dark":
            recommendations.append({
                "category": "LIGHTING",
                "priority": "LOW",
                "title": "Low Ambient Illumination",
                "explanation": "Current lighting is classified as 'dark' (<250 raw ADC).",
                "action": "Turn on task or ceiling lighting to prevent eye strain during study or laboratory activities.",
            })

        # 6. Acoustic Disturbance Decision
        if sound_swing is not None and sound_swing >= 2000:
            recommendations.append({
                "category": "ACOUSTICS",
                "priority": "LOW",
                "title": "Elevated Acoustic Noise",
                "explanation": f"Acoustic module registered substantial peak sound swing ({sound_swing}).",
                "action": "High ambient noise can degrade focus. Check for active conversations, equipment, or external sources.",
            })

        # 7. Predictive Trend Warnings
        if forecasts:
            temp_fc = forecasts.get("temperature", {})
            if temp_fc.get("status") == "forecast_ready":
                for proj in temp_fc.get("projections", []):
                    if proj.get("horizon_minutes") == 15 and proj.get("projected_value", 0) > 28.0:
                        recommendations.append({
                            "category": "PREDICTIVE_INSIGHT",
                            "priority": "MEDIUM",
                            "title": "Proactive Cooling Advisory",
                            "explanation": f"Temperature trend indicates room may reach {proj.get('projected_value')}°C in 15 minutes.",
                            "action": "Proactively enable ventilation now to arrest continued thermal buildup.",
                        })
                        break

        # Fallback if conditions are optimal
        if not recommendations:
            recommendations.append({
                "category": "OVERALL",
                "priority": "INFO",
                "title": "Optimal Indoor Environment",
                "explanation": "All monitored metrics are within acceptable comfort and baseline boundaries.",
                "action": "Maintain current ventilation and environmental settings.",
            })

        return recommendations
