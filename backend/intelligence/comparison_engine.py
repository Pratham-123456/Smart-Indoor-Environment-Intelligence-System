"""SIEIS (Smart Indoor Environmental Intelligence System) - Indoor vs Outdoor Comparison Engine.

Calculates:
- Temperature delta (Delta T in °C) and thermal direction.
- Relative humidity delta (Delta RH in percentage points 'pp').
- Magnus-Tetens dew point (°C) and absolute humidity (g/m³).
- Side-by-side air quality context (without invalid cross-unit subtractions).
- Holistic ventilation assessment (favourable, unfavourable, mixed, indeterminate).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from config import Config


def calculate_magnus_tetens_dew_point(temp_c: Optional[float], rh_pct: Optional[float]) -> Optional[float]:
    """Calculate dew point in °C using standard Magnus-Tetens formulation.

    a = 17.27, b = 237.7°C
    alpha(T, RH) = (a * T) / (b + T) + ln(RH / 100.0)
    T_dew = (b * alpha) / (a - alpha)
    """
    if temp_c is None or rh_pct is None:
        return None
    if rh_pct <= 0.0 or rh_pct > 100.0:
        return None
    if temp_c < -50.0 or temp_c > 80.0:
        return None

    a = 17.27
    b = 237.7
    try:
        alpha = ((a * temp_c) / (b + temp_c)) + math.log(rh_pct / 100.0)
        dew_point = (b * alpha) / (a - alpha)
        return round(dew_point, 1)
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def calculate_absolute_humidity(temp_c: Optional[float], rh_pct: Optional[float]) -> Optional[float]:
    """Calculate volumetric absolute humidity (AH) in grams per cubic meter (g/m³).

    AH = (6.112 * exp((17.67 * T) / (T + 243.5)) * RH * 2.1674) / (273.15 + T)
    """
    if temp_c is None or rh_pct is None:
        return None
    if rh_pct < 0.0 or rh_pct > 100.0:
        return None
    if temp_c < -40.0 or temp_c > 70.0:
        return None

    try:
        vapor_pressure = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
        ah = (vapor_pressure * rh_pct * 2.1674) / (273.15 + temp_c)
        return round(ah, 2)
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def evaluate_ventilation_favourability(
    indoor_temp: Optional[float],
    indoor_rh: Optional[float],
    outdoor_temp: Optional[float],
    outdoor_rh: Optional[float],
    outdoor_aqi: Optional[float],
    indoor_ah: Optional[float],
    outdoor_ah: Optional[float],
    mq135_ratio: Optional[float] = None,
    is_outdoor_stale: bool = False,
) -> tuple[str, str, Dict[str, Any]]:
    """Determine ventilation favourability: 'favourable', 'unfavourable', 'mixed', or 'indeterminate'.

    Returns (rating, explanation, factor_breakdown).
    """
    factors: Dict[str, Any] = {
        "thermal_advantage": "unknown",
        "moisture_advantage": "unknown",
        "outdoor_aqi_status": "unknown",
    }

    if is_outdoor_stale:
        return (
            "indeterminate",
            "Outdoor atmospheric telemetry is stale or unverified. Ventilation decision held indeterminate to prevent admitting unconditioned air or pollutants.",
            factors,
        )

    if indoor_temp is None or outdoor_temp is None or outdoor_aqi is None:
        return (
            "indeterminate",
            "Insufficient telemetry: requires indoor temperature, outdoor temperature, and outdoor AQI.",
            factors,
        )

    # 1. Outdoor Air Quality Filter
    aqi_favourable_max = Config.OUTDOOR_AQI_FAVOURABLE_MAX  # 75
    aqi_unfavourable_min = Config.OUTDOOR_AQI_UNFAVOURABLE_MIN  # 100

    if outdoor_aqi > aqi_unfavourable_min:
        factors["outdoor_aqi_status"] = "unfavourable"
        return (
            "unfavourable",
            f"Outdoor air quality is poor (US AQI {outdoor_aqi:.0f} > 100). Natural ventilation would admit outdoor pollutants.",
            factors,
        )
    elif outdoor_aqi <= aqi_favourable_max:
        factors["outdoor_aqi_status"] = "favourable"
    else:
        # Intermediate 76 - 100
        factors["outdoor_aqi_status"] = "intermediate_moderate"

    # 2. Thermal Analysis
    # Indoor warm: T_in > 24°C
    delta_t = indoor_temp - outdoor_temp
    is_indoor_hot = indoor_temp > 24.0
    is_outdoor_cooler = delta_t >= 1.0
    is_outdoor_hotter = delta_t <= -1.0

    if is_indoor_hot and is_outdoor_cooler:
        factors["thermal_advantage"] = "favourable_cooling"
    elif is_indoor_hot and is_outdoor_hotter:
        factors["thermal_advantage"] = "unfavourable_overheating"
    else:
        factors["thermal_advantage"] = "neutral"

    # 3. Moisture / Absolute Humidity Analysis
    moisture_favourability = "neutral"
    if indoor_ah is not None and outdoor_ah is not None:
        delta_ah = indoor_ah - outdoor_ah
        if indoor_rh is not None and indoor_rh > 60.0:
            # Indoor is humid; opening window helps if outdoor air has lower absolute moisture
            if delta_ah >= 1.5:
                moisture_favourability = "favourable_dehumidifying"
            elif delta_ah <= -1.5:
                moisture_favourability = "unfavourable_moisture_ingress"
        elif indoor_rh is not None and indoor_rh < 35.0:
            # Indoor is dry; outdoor moisture helps if outdoor AH is higher
            if delta_ah <= -1.5:
                moisture_favourability = "favourable_humidifying"
    factors["moisture_advantage"] = moisture_favourability

    # 4. Synthesise Overall Rating
    # If thermal is unfavourable overheating and outdoor AQI isn't stellar
    if factors["thermal_advantage"] == "unfavourable_overheating":
        return (
            "unfavourable",
            f"Outdoor air is hotter ({outdoor_temp:.1f}°C) than the room ({indoor_temp:.1f}°C). Opening windows would exacerbate indoor heat.",
            factors,
        )

    # If outdoor AQI is intermediate (76-100)
    if factors["outdoor_aqi_status"] == "intermediate_moderate":
        if is_indoor_hot and is_outdoor_cooler:
            return (
                "mixed",
                f"Thermal cooling is available (outdoors is {abs(delta_t):.1f}°C cooler), but outdoor air quality is moderate (US AQI {outdoor_aqi:.0f}). Ventilate briefly with caution.",
                factors,
            )
        elif mq135_ratio is not None and mq135_ratio >= 1.4:
            return (
                "mixed",
                f"Indoor air is stale/elevated, while outdoor AQI is moderate (US AQI {outdoor_aqi:.0f}). Consider partial or filtered ventilation.",
                factors,
            )
        else:
            return (
                "mixed",
                f"Outdoor AQI is moderate (US AQI {outdoor_aqi:.0f}). Neither strongly favourable nor critically unfavourable.",
                factors,
            )

    # If outdoor AQI is favourable (<= 75)
    if factors["outdoor_aqi_status"] == "favourable":
        if is_indoor_hot and is_outdoor_cooler:
            return (
                "favourable",
                f"Natural ventilation is favourable: outdoor air is {abs(delta_t):.1f}°C cooler and outdoor air quality is clean (US AQI {outdoor_aqi:.0f}).",
                factors,
            )
        if mq135_ratio is not None and mq135_ratio >= 1.25:
            return (
                "favourable",
                f"Natural ventilation is favourable to flush elevated indoor VOCs/stale air into clean outdoor air (US AQI {outdoor_aqi:.0f}).",
                factors,
            )
        if moisture_favourability == "favourable_dehumidifying":
            return (
                "favourable",
                f"Natural ventilation is favourable: outdoor air has lower absolute moisture and clean air quality (US AQI {outdoor_aqi:.0f}).",
                factors,
            )
        if moisture_favourability == "unfavourable_moisture_ingress":
            return (
                "mixed",
                "Outdoor air is clean, but outdoor humidity is significantly higher than indoors. Ventilation may increase indoor dampness.",
                factors,
            )

        return (
            "favourable",
            f"Outdoor air quality is clean (US AQI {outdoor_aqi:.0f}). Natural ventilation is safe and acceptable.",
            factors,
        )

    return ("mixed", "Mixed environmental indicators.", factors)


def compare_indoor_and_outdoor(
    indoor_telemetry: Dict[str, Any],
    outdoor_data: Dict[str, Any],
    indoor_estimates: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute complete comparison between validated indoor telemetry and outdoor conditions.

    Returns structured comparison schema compliant with Section 11 of the specification.
    """
    indoor_temp = indoor_telemetry.get("temperature")
    indoor_rh = indoor_telemetry.get("humidity")
    outdoor_temp = outdoor_data.get("temperature_c")
    outdoor_rh = outdoor_data.get("relative_humidity_pct")
    outdoor_aqi = outdoor_data.get("aqi")

    # 1. Temperature delta
    delta_temp_c: Optional[float] = None
    thermal_direction: str = "indeterminate"
    if indoor_temp is not None and outdoor_temp is not None:
        delta_temp_c = round(float(indoor_temp) - float(outdoor_temp), 1)
        if delta_temp_c >= 1.0:
            thermal_direction = "outdoor_cooler"
        elif delta_temp_c <= -1.0:
            thermal_direction = "outdoor_warmer"
        else:
            thermal_direction = "thermal_equilibrium"

    # 2. Relative humidity delta (in percentage points 'pp')
    delta_rh_pp: Optional[float] = None
    rh_direction: str = "indeterminate"
    if indoor_rh is not None and outdoor_rh is not None:
        delta_rh_pp = round(float(indoor_rh) - float(outdoor_rh), 1)
        if delta_rh_pp >= 5.0:
            rh_direction = "indoor_more_humid"
        elif delta_rh_pp <= -5.0:
            rh_direction = "outdoor_more_humid"
        else:
            rh_direction = "humidity_equilibrium"

    # 3. Psychrometrics: Dew point & Absolute humidity
    indoor_dew_point = calculate_magnus_tetens_dew_point(indoor_temp, indoor_rh)
    outdoor_dew_point = calculate_magnus_tetens_dew_point(outdoor_temp, outdoor_rh)
    indoor_ah = calculate_absolute_humidity(indoor_temp, indoor_rh)
    outdoor_ah = calculate_absolute_humidity(outdoor_temp, outdoor_rh)

    delta_ah_gm3: Optional[float] = None
    if indoor_ah is not None and outdoor_ah is not None:
        delta_ah_gm3 = round(indoor_ah - outdoor_ah, 2)

    # MQ-135 ratio if available
    mq135_ratio = indoor_telemetry.get("mq135_baseline_ratio")
    if mq135_ratio is None:
        pin_mv = indoor_telemetry.get("mq135_pin_mv")
        baseline_mv = indoor_telemetry.get("mq135_baseline_mv")
        if pin_mv is not None and baseline_mv is not None and baseline_mv > 0:
            mq135_ratio = round(pin_mv / baseline_mv, 2)

    # 4. Ventilation Assessment
    is_outdoor_stale = outdoor_data.get("is_stale", False) or outdoor_data.get("freshness_status") in ("stale", "stale_cached", "stale_observation", "offline", "unavailable")
    vent_rating, vent_explanation, vent_factors = evaluate_ventilation_favourability(
        indoor_temp=indoor_temp,
        indoor_rh=indoor_rh,
        outdoor_temp=outdoor_temp,
        outdoor_rh=outdoor_rh,
        outdoor_aqi=outdoor_aqi,
        indoor_ah=indoor_ah,
        outdoor_ah=outdoor_ah,
        mq135_ratio=mq135_ratio,
        is_outdoor_stale=is_outdoor_stale,
    )

    # Air quality side-by-side presentation
    pm25_est = indoor_estimates.get("pm25", {}) if indoor_estimates else {}
    co2_est = indoor_estimates.get("co2", {}) if indoor_estimates else {}

    return {
        "status": "ok",
        "calculated_at": datetime.now(timezone.utc).isoformat(),
        "temperature": {
            "indoor_c": indoor_temp,
            "outdoor_c": outdoor_temp,
            "delta_c": delta_temp_c,
            "direction": thermal_direction,
            "note": "Delta T does not prove thermal envelope insulation efficiency.",
        },
        "humidity": {
            "indoor_rh_pct": indoor_rh,
            "outdoor_rh_pct": outdoor_rh,
            "delta_rh_pp": delta_rh_pp,
            "unit": "pp",
            "direction": rh_direction,
            "psychrometrics": {
                "method": "magnus_tetens",
                "indoor_dew_point_c": indoor_dew_point,
                "outdoor_dew_point_c": outdoor_dew_point,
                "indoor_absolute_humidity_gm3": indoor_ah,
                "outdoor_absolute_humidity_gm3": outdoor_ah,
                "delta_absolute_humidity_gm3": delta_ah_gm3,
            },
        },
        "air_quality_side_by_side": {
            "indoor_mq135_ratio": mq135_ratio,
            "indoor_mq135_ready": indoor_telemetry.get("mq135_is_ready", False),
            "indoor_pm25_estimate_ugm3": pm25_est.get("value"),
            "indoor_co2_estimate_ppm": co2_est.get("value"),
            "outdoor_aqi": outdoor_aqi,
            "outdoor_aqi_scale": outdoor_data.get("aqi_scale", "us_aqi"),
            "outdoor_aqi_category": outdoor_data.get("aqi_category", "Unknown"),
            "outdoor_pm25": outdoor_data.get("pm25"),
            "attribution": outdoor_data.get("attribution", "Open-Meteo.com"),
            "disclaimer": "Never subtract or divide incompatible units (e.g. AQI index points vs mV or ppm).",
        },
        "ventilation_assessment": {
            "rating": vent_rating,  # favourable, unfavourable, mixed, indeterminate
            "explanation": vent_explanation,
            "factors": vent_factors,
        },
    }
