# SIEIS — Smart Indoor Environmental Intelligence System

> **A Distributed Embedded System for Real-Time Monitoring, Analysis, Anomaly Detection, and Intelligent Decision Support**
> 
> *College Engineering Project (Embedded Systems & Architecture)*  
> Baseline: Review 1 Presentation (`docs/embedded_project-1_(2)[1].pdf`) & Project Overview (`docs/SIEIS Project Overview.pdf`)

---

## 1. System Overview
**SIEIS** transforms conventional, passive indoor environmental monitoring into an intelligent, proactive decision-support platform. Traditional IoT monitors merely display raw numbers (e.g. *"CO₂ = 1100 ppm"*) without context or actionable advice. 

SIEIS couples an autonomous edge acquisition node with a Python/Flask intelligence backend and an interactive web dashboard to deliver:
- **Real-Time Contextual Scoring:** Computes an explainable **Environmental Health Score (0–100)** and an ASHRAE 55-aligned **Comfort Index**.
- **Dynamic Rolling Baseline:** Tracks relative gas responses against a 20% trimmed moving average, eliminating false alarms.
- **Automated Trend & Rate-of-Change Analysis:** Detects rising/falling thermal and chemical trajectories in real time.
- **Multi-Factor Anomaly Detection:** Employs hysteresis, cooldowns, and automatic alert resolution.
- **Qualified Trend Forecasting:** Employs ordinary least-squares linear projection with explicit $R^2$ confidence metrics.
- **Actionable Decision Support:** Translates environmental observations into concrete operational guidance (e.g. ventilation, task lighting, heating adjustment).
- **Absolute Measurement Integrity:** Rigorously distinguishes verified physical units (°C, %) from relative uncalibrated indicators (raw ADC, millivolts, audio swing), explicitly flagging unsupported original channels as `null`.

---

## 2. Hardware Architecture & Pin Configuration

| Subsystem | Sensor Module | Interface | ESP32 GPIO | Operating Voltage | Measurement Semantic |
|---|---|---|---|---|---|
| **Thermal / Hygric** | DHT22 (AM2302) | 1-Wire Digital | `GPIO 4` | 3.3V | Calibrated Temperature (°C) & Relative Humidity (%) |
| **Ambient Illumination** | Bare LDR Divider | ADC1_CH7 | `GPIO 35` | 3.3V | Relative brightness (12-bit raw ADC: Dark/Dim/Bright) |
| **Relative Gas Response** | MQ-135 | ADC1_CH6 | `GPIO 34` | 5.0V (10k:20k Divider) | Relative reducing gas voltage vs. rolling baseline |
| **Acoustic Activity** | LM393 Sound Module | ADC1_CH4 & DO | `GPIO 32` & `GPIO 26` | 3.3V / 5.0V | 150ms peak-to-peak audio swing & threshold comparator |

*Note: Barometric pressure (BME280), certified eCO₂/TVOC (ENS160), and calibrated Lux (BH1750) are explicitly unsupported by current hardware and exposed transparently as `null`.*

---

## 3. Directory Layout

```
SIEIS/
├── backend/
│   ├── intelligence/          # Scoring, baseline, trends, anomalies, forecasting, decision engine
│   │   ├── anomaly.py
│   │   ├── baseline.py
│   │   ├── decision.py
│   │   ├── forecasting.py
│   │   ├── scoring.py
│   │   └── trends.py
│   ├── static/                # Modern CSS3 stylesheet and Chart.js controllers
│   ├── templates/             # index.html responsive dashboard
│   ├── app.py                 # Flask REST API server and telemetry ingestion
│   ├── config.py              # Configuration defaults, bounds, and thresholds
│   ├── database.py            # SQLite persistent time-series manager
│   ├── schema.sql             # Relational database schema with performance indexes
│   ├── validation.py          # Strict payload validation layer
│   └── requirements.txt       # Python dependencies
├── docs/                      # Authoritative specifications and references
│   ├── ARCHITECTURE.md        # Mermaid diagrams, system flows, and sequence charts
│   ├── HARDWARE_AND_WIRING.md # Detailed circuit calculations and pin mappings
│   ├── API_CONTRACT.md        # REST JSON specifications and status codes
│   ├── INTELLIGENCE_SPEC.md   # Mathematical models, scoring formulas, and baselines
│   ├── SENSOR_LIMITATIONS.md  # Measurement integrity and scientific limitations
│   ├── SETUP_AND_OPERATIONS.md# Windows step-by-step setup and troubleshooting guide
│   ├── REVIEW_TRACEABILITY.md # Review 1 requirement-to-code traceability matrix
│   ├── HARDWARE_ACCEPTANCE_CHECKLIST.md # Verification checklist & demo scenarios
│   ├── embedded_project-1_(2)[1].pdf   # Original Review 1 presentation
│   └── SIEIS Project Overview.pdf      # Procured hardware overview
├── firmware/
│   ├── SIEIS_ESP32/           # Integrated production ESP32 sketch
│   │   ├── SIEIS_ESP32.ino    # Arduino C++ edge firmware
│   │   ├── config.example.h   # Wi-Fi credentials and endpoint template
│   │   └── README.md          # Firmware compilation and flashing guide
│   └── sieis_sensors_original_backup.ino # Unmodified backup of original sensor sketch
├── tests/                     # Automated test suite (31 tests)
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_database.py
│   ├── test_end_to_end_sim.py
│   ├── test_intelligence.py
│   └── test_validation.py
├── .gitignore
└── README.md
```

---

## 4. Quickstart Guide (Windows)

### 1. Launch Backend Server
From PowerShell in the project directory:
```powershell
.\.venv\Scripts\python.exe backend\app.py
```
*Access the live dashboard at `http://localhost:5000/` or from any device on your hotspot at `http://<laptop-ip>:5000/`.*

### 2. Run Automated Test Suite
```powershell
.\.venv\Scripts\pytest.exe -v
```
*(31 unit, database, intelligence, and end-to-end simulation tests pass in ~0.15s).*

### 3. Configure and Flash ESP32
1. Copy configuration template:
   ```powershell
   Copy-Item firmware\SIEIS_ESP32\config.example.h firmware\SIEIS_ESP32\config.h
   ```
2. Edit `firmware\SIEIS_ESP32\config.h` with your phone hotspot SSID, password, and laptop IP.
3. Flash via Arduino IDE or `arduino-cli`:
   ```powershell
   & "C:\Users\insan\Downloads\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" compile --fqbn esp32:esp32:esp32 firmware\SIEIS_ESP32\SIEIS_ESP32.ino
   & "C:\Users\insan\Downloads\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" upload -p COM4 --fqbn esp32:esp32:esp32 firmware\SIEIS_ESP32\SIEIS_ESP32.ino
   ```

---

## 5. Review Demonstration Scenarios
See [`docs/HARDWARE_ACCEPTANCE_CHECKLIST.md`](docs/HARDWARE_ACCEPTANCE_CHECKLIST.md) for 5 safe, repeatable presentation demonstrations:
1. **Optical Illumination:** Cover LDR ($\to$ Dark $<250$) vs. Phone Torch ($\to$ Bright $\ge 1700$).
2. **Thermal-Hygric Response:** Breath on DHT22 causes immediate humidity climb, activating the `RISING` trend badge and updating the Comfort Index.
3. **Acoustic Disturbance:** Hand-clap produces peak swing ($>1500$) and DO digital threshold trigger.
4. **Heater Warmup Isolation:** Demonstrates 5-minute false-alarm prevention during sensor warm-up.
5. **Network Resilience:** Temporarily turning off hotspot shows local acquisition continuing and dashboard indicating "Telemetry Stale", followed by automatic recovery.
