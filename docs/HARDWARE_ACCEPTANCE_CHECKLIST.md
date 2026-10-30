# SIEIS Hardware Acceptance & Demonstration Checklist

## 1. Pre-Flight Acceptance Checklist

| Checkpoint | Action / Condition | Verification Method | Expected Outcome | Status |
|---|---|---|---|---|
| **1. Power & USB** | Connect ESP32 to laptop via Micro-USB | Device Manager -> Ports (COM & LPT) | CP210x USB to UART Bridge detected on `COM4` | [ ] |
| **2. Pin Wiring** | Verify DHT22 on GPIO4, LDR on GPIO35, MQ-135 on GPIO34 (divider), Sound on GPIO32/26 | Physical inspection against `docs/HARDWARE_AND_WIRING.md` | All grounds common; voltage dividers secure | [ ] |
| **3. Hotspot Network**| Laptop and ESP32 configured for same Wi-Fi SSID | PowerShell `Get-NetIPAddress` | Laptop IP confirmed (e.g. `10.40.222.63`); 2.4 GHz enabled | [ ] |
| **4. Firmware Config** | `config.h` created with active SSID, password, server URL | Open `firmware/SIEIS_ESP32/config.h` | Credentials match active hotspot | [ ] |
| **5. Backend Launch** | Run `.\.venv\Scripts\python.exe backend\app.py` | PowerShell terminal | SQLite initialized; Flask listening on port 5000 | [ ] |
| **6. Firmware Upload**| Flash `firmware/SIEIS_ESP32/SIEIS_ESP32.ino` | Arduino IDE or `arduino-cli upload` | Upload 100% complete; boot message on Serial Monitor | [ ] |
| **7. First Ingestion** | Observe Serial Monitor & Flask terminal | Serial Monitor at 115200 baud | `[HTTP] POST Success (seq=1, HTTP 201)` | [ ] |
| **8. Dashboard Live** | Open `http://localhost:5000/` | Web browser | Status pill turns green: "Node Live (COM4 / Wi-Fi)" | [ ] |

---

## 2. Review Demonstration Scenarios (Safe & Repeatable)

### Scenario A: Optical Illumination Dynamic Response
- **Objective:** Prove real-time analog acquisition and categorical classification without faking Lux.
- **Procedure:**
  1. Observe current dashboard LDR card reading (typically `Dim`, raw ADC ~400–700).
  2. Cover the bare LDR completely with a fingertip.
  3. **Expected Result:** Within 5 seconds, raw ADC drops to $< 250$; card updates to `DARK`; Decision Engine produces advisory: *"Low Ambient Illumination: Turn on task lighting."*
  4. Illuminate the LDR directly using your phone's flashlight.
  5. **Expected Result:** Raw ADC jumps to $> 2000$; card updates to `BRIGHT`.

### Scenario B: Thermal & Hygric Dynamic Response (DHT22)
- **Objective:** Demonstrate precision physical sensor tracking and Comfort Index recalculation.
- **Procedure:**
  1. Observe steady-state temperature (~22–24°C) and humidity (~45–55%).
  2. Cup your hands closely around the DHT22 and breathe gently onto the white mesh for 3–5 seconds (do not splash liquid).
  3. **Expected Result:** Moisture from breath causes humidity reading to climb sharply (e.g., $50\% \to 70\%+$). The humidity trend badge flips to `RISING`.
  4. Comfort Index reflects the temporary surge in moisture.
  5. Within 1–2 minutes of normal room air, humidity steadily returns to baseline; trend badge returns to `FALLING` then `STABLE`.

### Scenario C: Acoustic Transient Activity (LM393)
- **Objective:** Demonstrate peak-to-peak audio swing analysis distinguishing ambient silence from room activity.
- **Procedure:**
  1. Keep room silent for 10 seconds. Observe sound swing (~50–200) and DO state (`Quiet`).
  2. Clap hands 3 times near the sensor module or speak loudly.
  3. **Expected Result:** The 150 ms peak-to-peak sampling window captures the acoustic swing, surging to $> 1500$. DO threshold pulses to `Threshold Active`.

### Scenario D: MQ-135 Warmup & Baseline Integrity
- **Objective:** Demonstrate heater warmup quarantining and baseline-relative anomaly alerts without hazardous gas.
- **Procedure:**
  1. Power cycle the ESP32.
  2. Observe Serial Monitor and Dashboard: MQ-135 status clearly displays `Warming Up (5 min window)`.
  3. Point out to reviewers that during this 5-minute stabilization window, the system deliberately ignores the initial transient spike and excludes the sensor from EHS scoring, proving industrial-grade false-alarm prevention.
  4. Once 300 seconds elapse, status smoothly transitions to `READY (Active)`, and the rolling baseline establishes.

### Scenario E: Network Resilience & Disconnection Handling
- **Objective:** Demonstrate embedded failover and dashboard staleness detection.
- **Procedure:**
  1. Temporarily disable Wi-Fi on your phone or unplug the router hotspot.
  2. Observe ESP32 Serial Monitor: Acquisition continues uninterrupted; Wi-Fi drops to periodic reconnection backoff.
  3. Observe Dashboard: After 30 seconds without packets, status pill turns amber (`Telemetry Stale`), and the top warning banner appears informing occupants that data is historical.
  4. Re-enable hotspot: ESP32 automatically reconnects and resumes POST transmission without requiring a microcontroller reset.
