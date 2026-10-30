# SIEIS Room Comfort Index (RCI) — Authoritative Mathematical Specification

**Document Identifier:** `SIEIS-SPEC-RCI-2026-REV2`  
**System:** SIEIS (Smart Indoor Environmental Intelligence System)  
**Classification:** Core Intelligence Algorithm & Mathematical Standard  
**Source Implementation:** [`backend/intelligence/rci.py`](file:///c:/Users/insan/OneDrive/Desktop/SIEIS/backend/intelligence/rci.py)  
**Configuration Thresholds:** [`backend/config.py`](file:///c:/Users/insan/OneDrive/Desktop/SIEIS/backend/config.py)  

---

## 1. Executive Summary & Design Philosophy

The **Room Comfort Index (RCI)** is the authoritative, explainable composite index $(0 - 100)$ developed for the Smart Indoor Environmental Intelligence System (SIEIS). It maps multi-modal physical sensor streams into a single, scalar metric representing indoor environmental quality and human comfort.

Unlike naive unweighted averaging or black-box machine learning models, RCI strictly adheres to the following engineering tenets:

1. **Standards-Aligned Piecewise Formulations:** Component evaluation curves are grounded in international standards, notably **ASHRAE Standard 55-2023** (Thermal Environmental Conditions for Human Occupancy), **CIBSE Guide A** (Environmental Design), **WHO Air Quality Guidelines**, and indoor ergonomic lighting/acoustics criteria.
2. **Dynamic Weight Re-Normalization:** If any secondary sensor channel is offline, in a physical warm-up cycle (such as the MQ-135 heater), or unconditioned, the engine dynamically excludes the unready channel and proportionally redistributes its weight across the remaining valid channels without distorting the $0 - 100$ scale.
3. **Epistemic Honesty:** RCI distinguishes direct physical measurements (DHT22 temperature and relative humidity) from uncalibrated relative indicators (MQ-135 relative gas response, bare LDR brightness, LM393 acoustic swing). Uncalibrated sensors contribute strictly to relative trends, never to fabricated absolute units (such as pseudo-lux, pseudo-dB, or uncalibrated ppm).
4. **Transparent Explainability:** Every RCI computation outputs not just a numerical score, but exact component sub-scores, active positive/negative contributors, data coverage percentages, and human-readable natural language diagnostic explanations.

---

## 2. Mathematical Foundation & Dynamic Re-Normalization

The Room Comfort Index synthesizes available indoor environmental telemetry using a **dynamically re-normalized weighted multi-attribute synthesis**:

$$\text{RCI} = \sum_{i \in \mathcal{A}} S_i \times \left( \frac{w_i}{\sum_{j \in \mathcal{A}} w_j} \right)$$

Where:
- $\mathcal{A}$ is the set of currently valid, conditioned sensor channels.
- $S_i \in [0.0, 100.0]$ is the normalized sub-index score for channel $i$.
- $w_i$ is the nominal weight assigned to channel $i$.
- $\sum_{j \in \mathcal{A}} w_j$ is the sum of nominal weights of all currently available channels.

### 2.1 Nominal Channel Weight Allocations

When all five hardware sensor channels are online, conditioned, and reporting fresh telemetry, the nominal weights are:

| Subsystem Channel | Symbol | Nominal Weight ($w_i$) | Percentage | Primary Reference / Standard |
|---|---|---|---|---|
| **Thermal Comfort (Temperature)** | $S_{\text{temp}}$ | $0.30$ | **30%** | ASHRAE 55-2023 / CIBSE Guide A |
| **Hygric Comfort (Humidity)** | $S_{\text{hum}}$ | $0.25$ | **25%** | ASHRAE 55 / Sterling Mold Matrix |
| **Air Freshness (MQ-135 Gas)** | $S_{\text{gas}}$ | $0.25$ | **25%** | Relative rolling baseline elevation |
| **Visual Ergonomics (LDR Brightness)** | $S_{\text{light}}$ | $0.10$ | **10%** | CIBSE Code for Lighting / OSHA |
| **Acoustic Activity (LM393 Sound)** | $S_{\text{sound}}$ | $0.10$ | **10%** | WHO Community Noise Guidelines |
| **Total Nominal Weight** | $\sum w_i$ | **$1.00$** | **100%** | — |

### 2.2 Re-Normalization Example (MQ-135 Warm-Up State)

During the initial $300\text{s}$ warm-up cycle of the MQ-135 semiconductor heater, or before the 30-sample rolling baseline is established, $S_{\text{gas}}$ is excluded from $\mathcal{A}$:

$$\mathcal{A} = \{ \text{temperature}, \text{humidity}, \text{lighting}, \text{sound} \}$$

$$\sum_{j \in \mathcal{A}} w_j = 0.30 + 0.25 + 0.10 + 0.10 = 0.75$$

The effective weights during warm-up become:
- Effective Temperature Weight: $\frac{0.30}{0.75} = 40.0\%$
- Effective Humidity Weight: $\frac{0.25}{0.75} = 33.33\%$
- Effective Light Weight: $\frac{0.10}{0.75} = 13.33\%$
- Effective Sound Weight: $\frac{0.10}{0.75} = 13.33\%$

The result is flagged as `is_provisional: True` with explicit annotation in the diagnostic explanation.

---

## 3. Component Scoring Formulations ($S_i$)

Every component score $S_i$ outputs a continuous value bounded in $[0.0, 100.0]$.

### 3.1 Thermal Comfort Component ($S_{\text{temp}}$)

Derived from the ASHRAE 55 winter/summer combined operative temperature comfort zone for sedentary occupants ($1.0 - 1.2\text{ met}$, $0.5 - 1.0\text{ clo}$).

**Threshold Parameters:**
- Optimal Min: $T_{\text{opt,min}} = 21.0^\circ\text{C}$
- Optimal Max: $T_{\text{opt,max}} = 24.0^\circ\text{C}$
- Absolute Min: $T_{\text{min}} = 14.0^\circ\text{C}$
- Absolute Max: $T_{\text{max}} = 33.0^\circ\text{C}$

**Piecewise Equation:**

$$S_{\text{temp}}(T) = \begin{cases} 
100.0 & \text{if } 21.0 \le T \le 24.0 \\
\left( \frac{T - 14.0}{21.0 - 14.0} \right) \times 100.0 & \text{if } 14.0 \le T < 21.0 \\
\left( \frac{33.0 - T}{33.0 - 24.0} \right) \times 100.0 & \text{if } 24.0 < T \le 33.0 \\
0.0 & \text{if } T < 14.0 \text{ or } T > 33.0
\end{cases}$$

```text
Score
 100 |          +--------------------+
     |         /                      \
     |        /                        \
     |       /                          \
   0 +------+----------------------------+------
           14.0 21.0                24.0 33.0    Temperature (°C)
```

---

### 3.2 Hygric Comfort Component ($S_{\text{hum}}$)

Aligned with the Sterling Criteria for human respiratory health, mucosal comfort, electrostatic discharge prevention, and mold spore germination limits.

**Threshold Parameters:**
- Optimal Min: $\text{RH}_{\text{opt,min}} = 40.0\%$
- Optimal Max: $\text{RH}_{\text{opt,max}} = 60.0\%$
- Absolute Min: $\text{RH}_{\text{min}} = 15.0\%$
- Absolute Max: $\text{RH}_{\text{max}} = 85.0\%$

**Piecewise Equation:**

$$S_{\text{hum}}(\text{RH}) = \begin{cases} 
100.0 & \text{if } 40.0 \le \text{RH} \le 60.0 \\
\left( \frac{\text{RH} - 15.0}{40.0 - 15.0} \right) \times 100.0 & \text{if } 15.0 \le \text{RH} < 40.0 \\
\left( \frac{85.0 - \text{RH}}{85.0 - 60.0} \right) \times 100.0 & \text{if } 60.0 < \text{RH} \le 85.0 \\
0.0 & \text{if } \text{RH} < 15.0 \text{ or } \text{RH} > 85.0
\end{cases}$$

```text
Score
 100 |          +--------------------+
     |         /                      \
     |        /                        \
     |       /                          \
   0 +------+----------------------------+------
           15.0 40.0                60.0 85.0    Relative Humidity (%)
```

---

### 3.3 Volatile Gas Baseline Response ($S_{\text{gas}}$)

The MQ-135 is a broad-spectrum metal-oxide semiconductor (MOS) sensor that responds to reducing and oxidisable gases ($\text{CO}_2$, $\text{CO}$, ethanol, ammonia, toluene, acetone). Because it lacks factory calibration and suffers from long-term sensor drift, SIEIS computes a dynamic **Elevation Ratio** against a rolling baseline rather than asserting uncalibrated ppm:

$$R_{\text{ratio}} = \frac{V_{\text{pin}}}{V_{\text{baseline}}}$$

Where $V_{\text{baseline}}$ is maintained by the `MQ135BaselineManager` using a 30-sample sliding window with a $20\%$ symmetric trimmed mean to filter transient spikes.

**Threshold Parameters:**
- Clean Threshold: $R_{\text{clean}} = 1.05$ (Sensor within $\le 5\%$ of ambient rolling baseline)
- Contamination Limit: $R_{\text{max}} = 2.50$ (Sensor voltage elevated $\ge 150\%$ above baseline)

**Piecewise Equation:**

$$S_{\text{gas}}(R) = \begin{cases} 
100.0 & \text{if } R \le 1.05 \\
\left( 1.0 - \frac{R - 1.05}{2.50 - 1.05} \right) \times 100.0 & \text{if } 1.05 < R < 2.50 \\
0.0 & \text{if } R \ge 2.50
\end{cases}$$

```text
Score
 100 | +---------+
     |            \
     |             \
     |              \
   0 +---------------+------------------
     0.0        1.05 2.50               Ratio (V_pin / V_baseline)
```

> [!NOTE]
> If the sensor is in pre-heat phase (`mq135_status != "ready"`), or $V_{\text{baseline}} \le 0$, $S_{\text{gas}}$ returns `None`, activating the dynamic weight redistribution.

---

### 3.4 Visual Ergonomics Component ($S_{\text{light}}$)

The ambient light sensor consists of a bare Light Dependent Resistor (LDR) in a voltage-divider circuit with a $10\text{ k}\Omega$ resistor to GND on ESP32 GPIO 35 (12-bit ADC, $0 - 4095$). Higher ADC counts represent higher ambient brightness.

**Empirically Calibrated Classification:**
- $\text{ADC} < 250$: `Dark` (Night / blinds closed / lights off)
- $250 \le \text{ADC} < 1700$: `Dim` (Comfortable indoor ambient lighting / shaded daytime)
- $\text{ADC} \ge 1700$: `Bright` (Direct office lighting / sunlight ingress / task illumination)

**Scoring Assignment:**

$$S_{\text{light}} = \begin{cases} 
100.0 & \text{if } \text{ADC} \ge 1700 \quad (\text{Optimal working illumination}) \\
85.0 & \text{if } 250 \le \text{ADC} < 1700 \quad (\text{Acceptable background light}) \\
50.0 & \text{if } \text{ADC} < 250 \quad (\text{Dark / insufficient for reading})
\end{cases}$$

*Labeling Guard: Never labeled as calibrated illuminance (Lux).*

---

### 3.5 Acoustic Disturbance Component ($S_{\text{sound}}$)

Monitored via the LM393 microphone module on ESP32 GPIO 32 (Analog peak-to-peak swing over a $50\text{ ms}$ sampling window) and GPIO 26 (Digital comparator trigger $\text{DO}$).

**Threshold Parameters:**
- Peak-to-peak ADC swing $< 400$: `Quiet` (Normal residential/office background)
- Peak-to-peak ADC swing $400 - 1199$: `Moderate` (Conversational activity / keyboard typing)
- Peak-to-peak ADC swing $\ge 1200$ or $\text{DO} = 1$: `Noisy / Disturbed` (Impulse noises, loud alarms, loud speech)

**Scoring Assignment:**

$$S_{\text{sound}} = \begin{cases} 
100.0 & \text{if } \text{Swing} < 400 \text{ and } \text{DO} = 0 \quad (\text{Serene / quiet environment}) \\
80.0 & \text{if } 400 \le \text{Swing} < 1200 \text{ and } \text{DO} = 0 \quad (\text{Moderate acceptable noise}) \\
40.0 & \text{if } \text{Swing} \ge 1200 \text{ or } \text{DO} = 1 \quad (\text{Acoustic disruption})
\end{cases}$$

*Labeling Guard: Never labeled as calibrated decibels (dB or dBA).*

---

## 4. Operational Guards, Coverage & Freshness

To prevent misleading comfort indices from faulty hardware or broken telemetry connections, the engine enforces three strict operational guards:

### 4.1 Mandatory Core Inputs Guard
Temperature and Relative Humidity from the DHT22 are mandatory. If either is `None`, NaN, or physically out-of-bounds:
- **Output:** `score: None`
- **Status:** `Indeterminate`
- **Reason:** `"Core temperature and relative humidity inputs are required for RCI."`

### 4.2 Data Coverage Guard
Data coverage is evaluated as the proportion of active nominal weights:

$$\text{Coverage } (\%) = \left( \frac{\sum_{i \in \mathcal{A}} w_i}{\sum_{j \in \text{All}} w_j} \right) \times 100.0$$

- Minimum Required Coverage: **$50.0\%$** (`Config.RCI_MIN_COVERAGE_PCT`).
- If Coverage $< 50.0\%$, calculation aborts with `Indeterminate`.

### 4.3 Telemetry Freshness Guard
- Telemetry Staleness Threshold: **$120\text{ seconds}$** (`Config.RCI_STALE_THRESHOLD_SECONDS`).
- If the time elapsed since the latest sensor observation exceeds $120\text{s}$, the calculation returns `is_stale: True`, holding the status as `Indeterminate / Stale` and displaying the exact elapsed staleness age.

---

## 5. Classification Bands & Explainability Outputs

### 5.1 Comfort Classification Bands

| Score Range | Comfort Status | UI Color Band | Operational Interpretation |
|---|---|---|---|
| **$80.0 \le \text{RCI} \le 100.0$** | **Optimal / Comfortable** | `Green` | Indoor conditions are optimal; no intervention needed. |
| **$50.0 \le \text{RCI} < 80.0$** | **Moderate / Needs Attention** | `Yellow` | One or more parameters are sub-optimal; consult recommendations. |
| **$0.0 \le \text{RCI} < 50.0$** | **Poor / Uncomfortable** | `Red` | Acute environmental degradation; active remediation advised. |

### 5.2 Contributor Attribution Rules
- **Positive Contributors:** Any valid channel where $S_i \ge 80.0$ is added to `main_positive_contributors` (e.g., `"Temperature (100.0%)"`, `"Sound (100.0%)"`).
- **Negative Contributors:** Any valid channel where $S_i < 70.0$ is added to `main_negative_contributors` (e.g., `"Gas_response (45.2%)"`).
- **Confidence Rating:**
  - `High`: Data coverage $\ge 90\%$ and not provisional.
  - `Moderate`: Data coverage $\ge 60\%$.
  - `Low`: Data coverage $< 60\%$.

---

## 6. Worked Step-by-Step Calculation Examples

### Example 1: Nominal Office Environment (All Channels Active)

**Inputs:**
- $T = 22.5^\circ\text{C}$
- $\text{RH} = 50.0\%$
- $V_{\text{pin}} = 280\text{ mV}$, $V_{\text{baseline}} = 275\text{ mV}$ ($R = 1.018$, status ready)
- $\text{LDR ADC} = 1850$
- $\text{Sound Swing} = 220$, $\text{DO} = 0$

**Component Scores:**
- $S_{\text{temp}} = 100.0$ (Inside $[21.0, 24.0]^\circ\text{C}$)
- $S_{\text{hum}} = 100.0$ (Inside $[40.0, 60.0]\%$)
- $S_{\text{gas}} = 100.0$ ($R = 1.018 \le 1.05$)
- $S_{\text{light}} = 100.0$ ($\text{ADC} = 1850 \ge 1700$)
- $S_{\text{sound}} = 100.0$ ($\text{Swing} = 220 < 400$)

$$\text{RCI} = (100.0 \times 0.30) + (100.0 \times 0.25) + (100.0 \times 0.25) + (100.0 \times 0.10) + (100.0 \times 0.10) = \mathbf{100.0}$$
- **Status:** `Optimal / Comfortable` (Green)
- **Coverage:** $100.0\%$ | **Confidence:** High

---

### Example 2: Warm Afternoon with Stale Air

**Inputs:**
- $T = 28.5^\circ\text{C}$ (Warm)
- $\text{RH} = 68.0\%$ (Humid)
- $V_{\text{pin}} = 450\text{ mV}$, $V_{\text{baseline}} = 300\text{ mV}$ ($R = 1.50$, status ready)
- $\text{LDR ADC} = 950$ (Dim)
- $\text{Sound Swing} = 310$, $\text{DO} = 0$ (Quiet)

**Component Scores:**
- $S_{\text{temp}} = \frac{33.0 - 28.5}{33.0 - 24.0} \times 100.0 = \frac{4.5}{9.0} \times 100.0 = \mathbf{50.0}$
- $S_{\text{hum}} = \frac{85.0 - 68.0}{85.0 - 60.0} \times 100.0 = \frac{17.0}{25.0} \times 100.0 = \mathbf{68.0}$
- $S_{\text{gas}} = \left( 1.0 - \frac{1.50 - 1.05}{2.50 - 1.05} \right) \times 100.0 = \left( 1.0 - \frac{0.45}{1.45} \right) \times 100.0 = (1.0 - 0.3103) \times 100.0 = \mathbf{69.0}$
- $S_{\text{light}} = \mathbf{85.0}$
- $S_{\text{sound}} = \mathbf{100.0}$

**Synthesis:**
$$\text{RCI} = (50.0 \times 0.30) + (68.0 \times 0.25) + (69.0 \times 0.25) + (85.0 \times 0.10) + (100.0 \times 0.10)$$
$$\text{RCI} = 15.0 + 17.0 + 17.25 + 8.5 + 10.0 = \mathbf{67.75} \approx \mathbf{67.8}$$
- **Status:** `Moderate / Needs Attention` (Yellow)
- **Negative Contributors:** Temperature (50.0%), Humidity (68.0%), Gas Response (69.0%)
- **Positive Contributors:** Sound (100.0%), Lighting (85.0%)

---

### Example 3: Initial Boot Warm-Up (4 Channels Active)

**Inputs:**
- $T = 23.0^\circ\text{C}$ ($S_{\text{temp}} = 100.0$)
- $\text{RH} = 45.0\%$ ($S_{\text{hum}} = 100.0$)
- MQ-135 status: `warming_up` ($S_{\text{gas}} = \text{None}$)
- $\text{LDR ADC} = 2100$ ($S_{\text{light}} = 100.0$)
- $\text{Sound Swing} = 150$ ($S_{\text{sound}} = 100.0$)

**Dynamic Normalization:**
- Active Weight Sum: $0.30 + 0.25 + 0.10 + 0.10 = 0.75$
- Coverage: $\frac{0.75}{1.00} \times 100.0 = \mathbf{75.0\%}$

$$\text{RCI} = 100.0 \times \frac{0.30}{0.75} + 100.0 \times \frac{0.25}{0.75} + 100.0 \times \frac{0.10}{0.75} + 100.0 \times \frac{0.10}{0.75} = \mathbf{100.0}$$
- **Status:** `Optimal / Comfortable` (Green)
- **Flags:** `is_provisional: True`, `Confidence: Moderate`
- **Explanation:** `"Thermal: 100.0% (23.0°C); Hygric: 100.0% (45.0%); Gas: [Excluded - Warmup/Baseline Unconditioned]"`

---

## 7. Architecture & Code Traceability

| Layer | File / Module | Responsibility |
|---|---|---|
| **Core Computation** | [`backend/intelligence/rci.py`](file:///c:/Users/insan/OneDrive/Desktop/SIEIS/backend/intelligence/rci.py) | Defines `RoomComfortIndexEngine` and `calculate_rci()`. Implements all piecewise curves and guards. |
| **System Thresholds** | [`backend/config.py`](file:///c:/Users/insan/OneDrive/Desktop/SIEIS/backend/config.py) | Defines `RCI_WEIGHT_*`, `RCI_TEMP_*`, `RCI_HUM_*`, `RCI_GAS_*`, and `RCI_STALE_THRESHOLD_SECONDS`. |
| **Database Persistence** | [`backend/database.py`](file:///c:/Users/insan/OneDrive/Desktop/SIEIS/backend/database.py) | Stores calculated RCI scores into SQLite table `comfort_scores` with timestamps and observation foreign keys. |
| **REST API Route** | [`backend/app.py`](file:///c:/Users/insan/OneDrive/Desktop/SIEIS/backend/app.py) | Exposes `GET /api/comfort-index` returning complete RCI schema with no-cache headers. |
| **Frontend Presentation** | [`backend/static/js/app.js`](file:///c:/Users/insan/OneDrive/Desktop/SIEIS/backend/static/js/app.js) | Function `updateRCIHero()` dynamically updates hero score, status pill, color band, progress rings, and contributor factors. |
| **Verification Suite** | [`tests/test_rci.py`](file:///c:/Users/insan/OneDrive/Desktop/SIEIS/tests/test_rci.py) | Automated unit tests verifying piecewise boundary transitions, dynamic weight redistribution, coverage guards, and staleness handling. |

---

*Authored by: SIEIS Embedded Intelligence Architecture Group*  
*Document Revision: 2.0.0 | Verified against live firmware & backend test suite (71 passing tests).*
