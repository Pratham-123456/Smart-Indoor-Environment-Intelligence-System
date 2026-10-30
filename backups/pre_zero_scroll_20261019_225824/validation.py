"""SIEIS Payload Validation Layer.

Validates incoming JSON packets from ESP32 nodes, enforcing schema contracts,
physical range plausibility, type integrity, and sensor operational status.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from config import Config


class ValidationError(Exception):
    """Raised when an incoming packet cannot be accepted."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class PayloadValidator:
    """Validates ESP32 sensor JSON payloads according to SIEIS specifications."""

    @staticmethod
    def _is_valid_number(val: Any) -> bool:
        """Checks if a value is a valid finite float or int (not NaN or Inf)."""
        if val is None:
            return True
        if isinstance(val, (int, float)):
            return not (math.isnan(val) or math.isinf(val))
        return False

    @classmethod
    def validate_incoming_packet(
        cls, payload: Any
    ) -> Tuple[Dict[str, Any], List[str], bool]:
        """Validates incoming JSON payload.

        Returns:
            sanitized_data (Dict[str, Any]): Normalized, safe dictionary.
            flags (List[str]): List of diagnostic or validation flags.
            is_valid (bool): True if physically plausible and usable for scoring.

        Raises:
            ValidationError: If packet is fundamentally malformed or missing device_id.
        """
        if not isinstance(payload, dict):
            raise ValidationError("Payload must be a valid JSON object.")

        # 1. Mandatory Device ID
        device_id = payload.get("device_id")
        if not device_id or not isinstance(device_id, str) or not device_id.strip():
            raise ValidationError("Field 'device_id' is required and must be a non-empty string.")

        flags: List[str] = []
        is_usable = True

        # 2. Metadata & Sequence
        seq_num = payload.get("sequence_number")
        if seq_num is not None:
            if not isinstance(seq_num, int) or seq_num < 0:
                flags.append("INVALID_SEQUENCE_NUMBER")
                seq_num = None

        uptime_ms = payload.get("uptime_ms")
        if uptime_ms is not None:
            if not isinstance(uptime_ms, int) or uptime_ms < 0:
                flags.append("INVALID_UPTIME")
                uptime_ms = None

        firmware_ver = payload.get("firmware_version")
        if firmware_ver and not isinstance(firmware_ver, str):
            firmware_ver = str(firmware_ver)

        # 3. DHT22: Temperature (-20 to 70 C)
        raw_temp = payload.get("temperature_c")
        temp_c: Optional[float] = None
        if raw_temp is not None:
            if not cls._is_valid_number(raw_temp):
                flags.append("TEMP_NAN_OR_INF")
                is_usable = False
            else:
                t = float(raw_temp)
                if Config.TEMP_MIN_C <= t <= Config.TEMP_MAX_C:
                    temp_c = round(t, 2)
                else:
                    flags.append(f"TEMP_OUT_OF_BOUNDS({t})")
                    is_usable = False
                    temp_c = round(t, 2)
        else:
            flags.append("TEMP_MISSING")

        # 4. DHT22: Relative Humidity (0 to 100 %)
        raw_hum = payload.get("humidity_percent")
        hum_pct: Optional[float] = None
        if raw_hum is not None:
            if not cls._is_valid_number(raw_hum):
                flags.append("HUM_NAN_OR_INF")
                is_usable = False
            else:
                h = float(raw_hum)
                if Config.HUMIDITY_MIN <= h <= Config.HUMIDITY_MAX:
                    hum_pct = round(h, 2)
                else:
                    flags.append(f"HUM_OUT_OF_BOUNDS({h})")
                    is_usable = False
                    hum_pct = round(h, 2)
        else:
            flags.append("HUM_MISSING")

        # 5. LDR: Raw ADC (0 - 4095) & Label
        raw_light = payload.get("light_raw")
        light_raw: Optional[int] = None
        if raw_light is not None:
            if isinstance(raw_light, (int, float)) and cls._is_valid_number(raw_light):
                lr = int(raw_light)
                if Config.LDR_MIN_RAW <= lr <= Config.LDR_MAX_RAW:
                    light_raw = lr
                else:
                    flags.append(f"LDR_OUT_OF_BOUNDS({lr})")
                    light_raw = lr
            else:
                flags.append("LDR_INVALID_TYPE")

        light_label = payload.get("light_label")
        if light_label not in ("dark", "dim", "bright"):
            if light_raw is not None:
                # Derive label if omitted or non-standard
                if light_raw < Config.LDR_DARK_THRESHOLD:
                    light_label = "dark"
                elif light_raw < Config.LDR_DIM_THRESHOLD:
                    light_label = "dim"
                else:
                    light_label = "bright"
            else:
                light_label = "unknown"

        # 6. MQ-135 Gas Sensor (ADC mV and Sensor AO mV)
        raw_mq_pin = payload.get("mq135_adc_mv")
        mq_pin_mv: Optional[int] = None
        if raw_mq_pin is not None:
            if isinstance(raw_mq_pin, (int, float)) and cls._is_valid_number(raw_mq_pin):
                mv = int(raw_mq_pin)
                if Config.MQ135_PIN_MV_MIN <= mv <= Config.MQ135_PIN_MV_MAX:
                    mq_pin_mv = mv
                else:
                    flags.append(f"MQ135_MV_OUT_OF_BOUNDS({mv})")
                    mq_pin_mv = mv
            else:
                flags.append("MQ135_PIN_INVALID_TYPE")

        raw_mq_sensor = payload.get("mq135_sensor_mv")
        mq_sensor_mv: Optional[int] = None
        if raw_mq_sensor is not None:
            if isinstance(raw_mq_sensor, (int, float)) and cls._is_valid_number(raw_mq_sensor):
                mq_sensor_mv = int(raw_mq_sensor)
        elif mq_pin_mv is not None:
            # 1.5x divider conversion for 10k:20k network
            mq_sensor_mv = int(mq_pin_mv * 1.5)

        mq_status = str(payload.get("mq135_status", "unknown")).lower()
        if mq_status not in ("ready", "warming_up", "conditioning", "error", "unknown"):
            mq_status = "unknown"

        # 7. Sound Module (LM393 swing & DO)
        raw_swing = payload.get("sound_swing")
        sound_swing: Optional[int] = None
        if raw_swing is not None:
            if isinstance(raw_swing, (int, float)) and cls._is_valid_number(raw_swing):
                sw = int(raw_swing)
                if Config.SOUND_SWING_MIN <= sw <= Config.SOUND_SWING_MAX:
                    sound_swing = sw
                else:
                    flags.append(f"SOUND_SWING_OUT_OF_BOUNDS({sw})")
                    sound_swing = sw

        raw_do = payload.get("sound_do")
        sound_do: Optional[int] = None
        if raw_do is not None:
            if raw_do in (0, 1, "0", "1"):
                sound_do = int(raw_do)
            else:
                flags.append("SOUND_DO_INVALID")

        sensor_status = payload.get("sensor_status", {})
        if not isinstance(sensor_status, dict):
            sensor_status = {}

        if not flags:
            flags.append("OK")

        sanitized_record = {
            "device_id": device_id.strip(),
            "firmware_version": firmware_ver or "1.0.0",
            "sequence_number": seq_num,
            "uptime_ms": uptime_ms,
            "temperature_c": temp_c,
            "humidity_percent": hum_pct,
            "light_raw": light_raw,
            "light_label": light_label,
            "mq135_adc_mv": mq_pin_mv,
            "mq135_sensor_mv": mq_sensor_mv,
            "mq135_status": mq_status,
            "sound_swing": sound_swing,
            "sound_do": sound_do,
            "sensor_status": sensor_status,
            "device_timestamp": payload.get("timestamp"),
            "validation_flags": ";".join(flags),
            "is_valid": is_usable,
        }

        return sanitized_record, flags, is_usable
