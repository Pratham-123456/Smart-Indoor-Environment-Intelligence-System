"""SIEIS (Smart Indoor Environmental Intelligence System) - Indoor Estimation Module.

Provides deterministic experimental heuristic proxy estimators for indoor PM2.5 and CO2.

ESSENTIAL ACCURACY DISCLOSURES:
- These are experimental estimates because the hardware does not include dedicated
  optical PM2.5 or NDIR CO2 measurement sensors.
- Uncalibrated heuristic outputs are demonstration estimates; their real-world accuracy is unknown.
- The estimates are NOT validated direct measurements.
- The MQ-135 signal is NOT uniquely convertible into CO2 ppm or PM2.5 concentration with
  the information currently available.
- A clean-air baseline and environmental proxy features do not establish scientific accuracy.
- Actual validation requires paired reference-sensor data.
- NEVER trigger a high-confidence health or safety alarm solely from these experimental estimates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from config import Config


MODEL_VERSION = "1.0.0"
MODEL_NAME = "sieis_heuristic_proxy"
METHOD_HEURISTIC = "heuristic_proxy"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_indoor_pm25(
    indoor_temp_c: Optional[float],
    indoor_rh_pct: Optional[float],
    mq135_pin_mv: Optional[float],
    mq135_baseline_mv: Optional[float],
    mq135_is_ready: bool = False,
    outdoor_pm25: Optional[float] = None,
    outdoor_aqi: Optional[float] = None,
    sound_swing: Optional[int] = None,
    ldr_raw: Optional[int] = None,
) -> Dict[str, Any]:
    """Estimate indoor PM2.5 using a deterministic heuristic proxy model.

    Combines outdoor particulate baseline (when available from API) or a standard
    indoor fallback baseline, positive MQ-135 baseline excursions, and humidity
    hygroscopic growth adjustment factors. Clamped to Config.PM25_ESTIMATE_MIN .. Config.PM25_ESTIMATE_MAX.

    Returns full metadata schema with uncertainty disclosures.
    """
    now_str = _iso_now()
    metadata_limitations = (
        "Proxy estimate only. The system lacks an optical laser particle counter (e.g. PMS5003). "
        "Outputs must not be used for regulatory, clinical, or life-safety applications."
    )

    # Validate essential inputs: need at least valid MQ-135 pin voltage and humidity
    if (
        mq135_pin_mv is None
        or indoor_rh_pct is None
        or mq135_pin_mv < Config.MQ135_PIN_MV_MIN
        or mq135_pin_mv > Config.MQ135_PIN_MV_MAX
        or indoor_rh_pct < Config.HUMIDITY_MIN
        or indoor_rh_pct > Config.HUMIDITY_MAX
    ):
        return {
            "value": None,
            "unit": "µg/m³",
            "label": "EXPERIMENTAL ESTIMATE",
            "status": "insufficient_data",
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "method": METHOD_HEURISTIC,
            "calibration_status": "uncalibrated_heuristic",
            "confidence_level": "none",
            "uncertainty_note": "Essential sensor inputs (MQ-135 or DHT22 RH) are missing or out of valid bounds.",
            "input_readiness": {
                "has_mq135": mq135_pin_mv is not None,
                "has_rh": indoor_rh_pct is not None,
                "mq135_ready": mq135_is_ready,
                "has_outdoor_pm25": outdoor_pm25 is not None,
            },
            "data_quality": {
                "mq135_baseline_valid": mq135_baseline_mv is not None and mq135_baseline_mv > 0,
                "outdoor_source_available": outdoor_pm25 is not None,
            },
            "limitations": metadata_limitations,
            "calculated_at": now_str,
        }

    # Determine baseline particulate context
    if outdoor_pm25 is not None and 0.0 <= outdoor_pm25 <= 1000.0:
        # Typical indoor/outdoor penetration ratio in closed environments ~0.55 - 0.70
        base_pm25 = max(5.0, outdoor_pm25 * 0.60)
        baseline_source = "outdoor_api_penetration"
    else:
        # Standard indoor clean/nominal background default
        base_pm25 = 15.0
        baseline_source = "nominal_indoor_default"

    # MQ-135 gas excursion addition (aerosol / smoke / cooking proxy)
    gas_component = 0.0
    calibration_status = "uncalibrated_heuristic"
    confidence = "low"

    if mq135_is_ready and mq135_baseline_mv is not None and mq135_baseline_mv > 0:
        ratio = mq135_pin_mv / mq135_baseline_mv
        if ratio > 1.0:
            # Positive excursion increases estimated PM2.5
            gas_component = (ratio - 1.0) * 35.0
        confidence = "low_to_moderate"
    else:
        # Baseline warming up or unconditioned
        calibration_status = "uncalibrated_warmup"
        # Bounded estimate based on raw pin voltage (approx clean ~300-500mV)
        if mq135_pin_mv > 600:
            gas_component = ((mq135_pin_mv - 600) / 1000.0) * 40.0
        confidence = "low"

    # Humidity adjustment: hygroscopic particle swelling above 60% RH
    humidity_adj = 0.0
    if indoor_rh_pct > 60.0:
        humidity_adj = ((indoor_rh_pct - 60.0) / 40.0) * 8.0
    elif indoor_rh_pct < 30.0:
        humidity_adj = -2.0

    raw_estimate = base_pm25 + gas_component + humidity_adj
    clamped_value = round(max(Config.PM25_ESTIMATE_MIN, min(Config.PM25_ESTIMATE_MAX, raw_estimate)), 1)

    uncertainty = (
        f"Uncalibrated proxy estimate (derived from {baseline_source}, MQ-135 excursion, and RH context). "
        "True indoor PM2.5 mass concentration requires a light-scattering or gravimetric particulate counter."
    )

    return {
        "value": clamped_value,
        "unit": "µg/m³",
        "label": "EXPERIMENTAL ESTIMATE",
        "status": "ok",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "method": METHOD_HEURISTIC,
        "calibration_status": calibration_status,
        "confidence_level": confidence,
        "uncertainty_note": uncertainty,
        "input_readiness": {
            "has_mq135": True,
            "has_rh": True,
            "mq135_ready": mq135_is_ready,
            "has_outdoor_pm25": outdoor_pm25 is not None,
        },
        "data_quality": {
            "baseline_source": baseline_source,
            "mq135_baseline_valid": mq135_baseline_mv is not None and mq135_baseline_mv > 0,
            "outdoor_source_available": outdoor_pm25 is not None,
        },
        "limitations": metadata_limitations,
        "calculated_at": now_str,
    }


def estimate_indoor_co2(
    mq135_pin_mv: Optional[float],
    mq135_baseline_mv: Optional[float],
    mq135_is_ready: bool = False,
    indoor_temp_c: Optional[float] = None,
    indoor_rh_pct: Optional[float] = None,
    sound_swing: Optional[int] = None,
) -> Dict[str, Any]:
    """Estimate indoor CO2 concentration using a deterministic heuristic proxy model.

    Assumes a documented nominal atmospheric baseline of Config.CO2_NOMINAL_ATMOSPHERIC_BASELINE (420 ppm).
    Calculates proxy accumulation from MQ-135 relative elevation above baseline, with contextual
    temperature/humidity compensation. Clamped to Config.CO2_ESTIMATE_MIN .. Config.CO2_ESTIMATE_MAX.

    Returns full metadata schema with prominent uncertainty disclosures.
    """
    now_str = _iso_now()
    metadata_limitations = (
        "Proxy estimate only. The system uses a metal-oxide MQ-135 sensor without an optical NDIR "
        "chamber. The MQ-135 responds non-selectively to CO2, VOCs, NH3, CO, and humidity. "
        "Nominal 420 ppm atmospheric reference is assumed, not measured."
    )

    # Missing or out-of-bounds MQ-135 reading
    if (
        mq135_pin_mv is None
        or mq135_pin_mv < Config.MQ135_PIN_MV_MIN
        or mq135_pin_mv > Config.MQ135_PIN_MV_MAX
    ):
        return {
            "value": None,
            "unit": "ppm",
            "label": "EXPERIMENTAL ESTIMATE",
            "status": "insufficient_data",
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "method": METHOD_HEURISTIC,
            "calibration_status": "uncalibrated_heuristic",
            "confidence_level": "none",
            "uncertainty_note": "MQ-135 gas sensor signal is missing or outside valid physical ADC voltage bounds.",
            "input_readiness": {
                "has_mq135": mq135_pin_mv is not None,
                "mq135_ready": mq135_is_ready,
            },
            "data_quality": {
                "mq135_baseline_valid": mq135_baseline_mv is not None and mq135_baseline_mv > 0,
            },
            "limitations": metadata_limitations,
            "calculated_at": now_str,
        }

    nominal_baseline = Config.CO2_NOMINAL_ATMOSPHERIC_BASELINE
    calibration_status = "uncalibrated_heuristic"
    confidence = "low"

    if mq135_is_ready and mq135_baseline_mv is not None and mq135_baseline_mv > 0:
        ratio = mq135_pin_mv / mq135_baseline_mv
        confidence = "low_to_moderate"

        # Heuristic power-law proxy: CO2 elevation scaling with gas sensor ratio
        if ratio <= 1.0:
            co2_est = nominal_baseline
        else:
            # Elevation above clean atmospheric baseline: 420 + (ratio - 1.0)^1.4 * 650
            elevation = ((ratio - 1.0) ** 1.35) * 750.0
            co2_est = nominal_baseline + elevation
    else:
        calibration_status = "uncalibrated_warmup"
        confidence = "low"
        # During warm-up or unconditioned baseline, use fallback curve relative to nominal 350mV clean air
        nominal_clean_mv = 350.0
        ratio = max(1.0, mq135_pin_mv / nominal_clean_mv)
        co2_est = nominal_baseline + (ratio - 1.0) * 400.0

    # Temperature / Humidity minor cross-sensitivity compensation if available
    # MQ-135 resistance shifts slightly with temperature and humidity
    if indoor_temp_c is not None and indoor_rh_pct is not None:
        # Standard calibration reference condition: 20°C, 65% RH
        temp_delta = indoor_temp_c - 20.0
        rh_delta = indoor_rh_pct - 65.0
        # Environmental correction factor
        correction_factor = 1.0 - (0.005 * temp_delta) - (0.002 * rh_delta)
        co2_est = co2_est * max(0.85, min(1.15, correction_factor))

    clamped_value = round(max(Config.CO2_ESTIMATE_MIN, min(Config.CO2_ESTIMATE_MAX, co2_est)), 0)

    uncertainty = (
        f"Uncalibrated proxy estimate assuming nominal {nominal_baseline} ppm atmospheric clean air baseline. "
        "Cross-sensitive to indoor VOCs, odours, and relative humidity. Not a certified NDIR measurement."
    )

    return {
        "value": int(clamped_value),
        "unit": "ppm",
        "label": "EXPERIMENTAL ESTIMATE",
        "status": "ok",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "method": METHOD_HEURISTIC,
        "calibration_status": calibration_status,
        "confidence_level": confidence,
        "uncertainty_note": uncertainty,
        "input_readiness": {
            "has_mq135": True,
            "mq135_ready": mq135_is_ready,
            "has_temp_hum_context": indoor_temp_c is not None and indoor_rh_pct is not None,
        },
        "data_quality": {
            "mq135_baseline_valid": mq135_baseline_mv is not None and mq135_baseline_mv > 0,
        },
        "limitations": metadata_limitations,
        "calculated_at": now_str,
    }
