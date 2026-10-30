"""Authoritative Room Comfort Index (RCI) Calculation Engine.

Implements the single source-of-truth Room Comfort Index algorithm according to
Section 8 of the SIEIS Master Specification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import Config


class RoomComfortIndexEngine:
    """Calculates the authoritative Room Comfort Index (0-100)."""

    @classmethod
    def calculate_temp_score(cls, temp_c: Optional[float]) -> Optional[float]:
        """Calculates temperature component score (0-100).

        Optimal band: 21.0 - 24.0 C -> 100.
        Acceptable lower: 14.0 - 21.0 C -> (T - 14) / (21 - 14) * 100.
        Acceptable upper: 24.0 - 33.0 C -> (33 - T) / (33 - 24) * 100.
        Below 14.0 or above 33.0 -> 0.
        """
        if temp_c is None:
            return None
        t = float(temp_c)
        if cls._is_invalid(t):
            return None

        if Config.RCI_TEMP_OPT_MIN <= t <= Config.RCI_TEMP_OPT_MAX:
            score = 100.0
        elif Config.RCI_TEMP_MIN <= t < Config.RCI_TEMP_OPT_MIN:
            score = ((t - Config.RCI_TEMP_MIN) / (Config.RCI_TEMP_OPT_MIN - Config.RCI_TEMP_MIN)) * 100.0
        elif Config.RCI_TEMP_OPT_MAX < t <= Config.RCI_TEMP_MAX:
            score = ((Config.RCI_TEMP_MAX - t) / (Config.RCI_TEMP_MAX - Config.RCI_TEMP_OPT_MAX)) * 100.0
        else:
            score = 0.0

        return round(max(0.0, min(100.0, score)), 1)

    @classmethod
    def calculate_humidity_score(cls, hum_pct: Optional[float]) -> Optional[float]:
        """Calculates relative humidity component score (0-100).

        Optimal band: 40.0 - 60.0 % -> 100.
        Acceptable lower: 15.0 - 40.0 % -> (RH - 15) / (40 - 15) * 100.
        Acceptable upper: 60.0 - 85.0 % -> (85 - RH) / (85 - 60) * 100.
        Below 15.0 or above 85.0 -> 0.
        """
        if hum_pct is None:
            return None
        h = float(hum_pct)
        if cls._is_invalid(h):
            return None

        if Config.RCI_HUM_OPT_MIN <= h <= Config.RCI_HUM_OPT_MAX:
            score = 100.0
        elif Config.RCI_HUM_MIN <= h < Config.RCI_HUM_OPT_MIN:
            score = ((h - Config.RCI_HUM_MIN) / (Config.RCI_HUM_OPT_MIN - Config.RCI_HUM_MIN)) * 100.0
        elif Config.RCI_HUM_OPT_MAX < h <= Config.RCI_HUM_MAX:
            score = ((Config.RCI_HUM_MAX - h) / (Config.RCI_HUM_MAX - Config.RCI_HUM_OPT_MAX)) * 100.0
        else:
            score = 0.0

        return round(max(0.0, min(100.0, score)), 1)

    @classmethod
    def calculate_gas_score(
        cls,
        mq_raw_adc: Optional[int | float],
        mq_baseline: Optional[float],
        mq_status: str = "ready",
    ) -> Optional[float]:
        """Calculates MQ-135 relative gas response score (0-100).

        Valid only when baseline is ready and valid.
        Ratio = MQ135_raw / MQ135_baseline.
        Ratio <= 1.05 -> 100.
        Ratio >= 2.50 -> 0.
        Otherwise: (1 - (ratio - 1.05) / (2.50 - 1.05)) * 100.
        """
        if (
            mq_raw_adc is None
            or mq_baseline is None
            or mq_baseline <= 0
            or mq_status != "ready"
        ):
            return None

        val = float(mq_raw_adc)
        if cls._is_invalid(val):
            return None

        ratio = val / mq_baseline
        if ratio <= Config.RCI_GAS_CLEAN_RATIO:
            score = 100.0
        elif ratio >= Config.RCI_GAS_MAX_RATIO:
            score = 0.0
        else:
            score = (
                1.0 - ((ratio - Config.RCI_GAS_CLEAN_RATIO) / (Config.RCI_GAS_MAX_RATIO - Config.RCI_GAS_CLEAN_RATIO))
            ) * 100.0

        return round(max(0.0, min(100.0, score)), 1)

    @classmethod
    def calculate_light_score(cls, light_raw: Optional[int | float]) -> Optional[float]:
        """Calculates LDR relative brightness score (0-100).

        Bright (ADC >= 1700): 100.
        Dim (ADC 250 - 1699): 85.
        Dark (ADC < 250): 50.
        """
        if light_raw is None:
            return None
        lr = float(light_raw)
        if cls._is_invalid(lr):
            return None

        if lr >= Config.LDR_DIM_THRESHOLD:
            return 100.0
        elif lr >= Config.LDR_DARK_THRESHOLD:
            return 85.0
        else:
            return 50.0

    @classmethod
    def calculate_sound_score(
        cls, sound_swing: Optional[int | float], sound_do: Optional[int] = 0
    ) -> Optional[float]:
        """Calculates sound activity score (0-100).

        Quiet / stable (< 400): 100.
        Moderate background (400 - 1199): 80.
        High swing (>= 1200) or DO threshold triggered: 40.
        """
        if sound_swing is None:
            return None
        sw = float(sound_swing)
        if cls._is_invalid(sw):
            return None

        if sound_do == 1 or sw >= 1200:
            return 40.0
        elif sw >= 400:
            return 80.0
        else:
            return 100.0

    @classmethod
    def calculate_rci(
        cls,
        observation: Optional[Dict[str, Any]],
        mq_baseline: Optional[float] = None,
        stale_seconds_elapsed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Calculates the complete Room Comfort Index conforming to Section 8 schema."""
        now_iso = datetime.now(timezone.utc).isoformat()

        if not observation:
            return cls._indeterminate_result(
                reason="No sensor telemetry observation provided.",
                calculated_at=now_iso,
                is_stale=True,
            )

        # 1. Check Stale Telemetry Threshold
        is_stale = False
        if stale_seconds_elapsed is not None and stale_seconds_elapsed > Config.RCI_STALE_THRESHOLD_SECONDS:
            is_stale = True

        # Extract readings
        temp_c = observation.get("temperature_c")
        hum_pct = observation.get("humidity_percent")
        light_raw = observation.get("light_raw")
        mq_raw = observation.get("mq135_adc_mv")
        mq_status = str(observation.get("mq135_status", "unknown")).lower()
        sound_swing = observation.get("sound_swing")
        sound_do = observation.get("sound_do", 0)

        # Mandatory Core Inputs Check
        if temp_c is None or hum_pct is None:
            return cls._indeterminate_result(
                reason="Core temperature and relative humidity inputs are required for RCI.",
                calculated_at=now_iso,
                is_stale=is_stale,
            )

        if is_stale:
            return cls._indeterminate_result(
                reason=f"Telemetry is stale ({stale_seconds_elapsed}s > {Config.RCI_STALE_THRESHOLD_SECONDS}s threshold).",
                calculated_at=now_iso,
                is_stale=True,
            )

        # Compute component scores
        s_temp = cls.calculate_temp_score(temp_c)
        s_hum = cls.calculate_humidity_score(hum_pct)
        s_gas = cls.calculate_gas_score(mq_raw, mq_baseline, mq_status)
        s_light = cls.calculate_light_score(light_raw)
        s_sound = cls.calculate_sound_score(sound_swing, sound_do)

        all_specs = [
            ("temperature", s_temp, Config.RCI_WEIGHT_TEMP),
            ("humidity", s_hum, Config.RCI_WEIGHT_HUM),
            ("gas_response", s_gas, Config.RCI_WEIGHT_GAS),
            ("lighting", s_light, Config.RCI_WEIGHT_LIGHT),
            ("sound", s_sound, Config.RCI_WEIGHT_SOUND),
        ]

        valid_components: Dict[str, float] = {}
        available_inputs: List[str] = []
        unavailable_inputs: List[str] = []
        active_weight_sum = 0.0

        for name, score, weight in all_specs:
            if score is not None:
                valid_components[name] = score
                available_inputs.append(name)
                active_weight_sum += weight
            else:
                unavailable_inputs.append(name)

        total_nominal_weight = sum(w for _, _, w in all_specs)
        coverage_pct = round((active_weight_sum / total_nominal_weight) * 100.0, 1)

        # Check coverage threshold
        if coverage_pct < Config.RCI_MIN_COVERAGE_PCT or active_weight_sum <= 0:
            return cls._indeterminate_result(
                reason=f"Data coverage ({coverage_pct}%) is below minimum required {Config.RCI_MIN_COVERAGE_PCT}%.",
                calculated_at=now_iso,
                is_stale=is_stale,
            )

        # Normalized weighted synthesis
        weighted_sum = sum(
            valid_components[name] * (weight / active_weight_sum)
            for name, _, weight in all_specs
            if name in valid_components
        )
        final_score = round(max(0.0, min(100.0, weighted_sum)), 1)

        # Determine band
        if final_score >= 80.0:
            status = "Optimal / Comfortable"
            color_band = "green"
        elif final_score >= 50.0:
            status = "Moderate / Needs Attention"
            color_band = "yellow"
        else:
            status = "Poor / Uncomfortable"
            color_band = "red"

        is_provisional = coverage_pct < 100.0 or (s_gas is None)
        confidence = "High" if coverage_pct >= 90.0 and not is_provisional else "Moderate" if coverage_pct >= 60.0 else "Low"

        # Categorize positive / negative contributors
        positive_contributors = [
            f"{k.capitalize()} ({v}%)" for k, v in valid_components.items() if v >= 80.0
        ]
        negative_contributors = [
            f"{k.capitalize()} ({v}%)" for k, v in valid_components.items() if v < 70.0
        ]

        # Explanation
        explanations = []
        if s_temp is not None:
            explanations.append(f"Thermal: {s_temp}% ({temp_c}°C)")
        if s_hum is not None:
            explanations.append(f"Hygric: {s_hum}% ({hum_pct}%)")
        if s_gas is not None:
            ratio_str = f"{round(float(mq_raw) / mq_baseline, 2)}x" if mq_baseline else "N/A"
            explanations.append(f"Gas: {s_gas}% ({ratio_str} baseline)")
        elif "gas_response" in unavailable_inputs:
            explanations.append("Gas: [Excluded - Warmup/Baseline Unconditioned]")

        return {
            "score": final_score,
            "status": status,
            "color_band": color_band,
            "is_provisional": is_provisional,
            "is_stale": is_stale,
            "data_coverage_percent": coverage_pct,
            "confidence_level": confidence,
            "component_scores": valid_components,
            "main_positive_contributors": positive_contributors,
            "main_negative_contributors": negative_contributors,
            "available_inputs": available_inputs,
            "unavailable_inputs": unavailable_inputs,
            "calculated_at": now_iso,
            "explanation": "; ".join(explanations),
        }

    @staticmethod
    def _is_invalid(val: Any) -> bool:
        import math
        return val is None or math.isnan(val) or math.isinf(val)

    @classmethod
    def _indeterminate_result(
        cls, reason: str, calculated_at: str, is_stale: bool = False
    ) -> Dict[str, Any]:
        return {
            "score": None,
            "status": "Indeterminate / Stale Telemetry" if is_stale else "Indeterminate / Insufficient Inputs",
            "color_band": "gray",
            "is_provisional": True,
            "is_stale": is_stale,
            "data_coverage_percent": 0.0,
            "confidence_level": "None",
            "component_scores": {},
            "main_positive_contributors": [],
            "main_negative_contributors": [],
            "available_inputs": [],
            "unavailable_inputs": ["temperature", "humidity", "gas_response", "lighting", "sound"],
            "calculated_at": calculated_at,
            "explanation": reason,
        }


def calculate_rci(
    observation: Optional[Dict[str, Any]] = None,
    mq_baseline: Optional[float] = None,
    stale_seconds_elapsed: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Top-level convenience wrapper for RoomComfortIndexEngine.calculate_rci.

    Supports both (observation_dict, mq_baseline, stale_seconds) and
    keyword parameters (temp_c, rh_pct, mq135_pin_mv, etc.).
    """
    if observation is None and kwargs:
        observation = {
            "temperature_c": kwargs.get("temp_c"),
            "humidity_percent": kwargs.get("rh_pct"),
            "light_raw": kwargs.get("ldr_raw"),
            "mq135_adc_mv": kwargs.get("mq135_pin_mv"),
            "mq135_status": "ready" if kwargs.get("mq135_is_ready") else "warming_up",
            "sound_swing": kwargs.get("sound_swing"),
            "sound_do": kwargs.get("sound_do", 0),
        }
        if mq_baseline is None:
            mq_baseline = kwargs.get("mq135_baseline_mv")
        if stale_seconds_elapsed is None:
            stale_seconds_elapsed = kwargs.get("telemetry_age_seconds")
    return RoomComfortIndexEngine.calculate_rci(observation, mq_baseline, stale_seconds_elapsed)

