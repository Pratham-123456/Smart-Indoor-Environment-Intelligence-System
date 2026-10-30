# Review 1 Objective Traceability Matrix

## 1. Traceability Baseline
This matrix traces every formal requirement, objective, and novelty claim established in the **Review 1 Presentation (`embedded_project-1_(2)[1].pdf`)** to its concrete implementation in the SIEIS codebase.

### Status Definitions:
- **Verified (Code & Tests Passed):** Implemented in codebase, covered by automated test suite, and verified passing.
- **Compiled & Ready for Hardware:** Sketch compiled cleanly with ESP32 Xtensa GCC toolchain, ready for physical flashing.
- **Hardware Gap (Documented):** Metric from Review 1 proposal that was dropped or replaced during procurement, represented transparently as `null`.

---

## 2. Formal Objective Mapping

| Review 1 Objective | Original Requirement | Implementation File | Verification Evidence & Tests | Implementation Status |
|---|---|---|---|---|
| **Objective A: Monitor** | Acquire indoor environmental measurements | `firmware/SIEIS_ESP32/SIEIS_ESP32.ino`, `backend/app.py` | `tests/test_api.py::test_hardware_status_endpoint`, `tests/test_validation.py` | **Verified (Code & Tests Passed)** (DHT22, LDR, MQ-135, LM393 active) |
| *Objective A (Pressure)* | Atmospheric pressure measurement (BME280) | `backend/schema.sql`, `backend/validation.py` | Exposes `null` with explicit documentation; BME280 dropped | **Hardware Gap (Documented)** |
| *Objective A (Gas Conc.)* | Certified eCO₂, TVOC, AQI (ENS160) | `backend/intelligence/baseline.py` | MQ-135 used for relative gas response; `eco2_ppm: null` | **Hardware Gap (Documented)** |
| *Objective A (Lux)* | Digital Lux measurement (BH1750) | `firmware/SIEIS_ESP32/SIEIS_ESP32.ino` | Bare LDR classified into dark/dim/bright; `lux: null` | **Hardware Gap (Documented)** |
| **Objective B: Transmit** | Validated JSON packets over Wi-Fi (HTTP) | `firmware/SIEIS_ESP32/SIEIS_ESP32.ino`, `backend/validation.py` | `tests/test_api.py::test_post_sensor_telemetry_success`, Sketch compiled | **Verified (Code & Tests Passed)** |
| **Objective B (Resilience)** | Reconnection backoff & non-blocking execution | `firmware/SIEIS_ESP32/SIEIS_ESP32.ino` | Firmware inspection; HTTP timeouts & bounded retries | **Compiled & Ready for Hardware** |
| **Objective C: Analyze (Scores)** | Environmental Health Score & Comfort Index | `backend/intelligence/scoring.py` | `tests/test_intelligence.py::test_comfort_index_optimal`, `test_environmental_health_score_*` | **Verified (Code & Tests Passed)** |
| **Objective C (Baseline)** | Adaptive rolling baseline for gas sensor | `backend/intelligence/baseline.py` | `tests/test_intelligence.py::test_mq135_baseline_warmup_exclusion`, `tests/test_database.py` | **Verified (Code & Tests Passed)** |
| **Objective C (Trends)** | Moving averages & rate-of-change per minute | `backend/intelligence/trends.py` | `tests/test_intelligence.py::test_trend_analyzer` | **Verified (Code & Tests Passed)** |
| **Objective C (Forecasting)**| Qualified trend-based predictive forecasting | `backend/intelligence/forecasting.py` | `tests/test_intelligence.py::test_forecaster_*` | **Verified (Code & Tests Passed)** |
| **Objective D: Decide** | Rule-based decision support & recommendations | `backend/intelligence/decision.py` | `tests/test_intelligence.py::test_decision_engine_stale_detection`, `test_end_to_end_sim.py` | **Verified (Code & Tests Passed)** |
| **Objective D (Alerts)** | Multi-parameter anomaly detection & auto-resolve | `backend/intelligence/anomaly.py` | `tests/test_intelligence.py::test_anomaly_detection_thermal_breach`, `test_end_to_end_sim.py` | **Verified (Code & Tests Passed)** |
| **Storage Layer** | Persistent SQLite time-series storage | `backend/database.py`, `backend/schema.sql` | `tests/test_database.py::*` (7 database unit tests) | **Verified (Code & Tests Passed)** |
| **Presentation Layer**| Interactive web dashboard with Chart.js | `backend/templates/index.html`, `backend/static/` | `tests/test_api.py::test_dashboard_route_serves_html`, client DOM tests | **Verified (Code & Tests Passed)** |

---

## 3. Review 1 Novelty Requirements Verification

| Claimed Novelty (Slide 11) | Review 1 Promise | Implemented Reality in SIEIS | Verification Status |
|---|---|---|---|
| **Primary Output** | Contextual Health Score, Comfort Index & Trends rather than raw numbers | Calculates 0–100 EHS and ASHRAE 55 Comfort Index with subcomponent transparency and rate-of-change badges | **Fully Implemented & Verified** |
| **Data Integrity** | Real-time range & rate-of-change validation | Enforces physical limits (e.g. Temp $-20..70^\circ\text{C}$, Hum $0..100\%$), sanitizes NaN/Inf, and flags spikes | **Fully Implemented & Verified** |
| **Alert Triggering** | Multi-parameter synthesis & predictive forecasting | Baseline elevation ratios (1.25x / 1.50x), thermal bounds, acoustic surges, and OLS linear trend projection | **Fully Implemented & Verified** |
| **User Guidance** | Direct, actionable operational recommendations | DecisionEngine generates specific advice (e.g., "Increase ventilation", "Task lighting required") | **Fully Implemented & Verified** |
| **Architecture** | Modular Embedded State Machine + Python Intelligence Engine | ESP32 decoupled acquisition + Python 3.14 Flask backend with 6 specialized intelligence modules | **Fully Implemented & Verified** |
