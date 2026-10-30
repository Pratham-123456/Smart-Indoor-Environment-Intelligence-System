"""SIEIS Trend-Based Forecasting Module.

Provides defensible, qualified short-horizon projections using ordinary least-squares
linear regression on recent valid observations. Strictly qualifies limitations
and avoids unwarranted precision.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional


class TrendForecaster:
    """Computes short-horizon statistical forecasts for environmental signals."""

    MIN_SAMPLES_REQUIRED = 8

    @staticmethod
    def _parse_iso(iso_str: str) -> Optional[float]:
        try:
            return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None

    @classmethod
    def forecast_signal(
        cls,
        observations: List[Dict[str, Any]],
        signal_key: str,
        horizon_minutes: List[int] = [5, 10, 15],
        val_min: Optional[float] = None,
        val_max: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calculates linear regression forecast for a specific signal.

        Args:
            observations: Chronologically sorted observations (oldest to newest).
            signal_key: Key in observation dict.
            horizon_minutes: List of future projection intervals in minutes.
            val_min: Physical lower bound clamp.
            val_max: Physical upper bound clamp.
        """
        # Collect valid points (t_seconds, value)
        points: List[tuple[float, float]] = []
        for obs in observations:
            val = obs.get(signal_key)
            ts_str = obs.get("received_at")
            if val is not None and ts_str:
                ts = cls._parse_iso(ts_str)
                if ts is not None:
                    points.append((ts, float(val)))

        if len(points) < cls.MIN_SAMPLES_REQUIRED:
            return {
                "signal": signal_key,
                "status": "insufficient_data",
                "valid_samples": len(points),
                "required_samples": cls.MIN_SAMPLES_REQUIRED,
                "method": "ordinary_least_squares_linear",
                "message": f"Requires at least {cls.MIN_SAMPLES_REQUIRED} valid observations; found {len(points)}.",
                "projections": [],
            }

        # Normalize time to minutes relative to start of window
        t0 = points[0][0]
        x = [(p[0] - t0) / 60.0 for p in points]  # minutes
        y = [p[1] for p in points]

        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        # Compute slope (m) and intercept (c)
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator = sum((x[i] - mean_x) ** 2 for i in range(n))

        if abs(denominator) < 1e-6:
            slope = 0.0
            intercept = mean_y
            r_squared = 0.0
        else:
            slope = numerator / denominator
            intercept = mean_y - (slope * mean_x)

            # Calculate R^2 (coefficient of determination)
            ss_tot = sum((y[i] - mean_y) ** 2 for i in range(n))
            ss_res = sum((y[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
            r_squared = round(1.0 - (ss_res / ss_tot), 3) if ss_tot > 1e-6 else 1.0

        current_t = x[-1]
        current_val = round(y[-1], 2)

        projections = []
        for hm in horizon_minutes:
            future_t = current_t + hm
            pred_raw = slope * future_t + intercept

            # Clamp to plausible limits
            pred_clamped = pred_raw
            if val_min is not None:
                pred_clamped = max(val_min, pred_clamped)
            if val_max is not None:
                pred_clamped = min(val_max, pred_clamped)

            projections.append({
                "horizon_minutes": hm,
                "projected_value": round(pred_clamped, 2),
                "delta": round(pred_clamped - current_val, 2),
            })

        # Confidence assessment based on R^2 and sample size
        if r_squared >= 0.70 and n >= 15:
            confidence = "MODERATE_HIGH"
        elif r_squared >= 0.40:
            confidence = "MODERATE"
        else:
            confidence = "LOW"

        return {
            "signal": signal_key,
            "status": "forecast_ready",
            "method": "ordinary_least_squares_linear",
            "valid_samples": n,
            "time_window_minutes": round(x[-1] - x[0], 1),
            "slope_per_minute": round(slope, 4),
            "r_squared": max(0.0, r_squared),
            "confidence": confidence,
            "current_value": current_val,
            "projections": projections,
            "disclaimer": (
                "Short-horizon statistical trend projection of observed sensor values. "
                "Assumes continuation of current rate of change; does not account for future "
                "unforeseen ventilation, HVAC, or occupancy interventions."
            ),
        }

    @classmethod
    def generate_all_forecasts(cls, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generates forecasts for primary environmental signals."""
        return {
            "temperature": cls.forecast_signal(
                observations, "temperature_c", val_min=-10.0, val_max=60.0
            ),
            "humidity": cls.forecast_signal(
                observations, "humidity_percent", val_min=0.0, val_max=100.0
            ),
            "mq135_adc_mv": cls.forecast_signal(
                observations, "mq135_adc_mv", val_min=0.0, val_max=3300.0
            ),
        }
