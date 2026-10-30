"""SIEIS Trend Analysis Module.

Calculates moving averages, rates of change per minute, and direction classifications
for physical and relative environmental measurements.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class TrendAnalyzer:
    """Analyzes historical time-series observations to extract trends and rates-of-change."""

    @staticmethod
    def _parse_iso(iso_str: str) -> Optional[float]:
        """Parses an ISO 8601 string to a Unix timestamp in seconds."""
        try:
            # Replace Z with +00:00 for python fromisoformat
            cleaned = iso_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            return dt.timestamp()
        except Exception:
            return None

    @classmethod
    def calculate_signal_trend(
        cls,
        observations: List[Dict[str, Any]],
        signal_key: str,
        stability_threshold: float = 0.05,
    ) -> Dict[str, Any]:
        """Calculates moving average, rate-of-change per minute, and trend direction.

        Args:
            observations: Chronologically sorted observations (oldest to newest).
            signal_key: Key in observation dict (e.g., 'temperature_c', 'humidity_percent', 'mq135_adc_mv').
            stability_threshold: Magnitude below which rate is considered 'STABLE'.
        """
        # Extract valid points (timestamp_sec, value)
        points: List[tuple[float, float]] = []
        for obs in observations:
            val = obs.get(signal_key)
            ts_str = obs.get("received_at")
            if val is not None and ts_str:
                ts = cls._parse_iso(ts_str)
                if ts is not None:
                    points.append((ts, float(val)))

        if not points:
            return {
                "signal": signal_key,
                "status": "NO_DATA",
                "current": None,
                "sma_short": None,
                "sma_long": None,
                "rate_per_min": None,
                "direction": "UNKNOWN",
            }

        values = [p[1] for p in points]
        current_val = round(values[-1], 2)

        # Simple moving averages
        sma_short = round(sum(values[-5:]) / len(values[-5:]), 2) if len(values) >= 1 else current_val
        sma_long = round(sum(values[-15:]) / len(values[-15:]), 2) if len(values) >= 5 else None

        # Rate of change per minute using first and last valid points in window (up to last 10 points)
        rate_per_min: Optional[float] = None
        direction = "STABLE"

        recent_window = points[-10:] if len(points) >= 2 else []
        if len(recent_window) >= 2:
            t_start, v_start = recent_window[0]
            t_end, v_end = recent_window[-1]
            dt_sec = t_end - t_start

            if dt_sec >= 5.0:  # Avoid division by micro intervals
                dt_min = dt_sec / 60.0
                rate_per_min = round((v_end - v_start) / dt_min, 3)

                if rate_per_min > stability_threshold:
                    direction = "RISING"
                elif rate_per_min < -stability_threshold:
                    direction = "FALLING"
                else:
                    direction = "STABLE"

        return {
            "signal": signal_key,
            "status": "OK",
            "current": current_val,
            "sma_short": sma_short,
            "sma_long": sma_long,
            "rate_per_min": rate_per_min,
            "direction": direction,
            "sample_count": len(points),
        }

    @classmethod
    def analyze_all_trends(cls, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Computes trend metrics across all active environmental signals."""
        return {
            "temperature": cls.calculate_signal_trend(
                observations, "temperature_c", stability_threshold=0.08
            ),
            "humidity": cls.calculate_signal_trend(
                observations, "humidity_percent", stability_threshold=0.20
            ),
            "mq135_adc_mv": cls.calculate_signal_trend(
                observations, "mq135_adc_mv", stability_threshold=2.0
            ),
            "light_raw": cls.calculate_signal_trend(
                observations, "light_raw", stability_threshold=10.0
            ),
            "sound_swing": cls.calculate_signal_trend(
                observations, "sound_swing", stability_threshold=50.0
            ),
        }
