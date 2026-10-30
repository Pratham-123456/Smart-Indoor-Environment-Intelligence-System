# SIEIS ESP32 Firmware Guide

## Overview
This directory contains the production-integrated embedded firmware for the **Smart Indoor Environmental Intelligence System (SIEIS)**.

The firmware performs:
1. Multi-sensor periodic sampling:
   - **DHT22:** Temperature (°C) and Relative Humidity (%)
   - **Bare LDR Divider:** 12-bit ADC raw brightness & Dark/Dim/Bright classification
   - **MQ-135:** 12-bit ADC millivolts & 1.5x divider conversion
   - **LM393 Sound Sensor:** Peak-to-peak swing over 150ms window & digital threshold state
2. Data validation & JSON formatting with sequence numbering and millisecond uptime.
3. Wi-Fi station connectivity with resilient auto-reconnect backoff.
4. HTTP POST telemetry transmission to the centralized Python/Flask backend.
5. USB Serial Monitor diagnostics at `115200` baud.

---

## Hardware Pin Connections

| Sensor | Sensor Pin | ESP32 GPIO | Operating Voltage | Notes |
|---|---|---|---|---|
| **DHT22** | DATA | `GPIO 4` | 3.3V | 3-pin module with onboard pull-up |
| **Bare LDR** | Divider Junction | `GPIO 35` | 3.3V | LDR to 3V3, 10k resistor to GND |
| **MQ-135** | AO (Analog Out) | `GPIO 34` | 5V | Fed through 10k:20k voltage divider to protect ESP32 3.3V ADC |
| **Sound Sensor** | AO (Analog Out) | `GPIO 32` | 3.3V / 5V | Peak-to-peak swing over 150ms window |
| **Sound Sensor** | DO (Digital Out) | `GPIO 26` | 3.3V / 5V | Digital comparator threshold |

---

## Configuration

1. Copy `config.example.h` to `config.h`:
   ```powershell
   Copy-Item config.example.h config.h
   ```
2. Open `config.h` and update your Wi-Fi credentials and laptop IP address:
   ```c
   #define WIFI_SSID             "Your_Hotspot_Name"
   #define WIFI_PASSWORD         "Your_Password"
   #define BACKEND_SERVER_URL    "http://10.40.222.63:5000/api/sensor"
   ```
3. `config.h` is excluded by `.gitignore` so your private network credentials will not be accidentally committed.

---

## How to Flash via Arduino IDE

1. Open Arduino IDE.
2. Go to **File -> Open** and select `firmware/SIEIS_ESP32/SIEIS_ESP32.ino`.
3. Select Board: **Tools -> Board -> esp32 -> ESP32 Dev Module**.
4. Select Port: **Tools -> Port -> COM4** (or whichever COM port your ESP32 is assigned).
5. Ensure libraries are installed:
   - `DHT sensor library` by Adafruit
   - `Adafruit Unified Sensor` by Adafruit
6. Click **Upload** (Ctrl + U).
7. Open **Tools -> Serial Monitor** at `115200` baud to observe live boot and telemetry logs.

---

## How to Flash via Command Line (arduino-cli)

Compile:
```powershell
& "C:\Users\insan\Downloads\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" compile --fqbn esp32:esp32:esp32 firmware\SIEIS_ESP32\SIEIS_ESP32.ino
```

Upload to COM4:
```powershell
& "C:\Users\insan\Downloads\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" upload -p COM4 --fqbn esp32:esp32:esp32 firmware\SIEIS_ESP32\SIEIS_ESP32.ino
```
