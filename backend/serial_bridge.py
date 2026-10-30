"""SIEIS USB Serial Ingestion Bridge.

Allows direct telemetry acquisition over USB Serial (e.g. COM4 at 115200 baud).
Parses both JSON packets from SIEIS_ESP32.ino and legacy text diagnostics
from sieis_sensors.ino, piping readings directly into the backend database.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("sieis.serial_bridge")

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class SerialBridge:
    """Manages background USB Serial telemetry reading from ESP32."""

    def __init__(self, port: str = "COM4", baud: int = 115200, on_packet: Optional[Callable[[dict], Any]] = None):
        self.port = port
        self.baud = baud
        self.on_packet = on_packet
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._ser: Optional[Any] = None
        self._seq = 0
        self.last_packet_time: Optional[float] = None
        self.packets_received: int = 0
        self.last_error: Optional[str] = None

    @property
    def is_streaming(self) -> bool:
        """Returns True if a packet was received within the last 15 seconds."""
        if not self.is_running or not self.last_packet_time:
            return False
        return (time.time() - self.last_packet_time) < 15.0

    @staticmethod
    def list_ports() -> list[str]:
        """Returns a list of available serial port names."""
        if not SERIAL_AVAILABLE:
            return []
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def start(self) -> bool:
        """Starts background serial reader thread."""
        if not SERIAL_AVAILABLE:
            logger.warning("pyserial is not installed.")
            return False
        if self.is_running:
            return True

        self.is_running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info(f"Started Serial Bridge on {self.port} @ {self.baud} baud.")
        return True

    def stop(self) -> None:
        """Stops background serial reader."""
        self.is_running = False
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
        logger.info("Stopped Serial Bridge.")

    def restart(self, port: Optional[str] = None) -> bool:
        """Restarts the serial bridge, optionally switching to a new port."""
        self.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if port:
            self.port = port
        return self.start()

    def reset_esp32(self) -> bool:
        """Sends a clean hardware reset pulse to reboot the ESP32."""
        if not self._ser or not hasattr(self._ser, "is_open") or not self._ser.is_open:
            return False
        try:
            self._ser.dtr = False
            self._ser.rts = True
            time.sleep(0.15)
            self._ser.rts = False
            time.sleep(0.1)
            logger.info(f"Sent hardware reset pulse to ESP32 on {self.port}.")
            return True
        except Exception as e:
            logger.warning(f"Could not pulse reset on {self.port}: {e}")
            return False

    def get_status(self) -> dict[str, Any]:
        """Returns bridge operational metrics."""
        now = time.time()
        age = round(now - self.last_packet_time, 1) if self.last_packet_time else None
        return {
            "port": self.port,
            "baud": self.baud,
            "is_running": self.is_running,
            "is_streaming": self.is_streaming,
            "packets_received": self.packets_received,
            "last_packet_time": self.last_packet_time,
            "seconds_since_last_packet": age,
            "last_error": self.last_error,
        }

    def _read_loop(self) -> None:
        """Continuous reading loop."""
        while self.is_running:
            try:
                logger.info(f"Opening serial port {self.port} @ {self.baud}...")
                s = serial.Serial()
                s.port = self.port
                s.baudrate = self.baud
                s.timeout = 2.0
                # Explicitly clear DTR/RTS before open to avoid trapping ESP32 in bootloader or reset
                s.dtr = False
                s.rts = False
                s.open()
                self._ser = s
                self.last_error = None
                time.sleep(0.5)
                logger.info(f"Successfully opened {self.port} for hardware telemetry.")

                while self.is_running:
                    try:
                        line_bytes = self._ser.readline()
                    except Exception as read_err:
                        self.last_error = str(read_err)
                        logger.warning(f"Error reading from {self.port}: {read_err}")
                        break

                    if not line_bytes:
                        continue

                    line = line_bytes.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    # Try parsing as JSON first
                    packet = self._try_parse_json(line)
                    if not packet:
                        # Fallback to parsing legacy text format from sieis_sensors.ino
                        self._seq += 1
                        packet = self._try_parse_text(line, self._seq)

                    if packet:
                        self.last_packet_time = time.time()
                        self.packets_received += 1
                        if self.on_packet:
                            self.on_packet(packet)

            except Exception as e:
                self.last_error = str(e)
                logger.warning(f"Serial port on {self.port}: {e}. Retrying in 3 seconds...")
                time.sleep(3.0)
            finally:
                if self._ser:
                    try:
                        self._ser.close()
                    except Exception:
                        pass
                    self._ser = None

    @staticmethod
    def _try_parse_json(line: str) -> Optional[dict]:
        """Checks if line contains a valid JSON telemetry object."""
        if "[JSON]" in line:
            line = line.split("[JSON]", 1)[1].strip()
        if not (line.startswith("{") and line.endswith("}")):
            return None
        try:
            data = json.loads(line)
            if "device_id" in data:
                return data
        except Exception:
            pass
        return None

    @staticmethod
    def _try_parse_text(line: str, seq_num: int = 1) -> Optional[dict]:
        """Parses legacy text line from sieis_sensors.ino into standard telemetry schema.

        Example line:
        Temp=24.1C Hum=50.2% | Light=520 (dim) | MQ135 pin=460mV AO~690mV (warming up) | Sound swing=180 DO=0
        """
        if "Light=" not in line and "Temp=" not in line:
            return None

        packet: dict[str, Any] = {
            "device_id": "esp32-sieis-01",
            "firmware_version": "1.0.0-hardware",
            "sequence_number": seq_num,
            "uptime_ms": int(time.time() * 1000) % 10000000,
            "sensor_status": {"transport": "usb_serial"},
        }

        # Temperature & Humidity
        temp_m = re.search(r"Temp=([\d\.\-]+)C", line)
        hum_m = re.search(r"Hum=([\d\.\-]+)%", line)
        if temp_m:
            packet["temperature_c"] = float(temp_m.group(1))
        if hum_m:
            packet["humidity_percent"] = float(hum_m.group(1))

        # Light
        light_m = re.search(r"Light=(\d+)\s*\(([^)]+)\)", line)
        if light_m:
            packet["light_raw"] = int(light_m.group(1))
            packet["light_label"] = light_m.group(2).strip().lower()

        # MQ-135
        mq_pin_m = re.search(r"MQ135 pin=(\d+)mV", line)
        mq_ao_m = re.search(r"AO~?(\d+)mV", line)
        is_warming = "warming up" in line.lower()
        if mq_pin_m:
            packet["mq135_adc_mv"] = int(mq_pin_m.group(1))
        if mq_ao_m:
            packet["mq135_sensor_mv"] = int(mq_ao_m.group(1))
        packet["mq135_status"] = "warming_up" if is_warming else "ready"

        # Sound
        swing_m = re.search(r"Sound swing=(\d+)", line)
        do_m = re.search(r"DO=(\d+)", line)
        if swing_m:
            packet["sound_swing"] = int(swing_m.group(1))
        if do_m:
            packet["sound_do"] = int(do_m.group(1))

        return packet
