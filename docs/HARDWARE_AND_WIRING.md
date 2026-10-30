# SIEIS Hardware & Wiring Reference

## 1. Overview
The **SIEIS Sensor Node** is built on the **ESP32 DevKit** micro-controller board (30-pin / 38-pin Dev Module with CP2102 USB-to-UART bridge).

The hardware configuration is verified and calibrated for 4 sensor subsystems:
1. **DHT22 (AM2302):** High-precision digital temperature and relative humidity sensor.
2. **Bare LDR Voltage Divider:** Ambient illumination intensity sensor.
3. **MQ-135 Gas Sensor:** Chemiresistive gas sensor for relative indoor air freshness and volatile organic reduction monitoring.
4. **LM393 Acoustic Module:** Ambient sound amplitude peak detector with analog envelope and comparator threshold.

---

## 2. Complete Interconnect & Pin Mapping

| Sensor Module | Sensor Pin | ESP32 GPIO | Operating Voltage | Interface Type | Description & Circuit Details |
|---|---|---|---|---|---|
| **DHT22** | VCC | 3V3 | 3.3V DC | Power | Powered from ESP32 regulated 3.3V rail |
| **DHT22** | DATA | `GPIO 4` | 3.3V Logic | 1-Wire Digital | Bidirectional digital communication with 10k pullup to 3.3V |
| **DHT22** | GND | GND | 0V | Ground | System common ground |
| **Bare LDR** | Leg 1 | 3V3 | 3.3V DC | Power | Upper leg of voltage divider tied to 3.3V |
| **Bare LDR** | Leg 2 (Junction) | `GPIO 35` | 0 – 3.3V Analog | ADC1_CH7 | Junction connected to GPIO 35 and 10 kΩ resistor to GND |
| **10 kΩ Resistor** | Pin 2 | GND | 0V | Ground | Pull-down leg of LDR divider |
| **MQ-135** | VCC | VIN (5V) | 5.0V DC | Power | Heater coil requires 5V for appropriate thermal activation (~150 mA) |
| **MQ-135** | GND | GND | 0V | Ground | System common ground |
| **MQ-135** | AO | `GPIO 34` | 0 – 3.3V Analog | ADC1_CH6 | **Protected by 10k : 20k Voltage Divider** (see Section 3) |
| **Sound Sensor** | VCC | 3V3 / VIN | 3.3V – 5V DC | Power | Power supply rail |
| **Sound Sensor** | GND | GND | 0V | Ground | System common ground |
| **Sound Sensor** | AO | `GPIO 32` | 0 – 3.3V Analog | ADC1_CH4 | Direct analog audio signal; sampled for 150ms peak-to-peak swing |
| **Sound Sensor** | DO | `GPIO 26` | 3.3V Logic | Digital Input | LM393 comparator digital threshold output |

---

## 3. Voltage Divider & ADC Safety Circuits

### 3.1 MQ-135 Output Protection Divider
The MQ-135 module operates from 5V VCC, meaning its raw analog output ($V_{AO}$) can swing up to ~4.5V under heavy gas concentration. Because ESP32 ADC inputs are strictly rated for a maximum of 3.3V, a voltage divider is placed between MQ-135 AO and ESP32 GPIO 34.

- **Resistor $R_1$:** $10\text{ k}\Omega$ (in series with MQ-135 AO)
- **Resistor $R_2$:** $20\text{ k}\Omega$ (two $10\text{ k}\Omega$ resistors in series from GPIO 34 to GND)
- **Divider Ratio:**
  $$\frac{V_{pin}}{V_{AO}} = \frac{R_2}{R_1 + R_2} = \frac{20\text{ k}\Omega}{10\text{ k}\Omega + 20\text{ k}\Omega} = \frac{2}{3} \approx 0.667$$
- **Reverse Scaling (Firmware Reconstruction):**
  $$V_{AO} = V_{pin} \times 1.5$$
- **Safety Margin:** At maximum theoretical output $V_{AO} = 5.0\text{V}$, $V_{pin} = 5.0 \times \frac{2}{3} = 3.33\text{V}$, fully safeguarding the ESP32 silicon.

### 3.2 LDR Illumination Divider
- **Configuration:** LDR connected to 3.3V, $10\text{ k}\Omega$ resistor connected to GND.
- **Behavior:** As ambient brightness increases, LDR photo-resistance drops, pulling the junction voltage higher toward 3.3V.
- **Calibrated Raw ADC Classification (12-bit, 0–4095):**
  - **Dark (< 250):** e.g., LDR covered with finger or unlit room (~25 raw).
  - **Dim (250 – 1699):** Normal indoor ambient lighting (~500 raw).
  - **Bright (≥ 1700):** Direct phone flashlight or intense daylight (~2985 raw).

---

## 4. Operational & Conditioning Requirements

### 4.1 MQ-135 Heater Burn-In vs Startup Warmup
- **Initial Conditioning / Burn-In (24 – 48 Hours):** A brand new MQ-135 sensor requires continuous 5V heating for 24 to 48 hours to desorb manufacturing moisture and chemical residues from its $SnO_2$ sensing layer.
- **Power-Up Warmup Window (5 Minutes / 300,000 ms):** After every subsequent reboot, the sensor heater requires 5 minutes to reach thermal equilibrium ($~300^\circ\text{C}$). The firmware strictly tags readings as `warming_up` during this window, preventing false positive alarms.

### 4.2 LM393 Sound Sensor Sampling Window
- Audio signals are AC waveforms with rapid zero-crossings. A single momentary `analogRead()` may capture a zero-crossing rather than the acoustic energy.
- The firmware executes a **150 ms peak-to-peak sampling window**:
  $$\text{Swing} = V_{peak} - V_{low}$$
- This distinguishes sustained acoustic disturbances (talking, applause) from background silence.
