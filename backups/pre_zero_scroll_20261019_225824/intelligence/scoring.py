"""SIEIS Environmental Health and Comfort Scoring Module.

Calculates explainable, transparent scores based strictly on active hardware
readings (DHT22, LDR, MQ-135, LM393). Accurately handles missing or uncalibrated
sensors and exposes data coverage.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import Config


class EnvironmentalScorer:
    """Calculates Comfort Index and Environmental Health Score (EHS)."""

    @classmethod
    def calculate_comfort_index(
        cls, temp_c: Optional[float], hum_pct: Optional[float]
    ) -> Dict[str, Any]:
        """Calculates thermal-hygric comfort index (0 to 100) based on DHT22 readings.

        Aligned with ASHRAE 55 and CIBSE recommendations for indoor comfort.
        """
        if temp_c is None and hum_pct is None:
            return {
                "score": None,
                "status": "UNAVAILABLE",
                "reason": "Neither temperature nor humidity reading is available.",
                "temp_score": None,
                "hum_score": None,
            }

        # 1. Thermal Comfort Score (0 to 100)
        temp_score: Optional[float] = None
        if temp_c is not None:
            t = temp_c
            opt_min, opt_max = Config.COMFORT_TEMP_OPTIMAL_MIN, Config.COMFORT_TEMP_OPTIMAL_MAX
            acc_min, acc_max = Config.COMFORT_TEMP_ACCEPTABLE_MIN, Config.COMFORT_TEMP_ACCEPTABLE_MAX

            if opt_min <= t <= opt_max:
                temp_score = 100.0
            elif acc_min <= t < opt_min:
                temp_score = 70.0 + (30.0 * (t - acc_min) / (opt_min - acc_min))
            elif opt_max < t <= acc_max:
                temp_score = 70.0 + (30.0 * (acc_max - t) / (acc_max - opt_max))
            elif t < acc_min:
                # Below 18 C down to 10 C
                temp_score = max(0.0, 70.0 * (t - 10.0) / (acc_min - 10.0))
            else:
                # Above 27 C up to 35 C
                temp_score = max(0.0, 70.0 * (35.0 - t) / (35.0 - acc_max))
            temp_score = round(temp_score, 1)

        # 2. Hygric / Humidity Comfort Score (0 to 100)
        hum_score: Optional[float] = None
        if hum_pct is not None:
            h = hum_pct
            opt_min, opt_max = Config.COMFORT_HUM_OPTIMAL_MIN, Config.COMFORT_HUM_OPTIMAL_MAX
            acc_min, acc_max = Config.COMFORT_HUM_ACCEPTABLE_MIN, Config.COMFORT_HUM_ACCEPTABLE_MAX

            if opt_min <= h <= opt_max:
                hum_score = 100.0
            elif acc_min <= h < opt_min:
                hum_score = 70.0 + (30.0 * (h - acc_min) / (opt_min - acc_min))
            elif opt_max < h <= acc_max:
                hum_score = 70.0 + (30.0 * (acc_max - h) / (acc_max - opt_max))
            elif h < acc_min:
                # Below 30% down to 15%
                hum_score = max(0.0, 70.0 * (h - 15.0) / (acc_min - 15.0))
            else:
                # Above 70% up to 85%
                hum_score = max(0.0, 70.0 * (85.0 - h) / (85.0 - acc_max))
            hum_score = round(hum_score, 1)

        # 3. Aggregate Comfort Index
        if temp_score is not None and hum_score is not None:
            comfort_val = round(0.55 * temp_score + 0.45 * hum_score, 1)
        elif temp_score is not None:
            comfort_val = temp_score
        else:
            comfort_val = hum_score

        if comfort_val >= 85.0:
            status = "COMFORTABLE"
        elif comfort_val >= 65.0:
            status = "SLIGHTLY_UNCOMFORTABLE"
        else:
            status = "UNCOMFORTABLE"

        return {
            "score": comfort_val,
            "status": status,
            "temp_score": temp_score,
            "hum_score": hum_score,
            "reason": f"Thermal score {temp_score}%, Hygric score {hum_score}%",
        }

    @classmethod
    def calculate_environmental_health_score(
        cls,
        observation: Dict[str, Any],
        mq135_baseline_mv: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calculates project-specific Environmental Health Score (EHS).

        Synthesizes validated comfort, gas response relative to baseline,
        ambient lighting, and noise activity into a 0-100 contextual rating.
        """
        temp_c = observation.get("temperature_c")
        hum_pct = observation.get("humidity_percent")
        light_raw = observation.get("light_raw")
        mq_pin_mv = observation.get("mq135_adc_mv")
        mq_status = observation.get("mq135_status", "unknown")
        sound_swing = observation.get("sound_swing")

        # 1. Thermal/Hygric Comfort Component (Default weight 0.40)
        comfort_res = cls.calculate_comfort_index(temp_c, hum_pct)
        comfort_subscore = comfort_res.get("score")

        # 2. Gas Response Relative to Baseline (Default weight 0.30)
        gas_subscore: Optional[float] = None
        gas_reason = ""
        if mq_status == "ready" and mq_pin_mv is not None and mq135_baseline_mv and mq135_baseline_mv > 0:
            ratio = mq_pin_mv / mq135_baseline_mv
            if ratio <= 1.05:
                gas_subscore = 100.0
                gas_reason = "Gas response within normal rolling baseline."
            elif ratio <= Config.MQ135_ELEVATION_RATIO_WARN:
                # 1.05 to 1.25 -> 100 down to 75
                frac = (ratio - 1.05) / (Config.MQ135_ELEVATION_RATIO_WARN - 1.05)
                gas_subscore = round(100.0 - 25.0 * frac, 1)
                gas_reason = f"Gas response slightly elevated ({round(ratio, 2)}x baseline)."
            elif ratio <= Config.MQ135_ELEVATION_RATIO_ALERT:
                # 1.25 to 1.50 -> 75 down to 40
                frac = (ratio - Config.MQ135_ELEVATION_RATIO_WARN) / (
                    Config.MQ135_ELEVATION_RATIO_ALERT - Config.MQ135_ELEVATION_RATIO_WARN
                )
                gas_subscore = round(75.0 - 35.0 * frac, 1)
                gas_reason = f"Gas response moderately elevated ({round(ratio, 2)}x baseline)."
            else:
                # > 1.50 -> drops to 10
                gas_subscore = max(10.0, round(40.0 - 30.0 * (ratio - 1.50), 1))
                gas_reason = f"Gas response significantly elevated ({round(ratio, 2)}x baseline)."
        else:
            if mq_status == "warming_up":
                gas_reason = "MQ-135 is warming up (5 min window); excluded from EHS."
            elif not mq135_baseline_mv:
                gas_reason = "Insufficient baseline history for MQ-135; excluded from EHS."
            else:
                gas_reason = "MQ-135 sensor reading unavailable."

        # 3. Ambient Lighting Component (Default weight 0.15)
        light_subscore: Optional[float] = None
        if light_raw is not None:
            if light_raw < Config.LDR_DARK_THRESHOLD:
                # Very dark (<250) - sub-optimal for daytime study/lab work
                light_subscore = 65.0
            elif light_raw < Config.LDR_DIM_THRESHOLD:
                # Dim to moderate lighting (250-1699) - comfortable indoor illumination
                light_subscore = 95.0
            else:
                # Bright / High illumination (>1700)
                light_subscore = 85.0

        # 4. Sound Activity Component (Default weight 0.15)
        sound_subscore: Optional[float] = None
        if sound_swing is not None:
            if sound_swing < 400:
                sound_subscore = 100.0  # Quiet
            elif sound_swing < 1200:
                sound_subscore = 85.0   # Normal conversation or background noise
            elif sound_swing < 2200:
                sound_subscore = 65.0   # Elevated disturbance
            else:
                sound_subscore = 40.0   # Loud disturbance or continuous noise

        # Dynamically re-normalize weights across available parameters
        available_weights: Dict[str, float] = {}
        subscores: Dict[str, float] = {}

        if comfort_subscore is not None:
            available_weights["comfort"] = 0.40
            subscores["comfort"] = comfort_subscore
        if gas_subscore is not None:
            available_weights["gas_response"] = 0.30
            subscores["gas_response"] = gas_subscore
        if light_subscore is not None:
            available_weights["lighting"] = 0.15
            subscores["lighting"] = light_subscore
        if sound_subscore is not None:
            available_weights["noise"] = 0.15
            subscores["noise"] = sound_subscore

        total_weight = sum(available_weights.values())
        if total_weight <= 0:
            return {
                "health_score": None,
                "health_grade": "UNKNOWN",
                "comfort_index": None,
                "comfort_status": "UNKNOWN",
                "data_coverage_pct": 0.0,
                "components": {},
                "calculation_reason": "No valid sensor data available to compute score.",
            }

        weighted_sum = sum(subscores[k] * (available_weights[k] / total_weight) for k in available_weights)
        final_health_score = round(weighted_sum, 1)

        # Grade assignment
        if final_health_score >= 85.0:
            grade = "OPTIMAL"
        elif final_health_score >= 70.0:
            grade = "GOOD"
        elif final_health_score >= 50.0:
            grade = "FAIR"
        elif final_health_score >= 30.0:
            grade = "POOR"
        else:
            grade = "CRITICAL"

        coverage_pct = round((len(available_weights) / 4.0) * 100.0, 1)

        reasons = []
        if comfort_subscore is not None:
            reasons.append(f"Comfort: {comfort_subscore}%")
        if gas_subscore is not None:
            reasons.append(f"Gas: {gas_subscore}% ({gas_reason})")
        elif gas_reason:
            reasons.append(f"Gas: [Excluded] {gas_reason}")
        if light_subscore is not None:
            reasons.append(f"Light: {light_subscore}%")
        if sound_subscore is not None:
            reasons.append(f"Sound: {sound_subscore}%")

        return {
            "health_score": final_health_score,
            "health_grade": grade,
            "comfort_index": comfort_subscore,
            "comfort_status": comfort_res.get("status", "UNKNOWN"),
            "data_coverage_pct": coverage_pct,
            "components": {
                "comfort": comfort_subscore,
                "gas_response": gas_subscore,
                "lighting": light_subscore,
                "noise": sound_subscore,
                "coverage_pct": coverage_pct,
            },
            "calculation_reason": "; ".join(reasons),
        }
