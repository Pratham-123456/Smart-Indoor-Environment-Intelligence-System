# SIEIS Sensor Limitations & Scientific Integrity Report

## 1. Principle of Measurement Integrity
A primary engineering tenet of the SIEIS project is **absolute scientific honesty**. Rather than generating fabricated metrics or dressing uncalibrated analog voltages up with prestigious units (such as certified AQI or decibels), SIEIS maps each procured sensor to its true physical capabilities.

Unsupported metrics from the original Review 1 plan are explicitly exposed as `null` in the data contract, with their status documented and visible on the dashboard.

---

## 2. Sensor-by-Sensor Audit

### 2.1 Temperature & Relative Humidity (DHT22 / AM2302)
- **Status:** **Active & Verified Physical Measurement.**
- **True Capability:**
  - Temperature range: $-40^\circ\text{C}$ to $+80^\circ\text{C}$ with $\pm 0.5^\circ\text{C}$ accuracy.
  - Relative humidity range: $0\%$ to $100\%$ with $\pm 2-5\%$ accuracy.
  - Minimum sampling period: 2.0 seconds between conversions.
- **Differences from Review 1 Plan:** The Review 1 proposal originally listed the **BME280** (which includes barometric pressure). Because the DHT22 replaced the BME280, atmospheric pressure is currently unsupported.
- **Software Handling:** Real readings are recorded directly. If a read failure occurs due to digital bus timing, the firmware preserves and reports the last known good reading alongside a `degraded_cached` diagnostic flag.

### 2.2 Relative Gas Response (MQ-135)
- **Status:** **Active Relative Indicator (Not Calibrated Concentration).**
- **Hardware Circuit:** Powered by 5V VCC (heater requirement); analog output stepped down via a 10k:20k voltage divider to protect the ESP32 3.3V ADC.
- **Scientific Limits:**
  - The MQ-135 utilizes a heated Tin Dioxide ($SnO_2$) ceramic substrate. In clean air, electrical conductivity is low. In the presence of reducing gases (ammonia, benzene, alcohol, smoke, CO), conductivity increases.
  - **What it is NOT:** It is NOT an NDIR CO₂ sensor, NOT an electrochemical sensor, NOT a calibrated photoionization detector (PID), and NOT a factory-calibrated TVOC meter.
  - **Why PPM or AQI cannot be claimed:** Generating PPM or standard AQI from an MQ-135 requires controlled reference gas chambers, temperature/humidity co-compensation curves, and calibration against certified gas canisters. Displaying raw MQ-135 output as "CO₂ ppm" or "AQI" without this is scientifically invalid.
- **Software Handling:** The backend compares current millivolts against the sensor's own **20% trimmed rolling baseline**. Alerts indicate *relative air freshness deterioration*, avoiding false claims of specific chemical concentrations.

### 2.3 Ambient Illumination (Bare LDR Voltage Divider)
- **Status:** **Active Relative Indicator (Not Calibrated Lux).**
- **Hardware Circuit:** Bare light-dependent resistor in series with a 10 kΩ pull-down resistor to GND.
- **Scientific Limits:**
  - LDR spectral sensitivity peaks around 540 nm (green), but resistance-to-illuminance is highly non-linear ($\gamma \approx 0.7-0.9$) and varies significantly between individual manufacturing batches.
  - It does NOT provide photopic-curve-corrected illuminance in Lux.
- **Differences from Review 1 Plan:** The original plan called for an I²C digital ambient light sensor (**BH1750**).
- **Software Handling:** The raw 12-bit ADC value (0–4095) is categorized into calibrated operating envelopes:
  - `< 250`: Dark (unlit / night room)
  - `250 – 1699`: Dim (comfortable ambient daylight/room lighting)
  - `≥ 1700`: Bright (direct artificial lamp or sunlight)

### 2.4 Ambient Acoustic Activity (LM393 Microphone Module)
- **Status:** **Active Relative Indicator (Not Calibrated Decibels).**
- **Hardware Circuit:** Electret microphone capsule with LM393 comparator. AO connected to GPIO 32; DO connected to GPIO 26.
- **Scientific Limits:**
  - The module lacks A-weighting frequency filters, calibrated acoustic reference chambers, and root-mean-square (RMS) SPL conversion.
  - It does NOT measure decibels ($dBA$).
- **Software Handling:** Samples the analog waveform over a 150 ms window to calculate the peak-to-peak amplitude swing ($V_{peak} - V_{low}$). This reliably distinguishes quiet background environments from active conversations, clapping, or loud disturbances.

---

## 3. Explicitly Unsupported Original Metrics

| Metric | Proposed Sensor | Procured Hardware Status | Backend Representation |
|---|---|---|---|
| **Barometric Pressure** | BME280 | BME280 dropped; DHT22 in use | `pressure_hpa: null` |
| **eCO₂ Concentration** | ENS160 | ENS160 not procured | `eco2_ppm: null` |
| **TVOC Concentration** | ENS160 | ENS160 not procured | `tvoc_ppb: null` |
| **Standard Multi-Gas AQI** | ENS160 | Not present | `aqi: null` |
| **Calibrated Lux** | BH1750 | Bare LDR divider in use | `lux: null` |
| **Certified Sound Pressure (dBA)** | Calibrated Mic | LM393 uncalibrated | `sound_db: null` |

---

## 4. Future Modular Sensor Integration
The backend database schema and REST API contract are architected with explicit optional fields. When hardware upgrades are procured (e.g. adding a BME280 or ENS160 over I²C on GPIO 21 / 22), the firmware can populate these keys without altering the database schema or breaking the existing frontend.
