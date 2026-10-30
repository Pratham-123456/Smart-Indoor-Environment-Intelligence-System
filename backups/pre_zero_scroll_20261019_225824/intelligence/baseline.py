"""SIEIS MQ-135 Rolling Baseline Manager.

Maintains an adaptive yet stable rolling baseline for the MQ-135 relative gas response.
Strictly excludes warmup period, startup transients, and outlier spikes to ensure
baseline integrity.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config import Config

logger = logging.getLogger("sieis.baseline")


class MQ135BaselineManager:
    """Manages computation and tracking of the MQ-135 baseline voltage."""

    def __init__(self, db: Any, window_size: int = Config.MQ135_BASELINE_WINDOW_SIZE):
        self.db = db
        self.window_size = window_size

    def update_baseline(
        self, device_id: str, current_time_iso: str
    ) -> Optional[float]:
        """Computes and records an updated rolling baseline for the given device.

        Returns:
            Current baseline in millivolts, or None if insufficient valid data.
        """
        # Fetch the most recent observations for this device
        recent_obs: List[Dict[str, Any]] = self.db.get_observations(
            device_id=device_id, limit=self.window_size * 2, valid_only=True
        )

        valid_readings: List[int] = []
        for obs in recent_obs:
            # Exclude readings from warmup phase or unknown status
            status = obs.get("mq135_status", "")
            uptime = obs.get("uptime_ms", 0) or 0
            mv = obs.get("mq135_adc_mv")

            if status == "ready" and uptime >= (Config.MQ135_WARMUP_SECONDS * 1000) and mv is not None:
                if Config.MQ135_PIN_MV_MIN <= mv <= Config.MQ135_PIN_MV_MAX:
                    valid_readings.append(mv)

        # Require at least 5 valid stable samples to establish a preliminary baseline
        if len(valid_readings) < 5:
            logger.debug(
                f"Device {device_id} has {len(valid_readings)} valid MQ-135 readings; "
                f"need at least 5 to calculate baseline."
            )
            # Check if an earlier baseline was already stored
            latest_stored = self.db.get_latest_baseline(device_id)
            return float(latest_stored["baseline_mv"]) if latest_stored else None

        # Take the most recent `window_size` readings
        samples = valid_readings[-self.window_size :]

        # Robust baseline: use 20% trimmed mean to prevent sudden smoke/gas spikes
        # from corrupting the baseline upwards immediately.
        sorted_samples = sorted(samples)
        trim_count = max(1, int(len(sorted_samples) * 0.2)) if len(sorted_samples) >= 10 else 0
        if trim_count > 0:
            trimmed = sorted_samples[trim_count : len(sorted_samples) - trim_count]
        else:
            trimmed = sorted_samples

        calculated_baseline = round(sum(trimmed) / len(trimmed), 1)

        # Store baseline point
        self.db.record_baseline(
            device_id=device_id,
            calculated_at=current_time_iso,
            baseline_mv=calculated_baseline,
            sample_count=len(samples),
            window_size=self.window_size,
        )

        logger.info(
            f"Updated baseline for {device_id}: {calculated_baseline} mV "
            f"(from {len(samples)} samples, trimmed {trim_count})"
        )
        return calculated_baseline

    def get_current_baseline(self, device_id: str) -> Optional[float]:
        """Retrieves the latest recorded baseline for the device."""
        latest = self.db.get_latest_baseline(device_id)
        if latest and "baseline_mv" in latest:
            return float(latest["baseline_mv"])
        return None
